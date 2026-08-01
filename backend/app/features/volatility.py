"""Volatility feature definitions."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.features.contracts import (
    FeatureValue,
    quantize_feature_value,
    rolling_arithmetic_mean,
    rolling_population_standard_deviation,
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

        closes = tuple(point.close for point in points)
        means = rolling_arithmetic_mean(closes, self.period)
        deviations = rolling_population_standard_deviation(
            closes,
            means,
            self.period,
        )
        results: list[FeatureValue] = []
        with localcontext() as context:
            context.prec = 50
            for index in range(self.period - 1, len(points)):
                middle = _required_decimal(means[index])
                deviation = _required_decimal(deviations[index])
                distance = deviation * Decimal(self.standard_deviations)
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


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise ValueError("Expected rolling statistical value is missing.")
    return value
