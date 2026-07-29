"""Volatility feature definitions."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.features.contracts import (
    FeatureValue,
    quantize_feature_value,
    validated_candle_points,
)
from app.market_data.models import Candle


@dataclass(frozen=True, slots=True)
class BollingerBands:
    period: int = 20
    standard_deviations: int = 2

    @property
    def feature_names(self) -> tuple[str, ...]:
        prefix = f"bollinger_{self.period}_{self.standard_deviations}"
        return (
            f"{prefix}_middle",
            f"{prefix}_upper",
            f"{prefix}_lower",
        )

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        points = validated_candle_points(candles)
        if self.period <= 0 or self.standard_deviations <= 0:
            raise ValueError("Bollinger Band parameters must be positive.")

        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index in range(self.period - 1, len(points)):
                window = points[index - self.period + 1 : index + 1]
                middle = sum(
                    (point.close for point in window),
                    Decimal(0),
                ) / Decimal(self.period)
                variance = sum(
                    (
                        (point.close - middle) * (point.close - middle)
                        for point in window
                    ),
                    Decimal(0),
                ) / Decimal(self.period)
                distance = variance.sqrt() * Decimal(self.standard_deviations)
                timestamp = points[index].timestamp
                results.extend(
                    (
                        FeatureValue(
                            timestamp=timestamp,
                            feature_name=self.feature_names[0],
                            value=quantize_feature_value(middle),
                        ),
                        FeatureValue(
                            timestamp=timestamp,
                            feature_name=self.feature_names[1],
                            value=quantize_feature_value(middle + distance),
                        ),
                        FeatureValue(
                            timestamp=timestamp,
                            feature_name=self.feature_names[2],
                            value=quantize_feature_value(middle - distance),
                        ),
                    )
                )
        return tuple(results)
