from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from overheadlink import __version__
from overheadlink.bootstrap import migrate_profile
from overheadlink.models import OverheadProfile
from overheadlink.profile import ProfileValidator
from overheadlink.v0312_pinmap import MIGRATION_ID, ensure_20260825_pinmap


class V0312SeparateHydFuelTests(unittest.TestCase):
    def migrated_temp_profile(self, directory: str) -> Path:
        payload = json.loads((PROJECT / "profiles" / "a320_fenix_overhead.json").read_text(encoding="utf-8"))
        migrate_profile(payload)
        path = Path(directory) / "a320_fenix_overhead.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    @staticmethod
    def assignment(board: dict, assignment_id: str) -> dict:
        return next(item for item in board["assignments"] if item["id"] == assignment_id)

    def test_separate_boards_and_aug25_hydfuel_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.migrated_temp_profile(directory)
            self.assertTrue(ensure_20260825_pinmap(path))
            payload = json.loads(path.read_text(encoding="utf-8"))
            boards = {board["id"]: board for board in payload["boards"]}

            for board_id in ("elec", "hyd-fuel", "air-cond", "ext-light-overhead"):
                self.assertIn(board_id, boards)
            self.assertNotIn("elec-hyd-fuel", boards)

            hyd = boards["hyd-fuel"]
            expected = {
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
                "hyd.eng_elec_pump.upper": "A6",
                "hyd.eng_elec_pump.lower": "A7",
                "hyd.eng_elec_pump.switch": "A5",
            }
            for assignment_id, pin in expected.items():
                self.assertEqual(self.assignment(hyd, assignment_id)["pin"], pin)

            blue_switch = self.assignment(hyd, "hyd.elec_pump.switch")
            self.assertFalse(blue_switch["enabled"])
            self.assertEqual(blue_switch["status"], "needs_verification")
            self.assertFalse(any(item["id"].startswith("hyd.elec_pump.") for item in boards["elec"]["assignments"]))
            self.assertTrue(any(entry.get("migration") == MIGRATION_ID for entry in payload["changeLog"]))

            profile = OverheadProfile.from_dict(payload)
            errors = [issue for issue in ProfileValidator().validate(profile) if issue.level == "error"]
            self.assertEqual(errors, [])

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.migrated_temp_profile(directory)
            self.assertTrue(ensure_20260825_pinmap(path))
            snapshot = path.read_text(encoding="utf-8")
            self.assertFalse(ensure_20260825_pinmap(path))
            self.assertEqual(path.read_text(encoding="utf-8"), snapshot)

    def test_version_alignment(self) -> None:
        with (PROJECT / "pyproject.toml").open("rb") as handle:
            project_version = str(tomllib.load(handle)["project"]["version"])
        self.assertEqual(__version__, project_version)
        self.assertEqual(project_version, "0.3.12")


if __name__ == "__main__":
    unittest.main()
