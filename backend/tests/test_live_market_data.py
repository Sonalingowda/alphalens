"""Sprint 1 live Binance market ingestion tests."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import unittest

from app.live_market_data import (
    BinanceKlineParser,
    BinanceWebSocketClient,
    CandleGapDetector,
    LiveMarketDataConflictError,
    LiveMarketIngestionService,
    LiveMessageValidationError,
    TenMinuteCandleAggregator,
    build_market_snapshot,
)
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import MarketSnapshotMemoryRepository
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.opportunity_intelligence.services import MarketScannerService


START = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


class BinanceKlineParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = BinanceKlineParser()

    def test_completed_kline_parses_all_required_fields_in_utc(self) -> None:
        candle = self.parser.parse(_message(START, "5m"))

        self.assertIsNotNone(candle)
        assert candle is not None
        self.assertEqual(candle.symbol, "BTCUSDT")
        self.assertEqual(candle.timeframe, CandleTimeframe.MINUTE_5)
        self.assertEqual(candle.open_time, START)
        self.assertEqual(
            candle.close_time,
            START + timedelta(minutes=5) - timedelta(milliseconds=1),
        )
        self.assertEqual(str(candle.open), "100.00000000")
        self.assertEqual(str(candle.high), "112.00000000")
        self.assertEqual(str(candle.low), "95.00000000")
        self.assertEqual(str(candle.close), "108.00000000")
        self.assertEqual(str(candle.volume), "2.50000000")
        self.assertEqual(candle.number_of_trades, 42)
        self.assertEqual(len(candle.source_payload_hash), 64)

    def test_incomplete_update_is_not_a_completed_candle(self) -> None:
        self.assertIsNone(self.parser.parse(_message(START, "5m", closed=False)))

    def test_invalid_json_and_unsupported_interval_fail_closed(self) -> None:
        with self.assertRaises(LiveMessageValidationError):
            self.parser.parse("not-json")
        with self.assertRaisesRegex(LiveMessageValidationError, "native input"):
            self.parser.parse(_message(START, "10m"))

    def test_invalid_ohlc_relationship_fails_closed(self) -> None:
        with self.assertRaisesRegex(LiveMessageValidationError, "High"):
            self.parser.parse(_message(START, "5m", high="99.00000000"))

    def test_parser_is_deterministic(self) -> None:
        raw = _message(START, "15m")
        first = self.parser.parse(raw)
        second = self.parser.parse(raw)
        self.assertEqual(first, second)


class LiveProcessingTests(unittest.TestCase):
    def test_10m_aggregation_reuses_exact_two_5m_semantics(self) -> None:
        parser = BinanceKlineParser()
        first = parser.parse(
            _message(
                START,
                "5m",
                open_price="100.00000000",
                high="110.00000000",
                low="95.00000000",
                close="105.00000000",
                volume="1.10000000",
                trades=10,
            )
        )
        second = parser.parse(
            _message(
                START + timedelta(minutes=5),
                "5m",
                open_price="105.00000000",
                high="112.00000000",
                low="101.00000000",
                close="108.00000000",
                volume="2.20000000",
                trades=20,
            )
        )
        assert first is not None and second is not None
        aggregator = TenMinuteCandleAggregator()

        self.assertIsNone(aggregator.add(first))
        result = aggregator.add(second)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.timeframe, CandleTimeframe.MINUTE_10)
        self.assertEqual(str(result.open), "100.00000000")
        self.assertEqual(str(result.high), "112.00000000")
        self.assertEqual(str(result.low), "95.00000000")
        self.assertEqual(str(result.close), "108.00000000")
        self.assertEqual(str(result.volume), "3.30000000")
        self.assertEqual(result.number_of_trades, 30)
        self.assertEqual(
            result.source_candle_hashes,
            (first.source_payload_hash, second.source_payload_hash),
        )

    def test_gap_detector_reports_exact_missing_intervals(self) -> None:
        parser = BinanceKlineParser()
        first = parser.parse(_message(START, "5m"))
        third = parser.parse(_message(START + timedelta(minutes=10), "5m"))
        assert first is not None and third is not None
        detector = CandleGapDetector()
        detector.remember(first)

        gap = detector.inspect(third)

        self.assertIsNotNone(gap)
        assert gap is not None
        self.assertEqual(gap.missing_start, START + timedelta(minutes=5))
        self.assertEqual(gap.missing_end, START + timedelta(minutes=5))
        self.assertEqual(gap.missing_count, 1)

    def test_snapshot_build_is_deterministic_and_preserves_provenance(self) -> None:
        candle = BinanceKlineParser().parse(_message(START, "5m"))
        assert candle is not None

        first = build_market_snapshot(candle, code_version="git:abcdef123456")
        second = build_market_snapshot(candle, code_version="git:abcdef123456")

        self.assertEqual(first, second)
        self.assertEqual(first.canonical_sha256(), second.canonical_sha256())
        self.assertEqual(
            first.candles[0].source_reference.integrity_digest,
            candle.source_payload_hash,
        )


class LiveIngestionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_completed_native_and_derived_candles_are_persisted(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        await service.initialize(START)

        await service.process_message(_message(START, "5m"))
        await service.process_message(_message(START + timedelta(minutes=5), "5m"))
        await service.process_message(_message(START, "15m"))

        five = await repository.get_by_scope(_scope_query("5m"))
        ten = await repository.get_by_scope(_scope_query("10m"))
        fifteen = await repository.get_by_scope(_scope_query("15m"))
        metrics = service.metrics.snapshot()
        self.assertEqual(len(five.items), 2)
        self.assertEqual(len(ten.items), 1)
        self.assertEqual(len(fifteen.items), 1)
        self.assertEqual(
            await service.scan(_scope_query("15m")),
            fifteen.items[0],
        )
        self.assertIsInstance(service, MarketScannerService)
        self.assertEqual(metrics.completed_candles, 4)
        self.assertEqual(metrics.persisted_snapshots, 4)
        self.assertEqual(metrics.messages_rejected, 0)

    async def test_duplicate_is_idempotent_and_conflict_fails_closed(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        raw = _message(START, "5m")

        await service.process_message(raw)
        await service.process_message(raw)
        with self.assertRaises(LiveMarketDataConflictError):
            await service.process_message(
                _message(
                    START,
                    "5m",
                    high="113.00000000",
                    close="109.00000000",
                )
            )

        page = await repository.get_by_scope(_scope_query("5m"))
        metrics = service.metrics.snapshot()
        self.assertEqual(len(page.items), 1)
        self.assertEqual(metrics.duplicate_candles, 1)
        self.assertEqual(metrics.conflicting_candles, 1)

    async def test_restart_replay_with_new_delivery_time_is_idempotent(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        first_service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        second_service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )

        await first_service.process_message(_message(START, "15m"))
        await second_service.process_message(
            _message(START, "15m", event_delay_milliseconds=500)
        )

        page = await repository.get_by_scope(_scope_query("15m"))
        self.assertEqual(len(page.items), 1)
        self.assertEqual(second_service.metrics.snapshot().duplicate_candles, 1)

    async def test_invalid_message_is_observed_without_persistence(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )

        await service.process_message("invalid")

        self.assertEqual(service.metrics.snapshot().messages_rejected, 1)

    async def test_gap_metrics_are_recorded_without_silent_repair(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        await service.process_message(_message(START, "15m"))
        await service.process_message(
            _message(START + timedelta(minutes=30), "15m")
        )

        metrics = service.metrics.snapshot()
        self.assertEqual(metrics.gaps_detected, 1)
        self.assertEqual(metrics.missing_intervals, 1)


class BinanceWebSocketClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_reconnects_with_exponential_backoff(self) -> None:
        stop = asyncio.Event()
        fixed_now = START + timedelta(minutes=5)
        sessions = [
            _FakeWebSocket([OSError("connection lost")]),
            _FakeWebSocket([OSError("connection lost again")]),
            _FakeWebSocket([OSError("connection lost once more")]),
            _FakeWebSocket([_message(START, "5m")]),
        ]
        connector = _FakeConnector(sessions)
        sleeps: list[float] = []

        async def sleep(delay: float) -> None:
            sleeps.append(delay)

        async def handler(message: str | bytes) -> None:
            self.assertEqual(message, _message(START, "5m"))
            stop.set()

        client = BinanceWebSocketClient(
            connector=connector,
            clock=lambda: fixed_now,
            sleeper=sleep,
            backoff_initial_seconds=1,
            backoff_max_seconds=8,
        )
        await client.run(handler, stop)

        self.assertEqual(connector.calls, 4)
        self.assertEqual(sleeps, [1, 2, 4])
        metrics = client.metrics.snapshot()
        self.assertEqual(metrics.connections, 4)
        self.assertEqual(metrics.disconnects, 3)
        self.assertEqual(metrics.reconnects, 3)
        self.assertEqual(metrics.messages_received, 1)

    async def test_connection_health_is_fresh_while_receiving(self) -> None:
        stop = asyncio.Event()
        fixed_now = START + timedelta(minutes=5)
        session = _FakeWebSocket([_message(START, "5m")])
        connector = _FakeConnector([session])
        observed_health = []
        client = BinanceWebSocketClient(
            connector=connector,
            clock=lambda: fixed_now,
        )

        async def handler(message: str | bytes) -> None:
            observed_health.append(client.health(fixed_now))
            stop.set()

        await client.run(handler, stop)

        self.assertTrue(observed_health[0].healthy)
        self.assertEqual(observed_health[0].last_message_at, fixed_now)

    async def test_heartbeat_timeout_closes_stale_connection(self) -> None:
        stop = asyncio.Event()
        session = _HangingWebSocket()
        connector = _FakeConnector([session])

        async def sleep(delay: float) -> None:
            stop.set()

        client = BinanceWebSocketClient(
            connector=connector,
            sleeper=sleep,
            heartbeat_timeout_seconds=0.001,
        )

        await client.run(lambda message: _unused_handler(message), stop)

        self.assertTrue(session.closed)
        self.assertEqual(client.metrics.snapshot().heartbeat_timeouts, 1)


class _FakeWebSocket:
    def __init__(self, messages: list[str | bytes | BaseException]) -> None:
        self._messages = list(messages)
        self.closed = False

    async def recv(self) -> str | bytes:
        if not self._messages:
            raise OSError("test stream exhausted")
        value = self._messages.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


class _HangingWebSocket(_FakeWebSocket):
    def __init__(self) -> None:
        super().__init__([])

    async def recv(self) -> str | bytes:
        await asyncio.Event().wait()
        raise AssertionError("Unreachable")


class _FakeContext:
    def __init__(self, websocket: _FakeWebSocket) -> None:
        self.websocket = websocket

    async def __aenter__(self) -> _FakeWebSocket:
        return self.websocket

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeConnector:
    def __init__(self, sessions: list[_FakeWebSocket]) -> None:
        self._sessions = list(sessions)
        self.calls = 0

    def __call__(self, url: str, **kwargs: object) -> _FakeContext:
        if not url.startswith("wss://"):
            raise AssertionError("Expected secure WebSocket URL.")
        self.calls += 1
        return _FakeContext(self._sessions.pop(0))


async def _unused_handler(message: str | bytes) -> None:
    raise AssertionError(f"Unexpected message: {message!r}")


def _scope_query(timeframe: str) -> ScopedRepositoryQuery:
    return ScopedRepositoryQuery(
        scope=MarketScope(instrument="BTCUSDT", timeframe=timeframe),
        as_of=START + timedelta(hours=1),
        limit=20,
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
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    unittest.main()
