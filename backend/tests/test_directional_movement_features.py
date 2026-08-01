"""Focused specification and integration tests for Directional Movement."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from types import SimpleNamespace
import unittest
from uuid import UUID

from app.features.contracts import (
    CandleField,
    FeatureComputationError,
    FeatureHistoryType,
)
from app.features.directional_movement import (
    ADXR_IDENTIFIER,
    AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
    DIRECTIONAL_INDEX_IDENTIFIER,
    DIRECTIONAL_INDICATORS_IDENTIFIER,
    DIRECTIONAL_MOVEMENT_FEATURE_DEFINITIONS,
    DIRECTIONAL_MOVEMENT_IDENTIFIER,
    NEGATIVE_DI_IDENTIFIER,
    NEGATIVE_DM_IDENTIFIER,
    POSITIVE_DI_IDENTIFIER,
    POSITIVE_DM_IDENTIFIER,
    DirectionalMovement,
)
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import _dependency_membership_rows


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000601")
_FAMILY_DEFINITIONS = {
    definition.metadata.identifier: definition
    for definition in DIRECTIONAL_MOVEMENT_FEATURE_DEFINITIONS
}
_FAMILY_IDENTIFIERS = tuple(_FAMILY_DEFINITIONS)
_FAMILY_OUTPUTS = (
    POSITIVE_DM_IDENTIFIER,
    NEGATIVE_DM_IDENTIFIER,
    POSITIVE_DI_IDENTIFIER,
    NEGATIVE_DI_IDENTIFIER,
    DIRECTIONAL_INDEX_IDENTIFIER,
    AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER,
    ADXR_IDENTIFIER,
)


class DirectionalMovementFormulaTests(unittest.TestCase):
    def test_metadata_matches_approved_warmup_and_dependency_graph(self) -> None:
        raw = _FAMILY_DEFINITIONS[DIRECTIONAL_MOVEMENT_IDENTIFIER].metadata
        indicators = _FAMILY_DEFINITIONS[DIRECTIONAL_INDICATORS_IDENTIFIER].metadata
        dx = _FAMILY_DEFINITIONS[DIRECTIONAL_INDEX_IDENTIFIER].metadata
        adx = _FAMILY_DEFINITIONS[AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER].metadata
        adxr = _FAMILY_DEFINITIONS[ADXR_IDENTIFIER].metadata

        self.assertEqual(raw.required_inputs, (CandleField.HIGH, CandleField.LOW))
        self.assertEqual(raw.history_type, FeatureHistoryType.BOUNDED)
        self.assertEqual(
            tuple(output.minimum_observations for output in raw.outputs), (2, 2)
        )
        self.assertEqual(indicators.history_type, FeatureHistoryType.RECURSIVE)
        self.assertEqual(
            indicators.dependencies, (DIRECTIONAL_MOVEMENT_IDENTIFIER, "true_range")
        )
        self.assertEqual(
            tuple(output.minimum_observations for output in indicators.outputs),
            (15, 15),
        )
        self.assertEqual(dx.dependencies, (DIRECTIONAL_INDICATORS_IDENTIFIER,))
        self.assertEqual(dx.outputs[0].minimum_observations, 15)
        self.assertEqual(adx.history_type, FeatureHistoryType.RECURSIVE)
        self.assertEqual(adx.outputs[0].minimum_observations, 28)
        self.assertEqual(adxr.outputs[0].minimum_observations, 42)

    def test_strict_tie_inside_and_dominant_movement_rules(self) -> None:
        start = datetime(2026, 8, 1, tzinfo=timezone.utc)
        candles = (
            _candle(start, Decimal(100), Decimal(110), Decimal(90)),
            _candle(
                start + timedelta(minutes=5), Decimal(100), Decimal(112), Decimal(88)
            ),
            _candle(
                start + timedelta(minutes=10), Decimal(100), Decimal(111), Decimal(89)
            ),
            _candle(
                start + timedelta(minutes=15), Decimal(100), Decimal(114), Decimal(90)
            ),
            _candle(
                start + timedelta(minutes=20), Decimal(100), Decimal(113), Decimal(86)
            ),
        )

        values = DirectionalMovement().compute(candles, CandleTimeframe.MINUTE_5)
        pairs = tuple(
            (values[index].value, values[index + 1].value)
            for index in range(0, len(values), 2)
        )

        self.assertEqual(
            pairs,
            (
                (Decimal("0E-18"), Decimal("0E-18")),
                (Decimal("0E-18"), Decimal("0E-18")),
                (Decimal("3.000000000000000000"), Decimal("0E-18")),
                (Decimal("0E-18"), Decimal("4.000000000000000000")),
            ),
        )

    def test_linear_one_sided_fixture_produces_exact_di_dx_adx_adxr(self) -> None:
        result = _pipeline(_linear_observations(42))

        self.assertEqual(
            _values(result, POSITIVE_DI_IDENTIFIER)[0].value,
            Decimal("50.000000000000000000"),
        )
        self.assertTrue(
            all(
                value.value == Decimal("0E-18")
                for value in _values(result, NEGATIVE_DI_IDENTIFIER)
            )
        )
        self.assertTrue(
            all(
                value.value == Decimal("100.000000000000000000")
                for value in _values(result, DIRECTIONAL_INDEX_IDENTIFIER)
            )
        )
        self.assertTrue(
            all(
                value.value == Decimal("100.000000000000000000")
                for value in _values(result, AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER)
            )
        )
        self.assertEqual(
            tuple(value.value for value in _values(result, ADXR_IDENTIFIER)),
            (Decimal("100.000000000000000000"),),
        )

    def test_flat_zero_denominators_are_defined_as_zero(self) -> None:
        result = _pipeline(_flat_observations(42))

        for output_name in _FAMILY_OUTPUTS:
            with self.subTest(output_name=output_name):
                self.assertTrue(
                    all(
                        value.value == Decimal("0E-18")
                        for value in _values(result, output_name)
                    )
                )

    def test_exact_warmup_counts_and_first_timestamps(self) -> None:
        observations = _linear_observations(42)
        result = _pipeline(observations)
        expected = {
            POSITIVE_DM_IDENTIFIER: (41, 1),
            NEGATIVE_DM_IDENTIFIER: (41, 1),
            POSITIVE_DI_IDENTIFIER: (28, 14),
            NEGATIVE_DI_IDENTIFIER: (28, 14),
            DIRECTIONAL_INDEX_IDENTIFIER: (28, 14),
            AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER: (15, 27),
            ADXR_IDENTIFIER: (1, 41),
        }

        for output_name, (count, first_index) in expected.items():
            with self.subTest(output_name=output_name):
                values = _values(result, output_name)
                self.assertEqual(len(values), count)
                self.assertEqual(
                    values[0].candle_timestamp,
                    observations[first_index].candle.timestamp,
                )

    def test_execution_isolated_from_ambient_decimal_context(self) -> None:
        observations = _nonlinear_observations(45)
        expected = _family_values(_pipeline(observations))

        with localcontext() as context:
            context.prec = 6
            actual = _family_values(_pipeline(observations))

        self.assertEqual(actual, expected)

    def test_invalid_and_discontinuous_candles_fail_closed(self) -> None:
        candles = tuple(observation.candle for observation in _linear_observations(4))
        invalid = (
            candles[:2] + (replace(candles[2], high=None),) + candles[3:],
            candles[:2] + (replace(candles[2], high=Decimal(0)),) + candles[3:],
            candles[:2]
            + (replace(candles[2], timestamp=candles[1].timestamp),)
            + candles[3:],
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(FeatureComputationError):
                    DirectionalMovement().compute(candidate, CandleTimeframe.MINUTE_5)

    def test_missing_registered_dependencies_fail_closed(self) -> None:
        candles = tuple(observation.candle for observation in _linear_observations(15))
        with self.assertRaisesRegex(
            FeatureComputationError,
            "dependency count is invalid",
        ):
            _FAMILY_DEFINITIONS[DIRECTIONAL_INDICATORS_IDENTIFIER].compute(
                candles,
                CandleTimeframe.MINUTE_5,
            )

    def test_outputs_are_immutable(self) -> None:
        values = DirectionalMovement().compute(
            tuple(observation.candle for observation in _linear_observations(3)),
            CandleTimeframe.MINUTE_5,
        )
        with self.assertRaises(FrozenInstanceError):
            values[-1].value = Decimal(0)


class DirectionalMovementPipelineTests(unittest.TestCase):
    def test_registry_and_pipeline_use_topological_family_order(self) -> None:
        result = _pipeline(_linear_observations(42))

        self.assertEqual(INTRADAY_PIPELINE_VERSION, "2.7.0")
        self.assertEqual(result.execution_order[-5:], _FAMILY_IDENTIFIERS)
        self.assertEqual(
            tuple(
                definition.identifier
                for definition in INTRADAY_FEATURE_REGISTRY.definitions[-5:]
            ),
            _FAMILY_IDENTIFIERS,
        )
        self.assertEqual(INTRADAY_FEATURE_REGISTRY.output_names[-7:], _FAMILY_OUTPUTS)

    def test_provenance_reuses_true_range_and_each_registered_stage(self) -> None:
        result = _pipeline(_linear_observations(42))
        memberships = _family_memberships(result)
        by_consumer = {
            identifier: tuple(
                membership
                for membership in memberships
                if membership.consumer_feature_identifier == identifier
            )
            for identifier in _FAMILY_IDENTIFIERS
        }

        self.assertEqual(by_consumer[DIRECTIONAL_MOVEMENT_IDENTIFIER], ())
        self.assertTrue(
            any(
                membership.dependency_feature_identifier == "true_range"
                for membership in by_consumer[DIRECTIONAL_INDICATORS_IDENTIFIER]
            )
        )
        self.assertEqual(
            {
                membership.dependency_feature_identifier
                for membership in by_consumer[DIRECTIONAL_INDEX_IDENTIFIER]
            },
            {DIRECTIONAL_INDICATORS_IDENTIFIER},
        )
        self.assertEqual(
            {
                membership.dependency_feature_identifier
                for membership in by_consumer[AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER]
            },
            {DIRECTIONAL_INDEX_IDENTIFIER, AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER},
        )
        self.assertEqual(
            {
                membership.dependency_feature_identifier
                for membership in by_consumer[ADXR_IDENTIFIER]
            },
            {AVERAGE_DIRECTIONAL_INDEX_IDENTIFIER},
        )
        self.assertTrue(
            all(
                membership.dependency_available_at
                <= next(
                    value.available_at
                    for value in result.values
                    if value.feature_identifier
                    == membership.consumer_feature_identifier
                    and value.output_name == membership.consumer_output_name
                    and value.candle_timestamp == membership.consumer_candle_timestamp
                )
                for membership in memberships
            )
        )

    def test_deterministic_replay_prefix_invariance_and_future_isolation(self) -> None:
        observations = _nonlinear_observations(45)
        full = _pipeline(observations)
        replay = _pipeline(observations)
        prefix = _pipeline(observations[:-1])
        changed_last = replace(
            observations[-1],
            candle=replace(
                observations[-1].candle,
                high=observations[-1].candle.high + Decimal(5),
                close=observations[-1].candle.close + Decimal(2),
            ),
        )
        changed = _pipeline(observations[:-1] + (changed_last,))
        prefix_end = observations[-2].candle.timestamp

        self.assertEqual(full, replay)
        self.assertEqual(full.result_hash, replay.result_hash)
        self.assertEqual(
            _family_values(prefix),
            tuple(
                value
                for value in _family_values(full)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertEqual(
            tuple(
                value
                for value in _family_values(full)
                if value.candle_timestamp <= prefix_end
            ),
            tuple(
                value
                for value in _family_values(changed)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertNotEqual(_family_values(full)[-7:], _family_values(changed)[-7:])

    def test_dependency_provenance_maps_to_immutable_persistence_rows(self) -> None:
        result = _pipeline(_linear_observations(42))
        stored_values = tuple(
            SimpleNamespace(
                id=index + 1,
                candle_timestamp=value.candle_timestamp,
                feature_name=value.output_name,
                feature_value=value.value,
            )
            for index, value in enumerate(result.values)
        )
        family_result = replace(
            result,
            dependency_memberships=_family_memberships(result),
        )

        rows = _dependency_membership_rows(
            UUID("00000000-0000-0000-0000-000000000602"),
            stored_values,
            family_result,
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(len(rows), len(family_result.dependency_memberships))
        self.assertTrue(
            all(
                row["feature_value_id"] != row["dependency_feature_value_id"]
                for row in rows
            )
        )


def _pipeline(observations: tuple[SourceCandleObservation, ...]):
    return run_intraday_feature_pipeline(
        build_intraday_source_snapshot(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=CandleTimeframe.MINUTE_5,
            observations=observations,
        )
    )


def _linear_observations(count: int) -> tuple[SourceCandleObservation, ...]:
    return _observations(tuple(Decimal(100 + index) for index in range(count)))


def _flat_observations(count: int) -> tuple[SourceCandleObservation, ...]:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return tuple(
        SourceCandleObservation(
            candle=_candle(
                start + timedelta(minutes=5 * index),
                Decimal(100),
                Decimal(100),
                Decimal(100),
            ),
            ingestion_batch_id=_BATCH_ID,
            is_complete=True,
        )
        for index in range(count)
    )


def _nonlinear_observations(count: int) -> tuple[SourceCandleObservation, ...]:
    closes = tuple(
        Decimal(100)
        + Decimal((index * 7) % 13) / Decimal(3)
        + Decimal(index) / Decimal(10)
        for index in range(count)
    )
    return _observations(closes)


def _observations(closes: tuple[Decimal, ...]) -> tuple[SourceCandleObservation, ...]:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return tuple(
        SourceCandleObservation(
            candle=_candle(
                start + timedelta(minutes=5 * index),
                close,
                close + Decimal(1),
                close - Decimal(1),
            ),
            ingestion_batch_id=_BATCH_ID,
            is_complete=True,
        )
        for index, close in enumerate(closes)
    )


def _candle(timestamp: datetime, close: Decimal, high: Decimal, low: Decimal) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=close,
        high=high,
        low=low,
        close=close,
        volume=Decimal(10),
    )


def _values(result, output_name: str):
    return tuple(value for value in result.values if value.output_name == output_name)


def _family_values(result):
    return tuple(
        value for value in result.values if value.output_name in _FAMILY_OUTPUTS
    )


def _family_memberships(result):
    return tuple(
        membership
        for membership in result.dependency_memberships
        if membership.consumer_feature_identifier in _FAMILY_IDENTIFIERS
    )


if __name__ == "__main__":
    unittest.main()
