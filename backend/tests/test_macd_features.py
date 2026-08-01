"""Focused specification and integration tests for approved MACD-01."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

from app.features.contracts import (
    CandleField,
    FeatureComputationError,
    FeatureDependencyInput,
    FeatureHistoryType,
)
from app.features.ema import (
    EMA_12_IDENTIFIER,
    EMA_26_IDENTIFIER,
    EMA_DEFINITION_VERSION,
    EMA_FEATURE_DEFINITIONS,
)
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.features.macd import (
    MACD_DEFINITION_VERSION,
    MACD_HISTOGRAM_IDENTIFIER,
    MACD_IDENTIFIER,
    MACD_LINE_IDENTIFIER,
    MACD_SIGNAL_IDENTIFIER,
    MACD_SIGNAL_MINIMUM_OBSERVATIONS,
    MACD_SIGNAL_PERIOD,
    MACD_SLOW_PERIOD,
    MovingAverageConvergenceDivergence,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import _dependency_membership_rows


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000401")
_NONLINEAR_CLOSES = tuple(
    Decimal(100) + Decimal(index * index) / Decimal(10) + Decimal(index % 3) / 7
    for index in range(38)
)
_EXPECTED_LINES = tuple(
    Decimal(value)
    for value in (
        "20.116842423936333414",
        "20.731213806447114467",
        "21.376305757913428803",
        "22.088257506123066201",
        "22.860433291687618964",
        "23.652759809817252964",
        "24.501987027043407774",
        "25.402071176983632678",
        "26.313509514663482587",
        "27.273599271937855222",
        "28.276819460435579020",
        "29.284164970393219273",
        "30.333405299045008995",
    )
)
_EXPECTED_SIGNALS = tuple(
    Decimal(value)
    for value in (
        "23.004820034957259761",
        "23.858575882353378853",
        "24.742224597969818887",
        "25.650612672454498964",
        "26.587171197772600970",
    )
)
_EXPECTED_HISTOGRAMS = tuple(
    Decimal(value)
    for value in (
        "3.308689479706222826",
        "3.415023389584476369",
        "3.534594862465760133",
        "3.633552297938720309",
        "3.746234101272408025",
    )
)


class MovingAverageConvergenceDivergenceFormulaTests(unittest.TestCase):
    feature = MovingAverageConvergenceDivergence()

    def test_metadata_declares_exact_outputs_and_registered_ema_dependencies(
        self,
    ) -> None:
        metadata = self.feature.metadata

        self.assertEqual(metadata.identifier, MACD_IDENTIFIER)
        self.assertEqual(metadata.definition_version, MACD_DEFINITION_VERSION)
        self.assertEqual(metadata.category, "momentum")
        self.assertEqual(metadata.required_inputs, (CandleField.CLOSE,))
        self.assertEqual(metadata.history_type, FeatureHistoryType.RECURSIVE)
        self.assertIsNone(metadata.maximum_lookback_observations)
        self.assertEqual(
            tuple(output.identifier for output in metadata.outputs),
            (
                MACD_LINE_IDENTIFIER,
                MACD_SIGNAL_IDENTIFIER,
                MACD_HISTOGRAM_IDENTIFIER,
            ),
        )
        self.assertEqual(
            tuple(output.minimum_observations for output in metadata.outputs),
            (MACD_SLOW_PERIOD,) + (MACD_SIGNAL_MINIMUM_OBSERVATIONS,) * 2,
        )
        self.assertEqual(
            metadata.dependencies,
            (EMA_12_IDENTIFIER, EMA_26_IDENTIFIER),
        )
        self.assertEqual(
            tuple(
                (
                    contract.identifier,
                    contract.definition_version,
                    contract.output_names,
                )
                for contract in metadata.dependency_contracts
            ),
            (
                (EMA_12_IDENTIFIER, EMA_DEFINITION_VERSION, (EMA_12_IDENTIFIER,)),
                (EMA_26_IDENTIFIER, EMA_DEFINITION_VERSION, (EMA_26_IDENTIFIER,)),
            ),
        )

    def test_approved_nonlinear_fixture_matches_line_signal_and_histogram(self) -> None:
        candles = _candles_from_closes(_NONLINEAR_CLOSES)

        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            _ema_inputs(candles, CandleTimeframe.MINUTE_5),
        )

        self.assertEqual(_values(values, MACD_LINE_IDENTIFIER), _EXPECTED_LINES)
        self.assertEqual(_values(values, MACD_SIGNAL_IDENTIFIER), _EXPECTED_SIGNALS)
        self.assertEqual(
            _values(values, MACD_HISTOGRAM_IDENTIFIER),
            _EXPECTED_HISTOGRAMS,
        )
        self.assertEqual(
            _output(values, MACD_LINE_IDENTIFIER)[0].timestamp,
            candles[25].timestamp,
        )
        self.assertEqual(
            _output(values, MACD_SIGNAL_IDENTIFIER)[0].timestamp,
            candles[33].timestamp,
        )

    def test_exact_per_output_warmup_boundaries(self) -> None:
        for count in (1, 11, 12, 25):
            with self.subTest(count=count):
                candles = _candles_from_closes(
                    tuple(Decimal(100 + index) for index in range(count))
                )
                self.assertEqual(
                    self.feature.compute(
                        candles,
                        CandleTimeframe.MINUTE_5,
                        _ema_inputs(candles, CandleTimeframe.MINUTE_5),
                    ),
                    (),
                )

        candles_33 = _candles_from_closes(
            tuple(Decimal(100 + index) for index in range(33))
        )
        values_33 = self.feature.compute(
            candles_33,
            CandleTimeframe.MINUTE_5,
            _ema_inputs(candles_33, CandleTimeframe.MINUTE_5),
        )
        self.assertEqual(len(_output(values_33, MACD_LINE_IDENTIFIER)), 8)
        self.assertEqual(_output(values_33, MACD_SIGNAL_IDENTIFIER), ())
        self.assertEqual(_output(values_33, MACD_HISTOGRAM_IDENTIFIER), ())

        candles_34 = _candles_from_closes(
            tuple(Decimal(100 + index) for index in range(34))
        )
        values_34 = self.feature.compute(
            candles_34,
            CandleTimeframe.MINUTE_5,
            _ema_inputs(candles_34, CandleTimeframe.MINUTE_5),
        )
        self.assertEqual(len(_output(values_34, MACD_LINE_IDENTIFIER)), 9)
        self.assertEqual(len(_output(values_34, MACD_SIGNAL_IDENTIFIER)), 1)
        self.assertEqual(len(_output(values_34, MACD_HISTOGRAM_IDENTIFIER)), 1)

    def test_constant_close_edge_produces_exact_zero_outputs(self) -> None:
        candles = _candles_from_closes((Decimal(100),) * 38)

        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            _ema_inputs(candles, CandleTimeframe.MINUTE_5),
        )

        self.assertTrue(
            all(value.value == Decimal("0.000000000000000000") for value in values)
        )

    def test_fast_and_slow_values_are_consumed_without_internal_recalculation(
        self,
    ) -> None:
        candles = _candles_from_closes(_NONLINEAR_CLOSES)
        dependencies = _ema_inputs(candles, CandleTimeframe.MINUTE_5)
        original = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            dependencies,
        )
        fast = dependencies[0]
        changed_fast = replace(
            fast,
            values=fast.values[:-1]
            + (replace(fast.values[-1], value=fast.values[-1].value + Decimal(1)),),
        )

        with patch(
            "app.features.macd.exponential_moving_average",
            wraps=__import__(
                "app.features.macd", fromlist=["exponential_moving_average"]
            ).exponential_moving_average,
        ) as signal_ema:
            changed = self.feature.compute(
                candles,
                CandleTimeframe.MINUTE_5,
                (changed_fast, dependencies[1]),
            )

        signal_ema.assert_called_once()
        self.assertEqual(signal_ema.call_args.args[1], MACD_SIGNAL_PERIOD)
        self.assertEqual(len(signal_ema.call_args.args[0]), len(_EXPECTED_LINES))
        self.assertEqual(
            _output(original, MACD_LINE_IDENTIFIER)[:-1],
            _output(changed, MACD_LINE_IDENTIFIER)[:-1],
        )
        self.assertNotEqual(
            _output(original, MACD_LINE_IDENTIFIER)[-1],
            _output(changed, MACD_LINE_IDENTIFIER)[-1],
        )

    def test_dependency_validation_fails_closed(self) -> None:
        candles = _candles_from_closes(_NONLINEAR_CLOSES)
        fast, slow = _ema_inputs(candles, CandleTimeframe.MINUTE_5)
        invalid_dependencies = (
            (),
            (fast,),
            (slow, fast),
            (replace(fast, definition_version="2.0.0"), slow),
            (replace(fast, output_name="other"), slow),
            (replace(fast, values=fast.values[:-1]), slow),
            (
                replace(
                    fast,
                    values=fast.values[:1]
                    + (replace(fast.values[1], timestamp=fast.values[0].timestamp),)
                    + fast.values[2:],
                ),
                slow,
            ),
            (
                replace(
                    fast,
                    values=(replace(fast.values[0], value=Decimal("NaN")),)
                    + fast.values[1:],
                ),
                slow,
            ),
        )

        for dependencies in invalid_dependencies:
            with self.subTest(dependencies=dependencies):
                with self.assertRaises(FeatureComputationError):
                    self.feature.compute(
                        candles,
                        CandleTimeframe.MINUTE_5,
                        dependencies,
                    )

    def test_decimal_execution_is_ambient_context_independent(self) -> None:
        candles = _candles_from_closes(_NONLINEAR_CLOSES)
        dependencies = _ema_inputs(candles, CandleTimeframe.MINUTE_5)
        expected = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            dependencies,
        )

        with localcontext() as context:
            context.prec = 6
            actual = self.feature.compute(
                candles,
                CandleTimeframe.MINUTE_5,
                dependencies,
            )

        self.assertEqual(actual, expected)

    def test_outputs_and_provenance_are_immutable(self) -> None:
        candles = _candles_from_closes(_NONLINEAR_CLOSES)
        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            _ema_inputs(candles, CandleTimeframe.MINUTE_5),
        )

        with self.assertRaises(FrozenInstanceError):
            values[-1].value = Decimal(0)
        with self.assertRaises(FrozenInstanceError):
            values[-1].dependencies[0].timestamp = values[-1].timestamp


class MovingAverageConvergenceDivergencePipelineTests(unittest.TestCase):
    def test_registry_and_pipeline_integrate_macd_after_ema_dependencies(self) -> None:
        observations = _observations(_NONLINEAR_CLOSES)
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )

        self.assertEqual(INTRADAY_PIPELINE_VERSION, "2.6.0")
        self.assertLess(
            result.execution_order.index(EMA_12_IDENTIFIER),
            result.execution_order.index(MACD_IDENTIFIER),
        )
        self.assertLess(
            result.execution_order.index(EMA_26_IDENTIFIER),
            result.execution_order.index(MACD_IDENTIFIER),
        )
        self.assertEqual(
            next(
                definition
                for definition in INTRADAY_FEATURE_REGISTRY.definitions
                if definition.identifier == MACD_IDENTIFIER
            ),
            MovingAverageConvergenceDivergence.metadata,
        )
        self.assertEqual(
            tuple(
                name
                for name in INTRADAY_FEATURE_REGISTRY.output_names
                if name
                in {
                    MACD_LINE_IDENTIFIER,
                    MACD_SIGNAL_IDENTIFIER,
                    MACD_HISTOGRAM_IDENTIFIER,
                }
            ),
            (
                MACD_LINE_IDENTIFIER,
                MACD_SIGNAL_IDENTIFIER,
                MACD_HISTOGRAM_IDENTIFIER,
            ),
        )
        self.assertEqual(
            _pipeline_values(result.values, MACD_LINE_IDENTIFIER),
            _EXPECTED_LINES,
        )
        self.assertEqual(
            _pipeline_values(result.values, MACD_SIGNAL_IDENTIFIER),
            _EXPECTED_SIGNALS,
        )
        self.assertEqual(
            _pipeline_values(result.values, MACD_HISTOGRAM_IDENTIFIER),
            _EXPECTED_HISTOGRAMS,
        )

    def test_pipeline_retains_reconstructable_ordered_provenance(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(_observations(_NONLINEAR_CLOSES), CandleTimeframe.MINUTE_5)
        )
        memberships = tuple(
            membership
            for membership in result.dependency_memberships
            if membership.consumer_feature_identifier == MACD_IDENTIFIER
        )
        first_signal_timestamp = next(
            value.candle_timestamp
            for value in result.values
            if value.output_name == MACD_SIGNAL_IDENTIFIER
        )
        first_signal = tuple(
            membership
            for membership in memberships
            if membership.consumer_output_name == MACD_SIGNAL_IDENTIFIER
            and membership.consumer_candle_timestamp == first_signal_timestamp
        )
        later_signal = tuple(
            membership
            for membership in memberships
            if membership.consumer_output_name == MACD_SIGNAL_IDENTIFIER
            and membership.consumer_candle_timestamp > first_signal_timestamp
        )

        self.assertEqual(len(first_signal), 18)
        self.assertEqual(
            tuple(membership.dependency_ordinal for membership in first_signal),
            tuple(range(18)),
        )
        self.assertEqual(
            tuple(
                membership.dependency_feature_identifier for membership in first_signal
            ),
            (EMA_12_IDENTIFIER, EMA_26_IDENTIFIER) * 9,
        )
        self.assertTrue(
            any(
                membership.dependency_feature_identifier == MACD_IDENTIFIER
                and membership.dependency_output_name == MACD_SIGNAL_IDENTIFIER
                for membership in later_signal
            )
        )
        self.assertTrue(
            all(
                membership.dependency_available_at
                <= next(
                    value.available_at
                    for value in result.values
                    if value.output_name == membership.consumer_output_name
                    and value.candle_timestamp == membership.consumer_candle_timestamp
                )
                for membership in memberships
            )
        )

    def test_prefix_invariance_future_isolation_and_hashing(self) -> None:
        observations = _observations(_NONLINEAR_CLOSES)
        full = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )
        replay = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )
        prefix = run_intraday_feature_pipeline(
            _snapshot(observations[:-1], CandleTimeframe.MINUTE_5)
        )
        changed_last = replace(
            observations[-1],
            candle=replace(
                observations[-1].candle,
                open=observations[-1].candle.open + Decimal(5),
                high=observations[-1].candle.high + Decimal(5),
                low=observations[-1].candle.low + Decimal(5),
                close=observations[-1].candle.close + Decimal(5),
            ),
        )
        changed = run_intraday_feature_pipeline(
            _snapshot(observations[:-1] + (changed_last,), CandleTimeframe.MINUTE_5)
        )
        prefix_end = observations[-2].candle.timestamp

        self.assertEqual(full, replay)
        self.assertEqual(full.result_hash, replay.result_hash)
        self.assertEqual(
            _macd_pipeline_values(prefix.values),
            tuple(
                value
                for value in _macd_pipeline_values(full.values)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertEqual(
            _macd_memberships(prefix.dependency_memberships),
            tuple(
                membership
                for membership in _macd_memberships(full.dependency_memberships)
                if membership.consumer_candle_timestamp <= prefix_end
            ),
        )
        self.assertEqual(
            tuple(
                value
                for value in _macd_pipeline_values(full.values)
                if value.candle_timestamp <= prefix_end
            ),
            tuple(
                value
                for value in _macd_pipeline_values(changed.values)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertNotEqual(
            _macd_pipeline_values(full.values)[-3:],
            _macd_pipeline_values(changed.values)[-3:],
        )

    def test_macd_provenance_maps_to_immutable_persistence_rows(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(_observations(_NONLINEAR_CLOSES), CandleTimeframe.MINUTE_5)
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
        macd_result = replace(
            result,
            dependency_memberships=_macd_memberships(result.dependency_memberships),
        )

        rows = _dependency_membership_rows(
            UUID("00000000-0000-0000-0000-000000000402"),
            stored_values,
            macd_result,
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(len(rows), len(macd_result.dependency_memberships))
        self.assertTrue(
            all(row["dependency_feature_value_id"] is not None for row in rows)
        )


def _ema_inputs(
    candles: tuple[Candle, ...],
    timeframe: CandleTimeframe,
) -> tuple[FeatureDependencyInput, FeatureDependencyInput]:
    definitions = {
        definition.metadata.identifier: definition
        for definition in EMA_FEATURE_DEFINITIONS
    }
    return tuple(
        FeatureDependencyInput(
            definition_identifier=identifier,
            definition_version=EMA_DEFINITION_VERSION,
            output_name=identifier,
            values=definitions[identifier].compute(candles, timeframe),
        )
        for identifier in (EMA_12_IDENTIFIER, EMA_26_IDENTIFIER)
    )


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


def _observations(
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


def _output(values, output_name):
    return tuple(value for value in values if value.feature_name == output_name)


def _values(values, output_name):
    return tuple(value.value for value in _output(values, output_name))


def _pipeline_values(values, output_name):
    return tuple(value.value for value in values if value.output_name == output_name)


def _macd_pipeline_values(values):
    return tuple(
        value for value in values if value.feature_identifier == MACD_IDENTIFIER
    )


def _macd_memberships(memberships):
    return tuple(
        membership
        for membership in memberships
        if membership.consumer_feature_identifier == MACD_IDENTIFIER
    )


def _duration(timeframe: CandleTimeframe) -> timedelta:
    return {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]
