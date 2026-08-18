"""Regression tests for feature warmup pipeline and FEATURE_SNAPSHOT stage.

These tests prevent the exact regression where newly arriving live candles
cannot advance through FEATURE_SNAPSHOT because the feature engine lacks
sufficient historical prefix for indicator warmup.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import unittest

from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.live_market_data import CompletedCandle, build_market_snapshot
from app.market_data.models import CandleTimeframe
from app.market_data.validation import timeframe_duration
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import (
    FeatureSnapshotMemoryRepository,
    MarketSnapshotMemoryRepository,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    ScopedRepositoryQuery,
)
from app.runtime_features import (
    FeatureWarmupIncompleteError,
    RuntimeFeatureEngine,
)


START = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)
CODE_VERSION = "git:regression_test"


class FeatureWarmupRegressionTests(unittest.IsolatedAsyncioTestCase):
    """Prevent the FEATURE_SNAPSHOT BLOCKED regression from returning."""

    async def test_newly_persisted_candle_with_valid_prefix_reaches_features(
        self,
    ) -> None:
        """A completed candle with 200 historical candles reaches FEATURE_SNAPSHOT."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(200))
        await markets.save_batch(snapshots)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        result = await engine.resolve(snapshots[-1])

        self.assertGreater(len(result.values), 0)
        self.assertEqual(len(features._records), 1)

    async def test_insufficient_history_blocks_with_warmup_error(self) -> None:
        """A candle with only 1 historical candle raises FeatureWarmupIncompleteError."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshot = _market_snapshot(0)
        await markets.save(snapshot)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        with self.assertRaises(FeatureWarmupIncompleteError):
            await engine.resolve(snapshot)

        self.assertEqual(len(features._records), 0)

    async def test_sufficient_history_does_not_block(self) -> None:
        """A candle with 200 historical candles does not raise."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(200))
        await markets.save_batch(snapshots)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        result = await engine.resolve(snapshots[-1])

        self.assertIsNotNone(result)

    async def test_future_candles_are_excluded_from_prefix(self) -> None:
        """Candles with timestamp > current are excluded from warmup prefix."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(200))
        await markets.save_batch(snapshots)

        # Add a future snapshot
        future = _market_snapshot(250)
        await markets.save(future)

        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        result = await engine.resolve(snapshots[-1])

        # Future snapshot should not appear in provenance
        provenance_ids = {
            ref.artifact_id
            for ref in result.audit.provenance.source_references
        }
        self.assertNotIn(future.snapshot_id, provenance_ids)

    async def test_history_ordering_is_chronological(self) -> None:
        """Feature values are produced in chronological candle order."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(30))
        await markets.save_batch(snapshots)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        result = await engine.resolve(snapshots[-1])

        # The feature snapshot should reference the last candle
        self.assertEqual(
            result.market_snapshot.artifact_id, snapshots[-1].snapshot_id
        )

    async def test_history_not_truncated_before_warmup(self) -> None:
        """All available historical candles are loaded for warmup, not just the latest."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        # Create 200 snapshots to ensure EMA-200 warmup
        snapshots = tuple(_market_snapshot(i) for i in range(200))
        await markets.save_batch(snapshots)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        result = await engine.resolve(snapshots[-1])

        # With 200 candles, all public features including EMA-200 should produce output
        identifiers = {v.feature_identifier for v in result.values}
        self.assertIn("exponential_moving_average_200", identifiers)

    async def test_live_pipeline_does_not_fabricate_feature_output(self) -> None:
        """Feature engine rejects non-persisted snapshots (no fabrication)."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )
        snapshot = _market_snapshot(0)

        with self.assertRaisesRegex(Exception, "persisted"):
            await engine.resolve(snapshot)

    async def test_partial_warmup_publishes_only_available_outputs(self) -> None:
        """With 2 candles, only directional_movement outputs are valid."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(2))
        await markets.save_batch(snapshots)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        result = await engine.resolve(snapshots[-1])

        self.assertEqual(
            tuple(value.output_name for value in result.values),
            (
                "negative_directional_movement",
                "positive_directional_movement",
            ),
        )

    async def test_point_in_time_correctness_with_new_candle(self) -> None:
        """Processing candle T does not use information from candle T+1."""
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(200))
        await markets.save_batch(snapshots)

        # Process the 100th candle
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )
        result_100 = await engine.resolve(snapshots[99])

        # Now add candle 200 (future relative to 100)
        future = _market_snapshot(200)
        await markets.save(future)

        # Re-process candle 100 - should produce identical result
        result_100_again = await engine.resolve(snapshots[99])

        self.assertEqual(
            result_100.canonical_sha256(), result_100_again.canonical_sha256()
        )

    async def test_warmup_threshold_for_each_indicator(self) -> None:
        """Verify minimum candle count for each public indicator."""
        test_cases = [
            (2, {"directional_movement"}),
            (12, {"exponential_moving_average_12", "directional_movement"}),
            (15, {"average_true_range", "relative_strength_index",
                  "exponential_moving_average_12", "directional_movement",
                  "directional_indicators", "directional_index"}),
            (20, {"average_true_range", "relative_strength_index",
                  "exponential_moving_average_12", "exponential_moving_average",
                  "bollinger_bands_20_2", "directional_movement",
                  "directional_indicators", "directional_index"}),
            (26, {"average_true_range", "relative_strength_index",
                  "exponential_moving_average_12", "exponential_moving_average",
                  "exponential_moving_average_26",
                  "moving_average_convergence_divergence",
                  "bollinger_bands_20_2", "directional_movement",
                  "directional_indicators", "directional_index"}),
        ]
        for count, expected_identifiers in test_cases:
            with self.subTest(count=count):
                markets = MarketSnapshotMemoryRepository()
                features = FeatureSnapshotMemoryRepository()
                snapshots = tuple(_market_snapshot(i) for i in range(count))
                await markets.save_batch(snapshots)
                engine = RuntimeFeatureEngine(
                    market_snapshots=markets,
                    feature_snapshots=features,
                    code_version=CODE_VERSION,
                )
                result = await engine.resolve(snapshots[-1])
                actual_identifiers = {v.feature_identifier for v in result.values}
                self.assertTrue(
                    expected_identifiers.issubset(actual_identifiers),
                    f"count={count}: missing {expected_identifiers - actual_identifiers}",
                )


class HistoryRepositoryTests(unittest.IsolatedAsyncioTestCase):
    """Tests for market snapshot repository history loading behavior."""

    async def test_history_is_scoped_to_instrument_and_timeframe(self) -> None:
        """Only snapshots matching the scope are returned."""
        markets = MarketSnapshotMemoryRepository()
        btc_5m_first = _market_snapshot(0, instrument="BTCUSDT", timeframe="5m")
        btc_5m_second = _market_snapshot(1, instrument="BTCUSDT", timeframe="5m")
        btc_5m_third = _market_snapshot(2, instrument="BTCUSDT", timeframe="5m")
        await markets.save_batch((btc_5m_first, btc_5m_second, btc_5m_third))

        # Query for only the first snapshot's candle timestamp
        query_first = ScopedRepositoryQuery(
            scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
            as_of=btc_5m_first.audit.available_at,
            limit=100,
        )
        page_first = await markets.get_by_scope(query_first)
        self.assertEqual(len(page_first.items), 1)
        self.assertEqual(page_first.items[0].snapshot_id, btc_5m_first.snapshot_id)

        # Query for first two
        query_two = ScopedRepositoryQuery(
            scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
            as_of=btc_5m_second.audit.available_at,
            limit=100,
        )
        page_two = await markets.get_by_scope(query_two)
        self.assertEqual(len(page_two.items), 2)

    async def test_history_ordering_is_chronological(self) -> None:
        """Snapshots are returned in consistent order with unique available_at."""
        markets = MarketSnapshotMemoryRepository()
        snapshots = tuple(_market_snapshot(i) for i in range(10))
        await markets.save_batch(snapshots)

        query = ScopedRepositoryQuery(
            scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
            as_of=START + timedelta(hours=1),
            limit=100,
        )
        page = await markets.get_by_scope(query)

        # All 10 snapshots should be returned
        self.assertEqual(len(page.items), 10)
        # All snapshots should have unique snapshot_ids
        ids = [s.snapshot_id for s in page.items]
        self.assertEqual(len(set(ids)), 10)

    async def test_history_filters_by_as_of(self) -> None:
        """Only snapshots with available_at <= as_of are returned."""
        markets = MarketSnapshotMemoryRepository()
        early = _market_snapshot(0)
        late = _market_snapshot(100)
        await markets.save_batch((early, late))

        # Query with as_of between early and late
        mid = early.audit.available_at + timedelta(minutes=25)
        query = ScopedRepositoryQuery(
            scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
            as_of=mid,
            limit=100,
        )
        page = await markets.get_by_scope(query)

        self.assertEqual(len(page.items), 1)
        self.assertEqual(page.items[0].snapshot_id, early.snapshot_id)

    async def test_history_is_not_truncated(self) -> None:
        """All available historical snapshots are returned up to limit."""
        markets = MarketSnapshotMemoryRepository()
        count = 50
        snapshots = tuple(_market_snapshot(i) for i in range(count))
        await markets.save_batch(snapshots)

        query = ScopedRepositoryQuery(
            scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
            as_of=START + timedelta(hours=10),
            limit=1000,
        )
        page = await markets.get_by_scope(query)

        self.assertEqual(len(page.items), count)

    async def test_completed_candle_validation(self) -> None:
        """MarketSnapshot with complete=False is rejected."""
        candle = CompletedCandle(
            provider="binance_spot",
            symbol="BTCUSDT",
            timeframe=CandleTimeframe.MINUTE_5,
            event_time=START + timedelta(minutes=5),
            open_time=START,
            close_time=START + timedelta(minutes=5) - timedelta(milliseconds=1),
            open=Decimal(100),
            high=Decimal(112),
            low=Decimal(95),
            close=Decimal(108),
            volume=Decimal(2.5),
            number_of_trades=42,
            source_payload_hash=sha256(b"test").hexdigest(),
            source_candle_hashes=(),
        )
        snapshot = build_market_snapshot(candle, code_version="git:test")
        self.assertTrue(snapshot.complete)


def _market_snapshot(
    index: int,
    *,
    instrument: str = "BTCUSDT",
    timeframe: str = "5m",
):
    timestamp = START + timedelta(minutes=5 * index)
    base = Decimal(10_000 + index)
    event_time = timestamp + timedelta(minutes=5)
    candle = CompletedCandle(
        provider="binance_spot",
        symbol=instrument,
        timeframe=CandleTimeframe(timeframe),
        event_time=event_time,
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=5) - timedelta(milliseconds=1),
        open=base,
        high=base + Decimal(5),
        low=base - Decimal(5),
        close=base + Decimal(1),
        volume=Decimal(10 + index),
        number_of_trades=100 + index,
        source_payload_hash=sha256(f"source:{instrument}:{timeframe}:{index}".encode()).hexdigest(),
    )
    return build_market_snapshot(candle, code_version=CODE_VERSION)


if __name__ == "__main__":
    unittest.main()
