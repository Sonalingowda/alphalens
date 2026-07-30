"""Approved AlphaLens v2 Tier-A feature definitions."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from typing import Protocol

from app.features.contracts import (
    INTRADAY_TIMEFRAMES,
    CandleField,
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureDefinitionMetadata,
    FeatureHistoryType,
    FeatureOutputMetadata,
    FeatureValue,
    quantize_feature_value,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import (
    floor_timeframe_boundary,
    timeframe_duration,
)


class IntradayFeatureDefinition(Protocol):
    metadata: FeatureDefinitionMetadata

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
    ) -> tuple[FeatureValue, ...]:
        """Compute one isolated feature from a validated candle prefix."""
        ...


_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class CandleGeometry:
    metadata = FeatureDefinitionMetadata(
        identifier="candle_geometry",
        description=(
            "Dimensionless signed body, total range, upper wick, and lower "
            "wick geometry for a completed candle."
        ),
        category="price_action",
        definition_version="1.0.0",
        required_inputs=(
            CandleField.OPEN,
            CandleField.HIGH,
            CandleField.LOW,
            CandleField.CLOSE,
        ),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier="candle_body_fraction",
                description="Signed close-to-open change divided by open.",
                minimum_observations=1,
            ),
            FeatureOutputMetadata(
                identifier="candle_range_fraction",
                description="High-low range divided by open.",
                minimum_observations=1,
            ),
            FeatureOutputMetadata(
                identifier="upper_wick_fraction",
                description="Upper wick divided by open.",
                minimum_observations=1,
            ),
            FeatureOutputMetadata(
                identifier="lower_wick_fraction",
                description="Lower wick divided by open.",
                minimum_observations=1,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=1,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference="app.features.tier_a.CandleGeometry",
    )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
    ) -> tuple[FeatureValue, ...]:
        validated = _validated_intraday_candles(candles, timeframe)
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for candle in validated:
                timestamp = _required_timestamp(candle.timestamp)
                open_price = _required_decimal(candle.open)
                high = _required_decimal(candle.high)
                low = _required_decimal(candle.low)
                close = _required_decimal(candle.close)
                values = (
                    (close - open_price) / open_price,
                    (high - low) / open_price,
                    (high - max(open_price, close)) / open_price,
                    (min(open_price, close) - low) / open_price,
                )
                results.extend(
                    FeatureValue(
                        timestamp=timestamp,
                        feature_name=output.identifier,
                        value=quantize_feature_value(value),
                    )
                    for output, value in zip(
                        self.metadata.outputs,
                        values,
                        strict=True,
                    )
                )
        return tuple(results)


@dataclass(frozen=True, slots=True)
class TrueRange:
    metadata = FeatureDefinitionMetadata(
        identifier="true_range",
        description=(
            "Completed-candle price range including displacement from the "
            "immediately preceding completed close."
        ),
        category="volatility",
        definition_version="1.0.0",
        required_inputs=(
            CandleField.HIGH,
            CandleField.LOW,
            CandleField.CLOSE,
        ),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier="true_range",
                description=(
                    "Maximum of current high-low range and displacement of "
                    "each current extreme from the preceding close."
                ),
                minimum_observations=2,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=2,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference="app.features.tier_a.TrueRange",
    )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
    ) -> tuple[FeatureValue, ...]:
        validated = _validated_intraday_candles(candles, timeframe)
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index in range(1, len(validated)):
                previous = validated[index - 1]
                current = validated[index]
                high = _required_decimal(current.high)
                low = _required_decimal(current.low)
                previous_close = _required_decimal(previous.close)
                value = max(
                    high - low,
                    abs(high - previous_close),
                    abs(low - previous_close),
                )
                results.append(
                    FeatureValue(
                        timestamp=_required_timestamp(current.timestamp),
                        feature_name="true_range",
                        value=quantize_feature_value(value),
                    )
                )
        return tuple(results)


TIER_A_FEATURE_DEFINITIONS: tuple[IntradayFeatureDefinition, ...] = (
    CandleGeometry(),
    TrueRange(),
)
TIER_A_FEATURE_METADATA = tuple(
    definition.metadata for definition in TIER_A_FEATURE_DEFINITIONS
)


def _validated_intraday_candles(
    candles: tuple[Candle, ...],
    timeframe: CandleTimeframe,
) -> tuple[Candle, ...]:
    if timeframe not in INTRADAY_TIMEFRAMES:
        raise FeatureComputationError(
            "Tier-A features support only 5m, 10m, and 15m."
        )

    expected_step = timeframe_duration(timeframe)
    previous_timestamp = None
    for candle in candles:
        timestamp = candle.timestamp
        if timestamp is None:
            raise FeatureComputationError(
                "Feature input contains a missing timestamp."
            )
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise FeatureComputationError(
                "Feature input timestamp must be timezone-aware."
            )
        if timestamp.utcoffset() != timedelta(0):
            raise FeatureComputationError(
                "Feature input timestamp must be canonical UTC."
            )
        if floor_timeframe_boundary(timestamp, timeframe) != timestamp:
            raise FeatureComputationError(
                "Feature input timestamp is not timeframe-aligned."
            )
        if (
            previous_timestamp is not None
            and timestamp - previous_timestamp != expected_step
        ):
            raise FeatureComputationError(
                "Feature input candles must be consecutive and chronological."
            )
        _validate_ohlc(candle)
        previous_timestamp = timestamp
    return candles


def _validate_ohlc(candle: Candle) -> None:
    values = (candle.open, candle.high, candle.low, candle.close)
    if any(not isinstance(value, Decimal) for value in values):
        raise FeatureComputationError(
            "Feature input contains a missing or non-Decimal OHLC value."
        )
    open_price = _required_decimal(candle.open)
    high = _required_decimal(candle.high)
    low = _required_decimal(candle.low)
    close = _required_decimal(candle.close)
    if any(
        not value.is_finite()
        for value in (open_price, high, low, close)
    ):
        raise FeatureComputationError(
            "Feature input contains a non-finite OHLC value."
        )
    if min(open_price, high, low, close) <= 0:
        raise FeatureComputationError(
            "Feature input contains a non-positive OHLC value."
        )
    if low > high or not low <= open_price <= high or not low <= close <= high:
        raise FeatureComputationError(
            "Feature input contains an invalid OHLC relationship."
        )


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError(
            "Feature timestamp is unexpectedly missing."
        )
    return value


def _required_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise FeatureComputationError(
            "Feature input value is unexpectedly missing."
        )
    return value
