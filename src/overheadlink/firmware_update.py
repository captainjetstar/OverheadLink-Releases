from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
from typing import Callable


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class FirmwareTarget:
    key: str
    label: str
    board_type: str
    firmware_version: str
    mcu: str
    programmer: str
    baudrates: tuple[int, ...]
    hex_relative_path: str


MEGA_TARGET = FirmwareTarget(
    key="mega",
    label="Mega 2560",
    board_type="MEGA",
    firmware_version="0.3.0",
    mcu="atmega2560",
    programmer="wiring",
    baudrates=(115200,),
    hex_relative_path="firmware/precompiled/mega/OverheadLinkMega.ino.hex",
)

NANO_TARGET = FirmwareTarget(
    key="nano",
    label="Backlight Nano",
    board_type="NANO",
    firmware_version="0.2.0",
    mcu="atmega328p",
    programmer="arduino",
    # Most classic CH340 Nanos use the old 57600 bootloader; newer boards use 115200.
    baudrates=(57600, 115200),
    hex_relative_path="firmware/precompiled/nano/OverheadLinkBacklightNano.ino.hex",
)

TARGETS = {target.key: target for target in (MEGA_TARGET, NANO_TARGET)}
TARGET_LABELS = {target.label: target for target in TARGETS.values()}


@dataclass(frozen=True, slots=True)
class FlashResult:
    target: FirmwareTarget
    port: str
    baudrate: int
    output: str


class FirmwareFlashError(RuntimeError):
    pass


class FirmwareFlasher:
    """Flash precompiled OverheadLink firmware with the bundled Arduino avrdude.

    No Arduino IDE or MobiFlight installation is required. The release package
    contains the exact HEX image and avrdude build used by CI.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.avrdude = self._find_avrdude()
        self.avrdude_conf = self._find_avrdude_conf()

    def _find_avrdude(self) -> Path:
        candidates = (
            self.root / "vendor" / "avrdude" / "bin" / "avrdude.exe",
            self.root / "vendor" / "avrdude" / "avrdude.exe",
            self.root / "vendor" / "avrdude" / "bin" / "avrdude",
            self.root / "vendor" / "avrdude" / "avrdude",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    def _find_avrdude_conf(self) -> Path:
        candidates = (
            self.root / "vendor" / "avrdude" / "etc" / "avrdude.conf",
            self.root / "vendor" / "avrdude" / "avrdude.conf",
            self.root / "vendor" / "avrdude" / "etc" / "avrdude.conf.in",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]

    def firmware_path(self, target: FirmwareTarget) -> Path:
        return self.root / Path(target.hex_relative_path)

    def missing_assets(self, target: FirmwareTarget) -> list[Path]:
        return [
            path
            for path in (self.avrdude, self.avrdude_conf, self.firmware_path(target))
            if not path.is_file()
        ]

    def command(self, port: str, target: FirmwareTarget, baudrate: int) -> list[str]:
        firmware = self.firmware_path(target)
        return [
            str(self.avrdude),
            "-C",
            str(self.avrdude_conf),
            "-v",
            "-p",
            target.mcu,
            "-c",
            target.programmer,
            "-P",
            str(port),
            "-b",
            str(baudrate),
            "-D",
            "-U",
            f"flash:w:{firmware}:i",
        ]

    @staticmethod
    def _friendly_progress(line: str) -> str | None:
        lowered = line.casefold()
        if "writing flash" in lowered or "writing |" in lowered:
            return "Writing firmware to flash…"
        if "reading on-chip flash data" in lowered or "verifying" in lowered:
            return "Verifying firmware…"
        if "bytes of flash verified" in lowered:
            return "Firmware verified. Finishing…"
        return None

    def flash(
        self,
        port: str,
        target: FirmwareTarget,
        progress: ProgressCallback | None = None,
        *,
        timeout_seconds: float = 75.0,
    ) -> FlashResult:
        missing = self.missing_assets(target)
        if missing:
            joined = "\n".join(str(path) for path in missing)
            raise FirmwareFlashError(
                "The firmware updater is missing files from this OverheadLink installation:\n" + joined
            )

        callback = progress or (lambda _message: None)
        failures: list[str] = []
        for attempt, baudrate in enumerate(target.baudrates, start=1):
            callback(
                f"Opening {port} for {target.label} firmware v{target.firmware_version} "
                f"({baudrate} baud)…"
            )
            command = self.command(port, target, baudrate)
            creationflags = 0
            if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags,
                )
            except OSError as error:
                raise FirmwareFlashError(f"Could not start the bundled firmware flasher: {error}") from error

            callback("Writing and verifying firmware…")
            try:
                output, _ = process.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as error:
                process.kill()
                output, _ = process.communicate(timeout=5)
                raise FirmwareFlashError(f"Firmware flashing timed out on {port}.") from error

            return_code = process.returncode
            lines = output.splitlines()
            for line in lines:
                friendly = self._friendly_progress(line)
                if friendly:
                    callback(friendly)
            if return_code == 0:
                callback("Firmware write and verification completed successfully.")
                return FlashResult(target=target, port=port, baudrate=baudrate, output=output)

            tail = "\n".join(lines[-18:]).strip()
            failures.append(f"{baudrate} baud: {tail or f'avrdude exited with code {return_code}'}")
            if attempt < len(target.baudrates):
                callback("Bootloader did not answer at that speed; trying the alternate Nano bootloader speed…")

        detail = "\n\n".join(failures)
        raise FirmwareFlashError(
            f"Firmware flashing failed on {port}. Make sure no other program has the COM port open.\n\n{detail}"
        )
