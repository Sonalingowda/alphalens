"""Transactional persistence for approved intraday feature results."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.contracts import FeatureComputationError
from app.features.intraday_pipeline import (
    INTRADAY_PIPELINE_VERSION,
    IntradayFeaturePipelineResult,
    IntradaySourceSnapshot,
    PipelineFeatureValue,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
    source_batch_evidence,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import Candle, CandleTimeframe
from app.persistence.models import (
    CandleRecord,
    EngineeredFeatureRecord,
    FeaturePipelineRunRecord,
    FeaturePipelineRunSourceRecord,
    FeaturePipelineRunValueRecord,
    IngestionBatchRecord,
)
from app.persistence.conflicts import unresolved_source_conflicts


_INSERT_CHUNK_SIZE = 500


@dataclass(frozen=True, slots=True)
class IntradayFeaturePersistenceResult:
    feature_run_id: UUID
    pipeline_version: str
    timeframe: str
    source_data_hash: str
    source_provenance_hash: str
    registry_hash: str
    result_hash: str
    source_candle_count: int
    source_batch_count: int
    computed_value_count: int
    inserted_value_count: int
    reused_value_count: int
    membership_count: int
    is_active: bool


@dataclass(frozen=True, slots=True)
class StoredIntradayFeatureRunEvidence:
    feature_run_id: UUID
    pipeline_version: str
    source_data_hash: str
    source_provenance_hash: str
    registry_hash: str
    result_hash: str
    feature_value_count: int
    persisted_value_count: int
    source_membership_count: int
    value_membership_count: int
    canonical_value_count: int
    is_active: bool


async def load_intraday_source_snapshot(
    session: AsyncSession,
    timeframe: CandleTimeframe,
) -> IntradaySourceSnapshot:
    if timeframe not in {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    }:
        raise FeatureComputationError(
            "Intraday feature persistence supports only 5m, 10m, and 15m."
        )
    conflicts = await unresolved_source_conflicts(session, timeframe)
    if conflicts:
        raise FeatureComputationError(
            "Unresolved source conflicts block intraday feature evidence."
        )
    records = tuple(
        (
            await session.scalars(
                select(CandleRecord)
                .where(
                    CandleRecord.asset_identifier == "BTC",
                    CandleRecord.quote_currency == "USD",
                    CandleRecord.timeframe == timeframe.value,
                )
                .order_by(CandleRecord.candle_timestamp)
            )
        ).all()
    )
    if not records:
        raise FeatureComputationError(
            f"No persisted BTC/USD {timeframe.value} candles are available."
        )
    observations = tuple(
        SourceCandleObservation(
            candle=Candle(
                timestamp=record.candle_timestamp,
                open=record.open_price,
                high=record.high_price,
                low=record.low_price,
                close=record.close_price,
                volume=record.volume,
            ),
            ingestion_batch_id=record.ingestion_batch_id,
            is_complete=record.is_complete,
        )
        for record in records
    )
    return build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=observations,
    )


async def get_stored_intraday_feature_run_evidence(
    session: AsyncSession,
    feature_run_id: UUID,
) -> StoredIntradayFeatureRunEvidence:
    run = await session.get(FeaturePipelineRunRecord, feature_run_id)
    if run is None:
        raise FeatureComputationError("Persisted feature run is unavailable.")
    required_hashes = (
        run.source_provenance_hash,
        run.registry_hash,
        run.result_hash,
    )
    if any(value is None for value in required_hashes):
        raise FeatureComputationError(
            "Persisted intraday feature run has incomplete hash evidence."
        )
    source_membership_count = int(
        await session.scalar(
            select(func.count()).select_from(
                FeaturePipelineRunSourceRecord
            ).where(
                FeaturePipelineRunSourceRecord.feature_run_id
                == feature_run_id
            )
        )
        or 0
    )
    value_membership_count = int(
        await session.scalar(
            select(func.count()).select_from(
                FeaturePipelineRunValueRecord
            ).where(
                FeaturePipelineRunValueRecord.feature_run_id
                == feature_run_id
            )
        )
        or 0
    )
    canonical_value_count = int(
        await session.scalar(
            select(func.count()).select_from(
                EngineeredFeatureRecord
            ).where(
                EngineeredFeatureRecord.asset_identifier
                == run.asset_identifier,
                EngineeredFeatureRecord.quote_currency
                == run.quote_currency,
                EngineeredFeatureRecord.timeframe == run.timeframe,
                EngineeredFeatureRecord.pipeline_version
                == run.pipeline_version,
            )
        )
        or 0
    )
    return StoredIntradayFeatureRunEvidence(
        feature_run_id=run.id,
        pipeline_version=run.pipeline_version,
        source_data_hash=run.source_data_hash,
        source_provenance_hash=_required_hash(
            run.source_provenance_hash
        ),
        registry_hash=_required_hash(run.registry_hash),
        result_hash=_required_hash(run.result_hash),
        feature_value_count=run.feature_value_count,
        persisted_value_count=run.persisted_value_count,
        source_membership_count=source_membership_count,
        value_membership_count=value_membership_count,
        canonical_value_count=canonical_value_count,
        is_active=run.is_active,
    )


async def count_intraday_feature_values(
    session: AsyncSession,
    timeframe: CandleTimeframe,
) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(
                EngineeredFeatureRecord
            ).where(
                EngineeredFeatureRecord.asset_identifier == "BTC",
                EngineeredFeatureRecord.quote_currency == "USD",
                EngineeredFeatureRecord.timeframe == timeframe.value,
                EngineeredFeatureRecord.pipeline_version
                == INTRADAY_PIPELINE_VERSION,
            )
        )
        or 0
    )


async def count_active_intraday_feature_runs(
    session: AsyncSession,
    timeframe: CandleTimeframe,
) -> int:
    return int(
        await session.scalar(
            select(func.count()).select_from(
                FeaturePipelineRunRecord
            ).where(
                FeaturePipelineRunRecord.asset_identifier == "BTC",
                FeaturePipelineRunRecord.quote_currency == "USD",
                FeaturePipelineRunRecord.timeframe == timeframe.value,
                FeaturePipelineRunRecord.pipeline_version
                == INTRADAY_PIPELINE_VERSION,
                FeaturePipelineRunRecord.is_active.is_(True),
            )
        )
        or 0
    )


async def persist_intraday_feature_result(
    session: AsyncSession,
    snapshot: IntradaySourceSnapshot,
    result: IntradayFeaturePipelineResult,
) -> IntradayFeaturePersistenceResult:
    expected = run_intraday_feature_pipeline(snapshot)
    if result != expected:
        raise FeatureComputationError(
            "Feature result failed deterministic integrity verification."
        )
    if result.pipeline_version != INTRADAY_PIPELINE_VERSION:
        raise FeatureComputationError(
            "Feature result uses an unapproved pipeline version."
        )
    if not result.point_in_time_validated or not result.values:
        raise FeatureComputationError(
            "Only non-empty point-in-time-valid results may be persisted."
        )

    feature_run_id = uuid4()
    recorded_at = datetime.now(timezone.utc)
    inserted_value_count = 0
    membership_count = 0

    async with session.begin():
        await _verify_source_snapshot_against_database(session, snapshot)
        run_record = FeaturePipelineRunRecord(
            id=feature_run_id,
            pipeline_version=INTRADAY_PIPELINE_VERSION,
            asset_identifier=result.asset_identifier,
            quote_currency=result.quote_currency,
            timeframe=result.timeframe.value,
            source_ingestion_batch_id=(
                result.source_ingestion_batch_ids[0]
            ),
            source_candle_count=len(snapshot.observations),
            source_range_start=snapshot.range_start,
            source_range_end=snapshot.range_end,
            source_data_hash=result.source_data_hash,
            source_provenance_hash=result.source_provenance_hash,
            result_hash=result.result_hash,
            registry_hash=result.registry_hash,
            registry_schema_version=result.registry_schema_version,
            availability_contract_version=(
                result.availability_contract_version
            ),
            registry_snapshot=(
                INTRADAY_FEATURE_REGISTRY.canonical_payload()
            ),
            point_in_time_validated=True,
            feature_value_count=len(result.values),
            persisted_value_count=0,
            is_active=False,
            computed_at=recorded_at,
        )
        session.add(run_record)
        await session.flush()

        await _persist_source_memberships(
            session,
            feature_run_id,
            snapshot,
            recorded_at,
        )
        stored_values, inserted_value_count = (
            await _reconcile_feature_values(
                session,
                feature_run_id,
                snapshot,
                result,
                recorded_at,
            )
        )
        await _persist_value_memberships(
            session,
            feature_run_id,
            stored_values,
            recorded_at,
        )
        run_record.persisted_value_count = len(stored_values)
        membership_count = await _verify_run_memberships(
            session,
            feature_run_id,
            expected_source_count=len(
                result.source_ingestion_batch_ids
            ),
            expected_value_count=len(result.values),
        )
        await _promote_active_run(
            session,
            run_record,
            recorded_at,
        )

    return IntradayFeaturePersistenceResult(
        feature_run_id=feature_run_id,
        pipeline_version=INTRADAY_PIPELINE_VERSION,
        timeframe=result.timeframe.value,
        source_data_hash=result.source_data_hash,
        source_provenance_hash=result.source_provenance_hash,
        registry_hash=result.registry_hash,
        result_hash=result.result_hash,
        source_candle_count=len(snapshot.observations),
        source_batch_count=len(result.source_ingestion_batch_ids),
        computed_value_count=len(result.values),
        inserted_value_count=inserted_value_count,
        reused_value_count=(
            len(result.values) - inserted_value_count
        ),
        membership_count=membership_count,
        is_active=True,
    )


async def _verify_source_snapshot_against_database(
    session: AsyncSession,
    snapshot: IntradaySourceSnapshot,
) -> None:
    conflicts = await unresolved_source_conflicts(
        session,
        snapshot.timeframe,
        range_start=snapshot.range_start,
        range_end=snapshot.range_end,
    )
    if conflicts:
        raise FeatureComputationError(
            "Unresolved source conflicts intersect the feature source range."
        )
    batches = tuple(
        (
            await session.scalars(
                select(IngestionBatchRecord).where(
                    IngestionBatchRecord.id.in_(
                        snapshot.source_ingestion_batch_ids
                    )
                )
            )
        ).all()
    )
    if len(batches) != len(snapshot.source_ingestion_batch_ids):
        raise FeatureComputationError(
            "One or more source ingestion batches do not exist."
        )
    for batch in batches:
        if (
            not batch.validation_passed
            or batch.asset_identifier != snapshot.asset_identifier
            or batch.quote_currency != snapshot.quote_currency
            or batch.timeframe != snapshot.timeframe.value
        ):
            raise FeatureComputationError(
                "Source ingestion batch is invalid or out of scope."
            )

    records = tuple(
        (
            await session.scalars(
                select(CandleRecord)
                .where(
                    CandleRecord.asset_identifier
                    == snapshot.asset_identifier,
                    CandleRecord.quote_currency
                    == snapshot.quote_currency,
                    CandleRecord.timeframe == snapshot.timeframe.value,
                    CandleRecord.candle_timestamp
                    >= snapshot.range_start,
                    CandleRecord.candle_timestamp
                    <= snapshot.range_end,
                )
                .order_by(CandleRecord.candle_timestamp)
            )
        ).all()
    )
    if len(records) != len(snapshot.observations):
        raise FeatureComputationError(
            "Persisted source candles do not match the snapshot count."
        )
    for record, observation in zip(
        records,
        snapshot.observations,
        strict=True,
    ):
        candle = observation.candle
        if (
            not record.is_complete
            or record.ingestion_batch_id
            != observation.ingestion_batch_id
            or record.candle_timestamp != candle.timestamp
            or record.open_price != candle.open
            or record.high_price != candle.high
            or record.low_price != candle.low
            or record.close_price != candle.close
            or record.volume != candle.volume
        ):
            raise FeatureComputationError(
                "Persisted source candle differs from snapshot evidence."
            )


async def _persist_source_memberships(
    session: AsyncSession,
    feature_run_id: UUID,
    snapshot: IntradaySourceSnapshot,
    recorded_at: datetime,
) -> None:
    for evidence in source_batch_evidence(snapshot):
        session.add(
            FeaturePipelineRunSourceRecord(
                feature_run_id=feature_run_id,
                ingestion_batch_id=evidence.ingestion_batch_id,
                source_candle_count=evidence.source_candle_count,
                source_range_start=evidence.range_start,
                source_range_end=evidence.range_end,
                source_subset_hash=evidence.source_subset_hash,
                recorded_at=recorded_at,
            )
        )
    await session.flush()


async def _reconcile_feature_values(
    session: AsyncSession,
    feature_run_id: UUID,
    snapshot: IntradaySourceSnapshot,
    result: IntradayFeaturePipelineResult,
    recorded_at: datetime,
) -> tuple[tuple[EngineeredFeatureRecord, ...], int]:
    existing = await _load_result_feature_values(session, result)
    source_batch_by_timestamp = {
        observation.candle.timestamp: observation.ingestion_batch_id
        for observation in snapshot.observations
    }
    _verify_stored_values(
        existing,
        result.values,
        source_batch_by_timestamp,
    )
    existing_identities = {
        (record.candle_timestamp, record.feature_name)
        for record in existing
    }
    missing = tuple(
        value
        for value in result.values
        if (value.candle_timestamp, value.output_name)
        not in existing_identities
    )

    inserted_count = 0
    for offset in range(0, len(missing), _INSERT_CHUNK_SIZE):
        chunk = missing[offset : offset + _INSERT_CHUNK_SIZE]
        statement = (
            insert(EngineeredFeatureRecord)
            .values(
                [
                    _feature_value_row(
                        value,
                        feature_run_id,
                        result,
                        source_batch_by_timestamp,
                        recorded_at,
                    )
                    for value in chunk
                ]
            )
            .on_conflict_do_nothing(
                constraint="uq_engineered_features_identity"
            )
            .returning(EngineeredFeatureRecord.id)
        )
        inserted_count += len(
            tuple((await session.scalars(statement)).all())
        )

    stored = await _load_result_feature_values(session, result)
    _verify_stored_values(
        stored,
        result.values,
        source_batch_by_timestamp,
        require_complete=True,
    )
    return _order_stored_values(stored, result.values), inserted_count


async def _load_result_feature_values(
    session: AsyncSession,
    result: IntradayFeaturePipelineResult,
) -> tuple[EngineeredFeatureRecord, ...]:
    timestamps = tuple(
        sorted({value.candle_timestamp for value in result.values})
    )
    output_names = tuple(
        sorted({value.output_name for value in result.values})
    )
    return tuple(
        (
            await session.scalars(
                select(EngineeredFeatureRecord).where(
                    EngineeredFeatureRecord.asset_identifier
                    == result.asset_identifier,
                    EngineeredFeatureRecord.quote_currency
                    == result.quote_currency,
                    EngineeredFeatureRecord.timeframe
                    == result.timeframe.value,
                    EngineeredFeatureRecord.pipeline_version
                    == INTRADAY_PIPELINE_VERSION,
                    EngineeredFeatureRecord.candle_timestamp.in_(timestamps),
                    EngineeredFeatureRecord.feature_name.in_(output_names),
                )
            )
        ).all()
    )


def _verify_stored_values(
    records: tuple[EngineeredFeatureRecord, ...],
    expected_values: tuple[PipelineFeatureValue, ...],
    source_batch_by_timestamp: dict[datetime | None, UUID],
    *,
    require_complete: bool = False,
) -> None:
    stored = {
        (record.candle_timestamp, record.feature_name): record
        for record in records
    }
    if len(stored) != len(records):
        raise FeatureComputationError(
            "Stored feature values contain duplicate identities."
        )
    if require_complete and len(stored) != len(expected_values):
        raise FeatureComputationError(
            "Stored feature values do not cover the complete result."
        )
    expected_identities = {
        (value.candle_timestamp, value.output_name)
        for value in expected_values
    }
    if set(stored) - expected_identities:
        raise FeatureComputationError(
            "Stored feature query returned an unexpected identity."
        )
    expected_by_identity = {
        (value.candle_timestamp, value.output_name): value
        for value in expected_values
    }
    for identity, record in stored.items():
        expected = expected_by_identity[identity]
        if (
            record.feature_value != expected.value
            or record.available_at != expected.available_at
            or record.source_ingestion_batch_id
            != source_batch_by_timestamp[expected.candle_timestamp]
        ):
            raise FeatureComputationError(
                "Immutable stored feature value differs from the result."
            )


def _order_stored_values(
    records: tuple[EngineeredFeatureRecord, ...],
    expected_values: tuple[PipelineFeatureValue, ...],
) -> tuple[EngineeredFeatureRecord, ...]:
    by_identity = {
        (record.candle_timestamp, record.feature_name): record
        for record in records
    }
    return tuple(
        by_identity[(value.candle_timestamp, value.output_name)]
        for value in expected_values
    )


def _feature_value_row(
    value: PipelineFeatureValue,
    feature_run_id: UUID,
    result: IntradayFeaturePipelineResult,
    source_batch_by_timestamp: dict[datetime | None, UUID],
    recorded_at: datetime,
) -> dict[str, object]:
    return {
        "asset_identifier": result.asset_identifier,
        "quote_currency": result.quote_currency,
        "timeframe": result.timeframe.value,
        "candle_timestamp": value.candle_timestamp,
        "available_at": value.available_at,
        "feature_name": value.output_name,
        "feature_value": value.value,
        "pipeline_version": INTRADAY_PIPELINE_VERSION,
        "source_ingestion_batch_id": (
            source_batch_by_timestamp[value.candle_timestamp]
        ),
        "computation_run_id": feature_run_id,
        "computed_at": recorded_at,
    }


async def _persist_value_memberships(
    session: AsyncSession,
    feature_run_id: UUID,
    values: tuple[EngineeredFeatureRecord, ...],
    recorded_at: datetime,
) -> None:
    statement = insert(FeaturePipelineRunValueRecord).values(
        [
            {
                "feature_run_id": feature_run_id,
                "feature_value_id": value.id,
                "recorded_at": recorded_at,
            }
            for value in values
        ]
    )
    await session.execute(statement)


async def _verify_run_memberships(
    session: AsyncSession,
    feature_run_id: UUID,
    *,
    expected_source_count: int,
    expected_value_count: int,
) -> int:
    source_count = int(
        await session.scalar(
            select(func.count()).select_from(
                FeaturePipelineRunSourceRecord
            ).where(
                FeaturePipelineRunSourceRecord.feature_run_id
                == feature_run_id
            )
        )
        or 0
    )
    value_count = int(
        await session.scalar(
            select(func.count()).select_from(
                FeaturePipelineRunValueRecord
            ).where(
                FeaturePipelineRunValueRecord.feature_run_id
                == feature_run_id
            )
        )
        or 0
    )
    if (
        source_count != expected_source_count
        or value_count != expected_value_count
    ):
        raise FeatureComputationError(
            "Persisted feature-run memberships are incomplete."
        )
    return value_count


async def _promote_active_run(
    session: AsyncSession,
    run_record: FeaturePipelineRunRecord,
    recorded_at: datetime,
) -> None:
    if (
        run_record.persisted_value_count
        != run_record.feature_value_count
        or run_record.result_hash is None
        or run_record.source_provenance_hash is None
    ):
        raise FeatureComputationError(
            "Incomplete feature run cannot be promoted."
        )
    await session.execute(
        update(FeaturePipelineRunRecord)
        .where(
            FeaturePipelineRunRecord.asset_identifier
            == run_record.asset_identifier,
            FeaturePipelineRunRecord.quote_currency
            == run_record.quote_currency,
            FeaturePipelineRunRecord.timeframe
            == run_record.timeframe,
            FeaturePipelineRunRecord.is_active.is_(True),
            FeaturePipelineRunRecord.id != run_record.id,
        )
        .values(is_active=False, superseded_at=recorded_at)
    )
    run_record.is_active = True
    await session.flush()


def _required_hash(value: str | None) -> str:
    if value is None:
        raise FeatureComputationError(
            "Persisted intraday feature run is missing hash evidence."
        )
    return value
