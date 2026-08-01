"""Binance Spot WebSocket transport and completed-kline parser."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Protocol

from websockets.exceptions import ConnectionClosed

from app.live_market_data.metrics import LiveIngestionMetrics
from app.live_market_data.models import (
    CompletedCandle,
    ConnectionHealth,
    ConnectionState,
    LiveMessageValidationError,
    NATIVE_TIMEFRAMES,
    SUPPORTED_SYMBOL,
)
from app.market_data.models import CandleTimeframe


BINANCE_MARKET_STREAM_BASE_URL = "wss://data-stream.binance.vision"
BINANCE_STREAM_PATH = (
    "/stream?streams=btcusdt@kline_5m/btcusdt@kline_15m"
)


class WebSocketSession(Protocol):
    async def recv(self) -> str | bytes: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class WebSocketContext(Protocol):
    async def __aenter__(self) -> WebSocketSession: ...

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> bool | None: ...


Connector = Callable[..., WebSocketContext]
MessageHandler = Callable[[str | bytes], Awaitable[None]]
Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


class HeartbeatTimeoutError(OSError):
    """Raised when no WebSocket traffic arrives inside the health window."""


class BinanceKlineParser:
    """Validate Binance combined-stream messages without implicit coercion."""

    def parse(self, raw_message: str | bytes) -> CompletedCandle | None:
        payload = _json_object(raw_message)
        event = payload.get("data", payload)
        if not isinstance(event, dict):
            raise LiveMessageValidationError("WebSocket event must be an object.")
        if event.get("e") != "kline":
            raise LiveMessageValidationError("WebSocket event is not a kline.")
        if event.get("s") != SUPPORTED_SYMBOL:
            raise LiveMessageValidationError("WebSocket symbol is unsupported.")
        event_time = _milliseconds(event.get("E"), "event time")
        kline = event.get("k")
        if not isinstance(kline, dict):
            raise LiveMessageValidationError("Kline body must be an object.")
        if kline.get("s") != SUPPORTED_SYMBOL:
            raise LiveMessageValidationError("Kline symbol conflicts with event symbol.")
        timeframe = _timeframe(kline.get("i"))
        expected_stream = f"btcusdt@kline_{timeframe.value}"
        stream = payload.get("stream")
        if "data" in payload and stream != expected_stream:
            raise LiveMessageValidationError(
                "Combined stream identity conflicts with the kline body."
            )
        if kline.get("x") is not True:
            return None

        canonical_source = json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return CompletedCandle(
            provider="binance_spot",
            symbol=SUPPORTED_SYMBOL,
            timeframe=timeframe,
            event_time=event_time,
            open_time=_milliseconds(kline.get("t"), "open time"),
            close_time=_milliseconds(kline.get("T"), "close time"),
            open=_decimal(kline.get("o"), "open"),
            high=_decimal(kline.get("h"), "high"),
            low=_decimal(kline.get("l"), "low"),
            close=_decimal(kline.get("c"), "close"),
            volume=_decimal(kline.get("v"), "volume"),
            number_of_trades=_non_negative_int(kline.get("n"), "number of trades"),
            source_payload_hash=sha256(canonical_source).hexdigest(),
        )


class BinanceWebSocketClient:
    """Long-running Binance client with deterministic reconnect behavior."""

    def __init__(
        self,
        *,
        base_url: str = BINANCE_MARKET_STREAM_BASE_URL,
        heartbeat_timeout_seconds: float = 60.0,
        backoff_initial_seconds: float = 1.0,
        backoff_max_seconds: float = 30.0,
        connector: Connector | None = None,
        clock: Clock | None = None,
        sleeper: Sleeper = asyncio.sleep,
        metrics: LiveIngestionMetrics | None = None,
    ) -> None:
        if not base_url.startswith("wss://"):
            raise ValueError("Binance WebSocket base URL must use wss://.")
        if heartbeat_timeout_seconds <= 0:
            raise ValueError("Heartbeat timeout must be positive.")
        if not 0 < backoff_initial_seconds <= backoff_max_seconds:
            raise ValueError("Reconnect backoff bounds are invalid.")
        self._url = f"{base_url.rstrip('/')}{BINANCE_STREAM_PATH}"
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._backoff_initial_seconds = backoff_initial_seconds
        self._backoff_max_seconds = backoff_max_seconds
        self._connector = connector or _websocket_connector
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleeper = sleeper
        self._metrics = metrics or LiveIngestionMetrics()
        self._state = ConnectionState.DISCONNECTED
        self._connected_at: datetime | None = None
        self._last_message_at: datetime | None = None
        self._reconnect_count = 0
        self._consecutive_failures = 0

    @property
    def url(self) -> str:
        return self._url

    @property
    def metrics(self) -> LiveIngestionMetrics:
        return self._metrics

    async def run(
        self,
        handler: MessageHandler,
        stop_event: asyncio.Event,
    ) -> None:
        if not callable(handler) or not isinstance(stop_event, asyncio.Event):
            raise TypeError("Client run requires a handler and asyncio.Event.")
        first_connection = True
        while not stop_event.is_set():
            self._state = ConnectionState.CONNECTING
            try:
                async with self._connector(
                    self._url,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=10,
                    max_queue=1024,
                ) as websocket:
                    now = self._utc_now()
                    self._state = ConnectionState.CONNECTED
                    self._connected_at = now
                    self._metrics.increment("connections")
                    if not first_connection:
                        self._reconnect_count += 1
                        self._metrics.increment("reconnects")
                    first_connection = False
                    while not stop_event.is_set():
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(),
                                timeout=self._heartbeat_timeout_seconds,
                            )
                        except TimeoutError as error:
                            self._state = ConnectionState.STALE
                            self._metrics.increment("heartbeat_timeouts")
                            await websocket.close(
                                code=1011,
                                reason="market stream heartbeat timeout",
                            )
                            raise HeartbeatTimeoutError(
                                "Binance market stream became stale."
                            ) from error
                        self._last_message_at = self._utc_now()
                        self._consecutive_failures = 0
                        self._metrics.increment("messages_received")
                        await handler(message)
            except asyncio.CancelledError:
                self._state = ConnectionState.STOPPED
                raise
            except (OSError, ConnectionError, ConnectionClosed):
                self._state = ConnectionState.DISCONNECTED
                self._metrics.increment("disconnects")
                self._consecutive_failures += 1
                if stop_event.is_set():
                    break
                delay = min(
                    self._backoff_initial_seconds
                    * (2 ** (self._consecutive_failures - 1)),
                    self._backoff_max_seconds,
                )
                await self._sleeper(delay)
        self._state = ConnectionState.STOPPED

    def health(self, now: datetime | None = None) -> ConnectionHealth:
        observed_at = _utc(now or self._utc_now(), "health observation")
        fresh = (
            self._last_message_at is not None
            and observed_at - self._last_message_at
            <= timedelta(seconds=self._heartbeat_timeout_seconds)
        )
        return ConnectionHealth(
            state=self._state,
            connected_at=self._connected_at,
            last_message_at=self._last_message_at,
            reconnect_count=self._reconnect_count,
            consecutive_failures=self._consecutive_failures,
            healthy=self._state is ConnectionState.CONNECTED and fresh,
        )

    def _utc_now(self) -> datetime:
        return _utc(self._clock(), "client clock")


def _websocket_connector(url: str, **kwargs: object) -> WebSocketContext:
    from websockets.asyncio.client import connect

    return connect(url, **kwargs)


def _json_object(raw_message: str | bytes) -> dict[str, Any]:
    if not isinstance(raw_message, (str, bytes)):
        raise LiveMessageValidationError("WebSocket message must be text or bytes.")
    try:
        value = json.loads(raw_message)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LiveMessageValidationError("WebSocket message is invalid JSON.") from error
    if not isinstance(value, dict):
        raise LiveMessageValidationError("WebSocket message must be a JSON object.")
    return value


def _milliseconds(value: object, name: str) -> datetime:
    integer = _non_negative_int(value, name)
    try:
        return datetime.fromtimestamp(integer // 1000, tz=timezone.utc) + timedelta(
            milliseconds=integer % 1000
        )
    except (OverflowError, OSError, ValueError) as error:
        raise LiveMessageValidationError(f"{name} is outside the timestamp range.") from error


def _timeframe(value: object) -> CandleTimeframe:
    try:
        timeframe = CandleTimeframe(value)
    except (TypeError, ValueError) as error:
        raise LiveMessageValidationError("Kline interval is unsupported.") from error
    if timeframe not in NATIVE_TIMEFRAMES:
        raise LiveMessageValidationError("Kline interval is not a native input.")
    return timeframe


def _decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, str) or not value:
        raise LiveMessageValidationError(f"Kline {name} must be a decimal string.")
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise LiveMessageValidationError(f"Kline {name} is invalid.") from error


def _non_negative_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LiveMessageValidationError(f"Kline {name} must be a non-negative integer.")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
    return value.astimezone(timezone.utc)
