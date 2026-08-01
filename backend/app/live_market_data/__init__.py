"""Public live market ingestion surface."""

from app.live_market_data.binance import (
    BINANCE_MARKET_STREAM_BASE_URL,
    BINANCE_STREAM_PATH,
    BinanceKlineParser,
    BinanceWebSocketClient,
    HeartbeatTimeoutError,
)
from app.live_market_data.metrics import (
    LiveIngestionMetrics,
    LiveIngestionMetricsSnapshot,
)
from app.live_market_data.models import (
    CandleGap,
    CompletedCandle,
    ConnectionHealth,
    ConnectionState,
    LiveChronologyError,
    LiveMarketDataConflictError,
    LiveMarketDataError,
    LiveMessageValidationError,
)
from app.live_market_data.processing import (
    CandleDeduplicator,
    CandleGapDetector,
    TenMinuteCandleAggregator,
)
from app.live_market_data.service import LiveMarketIngestionService
from app.live_market_data.snapshots import build_market_snapshot


__all__ = (
    "BINANCE_MARKET_STREAM_BASE_URL",
    "BINANCE_STREAM_PATH",
    "BinanceKlineParser",
    "BinanceWebSocketClient",
    "CandleDeduplicator",
    "CandleGap",
    "CandleGapDetector",
    "CompletedCandle",
    "ConnectionHealth",
    "ConnectionState",
    "HeartbeatTimeoutError",
    "LiveChronologyError",
    "LiveIngestionMetrics",
    "LiveIngestionMetricsSnapshot",
    "LiveMarketDataConflictError",
    "LiveMarketDataError",
    "LiveMarketIngestionService",
    "LiveMessageValidationError",
    "TenMinuteCandleAggregator",
    "build_market_snapshot",
)
