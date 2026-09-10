"""Verify the runtime pipeline is scheduled and executed after each 5m persist."""

from datetime import datetime, timedelta, timezone
import asyncio
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.live_market_data import BinanceKlineParser, build_market_snapshot
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
    def _snapshot(self):
        candle = BinanceKlineParser().parse(_message(START, "5m"))
        assert candle is not None
        return build_market_snapshot(candle, code_version="git:test")

    def _pipeline_service(self):
        return _PipelineAwareLiveMarketIngestionService(
            repository=MarketSnapshotMemoryRepository(),
            code_version="git:test",
        )

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

    async def test_pipeline_task_lifecycle_logs_include_snapshot_id(self) -> None:
        import app.prediction_api as prediction_api

        snapshot = self._snapshot()
        original = prediction_api._runtime_pipeline
        fake_pipeline = AsyncMock()
        fake_pipeline.run_for_snapshot = AsyncMock(
            return_value=SimpleNamespace(
                outcome=SimpleNamespace(value="NO_CANDIDATE")
            )
        )
        prediction_api._runtime_pipeline = fake_pipeline
        try:
            with self.assertLogs("alphalens.prediction_api", level="INFO") as captured:
                self._pipeline_service()._schedule_pipeline(snapshot)
                while any(not task.done() for task in _pipeline_tasks):
                    await asyncio.sleep(0)
        finally:
            prediction_api._runtime_pipeline = original

        messages = captured.output
        self.assertTrue(any("pipeline_task_scheduled" in line for line in messages))
        self.assertTrue(any("pipeline_task_started" in line for line in messages))
        self.assertTrue(any("pipeline_task_finished" in line for line in messages))
        for line in messages:
            if any(
                marker in line
                for marker in (
                    "pipeline_task_scheduled",
                    "pipeline_task_started",
                    "pipeline_task_finished",
                )
            ):
                self.assertIn(snapshot.snapshot_id, line)
        await asyncio.sleep(0)
        self.assertFalse(any(task.done() for task in _pipeline_tasks))

    async def test_pipeline_task_crash_logs_snapshot_id(self) -> None:
        import app.prediction_api as prediction_api

        snapshot = self._snapshot()
        original = prediction_api._runtime_pipeline
        fake_pipeline = AsyncMock()
        fake_pipeline.run_for_snapshot = AsyncMock(
            side_effect=RuntimeError("test pipeline failure")
        )
        prediction_api._runtime_pipeline = fake_pipeline
        try:
            with self.assertLogs("alphalens.prediction_api", level="ERROR") as captured:
                self._pipeline_service()._schedule_pipeline(snapshot)
                while any(not task.done() for task in _pipeline_tasks):
                    await asyncio.sleep(0)
        finally:
            prediction_api._runtime_pipeline = original

        self.assertTrue(any("pipeline_task_crashed" in line for line in captured.output))
        self.assertTrue(any(snapshot.snapshot_id in line for line in captured.output))

    async def test_pipeline_task_cancellation_logs_and_reraises(self) -> None:
        import app.prediction_api as prediction_api

        snapshot = self._snapshot()
        wait_forever = asyncio.Event()

        async def block(*args, **kwargs):
            await wait_forever.wait()

        original = prediction_api._runtime_pipeline
        fake_pipeline = AsyncMock()
        fake_pipeline.run_for_snapshot = AsyncMock(side_effect=block)
        prediction_api._runtime_pipeline = fake_pipeline
        try:
            with self.assertLogs("alphalens.prediction_api", level="INFO") as captured:
                self._pipeline_service()._schedule_pipeline(snapshot)
                await asyncio.sleep(0)
                task = next(
                    task
                    for task in _pipeline_tasks
                    if snapshot.snapshot_id in task.get_name()
                )
                self.assertFalse(task.done())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        finally:
            prediction_api._runtime_pipeline = original

        self.assertTrue(any("pipeline_task_cancelled" in line for line in captured.output))
        self.assertTrue(any(snapshot.snapshot_id in line for line in captured.output))

    async def test_pipeline_task_create_failure_logs_snapshot_id(self) -> None:
        import app.prediction_api as prediction_api

        snapshot = self._snapshot()
        with patch(
                "app.prediction_api.asyncio.create_task",
                side_effect=RuntimeError("task creation failed"),
            ):
            with self.assertLogs("alphalens.prediction_api", level="ERROR") as captured:
                with self.assertRaisesRegex(RuntimeError, "task creation failed"):
                    self._pipeline_service()._schedule_pipeline(snapshot)

        self.assertTrue(
            any("pipeline_task_create_failed" in line for line in captured.output)
        )
        self.assertTrue(any(snapshot.snapshot_id in line for line in captured.output))

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
