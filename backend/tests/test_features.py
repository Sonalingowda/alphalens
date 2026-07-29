"""Focused deterministic and point-in-time feature tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.features.contracts import FeatureComputationError, FeatureValue
from app.features.moving_averages import (
    ExponentialMovingAverage,
    SimpleMovingAverage,
)
from app.features.pipeline import run_feature_pipeline
from app.market_data.models import Candle


class FeaturePipelineTests(unittest.TestCase):
    def test_full_pipeline_uses_complete_warmup_windows(self) -> None:
        candles = _candles(90)

        result = run_feature_pipeline(candles)
        by_name = _by_name(result.values)

        self.assertTrue(result.point_in_time_validated)
        self.assertEqual(len(result.values), 763)
        self.assertEqual(by_name["sma_20"][0].timestamp, candles[19].timestamp)
        self.assertEqual(by_name["ema_20"][0].timestamp, candles[19].timestamp)
        self.assertEqual(by_name["sma_50"][0].timestamp, candles[49].timestamp)
        self.assertEqual(by_name["ema_50"][0].timestamp, candles[49].timestamp)
        self.assertEqual(by_name["rsi_14"][0].timestamp, candles[14].timestamp)
        self.assertEqual(
            by_name["macd_12_26_9_line"][0].timestamp,
            candles[25].timestamp,
        )
        self.assertEqual(
            by_name["macd_12_26_9_signal"][0].timestamp,
            candles[33].timestamp,
        )
        self.assertEqual(
            by_name["bollinger_20_2_middle"][0].timestamp,
            candles[19].timestamp,
        )
        self.assertEqual(
            by_name["volume_sma_20"][0].timestamp,
            candles[19].timestamp,
        )

    def test_future_change_does_not_change_past_values(self) -> None:
        candles = _candles(60)
        original = run_feature_pipeline(candles).values
        final = candles[-1]
        changed = replace(
            final,
            open=Decimal("1000"),
            high=Decimal("1100"),
            low=Decimal("900"),
            close=Decimal("1050"),
            volume=Decimal("9999"),
        )

        recomputed = run_feature_pipeline(candles[:-1] + (changed,)).values
        previous_timestamp = candles[-2].timestamp
        self.assertEqual(
            tuple(
                value
                for value in original
                if value.timestamp <= previous_timestamp
            ),
            tuple(
                value
                for value in recomputed
                if value.timestamp <= previous_timestamp
            ),
        )

    def test_identical_inputs_produce_identical_outputs(self) -> None:
        candles = _candles(60)

        first = run_feature_pipeline(candles)
        second = run_feature_pipeline(candles)

        self.assertEqual(first, second)

    def test_known_sma_and_ema_seed(self) -> None:
        candles = _candles(4)

        sma = SimpleMovingAverage(period=3).compute(candles)
        ema = ExponentialMovingAverage(period=3).compute(candles)

        self.assertEqual(sma[0].value, Decimal("2.000000000000000000"))
        self.assertEqual(ema[0].value, Decimal("2.000000000000000000"))
        self.assertEqual(sma[0].timestamp, candles[2].timestamp)
        self.assertEqual(ema[0].timestamp, candles[2].timestamp)

    def test_malformed_input_prevents_computation(self) -> None:
        candles = _candles(20)
        malformed = candles[:5] + (
            replace(candles[5], close=None),
        ) + candles[6:]

        with self.assertRaises(FeatureComputationError):
            run_feature_pipeline(malformed)


def _candles(count: int) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    results: list[Candle] = []
    for index in range(count):
        close = Decimal(index + 1)
        results.append(
            Candle(
                timestamp=start + timedelta(days=index),
                open=close,
                high=close + Decimal(1),
                low=max(close - Decimal(1), Decimal("0.5")),
                close=close,
                volume=Decimal(100 + index),
            )
        )
    return tuple(results)


def _by_name(
    values: tuple[FeatureValue, ...],
) -> dict[str, list[FeatureValue]]:
    grouped: dict[str, list[FeatureValue]] = {}
    for value in values:
        grouped.setdefault(value.feature_name, []).append(value)
    return grouped


if __name__ == "__main__":
    unittest.main()
