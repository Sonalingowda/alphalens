"""Bounded genuine BTCUSDT/5m replay for Checkpoint 04.

This driver is diagnostic only. It verifies the continuous processor against
the retained immutable evidence and never requests Binance data, fits a model,
or treats a historical replay as a live trial.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from app.live_market_data import (
    ContinuousClosedCandleProcessor,
    FilesystemRuntimeCheckpointStore,
    LiveMarketIngestionService,
    RuntimeProcessingOutcome,
)
from app.live_market_data.service import _completed_candle_from_rest_kline
from app.persistence.database import session_factory
from app.runtime_pipeline import build_runtime_pipeline
from app.opportunity_intelligence.persistence import MarketSnapshotPostgreSQLRepository


EXPECTED_DATASET_SHA256 = (
    "f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc"
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--start-index", type=int, default=25069)
    parser.add_argument("--count", type=int, default=300)
    args = parser.parse_args()

    raw = args.dataset.read_bytes()
    dataset_sha256 = hashlib.sha256(raw).hexdigest()
    if dataset_sha256 != EXPECTED_DATASET_SHA256:
        raise SystemExit("dataset SHA-256 mismatch; replay aborted")
    document = json.loads(raw)
    if (
        document["symbol"] != "BTCUSDT"
        or document["timeframe"] != "5m"
        or len(document["klines"]) != 25_920
    ):
        raise SystemExit("dataset identity/count mismatch; replay aborted")

    rows = document["klines"][args.start_index : args.start_index + args.count]
    if len(rows) != args.count:
        raise SystemExit("bounded replay window is outside the retained dataset")
    candles = tuple(_completed_candle_from_rest_kline(row) for row in rows)

    repository = MarketSnapshotPostgreSQLRepository(session_factory)
    ingestion = LiveMarketIngestionService(
        repository=repository,
        code_version="alphalens.checkpoint04.replay.1.0.0",
        rest_base_url="http://127.0.0.1:9",
        rest_fallback_urls=(),
    )
    pipeline = build_runtime_pipeline(session_factory)
    results: list[RuntimeProcessingOutcome] = []

    async def run_pipeline(snapshot, as_of):
        result = await pipeline.run_for_snapshot(snapshot, as_of)
        results.append(result.outcome if result is not None else "UNAVAILABLE")

    processor = ContinuousClosedCandleProcessor(
        ingestion=ingestion,
        checkpoint_store=FilesystemRuntimeCheckpointStore(
            args.checkpoint, source_dataset_sha256=dataset_sha256
        ),
        pipeline=run_pipeline,
        code_version="alphalens.checkpoint04.replay.1.0.0",
    )

    processed_before_restart = args.count // 2
    counts: dict[str, int] = {}
    for index, candle in enumerate(candles):
        if index == processed_before_restart:
            processor = ContinuousClosedCandleProcessor(
                ingestion=LiveMarketIngestionService(
                    repository=repository,
                    code_version="alphalens.checkpoint04.replay.1.0.0",
                    rest_base_url="http://127.0.0.1:9",
                    rest_fallback_urls=(),
                ),
                checkpoint_store=FilesystemRuntimeCheckpointStore(
                    args.checkpoint, source_dataset_sha256=dataset_sha256
                ),
                pipeline=run_pipeline,
                code_version="alphalens.checkpoint04.replay.1.0.0",
            )
        outcome = await processor.process(candle)
        counts[outcome.value] = counts.get(outcome.value, 0) + 1
        if index == 20:
            duplicate = await processor.process(candle)
            counts[duplicate.value] = counts.get(duplicate.value, 0) + 1

    print(
        json.dumps(
            {
                "dataset_sha256": dataset_sha256,
                "start_index": args.start_index,
                "candle_count": args.count,
                "first_open_time": candles[0].open_time.isoformat(),
                "last_open_time": candles[-1].open_time.isoformat(),
                "outcomes": counts,
                "pipeline_outcomes": [
                    value.value if hasattr(value, "value") else value
                    for value in results
                ],
                "checkpoint": asdict(processor.checkpoint),
                "health": processor.health.to_dict(),
                "network_requests": 0,
                "run_at": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
