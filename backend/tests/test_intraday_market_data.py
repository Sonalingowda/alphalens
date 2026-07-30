"""AlphaLens v2 intraday market-data contract tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.market_data.history import (
    HistoricalSample,
    TEN_MINUTE_DERIVATION,
    derive_btc_usd_10m_sample,
    fetch_btc_usd_intraday_native,
)
from app.market_data.kraken import KrakenMarketDataProvider
from app.market_data.models import (
    Candle,
    CandleTimeframe,
    HistoricalCandlePage,
)
from app.market_data.provider import MarketDataProviderError
from app.market_data.validation import validate_candles


class IntradayMarketDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_fetch_excludes_uncommitted_candle(self) -> None:
        now = datetime(2026, 7, 30, 12, 7, tzinfo=timezone.utc)
        candles = tuple(
            _candle(datetime(2026, 7, 30, 11, 45, tzinfo=timezone.utc) + offset)
            for offset in (
                timedelta(),
                timedelta(minutes=5),
                timedelta(minutes=10),
                timedelta(minutes=15),
                timedelta(minutes=20),
            )
        )
        provider = _IntradayProvider(candles, next_since=1_775_000_000)

        sample = await fetch_btc_usd_intraday_native(
            provider,
            CandleTimeframe.MINUTE_5,
            now=now,
        )

        self.assertTrue(sample.validation_report.passed)
        self.assertEqual(sample.timeframe, CandleTimeframe.MINUTE_5)
        self.assertEqual(len(sample.candles), 4)
        self.assertEqual(sample.excluded_incomplete_candle_count, 1)
        self.assertEqual(
            sample.requested_end_exclusive,
            datetime(2026, 7, 30, 12, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(provider.requested_timeframe, CandleTimeframe.MINUTE_5)

    async def test_kraken_rejects_non_native_10m_request(self) -> None:
        provider = KrakenMarketDataProvider(
            base_url="https://api.kraken.test",
            timeout_seconds=1,
        )

        with self.assertRaisesRegex(
            MarketDataProviderError,
            "does not support timeframe 10m",
        ):
            await provider.get_historical_candle_page(
                asset_identifier="BTC",
                quote_currency="USD",
                timeframe=CandleTimeframe.MINUTE_10,
                since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_10m_derivation_uses_exact_ohlcv_formula(self) -> None:
        start = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
        candles = (
            _candle(start, open_price="100", high="110", low="95", close="105", volume="1.1"),
            _candle(start + timedelta(minutes=5), open_price="105", high="112", low="101", close="108", volume="2.2"),
            _candle(start + timedelta(minutes=10), open_price="108", high="115", low="107", close="114", volume="3.3"),
            _candle(start + timedelta(minutes=15), open_price="114", high="116", low="109", close="110", volume="4.4"),
        )
        source = _source_sample(candles, start, start + timedelta(minutes=20))
        source_batch_id = UUID("00000000-0000-0000-0000-000000000005")

        first = derive_btc_usd_10m_sample(source, source_batch_id)
        second = derive_btc_usd_10m_sample(source, source_batch_id)

        self.assertEqual(first, second)
        self.assertTrue(first.validation_report.passed)
        self.assertEqual(first.timeframe, CandleTimeframe.MINUTE_10)
        self.assertEqual(first.source_timeframe, CandleTimeframe.MINUTE_5)
        self.assertEqual(first.derivation_method, TEN_MINUTE_DERIVATION)
        self.assertEqual(first.source_ingestion_batch_id, source_batch_id)
        self.assertEqual(len(first.candles), 2)
        self.assertEqual(first.candles[0].open, Decimal("100"))
        self.assertEqual(first.candles[0].high, Decimal("112"))
        self.assertEqual(first.candles[0].low, Decimal("95"))
        self.assertEqual(first.candles[0].close, Decimal("108"))
        self.assertEqual(first.candles[0].volume, Decimal("3.3"))

    def test_misaligned_and_incomplete_candles_fail_validation(self) -> None:
        end = datetime(2026, 7, 30, 12, 10, tzinfo=timezone.utc)
        candle = _candle(
            datetime(2026, 7, 30, 12, 7, tzinfo=timezone.utc),
        )

        report = validate_candles(
            candles=(candle,),
            timeframe=CandleTimeframe.MINUTE_5,
            expected_start=end - timedelta(minutes=5),
            expected_end=end,
        )

        issue_codes = {issue.code for issue in report.issues}
        self.assertFalse(report.passed)
        self.assertIn("misaligned_timestamp", issue_codes)
        self.assertIn("incomplete_candle", issue_codes)


class _IntradayProvider:
    def __init__(
        self,
        candles: tuple[Candle, ...],
        next_since: int,
    ) -> None:
        self._page = HistoricalCandlePage(
            candles=candles,
            next_since=next_since,
        )
        self.requested_timeframe: CandleTimeframe | None = None

    async def get_historical_candle_page(
        self,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        since: datetime,
    ) -> HistoricalCandlePage:
        if asset_identifier != "BTC" or quote_currency != "USD":
            raise AssertionError("Unexpected market.")
        if since.tzinfo is None:
            raise AssertionError("Expected timezone-aware cursor.")
        self.requested_timeframe = timeframe
        return self._page


def _source_sample(
    candles: tuple[Candle, ...],
    start: datetime,
    end: datetime,
) -> HistoricalSample:
    report = validate_candles(
        candles=candles,
        timeframe=CandleTimeframe.MINUTE_5,
        expected_start=start,
        expected_end=end,
    )
    return HistoricalSample(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=CandleTimeframe.MINUTE_5,
        requested_start=start,
        requested_end_exclusive=end,
        retrieved_at=end,
        candles=candles,
        validation_report=report,
    )


def _candle(
    timestamp: datetime,
    open_price: str = "100",
    high: str = "110",
    low: str = "90",
    close: str = "105",
    volume: str = "1.23456789",
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal(volume),
    )


if __name__ == "__main__":
    unittest.main()
