"""Deterministic and point-in-time target-generation tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.market_data.models import Candle
from app.targets.forward_log_return import (
    TARGET_DEFINITION_HASH,
    TARGET_HORIZON,
    TARGET_NAME,
    TARGET_VERSION,
    TargetGenerationError,
    generate_forward_log_return_targets,
)


class ForwardLogReturnTargetTests(unittest.TestCase):
    def test_generates_only_complete_five_observation_horizons(self) -> None:
        candles = _candles(10)

        result = generate_forward_log_return_targets(candles)

        self.assertEqual(result.target_name, TARGET_NAME)
        self.assertEqual(result.target_version, TARGET_VERSION)
        self.assertEqual(result.target_definition_hash, TARGET_DEFINITION_HASH)
        self.assertEqual(result.horizon, TARGET_HORIZON)
        self.assertEqual(len(result.labels), 5)
        self.assertEqual(len(result.exclusions), 5)
        self.assertEqual(
            result.labels[0].prediction_timestamp,
            candles[0].timestamp,
        )
        self.assertEqual(
            result.labels[0].label_available_at,
            candles[5].timestamp,
        )
        self.assertEqual(
            result.labels[-1].prediction_timestamp,
            candles[4].timestamp,
        )
        self.assertEqual(
            result.labels[-1].label_available_at,
            candles[9].timestamp,
        )
        self.assertTrue(
            all(
                exclusion.code == "insufficient_forward_horizon"
                for exclusion in result.exclusions
            )
        )
        self.assertTrue(result.point_in_time_validated)

    def test_known_log_return_preserves_decimal_precision(self) -> None:
        candles = _candles(6)

        label = generate_forward_log_return_targets(candles).labels[0]

        self.assertEqual(label.value, Decimal("0.048790164169432003"))

    def test_identical_inputs_produce_identical_labels(self) -> None:
        candles = _candles(20)

        first = generate_forward_log_return_targets(candles)
        second = generate_forward_log_return_targets(candles)

        self.assertEqual(first, second)

    def test_data_after_label_availability_cannot_change_label(self) -> None:
        candles = _candles(12)
        original = generate_forward_log_return_targets(candles).labels[0]
        changed = candles[:-1] + (
            replace(candles[-1], close=Decimal("999")),
        )

        recomputed = generate_forward_log_return_targets(changed).labels[0]

        self.assertEqual(original, recomputed)

    def test_invalid_or_non_chronological_input_is_rejected(self) -> None:
        candles = _candles(10)
        invalid = candles[:3] + (
            replace(candles[3], close=Decimal("0")),
        ) + candles[4:]
        non_chronological = candles[:4] + (
            replace(candles[4], timestamp=candles[3].timestamp),
        ) + candles[5:]

        with self.assertRaises(TargetGenerationError):
            generate_forward_log_return_targets(invalid)
        with self.assertRaises(TargetGenerationError):
            generate_forward_log_return_targets(non_chronological)


def _candles(count: int) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    results: list[Candle] = []
    for index in range(count):
        close = Decimal(100 + index)
        results.append(
            Candle(
                timestamp=start + timedelta(days=index),
                open=close,
                high=close + Decimal(1),
                low=close - Decimal(1),
                close=close,
                volume=Decimal(1000 + index),
            )
        )
    return tuple(results)


if __name__ == "__main__":
    unittest.main()
