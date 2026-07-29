"""Auditable persistence for chronological validation plans."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.pipeline import PIPELINE_VERSION
from app.persistence.models import (
    CandleRecord,
    EngineeredFeatureRecord,
    FeaturePipelineRunRecord,
    ValidationRunRecord,
)
from app.persistence.provenance import get_active_ingestion_batch
from app.validation.splits import (
    LookbackSeparation,
    TimestampRange,
    ValidationConfigurationError,
    WalkForwardConfig,
    WalkForwardPlan,
    generate_development_splits,
    verify_lookback_separation,
)


MAX_FEATURE_WINDOW = 50


@dataclass(frozen=True, slots=True)
class ValidationRunAudit:
    id: UUID
    strategy: str
    asset_identifier: str
    quote_currency: str
    timeframe: str
    source_ingestion_batch_id: UUID
    source_feature_run_id: UUID
    feature_pipeline_version: str
    source_data_hash: str
    source_observation_count: int
    minimum_train_size: int
    test_size: int
    step_size: int
    purge_gap_size: int
    final_holdout_size: int
    max_feature_window: int
    development_range_start: datetime
    development_range_end: datetime
    final_holdout_start: datetime
    final_holdout_end: datetime
    holdout_excluded: bool
    split_count: int
    split_boundaries: tuple[dict[str, Any], ...]
    lookback_separation: tuple[dict[str, Any], ...]
    configuration_hash: str
    split_hash: str
    is_active: bool
    superseded_at: datetime | None
    created_at: datetime


async def create_validation_run(
    session: AsyncSession,
    config: WalkForwardConfig,
) -> ValidationRunAudit:
    if config.purge_gap_size < MAX_FEATURE_WINDOW:
        raise ValidationConfigurationError(
            "Purge gap must be at least the existing maximum feature "
            f"window of {MAX_FEATURE_WINDOW} observations."
        )

    async with session.begin():
        candle_records = tuple(
            (
                await session.scalars(
                    select(CandleRecord)
                    .where(
                        CandleRecord.asset_identifier == "BTC",
                        CandleRecord.quote_currency == "USD",
                        CandleRecord.timeframe == "1d",
                    )
                    .order_by(CandleRecord.candle_timestamp)
                )
            ).all()
        )
        if not candle_records:
            raise ValueError("No persisted BTC/USD daily candles are available.")
        if any(not record.is_complete for record in candle_records):
            raise ValueError(
                "Chronological validation requires completed candles only."
            )

        source_batch = await get_active_ingestion_batch(session)
        source_batch_id = source_batch.id
        if (
            source_batch.candle_count != len(candle_records)
            or source_batch.available_range_start
            != candle_records[0].candle_timestamp
            or source_batch.available_range_end
            != candle_records[-1].candle_timestamp
        ):
            raise ValueError(
                "The active ingestion batch does not describe the complete "
                "persisted candle dataset."
            )

        feature_run = (
            await session.scalars(
                select(FeaturePipelineRunRecord)
                .where(
                    FeaturePipelineRunRecord.asset_identifier == "BTC",
                    FeaturePipelineRunRecord.quote_currency == "USD",
                    FeaturePipelineRunRecord.timeframe == "1d",
                    FeaturePipelineRunRecord.source_ingestion_batch_id
                    == source_batch_id,
                    FeaturePipelineRunRecord.pipeline_version
                    == PIPELINE_VERSION,
                    FeaturePipelineRunRecord.persisted_value_count > 0,
                    FeaturePipelineRunRecord.point_in_time_validated.is_(True),
                    FeaturePipelineRunRecord.is_active.is_(True),
                )
            )
        ).one_or_none()
        if feature_run is None:
            raise ValueError(
                "No validated feature computation run exists for the source."
            )
        feature_value_count = await session.scalar(
            select(func.count(EngineeredFeatureRecord.id)).where(
                EngineeredFeatureRecord.computation_run_id == feature_run.id,
            )
        )
        if feature_value_count != feature_run.persisted_value_count:
            raise ValueError(
                "The active feature run's stored values are incomplete."
            )

        timestamps = tuple(
            record.candle_timestamp for record in candle_records
        )
        plan = generate_development_splits(timestamps, config)
        separation = verify_lookback_separation(
            timestamps,
            plan,
            MAX_FEATURE_WINDOW,
        )
        boundaries = _split_boundaries(plan)
        separation_payload = _lookback_separation(separation)
        configuration_hash = _configuration_hash(config)
        split_hash = _split_hash(
            configuration_hash,
            source_batch_id,
            feature_run.source_data_hash,
            boundaries,
            plan,
        )
        run_id = uuid4()
        created_at = datetime.now(timezone.utc)
        await session.execute(
            update(ValidationRunRecord)
            .where(
                ValidationRunRecord.asset_identifier == "BTC",
                ValidationRunRecord.quote_currency == "USD",
                ValidationRunRecord.timeframe == "1d",
                ValidationRunRecord.is_active.is_(True),
            )
            .values(is_active=False, superseded_at=created_at)
        )
        record = ValidationRunRecord(
            id=run_id,
            strategy=plan.strategy,
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe="1d",
            source_ingestion_batch_id=source_batch_id,
            source_feature_run_id=feature_run.id,
            feature_pipeline_version=PIPELINE_VERSION,
            source_data_hash=feature_run.source_data_hash,
            source_observation_count=plan.source_observation_count,
            minimum_train_size=config.minimum_train_size,
            test_size=config.test_size,
            step_size=config.step_size,
            purge_gap_size=config.purge_gap_size,
            final_holdout_size=config.final_holdout_size,
            max_feature_window=MAX_FEATURE_WINDOW,
            development_range_start=plan.development_range.start,
            development_range_end=plan.development_range.end,
            final_holdout_start=plan.final_holdout_range.start,
            final_holdout_end=plan.final_holdout_range.end,
            holdout_excluded=True,
            split_count=len(plan.splits),
            split_boundaries=boundaries,
            lookback_separation=separation_payload,
            configuration_hash=configuration_hash,
            split_hash=split_hash,
            is_active=True,
            created_at=created_at,
        )
        session.add(record)
        await session.flush()
        await session.refresh(record)
        audit = _to_audit(record)

    return audit


async def get_validation_run(
    session: AsyncSession,
    run_id: UUID,
) -> ValidationRunAudit | None:
    record = await session.get(ValidationRunRecord, run_id)
    return _to_audit(record) if record is not None else None


def _configuration_hash(config: WalkForwardConfig) -> str:
    payload = {
        "strategy": "expanding_walk_forward",
        "minimum_train_size": config.minimum_train_size,
        "test_size": config.test_size,
        "step_size": config.step_size,
        "purge_gap_size": config.purge_gap_size,
        "final_holdout_size": config.final_holdout_size,
        "max_feature_window": MAX_FEATURE_WINDOW,
    }
    return _sha256_json(payload)


def _split_hash(
    configuration_hash: str,
    source_batch_id: UUID,
    source_data_hash: str,
    boundaries: list[dict[str, Any]],
    plan: WalkForwardPlan,
) -> str:
    return _sha256_json(
        {
            "configuration_hash": configuration_hash,
            "source_ingestion_batch_id": str(source_batch_id),
            "source_data_hash": source_data_hash,
            "development_range": _range_payload(plan.development_range),
            "final_holdout_range": _range_payload(
                plan.final_holdout_range
            ),
            "splits": boundaries,
        }
    )


def _split_boundaries(
    plan: WalkForwardPlan,
) -> list[dict[str, Any]]:
    return [
        {
            "sequence": split.sequence,
            "train": _range_payload(split.train),
            "purge_gap": _range_payload(split.purge_gap),
            "test": _range_payload(split.test),
        }
        for split in plan.splits
    ]


def _lookback_separation(
    results: tuple[LookbackSeparation, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "split_sequence": result.split_sequence,
            "train_end": result.train_end.isoformat(),
            "first_test_timestamp": result.first_test_timestamp.isoformat(),
            "earliest_first_test_feature_input": (
                result.earliest_first_test_feature_input.isoformat()
            ),
            "max_feature_window": result.max_feature_window,
            "passed": result.passed,
        }
        for result in results
    ]


def _range_payload(value: TimestampRange) -> dict[str, Any]:
    return {
        "start": value.start.isoformat(),
        "end": value.end.isoformat(),
        "observation_count": value.observation_count,
    }


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return sha256(encoded).hexdigest()


def _to_audit(record: ValidationRunRecord) -> ValidationRunAudit:
    return ValidationRunAudit(
        id=record.id,
        strategy=record.strategy,
        asset_identifier=record.asset_identifier,
        quote_currency=record.quote_currency,
        timeframe=record.timeframe,
        source_ingestion_batch_id=record.source_ingestion_batch_id,
        source_feature_run_id=record.source_feature_run_id,
        feature_pipeline_version=record.feature_pipeline_version,
        source_data_hash=record.source_data_hash,
        source_observation_count=record.source_observation_count,
        minimum_train_size=record.minimum_train_size,
        test_size=record.test_size,
        step_size=record.step_size,
        purge_gap_size=record.purge_gap_size,
        final_holdout_size=record.final_holdout_size,
        max_feature_window=record.max_feature_window,
        development_range_start=record.development_range_start,
        development_range_end=record.development_range_end,
        final_holdout_start=record.final_holdout_start,
        final_holdout_end=record.final_holdout_end,
        holdout_excluded=record.holdout_excluded,
        split_count=record.split_count,
        split_boundaries=tuple(record.split_boundaries),
        lookback_separation=tuple(record.lookback_separation),
        configuration_hash=record.configuration_hash,
        split_hash=record.split_hash,
        is_active=record.is_active,
        superseded_at=record.superseded_at,
        created_at=record.created_at,
    )
