from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from .bootstrap import writable_profile_path


MIGRATION_ID = "0.3.12-20260825-separate-hydfuel"

# Dedicated HYD/FUEL Mega. The six tank pumps retain their confirmed split-board
# pins; the entries below incorporate the later 2026-08-25 rewiring.
HYD_FUEL_PIN_MAP: dict[str, str] = {
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
    "fuel.xfeed.upper": "D43",
    "fuel.xfeed.lower": "D42",
    "fuel.xfeed.switch": "D38",
    "hyd.eng1_pump.upper": "D48",
    "hyd.eng1_pump.lower": "D49",
    "hyd.eng1_pump.switch": "D45",
    "hyd.elec_pump.upper": "D35",
    "hyd.elec_pump.lower": "D33",
}


def _has_migration(payload: dict[str, Any]) -> bool:
    return any(
        isinstance(entry, dict) and entry.get("migration") == MIGRATION_ID
        for entry in payload.get("changeLog", [])
    )


def _find_board(boards: list[Any], board_id: str) -> dict[str, Any] | None:
    return next(
        (board for board in boards if isinstance(board, dict) and board.get("id") == board_id),
        None,
    )


def _move_blue_elec_pump(elec: dict[str, Any], hyd: dict[str, Any]) -> bool:
    """Move the BLUE electrical-pump Korry to the dedicated HYD/FUEL board.

    The user supplied LED pins D35/D33 on 2026-08-25 but had not yet supplied
    the switch pin. We therefore keep the switch record for its Fenix binding
    but disable its old physical pin instead of guessing a replacement.
    """
    elec_assignments = elec.setdefault("assignments", [])
    hyd_assignments = hyd.setdefault("assignments", [])
    changed = False

    for assignment in list(elec_assignments):
        if not isinstance(assignment, dict):
            continue
        if str(assignment.get("id", "")).startswith("hyd.elec_pump."):
            elec_assignments.remove(assignment)
            if not any(
                isinstance(existing, dict) and existing.get("id") == assignment.get("id")
                for existing in hyd_assignments
            ):
                hyd_assignments.append(assignment)
            changed = True

    for assignment in hyd_assignments:
        if not isinstance(assignment, dict):
            continue
        assignment_id = str(assignment.get("id", ""))
        if assignment_id == "hyd.elec_pump.switch":
            if assignment.get("enabled") is not False:
                assignment["enabled"] = False
                changed = True
            desired = {
                "status": "needs_verification",
                "sourceRevision": "User confirmed 2026-08-25; switch pin not yet supplied",
                "notes": "Dedicated HYD/FUEL Mega. BLUE ELEC PUMP switch intentionally disabled until its new physical pin is confirmed.",
            }
            for key, value in desired.items():
                if assignment.get(key) != value:
                    assignment[key] = value
                    changed = True
    return changed


def _eng_elec_pump_assignments() -> list[dict[str, Any]]:
    # The physical control was dictated as "ENG ELEC PUMP". Its pin mapping is
    # recorded exactly as supplied. No Fenix expression is guessed here; the
    # app's Fenix action picker can bind it once the exact simulator action is
    # positively identified.
    common = {
        "status": "confirmed",
        "enabled": True,
        "debounceMs": 35,
        "sourceRevision": "User confirmed 2026-08-25",
        "notes": "Dedicated HYD/FUEL Mega; physical label dictated as ENG ELEC PUMP.",
    }
    return [
        {
            "id": "hyd.eng_elec_pump.upper",
            "control": "HYD ENG ELEC PUMP upper annunciator",
            "pin": "A6",
            "mode": "digital_output",
            "role": "led_upper",
            "activeLow": False,
            "sim": {"verified": False},
            **common,
        },
        {
            "id": "hyd.eng_elec_pump.lower",
            "control": "HYD ENG ELEC PUMP lower annunciator",
            "pin": "A7",
            "mode": "digital_output",
            "role": "led_lower",
            "activeLow": False,
            "sim": {"verified": False},
            **common,
        },
        {
            "id": "hyd.eng_elec_pump.switch",
            "control": "HYD ENG ELEC PUMP switch",
            "pin": "A5",
            "mode": "digital_input",
            "role": "switch",
            "activeLow": True,
            "sim": {"verified": False},
            **common,
        },
    ]


def _ensure_eng_elec_pump(hyd: dict[str, Any]) -> bool:
    assignments = hyd.setdefault("assignments", [])
    changed = False
    for desired in _eng_elec_pump_assignments():
        existing = next(
            (
                item
                for item in assignments
                if isinstance(item, dict) and item.get("id") == desired["id"]
            ),
            None,
        )
        if existing is None:
            assignments.append(desired)
            changed = True
            continue
        for key, value in desired.items():
            if existing.get(key) != value:
                existing[key] = value
                changed = True
    return changed


def _apply_pin_map(hyd: dict[str, Any]) -> bool:
    changed = False
    for assignment in hyd.get("assignments", []):
        if not isinstance(assignment, dict):
            continue
        assignment_id = str(assignment.get("id", ""))
        pin = HYD_FUEL_PIN_MAP.get(assignment_id)
        if pin is None:
            continue
        desired = {
            "pin": pin,
            "status": "revised" if assignment_id.startswith(("fuel.xfeed.", "hyd.eng1_pump.", "hyd.elec_pump.")) else assignment.get("status", "confirmed"),
            "sourceRevision": "Dedicated HYD/FUEL Mega confirmed 2026-08-25",
        }
        for key, value in desired.items():
            if assignment.get(key) != value:
                assignment[key] = value
                changed = True
    return changed


def migrate_20260825_pinmap(payload: dict[str, Any]) -> bool:
    boards = payload.get("boards", [])
    if not isinstance(boards, list):
        raise ValueError("Profile boards must be a list")

    # v0.3.7 prepare_profile() runs before this migration and guarantees the
    # separate ELEC / HYD-FUEL split for legacy installations.
    elec = _find_board(boards, "elec")
    hyd = _find_board(boards, "hyd-fuel")
    if elec is None or hyd is None:
        return False

    changed = False
    if hyd.get("name") != "HYD-FUEL":
        hyd["name"] = "HYD-FUEL"
        changed = True
    if hyd.get("optional") is not False:
        hyd["optional"] = False
        changed = True
    if elec.get("name") != "ELEC":
        elec["name"] = "ELEC"
        changed = True

    changed = _move_blue_elec_pump(elec, hyd) or changed
    changed = _apply_pin_map(hyd) or changed
    changed = _ensure_eng_elec_pump(hyd) or changed

    if not _has_migration(payload):
        payload.setdefault("changeLog", []).append(
            {
                "timestampUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "reason": (
                    "Keep ELEC and HYD/FUEL as separate Megas and apply the confirmed "
                    "2026-08-25 HYD/FUEL rewiring"
                ),
                "migration": MIGRATION_ID,
            }
        )
        changed = True
    return changed


def ensure_20260825_pinmap(path: Path | None = None) -> bool:
    target = path or writable_profile_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not migrate_20260825_pinmap(payload):
        return False

    backup = target.with_name(target.stem + "_pre_0.3.12_backup" + target.suffix)
    if not backup.exists():
        shutil.copy2(target, backup)

    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        json.loads(temporary.read_text(encoding="utf-8"))
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return True
