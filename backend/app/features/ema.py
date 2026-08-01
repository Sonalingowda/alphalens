"""Approved AlphaLens v2 EMA-01 feature definition."""

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
    exponential_moving_average,
    quantize_feature_value,
    validated_intraday_candles,
)
from app.market_data.models import Candle, CandleTimeframe


EMA_PERIOD = 20
EMA_DEFINITION_VERSION = "1.0.0"
EMA_IDENTIFIER = "exponential_moving_average"
_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class ExponentialMovingAverage:
    metadata = FeatureDefinitionMetadata(
        identifier=EMA_IDENTIFIER,
        description=(
            "Approved EMA-01 smoothed canonical Close price baseline for a "
            "completed candle."
        ),
        category="trend",
        definition_version=EMA_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=EMA_IDENTIFIER,
                description=(
                    "Price-level output defined by the approved EMA-01 "
                    "successor quantitative specification."
                ),
                minimum_observations=EMA_PERIOD,
            ),
        ),
        history_type=FeatureHistoryType.RECURSIVE,
        maximum_lookback_observations=None,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference="app.features.ema.ExponentialMovingAverage",
    )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        if dependency_inputs:
            raise FeatureComputationError(
                "EMA-01 does not accept derived feature dependencies."
            )
        validated = validated_intraday_candles(candles, timeframe)
        closes = tuple(_required_decimal(candle.close) for candle in validated)
        raw_values = exponential_moving_average(closes, EMA_PERIOD)
        results: list[FeatureValue] = []

        for index in range(EMA_PERIOD - 1, len(validated)):
            raw_value = raw_values[index]
            if raw_value is None:
                raise FeatureComputationError(
                    "EMA-01 recursive state is unexpectedly unavailable."
                )
            timestamp = _required_timestamp(validated[index].timestamp)
            dependencies = ()
            if results:
                dependencies = (
                    FeatureValueDependency(
                        definition_identifier=EMA_IDENTIFIER,
                        definition_version=EMA_DEFINITION_VERSION,
                        output_name=EMA_IDENTIFIER,
                        timestamp=results[-1].timestamp,
                    ),
                )
            results.append(
                FeatureValue(
                    timestamp=timestamp,
                    feature_name=EMA_IDENTIFIER,
                    value=quantize_feature_value(raw_value),
                    dependencies=dependencies,
                )
            )

        return tuple(results)


EMA_FEATURE_DEFINITIONS = (ExponentialMovingAverage(),)
EMA_FEATURE_METADATA = tuple(
    definition.metadata for definition in EMA_FEATURE_DEFINITIONS
)


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("EMA-01 source timestamp is missing.")
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal):
        raise FeatureComputationError("EMA-01 Close input is missing or non-Decimal.")
    return value
