"""BTC/USD intraday ingestion orchestration."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.market_data.history import (
    HistoricalSample,
    derive_btc_usd_10m_sample,
    fetch_btc_usd_intraday_native,
)
from app.market_data.models import CandleTimeframe
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.market_data.synchronization import (
    CoverageSnapshotReference,
    SynchronizedCoverageSnapshot,
    build_synchronized_coverage_snapshot,
)
from app.persistence.candles import (
    CandlePersistenceResult,
    persist_historical_sample,
)
from app.persistence.coverage import (
    load_historical_coverage_snapshot,
    persist_historical_coverage_snapshot,
)
from app.persistence.synchronization import (
    SynchronizedCoveragePersistenceResult,
    build_derivations_from_coverage,
    persist_synchronized_coverage_snapshot,
    persist_ten_minute_derivations,
)


@dataclass(frozen=True, slots=True)
class IntradayIngestionItem:
    sample: HistoricalSample
    persistence: CandlePersistenceResult


@dataclass(frozen=True, slots=True)
class IntradayIngestionResult:
    items: tuple[IntradayIngestionItem, ...]


@dataclass(frozen=True, slots=True)
class HistoricalSynchronizationResult:
    snapshot: SynchronizedCoverageSnapshot
    persistence: SynchronizedCoveragePersistenceResult


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


async def synchronize_btc_usd_intraday_coverage(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    as_of: datetime,
) -> HistoricalSynchronizationResult:
    """Persist one proven point-in-time 5m/10m/15m coverage snapshot."""
    references: list[CoverageSnapshotReference] = []
    for timeframe in (
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    ):
        async with session_maker() as session:
            snapshot = await load_historical_coverage_snapshot(
                session,
                timeframe,
                as_of=as_of,
            )
        async with session_maker() as session:
            persistence = await persist_historical_coverage_snapshot(
                session,
                snapshot,
            )
        references.append(
            CoverageSnapshotReference(
                snapshot_id=persistence.snapshot_id,
                snapshot=snapshot,
            )
        )

    five_minute, ten_minute, fifteen_minute = references
    derivations = build_derivations_from_coverage(
        five_minute.snapshot,
        ten_minute.snapshot,
    )
    async with session_maker() as session:
        await persist_ten_minute_derivations(session, derivations)
    synchronized = build_synchronized_coverage_snapshot(
        as_of=as_of,
        five_minute=five_minute,
        ten_minute=ten_minute,
        fifteen_minute=fifteen_minute,
        derivations=derivations,
    )
    async with session_maker() as session:
        persisted = await persist_synchronized_coverage_snapshot(
            session,
            synchronized,
        )
    return HistoricalSynchronizationResult(
        snapshot=synchronized,
        persistence=persisted,
    )
