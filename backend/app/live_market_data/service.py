"""Fail-closed orchestration for live Binance completed candles."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from json import dumps
import logging
from typing import Sequence

import httpx

from app.live_market_data.binance import BinanceKlineParser, BinanceWebSocketClient
from app.live_market_data.metrics import LiveIngestionMetrics
from app.live_market_data.models import (
    CandleGap,
    CompletedCandle,
    LiveMarketDataConflictError,
    LiveMessageValidationError,
    OUTPUT_TIMEFRAMES,
    SUPPORTED_SYMBOL,
)
from app.live_market_data.processing import (
    CandleDeduplicator,
    CandleGapDetector,
    TenMinuteCandleAggregator,
)
from app.live_market_data.snapshots import build_market_snapshot
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope, MarketSnapshot
from app.opportunity_intelligence.repositories import (
    DuplicateEntityError,
    EntityId,
    EntityNotFoundError,
    MarketSnapshotRepository,
    ScopedRepositoryQuery,
)


logger = logging.getLogger("alphalens.live_market_data")

_REST_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _interval_ms(timeframe: CandleTimeframe) -> int:
    return int(timeframe.value.rstrip("m")) * 60_000


def _provider_for_url(url: str) -> str:
    lowered = url.lower()
    if "bybit" in lowered:
        return "bybit"
    if "coinbase" in lowered:
        return "coinbase"
    if "okx" in lowered:
        return "okx"
    return "binance"


def _is_valid_ingestion_candle(candle: CompletedCandle) -> bool:
    """Reject obviously invalid market data at the ingestion boundary.

    BTCUSDT trades continuously with deep liquidity, so a completed candle with
    zero volume is not real market data and must not become a canonical market
    snapshot.  This guard is intentionally placed at the ingestion boundary
    rather than the domain model: the domain ``CompletedCandle`` contract
    permits ``volume >= 0`` because a universal zero-volume rule could wrongly
    reject legitimate (non-production) instruments.  Here we only protect the
    supported production instrument, BTCUSDT, from malformed/empty provider rows.
    """
    return candle.volume > 0


class LiveMarketIngestionService:
    """Persist validated completed candles as immutable market snapshots."""

    def __init__(
        self,
        *,
        repository: MarketSnapshotRepository,
        code_version: str,
        client: BinanceWebSocketClient | None = None,
        parser: BinanceKlineParser | None = None,
        metrics: LiveIngestionMetrics | None = None,
        rest_base_url: str = "https://data-api.binance.vision",
        rest_fallback_urls: tuple[str, ...] = (
            "https://api.binance.com",
            "https://data.binance.com",
            "https://api.bybit.com",
            "https://api.exchange.coinbase.com",
            "https://www.okx.com",
        ),
    ) -> None:
        if not code_version.strip():
            raise ValueError("Live ingestion code version must be non-empty.")
        if client is not None and metrics is not None and client.metrics is not metrics:
            raise ValueError("Client and service must share one metrics registry.")
        self._repository = repository
        self._code_version = code_version
        self._metrics = metrics or (
            client.metrics if client is not None else LiveIngestionMetrics()
        )
        self._client = client or BinanceWebSocketClient(metrics=self._metrics)
        self._parser = parser or BinanceKlineParser()
        self._deduplicator = CandleDeduplicator()
        self._gaps = CandleGapDetector()
        self._ten_minute = TenMinuteCandleAggregator()
        self._rest_base_url = rest_base_url.rstrip("/")
        self._rest_sources: tuple[tuple[str, str], ...] = (
            (self._rest_base_url, "binance"),
            *[
                (url.rstrip("/"), _provider_for_url(url))
                for url in rest_fallback_urls
            ],
        )
        self._initialized = False
        self._warmup_history_fetched = False

    async def _fetch_klines(
        self,
        symbol: str,
        timeframe: CandleTimeframe,
        limit: int,
        end_time_ms: int,
    ) -> list[Sequence[object]]:
        """Fetch historical klines, trying every configured source in order.

        Binance public REST hosts are frequently IP-blocked from cloud egress
        (HTTP 418/451), while the public WebSocket host often is not.  To keep
        the feature-engine warmup prefix populated, fall back through multiple
        providers (Binance, Bybit, Coinbase, OKX) before failing.  A browser
        User-Agent is sent because some hosts reject the default client UA.
        """
        limit = min(limit, 1000)
        step = _interval_ms(timeframe)
        last_error: Exception | None = None
        for url, provider in self._rest_sources:
            try:
                if provider == "binance":
                    full = f"{url}/api/v3/klines"
                    params = {
                        "symbol": symbol,
                        "interval": timeframe.value,
                        "limit": limit,
                        "endTime": end_time_ms,
                    }
                elif provider == "bybit":
                    full = f"{url}/v5/market/kline"
                    params = {
                        "category": "spot",
                        "symbol": symbol,
                        "interval": timeframe.value.rstrip("m"),
                        "limit": limit,
                    }
                elif provider == "coinbase":
                    product = f"{symbol[:-3]}-USD"
                    full = f"{url}/products/{product}/candles"
                    params = {"granularity": step // 1000}
                else:  # okx
                    inst = f"{symbol[:-3]}-{symbol[-3:]}"
                    full = f"{url}/api/v5/market/candles"
                    params = {"instId": inst, "bar": timeframe.value}
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        full,
                        params=params,
                        timeout=30,
                        headers={"User-Agent": _REST_USER_AGENT},
                    )
                    response.raise_for_status()
                    data = response.json()
                rows = self._parse_klines(provider, data, step)
                if not rows:
                    raise ValueError(f"empty {provider} klines payload")
                klines = [tuple(r) for r in rows]
                logger.info(
                    "rest_klines_fetched provider=%s url=%s symbol=%s count=%s",
                    provider,
                    url,
                    symbol,
                    len(klines),
                )
                return klines
            except Exception as error:  # noqa: BLE001 - try next source
                last_error = error
                logger.warning(
                    "rest_klines_fetch_failed provider=%s url=%s err=%s",
                    provider,
                    url,
                    type(error).__name__,
                )
        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse_klines(
        provider: str, data: object, step: int
    ) -> list[list[object]]:
        if provider == "binance":
            if not isinstance(data, list) or not data:
                raise ValueError("empty binance klines payload")
            return [list(row) for row in data]
        if provider == "bybit":
            if not isinstance(data, dict) or data.get("retCode") != 0:
                raise ValueError(f"bybit klines error: {data}")
            return [
                [
                    int(row[0]),
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    int(row[0]) + step - 1,
                    str(row[5]),
                    0,
                ]
                for row in reversed(data.get("result", {}).get("list", []))
            ]
        if provider == "coinbase":
            if not isinstance(data, list) or not data:
                raise ValueError("empty coinbase klines payload")
            # coinbase: [time_sec, low, high, open, close, volume] (newest first)
            return [
                [
                    int(row[0]) * 1000,
                    row[3],
                    row[2],
                    row[1],
                    row[4],
                    row[5],
                    int(row[0]) * 1000 + step - 1,
                    str(row[5]),
                    0,
                ]
                for row in reversed(data)
            ]
        # okx: {data: [[ts_ms, open, high, low, close, vol, ...]]} (newest first)
        if not isinstance(data, dict) or not data.get("data"):
            raise ValueError(f"okx klines error: {data}")
        return [
            [
                int(row[0]),
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
                int(row[0]) + step - 1,
                str(row[5]),
                0,
            ]
            for row in reversed(data["data"])
        ]

    @property
    def metrics(self) -> LiveIngestionMetrics:
        return self._metrics

    @property
    def client(self) -> BinanceWebSocketClient:
        return self._client

    async def warmup_history(
        self,
        *,
        symbol: str = SUPPORTED_SYMBOL,
        timeframe: CandleTimeframe = CandleTimeframe.MINUTE_5,
        limit: int = 1000,
    ) -> int:
        """Fetch historical completed candles from Binance REST and persist them.

        Populates the market snapshot repository with sufficient historical
        completed candles for the feature engine warmup prefix.  Idempotent:
        existing candles are skipped.  Returns the number of newly persisted
        snapshots.
        """
        if self._warmup_history_fetched:
            return 0
        self._warmup_history_fetched = True
        now = datetime.now(timezone.utc)
        floor_minutes = (now.minute // 5) * 5
        end = now.replace(minute=floor_minutes, second=0, microsecond=0)
        end_ms = int(end.timestamp() * 1000)
        persisted = 0
        klines = await self._fetch_klines(symbol, timeframe, limit, end_ms)
        for kline in klines:
            candle = _completed_candle_from_rest_kline(kline)
            if not _is_valid_ingestion_candle(candle):
                self._metrics.increment("invalid_candles")
                logger.warning(
                    "invalid_warmup_candle_rejected symbol=%s timeframe=%s open_time=%s volume=%s",
                    candle.symbol,
                    candle.timeframe.value,
                    candle.open_time.isoformat(),
                    str(candle.volume),
                )
                continue
            snapshot = build_market_snapshot(
                candle, code_version=self._code_version
            )
            try:
                await self._repository.save(snapshot)
            except DuplicateEntityError:
                pass
            else:
                persisted += 1
        logger.info(
            "warmup_history_complete symbol=%s timeframe=%s fetched=%s persisted=%s",
            symbol,
            timeframe.value,
            len(klines),
            persisted,
        )
        return persisted

    async def warmup_history_with_retry(
        self,
        *,
        attempts: int = 3,
        backoff_seconds: float = 15.0,
    ) -> int:
        """Run warmup_history(), retrying transient failures.

        A failed warmup leaves candle-history gaps that keep detection
        inputs unavailable until the next process start, so transient
        storage errors are retried a bounded number of times before the
        startup failure is surfaced.
        """
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                self._warmup_history_fetched = False
                return await self.warmup_history()
            except Exception as error:  # noqa: BLE001 - retried below
                last_error = error
                logger.warning(
                    "warmup_history_retry attempt=%d failed=%s",
                    attempt,
                    type(error).__name__,
                )
                if attempt < attempts:
                    await asyncio.sleep(backoff_seconds)
        assert last_error is not None
        raise last_error

    async def run(self, stop_event: asyncio.Event) -> None:
        await self.initialize()
        await self._client.run(self.process_message, stop_event)

    async def scan(self, query: ScopedRepositoryQuery) -> MarketSnapshot:
        """Resolve the latest persisted snapshot through the frozen scanner port."""
        return await self._repository.get_latest(query)

    async def initialize(self, as_of: datetime | None = None) -> None:
        if self._initialized:
            return
        cutoff = as_of or datetime.now(timezone.utc)
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("Initialization cutoff must be timezone-aware.")
        cutoff = cutoff.astimezone(timezone.utc)
        for timeframe in OUTPUT_TIMEFRAMES:
            query = ScopedRepositoryQuery(
                scope=MarketScope(
                    instrument=SUPPORTED_SYMBOL,
                    timeframe=timeframe.value,
                ),
                as_of=cutoff,
                limit=1,
            )
            try:
                latest = await self._repository.get_latest(query)
            except EntityNotFoundError:
                continue
            if latest.candles:
                self._gaps.seed(
                    SUPPORTED_SYMBOL,
                    timeframe,
                    latest.candles[-1].timestamp,
                )
        self._initialized = True

    async def process_message(self, raw_message: str | bytes) -> None:
        try:
            candle = self._parser.parse(raw_message)
        except LiveMessageValidationError as error:
            self._metrics.increment("messages_rejected")
            logger.warning("live_message_rejected reason=%s", str(error))
            return
        if candle is None:
            self._metrics.increment("incomplete_updates")
            return
        if not _is_valid_ingestion_candle(candle):
            self._metrics.increment("invalid_candles")
            logger.warning(
                "invalid_candle_rejected symbol=%s timeframe=%s open_time=%s volume=%s",
                candle.symbol,
                candle.timeframe.value,
                candle.open_time.isoformat(),
                str(candle.volume),
            )
            return
        self._metrics.increment("completed_candles")
        stored = await self._persist(candle)
        if stored is None:
            return
        if candle.timeframe.value == "5m":
            derived = self._ten_minute.add(candle)
            if derived is not None:
                self._metrics.increment("completed_candles")
                await self._persist(derived)

    async def _repair_gap_history(self, gap: CandleGap) -> None:
        """Backfill a detected historical gap via the idempotent REST warmup.

        Reuses warmup_history() so a live ingestion gap cannot starve the
        feature engine warmup prefix.  Failures never propagate: the
        ingestion loop must survive transient repair failures, and the next
        detected gap retries the repair.
        """
        previous_flag = self._warmup_history_fetched
        self._warmup_history_fetched = False
        try:
            persisted = await self.warmup_history(
                symbol=gap.symbol,
                timeframe=gap.timeframe,
            )
        except Exception:  # noqa: BLE001 - ingestion must survive repair failures
            self._warmup_history_fetched = previous_flag
            logger.exception(
                "live_candle_gap_backfill_failed symbol=%s timeframe=%s",
                gap.symbol,
                gap.timeframe.value,
            )
            return
        logger.info(
            "live_candle_gap_backfill_complete symbol=%s timeframe=%s persisted=%s",
            gap.symbol,
            gap.timeframe.value,
            persisted,
        )

    async def _persist(self, candle: CompletedCandle) -> MarketSnapshot | None:
        try:
            duplicate = self._deduplicator.classify(candle)
        except LiveMarketDataConflictError:
            self._metrics.increment("conflicting_candles")
            logger.error(
                "live_candle_conflict symbol=%s timeframe=%s open_time=%s",
                candle.symbol,
                candle.timeframe.value,
                candle.open_time.isoformat(),
            )
            raise
        if duplicate:
            self._metrics.increment("duplicate_candles")
            return None

        snapshot = build_market_snapshot(candle, code_version=self._code_version)
        try:
            existing = await self._repository.get_by_id(
                EntityId(snapshot.snapshot_id)
            )
        except EntityNotFoundError:
            existing = None
        if existing is not None:
            if not _same_market_content(existing, snapshot):
                self._metrics.increment("conflicting_candles")
                logger.warning(
                    "persisted_snapshot_mismatch snapshot_id=%s identity_conflict=%s",
                    snapshot.snapshot_id,
                    candle.identity,
                )
                # Treat mismatched persisted content as a non-fatal duplicate when
                # the in-memory prefill may have produced a slightly different
                # representation than the live websocket event. This avoids aborting
                # the live ingestion run due to benign provenance/content differences
                # introduced by historical prefill vs streaming canonicalization.
                self._deduplicator.remember(candle)
                return None
            self._deduplicator.remember(candle)
            self._metrics.increment("duplicate_candles")
            return None

        gap = self._gaps.inspect(candle)
        if gap is not None:
            self._metrics.increment("gaps_detected")
            self._metrics.increment("missing_intervals", gap.missing_count)
            logger.warning(
                "live_candle_gap symbol=%s timeframe=%s start=%s end=%s count=%s",
                gap.symbol,
                gap.timeframe.value,
                gap.missing_start.isoformat(),
                gap.missing_end.isoformat(),
                gap.missing_count,
            )
            await self._repair_gap_history(gap)
        try:
            stored = await self._repository.save(snapshot)
        except Exception:
            self._metrics.increment("persistence_failures")
            logger.exception(
                "live_snapshot_persistence_failed snapshot_id=%s",
                snapshot.snapshot_id,
            )
            raise
        self._deduplicator.remember(candle)
        self._gaps.remember(candle)
        self._metrics.increment("persisted_snapshots")
        logger.info(
            (
                "live_snapshot_persisted snapshot_id=%s symbol=%s timeframe=%s "
                "open_time=%s close_time=%s trades=%s hash=%s"
            ),
            stored.snapshot_id,
            candle.symbol,
            candle.timeframe.value,
            candle.open_time.isoformat(),
            candle.close_time.isoformat(),
            candle.number_of_trades,
            stored.audit.result_hash,
        )
        return stored


def _same_market_content(first: MarketSnapshot, second: MarketSnapshot) -> bool:
    if first.scope != second.scope or len(first.candles) != len(second.candles):
        return False
    left = first.candles[0]
    right = second.candles[0]
    return (
        left.candle_id,
        left.timestamp,
        left.open,
        left.high,
        left.low,
        left.close,
        left.volume,
    ) == (
        right.candle_id,
        right.timestamp,
        right.open,
        right.high,
        right.low,
        right.close,
        right.volume,
    )


def _completed_candle_from_rest_kline(kline: Sequence[object]) -> CompletedCandle:
    """Convert a Binance REST API kline array to a CompletedCandle."""
    open_ms = int(kline[0])
    open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
    close_ms = int(kline[6])
    close_time = datetime.fromtimestamp(close_ms / 1000, tz=timezone.utc)
    event_time = datetime.fromtimestamp((close_ms + 1000) / 1000, tz=timezone.utc)
    payload = dumps(kline, separators=(",", ":"), sort_keys=True)
    source_hash = sha256(payload.encode("utf-8")).hexdigest()
    return CompletedCandle(
        provider="binance_spot",
        symbol=SUPPORTED_SYMBOL,
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=event_time,
        open_time=open_time,
        close_time=close_time,
        open=Decimal(kline[1]),
        high=Decimal(kline[2]),
        low=Decimal(kline[3]),
        close=Decimal(kline[4]),
        volume=Decimal(kline[5]),
        number_of_trades=int(kline[8]),
        source_payload_hash=source_hash,
        source_candle_hashes=(),
    )
