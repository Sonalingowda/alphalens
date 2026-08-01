"""Deterministic live candle aggregation, duplicate, and gap controls."""

from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json

from app.live_market_data.models import (
    CandleGap,
    CompletedCandle,
    LiveChronologyError,
    LiveMarketDataConflictError,
)
from app.market_data.history import aggregate_btc_usd_10m_candle
from app.market_data.models import Candle, CandleTimeframe


class CandleDeduplicator:
    def __init__(self) -> None:
        self._hash_by_identity: dict[
            tuple[str, CandleTimeframe, datetime], str
        ] = {}

    def classify(self, candle: CompletedCandle) -> bool:
        existing = self._hash_by_identity.get(candle.identity)
        if existing is None:
            return False
        if existing != candle.content_hash:
            raise LiveMarketDataConflictError(
                "Completed candle identity has conflicting immutable content."
            )
        return True

    def remember(self, candle: CompletedCandle) -> None:
        self._hash_by_identity[candle.identity] = candle.content_hash


class CandleGapDetector:
    def __init__(self) -> None:
        self._latest: dict[tuple[str, CandleTimeframe], datetime] = {}

    def seed(self, symbol: str, timeframe: CandleTimeframe, timestamp: datetime) -> None:
        key = (symbol, timeframe)
        current = self._latest.get(key)
        if current is None or timestamp > current:
            self._latest[key] = timestamp

    def inspect(self, candle: CompletedCandle) -> CandleGap | None:
        key = (candle.symbol, candle.timeframe)
        previous = self._latest.get(key)
        duration = _duration(candle.timeframe)
        if previous is None:
            return None
        if candle.open_time < previous:
            raise LiveChronologyError("Completed candle stream moved backward.")
        if candle.open_time == previous:
            return None
        expected = previous + duration
        if candle.open_time == expected:
            return None
        missing_count = int((candle.open_time - expected) / duration)
        return CandleGap(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            missing_start=expected,
            missing_end=candle.open_time - duration,
            missing_count=missing_count,
        )

    def remember(self, candle: CompletedCandle) -> None:
        self.seed(candle.symbol, candle.timeframe, candle.open_time)


class TenMinuteCandleAggregator:
    """Reuse the frozen 5m-to-10m OHLCV formula for live data."""

    def __init__(self) -> None:
        self._first_by_bucket: dict[datetime, CompletedCandle] = {}

    def add(self, candle: CompletedCandle) -> CompletedCandle | None:
        if candle.timeframe is not CandleTimeframe.MINUTE_5:
            raise ValueError("10m aggregation accepts only completed 5m candles.")
        bucket = candle.open_time.replace(
            minute=(candle.open_time.minute // 10) * 10,
            second=0,
            microsecond=0,
        )
        if candle.open_time == bucket:
            self._first_by_bucket[bucket] = candle
            return None
        if candle.open_time != bucket + timedelta(minutes=5):
            raise LiveChronologyError("5m candle is not aligned to a 10m bucket.")
        first = self._first_by_bucket.pop(bucket, None)
        if first is None:
            return None
        aggregated = aggregate_btc_usd_10m_candle(
            _market_candle(first),
            _market_candle(candle),
            bucket,
        )
        source_hashes = (first.source_payload_hash, candle.source_payload_hash)
        payload = json.dumps(
            {
                "derivation": "two_adjacent_5m_utc_v1",
                "source_hashes": source_hashes,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return CompletedCandle(
            provider="alphalens_derived",
            symbol=candle.symbol,
            timeframe=CandleTimeframe.MINUTE_10,
            event_time=max(first.event_time, candle.event_time),
            open_time=bucket,
            close_time=candle.close_time,
            open=_required(aggregated.open),
            high=_required(aggregated.high),
            low=_required(aggregated.low),
            close=_required(aggregated.close),
            volume=_required(aggregated.volume),
            number_of_trades=first.number_of_trades + candle.number_of_trades,
            source_payload_hash=sha256(payload).hexdigest(),
            source_candle_hashes=source_hashes,
        )


def _market_candle(value: CompletedCandle) -> Candle:
    return Candle(
        timestamp=value.open_time,
        open=value.open,
        high=value.high,
        low=value.low,
        close=value.close,
        volume=value.volume,
    )


def _required(value: Decimal | None) -> Decimal:
    if value is None:
        raise RuntimeError("Frozen aggregation unexpectedly returned a null value.")
    return value


def _duration(timeframe: CandleTimeframe) -> timedelta:
    return {
        CandleTimeframe.MINUTE_5: timedelta(minutes=5),
        CandleTimeframe.MINUTE_10: timedelta(minutes=10),
        CandleTimeframe.MINUTE_15: timedelta(minutes=15),
    }[timeframe]
