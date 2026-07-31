"""Immutable persistence for historical freshness and adequacy reports."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.market_data.coverage import HistoricalCoverageError
from app.market_data.models import CandleTimeframe
from app.market_data.quality import (
    HistoricalQualityError,
    HistoricalQualityReport,
    TimeframeQualityReport,
    build_historical_quality_report,
    verify_historical_quality_report,
)
from app.market_data.synchronization import CoverageSnapshotReference
from app.persistence.conflicts import unresolved_source_conflicts
from app.persistence.coverage import (
    load_historical_coverage_snapshot,
    load_persisted_historical_coverage_snapshot,
    persist_historical_coverage_snapshot,
)
from app.persistence.models import (
    HistoricalQualityReportRecord,
    HistoricalQualityTimeframeRecord,
)


@dataclass(frozen=True, slots=True)
class HistoricalQualityPersistenceResult:
    report_id: UUID
    result_hash: str
    reused: bool


@dataclass(frozen=True, slots=True)
class HistoricalQualityExecutionResult:
    report: HistoricalQualityReport
    persistence: HistoricalQualityPersistenceResult


async def generate_historical_quality_report(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    as_of: datetime,
) -> HistoricalQualityExecutionResult:
    """Load point-in-time evidence and persist one independent 3-TF report."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HistoricalQualityError(
            "Historical quality as-of cutoff must be timezone-aware."
        )
    cutoff = as_of.astimezone(timezone.utc)
    references: list[CoverageSnapshotReference | None] = []
    conflict_counts: list[int] = []
    for timeframe in (
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    ):
        async with session_maker() as session:
            conflicts = await unresolved_source_conflicts(
                session,
                timeframe,
                available_by=cutoff,
            )
        conflict_counts.append(len(conflicts))
        try:
            async with session_maker() as session:
                snapshot = await load_historical_coverage_snapshot(
                    session,
                    timeframe,
                    as_of=cutoff,
                    report_unresolved_conflicts=True,
                )
        except HistoricalCoverageError as error:
            if "at least one canonical candle" not in str(error):
                raise
            references.append(None)
            continue
        async with session_maker() as session:
            persisted = await persist_historical_coverage_snapshot(
                session,
                snapshot,
            )
        references.append(
            CoverageSnapshotReference(
                snapshot_id=persisted.snapshot_id,
                snapshot=snapshot,
            )
        )

    report = build_historical_quality_report(
        as_of=cutoff,
        five_minute=references[0],
        ten_minute=references[1],
        fifteen_minute=references[2],
        unresolved_conflict_counts=tuple(conflict_counts),  # type: ignore[arg-type]
    )
    async with session_maker() as session:
        persistence = await persist_historical_quality_report(session, report)
    return HistoricalQualityExecutionResult(
        report=report,
        persistence=persistence,
    )


async def persist_historical_quality_report(
    session: AsyncSession,
    report: HistoricalQualityReport,
) -> HistoricalQualityPersistenceResult:
    """Insert one semantic report or verify and reuse its existing row."""
    verify_historical_quality_report(report)
    async with session.begin():
        existing = await session.scalar(
            select(HistoricalQualityReportRecord).where(
                HistoricalQualityReportRecord.result_hash == report.result_hash
            )
        )
        if existing is not None:
            rows = tuple(
                (
                    await session.scalars(
                        select(HistoricalQualityTimeframeRecord).where(
                            HistoricalQualityTimeframeRecord.report_id == existing.id
                        )
                    )
                ).all()
            )
            _verify_existing_report(existing, rows, report)
            return HistoricalQualityPersistenceResult(
                report_id=existing.id,
                result_hash=report.result_hash,
                reused=True,
            )

        report_id = uuid4()
        session.add(_report_record(report_id, report))
        await session.flush()
        session.add_all(
            [_timeframe_record(report_id, item) for item in report.timeframes]
        )
    return HistoricalQualityPersistenceResult(
        report_id=report_id,
        result_hash=report.result_hash,
        reused=False,
    )


async def load_persisted_historical_quality_report(
    session: AsyncSession,
    report_id: UUID,
) -> HistoricalQualityReport:
    """Reconstruct and verify one immutable historical quality report."""
    record = await session.get(HistoricalQualityReportRecord, report_id)
    if record is None:
        raise HistoricalQualityError("Historical quality evidence is missing.")
    rows = tuple(
        (
            await session.scalars(
                select(HistoricalQualityTimeframeRecord)
                .where(HistoricalQualityTimeframeRecord.report_id == report_id)
                .order_by(HistoricalQualityTimeframeRecord.timeframe)
            )
        ).all()
    )
    rows_by_timeframe = {row.timeframe: row for row in rows}
    if set(rows_by_timeframe) != {"5m", "10m", "15m"} or len(rows) != 3:
        raise HistoricalQualityError(
            "Stored historical quality report has incomplete timeframe evidence."
        )
    references: list[CoverageSnapshotReference | None] = []
    conflict_counts: list[int] = []
    for timeframe in ("5m", "10m", "15m"):
        row = rows_by_timeframe[timeframe]
        conflict_counts.append(row.unresolved_conflict_count)
        if row.source_snapshot_id is None:
            references.append(None)
            continue
        snapshot = await load_persisted_historical_coverage_snapshot(
            session,
            row.source_snapshot_id,
        )
        references.append(
            CoverageSnapshotReference(
                snapshot_id=row.source_snapshot_id,
                snapshot=snapshot,
            )
        )
    report = build_historical_quality_report(
        as_of=record.as_of,
        five_minute=references[0],
        ten_minute=references[1],
        fifteen_minute=references[2],
        unresolved_conflict_counts=tuple(conflict_counts),  # type: ignore[arg-type]
    )
    _verify_existing_report(record, rows, report)
    return report


def _report_record(
    report_id: UUID,
    report: HistoricalQualityReport,
) -> HistoricalQualityReportRecord:
    return HistoricalQualityReportRecord(
        id=report_id,
        schema_version=report.schema_version,
        hash_schema_version=report.hash_schema_version,
        acquisition_policy_identifier=report.acquisition_policy_identifier,
        acquisition_policy_version=report.acquisition_policy_version,
        acquisition_policy_hash=report.acquisition_policy_hash,
        source_policy_identifier=report.source_policy_identifier,
        source_policy_version=report.source_policy_version,
        as_of=report.as_of,
        freshness_policy_status=report.freshness_policy_status,
        publication_allowed=report.publication_allowed,
        source_provenance_hash=report.source_provenance_hash,
        result_hash=report.result_hash,
        immutable=True,
    )


def _timeframe_record(
    report_id: UUID,
    item: TimeframeQualityReport,
) -> HistoricalQualityTimeframeRecord:
    return HistoricalQualityTimeframeRecord(
        report_id=report_id,
        timeframe=item.timeframe.value,
        adequacy_status=item.adequacy_status,
        acquisition_outcome=item.acquisition_outcome,
        freshness_status=item.freshness_status,
        source_snapshot_id=(
            UUID(item.source_snapshot_id)
            if item.source_snapshot_id is not None
            else None
        ),
        source_snapshot_result_hash=item.source_snapshot_result_hash,
        source_provenance_hash=item.source_provenance_hash,
        first_completed_timestamp=item.first_completed_timestamp,
        last_completed_timestamp=item.last_completed_timestamp,
        elapsed_history_seconds=item.elapsed_history_seconds,
        expected_candle_count=item.expected_candle_count,
        observed_candle_count=item.observed_candle_count,
        gap_count=item.gap_count,
        gap_timestamps=[value.isoformat() for value in item.gap_timestamps],
        coverage_ratio=item.coverage_ratio,
        provider_limited_start=item.provider_limited_start,
        expected_latest_completed_timestamp=(item.expected_latest_completed_timestamp),
        latest_canonical_completed_at=item.latest_canonical_completed_at,
        canonical_lag_seconds=item.canonical_lag_seconds,
        latest_retrieved_at=item.latest_retrieved_at,
        retrieval_age_seconds=item.retrieval_age_seconds,
        unresolved_conflict_count=item.unresolved_conflict_count,
        validation_verified=item.validation_verified,
        provenance_verified=item.provenance_verified,
        result_hash=item.result_hash,
    )


def _verify_existing_report(
    record: HistoricalQualityReportRecord,
    rows: tuple[HistoricalQualityTimeframeRecord, ...],
    report: HistoricalQualityReport,
) -> None:
    expected: dict[str, Any] = {
        "schema_version": report.schema_version,
        "hash_schema_version": report.hash_schema_version,
        "acquisition_policy_identifier": report.acquisition_policy_identifier,
        "acquisition_policy_version": report.acquisition_policy_version,
        "acquisition_policy_hash": report.acquisition_policy_hash,
        "source_policy_identifier": report.source_policy_identifier,
        "source_policy_version": report.source_policy_version,
        "as_of": report.as_of,
        "freshness_policy_status": report.freshness_policy_status,
        "publication_allowed": report.publication_allowed,
        "source_provenance_hash": report.source_provenance_hash,
        "result_hash": report.result_hash,
        "immutable": True,
    }
    if any(getattr(record, name) != value for name, value in expected.items()):
        raise HistoricalQualityError(
            "Stored historical quality report conflicts with its result hash."
        )
    stored_by_timeframe = {row.timeframe: row for row in rows}
    if set(stored_by_timeframe) != {"5m", "10m", "15m"}:
        raise HistoricalQualityError(
            "Stored historical quality report has incomplete timeframe evidence."
        )
    for item in report.timeframes:
        expected_row = _timeframe_record(record.id, item)
        stored = stored_by_timeframe[item.timeframe.value]
        names = tuple(
            column.name
            for column in HistoricalQualityTimeframeRecord.__table__.columns
            if column.name != "report_id"
        )
        if any(getattr(stored, name) != getattr(expected_row, name) for name in names):
            raise HistoricalQualityError(
                "Stored timeframe quality evidence conflicts with its result hash."
            )
