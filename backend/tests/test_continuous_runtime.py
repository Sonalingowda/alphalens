"""Offline continuous-runtime, checkpoint, and recovery tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from app.live_market_data import (
    BinanceWebSocketClient,
    CompletedCandle,
    ContinuousClosedCandleProcessor,
    FilesystemRuntimeCheckpointStore,
    LiveMarketIngestionService,
    RuntimeOutOfOrderError,
    RuntimeProcessingOutcome,
)
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.persistence import MarketSnapshotMemoryRepository


SOURCE_HASH = "f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc"
START = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)


def _candle(index: int) -> CompletedCandle:
    open_time = START + timedelta(minutes=index * 5)
    close_time = open_time + timedelta(minutes=5) - timedelta(milliseconds=1)
    price = Decimal("82000") + Decimal(index)
    return CompletedCandle(
        provider="binance_spot",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=close_time + timedelta(milliseconds=1),
        open_time=open_time,
        close_time=close_time,
        open=price,
        high=price + Decimal("5"),
        low=price - Decimal("5"),
        close=price + Decimal("1"),
        volume=Decimal("100"),
        number_of_trades=100 + index,
        source_payload_hash=f"{index + 1:064x}",
    )


def _processor(path: Path, pipeline: AsyncMock) -> ContinuousClosedCandleProcessor:
    repository = MarketSnapshotMemoryRepository()
    ingestion = LiveMarketIngestionService(
        repository=repository,
        code_version="checkpoint04.test",
        rest_base_url="http://127.0.0.1:9",
        rest_fallback_urls=(),
    )
    return ContinuousClosedCandleProcessor(
        ingestion=ingestion,
        checkpoint_store=FilesystemRuntimeCheckpointStore(
            path, source_dataset_sha256=SOURCE_HASH
        ),
        pipeline=pipeline,
        code_version="checkpoint04.test",
    )


class ContinuousRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_trial_can_bind_the_websocket_to_5m_only(self) -> None:
        client = BinanceWebSocketClient(
            stream_timeframes=(CandleTimeframe.MINUTE_5,)
        )
        self.assertEqual(
            client.url,
            "wss://data-stream.binance.vision/stream?streams=btcusdt@kline_5m",
        )

    async def test_sequential_processing_and_duplicate_delivery_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            processor = _processor(Path(directory) / "checkpoint.json", pipeline)

            self.assertEqual(
                await processor.process(_candle(0)), RuntimeProcessingOutcome.PROCESSED
            )
            self.assertEqual(
                await processor.process(_candle(1)), RuntimeProcessingOutcome.PROCESSED
            )
            self.assertEqual(
                await processor.process(_candle(1)), RuntimeProcessingOutcome.DUPLICATE
            )
            self.assertEqual(pipeline.await_count, 2)
            self.assertEqual(processor.checkpoint.sequence, 2)  # type: ignore[union-attr]

    async def test_restart_recovers_durable_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            first_pipeline = AsyncMock()
            first = _processor(path, first_pipeline)
            await first.process(_candle(0))

            second_pipeline = AsyncMock()
            second = _processor(path, second_pipeline)
            self.assertEqual(second.checkpoint.sequence, 1)  # type: ignore[union-attr]
            self.assertEqual(
                await second.process(_candle(1)), RuntimeProcessingOutcome.PROCESSED
            )

    async def test_gap_is_quarantined_without_persisting_future_candle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            processor = _processor(Path(directory) / "checkpoint.json", pipeline)
            await processor.process(_candle(0))
            self.assertEqual(
                await processor.process(_candle(2)), RuntimeProcessingOutcome.QUARANTINED
            )
            self.assertEqual(pipeline.await_count, 1)
            self.assertEqual(processor.health.gap_status, "QUARANTINED")
            with self.assertRaises(RuntimeOutOfOrderError):
                await processor.process(_candle(-1))

    async def test_missing_candle_recovery_clears_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            processor = _processor(Path(directory) / "checkpoint.json", pipeline)
            await processor.process(_candle(0))
            await processor.process(_candle(2))
            self.assertEqual(
                await processor.process(_candle(1)), RuntimeProcessingOutcome.PROCESSED
            )
            self.assertEqual(
                await processor.process(_candle(2)), RuntimeProcessingOutcome.PROCESSED
            )
            self.assertEqual(processor.health.gap_status, "CLEAR")

    async def test_bounded_retry_recovers_transient_pipeline_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock(side_effect=[RuntimeError("temporary"), None])
            processor = _processor(Path(directory) / "checkpoint.json", pipeline)
            self.assertEqual(
                await processor.process_with_retry(_candle(0)),
                RuntimeProcessingOutcome.PROCESSED,
            )
            self.assertEqual(pipeline.await_count, 2)
            self.assertEqual(processor.health.retry_status, "idle")

    async def test_interrupted_commit_replays_inflight_candle_without_new_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            repository = MarketSnapshotMemoryRepository()
            ingestion = LiveMarketIngestionService(
                repository=repository,
                code_version="checkpoint04.test",
                rest_base_url="http://127.0.0.1:9",
                rest_fallback_urls=(),
            )

            class FailingCommitStore(FilesystemRuntimeCheckpointStore):
                saves = 0

                def save(self, checkpoint):
                    self.saves += 1
                    if self.saves == 2:
                        raise RuntimeError("simulated interrupted checkpoint commit")
                    return super().save(checkpoint)

            store = FailingCommitStore(path, source_dataset_sha256=SOURCE_HASH)
            first_pipeline = AsyncMock()
            first = ContinuousClosedCandleProcessor(
                ingestion=ingestion,
                checkpoint_store=store,
                pipeline=first_pipeline,
                code_version="checkpoint04.test",
            )
            with self.assertRaises(RuntimeError):
                await first.process(_candle(0))
            self.assertEqual(store.load().status, "PROCESSING")  # type: ignore[union-attr]

            second_pipeline = AsyncMock()
            second = ContinuousClosedCandleProcessor(
                ingestion=ingestion,
                checkpoint_store=FilesystemRuntimeCheckpointStore(
                    path, source_dataset_sha256=SOURCE_HASH
                ),
                pipeline=second_pipeline,
                code_version="checkpoint04.test",
            )
            self.assertEqual(
                await second.process(_candle(0)), RuntimeProcessingOutcome.PROCESSED
            )
            self.assertEqual(second.checkpoint.sequence, 1)  # type: ignore[union-attr]

    async def test_concurrent_delivery_serializes_and_persists_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            processor = _processor(Path(directory) / "checkpoint.json", pipeline)
            results = await __import__("asyncio").gather(
                processor.process(_candle(0)), processor.process(_candle(0))
            )
            self.assertEqual(
                sorted(results),
                sorted(
                    [RuntimeProcessingOutcome.PROCESSED, RuntimeProcessingOutcome.DUPLICATE]
                ),
            )
            self.assertEqual(pipeline.await_count, 1)

    def test_checkpoint_corruption_fails_closed(self) -> None:
        from app.live_market_data import RuntimeCheckpointError

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            path.write_text("{not-json", encoding="utf-8")
            store = FilesystemRuntimeCheckpointStore(path, source_dataset_sha256=SOURCE_HASH)
            with self.assertRaises(RuntimeCheckpointError):
                store.load()
