"""P1-03 resumable intraday historical orchestration tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from app.market_data.models import Candle, CandleTimeframe, HistoricalCandlePage
from app.market_data.orchestration import (
    CheckpointIntegrityError,
    CheckpointReconciliationRequired,
    HistoricalOrchestrationError,
    orchestrate_intraday_historical_window,
    verify_acquisition_checkpoint,
)
from app.market_data.provider import MarketDataProviderError
from app.persistence.candles import CandlePersistenceResult
from app.persistence.models import (
    HistoricalAcquisitionAttemptRecord,
    HistoricalAcquisitionCheckpointRecord,
    HistoricalAcquisitionOutcomeRecord,
)


_NOW = datetime(2026, 7, 31, 12, 7, tzinfo=timezone.utc)
_START = datetime(2026, 7, 31, 11, 50, tzinfo=timezone.utc)
_BATCH = UUID("00000000-0000-0000-0000-000000000501")


class HistoricalOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_window_terminates_and_reports_progress(self) -> None:
        provider = _Provider(_page())
        store = _Store(inserted_count=3)
        progress = []

        result = await orchestrate_intraday_historical_window(
            provider=provider,
            store=store,
            timeframe=CandleTimeframe.MINUTE_5,
            code_version="3f74cc4",
            now=_NOW,
            progress_callback=progress.append,
        )

        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.checkpoint.provider_row_count, 4)
        self.assertEqual(result.checkpoint.accepted_count, 3)
        self.assertEqual(result.checkpoint.excluded_incomplete_count, 1)
        self.assertEqual(result.checkpoint.inserted_count, 3)
        self.assertEqual(result.checkpoint.reused_count, 0)
        self.assertEqual(result.checkpoint.terminal_reason, "SUCCESS_NEW_INSERTS")
        self.assertEqual(progress, [result.checkpoint])
        self.assertEqual(len(store.attempts), 1)
        self.assertEqual(len(store.checkpoints), 1)

    async def test_restart_verifies_and_links_predecessor(self) -> None:
        first_store = _Store(inserted_count=3)
        first = await _run(first_store)
        second_store = _Store(
            inserted_count=0,
            predecessor=first.checkpoint,
        )

        second = await _run(second_store)

        self.assertEqual(
            second.checkpoint.predecessor_checkpoint_id,
            first.checkpoint.checkpoint_id,
        )
        self.assertEqual(second.checkpoint.reused_count, 3)
        self.assertEqual(second.checkpoint.inserted_count, 0)
        self.assertEqual(second.checkpoint.terminal_reason, "SUCCESS_REUSE_ONLY")

    async def test_unreconciled_partial_attempt_fails_before_provider(self) -> None:
        provider = _Provider(_page())
        store = _Store(prepare_error=CheckpointReconciliationRequired("reconcile"))

        with self.assertRaises(CheckpointReconciliationRequired):
            await _run(store, provider)

        self.assertEqual(provider.calls, 0)
        self.assertEqual(store.attempts, [])

    async def test_provider_timeout_and_malformed_response_are_terminal(self) -> None:
        for message in ("Unable to reach Kraken.", "Malformed response."):
            with self.subTest(message=message):
                store = _Store(inserted_count=0)
                provider = _Provider(MarketDataProviderError(message))

                with self.assertRaises(MarketDataProviderError):
                    await _run(store, provider)

                self.assertEqual(provider.calls, 1)
                self.assertEqual(len(store.failures), 1)
                self.assertEqual(store.failures[0][0], "PROVIDER_FAILED")
                self.assertEqual(store.persist_calls, 0)
                self.assertEqual(store.checkpoints, [])

    async def test_invalid_window_does_not_persist_or_checkpoint(self) -> None:
        invalid = Candle(
            timestamp=_START,
            open=Decimal("100"),
            high=Decimal("90"),
            low=Decimal("110"),
            close=Decimal("105"),
            volume=Decimal("-1"),
        )
        store = _Store(inserted_count=0)

        with self.assertRaises(HistoricalOrchestrationError):
            await _run(store, _Provider(_page((invalid,))))

        self.assertEqual(store.persist_calls, 0)
        self.assertEqual(store.failures[0][0], "VALIDATION_FAILED")
        self.assertEqual(store.checkpoints, [])

    async def test_progress_hash_is_deterministic_and_detects_corruption(self) -> None:
        first = await _run(_Store(inserted_count=3))
        second = await _run(_Store(inserted_count=3))

        self.assertNotEqual(first.attempt.attempt_id, second.attempt.attempt_id)
        self.assertEqual(
            first.checkpoint.progress_hash,
            second.checkpoint.progress_hash,
        )
        self.assertEqual(
            first.checkpoint.checkpoint_hash,
            second.checkpoint.checkpoint_hash,
        )
        with self.assertRaisesRegex(CheckpointIntegrityError, "hash"):
            verify_acquisition_checkpoint(
                replace(first.checkpoint, progress_hash="0" * 64)
            )

    async def test_unsupported_derived_timeframe_fails_before_attempt(self) -> None:
        provider = _Provider(_page())
        store = _Store(inserted_count=0)

        with self.assertRaisesRegex(HistoricalOrchestrationError, "native"):
            await orchestrate_intraday_historical_window(
                provider=provider,
                store=store,
                timeframe=CandleTimeframe.MINUTE_10,
                code_version="3f74cc4",
                now=_NOW,
            )

        self.assertEqual(provider.calls, 0)

    def test_schema_and_migration_are_append_only_and_reversible(self) -> None:
        self.assertEqual(
            HistoricalAcquisitionAttemptRecord.__table__.name,
            "historical_acquisition_attempts",
        )
        self.assertEqual(
            HistoricalAcquisitionOutcomeRecord.__table__.name,
            "historical_acquisition_outcomes",
        )
        self.assertIn(
            "uq_historical_acquisition_checkpoints_attempt",
            {
                item.name
                for item in HistoricalAcquisitionCheckpointRecord.__table__.constraints
            },
        )
        path = (
            Path(__file__).parents[1]
            / "alembic"
            / "versions"
            / "20260731_0029_create_historical_acquisition_checkpoints.py"
        )
        spec = importlib.util.spec_from_file_location("p1_03_migration", path)
        if spec is None or spec.loader is None:
            self.fail("P1-03 migration could not be loaded.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        mocked_op = MagicMock()
        with patch.object(module, "op", mocked_op):
            module.upgrade()
        self.assertEqual(module.down_revision, "20260731_0028")
        self.assertEqual(
            [call.args[0] for call in mocked_op.create_table.call_args_list],
            [
                "historical_acquisition_attempts",
                "historical_acquisition_outcomes",
                "historical_acquisition_checkpoints",
            ],
        )
        mocked_op.reset_mock()
        with patch.object(module, "op", mocked_op):
            module.downgrade()
        self.assertEqual(
            [call.args[0] for call in mocked_op.drop_table.call_args_list],
            [
                "historical_acquisition_checkpoints",
                "historical_acquisition_outcomes",
                "historical_acquisition_attempts",
            ],
        )


async def _run(store, provider=None):
    return await orchestrate_intraday_historical_window(
        provider=provider or _Provider(_page()),
        store=store,
        timeframe=CandleTimeframe.MINUTE_5,
        code_version="3f74cc4",
        now=_NOW,
    )


class _Provider:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    async def get_historical_candle_page(
        self,
        asset_identifier,
        quote_currency,
        timeframe,
        since,
    ):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _Store:
    def __init__(
        self,
        inserted_count=0,
        predecessor=None,
        prepare_error=None,
    ) -> None:
        self.inserted_count = inserted_count
        self.predecessor = predecessor
        self.prepare_error = prepare_error
        self.attempts = []
        self.failures = []
        self.checkpoints = []
        self.persist_calls = 0

    async def prepare_resume(self, timeframe, configuration_hash, code_version):
        if self.prepare_error is not None:
            raise self.prepare_error
        if self.predecessor is not None:
            verify_acquisition_checkpoint(self.predecessor)
        return self.predecessor

    async def record_attempt(self, attempt):
        self.attempts.append(attempt)

    async def record_failure(
        self,
        attempt,
        terminal_reason,
        failure_class,
        failure_summary,
        completed_at,
    ):
        self.failures.append(
            (terminal_reason, failure_class, failure_summary, completed_at)
        )

    async def persist_sample(self, attempt_id, sample):
        self.persist_calls += 1
        return CandlePersistenceResult(
            ingestion_batch_id=_BATCH,
            validation_passed=True,
            fetched_candle_count=len(sample.candles),
            persisted_candle_count=self.inserted_count,
            stored_candle_count=len(sample.candles),
            ingestion_batch_count=1,
        )

    async def record_checkpoint(self, attempt, checkpoint, completed_at):
        verify_acquisition_checkpoint(checkpoint)
        self.checkpoints.append(checkpoint)
        return checkpoint.checkpoint_id


def _page(candles=None):
    values = candles or tuple(
        _candle(_START + timedelta(minutes=5 * index)) for index in range(4)
    )
    return HistoricalCandlePage(
        candles=values,
        next_since=int((_NOW + timedelta(minutes=5)).timestamp()),
    )


def _candle(timestamp):
    return Candle(
        timestamp=timestamp,
        open=Decimal("100.000000000000000001"),
        high=Decimal("102.000000000000000001"),
        low=Decimal("99.000000000000000001"),
        close=Decimal("101.000000000000000001"),
        volume=Decimal("1.123456789012345678"),
    )


if __name__ == "__main__":
    unittest.main()
