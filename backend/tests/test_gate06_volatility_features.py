import math
import unittest
from datetime import datetime, timedelta, timezone

from scripts.gate06_volatility_features import (
    CompletedOHLC,
    WINDOW,
    garman_klass_volatility,
    parkinson_volatility,
    rolling_volatility_features,
)


def candles(count=WINDOW, *, offset=0):
    start = datetime(2026, 7, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * offset)
    return [
        CompletedOHLC(
            timestamp=start + timedelta(minutes=5 * index),
            open=100.0 + index * 0.1,
            high=101.0 + index * 0.1,
            low=99.0 + index * 0.1,
            close=100.5 + index * 0.1,
        )
        for index in range(count)
    ]


class VolatilityFeatureTests(unittest.TestCase):
    def test_parkinson_matches_independent_reference(self):
        window = candles()
        expected = math.sqrt(
            sum(math.log(item.high / item.low) ** 2 for item in window)
            / (4 * WINDOW * math.log(2))
        )
        self.assertAlmostEqual(parkinson_volatility(window), expected, places=15)

    def test_garman_klass_matches_independent_reference(self):
        window = candles()
        expected = math.sqrt(
            max(
                0.0,
                sum(
                    0.5 * math.log(item.high / item.low) ** 2
                    - (2 * math.log(2) - 1) * math.log(item.close / item.open) ** 2
                    for item in window
                )
                / WINDOW,
            )
        )
        self.assertAlmostEqual(garman_klass_volatility(window), expected, places=15)

    def test_rolling_window_ends_at_current_completed_candle(self):
        values = rolling_volatility_features(candles(22))
        self.assertEqual(len(values), 3)
        self.assertEqual(values[0]["timestamp"], candles(22)[19].timestamp)
        self.assertEqual(values[-1]["timestamp"], candles(22)[21].timestamp)

    def test_prefix_invariance_and_no_future_access(self):
        source = candles(25)
        prefix = rolling_volatility_features(source[:21])[-1]
        changed_future = (
            list(source[:21])
            + [CompletedOHLC(source[21].timestamp, 1, 1000, 0.1, 500)]
            + source[22:]
        )
        self.assertEqual(prefix, rolling_volatility_features(changed_future[:21])[-1])

    def test_invalid_and_incomplete_windows_fail_closed(self):
        for field, value in (("open", 0.0), ("high", float("nan")), ("low", -1.0)):
            window = candles()
            window[0] = CompletedOHLC(
                window[0].timestamp,
                value if field == "open" else window[0].open,
                value if field == "high" else window[0].high,
                value if field == "low" else window[0].low,
                window[0].close,
            )
            with self.assertRaises(ValueError):
                parkinson_volatility(window)
        window = candles()
        window[0] = CompletedOHLC(**{**window[0].__dict__, "complete": False})
        with self.assertRaises(ValueError):
            garman_klass_volatility(window)

    def test_window_size_and_order_are_rejected(self):
        with self.assertRaises(ValueError):
            parkinson_volatility(candles(19))
        window = candles()
        window[1], window[2] = window[2], window[1]
        with self.assertRaises(ValueError):
            garman_klass_volatility(window)

    def test_repeated_evaluation_is_deterministic(self):
        self.assertEqual(
            rolling_volatility_features(candles(25)),
            rolling_volatility_features(candles(25)),
        )


if __name__ == "__main__":
    unittest.main()
