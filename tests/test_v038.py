from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from overheadlink.bootstrap import BAT2_SIM_EXPRESSION, HYD_FUEL_PIN_MAP, migrate_profile
from overheadlink.models import OverheadProfile
from overheadlink.profile import ProfileStore, ProfileValidator
from overheadlink.protocol import encode_message, parse_message
from overheadlink.runtime import EnhancedOverheadLinkApp
from overheadlink.serial_manager import BoardManager, ConnectedBoard, SerialConnection
from overheadlink.updater import is_newer, version_tuple


class MigrationV038Tests(unittest.TestCase):
    def migrated_payload(self):
        payload = json.loads((PROJECT / "profiles" / "a320_fenix_overhead.json").read_text(encoding="utf-8"))
        self.assertTrue(migrate_profile(payload))
        return payload

    def test_split_profile_and_confirmed_hydfuel_map(self) -> None:
        payload = self.migrated_payload()
        profile = OverheadProfile.from_dict(payload)
        self.assertIsNotNone(profile.board("elec"))
        hyd = profile.board("hyd-fuel")
        self.assertIsNotNone(hyd)
        assert hyd is not None
        for assignment_id, pin in HYD_FUEL_PIN_MAP.items():
            assignment = hyd.assignment(assignment_id)
            self.assertIsNotNone(assignment, assignment_id)
            self.assertEqual(assignment.pin, pin)
        errors = [issue for issue in ProfileValidator().validate(profile) if issue.level == "error"]
        self.assertFalse(errors, errors)

    def test_idg_and_tm1637_are_persistent_first_class_hardware(self) -> None:
        profile = OverheadProfile.from_dict(self.migrated_payload())
        elec = profile.board("elec")
        assert elec is not None
        self.assertEqual(elec.assignment("elec.idg1.switch").pin, "D6")
        display = elec.peripheral("elec.bat2_voltage_display")
        self.assertIsNotNone(display)
        assert display is not None
        self.assertEqual(display.pins, {"clk": "A2", "dio": "A3"})
        self.assertEqual(display.sim_expression, BAT2_SIM_EXPRESSION)
        self.assertEqual(elec.reserved_pins, {"A2", "A3"})

    def test_migration_is_idempotent(self) -> None:
        payload = self.migrated_payload()
        before = copy.deepcopy(payload)
        self.assertFalse(migrate_profile(payload))
        self.assertEqual(payload, before)

    def test_profile_save_keeps_peripheral_metadata(self) -> None:
        profile = OverheadProfile.from_dict(self.migrated_payload())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            store = ProfileStore(path)
            store.save(profile, "persist peripheral")
            loaded = store.load()
            display = loaded.board("elec").peripheral("elec.bat2_voltage_display")
            self.assertEqual(display.pins["clk"], "A2")
            self.assertEqual(display.pins["dio"], "A3")
            self.assertEqual(display.sim_expression, BAT2_SIM_EXPRESSION)

    def test_reserved_display_pin_cannot_be_reassigned(self) -> None:
        profile = OverheadProfile.from_dict(self.migrated_payload())
        elec = profile.board("elec")
        assert elec is not None
        assignment = elec.assignment("elec.idg1.switch")
        assert assignment is not None
        with tempfile.TemporaryDirectory() as directory:
            store = ProfileStore(Path(directory) / "profile.json")
            store.save(profile, "seed")
            with self.assertRaisesRegex(ValueError, "reserved"):
                store.repair_assignment(profile, elec.id, assignment.id, elec.id, "A2", "collision test")


class ProtocolAndSerialV038Tests(unittest.TestCase):
    def test_checksum_must_be_exactly_two_hex_digits(self) -> None:
        valid = encode_message("HELLO").decode("ascii").strip()
        with self.assertRaises(ValueError):
            parse_message(valid + "0")

    def test_partial_serial_message_is_not_discarded(self) -> None:
        messages = []
        with patch("overheadlink.serial_manager.serial", object()):
            connection = SerialConnection("COM99", lambda _port, message: messages.append(message))
        payload = encode_message("DIN", 25, 0, 1234)
        midpoint = len(payload) // 2
        connection._feed_rx(payload[:midpoint])
        self.assertEqual(messages, [])
        connection._feed_rx(payload[midpoint:])
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message_type, "DIN")
        self.assertEqual(messages[0].parts[:2], ("25", "0"))

    def test_duplicate_online_board_identity_is_ambiguous(self) -> None:
        class FakeConnection:
            running = True
            last_error = ""

        manager = BoardManager()
        first = ConnectedBoard(port="COM1", board_name="ELEC", connection=FakeConnection())
        second = ConnectedBoard(port="COM2", board_name="ELEC", connection=FakeConnection())
        manager.boards_by_port = {"COM1": first, "COM2": second}
        self.assertIsNone(manager.by_profile_name("ELEC"))
        self.assertEqual(manager.duplicate_profile_ports("ELEC"), ["COM1", "COM2"])
        with self.assertRaisesRegex(RuntimeError, "duplicated"):
            manager.send_to_profile("ELEC", "RUN")


class RuntimeV038Tests(unittest.TestCase):
    def test_auto_runtime_retries_when_msfs_connected_but_wasm_not_ready(self) -> None:
        calls = []

        class BoolValue:
            def get(self):
                return False

        fake = object.__new__(EnhancedOverheadLinkApp)
        fake.offline_fenix = BoolValue()
        fake.fenix_connecting = False
        fake.fenix = type("Bridge", (), {"ready": False})()
        fake._dash_all_displays = lambda: calls.append("dash")
        fake._begin_fenix_connect = lambda force=False: calls.append(("connect", force))
        fake.after = lambda milliseconds, callback: calls.append(("after", milliseconds))
        EnhancedOverheadLinkApp._auto_runtime_tick(fake)
        self.assertEqual(calls[0], "dash")
        self.assertEqual(calls[1], ("connect", True))
        self.assertEqual(calls[2], ("after", 15000))


class UpdaterV038Tests(unittest.TestCase):
    def test_trailing_zero_versions_compare_equal(self) -> None:
        self.assertEqual(version_tuple("0.3.8.0"), (0, 3, 8))
        self.assertFalse(is_newer("0.3.8.0", "0.3.8"))
        self.assertTrue(is_newer("0.3.9", "0.3.8.99"))


class FirmwareV038Tests(unittest.TestCase):
    def test_firmware_contains_tm1637_reserved_driver(self) -> None:
        source = (PROJECT / "firmware" / "OverheadLinkMega" / "OverheadLinkMega.ino").read_text(encoding="utf-8")
        self.assertIn('FW_VERSION = "0.3.0"', source)
        self.assertIn("ROLE_PERIPHERAL", source)
        self.assertIn('strcmp(command, "TM1637_CFG")', source)
        self.assertIn('strcmp(command, "TM1637_VALUE")', source)
        self.assertIn('strcmp(command, "TM1637_DASH")', source)


if __name__ == "__main__":
    unittest.main()
