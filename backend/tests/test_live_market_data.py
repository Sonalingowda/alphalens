"""Sprint 1 live Binance market ingestion tests."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

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
from app.live_market_data import CompletedCandle
from app.prediction_api import _supervise_ingestion
from websockets.exceptions import InvalidHandshake, InvalidStatus, WebSocketException
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import MarketSnapshotMemoryRepository
from app.opportunity_intelligence.repositories import EntityId, ScopedRepositoryQuery
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
        service.warmup_history = AsyncMock(return_value=0)
        await service.process_message(_message(START, "15m"))
        await service.process_message(
            _message(START + timedelta(minutes=30), "15m")
        )

        metrics = service.metrics.snapshot()
        self.assertEqual(metrics.gaps_detected, 1)
        self.assertEqual(metrics.missing_intervals, 1)
        service.warmup_history.assert_awaited_once()

    async def test_warmup_history_persists_historical_klines(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        klines = _fake_binance_klines(200)

        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_response = _make_mock_response(klines)
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = mock_response
            count = await service.warmup_history(limit=200)

        self.assertEqual(count, 200)
        page = await repository.get_by_scope(_scope_query("5m", limit=200))
        self.assertEqual(len(page.items), 200)

    async def test_warmup_history_is_idempotent(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        klines = _fake_binance_klines(100)

        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_response = _make_mock_response(klines)
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = mock_response
            first_count = await service.warmup_history(limit=100)
            second_count = await service.warmup_history(limit=100)

        self.assertEqual(first_count, 100)
        self.assertEqual(second_count, 0)
        page = await repository.get_by_scope(_scope_query("5m", limit=200))
        self.assertEqual(len(page.items), 100)

    async def test_warmup_history_skips_existing_duplicates(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        klines = _fake_binance_klines(10)

        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_response = _make_mock_response(klines)
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = mock_response
            await service.warmup_history(limit=10)

        # Count before second warmup
        page_before = await repository.get_by_scope(_scope_query("5m", limit=20))
        count_before = len(page_before.items)

        # Run again with a new service (resetting the idempotency flag)
        service2 = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_response = _make_mock_response(klines)
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = mock_response
            await service2.warmup_history(limit=10)

        # Repository should not have grown
        page_after = await repository.get_by_scope(_scope_query("5m", limit=20))
        self.assertEqual(len(page_after.items), count_before)
        # All 10 klines from the first warmup should be present
        self.assertEqual(len(page_after.items), 10)

    async def test_warmup_history_defaults_to_public_binance_vision_host(self) -> None:
        service = LiveMarketIngestionService(
            repository=MarketSnapshotMemoryRepository(),
            code_version="git:abcdef123456",
        )
        self.assertEqual(service._rest_base_url, "https://data-api.binance.vision")

    async def test_warmup_history_uses_configured_rest_base_url(self) -> None:
        service = LiveMarketIngestionService(
            repository=MarketSnapshotMemoryRepository(),
            code_version="git:abcdef123456",
            rest_base_url="https://example.test/rest",
        )
        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = (
                _make_mock_response(_fake_binance_klines(3))
            )
            await service.warmup_history(limit=3)
            called = mock_httpx.AsyncClient.return_value.__aenter__.return_value.get
        called_url = called.call_args[0][0]
        self.assertEqual(called_url, "https://example.test/rest/api/v3/klines")
        self.assertNotIn("api.binance.com", called_url)

    async def test_warmup_history_no_longer_uses_banned_api_binance_com(self) -> None:
        service = LiveMarketIngestionService(
            repository=MarketSnapshotMemoryRepository(),
            code_version="git:abcdef123456",
        )
        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = (
                _make_mock_response(_fake_binance_klines(3))
            )
            await service.warmup_history(limit=3)
            called = mock_httpx.AsyncClient.return_value.__aenter__.return_value.get
        called_url = called.call_args[0][0]
        self.assertNotIn("api.binance.com", called_url)
        self.assertIn("data-api.binance.vision", called_url)

    async def test_warmup_history_falls_back_to_bybit_when_binance_blocked(self) -> None:
        self._assert_provider_fallback("bybit")

    async def test_warmup_history_falls_back_to_coinbase_when_binance_blocked(self) -> None:
        self._assert_provider_fallback("coinbase")

    async def test_warmup_history_falls_back_to_okx_when_binance_blocked(self) -> None:
        self._assert_provider_fallback("okx")

    async def _assert_provider_fallback(self, provider: str) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )

        def fake_get(url, params=None, timeout=None, headers=None):
            if provider in url:
                return _make_mock_response(_provider_payload(provider, 20))
            return _make_failing_response(418)

        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.side_effect = (
                fake_get
            )
            count = await service.warmup_history(limit=20)
        self.assertEqual(count, 20)
        page = await repository.get_by_scope(_scope_query("5m", limit=20))
        self.assertEqual(len(page.items), 20)

    async def test_gap_repair_backfills_missing_candle_via_rest(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        # Persist a contiguous prefix, then leave a gap at index 10.
        prefix = tuple(_market_snapshot(i) for i in list(range(10)) + list(range(11, 25)))
        await repository.save_batch(prefix)

        # REST returns the full contiguous range, including the missing candle.
        klines = [_kline_for_index(i) for i in range(25)]
        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = (
                _make_mock_response(klines)
            )
            persisted = await service.warmup_history(limit=25)

        self.assertEqual(persisted, 1)
        page = await repository.get_by_scope(
            ScopedRepositoryQuery(
                scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
                as_of=START + timedelta(hours=3),
                limit=30,
            )
        )
        self.assertEqual(len(page.items), 25)
        missing = _market_snapshot(10)
        fetched = await repository.get_by_id(EntityId(missing.snapshot_id))
        self.assertIsNotNone(fetched)

    async def test_gap_backfill_restores_ema26_and_detection(self) -> None:
        """End-to-end: a history gap blocks EMA26/detection; REST backfill fixes it.

        Mirrors the production incident where ``api.binance.com`` returned HTTP 418,
        so historical gaps were never repaired and detection stayed UNAVAILABLE.
        """
        from app.runtime_features import RuntimeFeatureEngine
        from app.runtime_context import RuntimeMarketContextService
        from app.runtime_detection import RuntimeOpportunityDetectionService
        from app.opportunity_intelligence.persistence import (
            DetectionMemoryRepository,
            FeatureSnapshotMemoryRepository,
            MarketContextMemoryRepository,
        )

        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        contexts = MarketContextMemoryRepository()
        detections = DetectionMemoryRepository()

        # History with a single missing candle at index 19 (0..18, 20..39).
        indices = [i for i in range(40) if i != 19]
        snapshots = {i: _market_snapshot(i) for i in indices}
        await markets.save_batch(tuple(snapshots.values()))

        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version="git:restored",
        )
        context_svc = RuntimeMarketContextService(
            market_snapshots=markets,
            feature_snapshots=features,
            market_contexts=contexts,
            code_version="git:restored",
        )
        detection_svc = RuntimeOpportunityDetectionService(
            market_snapshots=markets,
            feature_snapshots=features,
            market_contexts=contexts,
            detections=detections,
            code_version="git:restored",
        )

        # Before repair: latest candle cannot compute EMA26 -> detection UNAVAILABLE.
        latest_before = snapshots[39]
        feature_before = await engine.resolve(latest_before)
        await features.save(feature_before)
        context_before = await context_svc.build(latest_before, feature_before)
        await contexts.save(context_before)
        attempt_before, _ = await detection_svc.detect(
            latest_before, feature_before, context_before
        )
        self.assertEqual(attempt_before.state.value, "UNAVAILABLE")

        # REST backfill (now via the public binance.vision host) fills the gap.
        service = LiveMarketIngestionService(
            repository=markets,
            code_version="git:restored",
        )
        klines = [_kline_for_index(i) for i in range(40)]
        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = (
                _make_mock_response(klines)
            )
            await service.warmup_history(limit=40)
        page = await markets.get_by_scope(
            ScopedRepositoryQuery(
                scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
                as_of=START + timedelta(hours=4),
                limit=50,
            )
        )
        self.assertEqual(len(page.items), 40)

        # A new candle after repair sees the now-contiguous history -> EMA26 present.
        new_index = 40
        new_snapshot = _market_snapshot(new_index)
        await markets.save(new_snapshot)
        feature_after = await engine.resolve(new_snapshot)
        await features.save(feature_after)
        ema26 = [
            v
            for v in feature_after.values
            if v.feature_identifier == "exponential_moving_average_26"
        ]
        self.assertTrue(ema26, "EMA26 must be restored after gap repair")
        context_after = await context_svc.build(new_snapshot, feature_after)
        await contexts.save(context_after)
        attempt_after, _ = await detection_svc.detect(
            new_snapshot, feature_after, context_after
        )
        self.assertNotEqual(attempt_after.state.value, "UNAVAILABLE")

    async def test_production_lifespan_starts_and_stops_live_ingestion(self) -> None:
        from app import prediction_api

        started = asyncio.Event()
        stopped = asyncio.Event()

        async def run(stop_event: asyncio.Event) -> None:
            started.set()
            try:
                await stop_event.wait()
            finally:
                stopped.set()

        with patch.object(prediction_api.live_market_ingestion, "run", run):
            async with prediction_api._infrastructure_lifespan(prediction_api.app):
                await asyncio.wait_for(started.wait(), timeout=1)
                self.assertIs(
                    prediction_api.app.state.live_market_ingestion,
                    prediction_api.live_market_ingestion,
                )

        self.assertTrue(stopped.is_set())


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

    async def test_websocket_handshake_exception_reconnects_without_terminating(self):
        # A handshake/status failure surfaces as a websockets WebSocketException
        # (e.g. InvalidStatus 451 from Render egress). Previously this escaped
        # the reconnect handler and killed the ingestion task. It must now be
        # caught and trigger reconnect/backoff while ingestion stays alive.
        stop = asyncio.Event()
        sessions = [
            _FakeWebSocket([WebSocketException("handshake rejected")]),
            _FakeWebSocket([InvalidStatus(451)]),
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
            sleeper=sleep,
            backoff_initial_seconds=1,
            backoff_max_seconds=8,
        )
        # Must return normally: the WebSocketException must not terminate the loop.
        await client.run(handler, stop)

        self.assertEqual(connector.calls, 3)
        self.assertEqual(sleeps, [1, 2])
        metrics = client.metrics.snapshot()
        self.assertEqual(metrics.connections, 3)
        self.assertEqual(metrics.disconnects, 2)
        self.assertEqual(metrics.reconnects, 2)
        self.assertEqual(metrics.messages_received, 1)
        self.assertTrue(stop.is_set())

    async def test_websocket_exception_and_invalid_handshake_reconnect_bounded(self):
        # InvalidHandshake is also a WebSocketException subclass; reconnect must
        # use bounded exponential backoff (capped), not an unbounded loop.
        stop = asyncio.Event()
        sessions = [
            _FakeWebSocket([InvalidHandshake("bad handshake")]),
            _FakeWebSocket([WebSocketException("transient")]),
            _FakeWebSocket([InvalidHandshake("bad handshake again")]),
            _FakeWebSocket([_message(START, "5m")]),
        ]
        connector = _FakeConnector(sessions)
        sleeps: list[float] = []

        async def sleep(delay: float) -> None:
            sleeps.append(delay)

        async def handler(message: str | bytes) -> None:
            stop.set()

        client = BinanceWebSocketClient(
            connector=connector,
            sleeper=sleep,
            backoff_initial_seconds=1,
            backoff_max_seconds=4,
        )
        await client.run(handler, stop)

        self.assertEqual(connector.calls, 4)
        # 3 failures -> backoff 1, 2, 4 (capped at max 4): strictly increasing
        # and bounded.
        self.assertEqual(sleeps, [1, 2, 4])
        self.assertEqual(client.metrics.snapshot().messages_received, 1)


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


class _FakeHttpResponse:
    """Mock for httpx.Response with synchronous json() and raise_for_status()."""

    def __init__(self, json_data: object) -> None:
        self._json_data = json_data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> object:
        return self._json_data


def _make_mock_response(json_data: object) -> _FakeHttpResponse:
    return _FakeHttpResponse(json_data)


class _FakeFailingResponse:
    """Mock httpx.Response that fails raise_for_status for 4xx/5xx."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}",
                request=object(),
                response=object(),
            )

    def json(self) -> object:
        return {}


def _make_failing_response(status_code: int) -> _FakeFailingResponse:
    return _FakeFailingResponse(status_code)


def _provider_payload(provider: str, count: int) -> object:
    """Build a REST payload for ``provider`` containing ``count`` candles.

    Candle ``i`` borrows the OHLC from ``_kline_for_index(i)`` so the parsed
    result is identical regardless of which provider supplied it.
    """
    rows = []
    for i in range(count):
        kl = _kline_for_index(i)
        rows.append([kl[0], kl[1], kl[2], kl[3], kl[4], kl[5]])
    if provider == "binance":
        return rows
    if provider == "bybit":
        return {"retCode": 0, "result": {"list": list(reversed(rows))}}
    if provider == "okx":
        return {"data": list(reversed(rows))}
    # coinbase: [time_sec, low, high, open, close, volume] newest first
    cb = [[kl[0] // 1000, kl[3], kl[2], kl[1], kl[4], kl[5]] for kl in rows]
    return list(reversed(cb))


async def _unused_handler(message: str | bytes) -> None:
    raise AssertionError(f"Unexpected message: {message!r}")


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


def _market_snapshot(index: int):
    """Build a deterministic BTCUSDT/5m market snapshot for index ``i`` (5m steps)."""
    timestamp = START + timedelta(minutes=5 * index)
    base = Decimal(10_000 + index)
    event_time = timestamp + timedelta(minutes=5)
    candle = CompletedCandle(
        provider="binance_spot",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=event_time,
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=5) - timedelta(milliseconds=1),
        open=base,
        high=base + Decimal(5),
        low=base - Decimal(5),
        close=base + Decimal(1),
        volume=Decimal(10 + index),
        number_of_trades=100 + index,
        source_payload_hash=sha256(f"source:{index}".encode()).hexdigest(),
    )
    return build_market_snapshot(candle, code_version="git:abcdef123456")


def _kline_for_index(index: int) -> list:
    """Build a Binance REST kline array matching ``_market_snapshot(index)`` OHLC."""
    open_time = START + timedelta(minutes=5 * index)
    open_ms = int(open_time.timestamp() * 1000)
    close_ms = int(
        (open_time + timedelta(minutes=5) - timedelta(milliseconds=1)).timestamp() * 1000
    )
    base = 10_000 + index
    return [
        open_ms,
        f"{base}.00000000",
        f"{base + 5}.00000000",
        f"{base - 5}.00000000",
        f"{base + 1}.00000000",
        f"{10 + index}.00000000",
        close_ms,
        "42.00000000",
        100 + index,
        "21.00000000",
        "20.00000000",
        "0",
    ]


def _fake_binance_klines(count: int) -> list[list]:
    """Build fake Binance REST API kline arrays for testing."""
    base = START - timedelta(minutes=5 * count)
    klines = []
    for i in range(count):
        open_ms = int((base + timedelta(minutes=5 * i)).timestamp() * 1000)
        close_ms = int((base + timedelta(minutes=5 * (i + 1)) - timedelta(milliseconds=1)).timestamp() * 1000)
        klines.append([
            open_ms,              # 0: open time
            "100.00000000",       # 1: open
            "112.00000000",       # 2: high
            "95.00000000",        # 3: low
            "108.00000000",       # 4: close
            "2.50000000",         # 5: volume
            close_ms,             # 6: close time
            "42.00000000",        # 7: quote asset volume
            42,                   # 8: number of trades
            "21.00000000",        # 9: taker buy base asset volume
            "20.00000000",        # 10: taker buy quote asset volume
            "0",                  # 11: ignore
        ])
    return klines


class WarmupRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_warmup_failure_is_retried(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        attempts = {"count": 0}

        async def flaky() -> int:
            attempts["count"] += 1
            if attempts["count"] < 2:
                raise RuntimeError("transient storage error")
            return 0

        service.warmup_history = flaky  # type: ignore[method-assign]
        persisted = await service.warmup_history_with_retry(
            attempts=3, backoff_seconds=0
        )
        self.assertEqual(persisted, 0)
        self.assertEqual(attempts["count"], 2)

    async def test_exhausted_retries_surface_last_error(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )

        async def always_fails() -> int:
            raise RuntimeError("persistent storage outage")

        service.warmup_history = always_fails  # type: ignore[method-assign]
        with self.assertRaises(RuntimeError):
            await service.warmup_history_with_retry(
                attempts=2, backoff_seconds=0
            )

class IngestionSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_unexpected_exception_is_restarted_with_backoff(self) -> None:
        class FakeService:
            def __init__(self) -> None:
                self.calls = 0
                self.active = 0
                self.max_active = 0

            async def run(self, stop_event: asyncio.Event) -> None:
                self.calls += 1
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                try:
                    if self.calls < 3:
                        raise RuntimeError(f"boom {self.calls}")
                    await stop_event.wait()
                finally:
                    self.active -= 1

        stop = asyncio.Event()
        service = FakeService()
        task = asyncio.create_task(
            _supervise_ingestion(
                stop,
                service,
                backoff_initial_seconds=0.001,
                backoff_max_seconds=0.005,
            )
        )
        await asyncio.sleep(0.05)
        stop.set()
        await asyncio.wait_for(task, timeout=1)

        # Crashed twice, then ran until shutdown -> exactly 3 invocations.
        self.assertEqual(service.calls, 3)
        # Never two ingestion loops concurrently (no duplicate WS connections).
        self.assertEqual(service.max_active, 1)

    async def test_graceful_shutdown_does_not_restart(self) -> None:
        class FakeService:
            def __init__(self) -> None:
                self.calls = 0

            async def run(self, stop_event: asyncio.Event) -> None:
                self.calls += 1
                raise RuntimeError("boom")

        stop = asyncio.Event()
        stop.set()
        service = FakeService()
        await _supervise_ingestion(stop, service, backoff_initial_seconds=0.001)

        self.assertEqual(service.calls, 0)

    async def test_cancellation_does_not_cause_restart(self) -> None:
        class FakeService:
            async def run(self, stop_event: asyncio.Event) -> None:
                raise asyncio.CancelledError()

        stop = asyncio.Event()
        service = FakeService()
        with self.assertRaises(asyncio.CancelledError):
            await _supervise_ingestion(stop, service)

    async def test_no_concurrent_ingestion_loops_after_restart(self) -> None:
        # Mirror test_unexpected_exception_is_restarted but assert explicitly that
        # the supervisor awaits the previous run before starting the next one.
        class FakeService:
            def __init__(self) -> None:
                self.active = 0
                self.max_active = 0

            async def run(self, stop_event: asyncio.Event) -> None:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
                try:
                    if not stop_event.is_set():
                        raise RuntimeError("fail first")
                    await stop_event.wait()
                finally:
                    self.active -= 1

        stop = asyncio.Event()
        service = FakeService()
        task = asyncio.create_task(
            _supervise_ingestion(
                stop,
                service,
                backoff_initial_seconds=0.001,
                backoff_max_seconds=0.005,
            )
        )
        await asyncio.sleep(0.03)
        stop.set()
        await asyncio.wait_for(task, timeout=1)
        self.assertLessEqual(service.max_active, 1)


class InvalidCandleTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_zero_volume_candle_rejected_from_live(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        await service.initialize(START)

        await service.process_message(_message(START, "5m", volume="0.00000000"))

        metrics = service.metrics.snapshot()
        self.assertEqual(metrics.invalid_candles, 1)
        self.assertEqual(metrics.completed_candles, 0)
        page = await repository.get_by_scope(_scope_query("5m"))
        self.assertEqual(len(page.items), 0)

    async def test_valid_candle_still_persists(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        await service.initialize(START)

        await service.process_message(_message(START, "5m", volume="2.50000000"))

        self.assertEqual(service.metrics.snapshot().invalid_candles, 0)
        page = await repository.get_by_scope(_scope_query("5m"))
        self.assertEqual(len(page.items), 1)

    async def test_invalid_zero_volume_candle_rejected_from_warmup(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        service = LiveMarketIngestionService(
            repository=repository,
            code_version="git:abcdef123456",
        )
        open_ms = int(START.timestamp() * 1000)
        close_ms = int(
            (START + timedelta(minutes=5) - timedelta(milliseconds=1)).timestamp() * 1000
        )
        zero_kline = [
            open_ms,
            "100.00000000",
            "100.00000000",
            "100.00000000",
            "100.00000000",
            "0.00000000",
            close_ms,
            "0.00000000",
            0,
            "0.00000000",
            "0.00000000",
            "0",
        ]

        with patch("app.live_market_data.service.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = (
                _make_mock_response([zero_kline])
            )
            count = await service.warmup_history(limit=1)

        self.assertEqual(count, 0)
        self.assertEqual(service.metrics.snapshot().invalid_candles, 1)


if __name__ == "__main__":
    unittest.main()
