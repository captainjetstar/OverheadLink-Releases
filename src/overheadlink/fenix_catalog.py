from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .models import PinMode


CATALOG_FILENAME = "fenix_a320_overhead_hubhop.json"


@dataclass(frozen=True, slots=True)
class FenixAction:
    id: str
    path: str
    system: str
    label: str
    code: str
    preset_type: str
    status: str
    version: int
    author: str
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "FenixAction":
        return cls(
            id=str(raw["id"]),
            path=str(raw["path"]),
            system=str(raw["system"]),
            label=str(raw["label"]),
            code=str(raw["code"]).strip(),
            preset_type=str(raw["presetType"]),
            status=str(raw.get("status", "")),
            version=int(raw.get("version", 1)),
            author=str(raw.get("author", "MobiFlight Community")),
            description=str(raw.get("description", "")),
        )

    def compatible_with(self, mode: PinMode) -> bool:
        if mode == PinMode.DIGITAL_INPUT:
            return self.preset_type == "Input"
        if mode == PinMode.ANALOG_INPUT:
            return self.preset_type == "Input (Potentiometer)"
        if mode == PinMode.DIGITAL_OUTPUT:
            return self.preset_type == "Output"
        return False


@dataclass(frozen=True, slots=True)
class FenixActionCatalog:
    source: str
    snapshot_utc: str
    actions: tuple[FenixAction, ...]

    @classmethod
    def load(cls, path: Path) -> "FenixActionCatalog":
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        actions = tuple(FenixAction.from_dict(item) for item in raw.get("actions", []))
        if not actions:
            raise ValueError("The Fenix action catalogue is empty")
        ids = {action.id for action in actions}
        if len(ids) != len(actions):
            raise ValueError("The Fenix action catalogue contains duplicate IDs")
        if any(not action.code for action in actions):
            raise ValueError("The Fenix action catalogue contains a blank RPN expression")
        return cls(
            source=str(raw.get("source", "MobiFlight HubHop")),
            snapshot_utc=str(raw.get("snapshotUtc", "")),
            actions=actions,
        )

    def action(self, action_id: str) -> FenixAction | None:
        return next((action for action in self.actions if action.id == action_id), None)

    @property
    def systems(self) -> tuple[str, ...]:
        return tuple(sorted({action.system for action in self.actions}, key=str.casefold))

    @property
    def input_count(self) -> int:
        return sum(action.preset_type != "Output" for action in self.actions)

    @property
    def output_count(self) -> int:
        return sum(action.preset_type == "Output" for action in self.actions)
