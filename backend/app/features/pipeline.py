"""Initial deterministic feature pipeline and causality validation."""

from dataclasses import dataclass
from datetime import datetime

from app.features.contracts import (
    FeatureComputationError,
    FeatureDefinition,
    FeatureValue,
    validated_candle_points,
)
from app.features.momentum import (
    MovingAverageConvergenceDivergence,
    RelativeStrengthIndex,
)
from app.features.moving_averages import (
    ExponentialMovingAverage,
    SimpleMovingAverage,
)
from app.features.volatility import BollingerBands
from app.features.volume import VolumeSimpleMovingAverage
from app.market_data.models import Candle


PIPELINE_VERSION = "1.1.0"

INITIAL_FEATURES: tuple[FeatureDefinition, ...] = (
    SimpleMovingAverage(period=20),
    SimpleMovingAverage(period=50),
    ExponentialMovingAverage(period=20),
    ExponentialMovingAverage(period=50),
    RelativeStrengthIndex(period=14),
    MovingAverageConvergenceDivergence(
        fast_period=12,
        slow_period=26,
        signal_period=9,
    ),
    BollingerBands(period=20, standard_deviations=2),
    VolumeSimpleMovingAverage(period=20),
)


@dataclass(frozen=True, slots=True)
class FeaturePipelineResult:
    pipeline_version: str
    values: tuple[FeatureValue, ...]
    point_in_time_validated: bool


def run_feature_pipeline(
    candles: tuple[Candle, ...],
) -> FeaturePipelineResult:
    points = validated_candle_points(candles)
    if not points:
        raise FeatureComputationError("Feature pipeline requires candle input.")

    all_values: list[FeatureValue] = []
    for feature in INITIAL_FEATURES:
        values = feature.compute(candles)
        _validate_feature_outputs(feature, values, candles)
        _verify_prefix_invariance(feature, values, candles)
        all_values.extend(values)

    all_values.sort(key=lambda value: (value.timestamp, value.feature_name))
    return FeaturePipelineResult(
        pipeline_version=PIPELINE_VERSION,
        values=tuple(all_values),
        point_in_time_validated=True,
    )


def _validate_feature_outputs(
    feature: FeatureDefinition,
    values: tuple[FeatureValue, ...],
    candles: tuple[Candle, ...],
) -> None:
    input_timestamps = {candle.timestamp for candle in candles}
    seen: set[tuple[datetime, str]] = set()
    previous_by_name: dict[str, datetime] = {}

    for value in values:
        if value.feature_name not in feature.feature_names:
            raise FeatureComputationError(
                f"Unexpected output name {value.feature_name}."
            )
        if value.timestamp not in input_timestamps:
            raise FeatureComputationError(
                f"Feature {value.feature_name} emitted a non-source timestamp."
            )
        key = (value.timestamp, value.feature_name)
        if key in seen:
            raise FeatureComputationError(
                f"Feature {value.feature_name} emitted a duplicate timestamp."
            )
        previous = previous_by_name.get(value.feature_name)
        if previous is not None and value.timestamp <= previous:
            raise FeatureComputationError(
                f"Feature {value.feature_name} output is not chronological."
            )
        if not value.value.is_finite():
            raise FeatureComputationError(
                f"Feature {value.feature_name} emitted a non-finite value."
            )
        seen.add(key)
        previous_by_name[value.feature_name] = value.timestamp


def _verify_prefix_invariance(
    feature: FeatureDefinition,
    full_values: tuple[FeatureValue, ...],
    candles: tuple[Candle, ...],
) -> None:
    """Prove each historical output is unchanged when future candles are absent."""
    for prefix_length in range(1, len(candles) + 1):
        prefix = candles[:prefix_length]
        prefix_values = feature.compute(prefix)
        last_timestamp = prefix[-1].timestamp
        expected = tuple(
            value
            for value in full_values
            if last_timestamp is not None and value.timestamp <= last_timestamp
        )
        if prefix_values != expected:
            raise FeatureComputationError(
                f"Feature {feature.feature_names} failed point-in-time "
                f"prefix invariance at input position {prefix_length}."
            )
