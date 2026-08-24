from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Iterable

from .models import BoardKind, OverheadProfile, PinAssignment, PinMode, VerificationStatus


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    level: str
    board_id: str
    assignment_id: str | None
    message: str


class ProfileValidator:
    def validate(self, profile: OverheadProfile) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        board_ids: set[str] = set()
        for board in profile.boards:
            if board.id in board_ids:
                issues.append(ValidationIssue("error", board.id, None, "Duplicate board id"))
            board_ids.add(board.id)
            used: dict[int, PinAssignment] = {}
            assignment_ids: set[str] = set()
            for assignment in board.assignments:
                if assignment.id in assignment_ids:
                    issues.append(ValidationIssue("error", board.id, assignment.id, "Duplicate assignment id"))
                assignment_ids.add(assignment.id)
                if not assignment.enabled or assignment.status == VerificationStatus.SUPERSEDED:
                    continue
                if assignment.numeric_pin in used:
                    other = used[assignment.numeric_pin]
                    issues.append(
                        ValidationIssue(
                            "error",
                            board.id,
                            assignment.id,
                            f"{assignment.pin} also belongs to {other.control} / {other.id}",
                        )
                    )
                else:
                    used[assignment.numeric_pin] = assignment
                if board.kind == BoardKind.MEGA and assignment.numeric_pin in {0, 1}:
                    issues.append(ValidationIssue("error", board.id, assignment.id, "D0/D1 are reserved for USB serial"))
                if assignment.mode == PinMode.ANALOG_INPUT and not assignment.pin.startswith("A"):
                    issues.append(ValidationIssue("error", board.id, assignment.id, "Analogue input must use A0-A15"))
                if assignment.is_output and assignment.active_low:
                    issues.append(
                        ValidationIssue(
                            "warning",
                            board.id,
                            assignment.id,
                            "Output is marked active-low; verify the external driver polarity",
                        )
                    )
            if board.kind == BoardKind.BACKLIGHT_NANO:
                data = [a for a in board.assignments if a.enabled and a.mode == PinMode.WS2812_DATA]
                if len(data) != 1:
                    issues.append(ValidationIssue("error", board.id, None, "Backlight Nano requires exactly one WS2812 data pin"))
        return issues


class ProfileStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> OverheadProfile:
        with self.path.open("r", encoding="utf-8") as handle:
            return OverheadProfile.from_dict(json.load(handle))

    def save(self, profile: OverheadProfile, reason: str = "Profile updated") -> Path | None:
        backup: Path | None = None
        if self.path.exists():
            backup_dir = self.path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_dir / f"{self.path.stem}_{stamp}{self.path.suffix}"
            shutil.copy2(self.path, backup)
        profile.change_log.append(
            {
                "timestampUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "reason": reason,
            }
        )
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(profile.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temp.replace(self.path)
        return backup

    def repair_pin(
        self,
        profile: OverheadProfile,
        board_id: str,
        assignment_id: str,
        new_pin: str,
        evidence: str,
        *,
        active_low: bool | None = None,
    ) -> tuple[str, str]:
        _, previous, _, candidate = self.repair_assignment(
            profile,
            board_id,
            assignment_id,
            board_id,
            new_pin,
            evidence,
            active_low=active_low,
        )
        return previous, candidate

    def repair_assignment(
        self,
        profile: OverheadProfile,
        source_board_id: str,
        assignment_id: str,
        target_board_id: str,
        new_pin: str,
        evidence: str,
        *,
        active_low: bool | None = None,
        debounce_ms: int | None = None,
        calibration: dict[str, float | int | bool] | None = None,
        verification_status: VerificationStatus = VerificationStatus.AUTO_LEARNED,
    ) -> tuple[str, str, str, str]:
        source = profile.board(source_board_id)
        target = profile.board(target_board_id)
        if source is None:
            raise KeyError(f"Unknown board: {source_board_id}")
        if target is None:
            raise KeyError(f"Unknown board: {target_board_id}")
        if target.kind != BoardKind.MEGA:
            raise ValueError("Assignments can only be learned onto a Mega 2560 profile")
        assignment = source.assignment(assignment_id)
        if assignment is None:
            raise KeyError(f"Unknown assignment: {assignment_id}")
        previous = assignment.pin
        candidate = PinAssignment.from_dict({**assignment.to_dict(), "pin": new_pin}).pin
        if assignment.mode == PinMode.ANALOG_INPUT and not candidate.startswith("A"):
            raise ValueError("An analogue input must be assigned to A0-A15")
        for other in target.assignments:
            if other is assignment or not other.enabled or other.status == VerificationStatus.SUPERSEDED:
                continue
            if other.pin == candidate:
                raise ValueError(f"{target.name} {candidate} is already assigned to {other.control} / {other.id}")
        old_board_name = source.name
        if source is not target:
            source.assignments.remove(assignment)
            target.assignments.append(assignment)
        assignment.pin = candidate
        if active_low is not None:
            assignment.active_low = active_low
        if debounce_ms is not None:
            if not 0 <= debounce_ms <= 1000:
                raise ValueError("Debounce must be between 0 and 1000 milliseconds")
            assignment.debounce_ms = debounce_ms
        if calibration is not None:
            assignment.calibration = dict(calibration)
        assignment.status = verification_status
        assignment.notes = (assignment.notes + " " + evidence).strip()
        reason = f"{assignment.control}: {old_board_name} {previous} -> {target.name} {candidate}; {evidence}"
        self.save(profile, reason)
        return old_board_name, previous, target.name, candidate

    def swap_output_pins(
        self,
        profile: OverheadProfile,
        board_id: str,
        first_assignment_id: str,
        second_assignment_id: str,
        evidence: str,
    ) -> tuple[str, str]:
        board = profile.board(board_id)
        if board is None:
            raise KeyError(f"Unknown board: {board_id}")
        first = board.assignment(first_assignment_id)
        second = board.assignment(second_assignment_id)
        if first is None or second is None:
            raise KeyError("Unknown output assignment")
        if first.mode != PinMode.DIGITAL_OUTPUT or second.mode != PinMode.DIGITAL_OUTPUT:
            raise ValueError("Only two declared digital outputs can exchange pins")
        first_pin, second_pin = first.pin, second.pin
        first.pin, second.pin = second_pin, first_pin
        first.status = VerificationStatus.AUTO_LEARNED
        second.status = VerificationStatus.AUTO_LEARNED
        first.notes = (first.notes + " " + evidence).strip()
        second.notes = (second.notes + " " + evidence).strip()
        self.save(
            profile,
            f"Output pin swap on {board.name}: {first.control} {first_pin}->{second_pin}; "
            f"{second.control} {second_pin}->{first_pin}; {evidence}",
        )
        return first_pin, second_pin

    def assign_fenix_action(
        self,
        profile: OverheadProfile,
        board_id: str,
        assignment_id: str,
        slot: str,
        code: str,
        source_revision: str,
        evidence: str,
    ) -> str | None:
        board = profile.board(board_id)
        if board is None:
            raise KeyError(f"Unknown board: {board_id}")
        assignment = board.assignment(assignment_id)
        if assignment is None:
            raise KeyError(f"Unknown assignment: {assignment_id}")
        code = code.strip()
        if not code:
            raise ValueError("The Fenix action does not contain an RPN expression")
        if slot in {"press", "release"}:
            if assignment.mode not in {PinMode.DIGITAL_INPUT, PinMode.ANALOG_INPUT}:
                raise ValueError("Input actions can only be assigned to a physical input")
            if assignment.mode == PinMode.ANALOG_INPUT and slot != "press":
                raise ValueError("A potentiometer uses one value expression, not a release action")
            previous = assignment.sim.on_press if slot == "press" else assignment.sim.on_release
            if slot == "press":
                assignment.sim.on_press = code
            else:
                assignment.sim.on_release = code
        elif slot == "feedback":
            if assignment.mode != PinMode.DIGITAL_OUTPUT:
                raise ValueError("Feedback actions can only be assigned to an annunciator output")
            previous = assignment.sim.feedback
            assignment.sim.feedback = code
        else:
            raise ValueError(f"Unknown Fenix action slot: {slot}")
        assignment.sim.verified = True
        assignment.status = VerificationStatus.REVISED
        assignment.source_revision = source_revision
        assignment.notes = (assignment.notes + " " + evidence).strip()
        self.save(profile, f"{assignment.control}: Fenix {slot} action updated; {evidence}")
        return previous


def issue_summary(issues: Iterable[ValidationIssue]) -> tuple[int, int]:
    items = list(issues)
    return sum(i.level == "error" for i in items), sum(i.level == "warning" for i in items)
