"""Historical market data sample and paginated backfill orchestration."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
from typing import Callable

from app.market_data.models import Candle, CandleTimeframe
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.market_data.validation import CandleValidationReport, validate_candles


logger = logging.getLogger("uvicorn.error")
KRAKEN_OHLC_PAGE_LIMIT = 720


@dataclass(frozen=True, slots=True)
class BackfillProgress:
    page_number: int
    requested_since: datetime
    provider_row_count: int
    accepted_completed_count: int
    new_unique_completed_count: int
    excluded_incomplete_count: int
    excluded_pagination_overlap_count: int
    cumulative_completed_count: int
    next_since: datetime


@dataclass(frozen=True, slots=True)
class HistoricalSample:
    provider: str
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    requested_start: datetime
    requested_end_exclusive: datetime
    retrieved_at: datetime
    candles: tuple[Candle, ...]
    validation_report: CandleValidationReport
    pages_fetched: int = 1
    excluded_incomplete_candle_count: int = 0
    excluded_pagination_overlap_count: int = 0
    provider_page_limit: int = KRAKEN_OHLC_PAGE_LIMIT
    provider_limit_reached: bool = False
    pagination_exhausted: bool = True
    progress: tuple[BackfillProgress, ...] = ()


async def fetch_btc_usd_daily_sample(
    provider: MarketDataProvider,
) -> HistoricalSample:
    timeframe = CandleTimeframe.DAY_1
    requested_end = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    requested_start = requested_end - timedelta(days=90)
    candles = await provider.get_historical_candles(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        start=requested_start,
        end=requested_end,
    )
    retrieved_at = datetime.now(timezone.utc)
    validation_report = validate_candles(
        candles=candles,
        timeframe=timeframe,
        expected_start=requested_start,
        expected_end=requested_end,
    )

    return HistoricalSample(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=requested_start,
        requested_end_exclusive=requested_end,
        retrieved_at=retrieved_at,
        candles=candles,
        validation_report=validation_report,
    )


async def fetch_btc_usd_daily_backfill(
    provider: MarketDataProvider,
    requested_start: datetime,
    max_pages: int,
    progress_callback: Callable[[BackfillProgress], None] | None = None,
) -> HistoricalSample:
    if requested_start.tzinfo is None or requested_start.utcoffset() is None:
        raise MarketDataProviderError(
            "Historical backfill start must be timezone-aware."
        )
    if max_pages <= 0:
        raise MarketDataProviderError(
            "Historical backfill max_pages must be positive."
        )

    timeframe = CandleTimeframe.DAY_1
    requested_end = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    requested_start = requested_start.astimezone(timezone.utc)
    if requested_start >= requested_end:
        raise MarketDataProviderError(
            "Historical backfill start must precede today in UTC."
        )

    cursor = requested_start
    candles: list[Candle] = []
    completed_by_timestamp: dict[datetime, Candle] = {}
    progress_events: list[BackfillProgress] = []
    excluded_incomplete_count = 0
    excluded_pagination_overlap_count = 0
    provider_limit_reached = False
    pagination_exhausted = False

    while len(progress_events) < max_pages:
        page = await provider.get_historical_candle_page(
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe=timeframe,
            since=cursor,
        )
        provider_limit_reached = (
            provider_limit_reached
            or len(page.candles) >= KRAKEN_OHLC_PAGE_LIMIT
        )
        accepted: list[Candle] = []
        page_incomplete_count = 0
        page_overlap_count = 0
        new_unique_count = 0
        timestamps_seen_before_page = set(completed_by_timestamp)
        for candle in page.candles:
            timestamp = candle.timestamp
            if timestamp is not None and timestamp >= requested_end:
                page_incomplete_count += 1
                continue
            existing = (
                completed_by_timestamp.get(timestamp)
                if timestamp is not None
                else None
            )
            if (
                timestamp is not None
                and timestamp in timestamps_seen_before_page
                and existing == candle
            ):
                page_overlap_count += 1
                continue
            accepted.append(candle)
            if (
                timestamp is not None
                and timestamp not in completed_by_timestamp
            ):
                completed_by_timestamp[timestamp] = candle
                new_unique_count += 1

        candles.extend(accepted)
        excluded_incomplete_count += page_incomplete_count
        excluded_pagination_overlap_count += page_overlap_count
        next_since = datetime.fromtimestamp(
            page.next_since,
            tz=timezone.utc,
        )
        progress = BackfillProgress(
            page_number=len(progress_events) + 1,
            requested_since=cursor,
            provider_row_count=len(page.candles),
            accepted_completed_count=len(accepted),
            new_unique_completed_count=new_unique_count,
            excluded_incomplete_count=page_incomplete_count,
            excluded_pagination_overlap_count=page_overlap_count,
            cumulative_completed_count=len(candles),
            next_since=next_since,
        )
        progress_events.append(progress)
        logger.info(
            (
                "Historical backfill page=%s rows=%s completed=%s "
                "new_unique=%s incomplete=%s overlap=%s "
                "cumulative=%s next_since=%s"
            ),
            progress.page_number,
            progress.provider_row_count,
            progress.accepted_completed_count,
            progress.new_unique_completed_count,
            progress.excluded_incomplete_count,
            progress.excluded_pagination_overlap_count,
            progress.cumulative_completed_count,
            progress.next_since.isoformat(),
        )
        if progress_callback is not None:
            progress_callback(progress)

        if (
            not page.candles
            or new_unique_count == 0
            or page.next_since >= int(requested_end.timestamp())
        ):
            pagination_exhausted = True
            break
        if page.next_since <= int(cursor.timestamp()):
            raise MarketDataProviderError(
                "Kraken OHLC pagination cursor did not advance."
            )
        cursor = next_since

    if not pagination_exhausted:
        raise MarketDataProviderError(
            "Historical backfill reached max_pages before pagination "
            "was exhausted."
        )

    completed_candles = tuple(candles)
    first_timestamp = next(
        (
            candle.timestamp
            for candle in completed_candles
            if candle.timestamp is not None
        ),
        requested_start,
    )
    validation_report = validate_candles(
        candles=completed_candles,
        timeframe=timeframe,
        expected_start=first_timestamp,
        expected_end=requested_end,
    )

    return HistoricalSample(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=requested_start,
        requested_end_exclusive=requested_end,
        retrieved_at=datetime.now(timezone.utc),
        candles=completed_candles,
        validation_report=validation_report,
        pages_fetched=len(progress_events),
        excluded_incomplete_candle_count=excluded_incomplete_count,
        excluded_pagination_overlap_count=(
            excluded_pagination_overlap_count
        ),
        provider_page_limit=KRAKEN_OHLC_PAGE_LIMIT,
        provider_limit_reached=provider_limit_reached,
        pagination_exhausted=pagination_exhausted,
        progress=tuple(progress_events),
    )
