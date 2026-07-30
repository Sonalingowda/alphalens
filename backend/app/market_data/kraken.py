"""Kraken public market data provider."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.market_data.models import (
    Candle,
    CandleTimeframe,
    HistoricalCandlePage,
    MarketQuote,
)
from app.market_data.provider import MarketDataProviderError


class KrakenMarketDataProvider:
    provider_name = "kraken"
    _interval_minutes = {
        CandleTimeframe.MINUTE_5: 5,
        CandleTimeframe.MINUTE_15: 15,
        CandleTimeframe.DAY_1: 1440,
    }

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)

    async def get_current_quote(
        self,
        asset_identifier: str,
        quote_currency: str = "USD",
    ) -> MarketQuote:
        asset = asset_identifier.strip().upper()
        quote = quote_currency.strip().upper()
        if not asset or not quote:
            raise MarketDataProviderError(
                "Asset identifier and quote currency must be non-empty."
            )

        pair = f"{asset}/{quote}"
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = await client.get(
                    "/0/public/Ticker",
                    params={"pair": pair, "assetVersion": "1"},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MarketDataProviderError(
                f"Kraken returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise MarketDataProviderError(
                "Unable to reach the Kraken market data API."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataProviderError(
                "Kraken returned a non-JSON response."
            ) from exc

        return self._normalize_quote(payload, asset, quote, pair)

    def _normalize_quote(
        self,
        payload: Any,
        asset: str,
        quote: str,
        pair: str,
    ) -> MarketQuote:
        if not isinstance(payload, dict):
            raise MarketDataProviderError("Kraken returned a malformed response.")

        errors = payload.get("error")
        if not isinstance(errors, list):
            raise MarketDataProviderError("Kraken returned a malformed error field.")
        if errors:
            raise MarketDataProviderError(
                f"Kraken rejected the requested market pair: {', '.join(map(str, errors))}"
            )

        result = payload.get("result")
        if not isinstance(result, dict):
            raise MarketDataProviderError("Kraken returned a malformed result field.")

        ticker = result.get(pair)
        if not isinstance(ticker, dict):
            raise MarketDataProviderError(
                f"Kraken did not return ticker data for {pair}."
            )

        last_trade = ticker.get("c")
        if (
            not isinstance(last_trade, list)
            or not last_trade
            or not isinstance(last_trade[0], str)
        ):
            raise MarketDataProviderError(
                f"Kraken returned a malformed last-trade price for {pair}."
            )

        try:
            price = Decimal(last_trade[0])
        except InvalidOperation as exc:
            raise MarketDataProviderError(
                f"Kraken returned an invalid price for {pair}."
            ) from exc

        if not price.is_finite() or price <= 0:
            raise MarketDataProviderError(
                f"Kraken returned a non-positive price for {pair}."
            )

        return MarketQuote(
            asset_identifier=asset,
            quote_currency=quote,
            price=price,
            provider=self.provider_name,
            retrieved_at=datetime.now(timezone.utc),
        )

    async def get_historical_candles(
        self,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        start: datetime,
        end: datetime,
    ) -> tuple[Candle, ...]:
        if start.tzinfo is None or end.tzinfo is None:
            raise MarketDataProviderError(
                "Historical data boundaries must be timezone-aware."
            )
        if start >= end:
            raise MarketDataProviderError(
                "Historical data start must be earlier than end."
            )

        page = await self.get_historical_candle_page(
            asset_identifier=asset_identifier,
            quote_currency=quote_currency,
            timeframe=timeframe,
            since=start,
        )
        return tuple(
            candle
            for candle in page.candles
            if candle.timestamp is None or start <= candle.timestamp < end
        )

    async def get_historical_candle_page(
        self,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        since: datetime,
    ) -> HistoricalCandlePage:
        asset = asset_identifier.strip().upper()
        quote = quote_currency.strip().upper()
        if not asset or not quote:
            raise MarketDataProviderError(
                "Asset identifier and quote currency must be non-empty."
            )
        if since.tzinfo is None or since.utcoffset() is None:
            raise MarketDataProviderError(
                "Historical pagination cursor must be timezone-aware."
            )

        interval_minutes = self._interval_minutes.get(timeframe)
        if interval_minutes is None:
            raise MarketDataProviderError(
                f"Kraken does not support timeframe {timeframe.value}."
            )
        pair = f"{asset}/{quote}"
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            ) as client:
                response = await client.get(
                    "/0/public/OHLC",
                    params={
                        "pair": pair,
                        "interval": interval_minutes,
                        "since": int(since.timestamp()),
                        "assetVersion": "1",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise MarketDataProviderError(
                f"Kraken returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise MarketDataProviderError(
                "Unable to reach the Kraken market data API."
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataProviderError(
                "Kraken returned a non-JSON response."
            ) from exc

        rows, next_since = self._extract_ohlc_page(payload, pair)
        return HistoricalCandlePage(
            candles=tuple(self._normalize_candle(row) for row in rows),
            next_since=next_since,
        )

    def _extract_ohlc_page(
        self,
        payload: Any,
        pair: str,
    ) -> tuple[list[list[Any]], int]:
        if not isinstance(payload, dict):
            raise MarketDataProviderError("Kraken returned a malformed response.")

        errors = payload.get("error")
        if not isinstance(errors, list):
            raise MarketDataProviderError("Kraken returned a malformed error field.")
        if errors:
            raise MarketDataProviderError(
                f"Kraken rejected the requested market pair: {', '.join(map(str, errors))}"
            )

        result = payload.get("result")
        if not isinstance(result, dict):
            raise MarketDataProviderError("Kraken returned a malformed result field.")

        rows = result.get(pair)
        if not isinstance(rows, list) or any(
            not isinstance(row, list) for row in rows
        ):
            raise MarketDataProviderError(
                f"Kraken returned malformed OHLC data for {pair}."
            )

        next_since = result.get("last")
        if (
            not isinstance(next_since, int)
            or isinstance(next_since, bool)
            or next_since < 0
        ):
            raise MarketDataProviderError(
                "Kraken returned a malformed OHLC pagination cursor."
            )

        return rows, next_since

    def _normalize_candle(self, row: list[Any]) -> Candle:
        return Candle(
            timestamp=self._parse_timestamp(self._row_value(row, 0)),
            open=self._parse_decimal(self._row_value(row, 1)),
            high=self._parse_decimal(self._row_value(row, 2)),
            low=self._parse_decimal(self._row_value(row, 3)),
            close=self._parse_decimal(self._row_value(row, 4)),
            volume=self._parse_decimal(self._row_value(row, 6)),
        )

    @staticmethod
    def _row_value(row: list[Any], index: int) -> Any:
        return row[index] if index < len(row) else None

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, (int, float)):
            return None
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal | None:
        if not isinstance(value, (str, int, float)):
            return None
        try:
            parsed = Decimal(str(value))
        except InvalidOperation:
            return None
        return parsed if parsed.is_finite() else None
