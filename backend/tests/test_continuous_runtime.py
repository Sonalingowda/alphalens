"""Offline continuous-runtime, checkpoint, and recovery tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from app.live_market_data import (
    BinanceWebSocketClient,
    BoundedCheckpointCatchUp,
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


def _processor_with_recovery(
    path: Path,
    pipeline: AsyncMock,
    recovery,
    max_recoverable_gap_intervals: int = 3,
) -> ContinuousClosedCandleProcessor:
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
        gap_recovery=recovery,
        max_recoverable_gap_intervals=max_recoverable_gap_intervals,
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

    async def test_bounded_rest_gap_recovery_processes_missing_candles_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            recovery = AsyncMock(return_value=[_candle(1)])
            processor = _processor_with_recovery(
                Path(directory) / "checkpoint.json", pipeline, recovery
            )

            await processor.process(_candle(0))
            self.assertEqual(
                await processor.process(_candle(2)), RuntimeProcessingOutcome.PROCESSED
            )
            recovery.assert_awaited_once_with(
                START + timedelta(minutes=5), START + timedelta(minutes=5)
            )
            self.assertEqual(pipeline.await_count, 3)
            self.assertEqual(processor.checkpoint.sequence, 3)  # type: ignore[union-attr]
            self.assertEqual(processor.health.gap_status, "CLEAR")

    async def test_oversized_gap_remains_quarantined_without_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            recovery = AsyncMock()
            processor = _processor_with_recovery(
                Path(directory) / "checkpoint.json", pipeline, recovery
            )
            await processor.process(_candle(0))

            result = await processor.process(_candle(5))

            self.assertEqual(result, RuntimeProcessingOutcome.QUARANTINED)
            recovery.assert_not_awaited()
            self.assertEqual(processor.health.gap_status, "QUARANTINED")

    async def test_bounded_recovery_replays_multi_hour_gap_before_newer_candle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            missing = [_candle(index) for index in range(1, 59)]
            recovery = AsyncMock(return_value=missing)
            processor = _processor_with_recovery(
                Path(directory) / "checkpoint.json",
                pipeline,
                recovery,
                max_recoverable_gap_intervals=120,
            )

            await processor.process(_candle(0))
            result = await processor.process(_candle(59))

            self.assertEqual(result, RuntimeProcessingOutcome.PROCESSED)
            recovery.assert_awaited_once_with(
                START + timedelta(minutes=5),
                START + timedelta(minutes=58 * 5),
            )
            self.assertEqual(processor.checkpoint.sequence, 60)  # type: ignore[union-attr]
            self.assertEqual(
                processor.checkpoint.last_committed_open_time,  # type: ignore[union-attr]
                _candle(59).open_time,
            )
            self.assertEqual(pipeline.await_count, 60)

    async def test_invalid_recovery_range_quarantines_without_processing_future_candle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            recovery = AsyncMock(return_value=[_candle(2)])
            processor = _processor_with_recovery(
                Path(directory) / "checkpoint.json", pipeline, recovery, 120
            )

            await processor.process(_candle(0))
            result = await processor.process(_candle(3))

            self.assertEqual(result, RuntimeProcessingOutcome.QUARANTINED)
            self.assertEqual(pipeline.await_count, 1)
            self.assertEqual(
                processor.checkpoint.last_committed_open_time,  # type: ignore[union-attr]
                _candle(0).open_time,
            )

    async def test_stale_checkpoint_catch_up_uses_120_120_54_verified_batches(self) -> None:
        """A 294-interval stale checkpoint is replayed only in bounded batches."""
        with tempfile.TemporaryDirectory() as directory:
            pipeline = AsyncMock()
            processor = _processor(Path(directory) / "checkpoint.json", pipeline)
            await processor.process(_candle(0))
            self.assertEqual(
                await processor.process(_candle(294)),
                RuntimeProcessingOutcome.QUARANTINED,
            )

            all_candles = [_candle(index) for index in range(1, 295)]
            requested_ranges: list[tuple[datetime, datetime]] = []
            verified_batch_sizes: list[int] = []

            async def recover(start: datetime, end: datetime) -> list[CompletedCandle]:
                requested_ranges.append((start, end))
                return [
                    candle
                    for candle in all_candles
                    if start <= candle.open_time <= end
                ]

            async def verify(batch: tuple[CompletedCandle, ...]) -> None:
                verified_batch_sizes.append(len(batch))
                self.assertEqual(
                    [candle.open_time for candle in batch],
                    [
                        batch[0].open_time + timedelta(minutes=5 * index)
                        for index in range(len(batch))
                    ],
                )

            catch_up = BoundedCheckpointCatchUp(
                processor=processor,
                recovery=recover,
                batch_verifier=verify,
            )
            result = await catch_up.recover_to(_candle(294).open_time)

            self.assertEqual(verified_batch_sizes, [120, 120, 54])
            self.assertEqual(len(requested_ranges), 3)
            self.assertEqual(result.processed_candles, 294)
            self.assertEqual(
                result.batch_ranges,
                (
                    (_candle(1).open_time, _candle(120).open_time),
                    (_candle(121).open_time, _candle(240).open_time),
                    (_candle(241).open_time, _candle(294).open_time),
                ),
            )
            self.assertEqual(
                processor.checkpoint.last_committed_open_time,  # type: ignore[union-attr]
                _candle(294).open_time,
            )
            self.assertEqual(processor.checkpoint.status, "READY")  # type: ignore[union-attr]
            self.assertEqual(pipeline.await_count, 295)

    async def test_stale_checkpoint_catch_up_restarts_from_durable_error_boundary(self) -> None:
        """An interrupted pipeline is retried from its durable in-flight candle."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            repository = MarketSnapshotMemoryRepository()
            ingestion = LiveMarketIngestionService(
                repository=repository,
                code_version="checkpoint04.test",
                rest_base_url="http://127.0.0.1:9",
                rest_fallback_urls=(),
            )
            first_pipeline = AsyncMock(side_effect=[None, RuntimeError("interrupted")])
            first = ContinuousClosedCandleProcessor(
                ingestion=ingestion,
                checkpoint_store=FilesystemRuntimeCheckpointStore(
                    path, source_dataset_sha256=SOURCE_HASH
                ),
                pipeline=first_pipeline,
                code_version="checkpoint04.test",
            )
            await first.process(_candle(0))
            with self.assertRaises(RuntimeError):
                await first.process(_candle(1))
            self.assertEqual(first.checkpoint.status, "ERROR")  # type: ignore[union-attr]

            second_pipeline = AsyncMock()
            second = ContinuousClosedCandleProcessor(
                ingestion=ingestion,
                checkpoint_store=FilesystemRuntimeCheckpointStore(
                    path, source_dataset_sha256=SOURCE_HASH
                ),
                pipeline=second_pipeline,
                code_version="checkpoint04.test",
            )
            requested_starts: list[datetime] = []

            async def recover(start: datetime, end: datetime) -> list[CompletedCandle]:
                requested_starts.append(start)
                return [_candle(index) for index in range(1, 4)]

            async def verify(batch: tuple[CompletedCandle, ...]) -> None:
                self.assertEqual(len(batch), 3)

            result = await BoundedCheckpointCatchUp(
                processor=second,
                recovery=recover,
                batch_verifier=verify,
            ).recover_to(_candle(3).open_time)

            self.assertEqual(requested_starts, [_candle(1).open_time])
            self.assertEqual(result.processed_candles, 3)
            self.assertEqual(
                second.checkpoint.last_committed_open_time,  # type: ignore[union-attr]
                _candle(3).open_time,
            )
            self.assertEqual(second_pipeline.await_count, 3)

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
