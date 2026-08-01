"""In-memory intraday feature pipeline integrity tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.features.contracts import FeatureComputationError
from app.features.intraday_pipeline import (
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import Candle, CandleTimeframe


_BATCH_A = UUID("00000000-0000-0000-0000-000000000001")
_BATCH_B = UUID("00000000-0000-0000-0000-000000000002")


class IntradaySourceSnapshotTests(unittest.TestCase):
    def test_snapshot_is_deterministic_and_retains_all_source_batches(
        self,
    ) -> None:
        observations = _observations(4, CandleTimeframe.MINUTE_5)

        first = _snapshot(observations, CandleTimeframe.MINUTE_5)
        second = _snapshot(observations, CandleTimeframe.MINUTE_5)

        self.assertEqual(first, second)
        self.assertEqual(len(first.data_hash), 64)
        self.assertEqual(len(first.provenance_hash), 64)
        self.assertEqual(
            first.source_ingestion_batch_ids,
            (_BATCH_A, _BATCH_B),
        )
        self.assertEqual(first.range_start, observations[0].candle.timestamp)
        self.assertEqual(first.range_end, observations[-1].candle.timestamp)
        self.assertEqual(first.candles, tuple(item.candle for item in observations))

    def test_data_and_provenance_hashes_have_distinct_semantics(self) -> None:
        observations = _observations(3, CandleTimeframe.MINUTE_5)
        reassigned = tuple(
            replace(observation, ingestion_batch_id=_BATCH_A)
            for observation in observations
        )

        original = _snapshot(observations, CandleTimeframe.MINUTE_5)
        changed_provenance = _snapshot(
            reassigned,
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(original.data_hash, changed_provenance.data_hash)
        self.assertNotEqual(
            original.provenance_hash,
            changed_provenance.provenance_hash,
        )

    def test_incomplete_candle_is_rejected(self) -> None:
        observations = _observations(2, CandleTimeframe.MINUTE_5)
        incomplete = observations[:1] + (replace(observations[1], is_complete=False),)

        with self.assertRaisesRegex(
            FeatureComputationError,
            "Incomplete candles",
        ):
            _snapshot(incomplete, CandleTimeframe.MINUTE_5)

    def test_invalid_or_discontinuous_source_fails_closed(self) -> None:
        observations = _observations(3, CandleTimeframe.MINUTE_5)
        invalid_cases = (
            observations[:1]
            + (
                replace(
                    observations[1],
                    candle=replace(observations[1].candle, close=None),
                ),
            )
            + observations[2:],
            observations[:1]
            + (
                replace(
                    observations[1],
                    candle=replace(
                        observations[1].candle,
                        timestamp=observations[1].candle.timestamp
                        + timedelta(minutes=5),
                    ),
                ),
            )
            + observations[2:],
            observations[:1]
            + (
                replace(
                    observations[1],
                    candle=replace(
                        observations[1].candle,
                        volume=Decimal("-1"),
                    ),
                ),
            )
            + observations[2:],
            observations[:1]
            + (
                replace(
                    observations[1],
                    candle=replace(
                        observations[1].candle,
                        high=Decimal("90"),
                        low=Decimal("110"),
                    ),
                ),
            )
            + observations[2:],
        )

        for invalid in invalid_cases:
            with self.subTest(invalid=invalid):
                with self.assertRaises(FeatureComputationError):
                    _snapshot(invalid, CandleTimeframe.MINUTE_5)

    def test_empty_or_out_of_scope_snapshot_is_rejected(self) -> None:
        with self.assertRaises(FeatureComputationError):
            _snapshot((), CandleTimeframe.MINUTE_5)

        with self.assertRaises(FeatureComputationError):
            _snapshot(
                _observations(2, CandleTimeframe.DAY_1),
                CandleTimeframe.DAY_1,
            )

        with self.assertRaises(FeatureComputationError):
            build_intraday_source_snapshot(
                asset_identifier="ETH",
                quote_currency="USD",
                timeframe=CandleTimeframe.MINUTE_5,
                observations=_observations(
                    2,
                    CandleTimeframe.MINUTE_5,
                ),
            )


class IntradayFeaturePipelineTests(unittest.TestCase):
    def test_pipeline_executes_only_approved_registry_order(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(
                _observations(4, CandleTimeframe.MINUTE_5),
                CandleTimeframe.MINUTE_5,
            )
        )

        self.assertEqual(
            result.execution_order,
            (
                "candle_geometry",
                "true_range",
                "average_true_range",
                "exponential_moving_average_12",
                "exponential_moving_average",
                "exponential_moving_average_26",
                "exponential_moving_average_50",
                "exponential_moving_average_100",
                "exponential_moving_average_200",
                "relative_strength_index",
                "moving_average_convergence_divergence",
                "simple_moving_average_20",
                "rolling_standard_deviation_20",
                "bollinger_bands_20_2",
                "directional_movement",
                "directional_indicators",
                "directional_index",
                "average_directional_index",
                "average_directional_movement_rating",
            ),
        )
        self.assertEqual(
            result.registry_hash,
            INTRADAY_FEATURE_REGISTRY.configuration_hash,
        )
        self.assertEqual(result.registry_schema_version, "1.1.0")
        self.assertEqual(result.availability_contract_version, "1.0.0")
        self.assertTrue(result.point_in_time_validated)
        self.assertEqual(len(result.values), 25)
        self.assertEqual(len(result.result_hash), 64)

    def test_warmup_and_output_order_are_enforced(self) -> None:
        observations = _observations(3, CandleTimeframe.MINUTE_10)
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_10)
        )
        first_timestamp = observations[0].candle.timestamp
        second_timestamp = observations[1].candle.timestamp

        first_outputs = tuple(
            value.output_name
            for value in result.values
            if value.candle_timestamp == first_timestamp
        )
        second_outputs = tuple(
            value.output_name
            for value in result.values
            if value.candle_timestamp == second_timestamp
        )

        self.assertEqual(
            first_outputs,
            (
                "candle_body_fraction",
                "candle_range_fraction",
                "upper_wick_fraction",
                "lower_wick_fraction",
            ),
        )
        self.assertEqual(
            second_outputs,
            (
                "candle_body_fraction",
                "candle_range_fraction",
                "upper_wick_fraction",
                "lower_wick_fraction",
                "true_range",
                "positive_directional_movement",
                "negative_directional_movement",
            ),
        )

    def test_every_output_has_exact_candle_close_availability(self) -> None:
        duration_by_timeframe = {
            CandleTimeframe.MINUTE_5: timedelta(minutes=5),
            CandleTimeframe.MINUTE_10: timedelta(minutes=10),
            CandleTimeframe.MINUTE_15: timedelta(minutes=15),
        }

        for timeframe, duration in duration_by_timeframe.items():
            result = run_intraday_feature_pipeline(
                _snapshot(_observations(4, timeframe), timeframe)
            )
            for value in result.values:
                with self.subTest(
                    timeframe=timeframe,
                    output=value.output_name,
                ):
                    self.assertEqual(
                        value.available_at,
                        value.candle_timestamp + duration,
                    )
                    self.assertGreater(
                        value.available_at,
                        value.candle_timestamp,
                    )

    def test_repeated_execution_is_identical(self) -> None:
        snapshot = _snapshot(
            _observations(8, CandleTimeframe.MINUTE_15),
            CandleTimeframe.MINUTE_15,
        )

        first = run_intraday_feature_pipeline(snapshot)
        second = run_intraday_feature_pipeline(snapshot)

        self.assertEqual(first, second)
        self.assertEqual(first.result_hash, second.result_hash)

    def test_pipeline_results_are_prefix_invariant(self) -> None:
        observations = _observations(8, CandleTimeframe.MINUTE_5)
        full = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )

        for prefix_length in range(1, len(observations) + 1):
            prefix = observations[:prefix_length]
            prefix_result = run_intraday_feature_pipeline(
                _snapshot(prefix, CandleTimeframe.MINUTE_5)
            )
            prefix_end = prefix[-1].candle.timestamp
            expected = tuple(
                value for value in full.values if value.candle_timestamp <= prefix_end
            )
            self.assertEqual(prefix_result.values, expected)

    def test_future_mutation_does_not_change_prior_pipeline_values(
        self,
    ) -> None:
        observations = _observations(6, CandleTimeframe.MINUTE_5)
        changed_last = replace(
            observations[-1],
            candle=replace(
                observations[-1].candle,
                open=Decimal("200"),
                high=Decimal("220"),
                low=Decimal("190"),
                close=Decimal("215"),
            ),
        )
        changed = observations[:-1] + (changed_last,)
        prior_timestamp = observations[-2].candle.timestamp

        original = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )
        recomputed = run_intraday_feature_pipeline(
            _snapshot(changed, CandleTimeframe.MINUTE_5)
        )

        self.assertNotEqual(
            original.source_data_hash,
            recomputed.source_data_hash,
        )
        self.assertNotEqual(original.result_hash, recomputed.result_hash)
        self.assertEqual(
            tuple(
                value
                for value in original.values
                if value.candle_timestamp <= prior_timestamp
            ),
            tuple(
                value
                for value in recomputed.values
                if value.candle_timestamp <= prior_timestamp
            ),
        )

    def test_tampered_snapshot_is_rejected_before_execution(self) -> None:
        snapshot = _snapshot(
            _observations(3, CandleTimeframe.MINUTE_5),
            CandleTimeframe.MINUTE_5,
        )
        tampered = replace(snapshot, data_hash="0" * 64)

        with self.assertRaisesRegex(
            FeatureComputationError,
            "integrity verification",
        ):
            run_intraday_feature_pipeline(tampered)

    def test_pipeline_emits_no_duplicate_feature_identity(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(
                _observations(8, CandleTimeframe.MINUTE_5),
                CandleTimeframe.MINUTE_5,
            )
        )
        identities = tuple(
            (value.candle_timestamp, value.output_name) for value in result.values
        )

        self.assertEqual(len(identities), len(set(identities)))


def _snapshot(
    observations: tuple[SourceCandleObservation, ...],
    timeframe: CandleTimeframe,
):
    return build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
    )


def _observations(
    count: int,
    timeframe: CandleTimeframe,
) -> tuple[SourceCandleObservation, ...]:
    durations = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
        CandleTimeframe.DAY_1: timedelta(days=1),
    }
    duration = durations[timeframe]
    start = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
    observations: list[SourceCandleObservation] = []
    for index in range(count):
        open_price = Decimal(100 + index)
        close = open_price + Decimal("0.5")
        observations.append(
            SourceCandleObservation(
                candle=Candle(
                    timestamp=start + duration * index,
                    open=open_price,
                    high=close + Decimal("1"),
                    low=open_price - Decimal("1"),
                    close=close,
                    volume=Decimal(10 + index),
                ),
                ingestion_batch_id=(_BATCH_A if index % 2 == 0 else _BATCH_B),
                is_complete=True,
            )
        )
    return tuple(observations)


if __name__ == "__main__":
    unittest.main()
