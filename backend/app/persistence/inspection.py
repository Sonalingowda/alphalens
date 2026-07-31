"""Read-only point-in-time reconstruction of historical operational evidence."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.inspection import (
    HistoricalInspectionError,
    HistoricalOperationalInspection,
    build_historical_operational_inspection,
    verify_historical_operational_inspection,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.synchronization import CoverageSnapshotReference
from app.persistence.conflicts import source_conflict_evidence
from app.persistence.historical_orchestration import (
    acquisition_attempt_from_record,
    acquisition_checkpoint_from_record,
)
from app.persistence.models import (
    HistoricalAcquisitionAttemptRecord,
    HistoricalAcquisitionCheckpointRecord,
    HistoricalAcquisitionOutcomeRecord,
    HistoricalQualityReportRecord,
    SourceConflictRecord,
    SynchronizedCoverageSnapshotRecord,
)
from app.persistence.quality import load_persisted_historical_quality_report
from app.persistence.synchronization import (
    load_persisted_synchronized_coverage_snapshot,
)


async def load_historical_operational_inspection(
    session: AsyncSession,
    *,
    as_of: datetime,
) -> HistoricalOperationalInspection:
    """Load and verify all P1 operational evidence without mutating state."""
    cutoff = _utc(as_of)
    acquisition = await _acquisition_evidence(session, cutoff)
    conflicts = await _conflict_evidence(session, cutoff)
    synchronization = await _synchronization_evidence(session, cutoff)
    quality = await _quality_evidence(session, cutoff)
    inspection = build_historical_operational_inspection(
        as_of=cutoff,
        acquisition=acquisition,
        source_conflicts=conflicts,
        synchronized_coverage=synchronization,
        historical_quality=quality,
    )
    verify_historical_operational_inspection(inspection)
    return inspection


async def _acquisition_evidence(
    session: AsyncSession,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    records = tuple(
        (
            await session.scalars(
                select(HistoricalAcquisitionAttemptRecord)
                .where(
                    HistoricalAcquisitionAttemptRecord.asset_identifier == "BTC",
                    HistoricalAcquisitionAttemptRecord.quote_currency == "USD",
                    HistoricalAcquisitionAttemptRecord.started_at <= cutoff,
                    HistoricalAcquisitionAttemptRecord.created_at <= cutoff,
                )
                .order_by(
                    HistoricalAcquisitionAttemptRecord.timeframe,
                    HistoricalAcquisitionAttemptRecord.started_at.desc(),
                    HistoricalAcquisitionAttemptRecord.id.desc(),
                )
            )
        ).all()
    )
    latest = {record.timeframe: record for record in reversed(records)}
    result: list[dict[str, Any]] = []
    for timeframe in (CandleTimeframe.MINUTE_5, CandleTimeframe.MINUTE_15):
        record = latest.get(timeframe.value)
        if record is None:
            result.append(
                {
                    "timeframe": timeframe.value,
                    "operational_state": "NO_ATTEMPT",
                    "attempt": None,
                    "outcome": None,
                    "checkpoint": None,
                    "integrity_status": "UNAVAILABLE",
                }
            )
            continue
        attempt = acquisition_attempt_from_record(record)
        outcome = await session.get(HistoricalAcquisitionOutcomeRecord, record.id)
        if outcome is not None and outcome.completed_at > cutoff:
            outcome = None
        checkpoint = await session.scalar(
            select(HistoricalAcquisitionCheckpointRecord)
            .where(
                HistoricalAcquisitionCheckpointRecord.timeframe == timeframe.value,
                HistoricalAcquisitionCheckpointRecord.created_at <= cutoff,
            )
            .order_by(
                HistoricalAcquisitionCheckpointRecord.created_at.desc(),
                HistoricalAcquisitionCheckpointRecord.id.desc(),
            )
            .limit(1)
        )
        checkpoint_value = None
        if checkpoint is not None:
            verified = acquisition_checkpoint_from_record(checkpoint)
            checkpoint_attempt_record = await session.get(
                HistoricalAcquisitionAttemptRecord,
                verified.attempt_id,
            )
            if checkpoint_attempt_record is None:
                raise HistoricalInspectionError(
                    "Acquisition checkpoint attempt evidence is missing."
                )
            checkpoint_attempt = acquisition_attempt_from_record(
                checkpoint_attempt_record
            )
            if (
                checkpoint_attempt.timeframe is not timeframe
                or checkpoint_attempt.configuration_hash
                != verified.configuration_hash
            ):
                raise HistoricalInspectionError(
                    "Acquisition checkpoint conflicts with its attempt evidence."
                )
            checkpoint_value = {
                "checkpoint_id": str(verified.checkpoint_id),
                "schema_version": verified.schema_version,
                "hash_schema_version": verified.hash_schema_version,
                "attempt_id": str(verified.attempt_id),
                "predecessor_checkpoint_id": _optional_id(
                    verified.predecessor_checkpoint_id
                ),
                "ingestion_batch_id": str(verified.ingestion_batch_id),
                "timeframe": verified.timeframe.value,
                "requested_start": _timestamp(verified.requested_start),
                "requested_end_exclusive": _timestamp(
                    verified.requested_end_exclusive
                ),
                "provider_available_start": _timestamp(
                    verified.provider_available_start
                ),
                "provider_available_end": _timestamp(verified.provider_available_end),
                "provider_cursor": _timestamp(verified.provider_cursor),
                "provider_row_count": verified.provider_row_count,
                "accepted_count": verified.accepted_count,
                "excluded_incomplete_count": verified.excluded_incomplete_count,
                "reused_count": verified.reused_count,
                "inserted_count": verified.inserted_count,
                "conflict_count": verified.conflict_count,
                "validation_passed": verified.validation_passed,
                "provider_limit_reached": verified.provider_limit_reached,
                "terminal_reason": verified.terminal_reason,
                "configuration_hash": verified.configuration_hash,
                "source_data_hash": verified.source_data_hash,
                "progress_hash": verified.progress_hash,
                "checkpoint_hash": verified.checkpoint_hash,
            }
        outcome_value = None
        if outcome is not None:
            if not outcome.immutable:
                raise HistoricalInspectionError("Acquisition outcome is mutable.")
            if checkpoint is not None and checkpoint.attempt_id == record.id and (
                outcome.ingestion_batch_id != checkpoint.ingestion_batch_id
                or outcome.terminal_reason != checkpoint.terminal_reason
            ):
                raise HistoricalInspectionError(
                    "Acquisition outcome conflicts with checkpoint evidence."
                )
            outcome_value = {
                "ingestion_batch_id": _optional_id(outcome.ingestion_batch_id),
                "terminal_reason": outcome.terminal_reason,
                "failure_class": outcome.failure_class,
                "failure_summary": outcome.failure_summary,
                "completed_at": _timestamp(outcome.completed_at),
            }
        result.append(
            {
                "timeframe": timeframe.value,
                "operational_state": (
                    outcome.terminal_reason if outcome is not None else "IN_PROGRESS"
                ),
                "attempt": {
                    "attempt_id": str(attempt.attempt_id),
                    "requested_start": _timestamp(attempt.requested_start),
                    "requested_end_exclusive": _timestamp(
                        attempt.requested_end_exclusive
                    ),
                    "started_at": _timestamp(attempt.started_at),
                    "provider": record.provider,
                    "endpoint_identity": record.endpoint_identity,
                    "policy_identifier": record.policy_identifier,
                    "policy_version": record.policy_version,
                    "policy_hash": record.policy_hash,
                    "code_version": attempt.code_version,
                    "configuration_hash": attempt.configuration_hash,
                    "attempt_hash": attempt.attempt_hash,
                },
                "outcome": outcome_value,
                "checkpoint": checkpoint_value,
                "integrity_status": "VERIFIED",
            }
        )
    return result


async def _conflict_evidence(
    session: AsyncSession,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    records = tuple(
        (
            await session.scalars(
                select(SourceConflictRecord)
                .where(
                    SourceConflictRecord.asset_identifier == "BTC",
                    SourceConflictRecord.quote_currency == "USD",
                    SourceConflictRecord.available_at <= cutoff,
                    SourceConflictRecord.created_at <= cutoff,
                )
                .order_by(
                    SourceConflictRecord.timeframe,
                    SourceConflictRecord.candle_timestamp,
                    SourceConflictRecord.available_at,
                    SourceConflictRecord.id,
                )
            )
        ).all()
    )
    return [
        {
            "conflict_id": str(record.id),
            "schema_version": evidence.schema_version,
            "hash_schema_version": evidence.hash_schema_version,
            "timeframe": evidence.timeframe.value,
            "conflict_type": evidence.conflict_type,
            "candle_timestamp": _timestamp(evidence.candle_timestamp),
            "retrieved_at": _timestamp(evidence.retrieved_at),
            "available_at": _timestamp(evidence.available_at),
            "canonical_candle_id": evidence.canonical_candle_id,
            "canonical_ingestion_batch_id": str(
                evidence.canonical_ingestion_batch_id
            ),
            "canonical_provider": evidence.canonical_provider,
            "canonical_candle": _candle(evidence.canonical_candle),
            "incoming_attempt_id": _optional_id(evidence.incoming_attempt_id),
            "incoming_ingestion_batch_id": str(
                evidence.incoming_ingestion_batch_id
            ),
            "incoming_provider": evidence.incoming_provider,
            "incoming_candle": _candle(evidence.incoming_candle),
            "canonical_candle_hash": evidence.canonical_candle_hash,
            "incoming_candle_hash": evidence.incoming_candle_hash,
            "incoming_batch_source_hash": evidence.incoming_batch_source_hash,
            "conflict_hash": evidence.conflict_hash,
            "integrity_status": "VERIFIED",
        }
        for record in records
        for evidence in (source_conflict_evidence(record),)
    ]


async def _synchronization_evidence(
    session: AsyncSession,
    cutoff: datetime,
) -> dict[str, Any] | None:
    record = await session.scalar(
        select(SynchronizedCoverageSnapshotRecord)
        .where(
            SynchronizedCoverageSnapshotRecord.as_of <= cutoff,
            SynchronizedCoverageSnapshotRecord.created_at <= cutoff,
        )
        .order_by(
            SynchronizedCoverageSnapshotRecord.as_of.desc(),
            SynchronizedCoverageSnapshotRecord.created_at.desc(),
            SynchronizedCoverageSnapshotRecord.id.desc(),
        )
        .limit(1)
    )
    if record is None:
        return None
    snapshot = await load_persisted_synchronized_coverage_snapshot(
        session,
        record.id,
    )
    return {
        "synchronization_id": str(record.id),
        "as_of": _timestamp(snapshot.as_of),
        "schema_version": snapshot.schema_version,
        "hash_schema_version": snapshot.hash_schema_version,
        "source_snapshots": [
            _coverage(reference)
            for reference in (
                snapshot.five_minute,
                snapshot.ten_minute,
                snapshot.fifteen_minute,
            )
        ],
        "derivations": [
            {
                "derived_candle_id": item.derived_candle_id,
                "derived_ingestion_batch_id": str(item.derived_ingestion_batch_id),
                "derivation_method": item.derivation_method,
                "available_at": _timestamp(item.available_at),
                "derived_candle_hash": item.derived_candle_hash,
                "source_membership_hash": item.source_membership_hash,
                "result_hash": item.result_hash,
                "source_members": [
                    {
                        "ordinal": member.ordinal,
                        "candle_id": member.candle_id,
                        "ingestion_batch_id": str(member.ingestion_batch_id),
                        "available_at": _timestamp(member.available_at),
                        "candle_hash": member.candle_hash,
                    }
                    for member in item.source_members
                ],
            }
            for item in snapshot.derivations
        ],
        "differences": record.differences,
        "source_provenance_hash": snapshot.source_provenance_hash,
        "result_hash": snapshot.result_hash,
        "integrity_status": "VERIFIED",
    }


async def _quality_evidence(
    session: AsyncSession,
    cutoff: datetime,
) -> dict[str, Any] | None:
    record = await session.scalar(
        select(HistoricalQualityReportRecord)
        .where(
            HistoricalQualityReportRecord.as_of <= cutoff,
            HistoricalQualityReportRecord.created_at <= cutoff,
        )
        .order_by(
            HistoricalQualityReportRecord.as_of.desc(),
            HistoricalQualityReportRecord.created_at.desc(),
            HistoricalQualityReportRecord.id.desc(),
        )
        .limit(1)
    )
    if record is None:
        return None
    report = await load_persisted_historical_quality_report(session, record.id)
    return {
        "report_id": str(record.id),
        "as_of": _timestamp(report.as_of),
        "schema_version": report.schema_version,
        "hash_schema_version": report.hash_schema_version,
        "acquisition_policy_identifier": report.acquisition_policy_identifier,
        "acquisition_policy_version": report.acquisition_policy_version,
        "acquisition_policy_hash": report.acquisition_policy_hash,
        "source_policy_identifier": report.source_policy_identifier,
        "source_policy_version": report.source_policy_version,
        "freshness_policy_status": report.freshness_policy_status,
        "publication_allowed": report.publication_allowed,
        "timeframes": [
            {
                "timeframe": item.timeframe.value,
                "adequacy_status": item.adequacy_status,
                "acquisition_outcome": item.acquisition_outcome,
                "freshness_status": item.freshness_status,
                "source_snapshot_id": item.source_snapshot_id,
                "source_snapshot_result_hash": item.source_snapshot_result_hash,
                "source_provenance_hash": item.source_provenance_hash,
                "first_completed_timestamp": _optional_timestamp(
                    item.first_completed_timestamp
                ),
                "last_completed_timestamp": _optional_timestamp(
                    item.last_completed_timestamp
                ),
                "elapsed_history_seconds": item.elapsed_history_seconds,
                "expected_candle_count": item.expected_candle_count,
                "observed_candle_count": item.observed_candle_count,
                "gap_count": item.gap_count,
                "gap_timestamps": [_timestamp(value) for value in item.gap_timestamps],
                "coverage_ratio": _decimal(item.coverage_ratio),
                "provider_limited_start": _optional_timestamp(
                    item.provider_limited_start
                ),
                "expected_latest_completed_timestamp": _timestamp(
                    item.expected_latest_completed_timestamp
                ),
                "latest_canonical_completed_at": _optional_timestamp(
                    item.latest_canonical_completed_at
                ),
                "canonical_lag_seconds": item.canonical_lag_seconds,
                "latest_retrieved_at": _optional_timestamp(item.latest_retrieved_at),
                "retrieval_age_seconds": item.retrieval_age_seconds,
                "unresolved_conflict_count": item.unresolved_conflict_count,
                "validation_verified": item.validation_verified,
                "provenance_verified": item.provenance_verified,
                "result_hash": item.result_hash,
            }
            for item in report.timeframes
        ],
        "source_provenance_hash": report.source_provenance_hash,
        "result_hash": report.result_hash,
        "integrity_status": "VERIFIED",
    }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalInspectionError("Inspection as-of must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _optional_timestamp(value: datetime | None) -> str | None:
    return None if value is None else _timestamp(value)


def _optional_id(value: object | None) -> str | None:
    return None if value is None else str(value)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _candle(value: Candle) -> dict[str, str]:
    return {
        "timestamp": _timestamp(value.timestamp),
        "open": _decimal(value.open),
        "high": _decimal(value.high),
        "low": _decimal(value.low),
        "close": _decimal(value.close),
        "volume": _decimal(value.volume),
    }


def _coverage(reference: CoverageSnapshotReference) -> dict[str, Any]:
    snapshot = reference.snapshot
    return {
        "timeframe": snapshot.timeframe.value,
        "snapshot_id": str(reference.snapshot_id),
        "requested_range_start": _timestamp(snapshot.requested_range_start),
        "requested_range_end_exclusive": _timestamp(
            snapshot.requested_range_end_exclusive
        ),
        "coverage_range_start": _timestamp(snapshot.coverage_range_start),
        "coverage_range_end": _timestamp(snapshot.coverage_range_end),
        "expected_candle_count": snapshot.expected_candle_count,
        "observed_candle_count": snapshot.observed_candle_count,
        "gap_count": snapshot.gap_count,
        "gap_timestamps": [_timestamp(value) for value in snapshot.gap_timestamps],
        "source_batch_count": snapshot.source_batch_count,
        "validation_hash": snapshot.validation_hash,
        "source_data_hash": snapshot.source_data_hash,
        "source_provenance_hash": snapshot.source_provenance_hash,
        "result_hash": snapshot.result_hash,
    }
