from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


PROFILE_FILENAME = "a320_fenix_overhead.json"
SPLIT_MIGRATION_ID = "0.3.7-hydfuel-split"
PERIPHERAL_MIGRATION_ID = "0.3.8-tm1637-peripheral"
BAT2_SIM_EXPRESSION = "(A:ELECTRICAL BATTERY VOLTAGE:2, Volts)"


HYD_FUEL_PIN_MAP = {
    "fuel.left1.upper": "D10",
    "fuel.left1.lower": "D11",
    "fuel.left1.switch": "D9",
    "fuel.left2.upper": "D8",
    "fuel.left2.lower": "D7",
    "fuel.left2.switch": "D6",
    "fuel.center1.upper": "D5",
    "fuel.center1.lower": "D4",
    "fuel.center1.switch": "D3",
    "fuel.center2.upper": "D14",
    "fuel.center2.lower": "D15",
    "fuel.center2.switch": "D2",
    "fuel.right1.upper": "D16",
    "fuel.right1.lower": "D17",
    "fuel.right1.switch": "D18",
    "fuel.right2.upper": "D19",
    "fuel.right2.lower": "D20",
    "fuel.right2.switch": "D21",
    "hyd.eng2_pump.upper": "D22",
    "hyd.eng2_pump.lower": "D23",
    "hyd.eng2_pump.switch": "D25",
    "fuel.xfeed.upper": "D26",
    "fuel.xfeed.lower": "D28",
    "fuel.xfeed.switch": "D27",
    "hyd.eng1_pump.upper": "D31",
    "hyd.eng1_pump.lower": "D33",
    "hyd.eng1_pump.switch": "D30",
}


def data_root() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "OverheadLink"
    else:
        root = Path.home() / ".config" / "OverheadLink"
    root.mkdir(parents=True, exist_ok=True)
    return root


def bundled_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def writable_profile_path() -> Path:
    target = data_root() / "profiles" / PROFILE_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(bundled_root() / "profiles" / PROFILE_FILENAME, target)
    return target


def _has_migration(payload: dict[str, Any], migration_id: str) -> bool:
    return any(
        isinstance(entry, dict) and entry.get("migration") == migration_id
        for entry in payload.get("changeLog", [])
    )


def _append_migration(payload: dict[str, Any], migration_id: str, reason: str) -> None:
    if _has_migration(payload, migration_id):
        return
    payload.setdefault("changeLog", []).append(
        {
            "timestampUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": reason,
            "migration": migration_id,
        }
    )


def _idg1_assignment() -> dict[str, Any]:
    return {
        "id": "elec.idg1.switch",
        "control": "IDG 1 switch",
        "pin": "D6",
        "mode": "digital_input",
        "role": "switch",
        "status": "revised",
        "enabled": True,
        "activeLow": True,
        "debounceMs": 35,
        "sourceRevision": "User confirmed 2026-08-24",
        "sim": {
            "verified": True,
            "onPress": "(L:S_OH_ELEC_IDG1) ++ (>L:S_OH_ELEC_IDG1)",
            "onRelease": "(L:S_OH_ELEC_IDG1) s0 2 % 0 != if{ l0 ++ (>L:S_OH_ELEC_IDG1) }",
        },
        "notes": "IDG 1 switch moved to D6 on the dedicated ELEC Mega.",
    }


def _battery2_display() -> dict[str, Any]:
    return {
        "id": "elec.bat2_voltage_display",
        "type": "tm1637_4digit",
        "name": "BATTERY 2 voltage display",
        "clk": "A2",
        "dio": "A3",
        "status": "confirmed",
        "sourceRevision": "User confirmed 2026-08-24; driver added 0.3.8",
        "simExpression": BAT2_SIM_EXPRESSION,
        "brightness": 7,
        "minimumValue": 10.0,
        "maximumValue": 40.0,
        "decimals": 1,
        "notes": (
            "ELEC Mega TM1637. CLK=A2, DIO=A3. Uses the documented MSFS battery-2 voltage SimVar; "
            "implausible/unavailable values are shown as dashes rather than guessed."
        ),
    }


def _ensure_idg1(elec: dict[str, Any]) -> bool:
    assignments = elec.setdefault("assignments", [])
    existing = next(
        (item for item in assignments if isinstance(item, dict) and item.get("id") == "elec.idg1.switch"),
        None,
    )
    desired = _idg1_assignment()
    if existing is None:
        assignments.append(desired)
        return True
    changed = False
    for key, value in desired.items():
        if existing.get(key) != value:
            existing[key] = value
            changed = True
    return changed


def _ensure_battery_display(elec: dict[str, Any]) -> bool:
    peripherals = elec.setdefault("peripherals", [])
    existing = next(
        (item for item in peripherals if isinstance(item, dict) and item.get("id") == "elec.bat2_voltage_display"),
        None,
    )
    desired = _battery2_display()
    if existing is None:
        peripherals.append(desired)
        return True
    changed = False
    for key, value in desired.items():
        if existing.get(key) != value:
            existing[key] = value
            changed = True
    return changed


def _apply_hyd_map(hyd: dict[str, Any]) -> bool:
    changed = False
    for assignment in hyd.get("assignments", []):
        if not isinstance(assignment, dict):
            continue
        assignment_id = str(assignment.get("id", ""))
        pin = HYD_FUEL_PIN_MAP.get(assignment_id)
        if pin and assignment.get("pin") != pin:
            assignment["pin"] = pin
            assignment["status"] = "revised"
            assignment["sourceRevision"] = "Dedicated HYD/FUEL Mega confirmed 2026-08-24"
            changed = True
    return changed


def migrate_profile(payload: dict[str, Any]) -> bool:
    boards = payload.get("boards", [])
    if not isinstance(boards, list):
        raise ValueError("Profile boards must be a list")
    changed = False

    combined_index = next(
        (index for index, board in enumerate(boards) if isinstance(board, dict) and board.get("id") == "elec-hyd-fuel"),
        None,
    )
    if combined_index is not None:
        combined = boards[combined_index]
        assignments = list(combined.get("assignments", []))
        elec_assignments: list[dict[str, Any]] = []
        hyd_assignments: list[dict[str, Any]] = []
        for assignment in assignments:
            if not isinstance(assignment, dict):
                continue
            assignment_id = str(assignment.get("id", ""))
            if (assignment_id.startswith("fuel.") or assignment_id.startswith("hyd.")) and not assignment_id.startswith("hyd.elec_pump."):
                hyd_assignments.append(assignment)
            else:
                elec_assignments.append(assignment)

        elec = dict(combined)
        elec["id"] = "elec"
        elec["name"] = "ELEC"
        elec["assignments"] = elec_assignments
        elec["peripherals"] = list(elec.get("peripherals", []))
        hyd = {
            "id": "hyd-fuel",
            "name": "HYD-FUEL",
            "kind": combined.get("kind", "mega2560"),
            "optional": False,
            "expectedHardware": combined.get("expectedHardware", "Arduino Mega 2560"),
            "assignments": hyd_assignments,
        }
        boards[combined_index : combined_index + 1] = [elec, hyd]
        changed = True
        _append_migration(
            payload,
            SPLIT_MIGRATION_ID,
            "Split ELEC and HYD/FUEL Megas and apply the confirmed 2026-08-24 HYD/FUEL pin map",
        )

    elec = next((board for board in boards if isinstance(board, dict) and board.get("id") == "elec"), None)
    hyd = next((board for board in boards if isinstance(board, dict) and board.get("id") == "hyd-fuel"), None)
    if hyd is not None:
        changed = _apply_hyd_map(hyd) or changed
    if elec is not None:
        changed = _ensure_idg1(elec) or changed
        changed = _ensure_battery_display(elec) or changed
        if not _has_migration(payload, PERIPHERAL_MIGRATION_ID):
            _append_migration(
                payload,
                PERIPHERAL_MIGRATION_ID,
                "Add persistent TM1637 BATTERY 2 voltage display on ELEC A2/A3 and reserve its pins",
            )
            changed = True

    return changed


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        # Verify the complete JSON before replacing the live copy.
        json.loads(temporary.read_text(encoding="utf-8"))
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def prepare_profile() -> Path:
    path = writable_profile_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if migrate_profile(payload):
        backup = path.with_name(path.stem + "_pre_0.3.8_backup" + path.suffix)
        if not backup.exists():
            shutil.copy2(path, backup)
        _write_payload(path, payload)
    return path
