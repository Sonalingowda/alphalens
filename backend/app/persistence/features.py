"""Feature pipeline execution, immutable persistence, and read summaries."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.contracts import FeatureComputationError
from app.features.pipeline import PIPELINE_VERSION, run_feature_pipeline
from app.market_data.models import Candle
from app.persistence.models import (
    CandleRecord,
    EngineeredFeatureRecord,
    FeaturePipelineRunRecord,
)
from app.persistence.provenance import (
    candle_data_hash,
    get_active_ingestion_batch,
)


_INSERT_CHUNK_SIZE = 500


@dataclass(frozen=True, slots=True)
class FeaturePersistenceResult:
    computation_run_id: UUID
    pipeline_version: str
    source_ingestion_batch_id: UUID
    source_candle_count: int
    source_range_start: datetime
    source_range_end: datetime
    source_data_hash: str
    point_in_time_validated: bool
    computed_value_count: int
    inserted_value_count: int
    stored_value_count: int


@dataclass(frozen=True, slots=True)
class FeatureSeriesSummary:
    feature_name: str
    row_count: int
    earliest_timestamp: datetime
    latest_timestamp: datetime
    latest_value: Decimal


@dataclass(frozen=True, slots=True)
class StoredFeatureSummary:
    row_count: int
    computation_run_count: int
    pipeline_versions: tuple[str, ...]
    active_computation_run_id: UUID
    active_pipeline_version: str
    feature_series: tuple[FeatureSeriesSummary, ...]


async def compute_and_persist_features(
    session: AsyncSession,
) -> FeaturePersistenceResult:
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
            raise FeatureComputationError(
                "No persisted BTC/USD daily candles are available."
            )
        if any(not record.is_complete for record in records):
            raise FeatureComputationError(
                "Feature computation requires completed candles only."
            )

        try:
            source_batch = await get_active_ingestion_batch(session)
        except ValueError as exc:
            raise FeatureComputationError(str(exc)) from exc
        source_batch_id = source_batch.id
        if (
            source_batch.candle_count != len(records)
            or source_batch.available_range_start
            != records[0].candle_timestamp
            or source_batch.available_range_end
            != records[-1].candle_timestamp
        ):
            raise FeatureComputationError(
                "The active ingestion batch does not describe the complete "
                "persisted candle dataset."
            )

        candles = tuple(_to_candle(record) for record in records)
        pipeline_result = run_feature_pipeline(candles)
        computed_at = datetime.now(timezone.utc)
        computation_run_id = uuid4()
        source_data_hash = candle_data_hash(records)
        existing_values = {
            (timestamp, feature_name): feature_value
            for timestamp, feature_name, feature_value in (
                await session.execute(
                    select(
                        EngineeredFeatureRecord.candle_timestamp,
                        EngineeredFeatureRecord.feature_name,
                        EngineeredFeatureRecord.feature_value,
                    ).where(
                        EngineeredFeatureRecord.asset_identifier == "BTC",
                        EngineeredFeatureRecord.quote_currency == "USD",
                        EngineeredFeatureRecord.timeframe == "1d",
                        EngineeredFeatureRecord.pipeline_version
                        == pipeline_result.pipeline_version,
                    )
                )
            ).all()
        }
        for value in pipeline_result.values:
            existing = existing_values.get(
                (value.timestamp, value.feature_name)
            )
            if existing is not None and existing != value.value:
                raise FeatureComputationError(
                    "A recomputed feature differs from its immutable stored "
                    "value; a new pipeline version is required."
                )

        run_record = FeaturePipelineRunRecord(
            id=computation_run_id,
            pipeline_version=pipeline_result.pipeline_version,
            asset_identifier="BTC",
            quote_currency="USD",
            timeframe="1d",
            source_ingestion_batch_id=source_batch_id,
            source_candle_count=len(records),
            source_range_start=records[0].candle_timestamp,
            source_range_end=records[-1].candle_timestamp,
            source_data_hash=source_data_hash,
            point_in_time_validated=pipeline_result.point_in_time_validated,
            feature_value_count=len(pipeline_result.values),
            persisted_value_count=0,
            is_active=False,
            computed_at=computed_at,
        )
        session.add(run_record)
        await session.flush()

        inserted_ids: list[int] = []
        if pipeline_result.values:
            values = [
                {
                    "asset_identifier": "BTC",
                    "quote_currency": "USD",
                    "timeframe": "1d",
                    "candle_timestamp": value.timestamp,
                    "feature_name": value.feature_name,
                    "feature_value": value.value,
                    "pipeline_version": pipeline_result.pipeline_version,
                    "source_ingestion_batch_id": source_batch_id,
                    "computation_run_id": computation_run_id,
                    "computed_at": computed_at,
                }
                for value in pipeline_result.values
            ]
            for offset in range(0, len(values), _INSERT_CHUNK_SIZE):
                statement = (
                    insert(EngineeredFeatureRecord)
                    .values(values[offset : offset + _INSERT_CHUNK_SIZE])
                    .on_conflict_do_nothing(
                        constraint="uq_engineered_features_identity"
                    )
                    .returning(EngineeredFeatureRecord.id)
                )
                inserted_ids.extend(
                    (await session.scalars(statement)).all()
                )
        run_record.persisted_value_count = len(inserted_ids)
        if inserted_ids:
            await session.execute(
                update(FeaturePipelineRunRecord)
                .where(
                    FeaturePipelineRunRecord.asset_identifier == "BTC",
                    FeaturePipelineRunRecord.quote_currency == "USD",
                    FeaturePipelineRunRecord.timeframe == "1d",
                    FeaturePipelineRunRecord.is_active.is_(True),
                    FeaturePipelineRunRecord.id != computation_run_id,
                )
                .values(is_active=False, superseded_at=computed_at)
            )
            run_record.is_active = True

        stored_count = await session.scalar(
            select(func.count(EngineeredFeatureRecord.id)).where(
                EngineeredFeatureRecord.asset_identifier == "BTC",
                EngineeredFeatureRecord.quote_currency == "USD",
                EngineeredFeatureRecord.timeframe == "1d",
                EngineeredFeatureRecord.pipeline_version == PIPELINE_VERSION,
            )
        )

    return FeaturePersistenceResult(
        computation_run_id=computation_run_id,
        pipeline_version=pipeline_result.pipeline_version,
        source_ingestion_batch_id=source_batch_id,
        source_candle_count=len(records),
        source_range_start=records[0].candle_timestamp,
        source_range_end=records[-1].candle_timestamp,
        source_data_hash=source_data_hash,
        point_in_time_validated=pipeline_result.point_in_time_validated,
        computed_value_count=len(pipeline_result.values),
        inserted_value_count=len(inserted_ids),
        stored_value_count=int(stored_count or 0),
    )


async def get_stored_feature_summary(
    session: AsyncSession,
) -> StoredFeatureSummary:
    active_run = (
        await session.scalars(
            select(FeaturePipelineRunRecord).where(
                FeaturePipelineRunRecord.asset_identifier == "BTC",
                FeaturePipelineRunRecord.quote_currency == "USD",
                FeaturePipelineRunRecord.timeframe == "1d",
                FeaturePipelineRunRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    if active_run is None:
        raise RuntimeError("No active feature pipeline run is available.")
    market_filters = (
        EngineeredFeatureRecord.asset_identifier == "BTC",
        EngineeredFeatureRecord.quote_currency == "USD",
        EngineeredFeatureRecord.timeframe == "1d",
        EngineeredFeatureRecord.computation_run_id == active_run.id,
    )
    row_count = int(
        await session.scalar(
            select(func.count(EngineeredFeatureRecord.id)).where(*market_filters)
        )
        or 0
    )
    run_count = int(
        await session.scalar(
            select(func.count(FeaturePipelineRunRecord.id)).where(
                FeaturePipelineRunRecord.asset_identifier == "BTC",
                FeaturePipelineRunRecord.quote_currency == "USD",
                FeaturePipelineRunRecord.timeframe == "1d",
            )
        )
        or 0
    )
    versions = tuple(
        (
            await session.scalars(
                select(EngineeredFeatureRecord.pipeline_version)
                .where(*market_filters)
                .distinct()
                .order_by(EngineeredFeatureRecord.pipeline_version)
            )
        ).all()
    )
    grouped_rows = (
        await session.execute(
            select(
                EngineeredFeatureRecord.feature_name,
                func.count(EngineeredFeatureRecord.id),
                func.min(EngineeredFeatureRecord.candle_timestamp),
                func.max(EngineeredFeatureRecord.candle_timestamp),
            )
            .where(*market_filters)
            .group_by(EngineeredFeatureRecord.feature_name)
            .order_by(EngineeredFeatureRecord.feature_name)
        )
    ).all()

    series: list[FeatureSeriesSummary] = []
    for feature_name, count, earliest, latest in grouped_rows:
        latest_value = await session.scalar(
            select(EngineeredFeatureRecord.feature_value).where(
                *market_filters,
                EngineeredFeatureRecord.feature_name == feature_name,
                EngineeredFeatureRecord.candle_timestamp == latest,
            )
        )
        if earliest is None or latest is None or latest_value is None:
            raise RuntimeError("Stored feature summary contains incomplete data.")
        series.append(
            FeatureSeriesSummary(
                feature_name=feature_name,
                row_count=count,
                earliest_timestamp=earliest,
                latest_timestamp=latest,
                latest_value=latest_value,
            )
        )

    return StoredFeatureSummary(
        row_count=row_count,
        computation_run_count=run_count,
        pipeline_versions=versions,
        active_computation_run_id=active_run.id,
        active_pipeline_version=active_run.pipeline_version,
        feature_series=tuple(series),
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
