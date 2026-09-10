"""Opt-in local replay through the production live-ingestion pipeline.

This script is deliberately bounded and diagnostic.  It uses the production
``_PipelineAwareLiveMarketIngestionService`` instance, PostgreSQL repositories,
and ``asyncio.create_task`` scheduler from ``app.prediction_api``.  The input
message is a deterministic fixture, not real market data.  It never connects
to a production/staging environment.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys

from sqlalchemy import text

from app.live_market_data import BinanceKlineParser, CompletedCandle, build_market_snapshot
from app.market_data.history import HistoricalSample
from app.market_data.models import CandleTimeframe
from app.market_data.models import Candle
from app.market_data.validation import validate_candles
from app.persistence.candles import persist_historical_sample


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "backend/scripts/fixtures/binance_btcusdt_5m_closed.json"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-count", type=int, default=200)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--offset-minutes", type=int, default=0)
    return parser.parse_args()


def _load_fixture(path: Path, offset_minutes: int) -> tuple[str, CompletedCandle]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    offset_ms = offset_minutes * 60 * 1000
    payload["data"]["E"] += offset_ms
    payload["data"]["k"]["t"] += offset_ms
    payload["data"]["k"]["T"] += offset_ms
    raw = json.dumps(payload)
    candle = BinanceKlineParser().parse(raw)
    if candle is None:
        raise RuntimeError("Replay fixture is not a closed candle.")
    return raw, candle


def _history_snapshot(index: int, start: datetime):
    timestamp = start + timedelta(minutes=5 * index)
    base = Decimal(10_000 + index)
    candle = CompletedCandle(
        provider="binance_spot",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=timestamp + timedelta(minutes=5),
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=5) - timedelta(milliseconds=1),
        open=base,
        high=base + Decimal(5),
        low=base - Decimal(5),
        close=base + Decimal(1),
        volume=Decimal(10 + index),
        number_of_trades=100 + index,
        source_payload_hash=(f"{index:064x}"[-64:]),
    )
    return build_market_snapshot(candle, code_version="local-replay-fixture")


async def _counts(
    snapshot_id: str,
    signal_timestamp: datetime,
    valid_until: datetime,
) -> dict[str, int]:
    from app.persistence.database import session_factory

    predicates = {
        "market_snapshot": "canonical_payload->>'snapshot_id' = :snapshot_id",
        "feature_snapshot": (
            "canonical_payload->'market_snapshot'->>'artifact_id' = :snapshot_id"
        ),
        "all_runtime_aggregates": "canonical_payload::text LIKE :needle",
    }
    result: dict[str, int] = {}
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT entity_type, entity_id "
                    "FROM immutable_runtime_aggregates "
                    "WHERE canonical_payload::text LIKE :needle "
                    "ORDER BY entity_type, entity_id"
                ),
                {"needle": f"%{snapshot_id}%"},
            )
        ).all()
        result["aggregate_entities"] = [
            {"entity_type": entity_type, "entity_id": entity_id}
            for entity_type, entity_id in rows
        ]
        type_rows = (
            await session.execute(
                text(
                    "SELECT entity_type, count(*) "
                    "FROM immutable_runtime_aggregates "
                    "GROUP BY entity_type ORDER BY entity_type"
                )
            )
        ).all()
        result["aggregate_type_counts"] = {
            entity_type: count for entity_type, count in type_rows
        }
        outcome_rows = (
            await session.execute(
                text(
                    "SELECT canonical_payload->>'outcome', "
                    "canonical_payload->>'candles_evaluated', "
                    "canonical_payload->>'data_quality' "
                    "FROM immutable_runtime_aggregates "
                    "WHERE entity_type LIKE '%OutcomeRecord'"
                )
            )
        ).all()
        result["outcomes"] = [
            {
                "outcome": outcome,
                "candles_evaluated": candles_evaluated,
                "data_quality": data_quality,
            }
            for outcome, candles_evaluated, data_quality in outcome_rows
        ]
        for name, predicate in predicates.items():
            params = {
                "snapshot_id": snapshot_id,
                "needle": f"%{snapshot_id}%",
            }
            result[name] = int(
                await session.scalar(
                    text(
                        "SELECT count(*) FROM immutable_runtime_aggregates "
                        f"WHERE {predicate}"
                    ),
                    params,
                )
                or 0
            )
        result["candle_rows_at_snapshot"] = int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM market_data_candles "
                    "WHERE timeframe = '5m' AND candle_timestamp = "
                    ":candle_timestamp"
                ),
                {"candle_timestamp": datetime.fromtimestamp(
                    1788956400, tz=timezone.utc
                )},
            )
            or 0
        )
        candle_rows = (
            await session.execute(
                text(
                    "SELECT id, asset_identifier, quote_currency, timeframe, "
                    "candle_timestamp, open_price, high_price, low_price, "
                    "close_price, volume, provider, is_complete, "
                    "ingestion_batch_id "
                    "FROM market_data_candles "
                    "WHERE asset_identifier = 'BTCUSDT' AND timeframe = '5m' "
                    "AND candle_timestamp > :signal_timestamp "
                    "AND candle_timestamp <= :valid_until "
                    "ORDER BY candle_timestamp"
                ),
                {
                    "signal_timestamp": signal_timestamp,
                    "valid_until": valid_until,
                },
            )
        ).mappings().all()
        result["candle_rows_in_expected_window"] = [dict(row) for row in candle_rows]
        outcome_payload = (
            await session.execute(
                text(
                    "SELECT canonical_payload FROM immutable_runtime_aggregates "
                    "WHERE entity_type LIKE '%OutcomeRecord' "
                    "AND canonical_payload->>'opportunity_id' LIKE "
                    "'opportunity.runtime_ema_rsi.candidate.runtime_detection_ema_rsi.BTCUSDT.5m.178904%' "
                    "ORDER BY available_at DESC LIMIT 1"
                )
            )
        ).scalar_one_or_none()
        result["outcome_record"] = outcome_payload
    return result


async def _run_one_lifecycle_sweep(prediction_api) -> None:
    """Exercise the production sweep once without waiting sixty seconds."""
    original_interval = prediction_api._SWEEP_INTERVAL_SECONDS
    prediction_api._SWEEP_INTERVAL_SECONDS = 0.1
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        prediction_api._run_lifecycle_sweep(stop_event),
        name="local-replay-lifecycle-sweep",
    )
    try:
        await asyncio.sleep(0.5)
    finally:
        stop_event.set()
        await task
        prediction_api._SWEEP_INTERVAL_SECONDS = original_interval


async def _seed_historical_outcome_candle(fixture_candle: CompletedCandle) -> dict[str, object]:
    from app.persistence.database import session_factory

    candle_timestamp = fixture_candle.open_time + timedelta(minutes=10)
    candle = Candle(
        timestamp=candle_timestamp,
        open=Decimal("10201.000000000000000000"),
        high=Decimal("10220.000000000000000000"),
        low=Decimal("10200.000000000000000000"),
        close=Decimal("10215.000000000000000000"),
        volume=Decimal("210.000000000000000000"),
    )
    sample = HistoricalSample(
        provider="binance_spot",
        asset_identifier="BTCUSDT",
        quote_currency="USDT",
        timeframe=CandleTimeframe.MINUTE_5,
        requested_start=candle_timestamp,
        requested_end_exclusive=candle_timestamp + timedelta(minutes=5),
        retrieved_at=fixture_candle.event_time,
        candles=(candle,),
        validation_report=validate_candles(
            candles=(candle,),
            timeframe=CandleTimeframe.MINUTE_5,
            expected_start=candle_timestamp,
            expected_end=candle_timestamp + timedelta(minutes=5),
        ),
    )
    if not sample.validation_report.passed:
        raise RuntimeError(f"Historical replay candle failed validation: {sample.validation_report.issues}")
    async with session_factory() as session:
        result = await persist_historical_sample(session, sample)
        candle_id = await session.scalar(
            text(
                "SELECT id FROM market_data_candles "
                "WHERE asset_identifier = :asset_identifier "
                "AND quote_currency = :quote_currency "
                "AND timeframe = :timeframe "
                "AND candle_timestamp = :candle_timestamp"
            ),
            {
                "asset_identifier": sample.asset_identifier,
                "quote_currency": sample.quote_currency,
                "timeframe": sample.timeframe.value,
                "candle_timestamp": candle.timestamp,
            },
        )
    return {
        "id": candle_id,
        "asset_identifier": sample.asset_identifier,
        "quote_currency": sample.quote_currency,
        "timeframe": sample.timeframe.value,
        "candle_timestamp": candle.timestamp,
        "open_price": candle.open,
        "high_price": candle.high,
        "low_price": candle.low,
        "close_price": candle.close,
        "volume": candle.volume,
        "provider": sample.provider,
        "persisted_candle_count": result.persisted_candle_count,
        "ingestion_batch_id": str(result.ingestion_batch_id),
    }


async def _run(history_count: int, fixture_path: Path, offset_minutes: int) -> None:
    from app import prediction_api

    if prediction_api.settings.environment in {"production", "staging"}:
        raise SystemExit("Refusing to run with production/staging settings.")
    if history_count < 30 or history_count > 500:
        raise SystemExit("--history-count must be between 30 and 500.")

    raw, fixture_candle = _load_fixture(fixture_path, offset_minutes)
    history_start = fixture_candle.open_time - timedelta(minutes=5 * history_count)
    snapshots = tuple(
        _history_snapshot(index, history_start) for index in range(history_count)
    )
    await prediction_api.market_snapshot_repository.save_batch(snapshots)
    seeded_candle = await _seed_historical_outcome_candle(fixture_candle)
    await prediction_api.live_market_ingestion.initialize(fixture_candle.open_time)

    await prediction_api.live_market_ingestion.process_message(raw)
    target_id = (
        f"binance.spot.BTCUSDT.5m."
        f"{int(fixture_candle.open_time.timestamp() * 1000)}.snapshot"
    )
    for _ in range(600):
        matching = [
            task for task in prediction_api._pipeline_tasks
            if target_id in task.get_name()
        ]
        if matching:
            await asyncio.gather(*matching)
            break
        await asyncio.sleep(0.01)
    else:
        raise RuntimeError("No scheduled pipeline task was observed for fixture.")

    await _run_one_lifecycle_sweep(prediction_api)
    signal_timestamp = fixture_candle.event_time
    valid_until = signal_timestamp + timedelta(minutes=10)
    evidence = await _counts(target_id, signal_timestamp, valid_until)
    print(json.dumps({
        "fixture": str(fixture_path),
        "fixture_is_real_market_data": False,
        "snapshot_id": target_id,
        "history_snapshots_seeded": history_count,
        "seeded_historical_candle": seeded_candle,
        "pipeline_task_observed": True,
        "persisted_evidence": evidence,
    }, indent=2, sort_keys=True, default=str))


def main() -> None:
    arguments = _arguments()
    asyncio.run(_run(arguments.history_count, arguments.fixture, arguments.offset_minutes))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "backend"))
    main()
