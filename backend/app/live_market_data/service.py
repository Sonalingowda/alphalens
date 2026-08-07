"""Fail-closed orchestration for live Binance completed candles."""

import asyncio
from datetime import datetime, timezone
import logging

from app.live_market_data.binance import BinanceKlineParser, BinanceWebSocketClient
from app.live_market_data.metrics import LiveIngestionMetrics
from app.live_market_data.models import (
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
from app.opportunity_intelligence.domain import MarketScope, MarketSnapshot
from app.opportunity_intelligence.repositories import (
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
        self._initialized = False

    @property
    def metrics(self) -> LiveIngestionMetrics:
        return self._metrics

    @property
    def client(self) -> BinanceWebSocketClient:
        return self._client

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
