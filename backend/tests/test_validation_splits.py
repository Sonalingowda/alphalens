"""Chronological validation split and holdout safeguards."""

from datetime import datetime, timedelta, timezone
import unittest

from app.validation.splits import (
    ValidationConfigurationError,
    WalkForwardConfig,
    access_final_holdout,
    generate_development_splits,
    verify_lookback_separation,
)


class WalkForwardValidationTests(unittest.TestCase):
    def test_default_plan_is_expanding_and_excludes_holdout(self) -> None:
        timestamps = _timestamps(90)

        plan = generate_development_splits(
            timestamps,
            WalkForwardConfig(),
        )

        self.assertEqual(plan.strategy, "expanding_walk_forward")
        self.assertEqual(len(plan.splits), 2)
        self.assertEqual(plan.splits[0].train.start, timestamps[0])
        self.assertEqual(plan.splits[0].train.end, timestamps[19])
        self.assertEqual(plan.splits[0].purge_gap.start, timestamps[20])
        self.assertEqual(plan.splits[0].purge_gap.end, timestamps[69])
        self.assertEqual(plan.splits[0].test.start, timestamps[70])
        self.assertEqual(plan.splits[0].test.end, timestamps[74])
        self.assertEqual(plan.splits[-1].train.end, timestamps[24])
        self.assertEqual(plan.splits[-1].test.start, timestamps[75])
        self.assertEqual(plan.splits[-1].test.end, timestamps[79])
        self.assertEqual(plan.final_holdout_range.start, timestamps[80])
        self.assertEqual(plan.final_holdout_range.end, timestamps[89])
        self.assertLess(
            plan.splits[-1].test.end,
            plan.final_holdout_range.start,
        )

    def test_maximum_feature_lookback_is_separated_from_training(self) -> None:
        timestamps = _timestamps(90)
        plan = generate_development_splits(
            timestamps,
            WalkForwardConfig(),
        )

        checks = verify_lookback_separation(
            timestamps,
            plan,
            max_feature_window=50,
        )

        self.assertTrue(all(check.passed for check in checks))
        self.assertEqual(
            checks[0].earliest_first_test_feature_input,
            timestamps[21],
        )
        self.assertLess(
            checks[0].train_end,
            checks[0].earliest_first_test_feature_input,
        )

    def test_final_holdout_requires_explicit_acknowledgement(self) -> None:
        timestamps = _timestamps(90)
        config = WalkForwardConfig()

        with self.assertRaises(PermissionError):
            access_final_holdout(timestamps, config)

        holdout = access_final_holdout(
            timestamps,
            config,
            acknowledge_final_evaluation=True,
        )
        self.assertEqual(holdout, timestamps[-10:])

    def test_identical_inputs_produce_identical_plans(self) -> None:
        timestamps = _timestamps(90)
        config = WalkForwardConfig()

        self.assertEqual(
            generate_development_splits(timestamps, config),
            generate_development_splits(timestamps, config),
        )

    def test_overlapping_test_windows_are_rejected(self) -> None:
        with self.assertRaises(ValidationConfigurationError):
            generate_development_splits(
                _timestamps(90),
                WalkForwardConfig(test_size=5, step_size=4),
            )

    def test_insufficient_purge_for_feature_window_is_rejected(self) -> None:
        timestamps = _timestamps(90)
        plan = generate_development_splits(
            timestamps,
            WalkForwardConfig(purge_gap_size=49),
        )

        with self.assertRaises(ValidationConfigurationError):
            verify_lookback_separation(
                timestamps,
                plan,
                max_feature_window=50,
            )

    def test_non_chronological_timestamps_are_rejected(self) -> None:
        timestamps = _timestamps(90)
        malformed = timestamps[:10] + (timestamps[9],) + timestamps[11:]

        with self.assertRaises(ValidationConfigurationError):
            generate_development_splits(
                malformed,
                WalkForwardConfig(),
            )


def _timestamps(count: int) -> tuple[datetime, ...]:
    start = datetime(2026, 4, 29, tzinfo=timezone.utc)
    return tuple(start + timedelta(days=index) for index in range(count))


if __name__ == "__main__":
    unittest.main()
