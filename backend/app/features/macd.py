"""Approved AlphaLens v2 MACD-01 feature definition."""

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
    exponential_moving_average,
    quantize_feature_value,
    validated_intraday_candles,
)
from app.features.ema import (
    EMA_12_IDENTIFIER,
    EMA_26_IDENTIFIER,
    EMA_DEFINITION_VERSION,
)
from app.market_data.models import Candle, CandleTimeframe


MACD_DEFINITION_VERSION = "1.0.0"
MACD_IDENTIFIER = "moving_average_convergence_divergence"
MACD_LINE_IDENTIFIER = "macd_line"
MACD_SIGNAL_IDENTIFIER = "macd_signal"
MACD_HISTOGRAM_IDENTIFIER = "macd_histogram"
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
MACD_LINE_MINIMUM_OBSERVATIONS = MACD_SLOW_PERIOD
MACD_SIGNAL_MINIMUM_OBSERVATIONS = MACD_SLOW_PERIOD + MACD_SIGNAL_PERIOD - 1
_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class MovingAverageConvergenceDivergence:
    metadata = FeatureDefinitionMetadata(
        identifier=MACD_IDENTIFIER,
        description=(
            "Approved MACD-01 fast/slow EMA separation, signal baseline, and "
            "histogram residual for a completed candle."
        ),
        category="momentum",
        definition_version=MACD_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=MACD_LINE_IDENTIFIER,
                description=(
                    "Signed EMA-12 minus EMA-26 price-level difference defined "
                    "by the approved MACD-01 quantitative specification."
                ),
                minimum_observations=MACD_LINE_MINIMUM_OBSERVATIONS,
            ),
            FeatureOutputMetadata(
                identifier=MACD_SIGNAL_IDENTIFIER,
                description=(
                    "Nine-observation EMA baseline of the compact MACD line sequence."
                ),
                minimum_observations=MACD_SIGNAL_MINIMUM_OBSERVATIONS,
            ),
            FeatureOutputMetadata(
                identifier=MACD_HISTOGRAM_IDENTIFIER,
                description="Signed contemporaneous MACD line minus signal residual.",
                minimum_observations=MACD_SIGNAL_MINIMUM_OBSERVATIONS,
            ),
        ),
        history_type=FeatureHistoryType.RECURSIVE,
        maximum_lookback_observations=None,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.macd.MovingAverageConvergenceDivergence"
        ),
        dependencies=(EMA_12_IDENTIFIER, EMA_26_IDENTIFIER),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=EMA_12_IDENTIFIER,
                definition_version=EMA_DEFINITION_VERSION,
                output_names=(EMA_12_IDENTIFIER,),
            ),
            FeatureDependencyMetadata(
                identifier=EMA_26_IDENTIFIER,
                definition_version=EMA_DEFINITION_VERSION,
                output_names=(EMA_26_IDENTIFIER,),
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
        fast_values, slow_values = _validated_ema_dependencies(
            validated,
            dependency_inputs,
        )
        if not slow_values:
            return ()

        fast_by_timestamp = {value.timestamp: value for value in fast_values}
        line_timestamps = tuple(value.timestamp for value in slow_values)

        with localcontext() as context:
            context.prec = 50
            raw_lines = tuple(
                fast_by_timestamp[timestamp].value - slow_value.value
                for timestamp, slow_value in zip(
                    line_timestamps,
                    slow_values,
                    strict=True,
                )
            )
            raw_signals = exponential_moving_average(
                raw_lines,
                MACD_SIGNAL_PERIOD,
            )
            return _build_outputs(
                line_timestamps,
                raw_lines,
                raw_signals,
            )


MACD_FEATURE_DEFINITIONS = (MovingAverageConvergenceDivergence(),)
MACD_FEATURE_METADATA = tuple(
    definition.metadata for definition in MACD_FEATURE_DEFINITIONS
)


def _validated_ema_dependencies(
    candles: tuple[Candle, ...],
    dependency_inputs: tuple[FeatureDependencyInput, ...],
) -> tuple[tuple[FeatureValue, ...], tuple[FeatureValue, ...]]:
    if len(dependency_inputs) != 2:
        raise FeatureComputationError(
            "MACD-01 requires exactly EMA-12 and EMA-26 dependency inputs."
        )
    fast = _validated_ema_dependency(
        dependency_inputs[0],
        candles,
        identifier=EMA_12_IDENTIFIER,
        period=MACD_FAST_PERIOD,
    )
    slow = _validated_ema_dependency(
        dependency_inputs[1],
        candles,
        identifier=EMA_26_IDENTIFIER,
        period=MACD_SLOW_PERIOD,
    )
    return fast, slow


def _validated_ema_dependency(
    dependency: FeatureDependencyInput,
    candles: tuple[Candle, ...],
    *,
    identifier: str,
    period: int,
) -> tuple[FeatureValue, ...]:
    if (
        dependency.definition_identifier != identifier
        or dependency.definition_version != EMA_DEFINITION_VERSION
        or dependency.output_name != identifier
    ):
        raise FeatureComputationError(
            f"MACD-01 requires registered {identifier} 1.0.0."
        )
    expected_timestamps = tuple(
        _required_timestamp(candle.timestamp) for candle in candles[period - 1 :]
    )
    if tuple(value.timestamp for value in dependency.values) != expected_timestamps:
        raise FeatureComputationError(
            f"MACD-01 {identifier} coverage is incomplete or unordered."
        )
    for value in dependency.values:
        if value.feature_name != identifier:
            raise FeatureComputationError(
                f"MACD-01 received an unexpected {identifier} output."
            )
        if not isinstance(value.value, Decimal) or not value.value.is_finite():
            raise FeatureComputationError(
                f"MACD-01 received an invalid {identifier} Decimal."
            )
        if quantize_feature_value(value.value) != value.value:
            raise FeatureComputationError(
                f"MACD-01 received an unquantized {identifier} value."
            )
    return dependency.values


def _build_outputs(
    timestamps: tuple[datetime, ...],
    raw_lines: tuple[Decimal, ...],
    raw_signals: tuple[Decimal | None, ...],
) -> tuple[FeatureValue, ...]:
    results: list[FeatureValue] = []
    emitted_by_output: dict[str, list[FeatureValue]] = {
        MACD_LINE_IDENTIFIER: [],
        MACD_SIGNAL_IDENTIFIER: [],
        MACD_HISTOGRAM_IDENTIFIER: [],
    }
    seed_ema_dependencies = tuple(
        dependency
        for timestamp in timestamps[:MACD_SIGNAL_PERIOD]
        for dependency in _ema_dependencies(timestamp)
    )

    for index, (timestamp, raw_line) in enumerate(
        zip(timestamps, raw_lines, strict=True)
    ):
        line_dependencies = list(_ema_dependencies(timestamp))
        previous_line = _previous_dependency(
            emitted_by_output[MACD_LINE_IDENTIFIER],
            MACD_LINE_IDENTIFIER,
        )
        if previous_line is not None:
            line_dependencies.append(previous_line)
        line_value = FeatureValue(
            timestamp=timestamp,
            feature_name=MACD_LINE_IDENTIFIER,
            value=quantize_feature_value(raw_line),
            dependencies=tuple(line_dependencies),
        )
        results.append(line_value)
        emitted_by_output[MACD_LINE_IDENTIFIER].append(line_value)

        raw_signal = raw_signals[index]
        if raw_signal is None:
            continue

        previous_signal = _previous_dependency(
            emitted_by_output[MACD_SIGNAL_IDENTIFIER],
            MACD_SIGNAL_IDENTIFIER,
        )
        signal_dependencies = (
            seed_ema_dependencies
            if previous_signal is None
            else _ema_dependencies(timestamp) + (previous_signal,)
        )
        signal_value = FeatureValue(
            timestamp=timestamp,
            feature_name=MACD_SIGNAL_IDENTIFIER,
            value=quantize_feature_value(raw_signal),
            dependencies=signal_dependencies,
        )
        results.append(signal_value)
        emitted_by_output[MACD_SIGNAL_IDENTIFIER].append(signal_value)

        previous_histogram = _previous_dependency(
            emitted_by_output[MACD_HISTOGRAM_IDENTIFIER],
            MACD_HISTOGRAM_IDENTIFIER,
        )
        histogram_dependencies = seed_ema_dependencies
        if previous_histogram is not None:
            histogram_dependencies = (
                _ema_dependencies(timestamps[index - 1])
                + _ema_dependencies(timestamp)
                + (previous_histogram,)
            )
        histogram_value = FeatureValue(
            timestamp=timestamp,
            feature_name=MACD_HISTOGRAM_IDENTIFIER,
            value=quantize_feature_value(raw_line - raw_signal),
            dependencies=histogram_dependencies,
        )
        results.append(histogram_value)
        emitted_by_output[MACD_HISTOGRAM_IDENTIFIER].append(histogram_value)

    return tuple(results)


def _ema_dependencies(timestamp: datetime) -> tuple[FeatureValueDependency, ...]:
    return (
        FeatureValueDependency(
            definition_identifier=EMA_12_IDENTIFIER,
            definition_version=EMA_DEFINITION_VERSION,
            output_name=EMA_12_IDENTIFIER,
            timestamp=timestamp,
        ),
        FeatureValueDependency(
            definition_identifier=EMA_26_IDENTIFIER,
            definition_version=EMA_DEFINITION_VERSION,
            output_name=EMA_26_IDENTIFIER,
            timestamp=timestamp,
        ),
    )


def _previous_dependency(
    values: list[FeatureValue],
    output_name: str,
) -> FeatureValueDependency | None:
    if not values:
        return None
    return FeatureValueDependency(
        definition_identifier=MACD_IDENTIFIER,
        definition_version=MACD_DEFINITION_VERSION,
        output_name=output_name,
        timestamp=values[-1].timestamp,
    )


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("MACD-01 source timestamp is missing.")
    return value
