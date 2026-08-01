"""Runtime Feature Engine tests over immutable live market snapshots."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import unittest

from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.live_market_data import CompletedCandle, build_market_snapshot
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.persistence import (
    FeatureSnapshotMemoryRepository,
    MarketSnapshotMemoryRepository,
)
from app.opportunity_intelligence.repositories import EntityId
from app.opportunity_intelligence.services import (
    FeatureSnapshotService,
    ServiceContractError,
)
from app.runtime_features import (
    FeatureWarmupIncompleteError,
    RuntimeFeatureEngine,
)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
CODE_VERSION = "git:runtimefeatures123"
EXPECTED_DEFINITIONS = {
    "average_true_range",
    "exponential_moving_average_12",
    "exponential_moving_average",
    "exponential_moving_average_26",
    "exponential_moving_average_50",
    "exponential_moving_average_100",
    "exponential_moving_average_200",
    "relative_strength_index",
    "moving_average_convergence_divergence",
    "bollinger_bands_20_2",
    "directional_movement",
    "directional_indicators",
    "directional_index",
    "average_directional_index",
    "average_directional_movement_rating",
}


class RuntimeFeatureEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_approved_family_computes_after_warmup(self) -> None:
        markets, features, engine, snapshots = await _engine_with_history(200)

        result = await engine.resolve(snapshots[-1])

        self.assertEqual(
            {value.feature_identifier for value in result.values},
            EXPECTED_DEFINITIONS,
        )
        self.assertEqual(len(result.values), 23)
        self.assertEqual(
            result.registry_hash,
            INTRADAY_FEATURE_REGISTRY.configuration_hash,
        )
        self.assertEqual(result.market_snapshot.artifact_id, snapshots[-1].snapshot_id)
        self.assertEqual(
            tuple(
                (
                    value.feature_identifier,
                    value.definition_version,
                    value.output_name,
                    value.candle_timestamp,
                )
                for value in result.values
            ),
            tuple(
                sorted(
                    (
                        value.feature_identifier,
                        value.definition_version,
                        value.output_name,
                        value.candle_timestamp,
                    )
                    for value in result.values
                )
            ),
        )
        restored = await features.get_by_id(EntityId(result.snapshot_id))
        self.assertEqual(restored.canonical_json(), result.canonical_json())
        self.assertIsInstance(engine, FeatureSnapshotService)
        self.assertEqual(len(markets._records), 200)

    async def test_warmup_without_any_requested_output_persists_nothing(self) -> None:
        _, features, engine, snapshots = await _engine_with_history(1)

        with self.assertRaises(FeatureWarmupIncompleteError):
            await engine.resolve(snapshots[0])

        self.assertEqual(len(features._records), 0)

    async def test_partial_warmup_publishes_only_available_approved_outputs(self) -> None:
        _, _, engine, snapshots = await _engine_with_history(2)

        result = await engine.resolve(snapshots[-1])

        self.assertEqual(
            tuple(value.output_name for value in result.values),
            (
                "negative_directional_movement",
                "positive_directional_movement",
            ),
        )

    async def test_repeated_resolution_is_byte_identical_and_idempotent(self) -> None:
        _, features, engine, snapshots = await _engine_with_history(20)

        first = await engine.resolve(snapshots[-1])
        second = await engine.resolve(snapshots[-1])

        self.assertEqual(first.canonical_json(), second.canonical_json())
        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(len(features._records), 1)

    async def test_future_snapshot_cannot_change_prior_feature_snapshot(self) -> None:
        markets, _, engine, snapshots = await _engine_with_history(20)
        first = await engine.resolve(snapshots[-1])
        future = _market_snapshot(20)
        await markets.save(future)

        replayed = await engine.resolve(snapshots[-1])

        self.assertEqual(first.canonical_json(), replayed.canonical_json())
        self.assertNotIn(
            future.snapshot_id,
            tuple(
                reference.artifact_id
                for reference in replayed.audit.provenance.source_references
            ),
        )

    async def test_non_persisted_input_fails_closed(self) -> None:
        engine = RuntimeFeatureEngine(
            market_snapshots=MarketSnapshotMemoryRepository(),
            feature_snapshots=FeatureSnapshotMemoryRepository(),
            code_version=CODE_VERSION,
        )

        with self.assertRaisesRegex(ServiceContractError, "persisted"):
            await engine.resolve(_market_snapshot(1))

    async def test_open_candle_fails_before_computation(self) -> None:
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        open_snapshot = _premature_market_snapshot()
        await markets.save(open_snapshot)
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        with self.assertRaisesRegex(ServiceContractError, "before the candle closes"):
            await engine.resolve(open_snapshot)

        self.assertEqual(len(features._records), 0)

    async def test_gap_in_market_prefix_fails_closed(self) -> None:
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        first = _market_snapshot(0)
        third = _market_snapshot(2)
        await markets.save_batch((first, third))
        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version=CODE_VERSION,
        )

        with self.assertRaisesRegex(ValueError, "consecutive"):
            await engine.resolve(third)

        self.assertEqual(len(features._records), 0)


async def _engine_with_history(count: int):
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    snapshots = tuple(_market_snapshot(index) for index in range(count))
    await markets.save_batch(snapshots)
    engine = RuntimeFeatureEngine(
        market_snapshots=markets,
        feature_snapshots=features,
        code_version=CODE_VERSION,
    )
    return markets, features, engine, snapshots


def _market_snapshot(
    index: int,
):
    timestamp = START + timedelta(minutes=5 * index)
    base = Decimal(10_000 + index)
    event_time = timestamp + timedelta(minutes=5)
    candle = CompletedCandle(
        provider="binance_spot",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=event_time,
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=5) - timedelta(milliseconds=1),
        open=base,
        high=base + Decimal(5),
        low=base - Decimal(5),
        close=base + Decimal(1),
        volume=Decimal(10 + index),
        number_of_trades=100 + index,
        source_payload_hash=sha256(f"source:{index}".encode()).hexdigest(),
    )
    return build_market_snapshot(candle, code_version="git:live123456")


def _premature_market_snapshot():
    snapshot = _market_snapshot(0)
    premature_at = START + timedelta(minutes=1)
    source = replace(
        snapshot.candles[0].source_reference,
        available_at=premature_at,
    )
    candle = replace(
        snapshot.candles[0],
        available_at=premature_at,
        source_reference=source,
    )
    provenance = replace(
        snapshot.audit.provenance,
        source_references=(source,),
    )
    audit = replace(
        snapshot.audit,
        created_at=premature_at,
        evidence_cutoff=premature_at,
        available_at=premature_at,
        provenance=provenance,
    )
    return replace(snapshot, candles=(candle,), audit=audit)


if __name__ == "__main__":
    unittest.main()
