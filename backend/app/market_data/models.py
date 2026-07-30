"""Normalized market data models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class CandleTimeframe(str, Enum):
    MINUTE_5 = "5m"
    MINUTE_10 = "10m"
    MINUTE_15 = "15m"
    DAY_1 = "1d"


@dataclass(frozen=True, slots=True)
class MarketQuote:
    asset_identifier: str
    quote_currency: str
    price: Decimal
    provider: str
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class Candle:
    timestamp: datetime | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: Decimal | None


@dataclass(frozen=True, slots=True)
class HistoricalCandlePage:
    candles: tuple[Candle, ...]
    next_since: int
