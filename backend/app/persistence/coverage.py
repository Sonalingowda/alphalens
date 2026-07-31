"""Immutable historical coverage snapshot persistence."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.coverage import (
    CoverageBatchEvidence,
    CoverageObservation,
    HistoricalCoverageError,
    HistoricalCoverageSnapshot,
    build_historical_coverage_snapshot,
    verify_historical_coverage_snapshot,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import timeframe_duration
from app.persistence.models import (
    CandleRecord,
    HistoricalCoverageSnapshotBatchRecord,
    HistoricalCoverageSnapshotCandleRecord,
    HistoricalCoverageSnapshotRecord,
    IngestionBatchRecord,
)
from app.persistence.conflicts import unresolved_source_conflicts


@dataclass(frozen=True, slots=True)
class HistoricalCoveragePersistenceResult:
    snapshot_id: UUID
    result_hash: str
    observed_candle_count: int
    gap_count: int
    source_batch_count: int
    reused: bool


async def load_historical_coverage_snapshot(
    session: AsyncSession,
    timeframe: CandleTimeframe,
    *,
    as_of: datetime | None = None,
) -> HistoricalCoverageSnapshot:
    """Load canonical BTC/USD evidence and construct its coverage snapshot."""
    if timeframe not in {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    }:
        raise HistoricalCoverageError(
            "Historical coverage supports only 5m, 10m, and 15m."
        )

    cutoff = _utc(as_of) if as_of is not None else None
    conflicts = await unresolved_source_conflicts(
        session,
        timeframe,
        available_by=cutoff,
    )
    if conflicts:
        raise HistoricalCoverageError(
            "Unresolved source conflicts block a new coverage snapshot."
        )

    statement = (
        select(CandleRecord, IngestionBatchRecord)
        .join(
            IngestionBatchRecord,
            IngestionBatchRecord.id == CandleRecord.ingestion_batch_id,
        )
        .where(
            CandleRecord.asset_identifier == "BTC",
            CandleRecord.quote_currency == "USD",
            CandleRecord.timeframe == timeframe.value,
        )
    )
    if cutoff is not None:
        statement = statement.where(
            CandleRecord.ingested_at <= cutoff,
            IngestionBatchRecord.retrieved_at <= cutoff,
            CandleRecord.candle_timestamp
            <= cutoff - timeframe_duration(timeframe),
        )
    rows = (
        await session.execute(
            statement.order_by(CandleRecord.candle_timestamp, CandleRecord.id)
        )
    ).all()

    observations: list[CoverageObservation] = []
    batches: dict[UUID, CoverageBatchEvidence] = {}
    for candle_record, batch_record in rows:
        observations.append(_observation(candle_record))
        batch_evidence = _batch_evidence(batch_record)
        existing = batches.get(batch_evidence.ingestion_batch_id)
        if existing is not None and existing != batch_evidence:
            raise HistoricalCoverageError(
                "Conflicting source batch evidence was loaded."
            )
        batches[batch_evidence.ingestion_batch_id] = batch_evidence

    return build_historical_coverage_snapshot(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe=timeframe,
        observations=tuple(observations),
        batches=tuple(batches.values()),
    )


async def persist_historical_coverage_snapshot(
    session: AsyncSession,
    snapshot: HistoricalCoverageSnapshot,
) -> HistoricalCoveragePersistenceResult:
    """Persist a verified snapshot once, reusing an identical immutable row."""
    verify_historical_coverage_snapshot(snapshot)

    async with session.begin():
        existing = await session.scalar(
            select(HistoricalCoverageSnapshotRecord).where(
                HistoricalCoverageSnapshotRecord.result_hash
                == snapshot.result_hash
            )
        )
        if existing is not None:
            _verify_existing_record(existing, snapshot)
            candle_memberships = tuple(
                (
                    await session.scalars(
                        select(
                            HistoricalCoverageSnapshotCandleRecord
                        )
                        .where(
                            HistoricalCoverageSnapshotCandleRecord.snapshot_id
                            == existing.id
                        )
                        .order_by(
                            HistoricalCoverageSnapshotCandleRecord.ordinal
                        )
                    )
                ).all()
            )
            batch_memberships = tuple(
                (
                    await session.scalars(
                        select(HistoricalCoverageSnapshotBatchRecord)
                        .where(
                            HistoricalCoverageSnapshotBatchRecord.snapshot_id
                            == existing.id
                        )
                        .order_by(
                            HistoricalCoverageSnapshotBatchRecord
                            .ingestion_batch_id
                        )
                    )
                ).all()
            )
            _verify_existing_memberships(
                candle_memberships,
                batch_memberships,
                snapshot,
            )
            return _persistence_result(existing.id, snapshot, reused=True)

        snapshot_id = uuid4()
        session.add(_snapshot_record(snapshot_id, snapshot))
        await session.flush()
        session.add_all(
            [
                HistoricalCoverageSnapshotCandleRecord(
                    snapshot_id=snapshot_id,
                    candle_id=item.candle_id,
                    ordinal=ordinal,
                )
                for ordinal, item in enumerate(snapshot.observations)
            ]
        )
        session.add_all(
            [
                HistoricalCoverageSnapshotBatchRecord(
                    snapshot_id=snapshot_id,
                    ingestion_batch_id=item.ingestion_batch_id,
                    candle_count=item.candle_count,
                    source_subset_hash=item.source_subset_hash,
                )
                for item in snapshot.batch_memberships
            ]
        )

    return _persistence_result(snapshot_id, snapshot, reused=False)


def _observation(record: CandleRecord) -> CoverageObservation:
    return CoverageObservation(
        candle_id=record.id,
        ingestion_batch_id=record.ingestion_batch_id,
        provider=record.provider,
        is_complete=record.is_complete,
        candle=Candle(
            timestamp=_utc(record.candle_timestamp),
            open=record.open_price,
            high=record.high_price,
            low=record.low_price,
            close=record.close_price,
            volume=record.volume,
        ),
    )


def _batch_evidence(record: IngestionBatchRecord) -> CoverageBatchEvidence:
    source_timeframe = (
        CandleTimeframe(record.source_timeframe)
        if record.source_timeframe is not None
        else None
    )
    return CoverageBatchEvidence(
        ingestion_batch_id=record.id,
        provider=record.provider,
        asset_identifier=record.asset_identifier,
        quote_currency=record.quote_currency,
        timeframe=CandleTimeframe(record.timeframe),
        requested_start=_utc(record.requested_start),
        requested_end_exclusive=_utc(record.requested_end_exclusive),
        retrieved_at=_utc(record.retrieved_at),
        validation_passed=record.validation_passed,
        validation_issues=tuple(record.validation_issues),
        source_timeframe=source_timeframe,
        derivation_method=record.derivation_method,
        source_ingestion_batch_id=record.source_ingestion_batch_id,
    )


def _snapshot_record(
    snapshot_id: UUID,
    snapshot: HistoricalCoverageSnapshot,
) -> HistoricalCoverageSnapshotRecord:
    return HistoricalCoverageSnapshotRecord(
        id=snapshot_id,
        schema_version=snapshot.schema_version,
        hash_schema_version=snapshot.hash_schema_version,
        acquisition_policy_identifier=(
            snapshot.acquisition_policy_identifier
        ),
        acquisition_policy_version=snapshot.acquisition_policy_version,
        asset_identifier=snapshot.asset_identifier,
        quote_currency=snapshot.quote_currency,
        timeframe=snapshot.timeframe.value,
        requested_range_start=snapshot.requested_range_start,
        requested_range_end_exclusive=(
            snapshot.requested_range_end_exclusive
        ),
        coverage_range_start=snapshot.coverage_range_start,
        coverage_range_end=snapshot.coverage_range_end,
        expected_candle_count=snapshot.expected_candle_count,
        observed_candle_count=snapshot.observed_candle_count,
        gap_count=snapshot.gap_count,
        gap_timestamps=[
            value.isoformat() for value in snapshot.gap_timestamps
        ],
        source_batch_count=snapshot.source_batch_count,
        validation_summary={
            "passed": snapshot.validation_report.passed,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "timestamp": (
                        issue.timestamp.isoformat()
                        if issue.timestamp is not None
                        else None
                    ),
                }
                for issue in snapshot.validation_report.issues
            ],
        },
        derivation_summary=[
            dict(value) for value in snapshot.derivation_summary
        ],
        validation_hash=snapshot.validation_hash,
        source_data_hash=snapshot.source_data_hash,
        source_provenance_hash=snapshot.source_provenance_hash,
        result_hash=snapshot.result_hash,
        immutable=True,
    )


def _verify_existing_record(
    record: HistoricalCoverageSnapshotRecord,
    snapshot: HistoricalCoverageSnapshot,
) -> None:
    expected: dict[str, Any] = {
        "schema_version": snapshot.schema_version,
        "hash_schema_version": snapshot.hash_schema_version,
        "acquisition_policy_identifier": (
            snapshot.acquisition_policy_identifier
        ),
        "acquisition_policy_version": snapshot.acquisition_policy_version,
        "asset_identifier": snapshot.asset_identifier,
        "quote_currency": snapshot.quote_currency,
        "timeframe": snapshot.timeframe.value,
        "requested_range_start": snapshot.requested_range_start,
        "requested_range_end_exclusive": (
            snapshot.requested_range_end_exclusive
        ),
        "coverage_range_start": snapshot.coverage_range_start,
        "coverage_range_end": snapshot.coverage_range_end,
        "expected_candle_count": snapshot.expected_candle_count,
        "observed_candle_count": snapshot.observed_candle_count,
        "gap_count": snapshot.gap_count,
        "source_batch_count": snapshot.source_batch_count,
        "validation_hash": snapshot.validation_hash,
        "source_data_hash": snapshot.source_data_hash,
        "source_provenance_hash": snapshot.source_provenance_hash,
        "result_hash": snapshot.result_hash,
        "immutable": True,
    }
    mismatches = tuple(
        name
        for name, expected_value in expected.items()
        if getattr(record, name) != expected_value
    )
    if mismatches:
        raise HistoricalCoverageError(
            "Stored coverage snapshot conflicts with its result hash: "
            + ", ".join(mismatches)
        )


def _verify_existing_memberships(
    candle_memberships: tuple[
        HistoricalCoverageSnapshotCandleRecord,
        ...,
    ],
    batch_memberships: tuple[
        HistoricalCoverageSnapshotBatchRecord,
        ...,
    ],
    snapshot: HistoricalCoverageSnapshot,
) -> None:
    stored_candles = tuple(
        (item.candle_id, item.ordinal) for item in candle_memberships
    )
    expected_candles = tuple(
        (item.candle_id, ordinal)
        for ordinal, item in enumerate(snapshot.observations)
    )
    stored_batches = tuple(
        (
            item.ingestion_batch_id,
            item.candle_count,
            item.source_subset_hash,
        )
        for item in batch_memberships
    )
    expected_batches = tuple(
        (
            item.ingestion_batch_id,
            item.candle_count,
            item.source_subset_hash,
        )
        for item in snapshot.batch_memberships
    )
    if (
        stored_candles != expected_candles
        or stored_batches != expected_batches
    ):
        raise HistoricalCoverageError(
            "Stored coverage membership conflicts with its result hash."
        )


def _persistence_result(
    snapshot_id: UUID,
    snapshot: HistoricalCoverageSnapshot,
    *,
    reused: bool,
) -> HistoricalCoveragePersistenceResult:
    return HistoricalCoveragePersistenceResult(
        snapshot_id=snapshot_id,
        result_hash=snapshot.result_hash,
        observed_candle_count=snapshot.observed_candle_count,
        gap_count=snapshot.gap_count,
        source_batch_count=snapshot.source_batch_count,
        reused=reused,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise HistoricalCoverageError(
            "Persisted coverage timestamps must be timezone-aware."
        )
    return value.astimezone(timezone.utc)
