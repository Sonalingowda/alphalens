"""Immutable historical coverage snapshot tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.market_data.coverage import (
    ACQUISITION_POLICY_IDENTIFIER,
    COVERAGE_HASH_SCHEMA_VERSION,
    COVERAGE_SNAPSHOT_SCHEMA_VERSION,
    CoverageBatchEvidence,
    CoverageObservation,
    HistoricalCoverageError,
    build_historical_coverage_snapshot,
    verify_historical_coverage_snapshot,
)
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.coverage import (
    _snapshot_record,
    persist_historical_coverage_snapshot,
)
from app.persistence.models import (
    HistoricalCoverageSnapshotBatchRecord,
    HistoricalCoverageSnapshotCandleRecord,
    HistoricalCoverageSnapshotRecord,
)


_START = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
_BATCH_1 = UUID("00000000-0000-0000-0000-000000000101")
_BATCH_2 = UUID("00000000-0000-0000-0000-000000000102")
_SOURCE_BATCH = UUID("00000000-0000-0000-0000-000000000099")


class HistoricalCoverageTests(unittest.TestCase):
    def test_snapshot_is_deterministic_and_resolves_membership(self) -> None:
        observations, batches = _evidence()

        first = _build(observations, batches)
        second = _build(observations, tuple(reversed(batches)))

        self.assertEqual(first, second)
        self.assertEqual(first.schema_version, COVERAGE_SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(
            first.hash_schema_version,
            COVERAGE_HASH_SCHEMA_VERSION,
        )
        self.assertEqual(
            first.acquisition_policy_identifier,
            ACQUISITION_POLICY_IDENTIFIER,
        )
        self.assertEqual(first.observed_candle_count, 4)
        self.assertEqual(first.expected_candle_count, 4)
        self.assertEqual(first.gap_count, 0)
        self.assertEqual(first.source_batch_count, 2)
        self.assertEqual(
            tuple(item.candle_count for item in first.batch_memberships),
            (2, 2),
        )
        self.assertTrue(
            all(len(value) == 64 for value in _hashes(first))
        )
        verify_historical_coverage_snapshot(first)

    def test_gap_is_reported_without_fabrication(self) -> None:
        observations, batches = _evidence()
        observations = observations[:2] + observations[3:]

        snapshot = _build(observations, batches)

        self.assertFalse(snapshot.validation_report.passed)
        self.assertEqual(snapshot.expected_candle_count, 4)
        self.assertEqual(snapshot.observed_candle_count, 3)
        self.assertEqual(snapshot.gap_count, 1)
        self.assertEqual(
            snapshot.gap_timestamps,
            (_START + timedelta(minutes=10),),
        )
        self.assertEqual(
            tuple(
                issue.code for issue in snapshot.validation_report.issues
            ),
            ("missing_candle",),
        )

    def test_empty_coverage_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "at least one canonical candle",
        ):
            _build((), ())

    def test_noncanonical_order_and_duplicate_membership_are_rejected(
        self,
    ) -> None:
        observations, batches = _evidence()

        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "strictly chronological",
        ):
            _build(
                (observations[1], observations[0]) + observations[2:],
                batches,
            )

        duplicated_id = replace(
            observations[1],
            candle_id=observations[0].candle_id,
        )
        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "identities must be unique",
        ):
            _build(
                (observations[0], duplicated_id) + observations[2:],
                batches,
            )

    def test_membership_and_hash_tampering_is_rejected(self) -> None:
        observations, batches = _evidence()
        snapshot = _build(observations, batches)

        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "integrity verification failed",
        ):
            verify_historical_coverage_snapshot(
                replace(snapshot, result_hash="0" * 64)
            )

        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "exactly match candle memberships",
        ):
            _build(observations, batches[:1])

    def test_data_and_provenance_changes_have_distinct_hash_effects(
        self,
    ) -> None:
        observations, batches = _evidence()
        original = _build(observations, batches)
        changed_candle = replace(
            observations[0],
            candle=replace(
                observations[0].candle,
                close=Decimal("101.500000000000000001"),
            ),
        )
        changed_data = _build(
            (changed_candle,) + observations[1:],
            batches,
        )
        changed_batch = replace(
            batches[0],
            retrieved_at=batches[0].retrieved_at + timedelta(seconds=1),
        )
        changed_provenance = _build(
            observations,
            (changed_batch, batches[1]),
        )

        self.assertNotEqual(
            original.source_data_hash,
            changed_data.source_data_hash,
        )
        self.assertNotEqual(original.result_hash, changed_data.result_hash)
        self.assertEqual(
            original.source_data_hash,
            changed_provenance.source_data_hash,
        )
        self.assertNotEqual(
            original.validation_hash,
            changed_provenance.validation_hash,
        )
        self.assertNotEqual(
            original.source_provenance_hash,
            changed_provenance.source_provenance_hash,
        )

    def test_10m_snapshot_retains_derivation_evidence(self) -> None:
        observations, batches = _evidence(
            timeframe=CandleTimeframe.MINUTE_10,
        )

        snapshot = _build(
            observations,
            batches,
            timeframe=CandleTimeframe.MINUTE_10,
        )

        self.assertEqual(len(snapshot.derivation_summary), 2)
        self.assertEqual(
            snapshot.derivation_summary[0]["source_timeframe"],
            "5m",
        )
        self.assertEqual(
            snapshot.derivation_summary[0]["source_ingestion_batch_id"],
            str(_SOURCE_BATCH),
        )

    def test_persistence_record_preserves_snapshot_identity(self) -> None:
        snapshot = _build(*_evidence())
        snapshot_id = UUID("00000000-0000-0000-0000-000000000200")

        record = _snapshot_record(snapshot_id, snapshot)

        self.assertEqual(record.id, snapshot_id)
        self.assertEqual(record.result_hash, snapshot.result_hash)
        self.assertEqual(record.source_data_hash, snapshot.source_data_hash)
        self.assertEqual(record.gap_timestamps, [])
        self.assertTrue(record.immutable)

    def test_schema_enforces_ordered_and_unique_memberships(self) -> None:
        snapshot_table = HistoricalCoverageSnapshotRecord.__table__
        candle_table = HistoricalCoverageSnapshotCandleRecord.__table__
        batch_table = HistoricalCoverageSnapshotBatchRecord.__table__

        self.assertEqual(snapshot_table.name, "historical_coverage_snapshots")
        self.assertIn(
            "uq_coverage_snapshots_result_hash",
            {item.name for item in snapshot_table.constraints},
        )
        self.assertIn(
            "uq_coverage_snapshot_candles_ordinal",
            {item.name for item in candle_table.constraints},
        )
        self.assertEqual(
            tuple(column.name for column in candle_table.primary_key.columns),
            ("snapshot_id", "candle_id"),
        )
        self.assertEqual(
            tuple(column.name for column in batch_table.primary_key.columns),
            ("snapshot_id", "ingestion_batch_id"),
        )

    def test_migration_has_safe_upgrade_and_reverse_order_downgrade(
        self,
    ) -> None:
        migration_path = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20260731_0028_create_historical_coverage_snapshots.py"
        )
        spec = importlib.util.spec_from_file_location(
            "historical_coverage_migration",
            migration_path,
        )
        if spec is None or spec.loader is None:
            self.fail("Historical coverage migration could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mocked_op = MagicMock()

        with patch.object(module, "op", mocked_op):
            module.upgrade()
        created = [
            call.args[0] for call in mocked_op.create_table.call_args_list
        ]
        self.assertEqual(
            created,
            [
                "historical_coverage_snapshots",
                "historical_coverage_snapshot_candles",
                "historical_coverage_snapshot_batches",
            ],
        )

        mocked_op.reset_mock()
        with patch.object(module, "op", mocked_op):
            module.downgrade()
        dropped = [
            call.args[0] for call in mocked_op.drop_table.call_args_list
        ]
        self.assertEqual(
            dropped,
            [
                "historical_coverage_snapshot_batches",
                "historical_coverage_snapshot_candles",
                "historical_coverage_snapshots",
            ],
        )
        self.assertEqual(module.down_revision, "20260730_0027")
        self.assertTrue(
            migration_path.name.startswith("20260731_0028")
        )


class HistoricalCoveragePersistenceTests(
    unittest.IsolatedAsyncioTestCase
):
    async def test_persistence_is_insert_once_and_idempotent(self) -> None:
        snapshot = _build(*_evidence())
        new_session = _FakeSession()

        created = await persist_historical_coverage_snapshot(
            new_session,
            snapshot,
        )

        self.assertFalse(created.reused)
        self.assertEqual(created.result_hash, snapshot.result_hash)
        self.assertEqual(len(new_session.added), 1)
        self.assertEqual(
            tuple(len(group) for group in new_session.added_groups),
            (4, 2),
        )
        self.assertEqual(new_session.flush_count, 1)
        self.assertEqual(
            new_session.events,
            ["add", "flush", "add_all", "add_all"],
        )

        existing = _snapshot_record(created.snapshot_id, snapshot)
        candle_memberships = [
            HistoricalCoverageSnapshotCandleRecord(
                snapshot_id=created.snapshot_id,
                candle_id=item.candle_id,
                ordinal=ordinal,
            )
            for ordinal, item in enumerate(snapshot.observations)
        ]
        batch_memberships = [
            HistoricalCoverageSnapshotBatchRecord(
                snapshot_id=created.snapshot_id,
                ingestion_batch_id=item.ingestion_batch_id,
                candle_count=item.candle_count,
                source_subset_hash=item.source_subset_hash,
            )
            for item in snapshot.batch_memberships
        ]
        repeated_session = _FakeSession(
            existing,
            scalar_results=(candle_memberships, batch_memberships),
        )
        repeated = await persist_historical_coverage_snapshot(
            repeated_session,
            snapshot,
        )

        self.assertTrue(repeated.reused)
        self.assertEqual(repeated.snapshot_id, created.snapshot_id)
        self.assertEqual(repeated_session.added, [])
        self.assertEqual(repeated_session.flush_count, 0)

    async def test_persistence_rejects_membership_hash_mismatch(self) -> None:
        snapshot = _build(*_evidence())
        snapshot_id = UUID("00000000-0000-0000-0000-000000000301")
        existing = _snapshot_record(snapshot_id, snapshot)
        missing_candle_membership = [
            HistoricalCoverageSnapshotCandleRecord(
                snapshot_id=snapshot_id,
                candle_id=item.candle_id,
                ordinal=ordinal,
            )
            for ordinal, item in enumerate(snapshot.observations[:-1])
        ]
        batch_memberships = [
            HistoricalCoverageSnapshotBatchRecord(
                snapshot_id=snapshot_id,
                ingestion_batch_id=item.ingestion_batch_id,
                candle_count=item.candle_count,
                source_subset_hash=item.source_subset_hash,
            )
            for item in snapshot.batch_memberships
        ]

        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "membership conflicts with its result hash",
        ):
            await persist_historical_coverage_snapshot(
                _FakeSession(
                    existing,
                    scalar_results=(
                        missing_candle_membership,
                        batch_memberships,
                    ),
                ),
                snapshot,
            )

    async def test_persistence_rejects_result_hash_collision(self) -> None:
        snapshot = _build(*_evidence())
        existing = _snapshot_record(
            UUID("00000000-0000-0000-0000-000000000300"),
            snapshot,
        )
        existing.source_data_hash = "f" * 64

        with self.assertRaisesRegex(
            HistoricalCoverageError,
            "conflicts with its result hash",
        ):
            await persist_historical_coverage_snapshot(
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
        existing: HistoricalCoverageSnapshotRecord | None = None,
        scalar_results: tuple[list[object], ...] = (),
    ) -> None:
        self.existing = existing
        self.scalar_results = list(scalar_results)
        self.added: list[object] = []
        self.added_groups: list[list[object]] = []
        self.flush_count = 0
        self.events: list[str] = []

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def scalar(self, statement):
        del statement
        return self.existing

    async def scalars(self, statement):
        del statement
        return _FakeScalarResult(self.scalar_results.pop(0))

    def add(self, value: object) -> None:
        self.added.append(value)
        self.events.append("add")

    def add_all(self, values) -> None:
        self.added_groups.append(list(values))
        self.events.append("add_all")

    async def flush(self) -> None:
        self.flush_count += 1
        self.events.append("flush")


class _FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


def _build(
    observations: tuple[CoverageObservation, ...],
    batches: tuple[CoverageBatchEvidence, ...],
    *,
    timeframe: CandleTimeframe = CandleTimeframe.MINUTE_5,
):
    return build_historical_coverage_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
        batches=batches,
    )


def _evidence(
    *,
    timeframe: CandleTimeframe = CandleTimeframe.MINUTE_5,
) -> tuple[
    tuple[CoverageObservation, ...],
    tuple[CoverageBatchEvidence, ...],
]:
    duration = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
    }[timeframe]
    batch_ids = (_BATCH_1, _BATCH_1, _BATCH_2, _BATCH_2)
    observations = tuple(
        CoverageObservation(
            candle_id=index + 1,
            ingestion_batch_id=batch_id,
            provider="kraken",
            is_complete=True,
            candle=_candle(_START + duration * index),
        )
        for index, batch_id in enumerate(batch_ids)
    )
    derivation = (
        (
            CandleTimeframe.MINUTE_5,
            "aggregate_two_adjacent_5m_v1",
            _SOURCE_BATCH,
        )
        if timeframe is CandleTimeframe.MINUTE_10
        else (None, None, None)
    )
    batches = (
        _batch(
            _BATCH_1,
            timeframe,
            _START,
            _START + duration * 2,
            derivation,
        ),
        _batch(
            _BATCH_2,
            timeframe,
            _START + duration * 2,
            _START + duration * 4,
            derivation,
        ),
    )
    return observations, batches


def _batch(
    batch_id: UUID,
    timeframe: CandleTimeframe,
    start: datetime,
    end: datetime,
    derivation: tuple[
        CandleTimeframe | None,
        str | None,
        UUID | None,
    ],
) -> CoverageBatchEvidence:
    return CoverageBatchEvidence(
        ingestion_batch_id=batch_id,
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=start,
        requested_end_exclusive=end,
        retrieved_at=end + timedelta(seconds=30),
        validation_passed=True,
        validation_issues=(),
        source_timeframe=derivation[0],
        derivation_method=derivation[1],
        source_ingestion_batch_id=derivation[2],
    )


def _candle(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal("100.000000000000000001"),
        high=Decimal("102.000000000000000001"),
        low=Decimal("99.000000000000000001"),
        close=Decimal("101.000000000000000001"),
        volume=Decimal("1.123456789012345678"),
    )


def _hashes(snapshot) -> tuple[str, ...]:
    return (
        snapshot.validation_hash,
        snapshot.source_data_hash,
        snapshot.source_provenance_hash,
        snapshot.result_hash,
    )


if __name__ == "__main__":
    unittest.main()
