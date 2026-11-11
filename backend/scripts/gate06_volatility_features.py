"""Research-only point-in-time range-volatility features.

These functions intentionally do not import production feature contracts,
databases, network clients, or protected-data paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Sequence


WINDOW = 20
PARKINSON_NAME = "parkinson_volatility_20"
GARMAN_KLASS_NAME = "garman_klass_volatility_20"


@dataclass(frozen=True)
class CompletedOHLC:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    complete: bool = True


def _validate_window(window: Sequence[CompletedOHLC]) -> tuple[CompletedOHLC, ...]:
    if len(window) != WINDOW:
        raise ValueError(f"volatility window must contain exactly {WINDOW} candles")
    if any(not candle.complete for candle in window):
        raise ValueError("volatility window contains an incomplete candle")
    for candle in window:
        values = (candle.open, candle.high, candle.low, candle.close)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("volatility window contains a nonfinite OHLC value")
        if min(values) <= 0 or candle.high < candle.low:
            raise ValueError("volatility window contains invalid OHLC values")
    timestamps = [candle.timestamp for candle in window]
    if timestamps != sorted(timestamps) or len(set(timestamps)) != WINDOW:
        raise ValueError("volatility window timestamps must be strictly increasing")
    return tuple(window)


def _rolling_variance(window: Sequence[CompletedOHLC], *, kind: str) -> float:
    candles = _validate_window(window)
    if kind == "parkinson":
        total = sum(math.log(candle.high / candle.low) ** 2 for candle in candles)
        variance = total / (4.0 * WINDOW * math.log(2.0))
    elif kind == "garman_klass":
        total = sum(
            0.5 * math.log(candle.high / candle.low) ** 2
            - (2.0 * math.log(2.0) - 1.0) * math.log(candle.close / candle.open) ** 2
            for candle in candles
        )
        variance = total / WINDOW
    else:  # pragma: no cover - private function guard
        raise ValueError(f"unknown volatility kind: {kind}")
    if not math.isfinite(variance):
        raise ValueError("volatility variance is nonfinite")
    return math.sqrt(max(variance, 0.0))


def parkinson_volatility(window: Sequence[CompletedOHLC]) -> float:
    """Return sqrt(mean(log(high/low)^2)/(4 log(2)))."""

    return _rolling_variance(window, kind="parkinson")


def garman_klass_volatility(window: Sequence[CompletedOHLC]) -> float:
    """Return sqrt(mean(.5 log(H/L)^2 - (2log(2)-1)log(C/O)^2))."""

    return _rolling_variance(window, kind="garman_klass")


def rolling_volatility_features(
    candles: Sequence[CompletedOHLC],
) -> list[dict[str, object]]:
    """Compute features ending at each completed candle with a full window."""

    output: list[dict[str, object]] = []
    for end in range(WINDOW, len(candles) + 1):
        window = candles[end - WINDOW : end]
        output.append(
            {
                "timestamp": window[-1].timestamp,
                PARKINSON_NAME: parkinson_volatility(window),
                GARMAN_KLASS_NAME: garman_klass_volatility(window),
            }
        )
    return output
