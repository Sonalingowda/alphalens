"""Live, keyless market data service for completed paper-trading bars."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from typing import Protocol

from app.market_data.models import Candle, CandleTimeframe
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.market_data.validation import validate_candles
from app.paper_trading.models import PaperMarketSnapshot


class PaperMarketDataService(Protocol):
    async def fetch_completed_candles(
        self,
        *,
        as_of: datetime,
        history_observations: int,
    ) -> PaperMarketSnapshot: ...


class KrakenPaperMarketDataService:
    """Read the latest completed daily Kraken candles without credentials."""

    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    async def fetch_completed_candles(
        self,
        *,
        as_of: datetime,
        history_observations: int,
    ) -> PaperMarketSnapshot:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("Paper market-data time must be timezone-aware.")
        if not 50 <= history_observations <= 720:
            raise ValueError("Kraken history observations must be 50..720.")
        completed_end = as_of.astimezone(timezone.utc).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        page = await self._provider.get_historical_candle_page(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=CandleTimeframe.DAY_1,
            since=completed_end - timedelta(days=history_observations + 1),
        )
        candles = tuple(
            candle
            for candle in page.candles
            if candle.timestamp is not None
            and candle.timestamp < completed_end
        )[-history_observations:]
        if not candles:
            raise MarketDataProviderError(
                "Kraken returned no completed daily candles."
            )
        first = candles[0].timestamp
        if first is None:
            raise MarketDataProviderError(
                "Kraken returned an invalid first candle."
            )
        validation = validate_candles(
            candles=candles,
            timeframe=CandleTimeframe.DAY_1,
            expected_start=first,
            expected_end=completed_end,
        )
        if not validation.passed:
            codes = ",".join(item.code for item in validation.issues)
            raise MarketDataProviderError(
                f"Completed Kraken candles failed validation: {codes}."
            )
        latest = candles[-1].timestamp
        if latest is None:
            raise MarketDataProviderError(
                "Kraken returned an invalid latest candle."
            )
        retrieved_at = as_of.astimezone(timezone.utc)
        return PaperMarketSnapshot(
            provider="kraken",
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe="1d",
            retrieved_at=retrieved_at,
            completed_through=latest,
            candles=candles,
            market_data_hash=_market_hash(candles),
        )


def _market_hash(candles: tuple[Candle, ...]) -> str:
    payload = [
        {
            "timestamp": item.timestamp.isoformat()
            if item.timestamp is not None
            else None,
            "open": _decimal(item.open),
            "high": _decimal(item.high),
            "low": _decimal(item.low),
            "close": _decimal(item.close),
            "volume": _decimal(item.volume),
        }
        for item in candles
    ]
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None

