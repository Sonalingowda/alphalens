"""Isolated specification tests for approved Tier-A features."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.features.contracts import (
    FeatureAvailabilityRule,
    FeatureComputationError,
    FeatureValue,
    feature_available_at,
)
from app.features.registry import (
    INTRADAY_FEATURE_REGISTRY,
    TIER_A_FEATURE_REGISTRY,
)
from app.features.tier_a import (
    TIER_A_FEATURE_DEFINITIONS,
    CandleGeometry,
    TrueRange,
)
from app.market_data.models import Candle, CandleTimeframe


class CandleGeometryTests(unittest.TestCase):
    feature = CandleGeometry()

    def test_exact_up_candle_outputs(self) -> None:
        candle = _candle(
            _start(),
            open_price="100",
            high="110",
            low="90",
            close="105",
        )

        values = self.feature.compute(
            (candle,),
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(
            _values_by_name(values),
            {
                "candle_body_fraction": Decimal("0.050000000000000000"),
                "candle_range_fraction": Decimal("0.200000000000000000"),
                "upper_wick_fraction": Decimal("0.050000000000000000"),
                "lower_wick_fraction": Decimal("0.100000000000000000"),
            },
        )

    def test_exact_down_candle_outputs(self) -> None:
        values = self.feature.compute(
            (
                _candle(
                    _start(),
                    open_price="100",
                    high="104",
                    low="90",
                    close="95",
                ),
            ),
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(
            _values_by_name(values),
            {
                "candle_body_fraction": Decimal("-0.050000000000000000"),
                "candle_range_fraction": Decimal("0.140000000000000000"),
                "upper_wick_fraction": Decimal("0.040000000000000000"),
                "lower_wick_fraction": Decimal("0.050000000000000000"),
            },
        )

    def test_flat_candle_outputs_are_zero(self) -> None:
        candle = _candle(
            _start(),
            open_price="100",
            high="100",
            low="100",
            close="100",
        )

        values = self.feature.compute(
            (candle,),
            CandleTimeframe.MINUTE_10,
        )

        self.assertEqual(len(values), 4)
        self.assertTrue(all(value.value == 0 for value in values))

    def test_repeating_fraction_uses_approved_decimal_policy(self) -> None:
        candle = _candle(
            _start(),
            open_price="3",
            high="4",
            low="3",
            close="4",
        )

        values = _values_by_name(
            self.feature.compute(
                (candle,),
                CandleTimeframe.MINUTE_15,
            )
        )

        self.assertEqual(
            values["candle_body_fraction"],
            Decimal("0.333333333333333333"),
        )
        self.assertEqual(
            values["candle_range_fraction"],
            Decimal("0.333333333333333333"),
        )

    def test_warmup_and_output_order(self) -> None:
        self.assertEqual(
            self.feature.compute((), CandleTimeframe.MINUTE_5),
            (),
        )

        values = self.feature.compute(
            (_candle(_start()),),
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(
            tuple(value.feature_name for value in values),
            (
                "candle_body_fraction",
                "candle_range_fraction",
                "upper_wick_fraction",
                "lower_wick_fraction",
            ),
        )


class TrueRangeTests(unittest.TestCase):
    feature = TrueRange()

    def test_previous_close_inside_current_range(self) -> None:
        candles = (
            _candle(
                _start(),
                open_price="100",
                high="102",
                low="98",
                close="100",
            ),
            _candle(
                _start() + timedelta(minutes=5),
                open_price="100",
                high="110",
                low="95",
                close="105",
            ),
        )

        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].value, Decimal("15.000000000000000000"))
        self.assertEqual(values[0].timestamp, candles[1].timestamp)

    def test_previous_close_above_current_range(self) -> None:
        candles = (
            _candle(
                _start(),
                open_price="120",
                high="121",
                low="119",
                close="120",
            ),
            _candle(
                _start() + timedelta(minutes=10),
                open_price="105",
                high="110",
                low="100",
                close="105",
            ),
        )

        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_10,
        )

        self.assertEqual(values[0].value, Decimal("20.000000000000000000"))

    def test_previous_close_below_current_range(self) -> None:
        candles = (
            _candle(
                _start(),
                open_price="90",
                high="91",
                low="89",
                close="90",
            ),
            _candle(
                _start() + timedelta(minutes=15),
                open_price="105",
                high="110",
                low="100",
                close="105",
            ),
        )

        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_15,
        )

        self.assertEqual(values[0].value, Decimal("20.000000000000000000"))

    def test_flat_candle_and_unchanged_previous_close_is_zero(self) -> None:
        candles = (
            _candle(
                _start(),
                open_price="100",
                high="100",
                low="100",
                close="100",
            ),
            _candle(
                _start() + timedelta(minutes=5),
                open_price="100",
                high="100",
                low="100",
                close="100",
            ),
        )

        values = self.feature.compute(
            candles,
            CandleTimeframe.MINUTE_5,
        )

        self.assertEqual(values[0].value, Decimal("0E-18"))

    def test_warmup_omits_first_observation(self) -> None:
        candle = _candle(_start())

        self.assertEqual(
            self.feature.compute((), CandleTimeframe.MINUTE_5),
            (),
        )
        self.assertEqual(
            self.feature.compute((candle,), CandleTimeframe.MINUTE_5),
            (),
        )


class TierAIntegrityTests(unittest.TestCase):
    def test_registry_matches_approved_specification_exactly(self) -> None:
        self.assertEqual(
            tuple(
                definition.metadata.identifier
                for definition in TIER_A_FEATURE_DEFINITIONS
            ),
            ("candle_geometry", "true_range"),
        )
        self.assertEqual(
            tuple(
                definition.identifier
                for definition in TIER_A_FEATURE_REGISTRY.definitions
            ),
            ("candle_geometry", "true_range"),
        )
        self.assertEqual(
            TIER_A_FEATURE_REGISTRY.output_names,
            (
                "candle_body_fraction",
                "candle_range_fraction",
                "upper_wick_fraction",
                "lower_wick_fraction",
                "true_range",
            ),
        )
        self.assertTrue(
            all(
                definition.definition_version == "1.0.0"
                for definition in INTRADAY_FEATURE_REGISTRY.definitions
            )
        )

    def test_availability_is_declared_and_exact_for_every_timeframe(
        self,
    ) -> None:
        timestamp = _start()
        durations = {
            CandleTimeframe.MINUTE_5: timedelta(minutes=5),
            CandleTimeframe.MINUTE_10: timedelta(minutes=10),
            CandleTimeframe.MINUTE_15: timedelta(minutes=15),
        }

        for definition in INTRADAY_FEATURE_REGISTRY.definitions:
            self.assertEqual(
                definition.availability_rule,
                FeatureAvailabilityRule.CANDLE_CLOSE,
            )
            for timeframe, duration in durations.items():
                with self.subTest(
                    feature=definition.identifier,
                    timeframe=timeframe,
                ):
                    self.assertEqual(
                        feature_available_at(
                            timestamp,
                            timeframe,
                            definition.availability_rule,
                        ),
                        timestamp + duration,
                    )

    def test_identical_inputs_produce_identical_outputs(self) -> None:
        candles = _candles(8, CandleTimeframe.MINUTE_5)

        for definition in TIER_A_FEATURE_DEFINITIONS:
            with self.subTest(feature=definition.metadata.identifier):
                first = definition.compute(
                    candles,
                    CandleTimeframe.MINUTE_5,
                )
                second = definition.compute(
                    candles,
                    CandleTimeframe.MINUTE_5,
                )
                self.assertEqual(first, second)

    def test_every_feature_is_prefix_invariant(self) -> None:
        candles = _candles(8, CandleTimeframe.MINUTE_5)

        for definition in TIER_A_FEATURE_DEFINITIONS:
            full = definition.compute(
                candles,
                CandleTimeframe.MINUTE_5,
            )
            for prefix_length in range(1, len(candles) + 1):
                with self.subTest(
                    feature=definition.metadata.identifier,
                    prefix_length=prefix_length,
                ):
                    prefix = candles[:prefix_length]
                    expected_end = prefix[-1].timestamp
                    expected = tuple(
                        value for value in full if value.timestamp <= expected_end
                    )
                    self.assertEqual(
                        definition.compute(
                            prefix,
                            CandleTimeframe.MINUTE_5,
                        ),
                        expected,
                    )

    def test_future_mutation_does_not_change_prior_outputs(self) -> None:
        candles = _candles(8, CandleTimeframe.MINUTE_5)
        changed = candles[:-1] + (
            replace(
                candles[-1],
                open=Decimal("200"),
                high=Decimal("220"),
                low=Decimal("190"),
                close=Decimal("215"),
            ),
        )
        prior_timestamp = candles[-2].timestamp

        for definition in TIER_A_FEATURE_DEFINITIONS:
            original = definition.compute(
                candles,
                CandleTimeframe.MINUTE_5,
            )
            recomputed = definition.compute(
                changed,
                CandleTimeframe.MINUTE_5,
            )
            self.assertEqual(
                tuple(
                    value for value in original if value.timestamp <= prior_timestamp
                ),
                tuple(
                    value for value in recomputed if value.timestamp <= prior_timestamp
                ),
            )

    def test_missing_invalid_and_discontinuous_input_fails_closed(
        self,
    ) -> None:
        candles = _candles(3, CandleTimeframe.MINUTE_5)
        invalid_cases = (
            candles[:1] + (replace(candles[1], close=None),) + candles[2:],
            candles[:1] + (replace(candles[1], open=Decimal("0")),) + candles[2:],
            candles[:1]
            + (
                replace(
                    candles[1],
                    high=Decimal("90"),
                    low=Decimal("110"),
                ),
            )
            + candles[2:],
            candles[:1]
            + (
                replace(
                    candles[1],
                    timestamp=candles[1].timestamp + timedelta(minutes=5),
                ),
            )
            + candles[2:],
        )

        for definition in TIER_A_FEATURE_DEFINITIONS:
            for invalid in invalid_cases:
                with self.subTest(
                    feature=definition.metadata.identifier,
                    invalid=invalid,
                ):
                    with self.assertRaises(FeatureComputationError):
                        definition.compute(
                            invalid,
                            CandleTimeframe.MINUTE_5,
                        )

    def test_unsupported_timeframe_is_rejected(self) -> None:
        candle = _candle(_start())

        for definition in TIER_A_FEATURE_DEFINITIONS:
            with self.assertRaises(FeatureComputationError):
                definition.compute((candle,), CandleTimeframe.DAY_1)

    def test_no_duplicate_output_identity_is_emitted(self) -> None:
        candles = _candles(8, CandleTimeframe.MINUTE_5)

        for definition in TIER_A_FEATURE_DEFINITIONS:
            values = definition.compute(
                candles,
                CandleTimeframe.MINUTE_5,
            )
            identities = tuple(
                (value.timestamp, value.feature_name) for value in values
            )
            self.assertEqual(len(identities), len(set(identities)))


def _start() -> datetime:
    return datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)


def _candles(
    count: int,
    timeframe: CandleTimeframe,
) -> tuple[Candle, ...]:
    durations = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }
    duration = durations[timeframe]
    results: list[Candle] = []
    for index in range(count):
        open_price = Decimal(100 + index)
        close = open_price + Decimal("0.5")
        results.append(
            Candle(
                timestamp=_start() + duration * index,
                open=open_price,
                high=close + Decimal("1"),
                low=open_price - Decimal("1"),
                close=close,
                volume=Decimal(10 + index),
            )
        )
    return tuple(results)


def _candle(
    timestamp: datetime,
    *,
    open_price: str = "100",
    high: str = "105",
    low: str = "95",
    close: str = "102",
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def _values_by_name(
    values: tuple[FeatureValue, ...],
) -> dict[str, Decimal]:
    return {value.feature_name: value.value for value in values}


if __name__ == "__main__":
    unittest.main()
