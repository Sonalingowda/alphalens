"""Immutable adapter models for Binance live candle ingestion."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json

from app.market_data.models import CandleTimeframe


LIVE_INGESTION_VERSION = "1.0.0"
SUPPORTED_SYMBOL = "BTCUSDT"
NATIVE_TIMEFRAMES = frozenset(
    {CandleTimeframe.MINUTE_5, CandleTimeframe.MINUTE_15}
)
OUTPUT_TIMEFRAMES = (
    CandleTimeframe.MINUTE_5,
    CandleTimeframe.MINUTE_10,
    CandleTimeframe.MINUTE_15,
)


class LiveMarketDataError(RuntimeError):
    """Base error for fail-closed live market ingestion."""


class LiveMessageValidationError(LiveMarketDataError):
    """Raised when an exchange message violates the expected contract."""


class LiveMarketDataConflictError(LiveMarketDataError):
    """Raised when one immutable candle identity has conflicting content."""


class LiveChronologyError(LiveMarketDataError):
    """Raised when a stream moves backward outside duplicate replay."""


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STALE = "stale"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class CompletedCandle:
    """One validated immutable completed exchange or derived candle."""

    provider: str
    symbol: str
    timeframe: CandleTimeframe
    event_time: datetime
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    number_of_trades: int
    source_payload_hash: str
    source_candle_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.provider not in {"binance_spot", "alphalens_derived"}:
            raise LiveMessageValidationError("Candle provider is unsupported.")
        if self.symbol != SUPPORTED_SYMBOL:
            raise LiveMessageValidationError("Only BTCUSDT is supported.")
        if self.timeframe not in OUTPUT_TIMEFRAMES:
            raise LiveMessageValidationError("Candle timeframe is unsupported.")
        for name, value in (
            ("event_time", self.event_time),
            ("open_time", self.open_time),
            ("close_time", self.close_time),
        ):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise LiveMessageValidationError(f"{name} must be canonical UTC.")
        duration = _duration(self.timeframe)
        if self.open_time != _floor(self.open_time, duration):
            raise LiveMessageValidationError(
                "Candle open time is not aligned to its UTC timeframe."
            )
        if self.close_time != self.open_time + duration - timedelta(milliseconds=1):
            raise LiveMessageValidationError(
                "Candle close time does not match its timeframe."
            )
        if self.event_time < self.close_time:
            raise LiveMessageValidationError(
                "Completed candle event precedes its close time."
            )
        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
            ("volume", self.volume),
        ):
            if not isinstance(value, Decimal) or not value.is_finite():
                raise LiveMessageValidationError(f"{name} must be a finite Decimal.")
            if value.as_tuple().exponent < -18:
                raise LiveMessageValidationError(
                    f"{name} exceeds the canonical 18-place precision."
                )
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise LiveMessageValidationError("OHLC prices must be positive.")
        if self.volume < 0:
            raise LiveMessageValidationError("Volume must not be negative.")
        if self.low > min(self.open, self.close, self.high):
            raise LiveMessageValidationError("Low exceeds another OHLC value.")
        if self.high < max(self.open, self.close, self.low):
            raise LiveMessageValidationError("High is below another OHLC value.")
        if (
            not isinstance(self.number_of_trades, int)
            or isinstance(self.number_of_trades, bool)
            or self.number_of_trades < 0
        ):
            raise LiveMessageValidationError(
                "Number of trades must be a non-negative integer."
            )
        if len(self.source_payload_hash) != 64:
            raise LiveMessageValidationError("Source payload hash must be SHA-256.")
        if any(len(value) != 64 for value in self.source_candle_hashes):
            raise LiveMessageValidationError("Source candle hashes must be SHA-256.")

    @property
    def identity(self) -> tuple[str, CandleTimeframe, datetime]:
        return self.symbol, self.timeframe, self.open_time

    @property
    def content_hash(self) -> str:
        payload = {
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "open_time": self.open_time.isoformat(),
            "close_time": self.close_time.isoformat(),
            "open": format(self.open, "f"),
            "high": format(self.high, "f"),
            "low": format(self.low, "f"),
            "close": format(self.close, "f"),
            "volume": format(self.volume, "f"),
            "number_of_trades": self.number_of_trades,
            "source_candle_hashes": self.source_candle_hashes,
        }
        return sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class CandleGap:
    symbol: str
    timeframe: CandleTimeframe
    missing_start: datetime
    missing_end: datetime
    missing_count: int


@dataclass(frozen=True, slots=True)
class ConnectionHealth:
    state: ConnectionState
    connected_at: datetime | None
    last_message_at: datetime | None
    reconnect_count: int
    consecutive_failures: int
    healthy: bool


def _duration(timeframe: CandleTimeframe) -> timedelta:
    values = {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }
    return values[timeframe]


def _floor(value: datetime, duration: timedelta) -> datetime:
    seconds = int(duration.total_seconds())
    timestamp = int(value.astimezone(timezone.utc).timestamp())
    return datetime.fromtimestamp(timestamp // seconds * seconds, tz=timezone.utc)
