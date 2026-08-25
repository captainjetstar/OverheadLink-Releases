from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from overheadlink.firmware_update import FirmwareFlasher, MEGA_TARGET, NANO_TARGET


class FirmwareUpdaterTests(unittest.TestCase):
    def make_assets(self, root: Path, target) -> FirmwareFlasher:
        avrdude = root / "vendor" / "avrdude" / "bin" / "avrdude.exe"
        config = root / "vendor" / "avrdude" / "etc" / "avrdude.conf"
        firmware = root / target.hex_relative_path
        for path in (avrdude, config, firmware):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test")
        return FirmwareFlasher(root)

    def test_mega_command_uses_safe_expected_upload_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            flasher = self.make_assets(root, MEGA_TARGET)
            command = flasher.command("COM20", MEGA_TARGET, 115200)
            self.assertIn("COM20", command)
            self.assertIn("atmega2560", command)
            self.assertIn("wiring", command)
            self.assertIn("115200", command)
            self.assertIn("-D", command)
            self.assertTrue(command[-1].startswith("flash:w:"))
            self.assertTrue(command[-1].endswith(":i"))

    def test_nano_supports_old_and_new_bootloader_speeds(self) -> None:
        self.assertEqual(NANO_TARGET.baudrates, (57600, 115200))
        self.assertEqual(NANO_TARGET.mcu, "atmega328p")
        self.assertEqual(NANO_TARGET.programmer, "arduino")

    def test_missing_assets_are_reported_before_flash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            flasher = FirmwareFlasher(Path(temporary))
            missing = flasher.missing_assets(MEGA_TARGET)
            self.assertEqual(len(missing), 3)

    def test_progress_messages_are_reduced_to_user_friendly_phases(self) -> None:
        self.assertEqual(
            FirmwareFlasher._friendly_progress("avrdude: writing flash (12345 bytes):"),
            "Writing firmware to flash…",
        )
        self.assertEqual(
            FirmwareFlasher._friendly_progress("avrdude: verifying ..."),
            "Verifying firmware…",
        )


if __name__ == "__main__":
    unittest.main()
