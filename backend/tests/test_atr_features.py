"""Focused specification and integration tests for approved ATR-01."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import unittest
from uuid import UUID

from app.features.atr import ATR_PERIOD, AverageTrueRange
from app.features.contracts import (
    FeatureComputationError,
    FeatureDependencyInput,
    FeatureHistoryType,
    FeatureValue,
)
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import _dependency_membership_rows


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000101")


class AverageTrueRangeFormulaTests(unittest.TestCase):
    feature = AverageTrueRange()

    def test_metadata_matches_approved_quantitative_specification(self) -> None:
        metadata = self.feature.metadata

        self.assertEqual(metadata.identifier, "average_true_range")
        self.assertEqual(metadata.definition_version, "1.0.0")
        self.assertEqual(metadata.category, "volatility")
        self.assertEqual(metadata.history_type, FeatureHistoryType.BOUNDED)
        self.assertEqual(metadata.maximum_lookback_observations, 15)
        self.assertEqual(metadata.outputs[0].minimum_observations, 15)
        self.assertEqual(metadata.dependencies, ("true_range",))
        self.assertEqual(
            metadata.dependency_contracts[0].definition_version,
            "1.0.0",
        )
        self.assertEqual(
            metadata.dependency_contracts[0].output_names,
            ("true_range",),
        )

    def test_first_complete_window_is_exact_arithmetic_mean(self) -> None:
        candles = _candles(15, CandleTimeframe.MINUTE_5)
        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            (_true_range_input(candles, range(1, 15)),),
        )

        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].timestamp, candles[-1].timestamp)
        self.assertEqual(
            values[0].value,
            Decimal("7.500000000000000000"),
        )
        self.assertEqual(len(values[0].dependencies), ATR_PERIOD)
        self.assertEqual(
            tuple(value.timestamp for value in values[0].dependencies),
            tuple(candle.timestamp for candle in candles[1:]),
        )

    def test_rolling_window_is_current_inclusive(self) -> None:
        candles = _candles(16, CandleTimeframe.MINUTE_5)
        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            (_true_range_input(candles, range(1, 16)),),
        )

        self.assertEqual(
            tuple(value.value for value in values),
            (
                Decimal("7.500000000000000000"),
                Decimal("8.500000000000000000"),
            ),
        )
        self.assertEqual(
            tuple(dependency.timestamp for dependency in values[-1].dependencies),
            tuple(candle.timestamp for candle in candles[2:]),
        )

    def test_warmup_omits_every_incomplete_window(self) -> None:
        for candle_count in range(1, 15):
            candles = _candles(candle_count, CandleTimeframe.MINUTE_10)
            with self.subTest(candle_count=candle_count):
                self.assertEqual(
                    self.feature.compute(
                        candles,
                        CandleTimeframe.MINUTE_10,
                        (
                            _true_range_input(
                                candles,
                                range(1, candle_count),
                            ),
                        ),
                    ),
                    (),
                )

    def test_zero_and_half_even_ties_are_exact(self) -> None:
        candles = _candles(15, CandleTimeframe.MINUTE_15)
        fixtures = (
            ([Decimal(0)] * 14, Decimal("0.000000000000000000")),
            (
                [Decimal("0.000000000000000007")] + [Decimal(0)] * 13,
                Decimal("0.000000000000000000"),
            ),
            (
                [Decimal("0.000000000000000021")] + [Decimal(0)] * 13,
                Decimal("0.000000000000000002"),
            ),
        )

        for true_ranges, expected in fixtures:
            with self.subTest(expected=expected):
                result = self.feature.compute(
                    candles,
                    CandleTimeframe.MINUTE_15,
                    (_true_range_input(candles, true_ranges),),
                )
                self.assertEqual(result[0].value, expected)

    def test_dependency_contract_and_values_fail_closed(self) -> None:
        candles = _candles(15, CandleTimeframe.MINUTE_5)
        valid = _true_range_input(candles, range(1, 15))
        invalid_inputs = (
            (),
            (replace(valid, definition_version="2.0.0"),),
            (replace(valid, output_name="other_range"),),
            (
                replace(
                    valid,
                    values=valid.values[:-1],
                ),
            ),
            (
                replace(
                    valid,
                    values=valid.values[:-1]
                    + (replace(valid.values[-1], value=Decimal("-1")),),
                ),
            ),
        )

        for dependency_inputs in invalid_inputs:
            with self.subTest(dependency_inputs=dependency_inputs):
                with self.assertRaises(FeatureComputationError):
                    self.feature.compute(
                        candles,
                        CandleTimeframe.MINUTE_5,
                        dependency_inputs,
                    )

    def test_discontinuous_source_fails_closed(self) -> None:
        candles = _candles(15, CandleTimeframe.MINUTE_5)
        discontinuous = (
            candles[:7]
            + (
                replace(
                    candles[7],
                    timestamp=candles[7].timestamp + timedelta(minutes=5),
                ),
            )
            + candles[8:]
        )

        with self.assertRaises(FeatureComputationError):
            self.feature.compute(
                discontinuous,
                CandleTimeframe.MINUTE_5,
                (_true_range_input(candles, range(1, 15)),),
            )

    def test_outputs_and_memberships_are_immutable(self) -> None:
        candles = _candles(15, CandleTimeframe.MINUTE_5)
        value = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            (_true_range_input(candles, range(1, 15)),),
        )[0]

        with self.assertRaises(FrozenInstanceError):
            value.value = Decimal("1")


class AverageTrueRangePipelineTests(unittest.TestCase):
    def test_pipeline_reuses_true_range_and_retains_ordered_provenance(
        self,
    ) -> None:
        observations = _observations(16, CandleTimeframe.MINUTE_5)
        snapshot = build_intraday_source_snapshot(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=CandleTimeframe.MINUTE_5,
            observations=observations,
        )

        result = run_intraday_feature_pipeline(snapshot)

        self.assertEqual(INTRADAY_PIPELINE_VERSION, "2.6.0")
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
            ),
        )
        atr_values = tuple(
            value
            for value in result.values
            if value.output_name == "average_true_range"
        )
        self.assertEqual(
            tuple(value.value for value in atr_values),
            (
                Decimal("7.500000000000000000"),
                Decimal("8.500000000000000000"),
            ),
        )
        atr_memberships = tuple(
            value
            for value in result.dependency_memberships
            if value.consumer_feature_identifier == "average_true_range"
        )
        self.assertEqual(len(atr_memberships), 28)
        first_memberships = atr_memberships[:14]
        self.assertEqual(
            tuple(value.dependency_ordinal for value in first_memberships),
            tuple(range(14)),
        )
        self.assertTrue(
            all(
                value.dependency_feature_identifier == "true_range"
                and value.dependency_definition_version == "1.0.0"
                and value.dependency_output_name == "true_range"
                for value in atr_memberships
            )
        )
        self.assertEqual(
            tuple(value.dependency_candle_timestamp for value in first_memberships),
            tuple(value.candle.timestamp for value in observations[1:15]),
        )
        self.assertTrue(
            all(
                membership.dependency_available_at
                <= next(
                    value.available_at
                    for value in atr_values
                    if value.candle_timestamp == membership.consumer_candle_timestamp
                )
                for membership in atr_memberships
            )
        )

    def test_dependency_provenance_maps_to_exact_persisted_values(self) -> None:
        observations = _observations(15, CandleTimeframe.MINUTE_5)
        result = run_intraday_feature_pipeline(
            build_intraday_source_snapshot(
                asset_identifier="BTC",
                quote_currency="USD",
                timeframe=CandleTimeframe.MINUTE_5,
                observations=observations,
            )
        )
        stored_values = tuple(
            SimpleNamespace(
                id=index + 1,
                candle_timestamp=value.candle_timestamp,
                feature_name=value.output_name,
                feature_value=value.value,
            )
            for index, value in enumerate(result.values)
        )
        run_id = UUID("00000000-0000-0000-0000-000000000102")
        recorded_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
        atr_result = replace(
            result,
            dependency_memberships=tuple(
                membership
                for membership in result.dependency_memberships
                if membership.consumer_feature_identifier == "average_true_range"
            ),
        )

        rows = _dependency_membership_rows(
            run_id,
            stored_values,
            atr_result,
            recorded_at,
        )

        self.assertEqual(len(rows), 14)
        self.assertEqual(
            tuple(row["dependency_ordinal"] for row in rows),
            tuple(range(14)),
        )
        self.assertEqual(len({row["feature_value_id"] for row in rows}), 1)
        expected_dependency_ids = tuple(
            value.id for value in stored_values if value.feature_name == "true_range"
        )
        self.assertEqual(
            tuple(row["dependency_feature_value_id"] for row in rows),
            expected_dependency_ids,
        )
        self.assertTrue(all(row["feature_run_id"] == run_id for row in rows))

    def test_pipeline_is_prefix_invariant_and_future_isolated(self) -> None:
        observations = _observations(17, CandleTimeframe.MINUTE_5)
        full_snapshot = build_intraday_source_snapshot(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=CandleTimeframe.MINUTE_5,
            observations=observations,
        )
        full = run_intraday_feature_pipeline(full_snapshot)
        prefix = observations[:16]
        prefix_result = run_intraday_feature_pipeline(
            build_intraday_source_snapshot(
                asset_identifier="BTC",
                quote_currency="USD",
                timeframe=CandleTimeframe.MINUTE_5,
                observations=prefix,
            )
        )
        prefix_end = prefix[-1].candle.timestamp

        self.assertEqual(
            prefix_result.values,
            tuple(
                value for value in full.values if value.candle_timestamp <= prefix_end
            ),
        )
        changed_last = replace(
            observations[-1],
            candle=replace(
                observations[-1].candle,
                high=Decimal("200"),
            ),
        )
        changed = run_intraday_feature_pipeline(
            build_intraday_source_snapshot(
                asset_identifier="BTC",
                quote_currency="USD",
                timeframe=CandleTimeframe.MINUTE_5,
                observations=observations[:-1] + (changed_last,),
            )
        )
        self.assertEqual(
            tuple(
                value for value in full.values if value.candle_timestamp <= prefix_end
            ),
            tuple(
                value
                for value in changed.values
                if value.candle_timestamp <= prefix_end
            ),
        )


def _true_range_input(
    candles: tuple[Candle, ...],
    values,
) -> FeatureDependencyInput:
    materialized = tuple(Decimal(value) for value in values)
    return FeatureDependencyInput(
        definition_identifier="true_range",
        definition_version="1.0.0",
        output_name="true_range",
        values=tuple(
            FeatureValue(
                timestamp=candle.timestamp,
                feature_name="true_range",
                value=value.quantize(Decimal("0.000000000000000001")),
            )
            for candle, value in zip(
                candles[1:],
                materialized,
                strict=True,
            )
        ),
    )


def _observations(
    count: int,
    timeframe: CandleTimeframe,
) -> tuple[SourceCandleObservation, ...]:
    return tuple(
        SourceCandleObservation(
            candle=candle,
            ingestion_batch_id=_BATCH_ID,
            is_complete=True,
        )
        for candle in _candles(count, timeframe, expanding_ranges=True)
    )


def _candles(
    count: int,
    timeframe: CandleTimeframe,
    *,
    expanding_ranges: bool = False,
) -> tuple[Candle, ...]:
    duration = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]
    start = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    return tuple(
        Candle(
            timestamp=start + index * duration,
            open=Decimal("100"),
            high=(
                Decimal("100") + Decimal(index) if expanding_ranges else Decimal("101")
            ),
            low=Decimal("100"),
            close=Decimal("100"),
            volume=Decimal("1"),
        )
        for index in range(count)
    )


if __name__ == "__main__":
    unittest.main()
