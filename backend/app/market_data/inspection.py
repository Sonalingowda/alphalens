"""Deterministic immutable contracts for historical operational inspection."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any


INSPECTION_SCHEMA_VERSION = "1.0.0"
INSPECTION_HASH_SCHEMA_VERSION = "1.0.0"


class HistoricalInspectionError(RuntimeError):
    """Raised when an inspection snapshot cannot be proven."""


@dataclass(frozen=True, slots=True)
class HistoricalOperationalInspection:
    """Canonical, immutable JSON evidence returned by the inspection surface."""

    canonical_json: str
    result_hash: str

    def response(self) -> dict[str, Any]:
        value = json.loads(self.canonical_json)
        value["result_hash"] = self.result_hash
        return value


def build_historical_operational_inspection(
    *,
    as_of: datetime,
    acquisition: list[dict[str, Any]],
    source_conflicts: list[dict[str, Any]],
    synchronized_coverage: dict[str, Any] | None,
    historical_quality: dict[str, Any] | None,
) -> HistoricalOperationalInspection:
    """Seal already-verified evidence in one stable point-in-time representation."""
    cutoff = _utc(as_of)
    payload = {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "hash_schema_version": INSPECTION_HASH_SCHEMA_VERSION,
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "as_of": _timestamp(cutoff),
        "integrity_status": "VERIFIED",
        "operational_state": {
            "acquisition": [
                {
                    "timeframe": item["timeframe"],
                    "state": item["operational_state"],
                }
                for item in acquisition
            ],
            "source_conflict_count": len(source_conflicts),
            "synchronized_coverage": (
                "AVAILABLE" if synchronized_coverage is not None else "UNAVAILABLE"
            ),
            "historical_quality": (
                "AVAILABLE" if historical_quality is not None else "UNAVAILABLE"
            ),
        },
        "acquisition": acquisition,
        "source_conflicts": source_conflicts,
        "synchronized_coverage": synchronized_coverage,
        "historical_quality": historical_quality,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return HistoricalOperationalInspection(
        canonical_json=canonical,
        result_hash=sha256(canonical.encode("utf-8")).hexdigest(),
    )


def verify_historical_operational_inspection(
    inspection: HistoricalOperationalInspection,
) -> None:
    try:
        payload = json.loads(inspection.canonical_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HistoricalInspectionError(
            "Inspection evidence is not canonical JSON."
        ) from exc
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if (
        canonical != inspection.canonical_json
        or sha256(canonical.encode("utf-8")).hexdigest() != inspection.result_hash
    ):
        raise HistoricalInspectionError(
            "Historical inspection integrity verification failed."
        )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalInspectionError("Inspection as-of must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
