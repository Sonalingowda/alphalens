"""Always-on local BTCUSDT/5m worker for the private localhost product."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import signal
import tempfile

from app.live_market_data import (
    BinanceKlineParser,
    BinanceWebSocketClient,
    ContinuousClosedCandleProcessor,
    FilesystemRuntimeCheckpointStore,
    LiveMarketIngestionService,
)
from app.market_data.models import CandleTimeframe
from app.persistence.database import session_factory
from app.opportunity_intelligence.persistence import MarketSnapshotPostgreSQLRepository
from app.thesis_intelligence import ThesisIntelligenceService
from app.runtime_pipeline import build_runtime_pipeline


PROTECTED_START = datetime(2027, 1, 11, tzinfo=timezone.utc)
PROTECTED_END = datetime(2027, 2, 10, tzinfo=timezone.utc)
logger = logging.getLogger("alphalens.local_market_worker")


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
    parser.add_argument("--warmup-limit", type=int, default=250)
    args = parser.parse_args()

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
    )
    parser_impl = BinanceKlineParser()

    def write_status(worker_status: str, last_error: str | None = None) -> None:
        _write_json(
            args.status,
            {
                "worker_status": worker_status,
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
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    write_status("STARTING")
    try:
        if args.warmup_limit < 200:
            raise ValueError("Local warmup must retain at least 200 closed candles.")
        await ingestion.warmup_history_with_retry(limit=args.warmup_limit)
        write_status("WARMED")
    except Exception as error:  # noqa: BLE001 - status remains observable
        write_status("WARMUP_FAILED", type(error).__name__)
        logger.exception("local_warmup_failed")
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
        write_status("STOPPED")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

