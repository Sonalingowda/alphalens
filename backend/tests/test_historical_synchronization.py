"""P1-05 deterministic multi-timeframe synchronization tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.market_data.coverage import (
    CoverageBatchEvidence,
    CoverageObservation,
    build_historical_coverage_snapshot,
)
from app.market_data.history import (
    TEN_MINUTE_DERIVATION,
    aggregate_btc_usd_10m_candle,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.synchronization import (
    CoverageSnapshotReference,
    HistoricalSynchronizationError,
    build_synchronized_coverage_snapshot,
    verify_synchronized_coverage_snapshot,
)
from app.persistence.models import (
    SynchronizedCoverageSnapshotRecord,
    TenMinuteDerivationRecord,
    TenMinuteDerivationSourceRecord,
)
from app.persistence.synchronization import (
    _synchronization_record,
    build_derivations_from_coverage,
    persist_synchronized_coverage_snapshot,
)


_START = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
_AS_OF = datetime(2026, 8, 1, 12, 40, tzinfo=timezone.utc)
_FIVE_BATCH = UUID("00000000-0000-0000-0000-000000000701")
_TEN_BATCH = UUID("00000000-0000-0000-0000-000000000702")
_FIFTEEN_BATCH = UUID("00000000-0000-0000-0000-000000000703")
_FIVE_SNAPSHOT = UUID("00000000-0000-0000-0000-000000000711")
_TEN_SNAPSHOT = UUID("00000000-0000-0000-0000-000000000712")
_FIFTEEN_SNAPSHOT = UUID("00000000-0000-0000-0000-000000000713")


class HistoricalSynchronizationTests(unittest.TestCase):
    def test_utc_boundaries_and_shared_source_provenance_are_exact(self) -> None:
        start = datetime(2026, 8, 1, 23, 50, tzinfo=timezone.utc)
        synchronized = _synchronized(start=start, five_count=6)

        self.assertEqual(
            tuple(item.derived_candle.timestamp for item in synchronized.derivations),
            (
                start,
                datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 8, 2, 0, 10, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            tuple(
                member.ordinal
                for evidence in synchronized.derivations
                for member in evidence.source_members
            ),
            (0, 1, 0, 1, 0, 1),
        )
        self.assertEqual(
            tuple(
                member.candle_id
                for evidence in synchronized.derivations
                for member in evidence.source_members
            ),
            (1, 2, 3, 4, 5, 6),
        )
        self.assertTrue(
            all(
                len(value) == 64
                for evidence in synchronized.derivations
                for value in (
                    evidence.derived_candle_hash,
                    evidence.source_membership_hash,
                    evidence.result_hash,
                )
            )
        )
        verify_synchronized_coverage_snapshot(synchronized)

    def test_odd_complete_source_member_is_reported_not_fabricated(self) -> None:
        synchronized = _synchronized(five_count=5)

        self.assertEqual(len(synchronized.derivations), 2)
        self.assertEqual(
            synchronized.differences.unpaired_five_minute_timestamps,
            (_START + timedelta(minutes=20),),
        )
        self.assertNotIn(
            _START + timedelta(minutes=20),
            tuple(item.derived_candle.timestamp for item in synchronized.derivations),
        )

    def test_source_gap_is_reported_and_affected_pair_is_absent(self) -> None:
        five_timestamps = (
            _START,
            _START + timedelta(minutes=5),
            _START + timedelta(minutes=10),
            _START + timedelta(minutes=20),
        )
        synchronized = _synchronized(five_timestamps=five_timestamps)

        self.assertEqual(len(synchronized.derivations), 1)
        self.assertEqual(
            synchronized.five_minute.snapshot.gap_timestamps,
            (_START + timedelta(minutes=15),),
        )
        self.assertEqual(
            synchronized.differences.unpaired_five_minute_timestamps,
            (
                _START + timedelta(minutes=10),
                _START + timedelta(minutes=20),
            ),
        )

    def test_native_15m_divergence_is_reported_without_reconciliation(self) -> None:
        native_timestamps = (_START, _START + timedelta(minutes=30))
        synchronized = _synchronized(
            five_count=6,
            fifteen_timestamps=native_timestamps,
            as_of=_START + timedelta(minutes=45),
        )

        self.assertEqual(
            synchronized.differences.missing_native_fifteen_minute_timestamps,
            (_START + timedelta(minutes=15),),
        )
        self.assertEqual(
            synchronized.differences.native_fifteen_minute_without_complete_five_minute,
            (_START + timedelta(minutes=30),),
        )
        self.assertEqual(
            tuple(
                item.candle.timestamp
                for item in synchronized.fifteen_minute.snapshot.observations
            ),
            native_timestamps,
        )

    def test_repeated_synchronization_is_deterministic(self) -> None:
        first = _synchronized()
        second = _synchronized()

        self.assertEqual(first, second)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.source_provenance_hash, second.source_provenance_hash)
        self.assertEqual(len(first.result_hash), 64)

    def test_missing_or_modified_derivation_fails_closed(self) -> None:
        five, ten, fifteen = _coverage_sets()
        derivations = build_derivations_from_coverage(five.snapshot, ten.snapshot)

        with self.assertRaisesRegex(
            HistoricalSynchronizationError,
            "Every synchronized 10m candle",
        ):
            build_synchronized_coverage_snapshot(
                as_of=_AS_OF,
                five_minute=five,
                ten_minute=ten,
                fifteen_minute=fifteen,
                derivations=derivations[:-1],
            )

        corrupted = replace(
            derivations[0],
            source_membership_hash="0" * 64,
        )
        with self.assertRaisesRegex(
            HistoricalSynchronizationError,
            "integrity verification failed",
        ):
            build_synchronized_coverage_snapshot(
                as_of=_AS_OF,
                five_minute=five,
                ten_minute=ten,
                fifteen_minute=fifteen,
                derivations=(corrupted,) + derivations[1:],
            )

    def test_point_in_time_membership_excludes_late_evidence(self) -> None:
        five, ten, fifteen = _coverage_sets()
        derivations = build_derivations_from_coverage(five.snapshot, ten.snapshot)
        cutoff = _START + timedelta(minutes=29)

        with self.assertRaisesRegex(
            HistoricalSynchronizationError,
            "unavailable at the as-of cutoff|incomplete interval",
        ):
            build_synchronized_coverage_snapshot(
                as_of=cutoff,
                five_minute=five,
                ten_minute=ten,
                fifteen_minute=fifteen,
                derivations=derivations,
            )

    def test_schema_and_migration_preserve_immutable_memberships(self) -> None:
        self.assertEqual(
            TenMinuteDerivationRecord.__table__.name,
            "ten_minute_derivations",
        )
        self.assertEqual(
            tuple(
                column.name
                for column in TenMinuteDerivationSourceRecord.__table__.primary_key
            ),
            ("derived_candle_id", "ordinal"),
        )
        self.assertIn(
            "uq_synchronized_coverage_result_hash",
            {
                item.name
                for item in SynchronizedCoverageSnapshotRecord.__table__.constraints
            },
        )

        migration_path = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20260801_0031_create_synchronized_coverage.py"
        )
        spec = importlib.util.spec_from_file_location(
            "synchronized_coverage_migration",
            migration_path,
        )
        if spec is None or spec.loader is None:
            self.fail("Synchronization migration could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mocked_op = MagicMock()
        with patch.object(module, "op", mocked_op):
            module.upgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.create_table.call_args_list],
            [
                "ten_minute_derivations",
                "ten_minute_derivation_sources",
                "synchronized_coverage_snapshots",
            ],
        )
        mocked_op.reset_mock()
        with patch.object(module, "op", mocked_op):
            module.downgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.drop_table.call_args_list],
            [
                "synchronized_coverage_snapshots",
                "ten_minute_derivation_sources",
                "ten_minute_derivations",
            ],
        )
        self.assertEqual(module.down_revision, "20260801_0030")


class HistoricalSynchronizationPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_snapshot_is_reused_after_verification(self) -> None:
        snapshot = _synchronized()
        created_session = _FakeSession()

        created = await persist_synchronized_coverage_snapshot(
            created_session,
            snapshot,
        )

        self.assertFalse(created.reused)
        self.assertEqual(created_session.flush_count, 1)
        existing = _synchronization_record(created.synchronization_id, snapshot)
        repeated = await persist_synchronized_coverage_snapshot(
            _FakeSession(existing),
            snapshot,
        )
        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.synchronization_id, created.synchronization_id)

    async def test_stored_hash_collision_fails_closed(self) -> None:
        snapshot = _synchronized()
        existing = _synchronization_record(
            UUID("00000000-0000-0000-0000-000000000799"),
            snapshot,
        )
        existing.source_provenance_hash = "f" * 64

        with self.assertRaisesRegex(
            HistoricalSynchronizationError,
            "conflicts with its result hash",
        ):
            await persist_synchronized_coverage_snapshot(
                _FakeSession(existing),
                snapshot,
            )


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeSession:
    def __init__(
        self,
        existing: SynchronizedCoverageSnapshotRecord | None = None,
    ) -> None:
        self.existing = existing
        self.added: list[object] = []
        self.flush_count = 0

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def scalar(self, statement):
        del statement
        return self.existing

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1


def _synchronized(
    *,
    start: datetime = _START,
    five_count: int = 6,
    five_timestamps: tuple[datetime, ...] | None = None,
    fifteen_timestamps: tuple[datetime, ...] | None = None,
    as_of: datetime | None = None,
):
    five, ten, fifteen = _coverage_sets(
        start=start,
        five_count=five_count,
        five_timestamps=five_timestamps,
        fifteen_timestamps=fifteen_timestamps,
    )
    derivations = build_derivations_from_coverage(five.snapshot, ten.snapshot)
    return build_synchronized_coverage_snapshot(
        as_of=as_of or start + timedelta(minutes=40),
        five_minute=five,
        ten_minute=ten,
        fifteen_minute=fifteen,
        derivations=derivations,
    )


def _coverage_sets(
    *,
    start: datetime = _START,
    five_count: int = 6,
    five_timestamps: tuple[datetime, ...] | None = None,
    fifteen_timestamps: tuple[datetime, ...] | None = None,
) -> tuple[
    CoverageSnapshotReference,
    CoverageSnapshotReference,
    CoverageSnapshotReference,
]:
    source_timestamps = five_timestamps or tuple(
        start + timedelta(minutes=5 * index) for index in range(five_count)
    )
    five_candles = tuple(
        _five_candle(timestamp, index)
        for index, timestamp in enumerate(source_timestamps)
    )
    five = _snapshot(
        CandleTimeframe.MINUTE_5,
        five_candles,
        _FIVE_BATCH,
        candle_id_start=1,
        retrieved_at=max(source_timestamps) + timedelta(minutes=6),
    )
    by_timestamp = {candle.timestamp: candle for candle in five_candles}
    derived_candles = tuple(
        aggregate_btc_usd_10m_candle(
            candle,
            by_timestamp[timestamp + timedelta(minutes=5)],
            timestamp,
        )
        for timestamp, candle in sorted(by_timestamp.items())
        if timestamp.minute % 10 == 0
        and timestamp + timedelta(minutes=5) in by_timestamp
    )
    ten = _snapshot(
        CandleTimeframe.MINUTE_10,
        derived_candles,
        _TEN_BATCH,
        candle_id_start=101,
        retrieved_at=max(source_timestamps) + timedelta(minutes=6),
        derived=True,
    )
    native_timestamps = fifteen_timestamps or tuple(
        timestamp
        for timestamp in source_timestamps
        if timestamp.minute % 15 == 0
        and timestamp + timedelta(minutes=10) <= max(source_timestamps)
    )
    fifteen = _snapshot(
        CandleTimeframe.MINUTE_15,
        tuple(_native_fifteen_candle(timestamp) for timestamp in native_timestamps),
        _FIFTEEN_BATCH,
        candle_id_start=201,
        retrieved_at=max(native_timestamps) + timedelta(minutes=15),
    )
    return (
        CoverageSnapshotReference(_FIVE_SNAPSHOT, five),
        CoverageSnapshotReference(_TEN_SNAPSHOT, ten),
        CoverageSnapshotReference(_FIFTEEN_SNAPSHOT, fifteen),
    )


def _snapshot(
    timeframe: CandleTimeframe,
    candles: tuple[Candle, ...],
    batch_id: UUID,
    *,
    candle_id_start: int,
    retrieved_at: datetime,
    derived: bool = False,
):
    duration = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]
    observations = tuple(
        CoverageObservation(
            candle_id=candle_id_start + index,
            ingestion_batch_id=batch_id,
            provider="kraken",
            is_complete=True,
            candle=candle,
        )
        for index, candle in enumerate(candles)
    )
    first = candles[0].timestamp
    last = candles[-1].timestamp
    if first is None or last is None:
        raise AssertionError("Test candles require timestamps.")
    batch = CoverageBatchEvidence(
        ingestion_batch_id=batch_id,
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=first,
        requested_end_exclusive=last + duration,
        retrieved_at=retrieved_at,
        validation_passed=True,
        validation_issues=(),
        source_timeframe=(CandleTimeframe.MINUTE_5 if derived else None),
        derivation_method=(TEN_MINUTE_DERIVATION if derived else None),
        source_ingestion_batch_id=(_FIVE_BATCH if derived else None),
    )
    return build_historical_coverage_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
        batches=(batch,),
    )


def _five_candle(timestamp: datetime, index: int) -> Candle:
    base = Decimal("100") + Decimal(index)
    return Candle(
        timestamp=timestamp,
        open=base,
        high=base + Decimal("2"),
        low=base - Decimal("1"),
        close=base + Decimal("1"),
        volume=Decimal("1.123456789012345678") + Decimal(index),
    )


def _native_fifteen_candle(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("9.000000000000000001"),
    )


if __name__ == "__main__":
    unittest.main()
