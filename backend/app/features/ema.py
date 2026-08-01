"""Approved AlphaLens v2 EMA feature-family definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.features.contracts import (
    CandleField,
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureDefinitionMetadata,
    FeatureDependencyInput,
    FeatureHistoryType,
    FeatureMetadataError,
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
EMA_12_IDENTIFIER = "exponential_moving_average_12"
EMA_26_IDENTIFIER = "exponential_moving_average_26"
EMA_50_IDENTIFIER = "exponential_moving_average_50"
EMA_100_IDENTIFIER = "exponential_moving_average_100"
EMA_200_IDENTIFIER = "exponential_moving_average_200"
EMA_FAMILY_IDENTITIES = (
    (12, EMA_12_IDENTIFIER, "EMA-12"),
    (20, EMA_IDENTIFIER, "EMA-20"),
    (26, EMA_26_IDENTIFIER, "EMA-26"),
    (50, EMA_50_IDENTIFIER, "EMA-50"),
    (100, EMA_100_IDENTIFIER, "EMA-100"),
    (200, EMA_200_IDENTIFIER, "EMA-200"),
)
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
        return _compute_ema_family_member(
            candles,
            timeframe,
            dependency_inputs,
            period=EMA_PERIOD,
            identifier=EMA_IDENTIFIER,
            catalog_identifier="EMA-20",
        )


@dataclass(frozen=True, slots=True)
class ExponentialMovingAverageFamilyMember:
    period: int
    identifier: str
    catalog_identifier: str
    metadata: FeatureDefinitionMetadata = field(init=False)

    def __post_init__(self) -> None:
        if (
            self.period == EMA_PERIOD
            or (
                self.period,
                self.identifier,
                self.catalog_identifier,
            )
            not in EMA_FAMILY_IDENTITIES
        ):
            raise FeatureMetadataError(
                "EMA family member must use an approved non-EMA-20 identity."
            )
        object.__setattr__(
            self,
            "metadata",
            _family_member_metadata(
                self.period,
                self.identifier,
                self.catalog_identifier,
            ),
        )

    def compute(
        self,
        candles: tuple[Candle, ...],
        timeframe: CandleTimeframe,
        dependency_inputs: tuple[FeatureDependencyInput, ...] = (),
    ) -> tuple[FeatureValue, ...]:
        return _compute_ema_family_member(
            candles,
            timeframe,
            dependency_inputs,
            period=self.period,
            identifier=self.identifier,
            catalog_identifier=self.catalog_identifier,
        )


def _family_member_metadata(
    period: int,
    identifier: str,
    catalog_identifier: str,
) -> FeatureDefinitionMetadata:
    return FeatureDefinitionMetadata(
        identifier=identifier,
        description=(
            f"Approved {catalog_identifier} smoothed canonical Close price "
            "baseline for a completed candle."
        ),
        category="trend",
        definition_version=EMA_DEFINITION_VERSION,
        required_inputs=(CandleField.CLOSE,),
        supported_timeframes=_SUPPORTED_TIMEFRAMES,
        outputs=(
            FeatureOutputMetadata(
                identifier=identifier,
                description=(
                    f"Price-level output defined by the approved {catalog_identifier} "
                    "feature-family quantitative specification."
                ),
                minimum_observations=period,
            ),
        ),
        history_type=FeatureHistoryType.RECURSIVE,
        maximum_lookback_observations=None,
        requires_continuity=True,
        availability_rule=FeatureAvailabilityRule.CANDLE_CLOSE,
        implementation_reference=(
            "app.features.ema.ExponentialMovingAverageFamilyMember"
        ),
    )


def _compute_ema_family_member(
    candles: tuple[Candle, ...],
    timeframe: CandleTimeframe,
    dependency_inputs: tuple[FeatureDependencyInput, ...],
    *,
    period: int,
    identifier: str,
    catalog_identifier: str,
) -> tuple[FeatureValue, ...]:
    if dependency_inputs:
        raise FeatureComputationError(
            f"{catalog_identifier} does not accept derived feature dependencies."
        )
    validated = validated_intraday_candles(candles, timeframe)
    closes = tuple(_required_decimal(candle.close) for candle in validated)
    raw_values = exponential_moving_average(closes, period)
    results: list[FeatureValue] = []

    for index in range(period - 1, len(validated)):
        raw_value = raw_values[index]
        if raw_value is None:
            raise FeatureComputationError(
                f"{catalog_identifier} recursive state is unexpectedly unavailable."
            )
        timestamp = _required_timestamp(validated[index].timestamp)
        dependencies = ()
        if results:
            dependencies = (
                FeatureValueDependency(
                    definition_identifier=identifier,
                    definition_version=EMA_DEFINITION_VERSION,
                    output_name=identifier,
                    timestamp=results[-1].timestamp,
                ),
            )
        results.append(
            FeatureValue(
                timestamp=timestamp,
                feature_name=identifier,
                value=quantize_feature_value(raw_value),
                dependencies=dependencies,
            )
        )

    return tuple(results)


EMA_FEATURE_DEFINITIONS = (
    ExponentialMovingAverageFamilyMember(12, EMA_12_IDENTIFIER, "EMA-12"),
    ExponentialMovingAverage(),
    ExponentialMovingAverageFamilyMember(26, EMA_26_IDENTIFIER, "EMA-26"),
    ExponentialMovingAverageFamilyMember(50, EMA_50_IDENTIFIER, "EMA-50"),
    ExponentialMovingAverageFamilyMember(100, EMA_100_IDENTIFIER, "EMA-100"),
    ExponentialMovingAverageFamilyMember(200, EMA_200_IDENTIFIER, "EMA-200"),
)
EMA_FEATURE_METADATA = tuple(
    definition.metadata for definition in EMA_FEATURE_DEFINITIONS
)


def _required_timestamp(value: datetime | None) -> datetime:
    if value is None:
        raise FeatureComputationError("EMA source timestamp is missing.")
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if not isinstance(value, Decimal):
        raise FeatureComputationError("EMA Close input is missing or non-Decimal.")
    return value
