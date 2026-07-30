"""Shared contracts and input safeguards for feature computations."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from enum import StrEnum
import re
from typing import Protocol

from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import (
    floor_timeframe_boundary,
    timeframe_duration,
)


FEATURE_VALUE_QUANTUM = Decimal("0.000000000000000001")
FEATURE_AVAILABILITY_CONTRACT_VERSION = "1.0.0"
_FEATURE_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
INTRADAY_TIMEFRAMES = frozenset(
    {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    }
)


class FeatureComputationError(ValueError):
    """Raised when source data cannot produce defensible feature values."""


class FeatureMetadataError(ValueError):
    """Raised when a declarative feature definition is invalid."""


class CandleField(StrEnum):
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"


class FeatureAvailabilityRule(StrEnum):
    CANDLE_CLOSE = "candle_close"


class FeatureHistoryType(StrEnum):
    BOUNDED = "bounded"
    RECURSIVE = "recursive"


@dataclass(frozen=True, slots=True)
class FeatureOutputMetadata:
    identifier: str
    description: str
    minimum_observations: int

    def __post_init__(self) -> None:
        _validate_identifier(self.identifier, "Feature output identifier")
        if not self.description.strip():
            raise FeatureMetadataError(
                "Feature output description must not be empty."
            )
        if self.minimum_observations <= 0:
            raise FeatureMetadataError(
                "Feature output minimum observations must be positive."
            )


@dataclass(frozen=True, slots=True)
class FeatureDefinitionMetadata:
    identifier: str
    description: str
    category: str
    definition_version: str
    required_inputs: tuple[CandleField, ...]
    supported_timeframes: tuple[CandleTimeframe, ...]
    outputs: tuple[FeatureOutputMetadata, ...]
    history_type: FeatureHistoryType
    maximum_lookback_observations: int | None
    requires_continuity: bool
    availability_rule: FeatureAvailabilityRule
    dependencies: tuple[str, ...] = ()
    decimal_quantum: Decimal = FEATURE_VALUE_QUANTUM

    def __post_init__(self) -> None:
        _validate_identifier(self.identifier, "Feature identifier")
        if not self.description.strip():
            raise FeatureMetadataError(
                "Feature description must not be empty."
            )
        if not self.category.strip():
            raise FeatureMetadataError("Feature category must not be empty.")
        if not _SEMANTIC_VERSION_PATTERN.fullmatch(
            self.definition_version
        ):
            raise FeatureMetadataError(
                "Feature definition version must use MAJOR.MINOR.PATCH."
            )
        if not self.required_inputs:
            raise FeatureMetadataError(
                "Feature definition must declare required candle inputs."
            )
        if len(set(self.required_inputs)) != len(self.required_inputs):
            raise FeatureMetadataError(
                "Feature definition contains duplicate required inputs."
            )
        if not self.supported_timeframes:
            raise FeatureMetadataError(
                "Feature definition must declare supported timeframes."
            )
        if len(set(self.supported_timeframes)) != len(
            self.supported_timeframes
        ):
            raise FeatureMetadataError(
                "Feature definition contains duplicate timeframes."
            )
        unsupported = set(self.supported_timeframes) - INTRADAY_TIMEFRAMES
        if unsupported:
            raise FeatureMetadataError(
                "Phase 3 definitions support only 5m, 10m, and 15m."
            )
        if not self.outputs:
            raise FeatureMetadataError(
                "Feature definition must declare at least one output."
            )
        output_names = tuple(output.identifier for output in self.outputs)
        if len(set(output_names)) != len(output_names):
            raise FeatureMetadataError(
                "Feature definition contains duplicate output identifiers."
            )
        if (
            self.history_type is FeatureHistoryType.BOUNDED
            and self.maximum_lookback_observations is None
        ):
            raise FeatureMetadataError(
                "Bounded features require a maximum lookback."
            )
        if (
            self.maximum_lookback_observations is not None
            and self.maximum_lookback_observations <= 0
        ):
            raise FeatureMetadataError(
                "Maximum lookback observations must be positive."
            )
        if (
            self.maximum_lookback_observations is not None
            and max(
                output.minimum_observations for output in self.outputs
            )
            > self.maximum_lookback_observations
        ):
            raise FeatureMetadataError(
                "Output warm-up cannot exceed maximum lookback."
            )
        if not self.requires_continuity:
            raise FeatureMetadataError(
                "Phase 3 features must require continuous candle input."
            )
        if self.availability_rule is not FeatureAvailabilityRule.CANDLE_CLOSE:
            raise FeatureMetadataError(
                "Phase 3 features must use candle-close availability."
            )
        if len(set(self.dependencies)) != len(self.dependencies):
            raise FeatureMetadataError(
                "Feature definition contains duplicate dependencies."
            )
        for dependency in self.dependencies:
            _validate_identifier(dependency, "Feature dependency")
            if dependency == self.identifier:
                raise FeatureMetadataError(
                    "Feature definition cannot depend on itself."
                )
        if (
            not self.decimal_quantum.is_finite()
            or self.decimal_quantum <= 0
        ):
            raise FeatureMetadataError(
                "Feature Decimal quantum must be finite and positive."
            )


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


def feature_available_at(
    candle_timestamp: datetime,
    timeframe: CandleTimeframe,
    rule: FeatureAvailabilityRule,
) -> datetime:
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise FeatureMetadataError(
            "Feature availability supports only 5m, 10m, and 15m."
        )
    if candle_timestamp.tzinfo is None or candle_timestamp.utcoffset() is None:
        raise FeatureMetadataError(
            "Feature availability requires a timezone-aware timestamp."
        )
    if candle_timestamp.utcoffset().total_seconds() != 0:
        raise FeatureMetadataError(
            "Feature availability requires a canonical UTC timestamp."
        )
    if floor_timeframe_boundary(candle_timestamp, timeframe) != candle_timestamp:
        raise FeatureMetadataError(
            "Feature timestamp is not aligned to its timeframe."
        )
    if rule is not FeatureAvailabilityRule.CANDLE_CLOSE:
        raise FeatureMetadataError("Unsupported feature availability rule.")
    return candle_timestamp + timeframe_duration(timeframe)


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


def _validate_identifier(value: str, label: str) -> None:
    if not _FEATURE_IDENTIFIER_PATTERN.fullmatch(value):
        raise FeatureMetadataError(
            f"{label} must use lowercase snake_case."
        )
