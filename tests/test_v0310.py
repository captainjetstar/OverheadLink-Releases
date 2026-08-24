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
from overheadlink.v0310_fix import ADIRS_BOARD_ID, MIGRATION_ID, ensure_adirs_required


class V0310RequiredBoardTests(unittest.TestCase):
    def migrated_temp_profile(self, directory: str) -> Path:
        payload = json.loads((PROJECT / "profiles" / "a320_fenix_overhead.json").read_text(encoding="utf-8"))
        migrate_profile(payload)
        path = Path(directory) / "a320_fenix_overhead.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def test_adirs_is_migrated_from_optional_to_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.migrated_temp_profile(directory)
            before = json.loads(path.read_text(encoding="utf-8"))
            adirs_before = next(board for board in before["boards"] if board["id"] == ADIRS_BOARD_ID)
            self.assertTrue(adirs_before["optional"])

            self.assertTrue(ensure_adirs_required(path))
            after = json.loads(path.read_text(encoding="utf-8"))
            adirs_after = next(board for board in after["boards"] if board["id"] == ADIRS_BOARD_ID)
            self.assertFalse(adirs_after["optional"])
            self.assertTrue(any(entry.get("migration") == MIGRATION_ID for entry in after["changeLog"]))
            self.assertTrue(path.with_name(path.stem + "_pre_0.3.10_backup" + path.suffix).exists())

    def test_required_controller_count_is_six(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.migrated_temp_profile(directory)
            ensure_adirs_required(path)
            profile = OverheadProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
            required = [board for board in profile.boards if not board.optional]
            self.assertEqual(len(required), 6)
            self.assertEqual(
                {board.id for board in required},
                {"elec", "hyd-fuel", "air-cond", "ext-light-overhead", ADIRS_BOARD_ID, "backlight-nano"},
            )

    def test_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.migrated_temp_profile(directory)
            self.assertTrue(ensure_adirs_required(path))
            snapshot = path.read_text(encoding="utf-8")
            self.assertFalse(ensure_adirs_required(path))
            self.assertEqual(path.read_text(encoding="utf-8"), snapshot)

    def test_v0310_version_alignment(self) -> None:
        with (PROJECT / "pyproject.toml").open("rb") as handle:
            project_version = str(tomllib.load(handle)["project"]["version"])
        self.assertEqual(project_version, "0.3.10")
        self.assertEqual(__version__, project_version)

    def test_packaged_launcher_runs_required_board_migration(self) -> None:
        source = (PROJECT / "run_overheadlink.py").read_text(encoding="utf-8")
        self.assertIn("prepare_profile()", source)
        self.assertIn("ensure_adirs_required()", source)
        self.assertLess(source.index("prepare_profile()"), source.index("ensure_adirs_required()"))


if __name__ == "__main__":
    unittest.main()
