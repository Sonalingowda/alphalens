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
        self._initialized = False
        self._warmup_history_fetched = False

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
        params = {
            "symbol": symbol,
            "interval": timeframe.value,
            "limit": min(limit, 1000),
            "endTime": end_ms,
        }
        url = f"{self._rest_base_url}/api/v3/klines"
        persisted = 0
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30)
            response.raise_for_status()
            klines = response.json()
        for kline in klines:
            candle = _completed_candle_from_rest_kline(kline)
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
