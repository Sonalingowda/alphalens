"""Paginated historical backfill safeguards."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.market_data.history import (
    BackfillProgress,
    fetch_btc_usd_daily_backfill,
)
from app.market_data.models import (
    Candle,
    CandleTimeframe,
    HistoricalCandlePage,
)
from app.market_data.provider import MarketDataProviderError


class HistoricalBackfillTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_end_boundary_is_respected_across_pages(self) -> None:
        start = _completed_end() - timedelta(days=5)
        requested_end = start + timedelta(days=3)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(_candle(start), _candle(start + timedelta(days=1))),
                    next_since=int((start + timedelta(days=2)).timestamp()),
                ),
                int((start + timedelta(days=2)).timestamp()): (
                    HistoricalCandlePage(
                        candles=(
                            _candle(start + timedelta(days=2)),
                            _candle(requested_end),
                            _candle(requested_end + timedelta(days=1)),
                        ),
                        next_since=int(
                            (requested_end + timedelta(days=1)).timestamp()
                        ),
                    )
                ),
            }
        )

        sample = await fetch_btc_usd_daily_backfill(
            provider,
            requested_start=start,
            max_pages=5,
            requested_end_exclusive=requested_end,
        )

        self.assertTrue(sample.validation_report.passed)
        self.assertEqual(sample.requested_end_exclusive, requested_end)
        self.assertEqual(
            tuple(candle.timestamp for candle in sample.candles),
            tuple(start + timedelta(days=index) for index in range(3)),
        )
        self.assertEqual(sample.excluded_incomplete_candle_count, 2)
        self.assertEqual(sample.pages_fetched, 2)

    async def test_paginates_validates_and_excludes_current_candle(self) -> None:
        end = _completed_end()
        start = end - timedelta(days=4)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(
                        _candle(start),
                        _candle(start + timedelta(days=1)),
                    ),
                    next_since=int((start + timedelta(days=2)).timestamp()),
                ),
                int((start + timedelta(days=2)).timestamp()): (
                    HistoricalCandlePage(
                        candles=(
                            _candle(start + timedelta(days=2)),
                            _candle(start + timedelta(days=3)),
                            _candle(end),
                        ),
                        next_since=int(end.timestamp()),
                    )
                ),
            }
        )
        progress: list[BackfillProgress] = []

        sample = await fetch_btc_usd_daily_backfill(
            provider,
            requested_start=start,
            max_pages=5,
            progress_callback=progress.append,
        )

        self.assertTrue(sample.validation_report.passed)
        self.assertTrue(sample.pagination_exhausted)
        self.assertEqual(sample.pages_fetched, 2)
        self.assertEqual(len(sample.candles), 4)
        self.assertEqual(sample.excluded_incomplete_candle_count, 1)
        self.assertEqual(len(progress), 2)
        self.assertEqual(progress[-1].cumulative_completed_count, 4)

    async def test_repeating_bounded_request_is_stable(self) -> None:
        start = _completed_end() - timedelta(days=3)
        requested_end = start + timedelta(days=2)
        pages = {
            int(start.timestamp()): HistoricalCandlePage(
                candles=(
                    _candle(start),
                    _candle(start + timedelta(days=1)),
                    _candle(requested_end),
                ),
                next_since=int(requested_end.timestamp()),
            )
        }

        first = await fetch_btc_usd_daily_backfill(
            _PagedProvider(pages),
            requested_start=start,
            max_pages=5,
            requested_end_exclusive=requested_end,
        )
        second = await fetch_btc_usd_daily_backfill(
            _PagedProvider(pages),
            requested_start=start,
            max_pages=5,
            requested_end_exclusive=requested_end,
        )

        self.assertEqual(first.candles, second.candles)
        self.assertEqual(first.requested_start, second.requested_start)
        self.assertEqual(
            first.requested_end_exclusive,
            second.requested_end_exclusive,
        )
        self.assertEqual(first.progress, second.progress)

    async def test_exact_page_boundary_overlap_is_audited(self) -> None:
        end = _completed_end()
        start = end - timedelta(days=3)
        duplicate_timestamp = start + timedelta(days=1)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(
                        _candle(start),
                        _candle(duplicate_timestamp),
                    ),
                    next_since=int(duplicate_timestamp.timestamp()),
                ),
                int(duplicate_timestamp.timestamp()): HistoricalCandlePage(
                    candles=(
                        _candle(duplicate_timestamp),
                        _candle(start + timedelta(days=2)),
                        _candle(end),
                    ),
                    next_since=int(end.timestamp()),
                ),
            }
        )

        sample = await fetch_btc_usd_daily_backfill(
            provider,
            requested_start=start,
            max_pages=5,
        )

        self.assertTrue(sample.validation_report.passed)
        self.assertEqual(sample.excluded_pagination_overlap_count, 1)
        self.assertEqual(len(sample.candles), 3)

    async def test_duplicate_within_page_fails_validation(self) -> None:
        end = _completed_end()
        start = end - timedelta(days=2)
        duplicate = _candle(start)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(
                        duplicate,
                        duplicate,
                        _candle(start + timedelta(days=1)),
                        _candle(end),
                    ),
                    next_since=int(end.timestamp()),
                )
            }
        )

        sample = await fetch_btc_usd_daily_backfill(
            provider,
            requested_start=start,
            max_pages=5,
        )

        self.assertFalse(sample.validation_report.passed)
        self.assertIn(
            "duplicate_timestamp",
            {issue.code for issue in sample.validation_report.issues},
        )

    async def test_missing_candle_fails_validation(self) -> None:
        end = _completed_end()
        start = end - timedelta(days=3)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(
                        _candle(start),
                        _candle(start + timedelta(days=2)),
                        _candle(end),
                    ),
                    next_since=int(end.timestamp()),
                )
            }
        )

        sample = await fetch_btc_usd_daily_backfill(
            provider,
            requested_start=start,
            max_pages=5,
        )

        self.assertFalse(sample.validation_report.passed)
        self.assertIn(
            "missing_candle",
            {issue.code for issue in sample.validation_report.issues},
        )

    async def test_page_limit_prevents_partial_success(self) -> None:
        end = _completed_end()
        start = end - timedelta(days=3)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(_candle(start),),
                    next_since=int((start + timedelta(days=1)).timestamp()),
                )
            }
        )

        with self.assertRaises(MarketDataProviderError):
            await fetch_btc_usd_daily_backfill(
                provider,
                requested_start=start,
                max_pages=1,
            )

    async def test_invalid_prices_and_volume_fail_validation(self) -> None:
        end = _completed_end()
        start = end - timedelta(days=1)
        provider = _PagedProvider(
            {
                int(start.timestamp()): HistoricalCandlePage(
                    candles=(
                        Candle(
                            timestamp=start,
                            open=Decimal("100"),
                            high=Decimal("90"),
                            low=Decimal("110"),
                            close=Decimal("105"),
                            volume=Decimal("-1"),
                        ),
                        _candle(end),
                    ),
                    next_since=int(end.timestamp()),
                )
            }
        )

        sample = await fetch_btc_usd_daily_backfill(
            provider,
            requested_start=start,
            max_pages=5,
        )

        issue_codes = {
            issue.code for issue in sample.validation_report.issues
        }
        self.assertFalse(sample.validation_report.passed)
        self.assertIn("low_above_high", issue_codes)
        self.assertIn("negative_volume", issue_codes)


class _PagedProvider:
    def __init__(self, pages: dict[int, HistoricalCandlePage]) -> None:
        self._pages = pages

    async def get_historical_candle_page(
        self,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        since: datetime,
    ) -> HistoricalCandlePage:
        self.assert_request(asset_identifier, quote_currency, timeframe)
        return self._pages[int(since.timestamp())]

    @staticmethod
    def assert_request(
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
    ) -> None:
        if (
            asset_identifier != "BTC"
            or quote_currency != "USD"
            or timeframe is not CandleTimeframe.DAY_1
        ):
            raise AssertionError("Unexpected backfill request.")


def _completed_end() -> datetime:
    return datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def _candle(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("1.23456789"),
    )


if __name__ == "__main__":
    unittest.main()
