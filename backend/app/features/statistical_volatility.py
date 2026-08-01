"""Approved AlphaLens v2 statistical-volatility feature family."""

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
    rolling_arithmetic_mean,
    rolling_population_standard_deviation,
    validated_intraday_candles,
)
from app.market_data.models import Candle, CandleTimeframe


STATISTICAL_PERIOD = 20
STATISTICAL_DEFINITION_VERSION = "1.0.0"
SMA_20_IDENTIFIER = "simple_moving_average_20"
STANDARD_DEVIATION_20_IDENTIFIER = "rolling_standard_deviation_20"
BOLLINGER_IDENTIFIER = "bollinger_bands_20_2"
BOLLINGER_MIDDLE_IDENTIFIER = "bollinger_middle"
BOLLINGER_UPPER_IDENTIFIER = "bollinger_upper"
BOLLINGER_LOWER_IDENTIFIER = "bollinger_lower"
BOLLINGER_WIDTH_IDENTIFIER = "bollinger_band_width"
BOLLINGER_PERCENT_B_IDENTIFIER = "bollinger_percent_b"
BOLLINGER_MULTIPLIER = Decimal(2)
_SUPPORTED_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


@dataclass(frozen=True, slots=True)
class SimpleMovingAverage20:
    metadata = FeatureDefinitionMetadata(
        identifier=SMA_20_IDENTIFIER,
        description=(
            "Equal-weighted arithmetic mean of the latest 20 consecutive "
            "canonical Close observations."
        ),
        category="trend",
        definition_version=STATISTICAL_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=SMA_20_IDENTIFIER,
                description="Current-inclusive 20-observation Close price mean.",
                minimum_observations=STATISTICAL_PERIOD,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=STATISTICAL_PERIOD,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.statistical_volatility.SimpleMovingAverage20"
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
                "SMA-20 does not accept derived feature dependencies."
            )
        validated = validated_intraday_candles(candles, timeframe)
        means = rolling_arithmetic_mean(
            tuple(_required_decimal(candle.close) for candle in validated),
            STATISTICAL_PERIOD,
        )
        return tuple(
            FeatureValue(
                timestamp=_required_timestamp(validated[index].timestamp),
                feature_name=SMA_20_IDENTIFIER,
                value=quantize_feature_value(_required_decimal(means[index])),
            )
            for index in range(STATISTICAL_PERIOD - 1, len(validated))
        )


@dataclass(frozen=True, slots=True)
class RollingStandardDeviation20:
    metadata = FeatureDefinitionMetadata(
        identifier=STANDARD_DEVIATION_20_IDENTIFIER,
        description=(
            "Population standard deviation of the latest 20 consecutive "
            "canonical Close observations around registered SMA-20."
        ),
        category="volatility",
        definition_version=STATISTICAL_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=STANDARD_DEVIATION_20_IDENTIFIER,
                description=(
                    "Current-inclusive 20-observation population Close-price "
                    "standard deviation."
                ),
                minimum_observations=STATISTICAL_PERIOD,
            ),
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=STATISTICAL_PERIOD,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.statistical_volatility.RollingStandardDeviation20"
        ),
        dependencies=(SMA_20_IDENTIFIER,),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=SMA_20_IDENTIFIER,
                definition_version=STATISTICAL_DEFINITION_VERSION,
                output_names=(SMA_20_IDENTIFIER,),
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
        means = _validated_dependency(
            validated,
            dependency_inputs,
            identifier=SMA_20_IDENTIFIER,
        )
        closes = tuple(_required_decimal(candle.close) for candle in validated)
        aligned_means: tuple[Decimal | None, ...] = (None,) * min(
            STATISTICAL_PERIOD - 1,
            len(validated),
        ) + tuple(value.value for value in means)
        deviations = rolling_population_standard_deviation(
            closes,
            aligned_means,
            STATISTICAL_PERIOD,
        )
        return tuple(
            FeatureValue(
                timestamp=value.timestamp,
                feature_name=STANDARD_DEVIATION_20_IDENTIFIER,
                value=quantize_feature_value(_required_decimal(deviations[index])),
                dependencies=(_dependency(SMA_20_IDENTIFIER, value.timestamp),),
            )
            for index, value in enumerate(
                means,
                start=STATISTICAL_PERIOD - 1,
            )
        )


@dataclass(frozen=True, slots=True)
class BollingerBands20:
    metadata = FeatureDefinitionMetadata(
        identifier=BOLLINGER_IDENTIFIER,
        description=(
            "Approved 20-observation, two-population-standard-deviation "
            "Bollinger price envelope and normalized position outputs."
        ),
        category="volatility",
        definition_version=STATISTICAL_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=tuple(
            FeatureOutputMetadata(
                identifier=identifier,
                description=description,
                minimum_observations=STATISTICAL_PERIOD,
            )
            for identifier, description in (
                (
                    BOLLINGER_MIDDLE_IDENTIFIER,
                    "Registered SMA-20 center in quote-price units.",
                ),
                (
                    BOLLINGER_UPPER_IDENTIFIER,
                    "SMA-20 plus two population standard deviations.",
                ),
                (
                    BOLLINGER_LOWER_IDENTIFIER,
                    "SMA-20 minus two population standard deviations.",
                ),
                (
                    BOLLINGER_WIDTH_IDENTIFIER,
                    "Dimensionless upper-minus-lower width divided by middle.",
                ),
                (
                    BOLLINGER_PERCENT_B_IDENTIFIER,
                    "Unclipped current Close position within the Bollinger envelope.",
                ),
            )
        ),
        history_type=FeatureHistoryType.BOUNDED,
        maximum_lookback_observations=STATISTICAL_PERIOD,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.statistical_volatility.BollingerBands20"
        ),
        dependencies=(SMA_20_IDENTIFIER, STANDARD_DEVIATION_20_IDENTIFIER),
        dependency_contracts=(
            FeatureDependencyMetadata(
                identifier=SMA_20_IDENTIFIER,
                definition_version=STATISTICAL_DEFINITION_VERSION,
                output_names=(SMA_20_IDENTIFIER,),
            ),
            FeatureDependencyMetadata(
                identifier=STANDARD_DEVIATION_20_IDENTIFIER,
                definition_version=STATISTICAL_DEFINITION_VERSION,
                output_names=(STANDARD_DEVIATION_20_IDENTIFIER,),
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
        if len(dependency_inputs) != 2:
            raise FeatureComputationError(
                "Bollinger Bands require exactly SMA-20 and standard-deviation-20."
            )
        means = _validated_dependency(
            validated,
            dependency_inputs[:1],
            identifier=SMA_20_IDENTIFIER,
        )
        deviations = _validated_dependency(
            validated,
            dependency_inputs[1:],
            identifier=STANDARD_DEVIATION_20_IDENTIFIER,
        )

        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index, (mean_value, deviation_value) in enumerate(
                zip(means, deviations, strict=True),
                start=STATISTICAL_PERIOD - 1,
            ):
                mean = mean_value.value
                deviation = deviation_value.value
                distance = BOLLINGER_MULTIPLIER * deviation
                upper = mean + distance
                lower = mean - distance
                span = upper - lower
                if mean <= 0:
                    raise FeatureComputationError("Bollinger middle must be positive.")
                width = span / mean
                close = _required_decimal(validated[index].close)
                percent_b = Decimal("0.5") if span == 0 else (close - lower) / span
                dependencies = (
                    _dependency(SMA_20_IDENTIFIER, mean_value.timestamp),
                    _dependency(
                        STANDARD_DEVIATION_20_IDENTIFIER,
                        deviation_value.timestamp,
                    ),
                )
                results.extend(
                    FeatureValue(
                        timestamp=mean_value.timestamp,
                        feature_name=identifier,
                        value=quantize_feature_value(value),
                        dependencies=dependencies,
                    )
                    for identifier, value in (
                        (BOLLINGER_MIDDLE_IDENTIFIER, mean),
                        (BOLLINGER_UPPER_IDENTIFIER, upper),
                        (BOLLINGER_LOWER_IDENTIFIER, lower),
                        (BOLLINGER_WIDTH_IDENTIFIER, width),
                        (BOLLINGER_PERCENT_B_IDENTIFIER, percent_b),
                    )
                )
        return tuple(results)


STATISTICAL_VOLATILITY_FEATURE_DEFINITIONS = (
    SimpleMovingAverage20(),
    RollingStandardDeviation20(),
    BollingerBands20(),
)
STATISTICAL_VOLATILITY_FEATURE_METADATA = tuple(
    definition.metadata for definition in STATISTICAL_VOLATILITY_FEATURE_DEFINITIONS
)


def _validated_dependency(
    candles: tuple[Candle, ...],
    dependency_inputs: tuple[FeatureDependencyInput, ...],
    *,
    identifier: str,
) -> tuple[FeatureValue, ...]:
    if len(dependency_inputs) != 1:
        raise FeatureComputationError(
            f"Statistical feature requires exactly one {identifier} dependency."
        )
    dependency = dependency_inputs[0]
    if (
        dependency.definition_identifier != identifier
        or dependency.definition_version != STATISTICAL_DEFINITION_VERSION
        or dependency.output_name != identifier
    ):
        raise FeatureComputationError(
            f"Statistical feature requires registered {identifier} 1.0.0."
        )
    expected_timestamps = tuple(
        _required_timestamp(candle.timestamp)
        for candle in candles[STATISTICAL_PERIOD - 1 :]
    )
    if tuple(value.timestamp for value in dependency.values) != expected_timestamps:
        raise FeatureComputationError(
            f"Statistical feature {identifier} coverage is incomplete or unordered."
        )
    for value in dependency.values:
        if value.feature_name != identifier:
            raise FeatureComputationError(
                f"Statistical feature received unexpected {identifier} output."
            )
        if not isinstance(value.value, Decimal) or not value.value.is_finite():
            raise FeatureComputationError(
                f"Statistical feature received invalid {identifier} Decimal."
            )
        if quantize_feature_value(value.value) != value.value:
            raise FeatureComputationError(
                f"Statistical feature received unquantized {identifier} value."
            )
    return dependency.values


def _dependency(identifier: str, timestamp: datetime) -> FeatureValueDependency:
    return FeatureValueDependency(
        definition_identifier=identifier,
        definition_version=STATISTICAL_DEFINITION_VERSION,
        output_name=identifier,
        timestamp=timestamp,
    )


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("Statistical feature timestamp is missing.")
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal):
        raise FeatureComputationError(
            "Statistical feature input is missing or non-Decimal."
        )
    return value
