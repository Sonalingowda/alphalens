"""Price moving-average feature definitions."""

from dataclasses import dataclass

from app.features.contracts import (
    FeatureValue,
    exponential_moving_average,
    quantize_feature_value,
    rolling_arithmetic_mean,
    validated_candle_points,
)
from app.market_data.models import Candle


@dataclass(frozen=True, slots=True)
class SimpleMovingAverage:
    period: int

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (f"sma_{self.period}",)

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        points = validated_candle_points(candles)
        if self.period <= 0:
            raise ValueError("SMA period must be positive.")

        averages = rolling_arithmetic_mean(
            tuple(point.close for point in points),
            self.period,
        )
        return tuple(
            FeatureValue(
                timestamp=points[index].timestamp,
                feature_name=self.feature_names[0],
                value=quantize_feature_value(value),
            )
            for index, value in enumerate(averages)
            if value is not None
        )


@dataclass(frozen=True, slots=True)
class ExponentialMovingAverage:
    period: int

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (f"ema_{self.period}",)

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        points = validated_candle_points(candles)
        averages = exponential_moving_average(
            tuple(point.close for point in points),
            self.period,
        )
        return tuple(
            FeatureValue(
                timestamp=points[index].timestamp,
                feature_name=self.feature_names[0],
                value=quantize_feature_value(value),
            )
            for index, value in enumerate(averages)
            if value is not None
        )
