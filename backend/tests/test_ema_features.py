"""Focused specification and integration tests for approved EMA-01."""

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
    FeatureValueDependency,
)
from app.features.ema import (
    EMA_100_IDENTIFIER,
    EMA_12_IDENTIFIER,
    EMA_200_IDENTIFIER,
    EMA_26_IDENTIFIER,
    EMA_50_IDENTIFIER,
    EMA_DEFINITION_VERSION,
    EMA_FEATURE_DEFINITIONS,
    EMA_FAMILY_IDENTITIES,
    EMA_IDENTIFIER,
    EMA_PERIOD,
    ExponentialMovingAverage,
    ExponentialMovingAverageFamilyMember,
)
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    PipelineFeatureValue,
    SourceCandleObservation,
    _feature_dependency_memberships,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import _dependency_membership_rows


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000201")


class ExponentialMovingAverageFormulaTests(unittest.TestCase):
    feature = ExponentialMovingAverage()

    def test_metadata_matches_successor_registry_specification(self) -> None:
        metadata = self.feature.metadata

        self.assertEqual(metadata.identifier, "exponential_moving_average")
        self.assertEqual(metadata.definition_version, "1.0.0")
        self.assertEqual(metadata.category, "trend")
        self.assertEqual(metadata.required_inputs, (CandleField.CLOSE,))
        self.assertEqual(metadata.history_type, FeatureHistoryType.RECURSIVE)
        self.assertIsNone(metadata.maximum_lookback_observations)
        self.assertTrue(metadata.requires_continuity)
        self.assertEqual(metadata.outputs[0].identifier, EMA_IDENTIFIER)
        self.assertEqual(metadata.outputs[0].minimum_observations, EMA_PERIOD)
        self.assertEqual(metadata.dependencies, ())
        self.assertEqual(metadata.dependency_contracts, ())

    def test_seed_and_recursive_values_match_approved_fixtures(self) -> None:
        candles = _candles_from_closes(tuple(Decimal(index) for index in range(1, 23)))

        values = self.feature.compute(candles, CandleTimeframe.MINUTE_5)

        self.assertEqual(
            tuple(value.value for value in values),
            (
                Decimal("10.500000000000000000"),
                Decimal("11.500000000000000000"),
                Decimal("12.500000000000000000"),
            ),
        )
        self.assertEqual(values[0].timestamp, candles[19].timestamp)
        self.assertEqual(values[0].dependencies, ())
        self.assertEqual(
            tuple(value.dependencies[0].timestamp for value in values[1:]),
            (candles[19].timestamp, candles[20].timestamp),
        )

    def test_warmup_omits_every_undefined_value(self) -> None:
        for candle_count in range(1, EMA_PERIOD):
            with self.subTest(candle_count=candle_count):
                self.assertEqual(
                    self.feature.compute(
                        _candles_from_closes(
                            tuple(
                                Decimal(index) for index in range(1, candle_count + 1)
                            ),
                            CandleTimeframe.MINUTE_10,
                        ),
                        CandleTimeframe.MINUTE_10,
                    ),
                    (),
                )

        first = self.feature.compute(
            _candles_from_closes(
                tuple(Decimal(index) for index in range(1, EMA_PERIOD + 1)),
                CandleTimeframe.MINUTE_10,
            ),
            CandleTimeframe.MINUTE_10,
        )
        self.assertEqual(len(first), 1)

    def test_recursive_state_is_not_replaced_by_quantized_output(self) -> None:
        closes = (Decimal("100"),) * 19 + (
            Decimal("100.000000000000000001"),
            Decimal("100.000000000000000010"),
            Decimal("100.000000000000000020"),
            Decimal("100.000000000000000030"),
        )

        values = self.feature.compute(
            _candles_from_closes(closes),
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(
            tuple(value.value for value in values),
            (
                Decimal("100.000000000000000000"),
                Decimal("100.000000000000000001"),
                Decimal("100.000000000000000003"),
                Decimal("100.000000000000000005"),
            ),
        )

    def test_execution_is_isolated_from_ambient_decimal_context(self) -> None:
        candles = _candles_from_closes(
            tuple(Decimal(index) / Decimal(7) + Decimal(100) for index in range(23))
        )
        expected = self.feature.compute(candles, CandleTimeframe.MINUTE_5)

        with localcontext() as context:
            context.prec = 6
            actual = self.feature.compute(candles, CandleTimeframe.MINUTE_5)

        self.assertEqual(actual, expected)

    def test_derived_dependency_input_is_rejected(self) -> None:
        candles = _candles_from_closes(tuple(Decimal(index) for index in range(1, 21)))
        dependency = FeatureDependencyInput(
            definition_identifier="true_range",
            definition_version="1.0.0",
            output_name="true_range",
            values=(),
        )

        with self.assertRaisesRegex(
            FeatureComputationError,
            "does not accept derived feature dependencies",
        ):
            self.feature.compute(
                candles,
                CandleTimeframe.MINUTE_5,
                (dependency,),
            )

    def test_invalid_source_evidence_fails_closed(self) -> None:
        valid = _candles_from_closes(tuple(Decimal(index) for index in range(1, 21)))
        invalid_sequences = (
            valid[:5] + (replace(valid[5], close=None),) + valid[6:],
            valid[:5] + (replace(valid[5], close=6),) + valid[6:],
            valid[:5]
            + (
                replace(
                    valid[5],
                    timestamp=valid[4].timestamp,
                ),
            )
            + valid[6:],
            valid[:5]
            + (
                replace(
                    valid[5],
                    timestamp=valid[5].timestamp + timedelta(minutes=5),
                ),
            )
            + valid[6:],
            valid[:5]
            + (
                replace(
                    valid[5],
                    close=valid[5].high + Decimal(1),
                ),
            )
            + valid[6:],
        )

        for candles in invalid_sequences:
            with self.subTest(candles=candles):
                with self.assertRaises(FeatureComputationError):
                    self.feature.compute(candles, CandleTimeframe.MINUTE_5)

    def test_outputs_and_predecessor_memberships_are_immutable(self) -> None:
        values = self.feature.compute(
            _candles_from_closes(tuple(Decimal(index) for index in range(1, 22))),
            CandleTimeframe.MINUTE_5,
        )

        with self.assertRaises(FrozenInstanceError):
            values[-1].value = Decimal(0)
        with self.assertRaises(FrozenInstanceError):
            values[-1].dependencies[0].timestamp = values[-1].timestamp


class ExponentialMovingAverageFamilyTests(unittest.TestCase):
    def test_family_identities_periods_and_metadata_match_specification(self) -> None:
        self.assertEqual(
            EMA_FAMILY_IDENTITIES,
            (
                (12, EMA_12_IDENTIFIER, "EMA-12"),
                (20, EMA_IDENTIFIER, "EMA-20"),
                (26, EMA_26_IDENTIFIER, "EMA-26"),
                (50, EMA_50_IDENTIFIER, "EMA-50"),
                (100, EMA_100_IDENTIFIER, "EMA-100"),
                (200, EMA_200_IDENTIFIER, "EMA-200"),
            ),
        )
        self.assertEqual(
            tuple(
                definition.metadata.identifier for definition in EMA_FEATURE_DEFINITIONS
            ),
            tuple(identity[1] for identity in EMA_FAMILY_IDENTITIES),
        )
        self.assertEqual(
            tuple(
                definition.metadata.outputs[0].minimum_observations
                for definition in EMA_FEATURE_DEFINITIONS
            ),
            tuple(identity[0] for identity in EMA_FAMILY_IDENTITIES),
        )
        self.assertTrue(
            all(
                definition.metadata.required_inputs == (CandleField.CLOSE,)
                and definition.metadata.dependencies == ()
                and definition.metadata.dependency_contracts == ()
                and definition.metadata.history_type is FeatureHistoryType.RECURSIVE
                for definition in EMA_FEATURE_DEFINITIONS
            )
        )

    def test_all_members_share_formula_and_exact_warmup_boundaries(self) -> None:
        for definition, (period, identifier, _) in zip(
            EMA_FEATURE_DEFINITIONS,
            EMA_FAMILY_IDENTITIES,
            strict=True,
        ):
            with self.subTest(identifier=identifier):
                warmup = definition.compute(
                    _candles_from_closes(
                        tuple(Decimal(index) for index in range(1, period))
                    ),
                    CandleTimeframe.MINUTE_5,
                )
                self.assertEqual(warmup, ())

                values = definition.compute(
                    _candles_from_closes(
                        tuple(Decimal(index) for index in range(1, period + 3))
                    ),
                    CandleTimeframe.MINUTE_5,
                )
                seed = Decimal(period + 1) / Decimal(2)
                self.assertEqual(
                    tuple(value.value for value in values),
                    tuple(
                        (seed + offset).quantize(Decimal("0.000000000000000001"))
                        for offset in range(3)
                    ),
                )
                self.assertEqual(values[0].feature_name, identifier)
                self.assertEqual(values[0].dependencies, ())
                self.assertEqual(
                    tuple(value.dependencies[0].timestamp for value in values[1:]),
                    tuple(value.timestamp for value in values[:-1]),
                )

    def test_missing_members_use_one_parameterized_implementation(self) -> None:
        added = tuple(
            definition
            for definition in EMA_FEATURE_DEFINITIONS
            if definition.metadata.identifier != EMA_IDENTIFIER
        )

        self.assertEqual(len(added), 5)
        self.assertTrue(
            all(
                isinstance(definition, ExponentialMovingAverageFamilyMember)
                for definition in added
            )
        )
        self.assertEqual(
            {definition.metadata.implementation_reference for definition in added},
            {"app.features.ema.ExponentialMovingAverageFamilyMember"},
        )

    def test_every_family_member_is_prefix_invariant_and_future_isolated(self) -> None:
        closes = tuple(Decimal(index) / Decimal(7) + 100 for index in range(205))
        candles = _candles_from_closes(closes)
        changed_last = candles[:-1] + (
            replace(
                candles[-1],
                open=candles[-1].open + Decimal(5),
                high=candles[-1].high + Decimal(5),
                low=candles[-1].low + Decimal(5),
                close=candles[-1].close + Decimal(5),
            ),
        )

        for definition in EMA_FEATURE_DEFINITIONS:
            with self.subTest(identifier=definition.metadata.identifier):
                full = definition.compute(candles, CandleTimeframe.MINUTE_5)
                prefix = definition.compute(candles[:-1], CandleTimeframe.MINUTE_5)
                changed = definition.compute(changed_last, CandleTimeframe.MINUTE_5)
                self.assertEqual(prefix, full[:-1])
                self.assertEqual(changed[:-1], full[:-1])
                self.assertNotEqual(changed[-1], full[-1])

    def test_family_rejects_undeclared_dependencies(self) -> None:
        dependency = FeatureDependencyInput(
            definition_identifier="true_range",
            definition_version="1.0.0",
            output_name="true_range",
            values=(),
        )
        candles = _candles_from_closes(tuple(Decimal(index) for index in range(1, 13)))

        for definition in EMA_FEATURE_DEFINITIONS:
            with self.subTest(identifier=definition.metadata.identifier):
                with self.assertRaisesRegex(
                    FeatureComputationError,
                    "does not accept derived feature dependencies",
                ):
                    definition.compute(
                        candles,
                        CandleTimeframe.MINUTE_5,
                        (dependency,),
                    )


class ExponentialMovingAveragePipelineTests(unittest.TestCase):
    def test_registry_and_pipeline_integrate_ema_in_canonical_order(self) -> None:
        observations = _observations(23, CandleTimeframe.MINUTE_5)
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )

        self.assertEqual(INTRADAY_PIPELINE_VERSION, "2.5.0")
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
            ),
        )
        self.assertEqual(
            next(
                definition
                for definition in INTRADAY_FEATURE_REGISTRY.definitions
                if definition.identifier == EMA_IDENTIFIER
            ),
            ExponentialMovingAverage.metadata,
        )
        self.assertEqual(
            tuple(
                name
                for name in INTRADAY_FEATURE_REGISTRY.output_names
                if name.startswith("exponential_moving_average")
            ),
            tuple(identity[1] for identity in EMA_FAMILY_IDENTITIES),
        )
        ema_values = _ema_values(result.values)
        self.assertEqual(len(ema_values), 4)
        self.assertEqual(
            ema_values[0].candle_timestamp, observations[19].candle.timestamp
        )
        self.assertEqual(
            ema_values[0].available_at,
            observations[19].candle.timestamp + timedelta(minutes=5),
        )
        self.assertTrue(all(value.value > 0 for value in ema_values))

    def test_pipeline_emits_every_family_member_with_exact_recursive_lineage(
        self,
    ) -> None:
        observations = _observations(202, CandleTimeframe.MINUTE_5)
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )

        for period, identifier, _ in EMA_FAMILY_IDENTITIES:
            with self.subTest(identifier=identifier):
                values = tuple(
                    value for value in result.values if value.output_name == identifier
                )
                memberships = tuple(
                    membership
                    for membership in result.dependency_memberships
                    if membership.consumer_feature_identifier == identifier
                )
                self.assertEqual(len(values), 202 - period + 1)
                self.assertEqual(
                    values[0].candle_timestamp,
                    observations[period - 1].candle.timestamp,
                )
                self.assertEqual(len(memberships), len(values) - 1)
                self.assertEqual(
                    tuple(
                        membership.dependency_candle_timestamp
                        for membership in memberships
                    ),
                    tuple(value.candle_timestamp for value in values[:-1]),
                )
                self.assertEqual(
                    tuple(membership.dependency_value for membership in memberships),
                    tuple(value.value for value in values[:-1]),
                )

    def test_pipeline_retains_exact_recursive_predecessor_lineage(self) -> None:
        observations = _observations(23, CandleTimeframe.MINUTE_10)
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_10)
        )
        ema_values = _ema_values(result.values)
        memberships = _ema_memberships(result.dependency_memberships)

        self.assertEqual(len(memberships), len(ema_values) - 1)
        self.assertEqual(
            tuple(membership.dependency_ordinal for membership in memberships),
            (0, 0, 0),
        )
        self.assertEqual(
            tuple(membership.consumer_candle_timestamp for membership in memberships),
            tuple(value.candle_timestamp for value in ema_values[1:]),
        )
        self.assertEqual(
            tuple(membership.dependency_candle_timestamp for membership in memberships),
            tuple(value.candle_timestamp for value in ema_values[:-1]),
        )
        self.assertEqual(
            tuple(membership.dependency_value for membership in memberships),
            tuple(value.value for value in ema_values[:-1]),
        )
        self.assertTrue(
            all(
                membership.dependency_available_at
                < next(
                    value.available_at
                    for value in ema_values
                    if value.candle_timestamp == membership.consumer_candle_timestamp
                )
                for membership in memberships
            )
        )

    def test_invalid_recursive_lineage_is_rejected(self) -> None:
        feature = ExponentialMovingAverage()
        values = feature.compute(
            _candles_from_closes(tuple(Decimal(index) for index in range(1, 22))),
            CandleTimeframe.MINUTE_5,
        )
        lookup = {
            (
                EMA_IDENTIFIER,
                EMA_DEFINITION_VERSION,
                EMA_IDENTIFIER,
                value.timestamp,
            ): PipelineFeatureValue(
                feature_identifier=EMA_IDENTIFIER,
                definition_version=EMA_DEFINITION_VERSION,
                output_name=EMA_IDENTIFIER,
                candle_timestamp=value.timestamp,
                available_at=value.timestamp + timedelta(minutes=5),
                value=value.value,
            )
            for value in values
        }
        predecessor = values[1].dependencies[0]
        invalid_values = (
            (values[0], replace(values[1], dependencies=())),
            (
                values[0],
                replace(
                    values[1],
                    dependencies=(replace(predecessor, definition_version="2.0.0"),),
                ),
            ),
            (
                values[0],
                replace(
                    values[1],
                    dependencies=(replace(predecessor, output_name="other"),),
                ),
            ),
            (
                values[0],
                replace(
                    values[1],
                    dependencies=(replace(predecessor, timestamp=values[1].timestamp),),
                ),
            ),
            (
                replace(
                    values[0],
                    dependencies=(
                        FeatureValueDependency(
                            definition_identifier=EMA_IDENTIFIER,
                            definition_version=EMA_DEFINITION_VERSION,
                            output_name=EMA_IDENTIFIER,
                            timestamp=values[0].timestamp,
                        ),
                    ),
                ),
                values[1],
            ),
        )

        for tampered in invalid_values:
            with self.subTest(tampered=tampered):
                with self.assertRaises(FeatureComputationError):
                    _feature_dependency_memberships(
                        feature.metadata,
                        tampered,
                        lookup,
                    )

        with self.assertRaisesRegex(
            FeatureComputationError,
            "dependency value is missing",
        ):
            _feature_dependency_memberships(
                feature.metadata,
                values,
                {
                    key: value
                    for key, value in lookup.items()
                    if key[-1] != values[0].timestamp
                },
            )

    def test_prefix_invariance_and_future_isolation(self) -> None:
        observations = _observations(24, CandleTimeframe.MINUTE_5)
        full = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )
        prefix = run_intraday_feature_pipeline(
            _snapshot(observations[:-1], CandleTimeframe.MINUTE_5)
        )
        prefix_end = observations[-2].candle.timestamp

        self.assertEqual(
            _ema_values(prefix.values),
            tuple(
                value
                for value in _ema_values(full.values)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertEqual(
            _ema_memberships(prefix.dependency_memberships),
            tuple(
                membership
                for membership in _ema_memberships(full.dependency_memberships)
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
            _ema_values(full.values)[:-1],
            _ema_values(changed.values)[:-1],
        )
        self.assertNotEqual(
            _ema_values(full.values)[-1],
            _ema_values(changed.values)[-1],
        )

    def test_replay_and_hashing_are_deterministic(self) -> None:
        snapshot = _snapshot(_observations(23), CandleTimeframe.MINUTE_5)

        first = run_intraday_feature_pipeline(snapshot)
        second = run_intraday_feature_pipeline(snapshot)

        self.assertEqual(first, second)
        self.assertEqual(first.registry_hash, second.registry_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(len(first.registry_hash), 64)
        self.assertEqual(len(first.result_hash), 64)

    def test_recursive_provenance_maps_to_exact_persisted_values(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(_observations(23), CandleTimeframe.MINUTE_5)
        )
        ema_values = _ema_values(result.values)
        memberships = _ema_memberships(result.dependency_memberships)
        stored_values = tuple(
            SimpleNamespace(
                id=index + 1,
                candle_timestamp=value.candle_timestamp,
                feature_name=value.output_name,
                feature_value=value.value,
            )
            for index, value in enumerate(ema_values)
        )
        ema_result = replace(
            result,
            values=ema_values,
            dependency_memberships=memberships,
        )

        rows = _dependency_membership_rows(
            UUID("00000000-0000-0000-0000-000000000202"),
            stored_values,
            ema_result,
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(len(rows), len(ema_values) - 1)
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
            low=close - Decimal(1) if close > 1 else close / Decimal(2),
            close=close,
            volume=Decimal(10),
        )
        for index, close in enumerate(closes)
    )


def _observations(
    count: int,
    timeframe: CandleTimeframe = CandleTimeframe.MINUTE_5,
) -> tuple[SourceCandleObservation, ...]:
    closes = tuple(Decimal(100 + index) for index in range(count))
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


def _ema_values(values):
    return tuple(value for value in values if value.output_name == EMA_IDENTIFIER)


def _ema_memberships(memberships):
    return tuple(
        membership
        for membership in memberships
        if membership.consumer_feature_identifier == EMA_IDENTIFIER
    )


def _duration(timeframe: CandleTimeframe) -> timedelta:
    return {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]


if __name__ == "__main__":
    unittest.main()
