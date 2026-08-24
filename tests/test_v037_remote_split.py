from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from overheadlink.bootstrap import HYD_FUEL_PIN_MAP, MIGRATION_ID, migrate_profile
from overheadlink.models import OverheadProfile
from overheadlink.remote import RemotePanelServer


class FakeFenix:
    def __init__(self) -> None:
        self.ready = True
        self.commands: list[str] = []
        self.status = type("Status", (), {"detail": "Fenix test bridge ready"})()

    def execute(self, command: str) -> None:
        self.commands.append(command)


class FakeApp:
    def __init__(self, profile: OverheadProfile) -> None:
        self.profile = profile
        self.fenix = FakeFenix()
        self.feedback_values: dict[str, float] = {}


class V037MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        source = json.loads((PROJECT / "profiles" / "a320_fenix_overhead.json").read_text(encoding="utf-8"))
        self.payload = copy.deepcopy(source)

    def test_combined_board_is_split_with_confirmed_pins(self) -> None:
        self.assertTrue(migrate_profile(self.payload))
        ids = [board["id"] for board in self.payload["boards"]]
        self.assertIn("elec", ids)
        self.assertIn("hyd-fuel", ids)
        self.assertNotIn("elec-hyd-fuel", ids)

        hyd = next(board for board in self.payload["boards"] if board["id"] == "hyd-fuel")
        actual = {item["id"]: item["pin"] for item in hyd["assignments"] if item["id"] in HYD_FUEL_PIN_MAP}
        self.assertEqual(actual, HYD_FUEL_PIN_MAP)
        self.assertEqual(len(actual), 27)

    def test_elec_gets_idg1_and_battery2_display_metadata(self) -> None:
        migrate_profile(self.payload)
        elec = next(board for board in self.payload["boards"] if board["id"] == "elec")
        idg = next(item for item in elec["assignments"] if item["id"] == "elec.idg1.switch")
        self.assertEqual(idg["pin"], "D6")
        self.assertIn("S_OH_ELEC_IDG1", idg["sim"]["onPress"])

        display = next(item for item in elec["peripherals"] if item["id"] == "elec.bat2_voltage_display")
        self.assertEqual(display["clk"], "A2")
        self.assertEqual(display["dio"], "A3")

    def test_blue_electric_hyd_pump_remains_on_elec_until_remapped(self) -> None:
        migrate_profile(self.payload)
        elec = next(board for board in self.payload["boards"] if board["id"] == "elec")
        ids = {item["id"] for item in elec["assignments"]}
        self.assertIn("hyd.elec_pump.upper", ids)
        self.assertIn("hyd.elec_pump.lower", ids)
        self.assertIn("hyd.elec_pump.switch", ids)

    def test_migration_is_idempotent(self) -> None:
        self.assertTrue(migrate_profile(self.payload))
        snapshot = copy.deepcopy(self.payload)
        self.assertFalse(migrate_profile(self.payload))
        self.assertEqual(snapshot, self.payload)
        self.assertTrue(any(item.get("migration") == MIGRATION_ID for item in self.payload["changeLog"]))

    def test_no_duplicate_active_pins_after_split(self) -> None:
        migrate_profile(self.payload)
        profile = OverheadProfile.from_dict(self.payload)
        for board in profile.boards:
            pins = [item.pin for item in board.assignments if item.enabled and item.status.value != "superseded"]
            self.assertEqual(len(pins), len(set(pins)), board.name)

    def test_remote_tap_runs_idg_press_and_release(self) -> None:
        migrate_profile(self.payload)
        app = FakeApp(OverheadProfile.from_dict(self.payload))
        remote = RemotePanelServer(app, port=0)
        remote.execute_assignment("elec.idg1.switch", "tap")
        self.assertEqual(len(app.fenix.commands), 2)
        self.assertIn("S_OH_ELEC_IDG1", app.fenix.commands[0])
        self.assertIn("S_OH_ELEC_IDG1", app.fenix.commands[1])


if __name__ == "__main__":
    unittest.main()
