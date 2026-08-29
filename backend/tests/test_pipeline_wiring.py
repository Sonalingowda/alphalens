"""Verify the runtime pipeline is scheduled and executed after each 5m persist."""

from datetime import datetime, timedelta, timezone
import asyncio
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.live_market_data.models import CompletedCandle
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import MarketSnapshotMemoryRepository
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.prediction_api import (
    _PipelineAwareLiveMarketIngestionService,
    _pipeline_tasks,
)


START = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _scope_query(timeframe: str, *, limit: int = 20) -> ScopedRepositoryQuery:
    return ScopedRepositoryQuery(
        scope=MarketScope(instrument="BTCUSDT", timeframe=timeframe),
        as_of=START + timedelta(hours=1),
        limit=limit,
    )


def _message(
    start: datetime,
    interval: str,
    *,
    closed: bool = True,
    open_price: str = "100.00000000",
    high: str = "112.00000000",
    low: str = "95.00000000",
    close: str = "108.00000000",
    volume: str = "2.50000000",
    trades: int = 42,
    event_delay_milliseconds: int = 1,
) -> str:
    from json import dumps

    duration = {"5m": 5, "10m": 10, "15m": 15}[interval]
    close_time = start + timedelta(minutes=duration) - timedelta(milliseconds=1)
    event_time = close_time + timedelta(milliseconds=event_delay_milliseconds)
    payload = {
        "stream": f"btcusdt@kline_{interval}",
        "data": {
            "e": "kline",
            "E": int(event_time.timestamp() * 1000),
            "s": "BTCUSDT",
            "k": {
                "t": int(start.timestamp() * 1000),
                "T": int(close_time.timestamp() * 1000),
                "s": "BTCUSDT",
                "i": interval,
                "o": open_price,
                "c": close,
                "h": high,
                "l": low,
                "v": volume,
                "n": trades,
                "x": closed,
            },
        },
    }
    return dumps(payload, sort_keys=True, separators=(",", ":"))


def _derived_10m(start: datetime) -> CompletedCandle:
    return CompletedCandle(
        provider="alphalens_derived",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_10,
        event_time=start + timedelta(minutes=10),
        open_time=start,
        close_time=start + timedelta(minutes=10) - timedelta(milliseconds=1),
        open=Decimal("100"),
        high=Decimal("112"),
        low=Decimal("95"),
        close=Decimal("108"),
        volume=Decimal("2.5"),
        number_of_trades=42,
        source_payload_hash="a" * 64,
        source_candle_hashes=("b" * 64,),
    )


class PipelineWiringTest(IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        import asyncio

        for task in list(_pipeline_tasks):
            task.cancel()
        await asyncio.sleep(0)

    async def test_pipeline_scheduled_and_run_for_5m_candle(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = _PipelineAwareLiveMarketIngestionService(
            repository=repository,
            code_version="git:test",
        )
        await service.initialize(START)

        calls: list = []

        async def fake_run_for_snapshot(snapshot, as_of):
            calls.append(snapshot)
            return None

        import app.prediction_api as prediction_api

        original = prediction_api._runtime_pipeline
        fake_pipeline = AsyncMock()
        fake_pipeline.run_for_snapshot = AsyncMock(side_effect=fake_run_for_snapshot)
        prediction_api._runtime_pipeline = fake_pipeline
        try:
            await service.process_message(_message(START, "5m"))
            for _ in range(50):
                if calls:
                    break
                await asyncio.sleep(0.01)
            else:
                self.fail("pipeline run_for_snapshot was never invoked")
        finally:
            prediction_api._runtime_pipeline = original

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].scope.instrument, "BTCUSDT")
        self.assertEqual(calls[0].scope.timeframe, "5m")

    async def test_derived_10m_candle_invokes_pipeline_without_crash(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = _PipelineAwareLiveMarketIngestionService(
            repository=repository,
            code_version="git:test",
        )
        await service.initialize(START)

        calls: list = []

        async def fake_run_for_snapshot(snapshot, as_of):
            calls.append(snapshot)
            return None

        import app.prediction_api as prediction_api

        original = prediction_api._runtime_pipeline
        fake_pipeline = AsyncMock()
        fake_pipeline.run_for_snapshot = AsyncMock(side_effect=fake_run_for_snapshot)
        prediction_api._runtime_pipeline = fake_pipeline
        try:
            # 5m candle schedules a run; derived 10m candle also schedules a run
            # (scope-skipped internally by run_for_snapshot). Neither must crash.
            await service.process_message(_message(START, "5m"))
            await service._persist(_derived_10m(START))
            for _ in range(50):
                if len(calls) >= 2:
                    break
                await asyncio.sleep(0.01)
            else:
                self.fail("expected both 5m and 10m pipeline invocations")
        finally:
            prediction_api._runtime_pipeline = original

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].scope.timeframe, "5m")
        self.assertEqual(calls[1].scope.timeframe, "10m")


if __name__ == "__main__":
    import unittest

    unittest.main()
