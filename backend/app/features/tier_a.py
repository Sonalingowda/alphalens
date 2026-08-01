"""Approved AlphaLens v2 Tier-A feature definitions."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Protocol

from app.features.contracts import (
    CandleField,
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureDefinitionMetadata,
    FeatureDependencyInput,
    FeatureHistoryType,
    FeatureOutputMetadata,
    FeatureValue,
    quantize_feature_value,
    validated_intraday_candles,
)
from app.market_data.models import Candle, CandleTimeframe


class IntradayFeatureDefinition(Protocol):
    metadata: FeatureDefinitionMetadata

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
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
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        if dependency_inputs:
            raise FeatureComputationError(
                "Candle Geometry does not accept feature dependencies."
            )
        validated = validated_intraday_candles(candles, timeframe)
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
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        if dependency_inputs:
            raise FeatureComputationError(
                "True Range does not accept feature dependencies."
            )
        validated = validated_intraday_candles(candles, timeframe)
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


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("Feature timestamp is unexpectedly missing.")
    return value


def _required_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise FeatureComputationError("Feature input value is unexpectedly missing.")
    return value
