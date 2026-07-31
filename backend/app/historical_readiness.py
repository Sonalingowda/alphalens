"""P1-08 validation runner for immutable historical expansion readiness."""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.market_data.readiness import (
    HistoricalExpansionReadinessReport,
    HistoricalReadinessError,
    build_historical_expansion_readiness_report,
)
from app.persistence.database import session_factory
from app.persistence.inspection import load_historical_operational_inspection
from app.persistence.readiness import (
    HistoricalReadinessPersistenceResult,
    persist_historical_expansion_readiness_report,
)


@dataclass(frozen=True, slots=True)
class HistoricalReadinessExecution:
    report: HistoricalExpansionReadinessReport
    persistence: HistoricalReadinessPersistenceResult


async def execute_historical_expansion_validation(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    as_of: datetime,
) -> HistoricalReadinessExecution:
    """Read verified evidence, build readiness, and append its immutable report."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HistoricalReadinessError("Readiness as-of must be timezone-aware.")
    cutoff = as_of.astimezone(timezone.utc)
    async with session_maker() as session:
        inspection = await load_historical_operational_inspection(
            session,
            as_of=cutoff,
        )
    report = build_historical_expansion_readiness_report(inspection)
    async with session_maker() as session:
        persistence = await persist_historical_expansion_readiness_report(
            session,
            report,
        )
    return HistoricalReadinessExecution(report=report, persistence=persistence)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate immutable Phase-1 historical expansion evidence."
    )
    parser.add_argument(
        "--as-of",
        required=True,
        help="Explicit timezone-aware point-in-time cutoff.",
    )
    arguments = parser.parse_args()
    as_of = _parse_as_of(arguments.as_of)
    execution = asyncio.run(
        execute_historical_expansion_validation(session_factory, as_of=as_of)
    )
    payload = execution.report.response()
    payload["readiness_report_id"] = str(execution.persistence.report_id)
    payload["persistence_reused"] = execution.persistence.reused
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _parse_as_of(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HistoricalReadinessError("Readiness as-of is invalid.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalReadinessError("Readiness as-of must be timezone-aware.")
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    main()
