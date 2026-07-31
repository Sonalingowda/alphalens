"""Deterministic Phase-1 historical expansion readiness evidence."""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.market_data.inspection import (
    HistoricalInspectionError,
    HistoricalOperationalInspection,
    verify_historical_operational_inspection,
)
from app.market_data.readiness_validation import (
    _TIMEFRAMES,
    HistoricalReadinessError,
    SOURCE_MEMBERSHIP_MANIFEST_HASH_SCHEMA_VERSION,
    _canonical,
    _check,
    _hash,
    _membership_manifest,
    _parse_timestamp,
    _require,
    _sha256,
    _synchronization_summary,
    _timestamp,
    _validate_acquisition,
    _validate_conflicts,
    _validate_coverage_and_provenance,
    _validate_policy,
    _validate_quality,
    _validate_synchronization,
)


READINESS_SCHEMA_VERSION = "1.0.0"
READINESS_HASH_SCHEMA_VERSION = "1.0.0"
READY_STATUS = "READY_FOR_DOWNSTREAM_ADEQUACY_EVALUATION"
BLOCKED_STATUS = "BLOCKED"
@dataclass(frozen=True, slots=True)
class HistoricalExpansionReadinessReport:
    """Content-addressed immutable Phase-1 readiness report."""

    canonical_json: str
    result_hash: str

    def response(self) -> dict[str, Any]:
        payload = json.loads(self.canonical_json)
        payload["result_hash"] = self.result_hash
        return payload


def build_historical_expansion_readiness_report(
    inspection: HistoricalOperationalInspection,
) -> HistoricalExpansionReadinessReport:
    """Validate the complete inspected expansion path under approved policy."""
    try:
        verify_historical_operational_inspection(inspection)
    except HistoricalInspectionError as exc:
        raise HistoricalReadinessError(
            "Source inspection hash does not verify."
        ) from exc
    source = inspection.response()
    as_of = _parse_timestamp(source.get("as_of"), "Inspection as-of")
    _require(source.get("asset_identifier") == "BTC", "Inspection asset is invalid.")
    _require(source.get("quote_currency") == "USD", "Inspection quote is invalid.")
    _require(
        source.get("integrity_status") == "VERIFIED",
        "Inspection integrity status is not verified.",
    )

    blockers: list[str] = []
    acquisition = _validate_acquisition(source.get("acquisition"), blockers)

    conflicts = _validate_conflicts(source.get("source_conflicts"))
    if conflicts:
        blockers.append("UNRESOLVED_SOURCE_CONFLICT")

    synchronization = _validate_synchronization(
        source.get("synchronized_coverage"),
        blockers,
        as_of,
    )

    quality = _validate_quality(
        source.get("historical_quality"),
        blockers,
        as_of,
    )

    policy = _validate_policy(quality, blockers)

    timeframes = _validate_coverage_and_provenance(
        synchronization,
        quality,
        blockers,
    )

    membership_manifest = _membership_manifest(synchronization)
    checks = [
        _check("acquisition_evidence", blockers, "ACQUISITION_"),
        _check("source_conflict_state", blockers, "UNRESOLVED_SOURCE_"),
        _check("synchronization_evidence", blockers, "SYNCHRONIZATION_"),
        _check("historical_quality_evidence", blockers, "QUALITY_"),
        _check("policy_compatibility", blockers, "POLICY_"),
        _check("coverage_completeness", blockers, "COVERAGE_"),
        _check("provenance_traversal", blockers, "PROVENANCE_"),
        {
            "identifier": "deterministic_reproducibility",
            "status": "VERIFIED",
            "blockers": [],
        },
    ]
    ordered_blockers = tuple(dict.fromkeys(blockers))
    status = READY_STATUS if not ordered_blockers else BLOCKED_STATUS
    source_evidence = {
        "inspection_result_hash": inspection.result_hash,
        "synchronization_result_hash": (
            synchronization.get("result_hash") if synchronization else None
        ),
        "quality_result_hash": quality.get("result_hash") if quality else None,
        "synchronization_source_provenance_hash": (
            synchronization.get("source_provenance_hash")
            if synchronization
            else None
        ),
        "quality_source_provenance_hash": (
            quality.get("source_provenance_hash") if quality else None
        ),
        "source_membership_manifest_hash": membership_manifest["result_hash"],
    }
    source_provenance_hash = _sha256(
        {
            "hash_schema_version": READINESS_HASH_SCHEMA_VERSION,
            "source_evidence": source_evidence,
        }
    )
    payload = {
        "schema_version": READINESS_SCHEMA_VERSION,
        "hash_schema_version": READINESS_HASH_SCHEMA_VERSION,
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "as_of": _timestamp(as_of),
        "readiness_status": status,
        "acquisition_level_eligible": not ordered_blockers,
        "phase_2_authorized": False,
        "blockers": list(ordered_blockers),
        "checks": checks,
        "policy": policy,
        "acquisition": acquisition,
        "source_conflicts": conflicts,
        "synchronization": _synchronization_summary(synchronization),
        "timeframes": timeframes,
        "source_membership_manifest": membership_manifest,
        "source_evidence": source_evidence,
        "source_provenance_hash": source_provenance_hash,
    }
    canonical = _canonical(payload)
    report = HistoricalExpansionReadinessReport(
        canonical_json=canonical,
        result_hash=sha256(canonical.encode("utf-8")).hexdigest(),
    )
    verify_historical_expansion_readiness_report(report)
    return report


def verify_historical_expansion_readiness_report(
    report: HistoricalExpansionReadinessReport,
) -> None:
    """Verify canonical encoding, report hash, and readiness invariants."""
    try:
        payload = json.loads(report.canonical_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HistoricalReadinessError("Readiness report is not canonical JSON.") from exc
    canonical = _canonical(payload)
    expected_hash = sha256(canonical.encode("utf-8")).hexdigest()
    if canonical != report.canonical_json or expected_hash != report.result_hash:
        raise HistoricalReadinessError("Readiness report hash does not verify.")
    blockers = payload.get("blockers")
    eligible = payload.get("acquisition_level_eligible")
    status = payload.get("readiness_status")
    if not isinstance(blockers, list) or not all(
        isinstance(item, str) for item in blockers
    ):
        raise HistoricalReadinessError("Readiness blockers are invalid.")
    expected_status = READY_STATUS if not blockers else BLOCKED_STATUS
    if (
        status != expected_status
        or eligible is not (not blockers)
        or payload.get("phase_2_authorized") is not False
        or payload.get("asset_identifier") != "BTC"
        or payload.get("quote_currency") != "USD"
    ):
        raise HistoricalReadinessError("Readiness status invariants do not verify.")
    _parse_timestamp(payload.get("as_of"), "Readiness as-of")
    for name in (
        "source_provenance_hash",
        "source_evidence",
        "checks",
        "timeframes",
    ):
        _require(name in payload, f"Readiness report is missing {name}.")
    source = payload["source_evidence"]
    _require(isinstance(source, dict), "Readiness source evidence is invalid.")
    _hash(source.get("inspection_result_hash"), "Source inspection hash")
    for name in (
        "synchronization_result_hash",
        "quality_result_hash",
        "synchronization_source_provenance_hash",
        "quality_source_provenance_hash",
    ):
        if source.get(name) is not None:
            _hash(source[name], f"Readiness {name}")
    _hash(
        source.get("source_membership_manifest_hash"),
        "Readiness source-membership manifest hash",
    )
    expected_provenance = _sha256(
        {
            "hash_schema_version": READINESS_HASH_SCHEMA_VERSION,
            "source_evidence": source,
        }
    )
    if payload["source_provenance_hash"] != expected_provenance:
        raise HistoricalReadinessError("Readiness source provenance does not verify.")
    manifest = payload.get("source_membership_manifest")
    _require(isinstance(manifest, dict), "Source-membership manifest is invalid.")
    entries = manifest.get("ordered_memberships")
    _require(isinstance(entries, list), "Source-membership entries are invalid.")
    for entry in entries:
        _require(isinstance(entry, dict), "Source-membership entry is invalid.")
        _hash(entry.get("source_membership_hash"), "Source-membership hash")
        _hash(entry.get("result_hash"), "Derivation result hash")
    expected_manifest_hash = _sha256(
        {
            "hash_schema_version": SOURCE_MEMBERSHIP_MANIFEST_HASH_SCHEMA_VERSION,
            "ordered_memberships": entries,
        }
    )
    if (
        manifest.get("hash_schema_version")
        != SOURCE_MEMBERSHIP_MANIFEST_HASH_SCHEMA_VERSION
        or
        manifest.get("derivation_count") != len(entries)
        or manifest.get("result_hash") != expected_manifest_hash
    ):
        raise HistoricalReadinessError("Source-membership manifest does not verify.")
    _require(
        [item.get("timeframe") for item in payload["timeframes"]]
        in ([], list(_TIMEFRAMES)),
        "Readiness timeframe ordering is invalid.",
    )
    if eligible:
        _require(
            source.get("synchronization_result_hash") is not None
            and source.get("quality_result_hash") is not None
            and len(payload["timeframes"]) == 3
            and all(item.get("status") == "VERIFIED" for item in payload["checks"]),
            "Eligible readiness evidence is incomplete.",
        )
