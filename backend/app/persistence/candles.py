"""Validated candle batch persistence and read summaries."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.conflicts import (
    CanonicalSourceObservation,
    candle_sequence_hash,
    compare_source_batch,
)
from app.market_data.history import HistoricalSample
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import timeframe_duration
from app.persistence.conflicts import source_conflict_record
from app.persistence.models import CandleRecord, IngestionBatchRecord


@dataclass(frozen=True, slots=True)
class CandlePersistenceResult:
    ingestion_batch_id: UUID
    validation_passed: bool
    fetched_candle_count: int
    persisted_candle_count: int
    stored_candle_count: int
    ingestion_batch_count: int
    reused_candle_count: int = 0
    conflict_count: int = 0
    source_data_hash: str | None = None


@dataclass(frozen=True, slots=True)
class StoredCandleSummary:
    row_count: int
    date_range_start: datetime | None
    date_range_end: datetime | None
    latest_ingestion_batch_id: UUID | None
    latest_validation_passed: bool | None
    latest_validation_issues: tuple[dict[str, Any], ...]
    ingestion_batch_count: int


async def persist_historical_sample(
    session: AsyncSession,
    sample: HistoricalSample,
    acquisition_attempt_id: UUID | None = None,
) -> CandlePersistenceResult:
    derivation_metadata = (
        sample.source_timeframe,
        sample.derivation_method,
        sample.source_ingestion_batch_id,
    )
    if any(value is not None for value in derivation_metadata) and not all(
        value is not None for value in derivation_metadata
    ):
        raise ValueError("Derived candle provenance must be complete.")

    batch_id = uuid4()
    validation_issues = [
        {
            "code": issue.code,
            "message": issue.message,
            "timestamp": issue.timestamp.isoformat()
            if issue.timestamp is not None
            else None,
        }
        for issue in sample.validation_report.issues
    ]
    persisted_count = 0
    reused_count = 0
    conflict_count = 0
    source_data_hash = (
        candle_sequence_hash(sample.candles)
        if sample.validation_report.passed
        else None
    )
    available_timestamps = tuple(
        candle.timestamp
        for candle in sample.candles
        if candle.timestamp is not None
    )
    progress_events = [
        {
            "page_number": progress.page_number,
            "requested_since": progress.requested_since.isoformat(),
            "provider_row_count": progress.provider_row_count,
            "accepted_completed_count": progress.accepted_completed_count,
            "new_unique_completed_count": (
                progress.new_unique_completed_count
            ),
            "excluded_incomplete_count": (
                progress.excluded_incomplete_count
            ),
            "excluded_pagination_overlap_count": (
                progress.excluded_pagination_overlap_count
            ),
            "cumulative_completed_count": (
                progress.cumulative_completed_count
            ),
            "next_since": progress.next_since.isoformat(),
        }
        for progress in sample.progress
    ]

    async with session.begin():
        session.add(
            IngestionBatchRecord(
                id=batch_id,
                provider=sample.provider,
                asset_identifier=sample.asset_identifier,
                quote_currency=sample.quote_currency,
                timeframe=sample.timeframe.value,
                requested_start=sample.requested_start,
                requested_end_exclusive=sample.requested_end_exclusive,
                retrieved_at=sample.retrieved_at,
                validation_passed=sample.validation_report.passed,
                validation_issues=validation_issues,
                candle_count=len(sample.candles),
                persisted_candle_count=0,
                reused_candle_count=0,
                conflict_count=0,
                source_data_hash=source_data_hash,
                provider_page_count=sample.pages_fetched,
                excluded_incomplete_candle_count=(
                    sample.excluded_incomplete_candle_count
                ),
                excluded_pagination_overlap_count=(
                    sample.excluded_pagination_overlap_count
                ),
                provider_page_limit=sample.provider_page_limit,
                provider_limit_reached=sample.provider_limit_reached,
                pagination_exhausted=sample.pagination_exhausted,
                available_range_start=(
                    available_timestamps[0]
                    if available_timestamps
                    else None
                ),
                available_range_end=(
                    available_timestamps[-1]
                    if available_timestamps
                    else None
                ),
                insertion_mode="insert_only",
                progress_events=progress_events,
                source_timeframe=(
                    sample.source_timeframe.value
                    if sample.source_timeframe is not None
                    else None
                ),
                derivation_method=sample.derivation_method,
                source_ingestion_batch_id=(
                    sample.source_ingestion_batch_id
                ),
                acquisition_attempt_id=acquisition_attempt_id,
            )
        )
        await session.flush()

        if sample.validation_report.passed:
            await session.execute(
                select(func.pg_advisory_xact_lock(1_093_675_347))
            )
            canonical_by_timestamp = await _canonical_by_timestamp(
                session,
                sample,
            )
            if sample.timeframe in {
                CandleTimeframe.MINUTE_5,
                CandleTimeframe.MINUTE_15,
            }:
                comparison = compare_source_batch(
                    asset_identifier=sample.asset_identifier,
                    quote_currency=sample.quote_currency,
                    timeframe=sample.timeframe,
                    canonical_by_timestamp={
                        timestamp: CanonicalSourceObservation(
                            candle_id=record.id,
                            ingestion_batch_id=record.ingestion_batch_id,
                            provider=record.provider,
                            candle=_record_candle(record),
                        )
                        for timestamp, record in canonical_by_timestamp.items()
                    },
                    incoming_candles=sample.candles,
                    incoming_attempt_id=acquisition_attempt_id,
                    incoming_ingestion_batch_id=batch_id,
                    incoming_provider=sample.provider,
                    retrieved_at=sample.retrieved_at,
                    incoming_batch_source_hash=_required_hash(
                        source_data_hash
                    ),
                    interval_duration_seconds=int(
                        timeframe_duration(sample.timeframe).total_seconds()
                    ),
                )
                reused_count = comparison.reused_count
                conflict_evidence = comparison.conflicts
            else:
                conflict_evidence = ()
                reused_count = len(canonical_by_timestamp)
            conflict_count = len(conflict_evidence)
            if conflict_evidence:
                session.add_all(
                    [
                        source_conflict_record(evidence)
                        for evidence in conflict_evidence
                    ]
                )

            values = [
                _candle_values(candle, sample, batch_id)
                for candle in sample.candles
            ]
            if values and not conflict_evidence:
                statement = insert(CandleRecord).values(values)
                statement = statement.on_conflict_do_nothing(
                    constraint=(
                        "uq_market_candles_asset_quote_timeframe_timestamp"
                    )
                ).returning(CandleRecord.id)
                inserted_ids = tuple(
                    (await session.scalars(statement)).all()
                )
                persisted_count = len(inserted_ids)
                reused_count = len(sample.candles) - persisted_count

            batch = await session.get(IngestionBatchRecord, batch_id)
            if batch is None:
                raise RuntimeError("Ingestion batch disappeared during persistence.")
            batch.persisted_candle_count = persisted_count
            batch.reused_candle_count = reused_count
            batch.conflict_count = conflict_count

        stored_count = await _count_sample_candles(session, sample)
        batch_count = await session.scalar(
            select(func.count(IngestionBatchRecord.id)).where(
                IngestionBatchRecord.asset_identifier
                == sample.asset_identifier,
                IngestionBatchRecord.quote_currency
                == sample.quote_currency,
                IngestionBatchRecord.timeframe == sample.timeframe.value,
            )
        )

    return CandlePersistenceResult(
        ingestion_batch_id=batch_id,
        validation_passed=sample.validation_report.passed,
        fetched_candle_count=len(sample.candles),
        persisted_candle_count=persisted_count,
        stored_candle_count=stored_count,
        ingestion_batch_count=int(batch_count or 0),
        reused_candle_count=reused_count,
        conflict_count=conflict_count,
        source_data_hash=source_data_hash,
    )


async def get_stored_candle_summary(
    session: AsyncSession,
    asset_identifier: str = "BTC",
    quote_currency: str = "USD",
    timeframe: str = "1d",
) -> StoredCandleSummary:
    market_filters = (
        CandleRecord.asset_identifier == asset_identifier,
        CandleRecord.quote_currency == quote_currency,
        CandleRecord.timeframe == timeframe,
    )
    row_count, date_range_start, date_range_end = (
        await session.execute(
            select(
                func.count(CandleRecord.id),
                func.min(CandleRecord.candle_timestamp),
                func.max(CandleRecord.candle_timestamp),
            ).where(*market_filters)
        )
    ).one()
    latest_batch = (
        await session.execute(
            select(IngestionBatchRecord)
            .where(
                IngestionBatchRecord.asset_identifier == asset_identifier,
                IngestionBatchRecord.quote_currency == quote_currency,
                IngestionBatchRecord.timeframe == timeframe,
            )
            .order_by(
                IngestionBatchRecord.retrieved_at.desc(),
                IngestionBatchRecord.created_at.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    batch_count = await session.scalar(
        select(func.count(IngestionBatchRecord.id)).where(
            IngestionBatchRecord.asset_identifier == asset_identifier,
            IngestionBatchRecord.quote_currency == quote_currency,
            IngestionBatchRecord.timeframe == timeframe,
        )
    )

    return StoredCandleSummary(
        row_count=row_count,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        latest_ingestion_batch_id=latest_batch.id if latest_batch else None,
        latest_validation_passed=(
            latest_batch.validation_passed if latest_batch else None
        ),
        latest_validation_issues=(
            tuple(latest_batch.validation_issues) if latest_batch else ()
        ),
        ingestion_batch_count=int(batch_count or 0),
    )


async def _count_sample_candles(
    session: AsyncSession,
    sample: HistoricalSample,
) -> int:
    count = await session.scalar(
        select(func.count(CandleRecord.id)).where(
            CandleRecord.asset_identifier == sample.asset_identifier,
            CandleRecord.quote_currency == sample.quote_currency,
            CandleRecord.timeframe == sample.timeframe.value,
        )
    )
    return int(count or 0)


def _candle_values(
    candle: Candle,
    sample: HistoricalSample,
    batch_id: UUID,
) -> dict[str, object]:
    return {
        "asset_identifier": sample.asset_identifier,
        "quote_currency": sample.quote_currency,
        "timeframe": sample.timeframe.value,
        "candle_timestamp": _required_datetime(candle.timestamp),
        "open_price": _required_decimal(candle.open),
        "high_price": _required_decimal(candle.high),
        "low_price": _required_decimal(candle.low),
        "close_price": _required_decimal(candle.close),
        "volume": _required_decimal(candle.volume),
        "provider": sample.provider,
        "is_complete": True,
        "ingestion_batch_id": batch_id,
        "ingested_at": sample.retrieved_at,
    }


async def _canonical_by_timestamp(
    session: AsyncSession,
    sample: HistoricalSample,
) -> dict[datetime, CandleRecord]:
    timestamps = tuple(
        _required_datetime(candle.timestamp) for candle in sample.candles
    )
    records = tuple(
        (
            await session.scalars(
                select(CandleRecord).where(
                    CandleRecord.asset_identifier
                    == sample.asset_identifier,
                    CandleRecord.quote_currency == sample.quote_currency,
                    CandleRecord.timeframe == sample.timeframe.value,
                    CandleRecord.candle_timestamp.in_(timestamps),
                )
            )
        ).all()
    )
    return {record.candle_timestamp: record for record in records}


def _record_candle(record: CandleRecord) -> Candle:
    return Candle(
        timestamp=record.candle_timestamp,
        open=record.open_price,
        high=record.high_price,
        low=record.low_price,
        close=record.close_price,
        volume=record.volume,
    )


def _required_hash(value: str | None) -> str:
    if value is None:
        raise ValueError("Validated candle batch source hash is missing.")
    return value


def _required_datetime(value: datetime | None) -> datetime:
    if value is None:
        raise ValueError("Validated candle timestamp is unexpectedly missing.")
    return value


def _required_decimal(value: Decimal | None) -> Decimal:
    if value is None:
        raise ValueError("Validated candle value is unexpectedly missing.")
    return value
