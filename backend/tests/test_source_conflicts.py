"""P1-04 immutable source-conflict handling tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.market_data.conflicts import (
    CanonicalSourceObservation,
    SourceConflictError,
    SourceConflictIntegrityError,
    candle_sequence_hash,
    compare_source_batch,
    verify_source_conflict,
)
from app.market_data.models import Candle, CandleTimeframe, HistoricalCandlePage
from app.market_data.orchestration import orchestrate_intraday_historical_window
from app.persistence.candles import CandlePersistenceResult
from app.persistence.conflicts import (
    source_conflict_evidence,
    source_conflict_record,
)
from app.persistence.models import (
    HistoricalAcquisitionOutcomeRecord,
    SourceConflictRecord,
)


_TIMESTAMP = datetime(2026, 8, 1, 11, 50, tzinfo=timezone.utc)
_NOW = datetime(2026, 8, 1, 12, 7, tzinfo=timezone.utc)
_CANONICAL_BATCH = UUID("00000000-0000-0000-0000-000000000601")
_INCOMING_BATCH = UUID("00000000-0000-0000-0000-000000000602")
_ATTEMPT = UUID("00000000-0000-0000-0000-000000000603")
_CONFLICT_ID = UUID("00000000-0000-0000-0000-000000000604")


class SourceConflictTests(unittest.TestCase):
    def test_identical_and_precision_equivalent_replay_is_reused(self) -> None:
        canonical = _candle(_TIMESTAMP, close="101.000000000000000000")
        incoming = _candle(_TIMESTAMP, close="101.0")

        comparison = _compare(incoming, canonical=canonical)

        self.assertEqual(comparison.reused_count, 1)
        self.assertEqual(comparison.conflicts, ())
        self.assertTrue(comparison.canonical_insert_allowed)

    def test_conflicting_payload_fails_whole_batch_and_preserves_values(
        self,
    ) -> None:
        canonical = _candle(_TIMESTAMP, close="101")
        incoming = _candle(_TIMESTAMP, close="101.5")

        comparison = _compare(incoming, canonical=canonical)

        self.assertEqual(comparison.reused_count, 0)
        self.assertFalse(comparison.canonical_insert_allowed)
        self.assertEqual(len(comparison.conflicts), 1)
        conflict = comparison.conflicts[0]
        self.assertEqual(conflict.conflict_type, "provider_revision_conflict")
        self.assertEqual(conflict.canonical_candle.close, Decimal("101"))
        self.assertEqual(conflict.incoming_candle.close, Decimal("101.5"))
        self.assertEqual(canonical.close, Decimal("101"))
        verify_source_conflict(conflict)

    def test_provider_identity_conflict_is_not_exact_replay(self) -> None:
        candle = _candle(_TIMESTAMP)

        comparison = _compare(candle, canonical=candle, provider="other")

        self.assertFalse(comparison.canonical_insert_allowed)
        self.assertEqual(
            comparison.conflicts[0].conflict_type,
            "provider_identity_conflict",
        )

    def test_one_conflict_blocks_new_observations_from_entire_batch(self) -> None:
        canonical = _candle(_TIMESTAMP, close="101")
        conflict = _candle(_TIMESTAMP, close="102")
        new_candle = _candle(_TIMESTAMP + timedelta(minutes=5))

        comparison = compare_source_batch(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=CandleTimeframe.MINUTE_5,
            canonical_by_timestamp={
                _TIMESTAMP: CanonicalSourceObservation(
                    candle_id=1,
                    ingestion_batch_id=_CANONICAL_BATCH,
                    provider="kraken",
                    candle=canonical,
                )
            },
            incoming_candles=(conflict, new_candle),
            incoming_attempt_id=_ATTEMPT,
            incoming_ingestion_batch_id=_INCOMING_BATCH,
            incoming_provider="kraken",
            retrieved_at=_NOW,
            incoming_batch_source_hash=candle_sequence_hash((conflict, new_candle)),
            interval_duration_seconds=300,
        )

        self.assertFalse(comparison.canonical_insert_allowed)
        self.assertEqual(len(comparison.conflicts), 1)

    def test_repeated_execution_has_stable_semantic_hashes(self) -> None:
        canonical = _candle(_TIMESTAMP, close="101")
        incoming = _candle(_TIMESTAMP, close="102")
        first = _compare(incoming, canonical=canonical).conflicts[0]
        second = compare_source_batch(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=CandleTimeframe.MINUTE_5,
            canonical_by_timestamp={
                _TIMESTAMP: CanonicalSourceObservation(
                    candle_id=1,
                    ingestion_batch_id=_CANONICAL_BATCH,
                    provider="kraken",
                    candle=canonical,
                )
            },
            incoming_candles=(incoming,),
            incoming_attempt_id=UUID("00000000-0000-0000-0000-000000000613"),
            incoming_ingestion_batch_id=UUID("00000000-0000-0000-0000-000000000612"),
            incoming_provider="kraken",
            retrieved_at=_NOW + timedelta(minutes=5),
            incoming_batch_source_hash=candle_sequence_hash((incoming,)),
            interval_duration_seconds=300,
        ).conflicts[0]

        self.assertNotEqual(
            first.incoming_ingestion_batch_id,
            second.incoming_ingestion_batch_id,
        )
        self.assertEqual(first.canonical_candle_hash, second.canonical_candle_hash)
        self.assertEqual(first.incoming_candle_hash, second.incoming_candle_hash)
        self.assertEqual(first.conflict_hash, second.conflict_hash)

    def test_corruption_is_detected(self) -> None:
        conflict = _compare(
            _candle(_TIMESTAMP, close="102"),
            canonical=_candle(_TIMESTAMP, close="101"),
        ).conflicts[0]

        with self.assertRaisesRegex(
            SourceConflictIntegrityError,
            "integrity verification",
        ):
            verify_source_conflict(replace(conflict, conflict_hash="0" * 64))

    def test_persistence_round_trip_retains_complete_immutable_provenance(
        self,
    ) -> None:
        conflict = _compare(
            _candle(_TIMESTAMP, close="102"),
            canonical=_candle(_TIMESTAMP, close="101"),
        ).conflicts[0]

        record = source_conflict_record(conflict, _CONFLICT_ID)
        restored = source_conflict_evidence(record)

        self.assertEqual(restored, conflict)
        self.assertTrue(record.immutable)
        self.assertEqual(record.id, _CONFLICT_ID)
        self.assertEqual(record.canonical_ingestion_batch_id, _CANONICAL_BATCH)
        self.assertEqual(record.incoming_ingestion_batch_id, _INCOMING_BATCH)
        self.assertEqual(record.incoming_attempt_id, _ATTEMPT)
        self.assertEqual(record.retrieved_at, _NOW)
        self.assertEqual(
            record.available_at,
            _TIMESTAMP + timedelta(minutes=5),
        )

    def test_schema_and_migration_preserve_append_only_evidence(self) -> None:
        table = SourceConflictRecord.__table__
        self.assertEqual(table.name, "market_data_source_conflicts")
        self.assertIn(
            "uq_source_conflicts_batch_candle",
            {constraint.name for constraint in table.constraints},
        )
        outcome_sql = " ".join(
            str(constraint.sqltext)
            for constraint in HistoricalAcquisitionOutcomeRecord.__table__.constraints
            if hasattr(constraint, "sqltext")
        )
        self.assertIn("CONFLICT_FAILED", outcome_sql)

        path = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20260801_0030_create_immutable_source_conflicts.py"
        )
        spec = importlib.util.spec_from_file_location("p1_04_migration", path)
        if spec is None or spec.loader is None:
            self.fail("P1-04 migration could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mocked_op = MagicMock()
        with patch.object(module, "op", mocked_op):
            module.upgrade()
        self.assertEqual(module.down_revision, "20260731_0029")
        self.assertEqual(
            mocked_op.create_table.call_args.args[0],
            "market_data_source_conflicts",
        )
        mocked_op.reset_mock()
        with patch.object(module, "op", mocked_op):
            module.downgrade()
        mocked_op.drop_table.assert_called_once_with("market_data_source_conflicts")


class ConflictOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_conflict_records_terminal_failure_without_checkpoint(
        self,
    ) -> None:
        store = _ConflictStore()

        with self.assertRaises(SourceConflictError):
            await orchestrate_intraday_historical_window(
                provider=_Provider(),
                store=store,
                timeframe=CandleTimeframe.MINUTE_5,
                code_version="ba55adb",
                now=_NOW,
            )

        self.assertEqual(store.conflict_outcomes, 1)
        self.assertEqual(store.checkpoints, 0)
        self.assertEqual(store.failures, 0)


def _compare(
    incoming: Candle,
    *,
    canonical: Candle,
    provider: str = "kraken",
):
    return compare_source_batch(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=CandleTimeframe.MINUTE_5,
        canonical_by_timestamp={
            _TIMESTAMP: CanonicalSourceObservation(
                candle_id=1,
                ingestion_batch_id=_CANONICAL_BATCH,
                provider="kraken",
                candle=canonical,
            )
        },
        incoming_candles=(incoming,),
        incoming_attempt_id=_ATTEMPT,
        incoming_ingestion_batch_id=_INCOMING_BATCH,
        incoming_provider=provider,
        retrieved_at=_NOW,
        incoming_batch_source_hash=candle_sequence_hash((incoming,)),
        interval_duration_seconds=300,
    )


class _Provider:
    async def get_historical_candle_page(
        self,
        asset_identifier,
        quote_currency,
        timeframe,
        since,
    ):
        candles = tuple(
            _candle(_TIMESTAMP + timedelta(minutes=5 * index)) for index in range(4)
        )
        return HistoricalCandlePage(
            candles=candles,
            next_since=int((_NOW + timedelta(minutes=5)).timestamp()),
        )


class _ConflictStore:
    def __init__(self) -> None:
        self.conflict_outcomes = 0
        self.checkpoints = 0
        self.failures = 0

    async def prepare_resume(self, timeframe, configuration_hash, code_version):
        return None

    async def record_attempt(self, attempt):
        return None

    async def record_failure(self, *args):
        self.failures += 1

    async def persist_sample(self, attempt_id, sample):
        return CandlePersistenceResult(
            ingestion_batch_id=_INCOMING_BATCH,
            validation_passed=True,
            fetched_candle_count=len(sample.candles),
            persisted_candle_count=0,
            stored_candle_count=3,
            ingestion_batch_count=2,
            reused_candle_count=2,
            conflict_count=1,
            source_data_hash=candle_sequence_hash(sample.candles),
        )

    async def record_conflict(self, attempt, persistence, completed_at):
        self.conflict_outcomes += 1

    async def record_checkpoint(self, attempt, checkpoint, completed_at):
        self.checkpoints += 1
        return checkpoint.checkpoint_id


def _candle(
    timestamp: datetime,
    *,
    close: str = "101",
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("103"),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("1.123456789012345678"),
    )


if __name__ == "__main__":
    unittest.main()
