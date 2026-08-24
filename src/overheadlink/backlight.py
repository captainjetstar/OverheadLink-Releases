from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from .protocol import encode_message


class BrightnessPreset(StrEnum):
    FULL_LIGHT = "FULL LIGHT"
    HALF_DIM = "HALF DIM"
    DAY_TIME_DIM = "DAY TIME DIM"


FIRMWARE_TOKENS = {
    BrightnessPreset.FULL_LIGHT: "FULL_LIGHT",
    BrightnessPreset.HALF_DIM: "HALF_DIM",
    BrightnessPreset.DAY_TIME_DIM: "DAY_TIME_DIM",
}


@dataclass(slots=True)
class BacklightSettings:
    full_light: int = 255
    half_dim: int = 128
    day_time_dim: int = 180
    red: int = 255
    green: int = 128
    blue: int = 0
    led_count: int = 300
    startup_preset: BrightnessPreset = BrightnessPreset.DAY_TIME_DIM

    @classmethod
    def from_dict(cls, raw: dict) -> "BacklightSettings":
        presets = raw.get("presets", {})
        colour = raw.get("colour", {})
        return cls(
            full_light=int(presets.get("FULL LIGHT", 255)),
            half_dim=int(presets.get("HALF DIM", 128)),
            day_time_dim=int(presets.get("DAY TIME DIM", 180)),
            red=int(colour.get("red", 255)),
            green=int(colour.get("green", 128)),
            blue=int(colour.get("blue", 0)),
            led_count=int(raw.get("ledCount", 300)),
            startup_preset=BrightnessPreset(raw.get("startupPreset", "DAY TIME DIM")),
        )

    def brightness(self, preset: BrightnessPreset) -> int:
        return {
            BrightnessPreset.FULL_LIGHT: self.full_light,
            BrightnessPreset.HALF_DIM: self.half_dim,
            BrightnessPreset.DAY_TIME_DIM: self.day_time_dim,
        }[preset]

    def validate(self) -> None:
        for name, value in {
            "FULL LIGHT": self.full_light,
            "HALF DIM": self.half_dim,
            "DAY TIME DIM": self.day_time_dim,
            "red": self.red,
            "green": self.green,
            "blue": self.blue,
        }.items():
            if not 0 <= value <= 255:
                raise ValueError(f"{name} must be between 0 and 255")
        if self.led_count < 1:
            raise ValueError("LED count must be positive")


class BacklightController:
    def __init__(self, send: Callable[[bytes], None], settings: BacklightSettings):
        self.send = send
        self.settings = settings
        self.current = settings.startup_preset

    def apply(self, preset: BrightnessPreset) -> int:
        self.settings.validate()
        value = self.settings.brightness(preset)
        self.send(encode_message("PRESET", FIRMWARE_TOKENS[preset], value))
        self.current = preset
        return value

    def apply_colour(self) -> None:
        self.settings.validate()
        self.send(encode_message("COLOR", self.settings.red, self.settings.green, self.settings.blue))

