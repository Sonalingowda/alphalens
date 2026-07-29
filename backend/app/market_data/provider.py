"""Market data provider contract and shared errors."""

from datetime import datetime
from typing import Protocol

from app.market_data.models import (
    Candle,
    CandleTimeframe,
    HistoricalCandlePage,
    MarketQuote,
)


class MarketDataProviderError(RuntimeError):
    """Raised when a provider cannot return valid normalized market data."""


class MarketDataProvider(Protocol):
    async def get_current_quote(
        self,
        asset_identifier: str,
        quote_currency: str = "USD",
    ) -> MarketQuote:
        """Return the latest available quote for an asset."""

    async def get_historical_candles(
        self,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        """Return candles in the half-open time range [start, end)."""

    async def get_historical_candle_page(
        self,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        since: datetime,
    ) -> HistoricalCandlePage:
        """Return one provider page and its next incremental cursor."""
