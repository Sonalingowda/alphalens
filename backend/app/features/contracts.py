"""Shared contracts and input safeguards for feature computations."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Protocol

from app.market_data.models import Candle


FEATURE_VALUE_QUANTUM = Decimal("0.000000000000000001")


class FeatureComputationError(ValueError):
    """Raised when source data cannot produce defensible feature values."""


@dataclass(frozen=True, slots=True)
class CandlePoint:
    timestamp: datetime
    close: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class FeatureValue:
    timestamp: datetime
    feature_name: str
    value: Decimal


class FeatureDefinition(Protocol):
    feature_names: tuple[str, ...]

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        """Compute values using each candle and its preceding prefix only."""
        ...


def validated_candle_points(candles: tuple[Candle, ...]) -> tuple[CandlePoint, ...]:
    """Validate ordered, complete OHLCV inputs for an individual feature."""
    points: list[CandlePoint] = []
    previous_timestamp: datetime | None = None

    for candle in candles:
        timestamp = candle.timestamp
        values = (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        )
        if timestamp is None or any(value is None for value in values):
            raise FeatureComputationError(
                "Feature input contains a missing required candle field."
            )
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise FeatureComputationError(
                "Feature input timestamps must be timezone-aware."
            )
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise FeatureComputationError(
                "Feature input timestamps must be strictly chronological."
            )

        open_price = _required_decimal(candle.open)
        high = _required_decimal(candle.high)
        low = _required_decimal(candle.low)
        close = _required_decimal(candle.close)
        volume = _required_decimal(candle.volume)
        if min(open_price, high, low, close) <= 0 or volume < 0:
            raise FeatureComputationError(
                f"Feature input contains invalid values at {timestamp.isoformat()}."
            )
        if low > high or not low <= open_price <= high or not low <= close <= high:
            raise FeatureComputationError(
                f"Feature input contains invalid OHLC relationships at "
                f"{timestamp.isoformat()}."
            )

        points.append(CandlePoint(timestamp=timestamp, close=close, volume=volume))
        previous_timestamp = timestamp

    return tuple(points)


def quantize_feature_value(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise FeatureComputationError("Feature computation produced a non-finite value.")
    with localcontext() as context:
        context.prec = 50
        return value.quantize(FEATURE_VALUE_QUANTUM, rounding=ROUND_HALF_EVEN)


def exponential_moving_average(
    values: tuple[Decimal, ...],
    period: int,
) -> tuple[Decimal | None, ...]:
    if period <= 0:
        raise FeatureComputationError("EMA period must be positive.")

    results: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return tuple(results)

    with localcontext() as context:
        context.prec = 50
        previous = sum(values[:period], Decimal(0)) / Decimal(period)
        results[period - 1] = previous
        multiplier = Decimal(2) / Decimal(period + 1)

        for index in range(period, len(values)):
            previous = (values[index] - previous) * multiplier + previous
            results[index] = previous

    return tuple(results)


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise FeatureComputationError("Feature input value is unexpectedly missing.")
    return value
