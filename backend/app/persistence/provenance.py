"""Canonical research-dataset provenance resolution."""

from collections.abc import Sequence
from datetime import timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    CandleRecord,
    FeaturePipelineRunRecord,
    IngestionBatchRecord,
)


async def get_active_ingestion_batch(
    session: AsyncSession,
) -> IngestionBatchRecord:
    batch = (
        await session.scalars(
            select(IngestionBatchRecord).where(
                IngestionBatchRecord.asset_identifier == "BTC",
                IngestionBatchRecord.quote_currency == "USD",
                IngestionBatchRecord.timeframe == "1d",
                IngestionBatchRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    if batch is None:
        raise ValueError(
            "No active BTC/USD daily ingestion batch is available."
        )
    if not batch.validation_passed:
        raise ValueError("The active ingestion batch failed validation.")
    return batch


async def get_active_feature_run(
    session: AsyncSession,
    source_batch_id: UUID,
) -> FeaturePipelineRunRecord:
    run = (
        await session.scalars(
            select(FeaturePipelineRunRecord).where(
                FeaturePipelineRunRecord.asset_identifier == "BTC",
                FeaturePipelineRunRecord.quote_currency == "USD",
                FeaturePipelineRunRecord.timeframe == "1d",
                FeaturePipelineRunRecord.source_ingestion_batch_id
                == source_batch_id,
                FeaturePipelineRunRecord.is_active.is_(True),
                FeaturePipelineRunRecord.point_in_time_validated.is_(True),
                FeaturePipelineRunRecord.persisted_value_count > 0,
            )
        )
    ).one_or_none()
    if run is None:
        raise ValueError(
            "No active point-in-time-valid feature run is available for "
            "the active ingestion batch."
        )
    return run


def candle_data_hash(records: Sequence[CandleRecord]) -> str:
    """Hash ordered source candles exactly as feature provenance does."""
    digest = sha256()
    for record in records:
        fields = (
            record.candle_timestamp.astimezone(timezone.utc).isoformat(),
            format(record.open_price, "f"),
            format(record.high_price, "f"),
            format(record.low_price, "f"),
            format(record.close_price, "f"),
            format(record.volume, "f"),
        )
        digest.update(("|".join(fields) + "\n").encode())
    return digest.hexdigest()
