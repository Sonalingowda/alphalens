"""Deterministic historical freshness and acquisition adequacy reports."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json

from app.market_data.coverage import (
    ACQUISITION_POLICY_IDENTIFIER,
    ACQUISITION_POLICY_VERSION,
    verify_historical_coverage_snapshot,
)
from app.market_data.models import CandleTimeframe
from app.market_data.synchronization import CoverageSnapshotReference
from app.market_data.validation import floor_timeframe_boundary, timeframe_duration


QUALITY_REPORT_SCHEMA_VERSION = "1.0.0"
QUALITY_HASH_SCHEMA_VERSION = "1.0.0"
CANDIDATE_C_ACQUISITION_POLICY_IDENTIFIER = "candidate_c_acquisition_adequacy"
CANDIDATE_C_ACQUISITION_POLICY_VERSION = "1.0.0"
MINIMUM_ELAPSED_HISTORY_SECONDS = 365 * 24 * 60 * 60
MINIMUM_SOURCE_COVERAGE_RATIO = Decimal("0.995000000000000000")
FRESHNESS_POLICY_STATUS = "POLICY_UNAVAILABLE"
_DECIMAL_QUANTUM = Decimal("0.000000000000000001")


class HistoricalQualityError(ValueError):
    """Raised when freshness or adequacy cannot be proven."""


@dataclass(frozen=True, slots=True)
class AcquisitionAdequacyPolicy:
    identifier: str
    version: str
    minimum_elapsed_history_seconds: int
    minimum_source_coverage_ratio: Decimal


APPROVED_ACQUISITION_ADEQUACY_POLICY = AcquisitionAdequacyPolicy(
    identifier=CANDIDATE_C_ACQUISITION_POLICY_IDENTIFIER,
    version=CANDIDATE_C_ACQUISITION_POLICY_VERSION,
    minimum_elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS,
    minimum_source_coverage_ratio=MINIMUM_SOURCE_COVERAGE_RATIO,
)


@dataclass(frozen=True, slots=True)
class TimeframeQualityReport:
    timeframe: CandleTimeframe
    adequacy_status: str
    acquisition_outcome: str
    freshness_status: str
    source_snapshot_id: str | None
    source_snapshot_result_hash: str | None
    source_provenance_hash: str | None
    first_completed_timestamp: datetime | None
    last_completed_timestamp: datetime | None
    elapsed_history_seconds: int
    expected_candle_count: int
    observed_candle_count: int
    gap_count: int
    gap_timestamps: tuple[datetime, ...]
    coverage_ratio: Decimal
    provider_limited_start: datetime | None
    expected_latest_completed_timestamp: datetime
    latest_canonical_completed_at: datetime | None
    canonical_lag_seconds: int | None
    latest_retrieved_at: datetime | None
    retrieval_age_seconds: int | None
    unresolved_conflict_count: int
    validation_verified: bool
    provenance_verified: bool
    result_hash: str


@dataclass(frozen=True, slots=True)
class HistoricalQualityReport:
    schema_version: str
    hash_schema_version: str
    acquisition_policy_identifier: str
    acquisition_policy_version: str
    acquisition_policy_hash: str
    source_policy_identifier: str
    source_policy_version: str
    as_of: datetime
    freshness_policy_status: str
    publication_allowed: bool
    timeframes: tuple[
        TimeframeQualityReport,
        TimeframeQualityReport,
        TimeframeQualityReport,
    ]
    sources: tuple[
        CoverageSnapshotReference | None,
        CoverageSnapshotReference | None,
        CoverageSnapshotReference | None,
    ]
    source_provenance_hash: str
    result_hash: str


def build_historical_quality_report(
    *,
    as_of: datetime,
    five_minute: CoverageSnapshotReference | None,
    ten_minute: CoverageSnapshotReference | None,
    fifteen_minute: CoverageSnapshotReference | None,
    unresolved_conflict_counts: tuple[int, int, int] = (0, 0, 0),
    policy: AcquisitionAdequacyPolicy = APPROVED_ACQUISITION_ADEQUACY_POLICY,
) -> HistoricalQualityReport:
    """Build a fixed-order point-in-time report without freshness thresholds."""
    cutoff = _utc(as_of)
    _verify_policy(policy)
    if len(unresolved_conflict_counts) != 3 or any(
        value < 0 for value in unresolved_conflict_counts
    ):
        raise HistoricalQualityError(
            "Conflict counts must contain three nonnegative values."
        )
    references = (five_minute, ten_minute, fifteen_minute)
    timeframes = (
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    )
    reports = tuple(
        _build_timeframe_report(
            timeframe=timeframe,
            as_of=cutoff,
            reference=reference,
            unresolved_conflict_count=conflict_count,
            policy=policy,
        )
        for timeframe, reference, conflict_count in zip(
            timeframes,
            references,
            unresolved_conflict_counts,
            strict=True,
        )
    )
    policy_hash = _policy_hash(policy)
    provenance_hash = _sha256(
        {
            "hash_schema_version": QUALITY_HASH_SCHEMA_VERSION,
            "source_policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
            "source_policy_version": ACQUISITION_POLICY_VERSION,
            "timeframe_result_hashes": [item.result_hash for item in reports],
        }
    )
    result_hash = _sha256(
        {
            "schema_version": QUALITY_REPORT_SCHEMA_VERSION,
            "hash_schema_version": QUALITY_HASH_SCHEMA_VERSION,
            "acquisition_policy_hash": policy_hash,
            "as_of": _timestamp(cutoff),
            "freshness_policy_status": FRESHNESS_POLICY_STATUS,
            "publication_allowed": False,
            "source_provenance_hash": provenance_hash,
        }
    )
    return HistoricalQualityReport(
        schema_version=QUALITY_REPORT_SCHEMA_VERSION,
        hash_schema_version=QUALITY_HASH_SCHEMA_VERSION,
        acquisition_policy_identifier=policy.identifier,
        acquisition_policy_version=policy.version,
        acquisition_policy_hash=policy_hash,
        source_policy_identifier=ACQUISITION_POLICY_IDENTIFIER,
        source_policy_version=ACQUISITION_POLICY_VERSION,
        as_of=cutoff,
        freshness_policy_status=FRESHNESS_POLICY_STATUS,
        publication_allowed=False,
        timeframes=reports,  # type: ignore[arg-type]
        sources=references,
        source_provenance_hash=provenance_hash,
        result_hash=result_hash,
    )


def verify_historical_quality_report(report: HistoricalQualityReport) -> None:
    rebuilt = build_historical_quality_report(
        as_of=report.as_of,
        five_minute=report.sources[0],
        ten_minute=report.sources[1],
        fifteen_minute=report.sources[2],
        unresolved_conflict_counts=tuple(
            item.unresolved_conflict_count for item in report.timeframes
        ),
        policy=AcquisitionAdequacyPolicy(
            identifier=report.acquisition_policy_identifier,
            version=report.acquisition_policy_version,
            minimum_elapsed_history_seconds=MINIMUM_ELAPSED_HISTORY_SECONDS,
            minimum_source_coverage_ratio=MINIMUM_SOURCE_COVERAGE_RATIO,
        ),
    )
    if rebuilt != report:
        raise HistoricalQualityError(
            "Historical quality report integrity verification failed."
        )


def evaluate_acquisition_adequacy(
    *,
    elapsed_history_seconds: int,
    expected_candle_count: int,
    observed_candle_count: int,
    unresolved_conflict_count: int = 0,
    policy: AcquisitionAdequacyPolicy = APPROVED_ACQUISITION_ADEQUACY_POLICY,
) -> tuple[str, str, Decimal]:
    """Apply only the approved acquisition-layer Candidate C conditions."""
    _verify_policy(policy)
    if elapsed_history_seconds < 0 or unresolved_conflict_count < 0:
        raise HistoricalQualityError("Adequacy measurements cannot be negative.")
    if expected_candle_count == 0:
        if observed_candle_count != 0:
            raise HistoricalQualityError("Unavailable coverage counts are invalid.")
        return (
            ("UNAVAILABLE" if unresolved_conflict_count else "SOURCE_UNAVAILABLE"),
            (
                "UNRESOLVED_CONFLICT"
                if unresolved_conflict_count
                else "SOURCE_UNAVAILABLE"
            ),
            Decimal("0.000000000000000000"),
        )
    coverage_ratio = _ratio(observed_candle_count, expected_candle_count)
    if unresolved_conflict_count:
        return "UNAVAILABLE", "UNRESOLVED_CONFLICT", coverage_ratio
    if elapsed_history_seconds < policy.minimum_elapsed_history_seconds:
        return "INADEQUATE", "INADEQUATE_COVERAGE", coverage_ratio
    if coverage_ratio < policy.minimum_source_coverage_ratio:
        return "INADEQUATE", "INADEQUATE_CONTINUITY", coverage_ratio
    return (
        "ADEQUATE",
        "ADEQUATE_FOR_DOWNSTREAM_ADEQUACY_EVALUATION",
        coverage_ratio,
    )


def _build_timeframe_report(
    *,
    timeframe: CandleTimeframe,
    as_of: datetime,
    reference: CoverageSnapshotReference | None,
    unresolved_conflict_count: int,
    policy: AcquisitionAdequacyPolicy,
) -> TimeframeQualityReport:
    duration = timeframe_duration(timeframe)
    expected_latest = floor_timeframe_boundary(as_of, timeframe) - duration
    if reference is None:
        adequacy_status, outcome, coverage_ratio = evaluate_acquisition_adequacy(
            elapsed_history_seconds=0,
            expected_candle_count=0,
            observed_candle_count=0,
            unresolved_conflict_count=unresolved_conflict_count,
            policy=policy,
        )
        return _timeframe_report(
            timeframe=timeframe,
            adequacy_status=adequacy_status,
            acquisition_outcome=outcome,
            as_of=as_of,
            expected_latest=expected_latest,
            reference=None,
            elapsed_history_seconds=0,
            expected_candle_count=0,
            observed_candle_count=0,
            gap_timestamps=(),
            coverage_ratio=coverage_ratio,
            provider_limited_start=None,
            latest_canonical_completed_at=None,
            canonical_lag_seconds=None,
            latest_retrieved_at=None,
            retrieval_age_seconds=None,
            unresolved_conflict_count=unresolved_conflict_count,
        )

    snapshot = reference.snapshot
    verify_historical_coverage_snapshot(snapshot)
    if snapshot.timeframe is not timeframe:
        raise HistoricalQualityError(
            "Coverage reference does not match its report timeframe."
        )
    if (
        snapshot.acquisition_policy_identifier != ACQUISITION_POLICY_IDENTIFIER
        or snapshot.acquisition_policy_version != ACQUISITION_POLICY_VERSION
    ):
        raise HistoricalQualityError("Coverage source policy version is unsupported.")
    if any(batch.retrieved_at > as_of for batch in snapshot.batches):
        raise HistoricalQualityError(
            "Coverage contains retrieval evidence after the as-of cutoff."
        )
    if any(
        _utc(item.candle.timestamp) + duration > as_of for item in snapshot.observations
    ):
        raise HistoricalQualityError(
            "Coverage contains an incomplete candle at the as-of cutoff."
        )
    first = snapshot.coverage_range_start
    last = snapshot.coverage_range_end
    latest_completed_at = last + duration
    elapsed_seconds = int((latest_completed_at - first).total_seconds())
    adequacy_status, outcome, coverage_ratio = evaluate_acquisition_adequacy(
        elapsed_history_seconds=elapsed_seconds,
        expected_candle_count=snapshot.expected_candle_count,
        observed_candle_count=snapshot.observed_candle_count,
        unresolved_conflict_count=unresolved_conflict_count,
        policy=policy,
    )
    latest_retrieved = max(batch.retrieved_at for batch in snapshot.batches)
    retrieval_age = _seconds(as_of - latest_retrieved)
    canonical_lag = max(0, _seconds(expected_latest - last))
    provider_starts = tuple(
        batch.available_range_start or first
        for batch in snapshot.batches
        if batch.provider_limit_reached
    )
    provider_limited_start = min(provider_starts) if provider_starts else None

    return _timeframe_report(
        timeframe=timeframe,
        adequacy_status=adequacy_status,
        acquisition_outcome=outcome,
        as_of=as_of,
        expected_latest=expected_latest,
        reference=reference,
        elapsed_history_seconds=elapsed_seconds,
        expected_candle_count=snapshot.expected_candle_count,
        observed_candle_count=snapshot.observed_candle_count,
        gap_timestamps=snapshot.gap_timestamps,
        coverage_ratio=coverage_ratio,
        provider_limited_start=provider_limited_start,
        latest_canonical_completed_at=latest_completed_at,
        canonical_lag_seconds=canonical_lag,
        latest_retrieved_at=latest_retrieved,
        retrieval_age_seconds=retrieval_age,
        unresolved_conflict_count=unresolved_conflict_count,
    )


def _timeframe_report(
    *,
    timeframe: CandleTimeframe,
    adequacy_status: str,
    acquisition_outcome: str,
    as_of: datetime,
    expected_latest: datetime,
    reference: CoverageSnapshotReference | None,
    elapsed_history_seconds: int,
    expected_candle_count: int,
    observed_candle_count: int,
    gap_timestamps: tuple[datetime, ...],
    coverage_ratio: Decimal,
    provider_limited_start: datetime | None,
    latest_canonical_completed_at: datetime | None,
    canonical_lag_seconds: int | None,
    latest_retrieved_at: datetime | None,
    retrieval_age_seconds: int | None,
    unresolved_conflict_count: int,
) -> TimeframeQualityReport:
    snapshot = reference.snapshot if reference is not None else None
    payload = {
        "hash_schema_version": QUALITY_HASH_SCHEMA_VERSION,
        "timeframe": timeframe.value,
        "adequacy_status": adequacy_status,
        "acquisition_outcome": acquisition_outcome,
        "freshness_status": FRESHNESS_POLICY_STATUS,
        "source_snapshot_id": str(reference.snapshot_id) if reference else None,
        "source_snapshot_result_hash": snapshot.result_hash if snapshot else None,
        "source_provenance_hash": snapshot.source_provenance_hash if snapshot else None,
        "as_of": _timestamp(as_of),
        "first_completed_timestamp": (
            _timestamp(snapshot.coverage_range_start) if snapshot else None
        ),
        "last_completed_timestamp": (
            _timestamp(snapshot.coverage_range_end) if snapshot else None
        ),
        "elapsed_history_seconds": elapsed_history_seconds,
        "expected_candle_count": expected_candle_count,
        "observed_candle_count": observed_candle_count,
        "gap_timestamps": [_timestamp(item) for item in gap_timestamps],
        "coverage_ratio": _decimal(coverage_ratio),
        "provider_limited_start": (
            _timestamp(provider_limited_start)
            if provider_limited_start is not None
            else None
        ),
        "expected_latest_completed_timestamp": _timestamp(expected_latest),
        "latest_canonical_completed_at": (
            _timestamp(latest_canonical_completed_at)
            if latest_canonical_completed_at is not None
            else None
        ),
        "canonical_lag_seconds": canonical_lag_seconds,
        "latest_retrieved_at": (
            _timestamp(latest_retrieved_at) if latest_retrieved_at is not None else None
        ),
        "retrieval_age_seconds": retrieval_age_seconds,
        "unresolved_conflict_count": unresolved_conflict_count,
        "validation_verified": snapshot is not None,
        "provenance_verified": snapshot is not None,
    }
    return TimeframeQualityReport(
        timeframe=timeframe,
        adequacy_status=adequacy_status,
        acquisition_outcome=acquisition_outcome,
        freshness_status=FRESHNESS_POLICY_STATUS,
        source_snapshot_id=str(reference.snapshot_id) if reference else None,
        source_snapshot_result_hash=snapshot.result_hash if snapshot else None,
        source_provenance_hash=snapshot.source_provenance_hash if snapshot else None,
        first_completed_timestamp=snapshot.coverage_range_start if snapshot else None,
        last_completed_timestamp=snapshot.coverage_range_end if snapshot else None,
        elapsed_history_seconds=elapsed_history_seconds,
        expected_candle_count=expected_candle_count,
        observed_candle_count=observed_candle_count,
        gap_count=len(gap_timestamps),
        gap_timestamps=gap_timestamps,
        coverage_ratio=coverage_ratio,
        provider_limited_start=provider_limited_start,
        expected_latest_completed_timestamp=expected_latest,
        latest_canonical_completed_at=latest_canonical_completed_at,
        canonical_lag_seconds=canonical_lag_seconds,
        latest_retrieved_at=latest_retrieved_at,
        retrieval_age_seconds=retrieval_age_seconds,
        unresolved_conflict_count=unresolved_conflict_count,
        validation_verified=snapshot is not None,
        provenance_verified=snapshot is not None,
        result_hash=_sha256(payload),
    )


def _verify_policy(policy: AcquisitionAdequacyPolicy) -> None:
    if policy != APPROVED_ACQUISITION_ADEQUACY_POLICY:
        raise HistoricalQualityError(
            "Acquisition adequacy policy identifier, version, or values are unsupported."
        )


def _policy_hash(policy: AcquisitionAdequacyPolicy) -> str:
    return _sha256(
        {
            "hash_schema_version": QUALITY_HASH_SCHEMA_VERSION,
            "identifier": policy.identifier,
            "version": policy.version,
            "minimum_elapsed_history_seconds": policy.minimum_elapsed_history_seconds,
            "minimum_source_coverage_ratio": _decimal(
                policy.minimum_source_coverage_ratio
            ),
        }
    )


def _ratio(observed: int, expected: int) -> Decimal:
    if observed < 0 or expected <= 0 or observed > expected:
        raise HistoricalQualityError("Coverage counts are invalid.")
    with localcontext() as context:
        context.prec = 60
        return (Decimal(observed) / Decimal(expected)).quantize(
            _DECIMAL_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def _decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise HistoricalQualityError("Quality Decimal evidence must be finite.")
    return format(value.quantize(_DECIMAL_QUANTUM), "f")


def _seconds(value: timedelta) -> int:
    seconds = int(value.total_seconds())
    if seconds < 0:
        raise HistoricalQualityError(
            "Point-in-time freshness evidence cannot be negative."
        )
    return seconds


def _utc(value: datetime | None) -> datetime:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalQualityError("Quality timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
