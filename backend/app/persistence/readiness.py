"""Append-only persistence for Phase-1 historical readiness reports."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.readiness import (
    HistoricalExpansionReadinessReport,
    HistoricalReadinessError,
    verify_historical_expansion_readiness_report,
)
from app.persistence.models import HistoricalExpansionReadinessReportRecord


@dataclass(frozen=True, slots=True)
class HistoricalReadinessPersistenceResult:
    report_id: UUID
    result_hash: str
    reused: bool


async def persist_historical_expansion_readiness_report(
    session: AsyncSession,
    report: HistoricalExpansionReadinessReport,
) -> HistoricalReadinessPersistenceResult:
    """Insert one semantic readiness report or verify and reuse it."""
    verify_historical_expansion_readiness_report(report)
    async with session.begin():
        existing = await session.scalar(
            select(HistoricalExpansionReadinessReportRecord).where(
                HistoricalExpansionReadinessReportRecord.result_hash
                == report.result_hash
            )
        )
        if existing is not None:
            _verify_record(existing, report)
            return HistoricalReadinessPersistenceResult(
                report_id=existing.id,
                result_hash=report.result_hash,
                reused=True,
            )
        report_id = uuid4()
        session.add(_record(report_id, report))
        await session.flush()
    return HistoricalReadinessPersistenceResult(
        report_id=report_id,
        result_hash=report.result_hash,
        reused=False,
    )


async def load_historical_expansion_readiness_report(
    session: AsyncSession,
    report_id: UUID,
) -> HistoricalExpansionReadinessReport:
    """Load and verify one immutable readiness report."""
    record = await session.get(HistoricalExpansionReadinessReportRecord, report_id)
    if record is None:
        raise HistoricalReadinessError("Historical readiness report is missing.")
    report = HistoricalExpansionReadinessReport(
        canonical_json=record.canonical_json,
        result_hash=record.result_hash,
    )
    _verify_record(record, report)
    return report


def _record(
    report_id: UUID,
    report: HistoricalExpansionReadinessReport,
) -> HistoricalExpansionReadinessReportRecord:
    payload = report.response()
    source = payload["source_evidence"]
    return HistoricalExpansionReadinessReportRecord(
        id=report_id,
        schema_version=payload["schema_version"],
        hash_schema_version=payload["hash_schema_version"],
        asset_identifier=payload["asset_identifier"],
        quote_currency=payload["quote_currency"],
        as_of=_datetime(payload["as_of"]),
        readiness_status=payload["readiness_status"],
        acquisition_level_eligible=payload["acquisition_level_eligible"],
        blocker_count=len(payload["blockers"]),
        source_inspection_hash=source["inspection_result_hash"],
        source_synchronization_hash=source["synchronization_result_hash"],
        source_quality_hash=source["quality_result_hash"],
        source_provenance_hash=payload["source_provenance_hash"],
        canonical_json=report.canonical_json,
        result_hash=report.result_hash,
        immutable=True,
    )


def _verify_record(
    record: HistoricalExpansionReadinessReportRecord,
    report: HistoricalExpansionReadinessReport,
) -> None:
    verify_historical_expansion_readiness_report(report)
    expected = _record(record.id, report)
    names = (
        "schema_version",
        "hash_schema_version",
        "asset_identifier",
        "quote_currency",
        "as_of",
        "readiness_status",
        "acquisition_level_eligible",
        "blocker_count",
        "source_inspection_hash",
        "source_synchronization_hash",
        "source_quality_hash",
        "source_provenance_hash",
        "canonical_json",
        "result_hash",
        "immutable",
    )
    if any(getattr(record, name) != getattr(expected, name) for name in names):
        raise HistoricalReadinessError(
            "Stored historical readiness report conflicts with its result hash."
        )


def _datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise HistoricalReadinessError("Readiness report as-of is invalid.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalReadinessError("Readiness report as-of is invalid.")
    return parsed
