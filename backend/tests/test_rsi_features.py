"""Focused specification and integration tests for approved RSI-01."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from types import SimpleNamespace
import unittest
from uuid import UUID

from app.features.contracts import (
    CandleField,
    FeatureComputationError,
    FeatureDependencyInput,
    FeatureHistoryType,
)
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.features.momentum import RelativeStrengthIndex as LegacyRelativeStrengthIndex
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.features.rsi import (
    RSI_IDENTIFIER,
    RSI_MINIMUM_OBSERVATIONS,
    RSI_PERIOD,
    RelativeStrengthIndex,
)
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import _dependency_membership_rows


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000301")
_CLASSIC_CLOSES = tuple(
    Decimal(value)
    for value in (
        "44.34",
        "44.09",
        "44.15",
        "43.61",
        "44.33",
        "44.83",
        "45.10",
        "45.42",
        "45.84",
        "46.08",
        "45.89",
        "46.03",
        "45.61",
        "46.28",
        "46.28",
        "46.00",
        "46.03",
        "46.41",
        "46.22",
        "45.64",
    )
)


class RelativeStrengthIndexFormulaTests(unittest.TestCase):
    feature = RelativeStrengthIndex()

    def test_metadata_matches_approved_quantitative_specification(self) -> None:
        metadata = self.feature.metadata

        self.assertEqual(metadata.identifier, "relative_strength_index")
        self.assertEqual(metadata.definition_version, "1.0.0")
        self.assertEqual(metadata.category, "momentum")
        self.assertEqual(metadata.required_inputs, (CandleField.CLOSE,))
        self.assertEqual(metadata.history_type, FeatureHistoryType.RECURSIVE)
        self.assertIsNone(metadata.maximum_lookback_observations)
        self.assertTrue(metadata.requires_continuity)
        self.assertEqual(metadata.outputs[0].identifier, RSI_IDENTIFIER)
        self.assertEqual(
            metadata.outputs[0].minimum_observations,
            RSI_MINIMUM_OBSERVATIONS,
        )
        self.assertEqual(metadata.dependencies, ())
        self.assertEqual(metadata.dependency_contracts, ())

    def test_wilder_seed_and_recursion_match_approved_fixtures(self) -> None:
        values = self.feature.compute(
            _candles_from_closes(_CLASSIC_CLOSES),
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(
            tuple(value.value for value in values),
            (
                Decimal("70.464135021097046414"),
                Decimal("66.249618553555080867"),
                Decimal("66.480941834712670474"),
                Decimal("69.346853162908698511"),
                Decimal("66.294712658926250984"),
                Decimal("57.915020670085559689"),
            ),
        )
        self.assertEqual(
            values[0].timestamp, _candles_from_closes(_CLASSIC_CLOSES)[14].timestamp
        )
        self.assertEqual(values[0].dependencies, ())
        self.assertEqual(
            tuple(value.dependencies[0].timestamp for value in values[1:]),
            tuple(value.timestamp for value in values[:-1]),
        )

    def test_zero_gain_and_loss_edges_are_exact(self) -> None:
        fixtures = (
            (
                tuple(Decimal(index) for index in range(10, 26)),
                Decimal("100.000000000000000000"),
            ),
            (
                tuple(Decimal(100 - index) for index in range(16)),
                Decimal("0.000000000000000000"),
            ),
            (
                (Decimal("100"),) * 16,
                Decimal("50.000000000000000000"),
            ),
        )

        for closes, expected in fixtures:
            with self.subTest(expected=expected):
                values = self.feature.compute(
                    _candles_from_closes(closes),
                    CandleTimeframe.MINUTE_5,
                )
                self.assertTrue(values)
                self.assertTrue(all(value.value == expected for value in values))
                self.assertTrue(
                    all(Decimal(0) <= value.value <= Decimal(100) for value in values)
                )

    def test_warmup_omits_every_undefined_value(self) -> None:
        for candle_count in range(1, RSI_MINIMUM_OBSERVATIONS):
            with self.subTest(candle_count=candle_count):
                self.assertEqual(
                    self.feature.compute(
                        _candles_from_closes(
                            tuple(
                                Decimal(100 + index) for index in range(candle_count)
                            ),
                            CandleTimeframe.MINUTE_10,
                        ),
                        CandleTimeframe.MINUTE_10,
                    ),
                    (),
                )

        first = self.feature.compute(
            _candles_from_closes(
                tuple(Decimal(100 + index) for index in range(15)),
                CandleTimeframe.MINUTE_10,
            ),
            CandleTimeframe.MINUTE_10,
        )
        self.assertEqual(len(first), 1)

    def test_execution_is_isolated_from_ambient_decimal_context(self) -> None:
        candles = _candles_from_closes(_CLASSIC_CLOSES)
        expected = self.feature.compute(candles, CandleTimeframe.MINUTE_5)

        with localcontext() as context:
            context.prec = 6
            actual = self.feature.compute(candles, CandleTimeframe.MINUTE_5)

        self.assertEqual(actual, expected)

    def test_legacy_reference_reuses_identical_shared_wilder_primitive(self) -> None:
        candles = _candles_from_closes(_CLASSIC_CLOSES)

        successor = self.feature.compute(candles, CandleTimeframe.MINUTE_5)
        legacy = LegacyRelativeStrengthIndex(period=RSI_PERIOD).compute(candles)

        self.assertEqual(
            tuple((value.timestamp, value.value) for value in successor),
            tuple((value.timestamp, value.value) for value in legacy),
        )

    def test_derived_dependency_input_is_rejected(self) -> None:
        dependency = FeatureDependencyInput(
            definition_identifier="exponential_moving_average",
            definition_version="1.0.0",
            output_name="exponential_moving_average",
            values=(),
        )

        with self.assertRaisesRegex(
            FeatureComputationError,
            "does not accept derived feature dependencies",
        ):
            self.feature.compute(
                _candles_from_closes(_CLASSIC_CLOSES),
                CandleTimeframe.MINUTE_5,
                (dependency,),
            )

    def test_invalid_source_evidence_fails_closed(self) -> None:
        valid = _candles_from_closes(_CLASSIC_CLOSES)
        invalid_sequences = (
            valid[:5] + (replace(valid[5], close=None),) + valid[6:],
            valid[:5] + (replace(valid[5], close=45),) + valid[6:],
            valid[:5] + (replace(valid[5], timestamp=valid[4].timestamp),) + valid[6:],
            valid[:5]
            + (
                replace(
                    valid[5],
                    timestamp=valid[5].timestamp + timedelta(minutes=5),
                ),
            )
            + valid[6:],
            valid[:5]
            + (replace(valid[5], close=valid[5].high + Decimal(1)),)
            + valid[6:],
        )

        for candles in invalid_sequences:
            with self.subTest(candles=candles):
                with self.assertRaises(FeatureComputationError):
                    self.feature.compute(candles, CandleTimeframe.MINUTE_5)

    def test_outputs_and_predecessor_memberships_are_immutable(self) -> None:
        values = self.feature.compute(
            _candles_from_closes(_CLASSIC_CLOSES),
            CandleTimeframe.MINUTE_5,
        )

        with self.assertRaises(FrozenInstanceError):
            values[-1].value = Decimal(0)
        with self.assertRaises(FrozenInstanceError):
            values[-1].dependencies[0].timestamp = values[-1].timestamp


class RelativeStrengthIndexPipelineTests(unittest.TestCase):
    def test_registry_and_pipeline_integrate_rsi_in_canonical_order(self) -> None:
        observations = _observations_from_closes(
            tuple(Decimal(100 + index) for index in range(20)),
            CandleTimeframe.MINUTE_5,
        )
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )

        self.assertEqual(INTRADAY_PIPELINE_VERSION, "2.7.0")
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
            next(
                definition
                for definition in INTRADAY_FEATURE_REGISTRY.definitions
                if definition.identifier == RSI_IDENTIFIER
            ),
            RelativeStrengthIndex.metadata,
        )
        self.assertEqual(
            tuple(
                name
                for name in INTRADAY_FEATURE_REGISTRY.output_names
                if name == RSI_IDENTIFIER
            ),
            (RSI_IDENTIFIER,),
        )
        rsi_values = _rsi_values(result.values)
        self.assertEqual(len(rsi_values), 6)
        self.assertEqual(
            rsi_values[0].candle_timestamp, observations[14].candle.timestamp
        )
        self.assertEqual(
            rsi_values[0].available_at,
            observations[14].candle.timestamp + timedelta(minutes=5),
        )
        self.assertTrue(
            all(
                value.value == Decimal("100.000000000000000000") for value in rsi_values
            )
        )

    def test_pipeline_retains_exact_recursive_predecessor_lineage(self) -> None:
        observations = _observations_from_closes(
            _CLASSIC_CLOSES,
            CandleTimeframe.MINUTE_10,
        )
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_10)
        )
        rsi_values = _rsi_values(result.values)
        memberships = _rsi_memberships(result.dependency_memberships)

        self.assertEqual(len(memberships), len(rsi_values) - 1)
        self.assertTrue(all(value.dependency_ordinal == 0 for value in memberships))
        self.assertEqual(
            tuple(value.consumer_candle_timestamp for value in memberships),
            tuple(value.candle_timestamp for value in rsi_values[1:]),
        )
        self.assertEqual(
            tuple(value.dependency_candle_timestamp for value in memberships),
            tuple(value.candle_timestamp for value in rsi_values[:-1]),
        )
        self.assertEqual(
            tuple(value.dependency_value for value in memberships),
            tuple(value.value for value in rsi_values[:-1]),
        )
        self.assertTrue(
            all(
                membership.dependency_available_at
                < next(
                    value.available_at
                    for value in rsi_values
                    if value.candle_timestamp == membership.consumer_candle_timestamp
                )
                for membership in memberships
            )
        )

    def test_prefix_invariance_and_future_isolation(self) -> None:
        observations = _observations_from_closes(
            _CLASSIC_CLOSES,
            CandleTimeframe.MINUTE_5,
        )
        full = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )
        prefix = run_intraday_feature_pipeline(
            _snapshot(observations[:-1], CandleTimeframe.MINUTE_5)
        )
        prefix_end = observations[-2].candle.timestamp

        self.assertEqual(
            _rsi_values(prefix.values),
            tuple(
                value
                for value in _rsi_values(full.values)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertEqual(
            _rsi_memberships(prefix.dependency_memberships),
            tuple(
                membership
                for membership in _rsi_memberships(full.dependency_memberships)
                if membership.consumer_candle_timestamp <= prefix_end
            ),
        )

        changed_last = replace(
            observations[-1],
            candle=replace(
                observations[-1].candle,
                high=observations[-1].candle.high + Decimal(5),
                close=observations[-1].candle.close + Decimal(5),
            ),
        )
        changed = run_intraday_feature_pipeline(
            _snapshot(observations[:-1] + (changed_last,), CandleTimeframe.MINUTE_5)
        )
        self.assertEqual(
            _rsi_values(full.values)[:-1],
            _rsi_values(changed.values)[:-1],
        )
        self.assertNotEqual(
            _rsi_values(full.values)[-1],
            _rsi_values(changed.values)[-1],
        )

    def test_replay_and_hashing_are_deterministic(self) -> None:
        snapshot = _snapshot(
            _observations_from_closes(_CLASSIC_CLOSES, CandleTimeframe.MINUTE_15),
            CandleTimeframe.MINUTE_15,
        )

        first = run_intraday_feature_pipeline(snapshot)
        second = run_intraday_feature_pipeline(snapshot)

        self.assertEqual(first, second)
        self.assertEqual(first.registry_hash, second.registry_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(len(first.registry_hash), 64)
        self.assertEqual(len(first.result_hash), 64)

    def test_recursive_provenance_maps_to_exact_persisted_values(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(
                _observations_from_closes(_CLASSIC_CLOSES),
                CandleTimeframe.MINUTE_5,
            )
        )
        rsi_values = _rsi_values(result.values)
        memberships = _rsi_memberships(result.dependency_memberships)
        stored_values = tuple(
            SimpleNamespace(
                id=index + 1,
                candle_timestamp=value.candle_timestamp,
                feature_name=value.output_name,
                feature_value=value.value,
            )
            for index, value in enumerate(rsi_values)
        )
        rsi_result = replace(
            result,
            values=rsi_values,
            dependency_memberships=memberships,
        )

        rows = _dependency_membership_rows(
            UUID("00000000-0000-0000-0000-000000000302"),
            stored_values,
            rsi_result,
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(len(rows), len(rsi_values) - 1)
        self.assertEqual(
            tuple(row["feature_value_id"] for row in rows),
            tuple(value.id for value in stored_values[1:]),
        )
        self.assertEqual(
            tuple(row["dependency_feature_value_id"] for row in rows),
            tuple(value.id for value in stored_values[:-1]),
        )
        self.assertTrue(all(row["dependency_ordinal"] == 0 for row in rows))


def _candles_from_closes(
    closes: tuple[Decimal, ...],
    timeframe: CandleTimeframe = CandleTimeframe.MINUTE_5,
) -> tuple[Candle, ...]:
    step = _duration(timeframe)
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return tuple(
        Candle(
            timestamp=start + step * index,
            open=close,
            high=close + Decimal(1),
            low=close - Decimal(1),
            close=close,
            volume=Decimal(10),
        )
        for index, close in enumerate(closes)
    )


def _observations_from_closes(
    closes: tuple[Decimal, ...],
    timeframe: CandleTimeframe = CandleTimeframe.MINUTE_5,
) -> tuple[SourceCandleObservation, ...]:
    return tuple(
        SourceCandleObservation(
            candle=candle,
            ingestion_batch_id=_BATCH_ID,
            is_complete=True,
        )
        for candle in _candles_from_closes(closes, timeframe)
    )


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


def _rsi_values(values):
    return tuple(value for value in values if value.output_name == RSI_IDENTIFIER)


def _rsi_memberships(memberships):
    return tuple(
        membership
        for membership in memberships
        if membership.consumer_feature_identifier == RSI_IDENTIFIER
    )


def _duration(timeframe: CandleTimeframe) -> timedelta:
    return {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]


if __name__ == "__main__":
    unittest.main()
