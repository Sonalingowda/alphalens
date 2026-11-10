"""Always-on local BTCUSDT/5m worker for the private localhost product."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import fcntl
import json
import logging
import os
from pathlib import Path
import signal
import tempfile
from uuid import uuid4

from app.live_market_data import (
    BinanceKlineParser,
    BinanceWebSocketClient,
    BoundedCheckpointCatchUp,
    CompletedCandle,
    ContinuousClosedCandleProcessor,
    FilesystemRuntimeCheckpointStore,
    LiveMarketIngestionService,
)
from app.live_market_data.warmup import (
    AcceptedWarmupCheckpointStore,
    reconcile_warmup_checkpoint,
)
from app.market_data.models import CandleTimeframe
from app.persistence.database import session_factory
from app.opportunity_intelligence.persistence import MarketSnapshotPostgreSQLRepository
from app.thesis_intelligence import ThesisIntelligenceService
from app.runtime_pipeline import build_runtime_pipeline


PROTECTED_START = datetime(2027, 1, 11, tzinfo=timezone.utc)
PROTECTED_END = datetime(2027, 2, 10, tzinfo=timezone.utc)
logger = logging.getLogger("alphalens.local_market_worker")
DEFAULT_MAX_RECOVERABLE_GAP_INTERVALS = 120
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0


class WorkerOwnershipError(RuntimeError):
    """Raised when another local worker owns the checkpoint stream."""


class WorkerOwnershipLock:
    """A process-scoped advisory lock that survives stale lock files safely."""

    def __init__(self, checkpoint: Path) -> None:
        self.path = checkpoint.with_name(f".{checkpoint.name}.worker.lock")
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self._handle.close()
            self._handle = None
            raise WorkerOwnershipError(
                f"Another AlphaLens worker owns checkpoint {self.path}."
            ) from error
        self._handle.seek(0)
        self._handle.truncate()
        json.dump({"pid": os.getpid(), "checkpoint": str(self.path)}, self._handle)
        self._handle.write("\n")
        self._handle.flush()

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
    Path(handle.name).replace(path)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--heartbeat-interval-seconds",
        type=float,
        default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    )
    parser.add_argument("--warmup-limit", type=int, default=250)
    parser.add_argument(
        "--max-recoverable-gap-intervals",
        type=int,
        default=DEFAULT_MAX_RECOVERABLE_GAP_INTERVALS,
    )
    args = parser.parse_args()
    if not 1 <= args.max_recoverable_gap_intervals <= 120:
        raise ValueError("Maximum recoverable gap must be between 1 and 120 intervals.")
    if args.heartbeat_interval_seconds <= 0:
        raise ValueError("Heartbeat interval must be positive.")
    run_id = args.run_id or uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    ownership = WorkerOwnershipLock(args.checkpoint)
    ownership.acquire()

    stop_event = asyncio.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(signum, stop_event.set)

    repository = MarketSnapshotPostgreSQLRepository(session_factory)
    pipeline = build_runtime_pipeline(session_factory)
    thesis_service = ThesisIntelligenceService(session_factory)
    counters: dict[str, int] = {}

    def increment(name: str) -> None:
        counters[name] = counters.get(name, 0) + 1

    async def run_pipeline(snapshot, as_of):
        result = await pipeline.run_for_snapshot(snapshot, as_of)
        increment("pipeline_runs")
        if result is not None and result.opportunity is not None:
            match = await thesis_service.attach_assessment(result.opportunity)
            increment(f"thesis_match:{match.status}")
        candle = snapshot.candles[-1]
        await thesis_service.observe_candle(
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "provenance": candle.source_reference.artifact_id,
            }
        )
        return result

    ingestion = LiveMarketIngestionService(
        repository=repository,
        code_version="alphalens.local.product.1.0.0",
        rest_base_url="https://data-api.binance.vision",
        rest_fallback_urls=(),
        warmup_lineage_id=args.source_identity,
        warmup_checkpoint_store=AcceptedWarmupCheckpointStore(
            args.checkpoint.with_name(f"{args.checkpoint.stem}.warmup.json")
        ),
        client=BinanceWebSocketClient(
            stream_timeframes=(CandleTimeframe.MINUTE_5,),
            heartbeat_timeout_seconds=90.0,
            backoff_initial_seconds=1.0,
            backoff_max_seconds=30.0,
        ),
    )
    processor = ContinuousClosedCandleProcessor(
        ingestion=ingestion,
        checkpoint_store=FilesystemRuntimeCheckpointStore(
            args.checkpoint,
            source_dataset_sha256=args.source_identity,
        ),
        pipeline=run_pipeline,
        code_version="alphalens.local.product.1.0.0",
        retry_attempts=3,
        retry_backoff_seconds=1.0,
        gap_recovery=ingestion.recover_closed_candle_gap,
        max_recoverable_gap_intervals=args.max_recoverable_gap_intervals,
    )
    parser_impl = BinanceKlineParser()

    current_status = "STARTING"
    current_error: str | None = None
    heartbeat_task: asyncio.Task[None] | None = None

    def write_status(worker_status: str, last_error: str | None = None) -> None:
        nonlocal current_status, current_error
        current_status = worker_status
        current_error = last_error
        now = datetime.now(timezone.utc).isoformat()
        _write_json(
            args.status,
            {
                "worker_status": worker_status,
                "run_id": run_id,
                "pid": os.getpid(),
                "started_at": started_at,
                "heartbeat_at": now,
                "checkpoint_path": str(args.checkpoint.resolve()),
                "source_identity": args.source_identity,
                "symbol": "BTCUSDT",
                "timeframe": "5m",
                "closed_candles_only": True,
                "source": "Binance public market-data WebSocket",
                "checkpoint": processor.health.to_dict(),
                "connection": asdict(ingestion.client.health()),
                "counters": counters,
                "model_artifact_status": "UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT",
                "external_notifications": False,
                "trading": False,
                "last_error": last_error,
                "updated_at": now,
            },
        )

    async def heartbeat() -> None:
        while not stop_event.is_set():
            await asyncio.sleep(args.heartbeat_interval_seconds)
            if not stop_event.is_set():
                write_status(current_status, current_error)

    async def verify_recovery_batch(batch: tuple[CompletedCandle, ...]) -> None:
        """Verify that every recovered batch is genuine Binance closed data."""
        now = datetime.now(timezone.utc)
        previous = None
        for candle in batch:
            if candle.provider != "binance_spot":
                raise ValueError("Recovery batch contains a non-Binance candle.")
            if candle.symbol != "BTCUSDT" or candle.timeframe is not CandleTimeframe.MINUTE_5:
                raise ValueError("Recovery batch contains an unsupported candle scope.")
            if candle.close_time >= now or candle.event_time < candle.close_time:
                raise ValueError("Recovery batch contains an open or incomplete candle.")
            if previous is not None and candle.open_time != previous + timedelta(minutes=5):
                raise ValueError("Recovery batch is not chronologically contiguous.")
            previous = candle.open_time

    async def recover_startup_gap() -> None:
        checkpoint = processor.checkpoint
        if checkpoint is None or checkpoint.last_committed_open_time is None:
            return
        latest = await ingestion.latest_closed_candle()
        if latest.open_time <= checkpoint.last_committed_open_time:
            return
        write_status("RECOVERING")
        result = await BoundedCheckpointCatchUp(
            processor=processor,
            recovery=ingestion.recover_closed_candle_gap,
            batch_verifier=verify_recovery_batch,
            max_batch_intervals=args.max_recoverable_gap_intervals,
        ).recover_to(latest.open_time)
        increment("recovery_batches", len(result.batch_ranges))
        increment("recovery_candles", result.processed_candles)

    write_status("STARTING")
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        if args.warmup_limit < 200:
            raise ValueError("Local warmup must retain at least 200 closed candles.")
        warmup_store = ingestion.warmup_checkpoint_store
        if warmup_store is None:
            raise RuntimeError("Warmup checkpoint store is not configured.")
        reconcile_warmup_checkpoint(
            warmup_store,
            await repository.get_accepted_binance_warmup_checkpoint(args.source_identity),
        )
        await ingestion.warmup_history_with_retry(limit=args.warmup_limit)
        write_status("WARMED")
        await recover_startup_gap()
        write_status("WARMED")
    except Exception as error:  # noqa: BLE001 - status remains observable
        write_status("RECOVERY_FAILED", type(error).__name__)
        logger.exception("local_startup_recovery_failed")
        assert heartbeat_task is not None
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        ownership.release()
        raise

    async def handle_message(raw_message: str | bytes) -> None:
        try:
            candle = parser_impl.parse(raw_message)
        except Exception as error:  # noqa: BLE001 - quarantine malformed input
            increment(f"parse_error:{type(error).__name__}")
            write_status("RUNNING", type(error).__name__)
            return
        if candle is None:
            increment("incomplete_updates")
            return
        if candle.timeframe is not CandleTimeframe.MINUTE_5:
            increment("unsupported_timeframe")
            return
        if PROTECTED_START <= candle.open_time < PROTECTED_END:
            write_status("STOPPED_PROTECTED_WINDOW", "protected_test_window")
            stop_event.set()
            raise RuntimeError("Protected-test candle encountered.")
        increment("finalized_candles")
        try:
            outcome = await processor.process_with_retry(candle)
            increment(f"processor:{outcome.value}")
            write_status("RUNNING")
        except Exception as error:  # noqa: BLE001 - supervisor handles reconnect
            increment(f"processing_error:{type(error).__name__}")
            write_status("PROCESSING_ERROR", type(error).__name__)
            raise

    write_status("RUNNING")
    try:
        await ingestion.client.run(handle_message, stop_event)
    finally:
        assert heartbeat_task is not None
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        write_status("STOPPED")
        ownership.release()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

