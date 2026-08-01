"""Focused tests for the statistical-volatility feature family."""

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
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.features.statistical_volatility import (
    BOLLINGER_IDENTIFIER,
    BOLLINGER_LOWER_IDENTIFIER,
    BOLLINGER_MIDDLE_IDENTIFIER,
    BOLLINGER_PERCENT_B_IDENTIFIER,
    BOLLINGER_UPPER_IDENTIFIER,
    BOLLINGER_WIDTH_IDENTIFIER,
    SMA_20_IDENTIFIER,
    STANDARD_DEVIATION_20_IDENTIFIER,
    STATISTICAL_DEFINITION_VERSION,
    STATISTICAL_PERIOD,
    BollingerBands20,
    RollingStandardDeviation20,
    SimpleMovingAverage20,
)
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.intraday_features import _dependency_membership_rows


_BATCH_ID = UUID("00000000-0000-0000-0000-000000000501")
_EXPECTED = {
    SMA_20_IDENTIFIER: (
        Decimal("10.500000000000000000"),
        Decimal("11.500000000000000000"),
    ),
    STANDARD_DEVIATION_20_IDENTIFIER: (
        Decimal("5.766281297335397945"),
        Decimal("5.766281297335397945"),
    ),
    BOLLINGER_MIDDLE_IDENTIFIER: (
        Decimal("10.500000000000000000"),
        Decimal("11.500000000000000000"),
    ),
    BOLLINGER_UPPER_IDENTIFIER: (
        Decimal("22.032562594670795890"),
        Decimal("23.032562594670795890"),
    ),
    BOLLINGER_LOWER_IDENTIFIER: (
        Decimal("-1.032562594670795890"),
        Decimal("-0.032562594670795890"),
    ),
    BOLLINGER_WIDTH_IDENTIFIER: (
        Decimal("2.196678589461103979"),
        Decimal("2.005663059942747111"),
    ),
    BOLLINGER_PERCENT_B_IDENTIFIER: (
        Decimal("0.911877235523956996"),
        Decimal("0.911877235523956996"),
    ),
}


class StatisticalVolatilityFormulaTests(unittest.TestCase):
    sma = SimpleMovingAverage20()
    deviation = RollingStandardDeviation20()
    bands = BollingerBands20()

    def test_metadata_and_dependency_graph_match_specification(self) -> None:
        self.assertEqual(self.sma.metadata.identifier, SMA_20_IDENTIFIER)
        self.assertEqual(self.sma.metadata.dependencies, ())
        self.assertEqual(
            self.deviation.metadata.dependencies,
            (SMA_20_IDENTIFIER,),
        )
        self.assertEqual(
            self.bands.metadata.dependencies,
            (SMA_20_IDENTIFIER, STANDARD_DEVIATION_20_IDENTIFIER),
        )
        self.assertEqual(
            tuple(output.identifier for output in self.bands.metadata.outputs),
            (
                BOLLINGER_MIDDLE_IDENTIFIER,
                BOLLINGER_UPPER_IDENTIFIER,
                BOLLINGER_LOWER_IDENTIFIER,
                BOLLINGER_WIDTH_IDENTIFIER,
                BOLLINGER_PERCENT_B_IDENTIFIER,
            ),
        )
        for definition in (self.sma, self.deviation, self.bands):
            self.assertEqual(definition.metadata.definition_version, "1.0.0")
            self.assertEqual(definition.metadata.required_inputs, (CandleField.CLOSE,))
            self.assertEqual(
                definition.metadata.history_type, FeatureHistoryType.BOUNDED
            )
            self.assertEqual(
                definition.metadata.maximum_lookback_observations,
                STATISTICAL_PERIOD,
            )
            self.assertTrue(
                all(
                    output.minimum_observations == STATISTICAL_PERIOD
                    for output in definition.metadata.outputs
                )
            )

    def test_fixed_population_dispersion_and_bollinger_fixture(self) -> None:
        candles = _candles(tuple(Decimal(index) for index in range(1, 22)))
        sma_values, deviation_values, band_values = _compute_family(candles)

        all_values = sma_values + deviation_values + band_values
        for identifier, expected in _EXPECTED.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(_values(all_values, identifier), expected)

    def test_all_outputs_begin_after_exactly_twenty_closes(self) -> None:
        for count in range(1, STATISTICAL_PERIOD):
            with self.subTest(count=count):
                candles = _candles(
                    tuple(Decimal(100 + index) for index in range(count))
                )
                sma_values, deviation_values, band_values = _compute_family(candles)
                self.assertEqual(sma_values, ())
                self.assertEqual(deviation_values, ())
                self.assertEqual(band_values, ())

        candles = _candles(
            tuple(Decimal(100 + index) for index in range(STATISTICAL_PERIOD))
        )
        sma_values, deviation_values, band_values = _compute_family(candles)
        self.assertEqual(len(sma_values), 1)
        self.assertEqual(len(deviation_values), 1)
        self.assertEqual(len(band_values), 5)
        self.assertEqual(sma_values[0].timestamp, candles[19].timestamp)

    def test_zero_dispersion_defines_zero_width_and_neutral_percent_b(self) -> None:
        candles = _candles((Decimal(100),) * STATISTICAL_PERIOD)
        sma_values, deviation_values, band_values = _compute_family(candles)
        all_values = sma_values + deviation_values + band_values

        self.assertEqual(
            _values(all_values, STANDARD_DEVIATION_20_IDENTIFIER),
            (Decimal("0.000000000000000000"),),
        )
        self.assertEqual(
            _values(all_values, BOLLINGER_MIDDLE_IDENTIFIER),
            (Decimal("100.000000000000000000"),),
        )
        self.assertEqual(
            _values(all_values, BOLLINGER_UPPER_IDENTIFIER),
            (Decimal("100.000000000000000000"),),
        )
        self.assertEqual(
            _values(all_values, BOLLINGER_LOWER_IDENTIFIER),
            (Decimal("100.000000000000000000"),),
        )
        self.assertEqual(
            _values(all_values, BOLLINGER_WIDTH_IDENTIFIER),
            (Decimal("0.000000000000000000"),),
        )
        self.assertEqual(
            _values(all_values, BOLLINGER_PERCENT_B_IDENTIFIER),
            (Decimal("0.500000000000000000"),),
        )

    def test_percent_b_is_not_clipped(self) -> None:
        closes = (Decimal(100),) * 19 + (Decimal(200),)
        _, _, band_values = _compute_family(_candles(closes))

        self.assertGreater(
            _values(band_values, BOLLINGER_PERCENT_B_IDENTIFIER)[0],
            Decimal(1),
        )

    def test_registered_dependencies_are_consumed_and_validated(self) -> None:
        candles = _candles(tuple(Decimal(index) for index in range(1, 22)))
        sma_values = self.sma.compute(candles, CandleTimeframe.MINUTE_5)
        sma_input = _input(SMA_20_IDENTIFIER, sma_values)
        original = self.deviation.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            (sma_input,),
        )
        changed_sma = replace(
            sma_input,
            values=(replace(sma_values[0], value=sma_values[0].value + Decimal(1)),)
            + sma_values[1:],
        )
        changed = self.deviation.compute(
            candles,
            CandleTimeframe.MINUTE_5,
            (changed_sma,),
        )
        self.assertNotEqual(original[0].value, changed[0].value)

        invalid_inputs = (
            (),
            (replace(sma_input, definition_version="2.0.0"),),
            (replace(sma_input, output_name="other"),),
            (replace(sma_input, values=sma_values[:-1]),),
            (
                replace(
                    sma_input,
                    values=(replace(sma_values[0], value=Decimal("NaN")),)
                    + sma_values[1:],
                ),
            ),
        )
        for dependency_inputs in invalid_inputs:
            with self.subTest(dependency_inputs=dependency_inputs):
                with self.assertRaises(FeatureComputationError):
                    self.deviation.compute(
                        candles,
                        CandleTimeframe.MINUTE_5,
                        dependency_inputs,
                    )

    def test_execution_is_ambient_decimal_context_independent(self) -> None:
        candles = _candles(tuple(Decimal(index) / 7 + 100 for index in range(24)))
        expected = _compute_family(candles)

        with localcontext() as context:
            context.prec = 6
            actual = _compute_family(candles)

        self.assertEqual(actual, expected)

    def test_outputs_and_dependency_memberships_are_immutable(self) -> None:
        values = sum(
            _compute_family(
                _candles(tuple(Decimal(100 + index) for index in range(20)))
            ),
            (),
        )

        with self.assertRaises(FrozenInstanceError):
            values[-1].value = Decimal(0)
        with self.assertRaises(FrozenInstanceError):
            values[-1].dependencies[0].timestamp = values[-1].timestamp


class StatisticalVolatilityPipelineTests(unittest.TestCase):
    def test_registry_and_pipeline_use_canonical_dependency_order(self) -> None:
        observations = _observations(tuple(Decimal(index) for index in range(1, 22)))
        result = run_intraday_feature_pipeline(
            _snapshot(observations, CandleTimeframe.MINUTE_5)
        )

        self.assertEqual(INTRADAY_PIPELINE_VERSION, "2.6.0")
        self.assertEqual(
            result.execution_order[-3:],
            (
                SMA_20_IDENTIFIER,
                STANDARD_DEVIATION_20_IDENTIFIER,
                BOLLINGER_IDENTIFIER,
            ),
        )
        self.assertEqual(
            tuple(
                definition.identifier
                for definition in INTRADAY_FEATURE_REGISTRY.definitions[-3:]
            ),
            result.execution_order[-3:],
        )
        for identifier, expected in _EXPECTED.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(_pipeline_values(result.values, identifier), expected)

    def test_pipeline_retains_exact_dependency_provenance(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(
                _observations(tuple(Decimal(index) for index in range(1, 22))),
                CandleTimeframe.MINUTE_5,
            )
        )
        statistical_memberships = _statistical_memberships(
            result.dependency_memberships
        )
        deviation_memberships = tuple(
            membership
            for membership in statistical_memberships
            if membership.consumer_feature_identifier
            == STANDARD_DEVIATION_20_IDENTIFIER
        )
        band_memberships = tuple(
            membership
            for membership in statistical_memberships
            if membership.consumer_feature_identifier == BOLLINGER_IDENTIFIER
        )

        self.assertEqual(len(deviation_memberships), 2)
        self.assertTrue(
            all(
                membership.dependency_feature_identifier == SMA_20_IDENTIFIER
                for membership in deviation_memberships
            )
        )
        self.assertEqual(len(band_memberships), 20)
        for output_name in (
            BOLLINGER_MIDDLE_IDENTIFIER,
            BOLLINGER_UPPER_IDENTIFIER,
            BOLLINGER_LOWER_IDENTIFIER,
            BOLLINGER_WIDTH_IDENTIFIER,
            BOLLINGER_PERCENT_B_IDENTIFIER,
        ):
            output_memberships = tuple(
                membership
                for membership in band_memberships
                if membership.consumer_output_name == output_name
            )
            self.assertEqual(
                tuple(
                    membership.dependency_feature_identifier
                    for membership in output_memberships
                ),
                (
                    SMA_20_IDENTIFIER,
                    STANDARD_DEVIATION_20_IDENTIFIER,
                )
                * 2,
            )

    def test_prefix_invariance_future_isolation_and_hashing(self) -> None:
        observations = _observations(
            tuple(Decimal(index * index) / 11 + 100 for index in range(24))
        )
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
            _statistical_values(prefix.values),
            tuple(
                value
                for value in _statistical_values(full.values)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertEqual(
            tuple(
                value
                for value in _statistical_values(full.values)
                if value.candle_timestamp <= prefix_end
            ),
            tuple(
                value
                for value in _statistical_values(changed.values)
                if value.candle_timestamp <= prefix_end
            ),
        )
        self.assertNotEqual(
            _statistical_values(full.values)[-7:],
            _statistical_values(changed.values)[-7:],
        )

    def test_provenance_maps_to_existing_immutable_persistence(self) -> None:
        result = run_intraday_feature_pipeline(
            _snapshot(
                _observations(tuple(Decimal(index) for index in range(1, 22))),
                CandleTimeframe.MINUTE_5,
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
        statistical_result = replace(
            result,
            dependency_memberships=_statistical_memberships(
                result.dependency_memberships
            ),
        )

        rows = _dependency_membership_rows(
            UUID("00000000-0000-0000-0000-000000000502"),
            stored_values,
            statistical_result,
            datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(len(rows), len(statistical_result.dependency_memberships))


def _compute_family(candles: tuple[Candle, ...]):
    timeframe = CandleTimeframe.MINUTE_5
    sma = SimpleMovingAverage20().compute(candles, timeframe)
    deviation = RollingStandardDeviation20().compute(
        candles,
        timeframe,
        (_input(SMA_20_IDENTIFIER, sma),),
    )
    bands = BollingerBands20().compute(
        candles,
        timeframe,
        (
            _input(SMA_20_IDENTIFIER, sma),
            _input(STANDARD_DEVIATION_20_IDENTIFIER, deviation),
        ),
    )
    return sma, deviation, bands


def _input(identifier: str, values) -> FeatureDependencyInput:
    return FeatureDependencyInput(
        definition_identifier=identifier,
        definition_version=STATISTICAL_DEFINITION_VERSION,
        output_name=identifier,
        values=values,
    )


def _candles(closes: tuple[Decimal, ...]) -> tuple[Candle, ...]:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return tuple(
        Candle(
            timestamp=start + timedelta(minutes=5 * index),
            open=close,
            high=close + Decimal(1),
            low=close - Decimal(1) if close > 1 else close / 2,
            close=close,
            volume=Decimal(10),
        )
        for index, close in enumerate(closes)
    )


def _observations(closes: tuple[Decimal, ...]):
    return tuple(
        SourceCandleObservation(
            candle=candle,
            ingestion_batch_id=_BATCH_ID,
            is_complete=True,
        )
        for candle in _candles(closes)
    )


def _snapshot(observations, timeframe):
    return build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
    )


def _values(values, identifier):
    return tuple(value.value for value in values if value.feature_name == identifier)


def _pipeline_values(values, identifier):
    return tuple(value.value for value in values if value.output_name == identifier)


def _statistical_values(values):
    identifiers = {
        SMA_20_IDENTIFIER,
        STANDARD_DEVIATION_20_IDENTIFIER,
        BOLLINGER_IDENTIFIER,
    }
    return tuple(value for value in values if value.feature_identifier in identifiers)


def _statistical_memberships(memberships):
    identifiers = {
        STANDARD_DEVIATION_20_IDENTIFIER,
        BOLLINGER_IDENTIFIER,
    }
    return tuple(
        membership
        for membership in memberships
        if membership.consumer_feature_identifier in identifiers
    )
