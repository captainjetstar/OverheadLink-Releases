import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from overheadlink.current_profile import ensure_current_profile
from overheadlink.models import OverheadProfile
from overheadlink.profile import ProfileValidator


class CurrentProfileTests(unittest.TestCase):
    def test_upgrade_backup_idempotence_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            old = json.loads((ROOT / "tests/fixtures/legacy_profile.json").read_text())
            old["backlighting"]["colour"] = {"red": 255, "green": 35, "blue": 0}
            path.write_text(json.dumps(old))
            seed = ROOT / "profiles/a320_fenix_overhead.json"
            ensure_current_profile(path, seed)
            first = path.read_bytes()
            ensure_current_profile(path, seed)
            self.assertEqual(first, path.read_bytes())
            self.assertEqual(len(list((path.parent / "backups").glob("*.json"))), 1)
            profile = OverheadProfile.from_dict(json.loads(first))
            self.assertEqual(ProfileValidator().validate(profile), [])
            self.assertEqual(len(profile.boards), 6)
            self.assertEqual(profile.backlighting["colour"]["green"], 35)
            hyd = profile.board("hyd-fuel")
            self.assertEqual(hyd.assignment("hyd.elec_pump.switch").pin, "A4")
            self.assertFalse(hyd.assignment("fuel.mode_select.upper").enabled)
            self.assertEqual(len(profile.board("elec").peripherals), 2)

    def test_current_seed_is_valid(self):
        payload = json.loads((ROOT / "profiles/a320_fenix_overhead.json").read_text())
        self.assertEqual(ProfileValidator().validate(OverheadProfile.from_dict(payload)), [])
