"""Append-only persistence for resumable intraday acquisition evidence."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.market_data.coverage import (
    ACQUISITION_POLICY_IDENTIFIER,
    ACQUISITION_POLICY_VERSION,
)
from app.market_data.history import HistoricalSample
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.orchestration import (
    ACQUISITION_POLICY_HASH,
    KRAKEN_ENDPOINT_IDENTITY,
    AcquisitionAttempt,
    AcquisitionCheckpoint,
    CheckpointIntegrityError,
    CheckpointReconciliationRequired,
    HistoricalOrchestrationError,
    hash_candle_sequence,
    verify_acquisition_checkpoint,
    verify_acquisition_attempt,
)
from app.persistence.candles import (
    CandlePersistenceResult,
    persist_historical_sample,
)
from app.persistence.models import (
    CandleRecord,
    HistoricalAcquisitionAttemptRecord,
    HistoricalAcquisitionCheckpointRecord,
    HistoricalAcquisitionOutcomeRecord,
    IngestionBatchRecord,
)


class SqlHistoricalOrchestrationStore:
    """PostgreSQL-backed append-only orchestration evidence store."""

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_maker = session_maker

    async def prepare_resume(
        self,
        timeframe: CandleTimeframe,
        configuration_hash: str,
        code_version: str,
    ) -> AcquisitionCheckpoint | None:
        async with self._session_maker() as session:
            incomplete = await session.scalar(
                select(HistoricalAcquisitionAttemptRecord)
                .outerjoin(
                    HistoricalAcquisitionOutcomeRecord,
                    HistoricalAcquisitionOutcomeRecord.attempt_id
                    == HistoricalAcquisitionAttemptRecord.id,
                )
                .where(
                    HistoricalAcquisitionAttemptRecord.timeframe == timeframe.value,
                    HistoricalAcquisitionOutcomeRecord.attempt_id.is_(None),
                )
                .order_by(HistoricalAcquisitionAttemptRecord.started_at)
                .limit(1)
            )
            if incomplete is not None:
                batch = await session.scalar(
                    select(IngestionBatchRecord).where(
                        IngestionBatchRecord.acquisition_attempt_id == incomplete.id
                    )
                )
                if batch is not None:
                    raise CheckpointReconciliationRequired(
                        "Committed acquisition evidence lacks a checkpoint; "
                        "automatic checkpoint repair is prohibited."
                    )
                session.add(
                    HistoricalAcquisitionOutcomeRecord(
                        attempt_id=incomplete.id,
                        ingestion_batch_id=None,
                        terminal_reason="INTERRUPTED_BEFORE_PERSISTENCE",
                        failure_class="InterruptedAcquisition",
                        failure_summary=(
                            "Recovered an attempt with no persisted batch or outcome."
                        ),
                        completed_at=datetime.now(timezone.utc),
                        immutable=True,
                    )
                )
                await session.commit()

            row = (
                await session.execute(
                    select(
                        HistoricalAcquisitionCheckpointRecord,
                        HistoricalAcquisitionAttemptRecord,
                        IngestionBatchRecord,
                        HistoricalAcquisitionOutcomeRecord,
                    )
                    .join(
                        HistoricalAcquisitionAttemptRecord,
                        HistoricalAcquisitionAttemptRecord.id
                        == HistoricalAcquisitionCheckpointRecord.attempt_id,
                    )
                    .join(
                        IngestionBatchRecord,
                        IngestionBatchRecord.id
                        == HistoricalAcquisitionCheckpointRecord.ingestion_batch_id,
                    )
                    .join(
                        HistoricalAcquisitionOutcomeRecord,
                        HistoricalAcquisitionOutcomeRecord.attempt_id
                        == HistoricalAcquisitionCheckpointRecord.attempt_id,
                    )
                    .where(
                        HistoricalAcquisitionCheckpointRecord.timeframe
                        == timeframe.value
                    )
                    .order_by(
                        HistoricalAcquisitionCheckpointRecord.created_at.desc(),
                        HistoricalAcquisitionCheckpointRecord.id.desc(),
                    )
                    .limit(1)
                )
            ).one_or_none()
            if row is None:
                return None
            record, attempt, batch, outcome = row
            domain_attempt = _attempt(attempt)
            verify_acquisition_attempt(domain_attempt)
            if (
                attempt.configuration_hash != configuration_hash
                or attempt.code_version != code_version
                or record.configuration_hash != configuration_hash
            ):
                raise CheckpointIntegrityError(
                    "Latest checkpoint is incompatible with current configuration."
                )
            if (
                batch.acquisition_attempt_id != attempt.id
                or not batch.validation_passed
                or batch.persisted_candle_count != record.inserted_count
                or outcome.ingestion_batch_id != batch.id
                or outcome.terminal_reason != record.terminal_reason
                or not record.immutable
                or not outcome.immutable
            ):
                raise CheckpointIntegrityError(
                    "Checkpoint ingestion-batch evidence does not verify."
                )
            candle_count = await session.scalar(
                select(func.count(CandleRecord.id)).where(
                    CandleRecord.ingestion_batch_id == batch.id
                )
            )
            if int(candle_count or 0) != record.inserted_count:
                raise CheckpointIntegrityError(
                    "Checkpoint canonical candle membership does not verify."
                )
            checkpoint = _checkpoint(record)
            verify_acquisition_checkpoint(checkpoint)
            canonical = await _canonical_candles(
                session,
                timeframe,
                checkpoint.provider_available_start,
                checkpoint.provider_available_end,
            )
            if (
                len(canonical) != checkpoint.accepted_count
                or hash_candle_sequence(canonical) != checkpoint.source_data_hash
            ):
                raise CheckpointIntegrityError(
                    "Checkpoint source candle evidence does not verify."
                )
            return checkpoint

    async def record_attempt(self, attempt: AcquisitionAttempt) -> None:
        verify_acquisition_attempt(attempt)
        async with self._session_maker() as session:
            async with session.begin():
                session.add(_attempt_record(attempt))

    async def record_failure(
        self,
        attempt: AcquisitionAttempt,
        terminal_reason: str,
        failure_class: str,
        failure_summary: str,
        completed_at: datetime,
    ) -> None:
        verify_acquisition_attempt(attempt)
        async with self._session_maker() as session:
            async with session.begin():
                session.add(
                    HistoricalAcquisitionOutcomeRecord(
                        attempt_id=attempt.attempt_id,
                        ingestion_batch_id=None,
                        terminal_reason=terminal_reason,
                        failure_class=failure_class[:96],
                        failure_summary=failure_summary,
                        completed_at=completed_at,
                        immutable=True,
                    )
                )

    async def persist_sample(
        self,
        attempt_id: UUID,
        sample: HistoricalSample,
    ) -> CandlePersistenceResult:
        async with self._session_maker() as session:
            result = await persist_historical_sample(
                session,
                sample,
                acquisition_attempt_id=attempt_id,
            )
        timestamps = tuple(
            candle.timestamp
            for candle in sample.candles
            if candle.timestamp is not None
        )
        async with self._session_maker() as session:
            canonical = await _canonical_candles(
                session,
                sample.timeframe,
                timestamps[0],
                timestamps[-1],
            )
        if len(canonical) != len(sample.candles) or hash_candle_sequence(
            canonical
        ) != hash_candle_sequence(sample.candles):
            raise CheckpointReconciliationRequired(
                "Persisted canonical evidence differs from the acquired window."
            )
        return result

    async def record_checkpoint(
        self,
        attempt: AcquisitionAttempt,
        checkpoint: AcquisitionCheckpoint,
        completed_at: datetime,
    ) -> UUID:
        verify_acquisition_attempt(attempt)
        verify_acquisition_checkpoint(checkpoint)
        if (
            checkpoint.attempt_id != attempt.attempt_id
            or checkpoint.timeframe is not attempt.timeframe
            or checkpoint.configuration_hash != attempt.configuration_hash
        ):
            raise CheckpointIntegrityError(
                "Checkpoint is incompatible with its acquisition attempt."
            )
        async with self._session_maker() as session:
            async with session.begin():
                session.add(_checkpoint_record(checkpoint))
                session.add(
                    HistoricalAcquisitionOutcomeRecord(
                        attempt_id=attempt.attempt_id,
                        ingestion_batch_id=checkpoint.ingestion_batch_id,
                        terminal_reason=checkpoint.terminal_reason,
                        failure_class=None,
                        failure_summary=None,
                        completed_at=completed_at,
                        immutable=True,
                    )
                )
        return checkpoint.checkpoint_id


def _attempt_record(
    attempt: AcquisitionAttempt,
) -> HistoricalAcquisitionAttemptRecord:
    return HistoricalAcquisitionAttemptRecord(
        id=attempt.attempt_id,
        provider="kraken",
        endpoint_identity=KRAKEN_ENDPOINT_IDENTITY,
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=attempt.timeframe.value,
        requested_start=attempt.requested_start,
        requested_end_exclusive=attempt.requested_end_exclusive,
        started_at=attempt.started_at,
        policy_identifier=ACQUISITION_POLICY_IDENTIFIER,
        policy_version=ACQUISITION_POLICY_VERSION,
        policy_hash=ACQUISITION_POLICY_HASH,
        code_version=attempt.code_version,
        configuration_hash=attempt.configuration_hash,
        attempt_hash=attempt.attempt_hash,
        immutable=True,
    )


def _attempt(value: HistoricalAcquisitionAttemptRecord) -> AcquisitionAttempt:
    if (
        value.provider != "kraken"
        or value.endpoint_identity != KRAKEN_ENDPOINT_IDENTITY
        or value.asset_identifier != "BTC"
        or value.quote_currency != "USD"
        or value.policy_identifier != ACQUISITION_POLICY_IDENTIFIER
        or value.policy_version != ACQUISITION_POLICY_VERSION
        or value.policy_hash != ACQUISITION_POLICY_HASH
        or not value.immutable
    ):
        raise CheckpointIntegrityError(
            "Acquisition attempt provenance does not verify."
        )
    return AcquisitionAttempt(
        attempt_id=value.id,
        timeframe=CandleTimeframe(value.timeframe),
        requested_start=_utc(value.requested_start),
        requested_end_exclusive=_utc(value.requested_end_exclusive),
        started_at=_utc(value.started_at),
        code_version=value.code_version,
        configuration_hash=value.configuration_hash,
        attempt_hash=value.attempt_hash,
    )


def _checkpoint_record(
    value: AcquisitionCheckpoint,
) -> HistoricalAcquisitionCheckpointRecord:
    return HistoricalAcquisitionCheckpointRecord(
        id=value.checkpoint_id,
        attempt_id=value.attempt_id,
        predecessor_checkpoint_id=value.predecessor_checkpoint_id,
        ingestion_batch_id=value.ingestion_batch_id,
        schema_version=value.schema_version,
        hash_schema_version=value.hash_schema_version,
        timeframe=value.timeframe.value,
        requested_start=value.requested_start,
        requested_end_exclusive=value.requested_end_exclusive,
        provider_available_start=value.provider_available_start,
        provider_available_end=value.provider_available_end,
        provider_cursor=value.provider_cursor,
        provider_row_count=value.provider_row_count,
        accepted_count=value.accepted_count,
        excluded_incomplete_count=value.excluded_incomplete_count,
        reused_count=value.reused_count,
        inserted_count=value.inserted_count,
        conflict_count=value.conflict_count,
        validation_passed=value.validation_passed,
        provider_limit_reached=value.provider_limit_reached,
        terminal_reason=value.terminal_reason,
        configuration_hash=value.configuration_hash,
        source_data_hash=value.source_data_hash,
        progress_hash=value.progress_hash,
        checkpoint_hash=value.checkpoint_hash,
        immutable=True,
    )


def _checkpoint(
    value: HistoricalAcquisitionCheckpointRecord,
) -> AcquisitionCheckpoint:
    return AcquisitionCheckpoint(
        checkpoint_id=value.id,
        schema_version=value.schema_version,
        hash_schema_version=value.hash_schema_version,
        attempt_id=value.attempt_id,
        predecessor_checkpoint_id=value.predecessor_checkpoint_id,
        timeframe=CandleTimeframe(value.timeframe),
        requested_start=_utc(value.requested_start),
        requested_end_exclusive=_utc(value.requested_end_exclusive),
        provider_available_start=_utc(value.provider_available_start),
        provider_available_end=_utc(value.provider_available_end),
        provider_cursor=_utc(value.provider_cursor),
        provider_row_count=value.provider_row_count,
        accepted_count=value.accepted_count,
        excluded_incomplete_count=value.excluded_incomplete_count,
        reused_count=value.reused_count,
        inserted_count=value.inserted_count,
        conflict_count=value.conflict_count,
        ingestion_batch_id=value.ingestion_batch_id,
        validation_passed=value.validation_passed,
        provider_limit_reached=value.provider_limit_reached,
        terminal_reason=value.terminal_reason,
        configuration_hash=value.configuration_hash,
        source_data_hash=value.source_data_hash,
        progress_hash=value.progress_hash,
        checkpoint_hash=value.checkpoint_hash,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalOrchestrationError(
            "Persisted orchestration timestamps must be timezone-aware."
        )
    return value.astimezone(timezone.utc)


async def _canonical_candles(
    session: AsyncSession,
    timeframe: CandleTimeframe,
    start: datetime,
    end: datetime,
) -> tuple[Candle, ...]:
    records = tuple(
        (
            await session.scalars(
                select(CandleRecord)
                .where(
                    CandleRecord.asset_identifier == "BTC",
                    CandleRecord.quote_currency == "USD",
                    CandleRecord.timeframe == timeframe.value,
                    CandleRecord.candle_timestamp >= start,
                    CandleRecord.candle_timestamp <= end,
                )
                .order_by(CandleRecord.candle_timestamp, CandleRecord.id)
            )
        ).all()
    )
    return tuple(
        Candle(
            timestamp=_utc(record.candle_timestamp),
            open=record.open_price,
            high=record.high_price,
            low=record.low_price,
            close=record.close_price,
            volume=record.volume,
        )
        for record in records
    )
