"""Bounded public Binance BTCUSDT/5m finalized-candle trial.

Operational evidence only. This runner never uses private exchange endpoints,
never places orders, and refuses any candle in the frozen protected-test
window. It intentionally does not perform historical backfill.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

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
from app.runtime_pipeline import build_runtime_pipeline


PROTECTED_START = datetime(2027, 1, 11, tzinfo=timezone.utc)
PROTECTED_END = datetime(2027, 2, 10, tzinfo=timezone.utc)
WS_ENDPOINT = "wss://data-stream.binance.vision"
TRIAL_IDENTITY = "alphalens.batch6t.public.binance.btcusdt.5m.operational.v1"
TRIAL_SOURCE_IDENTITY_SHA256 = hashlib.sha256(TRIAL_IDENTITY.encode()).hexdigest()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--duration-seconds", type=float, default=86400.0)
    args = parser.parse_args()
    if args.duration_seconds <= 0 or args.duration_seconds > 86400:
        raise SystemExit("duration must be >0 and <=86400 seconds")

    started_at = datetime.now(timezone.utc)
    if PROTECTED_START <= started_at < PROTECTED_END:
        raise SystemExit("trial start is inside the protected-test window")

    repository = MarketSnapshotPostgreSQLRepository(session_factory)
    ingestion = LiveMarketIngestionService(
        repository=repository,
        code_version="alphalens.checkpoint04.live-trial.1.0.0",
        rest_base_url="http://127.0.0.1:9",
        rest_fallback_urls=(),
    )
    pipeline = build_runtime_pipeline(session_factory)
    counters: Counter[str] = Counter()
    outcomes: Counter[str] = Counter()

    async def run_pipeline(snapshot, as_of):
        result = await pipeline.run_for_snapshot(snapshot, as_of)
        counters["pipeline_runs"] += 1
        if result is None:
            outcomes["UNAVAILABLE"] += 1
        else:
            outcomes[result.outcome.value] += 1

    processor = ContinuousClosedCandleProcessor(
        ingestion=ingestion,
        checkpoint_store=FilesystemRuntimeCheckpointStore(
            args.checkpoint,
            source_dataset_sha256=TRIAL_SOURCE_IDENTITY_SHA256,
        ),
        pipeline=run_pipeline,
        code_version="alphalens.checkpoint04.live-trial.1.0.0",
        retry_attempts=3,
        retry_backoff_seconds=1.0,
    )
    parser_impl = BinanceKlineParser()
    client = BinanceWebSocketClient(
        base_url=WS_ENDPOINT,
        stream_timeframes=(CandleTimeframe.MINUTE_5,),
        heartbeat_timeout_seconds=90.0,
        backoff_initial_seconds=1.0,
        backoff_max_seconds=30.0,
    )
    stop_event = asyncio.Event()
    stop_reason = "duration_elapsed"

    async def stop_after_duration() -> None:
        await asyncio.sleep(args.duration_seconds)
        stop_event.set()

    async def handle_message(raw_message: str | bytes) -> None:
        nonlocal stop_reason
        counters["messages_received"] += 1
        try:
            candle = parser_impl.parse(raw_message)
        except Exception as error:  # noqa: BLE001 - record and quarantine input
            counters[f"parse_error:{type(error).__name__}"] += 1
            return
        if candle is None:
            counters["incomplete_updates"] += 1
            return
        if candle.timeframe is not CandleTimeframe.MINUTE_5:
            counters["unsupported_timeframe"] += 1
            return
        if PROTECTED_START <= candle.open_time < PROTECTED_END:
            stop_reason = "protected_window_violation"
            stop_event.set()
            raise RuntimeError("protected-test candle encountered; trial aborted")
        counters["finalized_candles"] += 1
        try:
            outcome = await processor.process_with_retry(candle)
        except Exception as error:  # noqa: BLE001 - preserve trial evidence
            counters[f"processing_error:{type(error).__name__}"] += 1
            stop_reason = f"processing_error:{type(error).__name__}"
            stop_event.set()
            return
        outcomes[f"processor:{outcome.value}"] += 1

    stopper = asyncio.create_task(stop_after_duration())
    try:
        await client.run(handle_message, stop_event)
    finally:
        stopper.cancel()
        try:
            await stopper
        except asyncio.CancelledError:
            pass
    ended_at = datetime.now(timezone.utc)
    payload = {
        "trial_identity": TRIAL_IDENTITY,
        "endpoint": WS_ENDPOINT,
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "closed_candles_only": True,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": (ended_at - started_at).total_seconds(),
        "requested_duration_seconds": args.duration_seconds,
        "protected_window": {
            "start": PROTECTED_START.isoformat(),
            "end_exclusive": PROTECTED_END.isoformat(),
        },
        "source_identity_sha256": TRIAL_SOURCE_IDENTITY_SHA256,
        "counters": dict(counters),
        "pipeline_outcomes": dict(outcomes),
        "checkpoint": (
            asdict(processor.checkpoint)
            if processor.checkpoint is not None
            else None
        ),
        "health": processor.health.to_dict(),
        "connection": asdict(client.health()),
        "model_artifact_status": "UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT",
        "external_notifications": False,
        "trading": False,
        "stop_reason": stop_reason,
    }
    args.report.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(payload, sort_keys=True, default=str))


if __name__ == "__main__":
    asyncio.run(main())
