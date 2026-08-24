from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import fmean, pstdev
from time import monotonic

from .models import canonical_pin


@dataclass(frozen=True, slots=True)
class DigitalObservation:
    board_id: str
    pin: str
    value: bool
    timestamp: float


@dataclass(frozen=True, slots=True)
class DigitalLearningResult:
    board_id: str
    pin: str
    active_low: bool
    confirmations: int
    confidence: float


class DigitalLearningSession:
    """Requires two deliberate activations of one pin before proposing a map."""

    def __init__(self, minimum_gap_seconds: float = 0.15, timeout_seconds: float = 45.0):
        self.started = monotonic()
        self.minimum_gap = minimum_gap_seconds
        self.timeout = timeout_seconds
        self.activations: dict[tuple[str, str, bool], list[float]] = defaultdict(list)
        self.all_events: list[DigitalObservation] = []

    @property
    def expired(self) -> bool:
        return monotonic() - self.started > self.timeout

    def observe(self, board_id: str, pin: str | int, value: bool, timestamp: float | None = None) -> DigitalLearningResult | None:
        timestamp = monotonic() if timestamp is None else timestamp
        pin = canonical_pin(pin)
        observation = DigitalObservation(board_id, pin, value, timestamp)
        self.all_events.append(observation)
        key = (board_id, pin, value)
        times = self.activations[key]
        if not times or timestamp - times[-1] >= self.minimum_gap:
            times.append(timestamp)
        if len(times) < 2:
            return None

        contenders = sorted(
            ((len(seen), candidate) for candidate, seen in self.activations.items()),
            reverse=True,
        )
        best_count, best = contenders[0]
        second_count = contenders[1][0] if len(contenders) > 1 else 0
        if best != key or best_count < 2 or best_count == second_count:
            return None
        confidence = min(1.0, 0.70 + 0.15 * (best_count - second_count))
        return DigitalLearningResult(board_id, pin, active_low=not value, confirmations=best_count, confidence=confidence)


@dataclass(frozen=True, slots=True)
class AnalogLearningResult:
    board_id: str
    pin: str
    minimum: int
    maximum: int
    centre: int
    noise: float
    inverted: bool
    confidence: float


@dataclass(slots=True)
class AnalogLearningSession:
    minimum_range: int = 150
    samples: dict[tuple[str, str], list[int]] = field(default_factory=lambda: defaultdict(list))

    def observe(self, board_id: str, pin: str | int, value: int) -> None:
        if not 0 <= value <= 1023:
            raise ValueError(f"Analogue value outside 0..1023: {value}")
        self.samples[(board_id, canonical_pin(pin))].append(value)

    def finalize(self) -> AnalogLearningResult:
        ranked: list[tuple[int, tuple[str, str], list[int]]] = []
        for key, values in self.samples.items():
            # A potentiometer should produce several distinct levels. Requiring
            # this prevents a nearby two-state switch on an analogue-capable pin
            # from winning simply because it also spans close to 0..1023.
            if len(values) >= 5 and len(set(values)) >= 5:
                ranked.append((max(values) - min(values), key, values))
        if not ranked:
            raise ValueError("No analogue channel has enough samples")
        ranked.sort(reverse=True, key=lambda item: item[0])
        span, (board_id, pin), values = ranked[0]
        if span < self.minimum_range:
            raise ValueError(f"Best analogue range is only {span}; check 5V, GND and wiper wiring")
        runner_up = ranked[1][0] if len(ranked) > 1 else 0
        endpoint_window = max(2, len(values) // 10)
        start_mean = fmean(values[:endpoint_window])
        end_mean = fmean(values[-endpoint_window:])
        centre = round(fmean(values[len(values) // 2 - 1 : len(values) // 2 + 2]))
        noise_window = values[-min(10, len(values)) :]
        noise = pstdev(noise_window) if len(noise_window) > 1 else 0.0
        separation = max(0.0, min(1.0, (span - runner_up) / max(span, 1)))
        confidence = min(1.0, 0.65 + 0.25 * separation + (0.10 if span >= 800 else 0.0))
        return AnalogLearningResult(
            board_id=board_id,
            pin=pin,
            minimum=min(values),
            maximum=max(values),
            centre=centre,
            noise=round(noise, 2),
            inverted=end_mean < start_mean,
            confidence=confidence,
        )
