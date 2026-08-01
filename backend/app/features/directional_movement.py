"""Approved AlphaLens v2 Directional Movement feature family."""

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
    wilder_smoothed_sum,
)
from app.market_data.models import Candle, CandleTimeframe


DIRECTIONAL_MOVEMENT_PERIOD = 14
DIRECTIONAL_MOVEMENT_DEFINITION_VERSION = "1.0.0"
DIRECTIONAL_MOVEMENT_IDENTIFIER = "directional_movement"
POSITIVE_DM_IDENTIFIER = "positive_directional_movement"
NEGATIVE_DM_IDENTIFIER = "negative_directional_movement"
DIRECTIONAL_INDICATORS_IDENTIFIER = "directional_indicators"
POSITIVE_DI_IDENTIFIER = "positive_directional_indicator"
NEGATIVE_DI_IDENTIFIER = "negative_directional_indicator"
DIRECTIONAL_INDEX_IDENTIFIER = "directional_index"
AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER = "average_directional_index"
ADXR_IDENTIFIER = "average_directional_movement_rating"
TRUE_RANGE_IDENTIFIER = "true_range"
TRUE_RANGE_DEFINITION_VERSION = "1.0.0"
_HUNDRED = Decimal(100)
_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class DirectionalMovement:
    metadata = FeatureDefinitionMetadata(
        identifier=DIRECTIONAL_MOVEMENT_IDENTIFIER,
        description="Strict dominant movement of consecutive canonical High and Low.",
        category="trend_strength",
        definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
        required_inputs=(CandleField.HIGH, CandleField.LOW),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=POSITIVE_DM_IDENTIFIER,
                description="Retained strictly dominant upward High movement.",
                minimum_observations=2,
            ),
            FeatureOutputMetadata(
                identifier=NEGATIVE_DM_IDENTIFIER,
                description="Retained strictly dominant downward Low movement.",
                minimum_observations=2,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=2,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.directional_movement.DirectionalMovement"
        ),
    )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        if dependency_inputs:
            raise FeatureComputationError(
                "Directional Movement does not accept derived dependencies."
            )
        validated = validated_intraday_candles(candles, timeframe)
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index in range(1, len(validated)):
                current = validated[index]
                previous = validated[index - 1]
                upward = _required_decimal(current.high) - _required_decimal(
                    previous.high
                )
                downward = _required_decimal(previous.low) - _required_decimal(
                    current.low
                )
                positive = upward if upward > downward and upward > 0 else Decimal(0)
                negative = (
                    downward if downward > upward and downward > 0 else Decimal(0)
                )
                timestamp = _required_timestamp(current.timestamp)
                results.extend(
                    (
                        FeatureValue(
                            timestamp=timestamp,
                            feature_name=POSITIVE_DM_IDENTIFIER,
                            value=quantize_feature_value(positive),
                        ),
                        FeatureValue(
                            timestamp=timestamp,
                            feature_name=NEGATIVE_DM_IDENTIFIER,
                            value=quantize_feature_value(negative),
                        ),
                    )
                )
        return tuple(results)


@dataclass(frozen=True, slots=True)
class DirectionalIndicators:
    metadata = FeatureDefinitionMetadata(
        identifier=DIRECTIONAL_INDICATORS_IDENTIFIER,
        description=(
            "Wilder-smoothed positive and negative directional movement relative "
            "to registered True Range."
        ),
        category="trend_strength",
        definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
        required_inputs=(CandleField.HIGH, CandleField.LOW, CandleField.CLOSE),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=POSITIVE_DI_IDENTIFIER,
                description="Smoothed positive movement relative to True Range.",
                minimum_observations=DIRECTIONAL_MOVEMENT_PERIOD + 1,
            ),
            FeatureOutputMetadata(
                identifier=NEGATIVE_DI_IDENTIFIER,
                description="Smoothed negative movement relative to True Range.",
                minimum_observations=DIRECTIONAL_MOVEMENT_PERIOD + 1,
            ),
        ),
        history_type=FeatureHistoryType.RECURSIVE,
        maximum_lookback_observations=None,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.directional_movement.DirectionalIndicators"
        ),
        dependencies=(DIRECTIONAL_MOVEMENT_IDENTIFIER, TRUE_RANGE_IDENTIFIER),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=DIRECTIONAL_MOVEMENT_IDENTIFIER,
                definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
                output_names=(POSITIVE_DM_IDENTIFIER, NEGATIVE_DM_IDENTIFIER),
            ),
            FeatureDependencyMetadata(
                identifier=TRUE_RANGE_IDENTIFIER,
                definition_version=TRUE_RANGE_DEFINITION_VERSION,
                output_names=(TRUE_RANGE_IDENTIFIER,),
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
        positive_dm, negative_dm, true_ranges = _validated_aligned_dependencies(
            validated,
            dependency_inputs,
            (
                (DIRECTIONAL_MOVEMENT_IDENTIFIER, POSITIVE_DM_IDENTIFIER),
                (DIRECTIONAL_MOVEMENT_IDENTIFIER, NEGATIVE_DM_IDENTIFIER),
                (TRUE_RANGE_IDENTIFIER, TRUE_RANGE_IDENTIFIER),
            ),
        )
        smoothed_positive = wilder_smoothed_sum(
            tuple(value.value for value in positive_dm),
            DIRECTIONAL_MOVEMENT_PERIOD,
        )
        smoothed_negative = wilder_smoothed_sum(
            tuple(value.value for value in negative_dm),
            DIRECTIONAL_MOVEMENT_PERIOD,
        )
        smoothed_ranges = wilder_smoothed_sum(
            tuple(value.value for value in true_ranges),
            DIRECTIONAL_MOVEMENT_PERIOD,
        )
        results: list[FeatureValue] = []
        previous_by_output: dict[str, datetime] = {}
        with localcontext() as context:
            context.prec = 50
            for dependency_index in range(
                DIRECTIONAL_MOVEMENT_PERIOD - 1,
                len(true_ranges),
            ):
                range_sum = _required_state(smoothed_ranges[dependency_index])
                positive_sum = _required_state(smoothed_positive[dependency_index])
                negative_sum = _required_state(smoothed_negative[dependency_index])
                positive_di = (
                    Decimal(0)
                    if range_sum == 0
                    else _HUNDRED * positive_sum / range_sum
                )
                negative_di = (
                    Decimal(0)
                    if range_sum == 0
                    else _HUNDRED * negative_sum / range_sum
                )
                timestamp = true_ranges[dependency_index].timestamp
                for output_name, raw_value, movement_values in (
                    (POSITIVE_DI_IDENTIFIER, positive_di, positive_dm),
                    (NEGATIVE_DI_IDENTIFIER, negative_di, negative_dm),
                ):
                    dependencies = _smoothed_dependencies(
                        output_name,
                        timestamp,
                        dependency_index,
                        movement_values,
                        true_ranges,
                        previous_by_output.get(output_name),
                    )
                    results.append(
                        FeatureValue(
                            timestamp=timestamp,
                            feature_name=output_name,
                            value=quantize_feature_value(raw_value),
                            dependencies=dependencies,
                        )
                    )
                    previous_by_output[output_name] = timestamp
        return tuple(results)


@dataclass(frozen=True, slots=True)
class DirectionalIndex:
    metadata = FeatureDefinitionMetadata(
        identifier=DIRECTIONAL_INDEX_IDENTIFIER,
        description="Absolute contemporaneous imbalance between registered DI values.",
        category="trend_strength",
        definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
        required_inputs=(CandleField.HIGH, CandleField.LOW, CandleField.CLOSE),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=DIRECTIONAL_INDEX_IDENTIFIER,
                description="Absolute directional-indicator imbalance scaled by 100.",
                minimum_observations=DIRECTIONAL_MOVEMENT_PERIOD + 1,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=DIRECTIONAL_MOVEMENT_PERIOD + 1,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference="app.features.directional_movement.DirectionalIndex",
        dependencies=(DIRECTIONAL_INDICATORS_IDENTIFIER,),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=DIRECTIONAL_INDICATORS_IDENTIFIER,
                definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
                output_names=(POSITIVE_DI_IDENTIFIER, NEGATIVE_DI_IDENTIFIER),
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
        positive_values, negative_values = _validated_aligned_dependencies(
            validated,
            dependency_inputs,
            (
                (DIRECTIONAL_INDICATORS_IDENTIFIER, POSITIVE_DI_IDENTIFIER),
                (DIRECTIONAL_INDICATORS_IDENTIFIER, NEGATIVE_DI_IDENTIFIER),
            ),
            first_candle_index=DIRECTIONAL_MOVEMENT_PERIOD,
        )
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for positive, negative in zip(
                positive_values,
                negative_values,
                strict=True,
            ):
                denominator = positive.value + negative.value
                value = (
                    Decimal(0)
                    if denominator == 0
                    else _HUNDRED * abs(positive.value - negative.value) / denominator
                )
                results.append(
                    FeatureValue(
                        timestamp=positive.timestamp,
                        feature_name=DIRECTIONAL_INDEX_IDENTIFIER,
                        value=quantize_feature_value(value),
                        dependencies=(
                            _dependency(
                                DIRECTIONAL_INDICATORS_IDENTIFIER,
                                POSITIVE_DI_IDENTIFIER,
                                positive.timestamp,
                            ),
                            _dependency(
                                DIRECTIONAL_INDICATORS_IDENTIFIER,
                                NEGATIVE_DI_IDENTIFIER,
                                negative.timestamp,
                            ),
                        ),
                    )
                )
        return tuple(results)


@dataclass(frozen=True, slots=True)
class AverageDirectionalIndex:
    metadata = FeatureDefinitionMetadata(
        identifier=AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
        description="Wilder-smoothed directional-strength magnitude.",
        category="trend_strength",
        definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
        required_inputs=(CandleField.HIGH, CandleField.LOW, CandleField.CLOSE),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                description="Fourteen-observation Wilder-smoothed DX.",
                minimum_observations=2 * DIRECTIONAL_MOVEMENT_PERIOD,
            ),
        ),
        history_type=FeatureHistoryType.RECURSIVE,
        maximum_lookback_observations=None,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.directional_movement.AverageDirectionalIndex"
        ),
        dependencies=(DIRECTIONAL_INDEX_IDENTIFIER,),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=DIRECTIONAL_INDEX_IDENTIFIER,
                definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
                output_names=(DIRECTIONAL_INDEX_IDENTIFIER,),
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
        (dx_values,) = _validated_aligned_dependencies(
            validated,
            dependency_inputs,
            ((DIRECTIONAL_INDEX_IDENTIFIER, DIRECTIONAL_INDEX_IDENTIFIER),),
            first_candle_index=DIRECTIONAL_MOVEMENT_PERIOD,
        )
        if len(dx_values) < DIRECTIONAL_MOVEMENT_PERIOD:
            return ()

        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            previous = sum(
                (value.value for value in dx_values[:DIRECTIONAL_MOVEMENT_PERIOD]),
                Decimal(0),
            ) / Decimal(DIRECTIONAL_MOVEMENT_PERIOD)
            seed_timestamp = dx_values[DIRECTIONAL_MOVEMENT_PERIOD - 1].timestamp
            results.append(
                FeatureValue(
                    timestamp=seed_timestamp,
                    feature_name=AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                    value=quantize_feature_value(previous),
                    dependencies=tuple(
                        _dependency(
                            DIRECTIONAL_INDEX_IDENTIFIER,
                            DIRECTIONAL_INDEX_IDENTIFIER,
                            value.timestamp,
                        )
                        for value in dx_values[:DIRECTIONAL_MOVEMENT_PERIOD]
                    ),
                )
            )
            for dx_value in dx_values[DIRECTIONAL_MOVEMENT_PERIOD:]:
                previous = (
                    Decimal(DIRECTIONAL_MOVEMENT_PERIOD - 1) * previous + dx_value.value
                ) / Decimal(DIRECTIONAL_MOVEMENT_PERIOD)
                results.append(
                    FeatureValue(
                        timestamp=dx_value.timestamp,
                        feature_name=AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                        value=quantize_feature_value(previous),
                        dependencies=(
                            _dependency(
                                DIRECTIONAL_INDEX_IDENTIFIER,
                                DIRECTIONAL_INDEX_IDENTIFIER,
                                dx_value.timestamp,
                            ),
                            _dependency(
                                AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                                AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                                results[-1].timestamp,
                            ),
                        ),
                    )
                )
        return tuple(results)


@dataclass(frozen=True, slots=True)
class AverageDirectionalMovementRating:
    metadata = FeatureDefinitionMetadata(
        identifier=ADXR_IDENTIFIER,
        description="Mean of current ADX and ADX lagged exactly 14 observations.",
        category="trend_strength",
        definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
        required_inputs=(CandleField.HIGH, CandleField.LOW, CandleField.CLOSE),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=ADXR_IDENTIFIER,
                description="Equal-weighted current and 14-observation-lagged ADX.",
                minimum_observations=3 * DIRECTIONAL_MOVEMENT_PERIOD,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=3 * DIRECTIONAL_MOVEMENT_PERIOD,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.directional_movement.AverageDirectionalMovementRating"
        ),
        dependencies=(AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                definition_version=DIRECTIONAL_MOVEMENT_DEFINITION_VERSION,
                output_names=(AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,),
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
        (adx_values,) = _validated_aligned_dependencies(
            validated,
            dependency_inputs,
            (
                (
                    AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                    AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                ),
            ),
            first_candle_index=2 * DIRECTIONAL_MOVEMENT_PERIOD - 1,
        )
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index in range(DIRECTIONAL_MOVEMENT_PERIOD, len(adx_values)):
                current = adx_values[index]
                lagged = adx_values[index - DIRECTIONAL_MOVEMENT_PERIOD]
                results.append(
                    FeatureValue(
                        timestamp=current.timestamp,
                        feature_name=ADXR_IDENTIFIER,
                        value=quantize_feature_value(
                            (current.value + lagged.value) / Decimal(2)
                        ),
                        dependencies=(
                            _dependency(
                                AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                                AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                                current.timestamp,
                            ),
                            _dependency(
                                AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                                AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                                lagged.timestamp,
                            ),
                        ),
                    )
                )
        return tuple(results)


DIRECTIONAL_MOVEMENT_FEATURE_DEFINITIONS = (
    DirectionalMovement(),
    DirectionalIndicators(),
    DirectionalIndex(),
    AverageDirectionalIndex(),
    AverageDirectionalMovementRating(),
)
DIRECTIONAL_MOVEMENT_FEATURE_METADATA = tuple(
    definition.metadata for definition in DIRECTIONAL_MOVEMENT_FEATURE_DEFINITIONS
)


def _validated_aligned_dependencies(
    candles: tuple[Candle, ...],
    dependency_inputs: tuple[FeatureDependencyInput, ...],
    expected: tuple[tuple[str, str], ...],
    *,
    first_candle_index: int = 1,
) -> tuple[tuple[FeatureValue, ...], ...]:
    if len(dependency_inputs) != len(expected):
        raise FeatureComputationError(
            "Directional Movement dependency count is invalid."
        )
    expected_timestamps = tuple(
        _required_timestamp(candle.timestamp) for candle in candles[first_candle_index:]
    )
    validated: list[tuple[FeatureValue, ...]] = []
    for dependency, (definition_identifier, output_name) in zip(
        dependency_inputs,
        expected,
        strict=True,
    ):
        expected_version = (
            TRUE_RANGE_DEFINITION_VERSION
            if definition_identifier == TRUE_RANGE_IDENTIFIER
            else DIRECTIONAL_MOVEMENT_DEFINITION_VERSION
        )
        if (
            dependency.definition_identifier != definition_identifier
            or dependency.definition_version != expected_version
            or dependency.output_name != output_name
        ):
            raise FeatureComputationError(
                f"Directional Movement requires registered {output_name} 1.0.0."
            )
        if tuple(value.timestamp for value in dependency.values) != expected_timestamps:
            raise FeatureComputationError(
                f"Directional Movement {output_name} coverage is incomplete or unordered."
            )
        for value in dependency.values:
            if (
                value.feature_name != output_name
                or not isinstance(value.value, Decimal)
                or not value.value.is_finite()
                or value.value < 0
                or (
                    output_name
                    in {
                        POSITIVE_DI_IDENTIFIER,
                        NEGATIVE_DI_IDENTIFIER,
                        DIRECTIONAL_INDEX_IDENTIFIER,
                        AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
                    }
                    and value.value > _HUNDRED
                )
                or quantize_feature_value(value.value) != value.value
            ):
                raise FeatureComputationError(
                    f"Directional Movement received invalid {output_name} evidence."
                )
        validated.append(dependency.values)
    return tuple(validated)


def _smoothed_dependencies(
    output_name: str,
    timestamp: datetime,
    dependency_index: int,
    movement_values: tuple[FeatureValue, ...],
    true_ranges: tuple[FeatureValue, ...],
    previous_timestamp: datetime | None,
) -> tuple[FeatureValueDependency, ...]:
    movement_output = (
        POSITIVE_DM_IDENTIFIER
        if output_name == POSITIVE_DI_IDENTIFIER
        else NEGATIVE_DM_IDENTIFIER
    )
    if previous_timestamp is None:
        start = dependency_index - DIRECTIONAL_MOVEMENT_PERIOD + 1
        return tuple(
            _dependency(
                DIRECTIONAL_MOVEMENT_IDENTIFIER, movement_output, value.timestamp
            )
            for value in movement_values[start : dependency_index + 1]
        ) + tuple(
            _dependency(TRUE_RANGE_IDENTIFIER, TRUE_RANGE_IDENTIFIER, value.timestamp)
            for value in true_ranges[start : dependency_index + 1]
        )
    return (
        _dependency(DIRECTIONAL_MOVEMENT_IDENTIFIER, movement_output, timestamp),
        _dependency(TRUE_RANGE_IDENTIFIER, TRUE_RANGE_IDENTIFIER, timestamp),
        _dependency(DIRECTIONAL_INDICATORS_IDENTIFIER, output_name, previous_timestamp),
    )


def _dependency(
    definition_identifier: str,
    output_name: str,
    timestamp: datetime,
) -> FeatureValueDependency:
    version = (
        TRUE_RANGE_DEFINITION_VERSION
        if definition_identifier == TRUE_RANGE_IDENTIFIER
        else DIRECTIONAL_MOVEMENT_DEFINITION_VERSION
    )
    return FeatureValueDependency(
        definition_identifier=definition_identifier,
        definition_version=version,
        output_name=output_name,
        timestamp=timestamp,
    )


def _required_state(value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise FeatureComputationError(
            "Directional Movement smoothing state is unavailable or invalid."
        )
    return value


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError(
            "Directional Movement source timestamp is missing."
        )
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise FeatureComputationError(
            "Directional Movement source input is missing or invalid."
        )
    return value
