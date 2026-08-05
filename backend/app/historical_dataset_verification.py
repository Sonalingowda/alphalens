"""Read-only CLI verification for approved historical market evidence."""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.market_data.inspection import HistoricalInspectionError
from app.market_data.readiness import (
    HistoricalExpansionReadinessReport,
    HistoricalReadinessError,
    build_historical_expansion_readiness_report,
    verify_historical_expansion_readiness_report,
)
from app.persistence.database import session_factory
from app.persistence.inspection import load_historical_operational_inspection


VERIFICATION_SCHEMA_VERSION = "1.0.0"
VERIFICATION_HASH_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class HistoricalDatasetVerificationReport:
    """Deterministic, content-addressed result of a read-only verification."""

    canonical_json: str
    result_hash: str

    def response(self) -> dict[str, Any]:
        payload = json.loads(self.canonical_json)
        payload["result_hash"] = self.result_hash
        return payload


async def execute_historical_dataset_verification(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    as_of: datetime,
) -> HistoricalDatasetVerificationReport:
    """Read and verify historical evidence without acquiring or persisting data."""
    cutoff = _parse_as_of_datetime(as_of)
    async with session_maker() as session:
        inspection = await load_historical_operational_inspection(
            session,
            as_of=cutoff,
        )
    readiness = build_historical_expansion_readiness_report(inspection)
    return build_historical_dataset_verification_report(readiness)


def build_historical_dataset_verification_report(
    readiness: HistoricalExpansionReadinessReport,
) -> HistoricalDatasetVerificationReport:
    """Wrap verified historical evidence in the CLI's stable report contract."""
    verify_historical_expansion_readiness_report(readiness)
    source = readiness.response()
    blockers = source["blockers"]
    payload = {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "hash_schema_version": VERIFICATION_HASH_SCHEMA_VERSION,
        "report_type": "historical_dataset_verification",
        "asset_identifier": source["asset_identifier"],
        "quote_currency": source["quote_currency"],
        "as_of": source["as_of"],
        "verification_status": "PASSED" if not blockers else "FAILED",
        "failure_reasons": blockers,
        "checks": source["checks"],
        "timeframes": source["timeframes"],
        "source_evidence": {
            "readiness_result_hash": readiness.result_hash,
            "inspection_result_hash": source["source_evidence"][
                "inspection_result_hash"
            ],
            "source_provenance_hash": source["source_provenance_hash"],
        },
    }
    canonical = _canonical(payload)
    report = HistoricalDatasetVerificationReport(
        canonical_json=canonical,
        result_hash=sha256(canonical.encode("utf-8")).hexdigest(),
    )
    verify_historical_dataset_verification_report(report)
    return report


def verify_historical_dataset_verification_report(
    report: HistoricalDatasetVerificationReport,
) -> None:
    """Verify report encoding, hash, and pass/fail state."""
    try:
        payload = json.loads(report.canonical_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HistoricalReadinessError("Verification report is not JSON.") from exc
    canonical = _canonical(payload)
    if (
        canonical != report.canonical_json
        or sha256(canonical.encode("utf-8")).hexdigest() != report.result_hash
    ):
        raise HistoricalReadinessError("Verification report hash does not verify.")
    if (
        payload.get("schema_version") != VERIFICATION_SCHEMA_VERSION
        or payload.get("hash_schema_version") != VERIFICATION_HASH_SCHEMA_VERSION
        or payload.get("report_type") != "historical_dataset_verification"
        or payload.get("asset_identifier") != "BTC"
        or payload.get("quote_currency") != "USD"
    ):
        raise HistoricalReadinessError("Verification report scope is invalid.")
    _parse_as_of(payload.get("as_of"))
    failures = payload.get("failure_reasons")
    status = payload.get("verification_status")
    if (
        not isinstance(failures, list)
        or not all(isinstance(value, str) for value in failures)
        or failures != list(dict.fromkeys(failures))
        or status != ("PASSED" if not failures else "FAILED")
    ):
        raise HistoricalReadinessError("Verification report status is invalid.")
    source = payload.get("source_evidence")
    if not isinstance(source, dict):
        raise HistoricalReadinessError("Verification report source evidence is invalid.")
    for name in (
        "readiness_result_hash",
        "inspection_result_hash",
        "source_provenance_hash",
    ):
        value = source.get(name)
        if not isinstance(value, str) or len(value) != 64:
            raise HistoricalReadinessError("Verification report source hash is invalid.")


def main(arguments: Sequence[str] | None = None) -> int:
    """Run verification and return a non-zero status when evidence fails."""
    parser = argparse.ArgumentParser(
        description="Verify approved historical BTC/USD market evidence read-only."
    )
    parser.add_argument(
        "--as-of",
        required=True,
        help="Explicit timezone-aware point-in-time cutoff.",
    )
    parsed = parser.parse_args(arguments)
    try:
        report = asyncio.run(
            execute_historical_dataset_verification(
                session_factory,
                as_of=_parse_as_of(parsed.as_of),
            )
        )
        print(_canonical(report.response()))
        return 0 if report.response()["verification_status"] == "PASSED" else 1
    except (HistoricalInspectionError, HistoricalReadinessError, SQLAlchemyError) as exc:
        print(
            _canonical(
                {
                    "report_type": "historical_dataset_verification",
                    "verification_status": "FAILED",
                    "failure_reasons": ["VERIFICATION_UNAVAILABLE"],
                    "error": type(exc).__name__,
                }
            )
        )
        return 1


def _parse_as_of(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HistoricalReadinessError("Verification as-of is invalid.") from exc
    return _parse_as_of_datetime(parsed)


def _parse_as_of_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalReadinessError("Verification as-of must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _canonical(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raise SystemExit(main())
