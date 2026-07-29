"""Volume feature definitions."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.features.contracts import (
    FeatureValue,
    quantize_feature_value,
    validated_candle_points,
)
from app.market_data.models import Candle


@dataclass(frozen=True, slots=True)
class VolumeSimpleMovingAverage:
    period: int = 20

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (f"volume_sma_{self.period}",)

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        points = validated_candle_points(candles)
        if self.period <= 0:
            raise ValueError("Volume SMA period must be positive.")

        results: list[FeatureValue] = []
        rolling_sum = Decimal(0)
        with localcontext() as context:
            context.prec = 50
            for index, point in enumerate(points):
                rolling_sum += point.volume
                if index >= self.period:
                    rolling_sum -= points[index - self.period].volume
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
