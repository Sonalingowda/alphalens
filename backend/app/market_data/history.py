"""Historical market data sample and paginated backfill orchestration."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Callable
from uuid import UUID

from app.market_data.models import Candle, CandleTimeframe
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.market_data.validation import (
    CandleValidationReport,
    floor_timeframe_boundary,
    timeframe_duration,
    validate_candles,
)


logger = logging.getLogger("uvicorn.error")
KRAKEN_OHLC_PAGE_LIMIT = 720
TEN_MINUTE_DERIVATION = "utc_5m_pair_v1"


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
    source_timeframe: CandleTimeframe | None = None
    derivation_method: str | None = None
    source_ingestion_batch_id: UUID | None = None


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


async def fetch_btc_usd_intraday_native(
    provider: MarketDataProvider,
    timeframe: CandleTimeframe,
    now: datetime | None = None,
) -> HistoricalSample:
    if timeframe not in {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_15,
    }:
        raise MarketDataProviderError(
            "Native intraday ingestion supports only Kraken 5m and 15m candles."
        )

    retrieved_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    requested_end = floor_timeframe_boundary(retrieved_at, timeframe)
    duration = timeframe_duration(timeframe)
    requested_start = requested_end - (duration * KRAKEN_OHLC_PAGE_LIMIT)
    page = await provider.get_historical_candle_page(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        since=requested_start,
    )

    completed: list[Candle] = []
    incomplete_count = 0
    for candle in page.candles:
        if candle.timestamp is not None and candle.timestamp >= requested_end:
            incomplete_count += 1
            continue
        completed.append(candle)

    available_timestamps = tuple(
        candle.timestamp
        for candle in completed
        if candle.timestamp is not None
    )
    if not available_timestamps:
        raise MarketDataProviderError(
            f"Kraken returned no completed {timeframe.value} BTC/USD candles."
        )
    available_start = available_timestamps[0]
    validation_report = validate_candles(
        candles=tuple(completed),
        timeframe=timeframe,
        expected_start=available_start,
        expected_end=requested_end,
    )
    progress = BackfillProgress(
        page_number=1,
        requested_since=requested_start,
        provider_row_count=len(page.candles),
        accepted_completed_count=len(completed),
        new_unique_completed_count=len(completed),
        excluded_incomplete_count=incomplete_count,
        excluded_pagination_overlap_count=0,
        cumulative_completed_count=len(completed),
        next_since=datetime.fromtimestamp(page.next_since, tz=timezone.utc),
    )
    logger.info(
        (
            "Intraday fetch timeframe=%s rows=%s completed=%s incomplete=%s "
            "available_start=%s available_end=%s"
        ),
        timeframe.value,
        len(page.candles),
        len(completed),
        incomplete_count,
        available_start.isoformat(),
        available_timestamps[-1].isoformat(),
    )
    return HistoricalSample(
        provider="kraken",
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        requested_start=requested_start,
        requested_end_exclusive=requested_end,
        retrieved_at=retrieved_at,
        candles=tuple(completed),
        validation_report=validation_report,
        pages_fetched=1,
        excluded_incomplete_candle_count=incomplete_count,
        provider_page_limit=KRAKEN_OHLC_PAGE_LIMIT,
        provider_limit_reached=(
            len(page.candles) >= KRAKEN_OHLC_PAGE_LIMIT
        ),
        pagination_exhausted=True,
        progress=(progress,),
    )


def derive_btc_usd_10m_sample(
    source: HistoricalSample,
    source_ingestion_batch_id: UUID,
) -> HistoricalSample:
    if source.timeframe is not CandleTimeframe.MINUTE_5:
        raise MarketDataProviderError(
            "10m candles must be derived from a 5m source sample."
        )
    if not source.validation_report.passed:
        raise MarketDataProviderError(
            "10m candles cannot be derived from a failed 5m validation batch."
        )

    source_by_timestamp = {
        candle.timestamp: candle
        for candle in source.candles
        if candle.timestamp is not None
    }
    first_source = min(source_by_timestamp, default=None)
    if first_source is None:
        raise MarketDataProviderError(
            "10m derivation requires completed 5m source candles."
        )

    derived_start = floor_timeframe_boundary(
        first_source,
        CandleTimeframe.MINUTE_10,
    )
    if derived_start < first_source:
        derived_start += timeframe_duration(CandleTimeframe.MINUTE_10)
    derived_end = floor_timeframe_boundary(
        source.requested_end_exclusive,
        CandleTimeframe.MINUTE_10,
    )

    derived: list[Candle] = []
    bucket = derived_start
    five_minutes = timeframe_duration(CandleTimeframe.MINUTE_5)
    ten_minutes = timeframe_duration(CandleTimeframe.MINUTE_10)
    while bucket < derived_end:
        first = source_by_timestamp.get(bucket)
        second = source_by_timestamp.get(bucket + five_minutes)
        if first is not None and second is not None:
            derived.append(aggregate_btc_usd_10m_candle(first, second, bucket))
        bucket += ten_minutes

    validation_report = validate_candles(
        candles=tuple(derived),
        timeframe=CandleTimeframe.MINUTE_10,
        expected_start=derived_start,
        expected_end=derived_end,
    )
    progress = BackfillProgress(
        page_number=1,
        requested_since=source.requested_start,
        provider_row_count=len(source.candles),
        accepted_completed_count=len(derived),
        new_unique_completed_count=len(derived),
        excluded_incomplete_count=source.excluded_incomplete_candle_count,
        excluded_pagination_overlap_count=0,
        cumulative_completed_count=len(derived),
        next_since=derived_end,
    )
    return HistoricalSample(
        provider=source.provider,
        asset_identifier=source.asset_identifier,
        quote_currency=source.quote_currency,
        timeframe=CandleTimeframe.MINUTE_10,
        requested_start=derived_start,
        requested_end_exclusive=derived_end,
        retrieved_at=source.retrieved_at,
        candles=tuple(derived),
        validation_report=validation_report,
        pages_fetched=source.pages_fetched,
        excluded_incomplete_candle_count=(
            source.excluded_incomplete_candle_count
        ),
        provider_page_limit=source.provider_page_limit,
        provider_limit_reached=source.provider_limit_reached,
        pagination_exhausted=source.pagination_exhausted,
        progress=(progress,),
        source_timeframe=CandleTimeframe.MINUTE_5,
        derivation_method=TEN_MINUTE_DERIVATION,
        source_ingestion_batch_id=source_ingestion_batch_id,
    )


def aggregate_btc_usd_10m_candle(
    first: Candle,
    second: Candle,
    timestamp: datetime,
) -> Candle:
    """Apply the frozen exact two-candle 10m aggregation formula."""
    values = (
        first.open,
        first.high,
        first.low,
        first.close,
        first.volume,
        second.open,
        second.high,
        second.low,
        second.close,
        second.volume,
    )
    if any(value is None for value in values):
        raise MarketDataProviderError(
            "Validated 5m source candle contains a missing value."
        )

    first_open = _required_decimal(first.open)
    first_high = _required_decimal(first.high)
    first_low = _required_decimal(first.low)
    first_volume = _required_decimal(first.volume)
    second_high = _required_decimal(second.high)
    second_low = _required_decimal(second.low)
    second_close = _required_decimal(second.close)
    second_volume = _required_decimal(second.volume)
    return Candle(
        timestamp=timestamp,
        open=first_open,
        high=max(first_high, second_high),
        low=min(first_low, second_low),
        close=second_close,
        volume=first_volume + second_volume,
    )


def _required_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise MarketDataProviderError(
            "Validated source candle contains a non-decimal value."
        )
    return value
