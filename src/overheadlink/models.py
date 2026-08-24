from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BoardKind(StrEnum):
    MEGA = "mega2560"
    BACKLIGHT_NANO = "backlight_nano"


class PinMode(StrEnum):
    DIGITAL_INPUT = "digital_input"
    ANALOG_INPUT = "analog_input"
    DIGITAL_OUTPUT = "digital_output"
    WS2812_DATA = "ws2812_data"


class AssignmentRole(StrEnum):
    SWITCH = "switch"
    SELECTOR_POSITION = "selector_position"
    ROTARY_CONTACT = "rotary_contact"
    POTENTIOMETER = "potentiometer"
    LED_UPPER = "led_upper"
    LED_LOWER = "led_lower"
    LED_SINGLE = "led_single"
    BACKLIGHT_DATA = "backlight_data"


class VerificationStatus(StrEnum):
    CONFIRMED = "confirmed"
    REVISED = "revised"
    NEEDS_VERIFICATION = "needs_verification"
    AUTO_LEARNED = "auto_learned"
    SUPERSEDED = "superseded"


def pin_number(pin: str) -> int:
    pin = pin.strip().upper()
    if pin.startswith("D"):
        value = int(pin[1:])
        if not 0 <= value <= 53:
            raise ValueError(f"Mega digital pin out of range: {pin}")
        return value
    if pin.startswith("A"):
        channel = int(pin[1:])
        if not 0 <= channel <= 15:
            raise ValueError(f"Mega analogue channel out of range: {pin}")
        return 54 + channel
    raise ValueError(f"Unsupported pin name: {pin}")


def canonical_pin(pin: str | int) -> str:
    if isinstance(pin, str):
        pin = pin_number(pin)
    if 0 <= pin <= 53:
        return f"D{pin}"
    if 54 <= pin <= 69:
        return f"A{pin - 54}"
    raise ValueError(f"Mega pin out of range: {pin}")


@dataclass(slots=True)
class SimulatorBinding:
    on_press: str | None = None
    on_release: str | None = None
    feedback: str | None = None
    feedback_true_when: str | None = None
    verified: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "SimulatorBinding":
        raw = raw or {}
        return cls(
            on_press=raw.get("onPress"),
            on_release=raw.get("onRelease"),
            feedback=raw.get("feedback"),
            feedback_true_when=raw.get("feedbackTrueWhen"),
            verified=bool(raw.get("verified", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"verified": self.verified}
        if self.on_press:
            result["onPress"] = self.on_press
        if self.on_release:
            result["onRelease"] = self.on_release
        if self.feedback:
            result["feedback"] = self.feedback
        if self.feedback_true_when:
            result["feedbackTrueWhen"] = self.feedback_true_when
        return result


@dataclass(slots=True)
class PinAssignment:
    id: str
    control: str
    pin: str
    mode: PinMode
    role: AssignmentRole
    status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    enabled: bool = True
    active_low: bool = True
    debounce_ms: int = 35
    notes: str = ""
    source_revision: str = ""
    sim: SimulatorBinding = field(default_factory=SimulatorBinding)
    calibration: dict[str, float | int | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pin = canonical_pin(self.pin)
        if self.debounce_ms < 0 or self.debounce_ms > 1000:
            raise ValueError(f"Invalid debounce for {self.id}: {self.debounce_ms}")

    @property
    def numeric_pin(self) -> int:
        return pin_number(self.pin)

    @property
    def is_output(self) -> bool:
        return self.mode in {PinMode.DIGITAL_OUTPUT, PinMode.WS2812_DATA}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PinAssignment":
        return cls(
            id=str(raw["id"]),
            control=str(raw["control"]),
            pin=str(raw["pin"]),
            mode=PinMode(raw["mode"]),
            role=AssignmentRole(raw["role"]),
            status=VerificationStatus(raw.get("status", "needs_verification")),
            enabled=bool(raw.get("enabled", True)),
            active_low=bool(raw.get("activeLow", True)),
            debounce_ms=int(raw.get("debounceMs", 35)),
            notes=str(raw.get("notes", "")),
            source_revision=str(raw.get("sourceRevision", "")),
            sim=SimulatorBinding.from_dict(raw.get("sim")),
            calibration=dict(raw.get("calibration", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "control": self.control,
            "pin": self.pin,
            "mode": self.mode.value,
            "role": self.role.value,
            "status": self.status.value,
            "enabled": self.enabled,
            "activeLow": self.active_low,
            "debounceMs": self.debounce_ms,
            "sourceRevision": self.source_revision,
            "sim": self.sim.to_dict(),
        }
        if self.notes:
            result["notes"] = self.notes
        if self.calibration:
            result["calibration"] = self.calibration
        return result


@dataclass(slots=True)
class BoardProfile:
    id: str
    name: str
    kind: BoardKind
    optional: bool = False
    assignments: list[PinAssignment] = field(default_factory=list)
    expected_hardware: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BoardProfile":
        return cls(
            id=str(raw["id"]),
            name=str(raw["name"]),
            kind=BoardKind(raw["kind"]),
            optional=bool(raw.get("optional", False)),
            expected_hardware=str(raw.get("expectedHardware", "")),
            assignments=[PinAssignment.from_dict(item) for item in raw.get("assignments", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "optional": self.optional,
            "expectedHardware": self.expected_hardware,
            "assignments": [assignment.to_dict() for assignment in self.assignments],
        }

    def assignment(self, assignment_id: str) -> PinAssignment | None:
        return next((item for item in self.assignments if item.id == assignment_id), None)


@dataclass(slots=True)
class OverheadProfile:
    schema_version: int
    profile_id: str
    name: str
    aircraft: str
    boards: list[BoardProfile]
    backlighting: dict[str, Any] = field(default_factory=dict)
    change_log: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "OverheadProfile":
        return cls(
            schema_version=int(raw["schemaVersion"]),
            profile_id=str(raw["profileId"]),
            name=str(raw["name"]),
            aircraft=str(raw["aircraft"]),
            boards=[BoardProfile.from_dict(board) for board in raw.get("boards", [])],
            backlighting=dict(raw.get("backlighting", {})),
            change_log=list(raw.get("changeLog", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "profileId": self.profile_id,
            "name": self.name,
            "aircraft": self.aircraft,
            "boards": [board.to_dict() for board in self.boards],
            "backlighting": self.backlighting,
            "changeLog": self.change_log,
        }

    def board(self, board_id: str) -> BoardProfile | None:
        return next((board for board in self.boards if board.id == board_id), None)

