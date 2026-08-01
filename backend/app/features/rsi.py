"""Approved AlphaLens v2 RSI-01 feature definition."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.features.contracts import (
    CandleField,
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureDefinitionMetadata,
    FeatureDependencyInput,
    FeatureHistoryType,
    FeatureOutputMetadata,
    FeatureValue,
    FeatureValueDependency,
    quantize_feature_value,
    validated_intraday_candles,
    wilder_relative_strength_index,
)
from app.market_data.models import Candle, CandleTimeframe


RSI_PERIOD = 14
RSI_MINIMUM_OBSERVATIONS = RSI_PERIOD + 1
RSI_DEFINITION_VERSION = "1.0.0"
RSI_IDENTIFIER = "relative_strength_index"
_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class RelativeStrengthIndex:
    metadata = FeatureDefinitionMetadata(
        identifier=RSI_IDENTIFIER,
        description=(
            "Approved RSI-01 bounded balance of Wilder-smoothed canonical "
            "Close gains and losses for a completed candle."
        ),
        category="momentum",
        definition_version=RSI_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=RSI_IDENTIFIER,
                description=(
                    "Dimensionless bounded output defined by the approved "
                    "RSI-01 quantitative specification."
                ),
                minimum_observations=RSI_MINIMUM_OBSERVATIONS,
            ),
        ),
        history_type=FeatureHistoryType.RECURSIVE,
        maximum_lookback_observations=None,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference="app.features.rsi.RelativeStrengthIndex",
    )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        if dependency_inputs:
            raise FeatureComputationError(
                "RSI-01 does not accept derived feature dependencies."
            )
        validated = validated_intraday_candles(candles, timeframe)
        closes = tuple(_required_decimal(candle.close) for candle in validated)
        raw_values = wilder_relative_strength_index(closes, RSI_PERIOD)
        results: list[FeatureValue] = []

        for index in range(RSI_PERIOD, len(validated)):
            raw_value = raw_values[index]
            if raw_value is None:
                raise FeatureComputationError(
                    "RSI-01 recursive state is unexpectedly unavailable."
                )
            timestamp = _required_timestamp(validated[index].timestamp)
            dependencies = ()
            if results:
                dependencies = (
                    FeatureValueDependency(
                        definition_identifier=RSI_IDENTIFIER,
                        definition_version=RSI_DEFINITION_VERSION,
                        output_name=RSI_IDENTIFIER,
                        timestamp=results[-1].timestamp,
                    ),
                )
            results.append(
                FeatureValue(
                    timestamp=timestamp,
                    feature_name=RSI_IDENTIFIER,
                    value=quantize_feature_value(raw_value),
                    dependencies=dependencies,
                )
            )

        return tuple(results)


RSI_FEATURE_DEFINITIONS = (RelativeStrengthIndex(),)
RSI_FEATURE_METADATA = tuple(
    definition.metadata for definition in RSI_FEATURE_DEFINITIONS
)


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("RSI-01 source timestamp is missing.")
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal):
        raise FeatureComputationError("RSI-01 Close input is missing or non-Decimal.")
    return value
