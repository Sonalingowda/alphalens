"""Approved Phase 2 ATR-01 feature definition."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext

from app.features.contracts import (
    CandleField,
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureDefinitionMetadata,
    FeatureDependencyInput,
    FeatureDependencyMetadata,
    FeatureHistoryType,
    FeatureOutputMetadata,
    FeatureValue,
    FeatureValueDependency,
    quantize_feature_value,
    validated_intraday_candles,
)
from app.market_data.models import Candle, CandleTimeframe


ATR_PERIOD = 14
ATR_DEFINITION_VERSION = "1.0.0"
TRUE_RANGE_DEFINITION_VERSION = "1.0.0"
_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class AverageTrueRange:
    metadata = FeatureDefinitionMetadata(
        identifier="average_true_range",
        description=(
            "Arithmetic mean of the latest 14 consecutive registered True "
            "Range values for completed candles."
        ),
        category="volatility",
        definition_version=ATR_DEFINITION_VERSION,
        required_inputs=(
            CandleField.HIGH,
            CandleField.LOW,
            CandleField.CLOSE,
        ),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier="average_true_range",
                description=(
                    "Current-inclusive 14-observation arithmetic mean of "
                    "registered True Range in quote-price units."
                ),
                minimum_observations=ATR_PERIOD + 1,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=ATR_PERIOD + 1,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference="app.features.atr.AverageTrueRange",
        dependencies=("true_range",),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier="true_range",
                definition_version=TRUE_RANGE_DEFINITION_VERSION,
                output_names=("true_range",),
            ),
        ),
    )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        validated = validated_intraday_candles(candles, timeframe)
        true_ranges = _validated_true_range_dependencies(
            validated,
            dependency_inputs,
        )
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index in range(ATR_PERIOD - 1, len(true_ranges)):
                window = true_ranges[index - ATR_PERIOD + 1 : index + 1]
                raw_value = sum(
                    (value.value for value in window),
                    Decimal(0),
                ) / Decimal(ATR_PERIOD)
                results.append(
                    FeatureValue(
                        timestamp=window[-1].timestamp,
                        feature_name="average_true_range",
                        value=quantize_feature_value(raw_value),
                        dependencies=tuple(
                            FeatureValueDependency(
                                definition_identifier="true_range",
                                definition_version=(TRUE_RANGE_DEFINITION_VERSION),
                                output_name="true_range",
                                timestamp=value.timestamp,
                            )
                            for value in window
                        ),
                    )
                )
        return tuple(results)


ATR_FEATURE_DEFINITIONS = (AverageTrueRange(),)
ATR_FEATURE_METADATA = tuple(
    definition.metadata for definition in ATR_FEATURE_DEFINITIONS
)


def _validated_true_range_dependencies(
    candles: tuple[Candle, ...],
    dependency_inputs: tuple[FeatureDependencyInput, ...],
) -> tuple[FeatureValue, ...]:
    if len(dependency_inputs) != 1:
        raise FeatureComputationError(
            "Average True Range requires exactly one True Range input."
        )
    dependency = dependency_inputs[0]
    if (
        dependency.definition_identifier != "true_range"
        or dependency.definition_version != TRUE_RANGE_DEFINITION_VERSION
        or dependency.output_name != "true_range"
    ):
        raise FeatureComputationError(
            "Average True Range requires registered true_range 1.0.0."
        )

    expected_timestamps = tuple(
        _required_timestamp(candle.timestamp) for candle in candles[1:]
    )
    values = dependency.values
    if tuple(value.timestamp for value in values) != expected_timestamps:
        raise FeatureComputationError(
            "Average True Range dependency coverage is incomplete or unordered."
        )
    for value in values:
        if value.feature_name != "true_range":
            raise FeatureComputationError(
                "Average True Range received an unexpected dependency output."
            )
        if (
            not isinstance(value.value, Decimal)
            or not value.value.is_finite()
            or value.value < 0
            or quantize_feature_value(value.value) != value.value
        ):
            raise FeatureComputationError(
                "Average True Range received an invalid True Range value."
            )
    return values


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("Average True Range source timestamp is missing.")
    return value
