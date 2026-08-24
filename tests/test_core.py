from __future__ import annotations

import copy
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import json


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from overheadlink.backlight import COLOUR_PRESETS, BacklightController, BacklightSettings, BrightnessPreset, ColourPreset
from overheadlink.learning import AnalogLearningSession, DigitalLearningSession
from overheadlink.models import canonical_pin, pin_number
from overheadlink.preferences import AppPreferences, canonical_port
from overheadlink.profile import ProfileStore, ProfileValidator
from overheadlink.protocol import encode_message, parse_message
from overheadlink.serial_manager import BoardManager, PortCandidate
from overheadlink.simulator import FenixBridge, MobiFlightWasmCommandBuilder, SimConnectClientDataTransport, SimulatorState
from overheadlink.updater import UpdateInfo, download_update, is_newer, latest_release, version_tuple


class FakeClientDataTransport:
    def __init__(self, registration_response_number: int = 1) -> None:
        self.on_data = None
        self.maps: list[tuple[str, int]] = []
        self.definitions: list[tuple[int, int, int]] = []
        self.requests: list[tuple[int, int, int]] = []
        self.sent: list[tuple[int, int, bytes]] = []
        self.closed = False
        self.registration_response_number = registration_response_number
        self.registration_attempts = 0

    def open(self, on_data, _on_quit, _on_error) -> None:
        self.on_data = on_data

    def map_area(self, name: str, area_id: int) -> None:
        self.maps.append((name, area_id))

    def add_definition(self, definition_id: int, offset: int, size: int) -> None:
        self.definitions.append((definition_id, offset, size))

    def request(self, area_id: int, request_id: int, definition_id: int) -> None:
        self.requests.append((area_id, request_id, definition_id))

    def send(self, area_id: int, definition_id: int, payload: bytes) -> None:
        self.sent.append((area_id, definition_id, payload))
        command = payload.split(b"\x00", 1)[0]
        if command == b"MF.Ping" and self.on_data:
            self.on_data(0, b"MF.Pong\x00")
        if command == b"MF.Clients.Add.OverheadLink":
            self.registration_attempts += 1
            if self.registration_attempts >= self.registration_response_number and self.on_data:
                self.on_data(0, b"MF.Clients.Add.OverheadLink.Finished\x00")

    def close(self) -> None:
        self.closed = True


class PinTests(unittest.TestCase):
    def test_mega_pin_conversion(self) -> None:
        self.assertEqual(pin_number("D53"), 53)
        self.assertEqual(pin_number("A0"), 54)
        self.assertEqual(pin_number("A15"), 69)
        self.assertEqual(canonical_pin(55), "A1")

    def test_bad_pin_rejected(self) -> None:
        with self.assertRaises(ValueError):
            pin_number("D54")


class ProtocolTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        payload = encode_message("preset", "DAY_TIME_DIM", 180)
        message = parse_message(payload)
        self.assertEqual(message.message_type, "PRESET")
        self.assertEqual(message.parts, ("DAY_TIME_DIM", "180"))

    def test_corrupt_checksum_rejected(self) -> None:
        payload = encode_message("HELLO").decode().strip()[:-2] + "00"
        with self.assertRaises(ValueError):
            parse_message(payload)


class LearningTests(unittest.TestCase):
    def test_digital_requires_two_confirmations(self) -> None:
        session = DigitalLearningSession()
        self.assertIsNone(session.observe("AIR-COND", 4, False, 1.0))
        result = session.observe("AIR-COND", 4, False, 2.0)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.pin, "D4")
        self.assertTrue(result.active_low)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_analogue_selects_largest_coherent_range(self) -> None:
        session = AnalogLearningSession()
        for value in (500, 502, 499, 501, 500, 503):
            session.observe("AIR-COND", "A1", value)
        for value in (12, 80, 240, 520, 850, 1001, 900, 520, 250, 20):
            session.observe("AIR-COND", "A2", value)
        result = session.finalize()
        self.assertEqual(result.pin, "A2")
        self.assertEqual(result.minimum, 12)
        self.assertEqual(result.maximum, 1001)


class BacklightTests(unittest.TestCase):
    def test_named_presets(self) -> None:
        sent: list[bytes] = []
        controller = BacklightController(sent.append, BacklightSettings())
        self.assertEqual(controller.apply(BrightnessPreset.FULL_LIGHT), 255)
        self.assertEqual(parse_message(sent[-1]).parts, ("FULL_LIGHT", "255"))
        self.assertEqual(controller.apply(BrightnessPreset.HALF_DIM), 128)
        self.assertEqual(controller.apply(BrightnessPreset.DAY_TIME_DIM), 180)

    def test_colour_presets_send_rgb_and_cover_requested_options(self) -> None:
        sent: list[bytes] = []
        controller = BacklightController(sent.append, BacklightSettings())
        for preset, rgb in COLOUR_PRESETS.items():
            self.assertEqual(controller.apply_colour(*rgb), rgb)
            self.assertEqual(parse_message(sent[-1]).message_type, "COLOR")
            self.assertEqual(parse_message(sent[-1]).parts, tuple(str(value) for value in rgb))
        self.assertEqual(
            set(COLOUR_PRESETS),
            {
                ColourPreset.AIRBUS_AMBER,
                ColourPreset.WARM_WHITE,
                ColourPreset.SOFT_WHITE,
                ColourPreset.DEEP_ORANGE,
                ColourPreset.RED_NIGHT,
            },
        )


class PortPreferenceTests(unittest.TestCase):
    def test_ignored_ports_persist_and_normalize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            preferences = AppPreferences.load(path)
            preferences.ignore("com22")
            preferences.ignore(" COM9 ")
            reloaded = AppPreferences.load(path)
            self.assertEqual(reloaded.ignored_ports, {"COM9", "COM22"})
            reloaded.use("com9")
            self.assertEqual(AppPreferences.load(path).ignored_ports, {"COM22"})
            self.assertEqual(canonical_port("COM14"), "COM14")

    def test_board_manager_never_opens_ignored_port(self) -> None:
        opened: list[str] = []
        closed: list[str] = []

        class FakeConnection:
            def __init__(self, port, _on_message):
                self.port = port
                self.running = False

            def start(self):
                opened.append(self.port)
                self.running = True

            def close(self):
                closed.append(self.port)
                self.running = False

        manager = BoardManager(ignored_ports={"com18"})
        manager.candidate_ports = lambda: [
            PortCandidate("COM14", "Mega", 0x2341, 1),
            PortCandidate("COM18", "Rowsfire", 0x2341, 1),
        ]
        with (
            patch("overheadlink.serial_manager.serial", object()),
            patch("overheadlink.serial_manager.list_ports", object()),
            patch("overheadlink.serial_manager.SerialConnection", FakeConnection),
        ):
            manager.scan()
            self.assertEqual(opened, ["COM14"])
            self.assertNotIn("COM18", manager.boards_by_port)
            manager.ignore_port("com14")
            self.assertIn("COM14", closed)
            manager.use_port("COM18")
            manager.scan()
            self.assertIn("COM18", opened)


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = PROJECT / "profiles" / "a320_fenix_overhead.json"
        cls.profile = ProfileStore(cls.path).load()

    def test_seed_profile_has_no_pin_conflicts(self) -> None:
        issues = ProfileValidator().validate(self.profile)
        self.assertFalse([issue for issue in issues if issue.level == "error"], issues)

    def test_required_boards_and_backlight(self) -> None:
        names = {board.name for board in self.profile.boards}
        self.assertTrue({"ELEC-HYD-FUEL", "AIR-COND", "EXT-LIGHT-OVERHEAD", "BACKLIGHT-NANO"}.issubset(names))
        self.assertEqual(self.profile.backlighting["dataPin"], "D6")
        self.assertEqual(self.profile.backlighting["ledCount"], 300)
        self.assertEqual(self.profile.backlighting["presets"], {"FULL LIGHT": 255, "HALF DIM": 128, "DAY TIME DIM": 180})

    def test_latest_aircond_assignments(self) -> None:
        board = self.profile.board("air-cond")
        assert board is not None
        expected = {
            "pneu.pack1.upper": "D2",
            "pneu.pack1.lower": "D3",
            "pneu.pack1.switch": "D4",
            "pneu.eng1_bleed.lower": "D6",
            "pneu.eng1_bleed.upper": "D7",
            "pneu.eng1_bleed.switch": "D5",
            "pneu.ram_air.upper": "D8",
            "pneu.ram_air.lower": "D9",
            "pneu.ram_air.switch": "D10",
            "pneu.apu_bleed.switch": "A4",
            "temp.aft": "A1",
            "temp.cockpit": "A2",
            "temp.forward": "A3",
        }
        for assignment_id, pin in expected.items():
            self.assertEqual(board.assignment(assignment_id).pin, pin)

    def test_resolved_external_light_conflict(self) -> None:
        board = self.profile.board("ext-light-overhead")
        assert board is not None
        expected = {
            "pneu.ditching.upper": "D45",
            "pneu.ditching.lower": "D44",
            "pneu.ditching.switch": "D46",
            "signs.emergency.upper": "D49",
            "signs.emergency.lower": "D48",
            "signs.emergency.switch": "D47",
            "signs.seatbelt.pos1": "D50",
            "signs.seatbelt.pos2": "D51",
        }
        for assignment_id, pin in expected.items():
            self.assertEqual(board.assignment(assignment_id).pin, pin)

    def test_validator_detects_deliberate_duplicate(self) -> None:
        profile = copy.deepcopy(self.profile)
        board = profile.board("air-cond")
        assert board is not None
        board.assignment("pneu.pack1.switch").pin = "D2"
        issues = ProfileValidator().validate(profile)
        self.assertTrue(any(issue.level == "error" and "also belongs" in issue.message for issue in issues))

    def test_cross_board_pin_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = copy.deepcopy(self.profile)
            path = Path(directory) / "profile.json"
            store = ProfileStore(path)
            store.save(profile, "test seed")
            source = profile.board("elec-hyd-fuel")
            target = profile.board("air-cond")
            assert source is not None and target is not None
            assignment = source.assignment("hyd.elec_pump.switch")
            assert assignment is not None
            store.repair_assignment(
                profile,
                source.id,
                assignment.id,
                target.id,
                "D23",
                "cross-board test",
                active_low=True,
            )
            reloaded = store.load()
            self.assertIsNone(reloaded.board(source.id).assignment(assignment.id))
            moved = reloaded.board(target.id).assignment(assignment.id)
            self.assertIsNotNone(moved)
            self.assertEqual(moved.pin, "D23")

    def test_safe_output_swap_preserves_unique_pin_map(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = copy.deepcopy(self.profile)
            path = Path(directory) / "profile.json"
            store = ProfileStore(path)
            board = profile.board("air-cond")
            assert board is not None
            first = board.assignment("pneu.pack1.upper")
            second = board.assignment("pneu.pack1.lower")
            assert first is not None and second is not None
            first_pin, second_pin = first.pin, second.pin
            store.swap_output_pins(profile, board.id, first.id, second.id, "test swap")
            self.assertEqual(first.pin, second_pin)
            self.assertEqual(second.pin, first_pin)
            errors = [issue for issue in ProfileValidator().validate(profile) if issue.level == "error"]
            self.assertFalse(errors)

    def test_pin_repair_persists_detected_polarity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = copy.deepcopy(self.profile)
            path = Path(directory) / "profile.json"
            store = ProfileStore(path)
            store.save(profile, "test seed")
            board = profile.board("elec-hyd-fuel")
            assert board is not None
            assignment = board.assignments[0]
            store.repair_pin(
                profile,
                board.id,
                assignment.id,
                "D43",
                "test repair",
                active_low=False,
            )
            reloaded_board = store.load().board(board.id)
            assert reloaded_board is not None
            reloaded = reloaded_board.assignment(assignment.id)
            assert reloaded is not None
            self.assertEqual(reloaded.pin, "D43")
            self.assertFalse(reloaded.active_low)


class SimulatorCommandTests(unittest.TestCase):
    def test_client_data_uses_valid_on_set_period(self) -> None:
        self.assertEqual(SimConnectClientDataTransport.PERIOD_ON_SET, 3)

    def test_bundled_simconnect_runtime_is_discoverable(self) -> None:
        runtime = PROJECT / "vendor" / "SimConnect.dll"
        self.assertTrue(runtime.is_file())
        self.assertIn(runtime, SimConnectClientDataTransport.dll_candidates())

    def test_wasm_commands(self) -> None:
        self.assertEqual(MobiFlightWasmCommandBuilder.ping(), "MF.Ping")
        self.assertEqual(
            MobiFlightWasmCommandBuilder.execute_rpn("1 (>L:S_TEST)"),
            "MF.SimVars.Set.1 (>L:S_TEST)",
        )
        self.assertEqual(
            MobiFlightWasmCommandBuilder.register_float("(L:I_TEST)"),
            "MF.SimVars.Add.(L:I_TEST)",
        )

    def test_live_bridge_channel_registration_and_feedback(self) -> None:
        fake = FakeClientDataTransport()
        feedback: list[tuple[str, float]] = []
        bridge = FenixBridge(
            lambda assignment_id, value: feedback.append((assignment_id, value)),
            transport_factory=lambda: fake,
            registration_timeout=0.1,
        )
        status = bridge.connect()
        self.assertEqual(status.state, SimulatorState.FENIX_CONNECTED)
        self.assertIn(("MobiFlight.Command", 1), fake.maps)
        self.assertIn(("OverheadLink.LVars", 3), fake.maps)
        bridge.subscribe("test.led", "(L:I_TEST)")
        self.assertIn((1000, 0, 4), fake.definitions)
        assert fake.on_data is not None
        fake.on_data(1000, struct.pack("<f", 1.0))
        self.assertEqual(feedback, [("test.led", 1.0)])
        bridge.execute("1 (>L:S_TEST)")
        commands = [payload.split(b"\x00", 1)[0] for _, _, payload in fake.sent]
        self.assertIn(b"MF.SimVars.Add.(L:I_TEST)", commands)
        self.assertIn(b"MF.SimVars.Set.1 (>L:S_TEST)", commands)

    def test_live_bridge_retries_registration(self) -> None:
        fake = FakeClientDataTransport(registration_response_number=3)
        bridge = FenixBridge(transport_factory=lambda: fake, registration_timeout=2.5)
        status = bridge.connect()
        self.assertEqual(status.state, SimulatorState.FENIX_CONNECTED)
        self.assertEqual(fake.registration_attempts, 3)


class UpdaterTests(unittest.TestCase):
    def test_version_comparison(self) -> None:
        self.assertEqual(version_tuple("v0.3.4"), (0, 3, 4))
        self.assertTrue(is_newer("0.4.0", "0.3.4"))
        self.assertFalse(is_newer("0.3.4", "0.3.4"))

    def test_latest_release_requires_installer_and_checksum(self) -> None:
        release = {
            "tag_name": "v0.3.4",
            "body": "Updater release",
            "html_url": "https://github.com/example/release",
            "assets": [
                {"name": "OverheadLink_v0.3.4_Windows_x64.exe", "browser_download_url": "https://example/app.exe"},
                {"name": "OverheadLink_v0.3.4_Windows_x64.exe.sha256", "browser_download_url": "https://example/app.sha256"},
            ],
        }

        class Response:
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size=-1):
                return json.dumps(release).encode()

        with patch("overheadlink.updater._open_url", return_value=Response()):
            update = latest_release()
        self.assertEqual(update.version, "0.3.4")
        self.assertEqual(update.checksum_url, "https://example/app.sha256")

    def test_download_verifies_hash_and_package_signature(self) -> None:
        payload = b"MZ" + (b"\x00" * 64) + b"OHLNK03!" + (16).to_bytes(8, "little")
        checksum = hashlib.sha256(payload).hexdigest().encode()

        class Response(io.BytesIO):
            headers = {"Content-Length": str(len(payload))}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()
                return False

        update = UpdateInfo("0.3.4", "", "https://example/app.exe", "https://example/app.sha256", "")
        with tempfile.TemporaryDirectory() as directory, patch(
            "overheadlink.updater._open_url",
            side_effect=[Response(checksum), Response(payload)],
        ):
            target = download_update(update, Path(directory))
            self.assertEqual(target.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
