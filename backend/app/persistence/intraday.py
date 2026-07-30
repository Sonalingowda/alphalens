"""BTC/USD intraday ingestion orchestration."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.market_data.history import (
    HistoricalSample,
    derive_btc_usd_10m_sample,
    fetch_btc_usd_intraday_native,
)
from app.market_data.models import CandleTimeframe
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.persistence.candles import (
    CandlePersistenceResult,
    persist_historical_sample,
)


@dataclass(frozen=True, slots=True)
class IntradayIngestionItem:
    sample: HistoricalSample
    persistence: CandlePersistenceResult


@dataclass(frozen=True, slots=True)
class IntradayIngestionResult:
    items: tuple[IntradayIngestionItem, ...]


async def ingest_btc_usd_intraday(
    provider: MarketDataProvider,
    session_maker: async_sessionmaker[AsyncSession],
) -> IntradayIngestionResult:
    five_minute = await fetch_btc_usd_intraday_native(
        provider,
        CandleTimeframe.MINUTE_5,
    )
    fifteen_minute = await fetch_btc_usd_intraday_native(
        provider,
        CandleTimeframe.MINUTE_15,
    )

    five_result = await _persist(session_maker, five_minute)
    fifteen_result = await _persist(session_maker, fifteen_minute)
    if not five_result.validation_passed:
        raise MarketDataProviderError(
            "The 5m source batch failed validation; 10m derivation was not persisted."
        )

    ten_minute = derive_btc_usd_10m_sample(
        five_minute,
        source_ingestion_batch_id=five_result.ingestion_batch_id,
    )
    ten_result = await _persist(session_maker, ten_minute)
    return IntradayIngestionResult(
        items=(
            IntradayIngestionItem(five_minute, five_result),
            IntradayIngestionItem(ten_minute, ten_result),
            IntradayIngestionItem(fifteen_minute, fifteen_result),
        )
    )


async def _persist(
    session_maker: async_sessionmaker[AsyncSession],
    sample: HistoricalSample,
) -> CandlePersistenceResult:
    async with session_maker() as session:
        return await persist_historical_sample(session, sample)
