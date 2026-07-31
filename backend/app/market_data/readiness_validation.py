"""Approved-policy checks for historical expansion readiness evidence."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from app.market_data.coverage import (
    ACQUISITION_POLICY_IDENTIFIER,
    ACQUISITION_POLICY_VERSION,
)
from app.market_data.orchestration import ACQUISITION_POLICY_HASH
from app.market_data.quality import (
    CANDIDATE_C_ACQUISITION_POLICY_IDENTIFIER,
    CANDIDATE_C_ACQUISITION_POLICY_VERSION,
    approved_acquisition_adequacy_policy_hash,
    evaluate_acquisition_adequacy,
)


_TIMEFRAMES = ("5m", "10m", "15m")
_NATIVE_TIMEFRAMES = ("5m", "15m")
SOURCE_MEMBERSHIP_MANIFEST_HASH_SCHEMA_VERSION = "1.0.0"


class HistoricalReadinessError(RuntimeError):
    """Raised when readiness evidence cannot be safely interpreted."""


def _validate_acquisition(value: Any, blockers: list[str]) -> list[dict[str, Any]]:
    _require(isinstance(value, list), "Acquisition evidence must be a list.")
    by_timeframe = _unique_by_timeframe(value, _NATIVE_TIMEFRAMES, "Acquisition")
    result: list[dict[str, Any]] = []
    for timeframe in _NATIVE_TIMEFRAMES:
        item = by_timeframe[timeframe]
        attempt = item.get("attempt")
        checkpoint = item.get("checkpoint")
        if attempt is None:
            _require(
                item.get("integrity_status") == "UNAVAILABLE",
                "Unavailable acquisition integrity status is invalid.",
            )
            blockers.append(f"ACQUISITION_{timeframe.upper()}_UNAVAILABLE")
        else:
            _require(
                item.get("integrity_status") == "VERIFIED",
                "Acquisition integrity is not verified.",
            )
            _hash(attempt.get("attempt_hash"), "Acquisition attempt hash")
            _hash(attempt.get("configuration_hash"), "Acquisition configuration hash")
            _hash(attempt.get("policy_hash"), "Acquisition policy hash")
            if (
                attempt.get("policy_identifier") != ACQUISITION_POLICY_IDENTIFIER
                or attempt.get("policy_version") != ACQUISITION_POLICY_VERSION
                or attempt.get("policy_hash") != ACQUISITION_POLICY_HASH
            ):
                blockers.append(f"POLICY_{timeframe.upper()}_INCOMPATIBLE")
        if checkpoint is None:
            blockers.append(f"ACQUISITION_{timeframe.upper()}_CHECKPOINT_UNAVAILABLE")
        else:
            _hash(checkpoint.get("checkpoint_hash"), "Checkpoint hash")
            _hash(checkpoint.get("progress_hash"), "Checkpoint progress hash")
            _hash(checkpoint.get("source_data_hash"), "Checkpoint source hash")
            _require(
                checkpoint.get("timeframe") == timeframe,
                "Checkpoint timeframe is inconsistent.",
            )
            counts = tuple(
                checkpoint.get(name)
                for name in (
                    "provider_row_count",
                    "accepted_count",
                    "excluded_incomplete_count",
                    "reused_count",
                    "inserted_count",
                )
            )
            _require(
                all(isinstance(value, int) and value >= 0 for value in counts)
                and checkpoint.get("accepted_count")
                == checkpoint.get("reused_count") + checkpoint.get("inserted_count")
                and checkpoint.get("validation_passed") is True,
                "Checkpoint acquisition counts do not verify.",
            )
            provider_start = _parse_timestamp(
                checkpoint.get("provider_available_start"),
                "Checkpoint provider start",
            )
            provider_end = _parse_timestamp(
                checkpoint.get("provider_available_end"),
                "Checkpoint provider end",
            )
            _require(
                provider_start <= provider_end,
                "Checkpoint provider range is invalid.",
            )
        result.append(
            {
                "timeframe": timeframe,
                "operational_state": item.get("operational_state"),
                "attempt_hash": attempt.get("attempt_hash") if attempt else None,
                "code_version": attempt.get("code_version") if attempt else None,
                "configuration_hash": (
                    attempt.get("configuration_hash") if attempt else None
                ),
                "policy_hash": attempt.get("policy_hash") if attempt else None,
                "checkpoint_hash": (
                    checkpoint.get("checkpoint_hash") if checkpoint else None
                ),
                "progress_hash": (
                    checkpoint.get("progress_hash") if checkpoint else None
                ),
                "terminal_reason": (
                    item.get("outcome", {}).get("terminal_reason")
                    if item.get("outcome")
                    else None
                ),
                "provider_available_start": (
                    checkpoint.get("provider_available_start")
                    if checkpoint
                    else None
                ),
                "provider_available_end": (
                    checkpoint.get("provider_available_end")
                    if checkpoint
                    else None
                ),
                "provider_row_count": (
                    checkpoint.get("provider_row_count") if checkpoint else None
                ),
                "accepted_count": (
                    checkpoint.get("accepted_count") if checkpoint else None
                ),
                "excluded_incomplete_count": (
                    checkpoint.get("excluded_incomplete_count")
                    if checkpoint
                    else None
                ),
                "reused_count": checkpoint.get("reused_count") if checkpoint else None,
                "inserted_count": (
                    checkpoint.get("inserted_count") if checkpoint else None
                ),
                "provider_limit_reached": (
                    checkpoint.get("provider_limit_reached")
                    if checkpoint
                    else None
                ),
            }
        )
    return result


def _validate_conflicts(value: Any) -> list[dict[str, str]]:
    _require(isinstance(value, list), "Source-conflict evidence must be a list.")
    result: list[dict[str, str]] = []
    prior: tuple[str, str, str, str] | None = None
    for item in value:
        _require(isinstance(item, dict), "Source-conflict evidence is invalid.")
        conflict_hash = _hash(item.get("conflict_hash"), "Source-conflict hash")
        key = (
            str(item.get("timeframe")),
            str(item.get("candle_timestamp")),
            str(item.get("available_at")),
            str(item.get("conflict_id")),
        )
        _require(prior is None or prior <= key, "Source conflicts are not ordered.")
        prior = key
        result.append(
            {
                "conflict_id": str(item.get("conflict_id")),
                "timeframe": str(item.get("timeframe")),
                "available_at": str(item.get("available_at")),
                "conflict_hash": conflict_hash,
            }
        )
    return result


def _validate_synchronization(
    value: Any,
    blockers: list[str],
    as_of: datetime,
) -> dict[str, Any] | None:
    if value is None:
        blockers.append("SYNCHRONIZATION_UNAVAILABLE")
        return None
    _require(isinstance(value, dict), "Synchronization evidence is invalid.")
    _require(
        value.get("integrity_status") == "VERIFIED",
        "Synchronization integrity is not verified.",
    )
    _require(
        _parse_timestamp(value.get("as_of"), "Synchronization as-of") <= as_of,
        "Synchronization evidence is after the inspection cutoff.",
    )
    _hash(value.get("result_hash"), "Synchronization result hash")
    _hash(value.get("source_provenance_hash"), "Synchronization provenance hash")
    snapshots = value.get("source_snapshots")
    _require(isinstance(snapshots, list), "Synchronization snapshots are invalid.")
    snapshot_by_timeframe = _unique_by_timeframe(
        snapshots,
        _TIMEFRAMES,
        "Synchronization snapshot",
    )
    for timeframe in _TIMEFRAMES:
        snapshot = snapshot_by_timeframe[timeframe]
        _hash(snapshot.get("result_hash"), "Coverage snapshot result hash")
        _hash(snapshot.get("source_data_hash"), "Coverage source-data hash")
        _hash(
            snapshot.get("source_provenance_hash"),
            "Coverage source-provenance hash",
        )
        expected = snapshot.get("expected_candle_count")
        observed = snapshot.get("observed_candle_count")
        gaps = snapshot.get("gap_count")
        _require(
            isinstance(expected, int)
            and isinstance(observed, int)
            and isinstance(gaps, int)
            and expected > 0
            and observed > 0
            and gaps >= 0
            and expected == observed + gaps,
            "Coverage snapshot counts are invalid.",
        )
        _require(
            _parse_timestamp(
                snapshot.get("coverage_range_start"),
                "Coverage range start",
            )
            <= _parse_timestamp(
                snapshot.get("coverage_range_end"),
                "Coverage range end",
            ),
            "Coverage snapshot range is invalid.",
        )
    derivations = value.get("derivations")
    _require(isinstance(derivations, list), "Synchronization derivations are invalid.")
    derived_ids: set[int] = set()
    for derivation in derivations:
        _require(isinstance(derivation, dict), "10m derivation evidence is invalid.")
        derived_id = derivation.get("derived_candle_id")
        _require(
            isinstance(derived_id, int) and derived_id not in derived_ids,
            "10m derivation identities are invalid or duplicated.",
        )
        derived_ids.add(derived_id)
        _hash(derivation.get("result_hash"), "10m derivation result hash")
        _hash(
            derivation.get("source_membership_hash"),
            "10m source-membership hash",
        )
        members = derivation.get("source_members")
        _require(
            isinstance(members, list)
            and [member.get("ordinal") for member in members] == [0, 1],
            "10m derivation must retain exactly two ordered 5m members.",
        )
        for member in members:
            _hash(member.get("candle_hash"), "10m source candle hash")
    return value


def _validate_quality(
    value: Any,
    blockers: list[str],
    as_of: datetime,
) -> dict[str, Any] | None:
    if value is None:
        blockers.append("QUALITY_UNAVAILABLE")
        return None
    _require(isinstance(value, dict), "Historical quality evidence is invalid.")
    _require(
        value.get("integrity_status") == "VERIFIED",
        "Historical quality integrity is not verified.",
    )
    _require(
        _parse_timestamp(value.get("as_of"), "Historical quality as-of") <= as_of,
        "Historical quality evidence is after the inspection cutoff.",
    )
    _hash(value.get("result_hash"), "Historical quality result hash")
    _hash(value.get("source_provenance_hash"), "Historical quality provenance hash")
    timeframes = value.get("timeframes")
    _require(isinstance(timeframes, list), "Historical quality timeframes are invalid.")
    by_timeframe = _unique_by_timeframe(timeframes, _TIMEFRAMES, "Quality timeframe")
    for timeframe in _TIMEFRAMES:
        item = by_timeframe[timeframe]
        elapsed = item.get("elapsed_history_seconds")
        expected = item.get("expected_candle_count")
        observed = item.get("observed_candle_count")
        conflict_count = item.get("unresolved_conflict_count")
        gap_count = item.get("gap_count")
        gap_timestamps = item.get("gap_timestamps")
        _require(
            isinstance(elapsed, int)
            and isinstance(expected, int)
            and isinstance(observed, int)
            and isinstance(conflict_count, int),
            "Historical quality measurements are invalid.",
        )
        _require(
            isinstance(gap_count, int)
            and isinstance(gap_timestamps, list)
            and gap_count == len(gap_timestamps),
            "Historical quality gap evidence is invalid.",
        )
        for timestamp in gap_timestamps:
            _parse_timestamp(timestamp, "Historical quality gap timestamp")
        expected_status, expected_outcome, expected_ratio = (
            evaluate_acquisition_adequacy(
                elapsed_history_seconds=elapsed,
                expected_candle_count=expected,
                observed_candle_count=observed,
                unresolved_conflict_count=conflict_count,
            )
        )
        _require(
            item.get("adequacy_status") == expected_status
            and item.get("acquisition_outcome") == expected_outcome
            and item.get("coverage_ratio") == format(expected_ratio, "f"),
            "Historical quality outcome does not match approved policy.",
        )
        if (
            item.get("adequacy_status") != "ADEQUATE"
            or item.get("acquisition_outcome")
            != "ADEQUATE_FOR_DOWNSTREAM_ADEQUACY_EVALUATION"
        ):
            blockers.append(f"QUALITY_{timeframe.upper()}_INADEQUATE")
        if (
            item.get("validation_verified") is not True
            or item.get("provenance_verified") is not True
        ):
            blockers.append(f"QUALITY_{timeframe.upper()}_INTEGRITY_UNPROVEN")
        if item.get("unresolved_conflict_count") != 0:
            blockers.append(f"QUALITY_{timeframe.upper()}_CONFLICT")
        _hash(item.get("result_hash"), "Timeframe quality result hash")
    return value


def _validate_policy(
    quality: dict[str, Any] | None,
    blockers: list[str],
) -> dict[str, Any]:
    expected_hash = approved_acquisition_adequacy_policy_hash()
    actual = {
        "acquisition_policy_identifier": (
            quality.get("acquisition_policy_identifier") if quality else None
        ),
        "acquisition_policy_version": (
            quality.get("acquisition_policy_version") if quality else None
        ),
        "acquisition_policy_hash": (
            quality.get("acquisition_policy_hash") if quality else None
        ),
        "source_policy_identifier": (
            quality.get("source_policy_identifier") if quality else None
        ),
        "source_policy_version": (
            quality.get("source_policy_version") if quality else None
        ),
    }
    expected = {
        "acquisition_policy_identifier": CANDIDATE_C_ACQUISITION_POLICY_IDENTIFIER,
        "acquisition_policy_version": CANDIDATE_C_ACQUISITION_POLICY_VERSION,
        "acquisition_policy_hash": expected_hash,
        "source_policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
        "source_policy_version": ACQUISITION_POLICY_VERSION,
    }
    if actual != expected:
        blockers.append("POLICY_INCOMPATIBLE")
    return {**actual, "compatibility_status": "VERIFIED" if actual == expected else "BLOCKED"}


def _validate_coverage_and_provenance(
    synchronization: dict[str, Any] | None,
    quality: dict[str, Any] | None,
    blockers: list[str],
) -> list[dict[str, Any]]:
    if synchronization is None or quality is None:
        if synchronization is None:
            blockers.append("PROVENANCE_SYNCHRONIZATION_UNAVAILABLE")
        if quality is None:
            blockers.append("COVERAGE_QUALITY_UNAVAILABLE")
        return []
    sync_by = _unique_by_timeframe(
        synchronization["source_snapshots"],
        _TIMEFRAMES,
        "Synchronization snapshot",
    )
    quality_by = _unique_by_timeframe(
        quality["timeframes"],
        _TIMEFRAMES,
        "Quality timeframe",
    )
    result: list[dict[str, Any]] = []
    if len(synchronization["derivations"]) != sync_by["10m"].get(
        "observed_candle_count"
    ):
        blockers.append("SYNCHRONIZATION_DERIVATION_COUNT_DIVERGENCE")
    for timeframe in _TIMEFRAMES:
        sync_item = sync_by[timeframe]
        quality_item = quality_by[timeframe]
        if (
            quality_item.get("source_snapshot_id") != sync_item.get("snapshot_id")
            or quality_item.get("source_snapshot_result_hash")
            != sync_item.get("result_hash")
            or quality_item.get("source_provenance_hash")
            != sync_item.get("source_provenance_hash")
        ):
            blockers.append(f"PROVENANCE_{timeframe.upper()}_DIVERGENCE")
        if (
            quality_item.get("expected_candle_count")
            != sync_item.get("expected_candle_count")
            or quality_item.get("observed_candle_count")
            != sync_item.get("observed_candle_count")
            or quality_item.get("gap_count") != sync_item.get("gap_count")
        ):
            blockers.append(f"COVERAGE_{timeframe.upper()}_DIVERGENCE")
        result.append(
            {
                "timeframe": timeframe,
                "source_snapshot_id": sync_item.get("snapshot_id"),
                "coverage_range_start": sync_item.get("coverage_range_start"),
                "coverage_range_end": sync_item.get("coverage_range_end"),
                "expected_candle_count": quality_item.get("expected_candle_count"),
                "observed_candle_count": quality_item.get("observed_candle_count"),
                "gap_count": quality_item.get("gap_count"),
                "gap_timestamps": quality_item.get("gap_timestamps"),
                "coverage_ratio": quality_item.get("coverage_ratio"),
                "elapsed_history_seconds": quality_item.get(
                    "elapsed_history_seconds"
                ),
                "adequacy_status": quality_item.get("adequacy_status"),
                "acquisition_outcome": quality_item.get("acquisition_outcome"),
                "source_data_hash": sync_item.get("source_data_hash"),
                "source_provenance_hash": sync_item.get("source_provenance_hash"),
                "result_hash": sync_item.get("result_hash"),
            }
        )
    return result


def _membership_manifest(synchronization: dict[str, Any] | None) -> dict[str, Any]:
    entries = [] if synchronization is None else [
        {
            "derived_candle_id": item["derived_candle_id"],
            "source_membership_hash": item["source_membership_hash"],
            "result_hash": item["result_hash"],
        }
        for item in synchronization["derivations"]
    ]
    return {
        "hash_schema_version": SOURCE_MEMBERSHIP_MANIFEST_HASH_SCHEMA_VERSION,
        "derivation_count": len(entries),
        "ordered_memberships": entries,
        "result_hash": _sha256(
            {
                "hash_schema_version": SOURCE_MEMBERSHIP_MANIFEST_HASH_SCHEMA_VERSION,
                "ordered_memberships": entries,
            }
        ),
    }


def _synchronization_summary(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    differences = value.get("differences")
    _require(isinstance(differences, dict), "Synchronization differences are invalid.")
    return {
        "synchronization_id": value.get("synchronization_id"),
        "as_of": value.get("as_of"),
        "derivation_count": len(value["derivations"]),
        "differences": differences,
        "source_provenance_hash": value.get("source_provenance_hash"),
        "result_hash": value.get("result_hash"),
    }


def _check(
    identifier: str,
    blockers: list[str],
    prefix: str,
) -> dict[str, Any]:
    related = [item for item in blockers if item.startswith(prefix)]
    return {
        "identifier": identifier,
        "status": "VERIFIED" if not related else "BLOCKED",
        "blockers": related,
    }


def _unique_by_timeframe(
    values: list[Any],
    expected: tuple[str, ...],
    label: str,
) -> dict[str, dict[str, Any]]:
    _require(all(isinstance(item, dict) for item in values), f"{label} is invalid.")
    by_timeframe = {item.get("timeframe"): item for item in values}
    _require(
        len(values) == len(expected)
        and tuple(item.get("timeframe") for item in values) == expected
        and set(by_timeframe) == set(expected),
        f"{label} ordering or membership is invalid.",
    )
    return by_timeframe  # type: ignore[return-value]


def _hash(value: Any, label: str) -> str:
    _require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        f"{label} is invalid.",
    )
    return value


def _parse_timestamp(value: Any, label: str) -> datetime:
    _require(isinstance(value, str), f"{label} is invalid.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HistoricalReadinessError(f"{label} is invalid.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise HistoricalReadinessError(f"{label} must be timezone-aware.")
    return parsed.astimezone(timezone.utc)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise HistoricalReadinessError(message)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()
