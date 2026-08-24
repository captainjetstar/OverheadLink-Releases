from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Iterable

from .models import BoardKind, OverheadProfile, PinAssignment, PinMode, PeripheralType, VerificationStatus, pin_number


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
            used: dict[int, tuple[str, str]] = {}
            assignment_ids: set[str] = set()
            for assignment in board.assignments:
                if assignment.id in assignment_ids:
                    issues.append(ValidationIssue("error", board.id, assignment.id, "Duplicate assignment id"))
                assignment_ids.add(assignment.id)
                if not assignment.enabled or assignment.status == VerificationStatus.SUPERSEDED:
                    continue
                numeric = assignment.numeric_pin
                if numeric in used:
                    other_control, other_id = used[numeric]
                    issues.append(
                        ValidationIssue(
                            "error",
                            board.id,
                            assignment.id,
                            f"{assignment.pin} also belongs to {other_control} / {other_id}",
                        )
                    )
                else:
                    used[numeric] = (assignment.control, assignment.id)
                if board.kind == BoardKind.MEGA and numeric in {0, 1}:
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

            peripheral_ids: set[str] = set()
            for peripheral in board.peripherals:
                if peripheral.id in peripheral_ids:
                    issues.append(ValidationIssue("error", board.id, peripheral.id, "Duplicate peripheral id"))
                peripheral_ids.add(peripheral.id)
                if board.kind != BoardKind.MEGA:
                    issues.append(ValidationIssue("error", board.id, peripheral.id, "Hardware peripherals require a Mega 2560"))
                if peripheral.peripheral_type == PeripheralType.TM1637_4DIGIT:
                    if set(peripheral.pins) != {"clk", "dio"}:
                        issues.append(ValidationIssue("error", board.id, peripheral.id, "TM1637 requires exactly CLK and DIO pins"))
                    if peripheral.pins.get("clk") == peripheral.pins.get("dio"):
                        issues.append(ValidationIssue("error", board.id, peripheral.id, "TM1637 CLK and DIO cannot share a pin"))
                for role, pin in peripheral.pins.items():
                    numeric = pin_number(pin)
                    if numeric in {0, 1}:
                        issues.append(ValidationIssue("error", board.id, peripheral.id, f"{pin} is reserved for USB serial"))
                    if numeric in used:
                        other_control, other_id = used[numeric]
                        issues.append(
                            ValidationIssue(
                                "error",
                                board.id,
                                peripheral.id,
                                f"Peripheral {role.upper()} {pin} conflicts with {other_control} / {other_id}",
                            )
                        )
                    else:
                        used[numeric] = (f"{peripheral.name} {role.upper()}", peripheral.id)
                if peripheral.sim_expression and "\x00" in peripheral.sim_expression:
                    issues.append(ValidationIssue("error", board.id, peripheral.id, "Peripheral simulator expression contains NUL"))

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
        issues = [issue for issue in ProfileValidator().validate(profile) if issue.level == "error"]
        if issues:
            detail = "; ".join(f"{issue.board_id}: {issue.message}" for issue in issues[:5])
            raise ValueError(f"Profile contains validation errors: {detail}")
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
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(profile.to_dict(), handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
            # Parse the temporary copy before replacing the user's live profile.
            with temp.open("r", encoding="utf-8") as handle:
                OverheadProfile.from_dict(json.load(handle))
            temp.replace(self.path)
        except Exception:
            temp.unlink(missing_ok=True)
            if profile.change_log and profile.change_log[-1].get("reason") == reason:
                profile.change_log.pop()
            raise
        return backup

    @staticmethod
    def _ensure_candidate_allowed(target, candidate: str, assignment: PinAssignment) -> None:
        if candidate in {"D0", "D1"}:
            raise ValueError("D0 and D1 are reserved for Mega USB serial communication")
        if assignment.mode == PinMode.ANALOG_INPUT and not candidate.startswith("A"):
            raise ValueError("An analogue input must be assigned to A0-A15")
        if candidate in target.reserved_pins:
            owner = next(
                peripheral for peripheral in target.peripherals if candidate in peripheral.pins.values()
            )
            raise ValueError(f"{target.name} {candidate} is reserved by {owner.name}")

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
        self._ensure_candidate_allowed(target, candidate, assignment)
        for other in target.assignments:
            if other is assignment or not other.enabled or other.status == VerificationStatus.SUPERSEDED:
                continue
            if other.pin == candidate:
                raise ValueError(f"{target.name} {candidate} is already assigned to {other.control} / {other.id}")
        if debounce_ms is not None and not 0 <= debounce_ms <= 1000:
            raise ValueError("Debounce must be between 0 and 1000 milliseconds")

        old_board_name = source.name
        old_values = (assignment.pin, assignment.active_low, assignment.debounce_ms, dict(assignment.calibration), assignment.status, assignment.notes)
        moved = source is not target
        if moved:
            source.assignments.remove(assignment)
            target.assignments.append(assignment)
        try:
            assignment.pin = candidate
            if active_low is not None:
                assignment.active_low = active_low
            if debounce_ms is not None:
                assignment.debounce_ms = debounce_ms
            if calibration is not None:
                assignment.calibration = dict(calibration)
            assignment.status = verification_status
            assignment.notes = (assignment.notes + " " + evidence).strip()
            reason = f"{assignment.control}: {old_board_name} {previous} -> {target.name} {candidate}; {evidence}"
            self.save(profile, reason)
        except Exception:
            if moved:
                target.assignments.remove(assignment)
                source.assignments.append(assignment)
            assignment.pin, assignment.active_low, assignment.debounce_ms, assignment.calibration, assignment.status, assignment.notes = old_values
            raise
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
        first_status, second_status = first.status, second.status
        first_notes, second_notes = first.notes, second.notes
        first.pin, second.pin = second_pin, first_pin
        first.status = VerificationStatus.AUTO_LEARNED
        second.status = VerificationStatus.AUTO_LEARNED
        first.notes = (first.notes + " " + evidence).strip()
        second.notes = (second.notes + " " + evidence).strip()
        try:
            self.save(
                profile,
                f"Output pin swap on {board.name}: {first.control} {first_pin}->{second_pin}; "
                f"{second.control} {second_pin}->{first_pin}; {evidence}",
            )
        except Exception:
            first.pin, second.pin = first_pin, second_pin
            first.status, second.status = first_status, second_status
            first.notes, second.notes = first_notes, second_notes
            raise
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
        if not code or "\x00" in code:
            raise ValueError("The Fenix action does not contain a valid RPN expression")
        old_binding = assignment.sim.to_dict()
        old_status, old_source, old_notes = assignment.status, assignment.source_revision, assignment.notes
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
        try:
            self.save(profile, f"{assignment.control}: Fenix {slot} action updated; {evidence}")
        except Exception:
            from .models import SimulatorBinding
            assignment.sim = SimulatorBinding.from_dict(old_binding)
            assignment.status, assignment.source_revision, assignment.notes = old_status, old_source, old_notes
            raise
        return previous


def issue_summary(issues: Iterable[ValidationIssue]) -> tuple[int, int]:
    items = list(issues)
    return sum(i.level == "error" for i in items), sum(i.level == "warning" for i in items)
