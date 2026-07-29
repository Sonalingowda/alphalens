"""Momentum feature definitions."""

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
class RelativeStrengthIndex:
    period: int = 14

    @property
    def feature_names(self) -> tuple[str, ...]:
        return (f"rsi_{self.period}",)

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        points = validated_candle_points(candles)
        if self.period <= 0:
            raise ValueError("RSI period must be positive.")
        if len(points) <= self.period:
            return ()

        with localcontext() as context:
            context.prec = 50
            changes = tuple(
                points[index].close - points[index - 1].close
                for index in range(1, len(points))
            )
            gains = tuple(max(change, Decimal(0)) for change in changes)
            losses = tuple(max(-change, Decimal(0)) for change in changes)
            average_gain = sum(gains[: self.period], Decimal(0)) / Decimal(
                self.period
            )
            average_loss = sum(losses[: self.period], Decimal(0)) / Decimal(
                self.period
            )
            results = [
                FeatureValue(
                    timestamp=points[self.period].timestamp,
                    feature_name=self.feature_names[0],
                    value=quantize_feature_value(
                        _relative_strength_index(average_gain, average_loss)
                    ),
                )
            ]

            for point_index in range(self.period + 1, len(points)):
                change_index = point_index - 1
                average_gain = (
                    average_gain * Decimal(self.period - 1)
                    + gains[change_index]
                ) / Decimal(self.period)
                average_loss = (
                    average_loss * Decimal(self.period - 1)
                    + losses[change_index]
                ) / Decimal(self.period)
                results.append(
                    FeatureValue(
                        timestamp=points[point_index].timestamp,
                        feature_name=self.feature_names[0],
                        value=quantize_feature_value(
                            _relative_strength_index(
                                average_gain,
                                average_loss,
                            )
                        ),
                    )
                )

        return tuple(results)


@dataclass(frozen=True, slots=True)
class MovingAverageConvergenceDivergence:
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9

    @property
    def feature_names(self) -> tuple[str, ...]:
        prefix = (
            f"macd_{self.fast_period}_{self.slow_period}_{self.signal_period}"
        )
        return (
            f"{prefix}_line",
            f"{prefix}_signal",
            f"{prefix}_histogram",
        )

    def compute(self, candles: tuple[Candle, ...]) -> tuple[FeatureValue, ...]:
        points = validated_candle_points(candles)
        if not 0 < self.fast_period < self.slow_period:
            raise ValueError("MACD periods require 0 < fast < slow.")
        if self.signal_period <= 0:
            raise ValueError("MACD signal period must be positive.")

        closes = tuple(point.close for point in points)
        fast = exponential_moving_average(closes, self.fast_period)
        slow = exponential_moving_average(closes, self.slow_period)
        line_indexes = [
            index
            for index in range(len(points))
            if fast[index] is not None and slow[index] is not None
        ]
        line_values = tuple(
            _required_decimal(fast[index]) - _required_decimal(slow[index])
            for index in line_indexes
        )
        signals = exponential_moving_average(line_values, self.signal_period)

        results: list[FeatureValue] = []
        for compact_index, point_index in enumerate(line_indexes):
            line = line_values[compact_index]
            results.append(
                FeatureValue(
                    timestamp=points[point_index].timestamp,
                    feature_name=self.feature_names[0],
                    value=quantize_feature_value(line),
                )
            )
            signal = signals[compact_index]
            if signal is not None:
                results.extend(
                    (
                        FeatureValue(
                            timestamp=points[point_index].timestamp,
                            feature_name=self.feature_names[1],
                            value=quantize_feature_value(signal),
                        ),
                        FeatureValue(
                            timestamp=points[point_index].timestamp,
                            feature_name=self.feature_names[2],
                            value=quantize_feature_value(line - signal),
                        ),
                    )
                )
        return tuple(results)


def _relative_strength_index(
    average_gain: Decimal,
    average_loss: Decimal,
) -> Decimal:
    if average_loss == 0:
        return Decimal(50) if average_gain == 0 else Decimal(100)
    relative_strength = average_gain / average_loss
    return Decimal(100) - Decimal(100) / (Decimal(1) + relative_strength)


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise ValueError("Expected MACD moving average is missing.")
    return value
