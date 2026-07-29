"""Price moving-average feature definitions."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.features.contracts import (
    FeatureValue,
    exponential_moving_average,
    quantize_feature_value,
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

        results: list[FeatureValue] = []
        rolling_sum = Decimal(0)
        with localcontext() as context:
            context.prec = 50
            for index, point in enumerate(points):
                rolling_sum += point.close
                if index >= self.period:
                    rolling_sum -= points[index - self.period].close
                if index >= self.period - 1:
                    results.append(
                        FeatureValue(
                            timestamp=point.timestamp,
                            feature_name=self.feature_names[0],
                            value=quantize_feature_value(
                                rolling_sum / Decimal(self.period)
                            ),
                        )
                    )
        return tuple(results)


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
