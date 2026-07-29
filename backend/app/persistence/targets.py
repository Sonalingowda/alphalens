"""Immutable persistence for the approved forward log-return target."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.models import Candle
from app.persistence.models import (
    CandleRecord,
    ForwardLogReturnTargetRecord,
    ForwardLogReturnTargetRunRecord,
    FeaturePipelineRunRecord,
)
from app.persistence.provenance import (
    candle_data_hash,
    get_active_feature_run,
    get_active_ingestion_batch,
)
from app.targets.forward_log_return import (
    TARGET_HORIZON,
    TARGET_VALUE_QUANTUM,
    ForwardLogReturnLabel,
    TargetGenerationError,
    generate_forward_log_return_targets,
)


_INSERT_CHUNK_SIZE = 500


@dataclass(frozen=True, slots=True)
class TargetPersistenceResult:
    generation_run_id: UUID
    target_name: str
    target_version: str
    target_definition_hash: str
    horizon: int
    source_ingestion_batch_id: UUID
    source_feature_run_id: UUID
    feature_pipeline_version: str
    dataset_hash: str
    label_data_hash: str
    source_candle_count: int
    generated_label_count: int
    inserted_label_count: int
    stored_label_count: int
    excluded_observation_count: int
    exclusion_details: tuple[dict[str, object], ...]
    first_eligible_timestamp: datetime
    last_eligible_timestamp: datetime
    minimum_value: Decimal
    maximum_value: Decimal
    mean_value: Decimal
    positive_label_count: int
    negative_label_count: int
    zero_label_count: int
    point_in_time_validated: bool


async def generate_and_persist_forward_log_returns(
    session: AsyncSession,
) -> TargetPersistenceResult:
    async with session.begin():
        records = tuple(
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
        if not records:
            raise TargetGenerationError(
                "No persisted BTC/USD daily candles are available."
            )
        if any(not record.is_complete for record in records):
            raise TargetGenerationError(
                "Target generation requires completed candles only."
            )

        try:
            source_batch = await get_active_ingestion_batch(session)
            feature_run = await get_active_feature_run(
                session,
                source_batch.id,
            )
        except ValueError as exc:
            raise TargetGenerationError(str(exc)) from exc

        if (
            source_batch.candle_count != len(records)
            or source_batch.available_range_start
            != records[0].candle_timestamp
            or source_batch.available_range_end
            != records[-1].candle_timestamp
        ):
            raise TargetGenerationError(
                "The active ingestion batch does not describe the complete "
                "persisted candle dataset."
            )
        _validate_provenance(records, source_batch.id, feature_run)
        dataset_hash = candle_data_hash(records)
        if dataset_hash != feature_run.source_data_hash:
            raise TargetGenerationError(
                "The active feature run and current candle dataset hashes "
                "do not match."
            )

        result = generate_forward_log_return_targets(
            tuple(_to_candle(record) for record in records)
        )
        if not result.labels:
            raise TargetGenerationError(
                "The source dataset has no complete forward horizons."
            )

        label_data_hash = _label_data_hash(result.labels)
        statistics = _label_statistics(result.labels)
        exclusion_details: tuple[dict[str, object], ...] = (
            {
                "code": "insufficient_forward_horizon",
                "count": len(result.exclusions),
                "prediction_timestamps": [
                    exclusion.prediction_timestamp.isoformat()
                    for exclusion in result.exclusions
                ],
            },
        )
        _verify_existing_immutable_values(
            await _existing_values(
                session,
                result.target_name,
                result.target_version,
            ),
            result.labels,
            feature_run,
            dataset_hash,
        )

        generation_run_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        run_record = ForwardLogReturnTargetRunRecord(
            id=generation_run_id,
            target_name=result.target_name,
            target_version=result.target_version,
            target_definition_hash=result.target_definition_hash,
            horizon=result.horizon,
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe="1d",
            source_ingestion_batch_id=source_batch.id,
            source_feature_run_id=feature_run.id,
            feature_pipeline_version=feature_run.pipeline_version,
            dataset_hash=dataset_hash,
            label_data_hash=label_data_hash,
            source_candle_count=len(records),
            source_range_start=records[0].candle_timestamp,
            source_range_end=records[-1].candle_timestamp,
            generated_label_count=len(result.labels),
            persisted_label_count=0,
            excluded_observation_count=len(result.exclusions),
            exclusion_details=list(exclusion_details),
            first_eligible_timestamp=result.labels[0].prediction_timestamp,
            last_eligible_timestamp=result.labels[-1].prediction_timestamp,
            label_value_min=statistics.minimum,
            label_value_max=statistics.maximum,
            label_value_mean=statistics.mean,
            positive_label_count=statistics.positive_count,
            negative_label_count=statistics.negative_count,
            zero_label_count=statistics.zero_count,
            point_in_time_validated=result.point_in_time_validated,
            is_active=False,
            generated_at=generated_at,
        )
        session.add(run_record)
        await session.flush()

        inserted_ids: list[int] = []
        values = [
            {
                "asset_identifier": "BTC",
                "quote_currency": "USD",
                "timeframe": "1d",
                "target_name": result.target_name,
                "target_version": result.target_version,
                "prediction_timestamp": label.prediction_timestamp,
                "label_available_at": label.label_available_at,
                "horizon": result.horizon,
                "target_value": label.value,
                "source_ingestion_batch_id": source_batch.id,
                "source_feature_run_id": feature_run.id,
                "feature_pipeline_version": feature_run.pipeline_version,
                "dataset_hash": dataset_hash,
                "generation_run_id": generation_run_id,
                "generated_at": generated_at,
            }
            for label in result.labels
        ]
        for offset in range(0, len(values), _INSERT_CHUNK_SIZE):
            statement = (
                insert(ForwardLogReturnTargetRecord)
                .values(values[offset : offset + _INSERT_CHUNK_SIZE])
                .on_conflict_do_nothing(
                    constraint="uq_forward_log_return_targets_identity"
                )
                .returning(ForwardLogReturnTargetRecord.id)
            )
            inserted_ids.extend((await session.scalars(statement)).all())

        run_record.persisted_label_count = len(inserted_ids)
        if inserted_ids:
            await session.execute(
                update(ForwardLogReturnTargetRunRecord)
                .where(
                    ForwardLogReturnTargetRunRecord.asset_identifier == "BTC",
                    ForwardLogReturnTargetRunRecord.quote_currency == "USD",
                    ForwardLogReturnTargetRunRecord.timeframe == "1d",
                    ForwardLogReturnTargetRunRecord.target_name
                    == result.target_name,
                    ForwardLogReturnTargetRunRecord.is_active.is_(True),
                    ForwardLogReturnTargetRunRecord.id != generation_run_id,
                )
                .values(is_active=False, superseded_at=generated_at)
            )
            run_record.is_active = True

        stored_label_count = int(
            await session.scalar(
                select(func.count(ForwardLogReturnTargetRecord.id)).where(
                    ForwardLogReturnTargetRecord.asset_identifier == "BTC",
                    ForwardLogReturnTargetRecord.quote_currency == "USD",
                    ForwardLogReturnTargetRecord.timeframe == "1d",
                    ForwardLogReturnTargetRecord.target_name
                    == result.target_name,
                    ForwardLogReturnTargetRecord.target_version
                    == result.target_version,
                )
            )
            or 0
        )

    return TargetPersistenceResult(
        generation_run_id=generation_run_id,
        target_name=result.target_name,
        target_version=result.target_version,
        target_definition_hash=result.target_definition_hash,
        horizon=result.horizon,
        source_ingestion_batch_id=source_batch.id,
        source_feature_run_id=feature_run.id,
        feature_pipeline_version=feature_run.pipeline_version,
        dataset_hash=dataset_hash,
        label_data_hash=label_data_hash,
        source_candle_count=len(records),
        generated_label_count=len(result.labels),
        inserted_label_count=len(inserted_ids),
        stored_label_count=stored_label_count,
        excluded_observation_count=len(result.exclusions),
        exclusion_details=exclusion_details,
        first_eligible_timestamp=result.labels[0].prediction_timestamp,
        last_eligible_timestamp=result.labels[-1].prediction_timestamp,
        minimum_value=statistics.minimum,
        maximum_value=statistics.maximum,
        mean_value=statistics.mean,
        positive_label_count=statistics.positive_count,
        negative_label_count=statistics.negative_count,
        zero_label_count=statistics.zero_count,
        point_in_time_validated=result.point_in_time_validated,
    )


@dataclass(frozen=True, slots=True)
class _LabelStatistics:
    minimum: Decimal
    maximum: Decimal
    mean: Decimal
    positive_count: int
    negative_count: int
    zero_count: int


def _validate_provenance(
    records: tuple[CandleRecord, ...],
    source_batch_id: UUID,
    feature_run: FeaturePipelineRunRecord,
) -> None:
    if (
        feature_run.source_ingestion_batch_id != source_batch_id
        or feature_run.source_candle_count != len(records)
        or feature_run.source_range_start != records[0].candle_timestamp
        or feature_run.source_range_end != records[-1].candle_timestamp
    ):
        raise TargetGenerationError(
            "The active feature run does not describe the complete active "
            "candle dataset."
        )


def _to_candle(record: CandleRecord) -> Candle:
    return Candle(
        timestamp=record.candle_timestamp,
        open=record.open_price,
        high=record.high_price,
        low=record.low_price,
        close=record.close_price,
        volume=record.volume,
    )


async def _existing_values(
    session: AsyncSession,
    target_name: str,
    target_version: str,
) -> dict[datetime, ForwardLogReturnTargetRecord]:
    records = (
        await session.scalars(
            select(ForwardLogReturnTargetRecord).where(
                ForwardLogReturnTargetRecord.asset_identifier == "BTC",
                ForwardLogReturnTargetRecord.quote_currency == "USD",
                ForwardLogReturnTargetRecord.timeframe == "1d",
                ForwardLogReturnTargetRecord.target_name == target_name,
                ForwardLogReturnTargetRecord.target_version == target_version,
            )
        )
    ).all()
    return {record.prediction_timestamp: record for record in records}


def _verify_existing_immutable_values(
    existing: dict[datetime, ForwardLogReturnTargetRecord],
    labels: tuple[ForwardLogReturnLabel, ...],
    feature_run: FeaturePipelineRunRecord,
    dataset_hash: str,
) -> None:
    for label in labels:
        stored = existing.get(label.prediction_timestamp)
        if stored is None:
            continue
        if (
            stored.target_value != label.value
            or stored.label_available_at != label.label_available_at
            or stored.horizon != TARGET_HORIZON
            or stored.source_feature_run_id != feature_run.id
            or stored.feature_pipeline_version != feature_run.pipeline_version
            or stored.dataset_hash != dataset_hash
        ):
            raise TargetGenerationError(
                "A recomputed target differs from its immutable stored "
                "value or provenance; a new target version is required."
            )


def _label_statistics(
    labels: tuple[ForwardLogReturnLabel, ...],
) -> _LabelStatistics:
    values = tuple(label.value for label in labels)
    with localcontext() as context:
        context.prec = 50
        mean = (sum(values, Decimal(0)) / Decimal(len(values))).quantize(
            TARGET_VALUE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
    return _LabelStatistics(
        minimum=min(values),
        maximum=max(values),
        mean=mean,
        positive_count=sum(value > 0 for value in values),
        negative_count=sum(value < 0 for value in values),
        zero_count=sum(value == 0 for value in values),
    )


def _label_data_hash(
    labels: tuple[ForwardLogReturnLabel, ...],
) -> str:
    digest = sha256()
    for label in labels:
        fields = (
            label.prediction_timestamp.astimezone(timezone.utc).isoformat(),
            label.label_available_at.astimezone(timezone.utc).isoformat(),
            format(label.value, "f"),
        )
        digest.update(("|".join(fields) + "\n").encode())
    return digest.hexdigest()
