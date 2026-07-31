"""Immutable persistence and verification for market-data source conflicts."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.conflicts import (
    SourceConflictEvidence,
    SourceConflictIntegrityError,
    verify_source_conflict,
)
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.models import SourceConflictRecord


def source_conflict_record(
    evidence: SourceConflictEvidence,
    conflict_id: UUID | None = None,
) -> SourceConflictRecord:
    verify_source_conflict(evidence)
    canonical = evidence.canonical_candle
    incoming = evidence.incoming_candle
    return SourceConflictRecord(
        id=conflict_id or uuid4(),
        schema_version=evidence.schema_version,
        hash_schema_version=evidence.hash_schema_version,
        conflict_type=evidence.conflict_type,
        asset_identifier=evidence.asset_identifier,
        quote_currency=evidence.quote_currency,
        timeframe=evidence.timeframe.value,
        candle_timestamp=evidence.candle_timestamp,
        canonical_candle_id=evidence.canonical_candle_id,
        canonical_ingestion_batch_id=evidence.canonical_ingestion_batch_id,
        canonical_provider=evidence.canonical_provider,
        canonical_open=canonical.open,
        canonical_high=canonical.high,
        canonical_low=canonical.low,
        canonical_close=canonical.close,
        canonical_volume=canonical.volume,
        incoming_attempt_id=evidence.incoming_attempt_id,
        incoming_ingestion_batch_id=evidence.incoming_ingestion_batch_id,
        incoming_provider=evidence.incoming_provider,
        incoming_open=incoming.open,
        incoming_high=incoming.high,
        incoming_low=incoming.low,
        incoming_close=incoming.close,
        incoming_volume=incoming.volume,
        retrieved_at=evidence.retrieved_at,
        available_at=evidence.available_at,
        canonical_candle_hash=evidence.canonical_candle_hash,
        incoming_candle_hash=evidence.incoming_candle_hash,
        incoming_batch_source_hash=evidence.incoming_batch_source_hash,
        conflict_hash=evidence.conflict_hash,
        immutable=True,
    )


def source_conflict_evidence(
    record: SourceConflictRecord,
) -> SourceConflictEvidence:
    evidence = SourceConflictEvidence(
        schema_version=record.schema_version,
        hash_schema_version=record.hash_schema_version,
        conflict_type=record.conflict_type,
        asset_identifier=record.asset_identifier,
        quote_currency=record.quote_currency,
        timeframe=CandleTimeframe(record.timeframe),
        candle_timestamp=_utc(record.candle_timestamp),
        canonical_candle_id=record.canonical_candle_id,
        canonical_ingestion_batch_id=record.canonical_ingestion_batch_id,
        canonical_provider=record.canonical_provider,
        canonical_candle=Candle(
            timestamp=_utc(record.candle_timestamp),
            open=record.canonical_open,
            high=record.canonical_high,
            low=record.canonical_low,
            close=record.canonical_close,
            volume=record.canonical_volume,
        ),
        incoming_attempt_id=record.incoming_attempt_id,
        incoming_ingestion_batch_id=record.incoming_ingestion_batch_id,
        incoming_provider=record.incoming_provider,
        incoming_candle=Candle(
            timestamp=_utc(record.candle_timestamp),
            open=record.incoming_open,
            high=record.incoming_high,
            low=record.incoming_low,
            close=record.incoming_close,
            volume=record.incoming_volume,
        ),
        retrieved_at=_utc(record.retrieved_at),
        available_at=_utc(record.available_at),
        canonical_candle_hash=record.canonical_candle_hash,
        incoming_candle_hash=record.incoming_candle_hash,
        incoming_batch_source_hash=record.incoming_batch_source_hash,
        conflict_hash=record.conflict_hash,
    )
    if not record.immutable:
        raise SourceConflictIntegrityError(
            "Stored source-conflict evidence is mutable."
        )
    verify_source_conflict(evidence)
    return evidence


async def unresolved_source_conflicts(
    session: AsyncSession,
    timeframe: CandleTimeframe,
    *,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    available_by: datetime | None = None,
) -> tuple[SourceConflictEvidence, ...]:
    statement = select(SourceConflictRecord).where(
        SourceConflictRecord.asset_identifier == "BTC",
        SourceConflictRecord.quote_currency == "USD",
        SourceConflictRecord.timeframe == timeframe.value,
    )
    if range_start is not None:
        statement = statement.where(
            SourceConflictRecord.candle_timestamp >= range_start
        )
    if range_end is not None:
        statement = statement.where(SourceConflictRecord.candle_timestamp <= range_end)
    if available_by is not None:
        statement = statement.where(SourceConflictRecord.available_at <= available_by)
    records = tuple(
        (
            await session.scalars(
                statement.order_by(
                    SourceConflictRecord.candle_timestamp,
                    SourceConflictRecord.created_at,
                    SourceConflictRecord.id,
                )
            )
        ).all()
    )
    return tuple(source_conflict_evidence(record) for record in records)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SourceConflictIntegrityError(
            "Stored conflict timestamps must be timezone-aware."
        )
    return value.astimezone(timezone.utc)
