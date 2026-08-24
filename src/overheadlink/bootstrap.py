from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


PROFILE_FILENAME = "a320_fenix_overhead.json"
MIGRATION_ID = "0.3.7-hydfuel-split"


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


def _data_root() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "OverheadLink"
    else:
        root = Path.home() / ".config" / "OverheadLink"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _bundled_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def writable_profile_path() -> Path:
    target = _data_root() / "profiles" / PROFILE_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(_bundled_root() / "profiles" / PROFILE_FILENAME, target)
    return target


def _migration_applied(payload: dict[str, Any]) -> bool:
    return any(
        isinstance(entry, dict) and entry.get("migration") == MIGRATION_ID
        for entry in payload.get("changeLog", [])
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
        "sourceRevision": "User confirmed 2026-08-24",
        "notes": "Hardware allocation retained by OverheadLink. CLK=A2, DIO=A3.",
    }


def _ensure_battery_display(payload: dict[str, Any]) -> bool:
    boards = payload.get("boards", [])
    elec = next((board for board in boards if isinstance(board, dict) and board.get("id") == "elec"), None)
    if elec is None:
        return False
    peripherals = elec.setdefault("peripherals", [])
    if any(isinstance(item, dict) and item.get("id") == "elec.bat2_voltage_display" for item in peripherals):
        return False
    peripherals.append(_battery2_display())
    return True


def migrate_profile(payload: dict[str, Any]) -> bool:
    if _migration_applied(payload):
        _ensure_battery_display(payload)
        return False

    boards = payload.get("boards", [])
    if not isinstance(boards, list):
        raise ValueError("Profile boards must be a list")

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

        for assignment in hyd_assignments:
            assignment_id = str(assignment.get("id", ""))
            pin = HYD_FUEL_PIN_MAP.get(assignment_id)
            if pin:
                assignment["pin"] = pin
                assignment["status"] = "revised"
                assignment["sourceRevision"] = "Dedicated HYD/FUEL Mega confirmed 2026-08-24"

        if not any(item.get("id") == "elec.idg1.switch" for item in elec_assignments):
            elec_assignments.append(_idg1_assignment())

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
    else:
        elec = next((board for board in boards if isinstance(board, dict) and board.get("id") == "elec"), None)
        hyd = next((board for board in boards if isinstance(board, dict) and board.get("id") == "hyd-fuel"), None)
        if elec is not None:
            assignments = elec.setdefault("assignments", [])
            if not any(isinstance(item, dict) and item.get("id") == "elec.idg1.switch" for item in assignments):
                assignments.append(_idg1_assignment())
        if hyd is not None:
            for assignment in hyd.get("assignments", []):
                if not isinstance(assignment, dict):
                    continue
                assignment_id = str(assignment.get("id", ""))
                if assignment_id in HYD_FUEL_PIN_MAP:
                    assignment["pin"] = HYD_FUEL_PIN_MAP[assignment_id]
                    assignment["status"] = "revised"
                    assignment["sourceRevision"] = "Dedicated HYD/FUEL Mega confirmed 2026-08-24"

    _ensure_battery_display(payload)
    payload.setdefault("changeLog", []).append(
        {
            "timestampUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason": "Split ELEC and HYD/FUEL Megas; apply confirmed 2026-08-24 pin map; add IDG1 D6 and BAT2 display A2/A3 metadata",
            "migration": MIGRATION_ID,
        }
    )
    return True


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def prepare_profile() -> Path:
    path = writable_profile_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    changed = migrate_profile(payload)
    if changed:
        backup = path.with_name(path.stem + "_pre_0.3.7_backup" + path.suffix)
        if not backup.exists():
            shutil.copy2(path, backup)
        _write_payload(path, payload)
    elif _ensure_battery_display(payload):
        _write_payload(path, payload)
    return path


def _preserve_peripherals_after_save(profile_store: Any) -> None:
    original_save = profile_store.save

    def preserving_save(profile: Any, reason: str = "Profile updated") -> Any:
        backup = original_save(profile, reason)
        try:
            payload = json.loads(profile_store.path.read_text(encoding="utf-8"))
            if _ensure_battery_display(payload):
                _write_payload(profile_store.path, payload)
        except (OSError, json.JSONDecodeError):
            pass
        return backup

    profile_store.save = preserving_save


def install_app_extensions(app_class: type) -> None:
    if getattr(app_class, "_overheadlink_remote_installed", False):
        return

    original_init = app_class.__init__
    original_close = app_class._close

    def wrapped_init(self, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        _preserve_peripherals_after_save(self.profile_store)
        try:
            from .remote import RemotePanelServer, install_remote_tab

            self.remote_panel_server = RemotePanelServer(self)
            self.remote_panel_server.start()
            install_remote_tab(self, self.remote_panel_server)
            self._log(
                f"REMOTE PANEL ready: {self.remote_panel_server.url} | pairing code {self.remote_panel_server.pairing_code}"
            )
        except Exception as error:
            self.remote_panel_server = None
            self._log(f"REMOTE PANEL failed to start: {error}")

    def wrapped_close(self) -> None:
        server = getattr(self, "remote_panel_server", None)
        if server is not None:
            try:
                server.stop()
            except Exception:
                pass
        original_close(self)

    app_class.__init__ = wrapped_init
    app_class._close = wrapped_close
    app_class._overheadlink_remote_installed = True
