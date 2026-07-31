"""Deterministic immutable historical coverage snapshot contracts."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from typing import Any, Mapping
from uuid import UUID

from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import (
    CandleValidationReport,
    timeframe_duration,
    validate_candles,
)


COVERAGE_SNAPSHOT_SCHEMA_VERSION = "1.0.0"
COVERAGE_HASH_SCHEMA_VERSION = "1.0.0"
ACQUISITION_POLICY_IDENTIFIER = "alphalens_v2_intraday_data_acquisition"
ACQUISITION_POLICY_VERSION = "1.0.0"
_DECIMAL_QUANTUM = Decimal("0.000000000000000001")
_SUPPORTED_TIMEFRAMES = frozenset(
    {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    }
)


class HistoricalCoverageError(ValueError):
    """Raised when canonical coverage evidence is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class CoverageObservation:
    candle_id: int
    ingestion_batch_id: UUID
    provider: str
    is_complete: bool
    candle: Candle


@dataclass(frozen=True, slots=True)
class CoverageBatchEvidence:
    ingestion_batch_id: UUID
    provider: str
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    requested_start: datetime
    requested_end_exclusive: datetime
    retrieved_at: datetime
    validation_passed: bool
    validation_issues: tuple[Mapping[str, Any], ...]
    source_timeframe: CandleTimeframe | None = None
    derivation_method: str | None = None
    source_ingestion_batch_id: UUID | None = None
    provider_limit_reached: bool = False
    available_range_start: datetime | None = None
    available_range_end: datetime | None = None


@dataclass(frozen=True, slots=True)
class CoverageBatchMembership:
    ingestion_batch_id: UUID
    candle_count: int
    source_subset_hash: str


@dataclass(frozen=True, slots=True)
class HistoricalCoverageSnapshot:
    schema_version: str
    hash_schema_version: str
    acquisition_policy_identifier: str
    acquisition_policy_version: str
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    requested_range_start: datetime
    requested_range_end_exclusive: datetime
    coverage_range_start: datetime
    coverage_range_end: datetime
    expected_candle_count: int
    observed_candle_count: int
    gap_count: int
    gap_timestamps: tuple[datetime, ...]
    source_batch_count: int
    validation_report: CandleValidationReport
    validation_hash: str
    source_data_hash: str
    source_provenance_hash: str
    result_hash: str
    observations: tuple[CoverageObservation, ...]
    batches: tuple[CoverageBatchEvidence, ...]
    batch_memberships: tuple[CoverageBatchMembership, ...]
    derivation_summary: tuple[Mapping[str, str], ...]


def build_historical_coverage_snapshot(
    *,
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
    observations: tuple[CoverageObservation, ...],
    batches: tuple[CoverageBatchEvidence, ...],
) -> HistoricalCoverageSnapshot:
    """Build a deterministic snapshot from canonical persisted evidence."""
    asset = asset_identifier.strip().upper()
    quote = quote_currency.strip().upper()
    if asset != "BTC" or quote != "USD":
        raise HistoricalCoverageError(
            "Historical coverage supports only BTC/USD."
        )
    if timeframe not in _SUPPORTED_TIMEFRAMES:
        raise HistoricalCoverageError(
            "Historical coverage supports only 5m, 10m, and 15m."
        )
    if not observations:
        raise HistoricalCoverageError(
            "Historical coverage requires at least one canonical candle."
        )

    _validate_observations(observations, timeframe)
    batch_by_id = _validate_batches(
        batches,
        asset_identifier=asset,
        quote_currency=quote,
        timeframe=timeframe,
    )
    referenced_batch_ids = {item.ingestion_batch_id for item in observations}
    if referenced_batch_ids != set(batch_by_id):
        raise HistoricalCoverageError(
            "Snapshot batch evidence must exactly match candle memberships."
        )

    candles = tuple(item.candle for item in observations)
    first_timestamp = _required_timestamp(candles[0].timestamp)
    last_timestamp = _required_timestamp(candles[-1].timestamp)
    duration = timeframe_duration(timeframe)
    validation_report = validate_candles(
        candles=candles,
        timeframe=timeframe,
        expected_start=first_timestamp,
        expected_end=last_timestamp + duration,
    )
    non_gap_issues = tuple(
        issue
        for issue in validation_report.issues
        if issue.code != "missing_candle"
    )
    if non_gap_issues:
        codes = ", ".join(issue.code for issue in non_gap_issues)
        raise HistoricalCoverageError(
            f"Canonical candle evidence failed validation: {codes}."
        )
    gap_timestamps = tuple(
        _required_timestamp(issue.timestamp)
        for issue in validation_report.issues
        if issue.code == "missing_candle"
    )
    expected_count = (
        int((last_timestamp - first_timestamp) / duration) + 1
    )
    if expected_count != len(observations) + len(gap_timestamps):
        raise HistoricalCoverageError(
            "Historical coverage counts are internally inconsistent."
        )

    ordered_batches = tuple(
        sorted(batches, key=lambda item: str(item.ingestion_batch_id))
    )
    batch_memberships = tuple(
        _batch_membership(batch.ingestion_batch_id, observations)
        for batch in ordered_batches
    )
    requested_start = min(item.requested_start for item in ordered_batches)
    requested_end = max(
        item.requested_end_exclusive for item in ordered_batches
    )
    derivation_summary = _derivation_summary(timeframe, ordered_batches)

    data_payload = {
        "hash_schema_version": COVERAGE_HASH_SCHEMA_VERSION,
        "asset_identifier": asset,
        "quote_currency": quote,
        "timeframe": timeframe.value,
        "candles": [
            _canonical_candle(item.candle) for item in observations
        ],
    }
    source_data_hash = _sha256(data_payload)
    validation_payload = {
        "hash_schema_version": COVERAGE_HASH_SCHEMA_VERSION,
        "validation_policy": "market_data_validation",
        "batches": [
            _canonical_batch_validation(item) for item in ordered_batches
        ],
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "timestamp": (
                    _canonical_timestamp(issue.timestamp)
                    if issue.timestamp is not None
                    else None
                ),
            }
            for issue in validation_report.issues
        ],
    }
    validation_hash = _sha256(validation_payload)
    provenance_payload = {
        "hash_schema_version": COVERAGE_HASH_SCHEMA_VERSION,
        "acquisition_policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
        "acquisition_policy_version": ACQUISITION_POLICY_VERSION,
        "source_batches": [
            _canonical_batch_provenance(item) for item in ordered_batches
        ],
        "observations": [
            {
                "candle_id": item.candle_id,
                "ingestion_batch_id": str(item.ingestion_batch_id),
                "provider": item.provider,
                "timestamp": _canonical_timestamp(item.candle.timestamp),
            }
            for item in observations
        ],
        "batch_memberships": [
            {
                "ingestion_batch_id": str(item.ingestion_batch_id),
                "candle_count": item.candle_count,
                "source_subset_hash": item.source_subset_hash,
            }
            for item in batch_memberships
        ],
        "derivation_summary": list(derivation_summary),
    }
    source_provenance_hash = _sha256(provenance_payload)
    result_payload = {
        "schema_version": COVERAGE_SNAPSHOT_SCHEMA_VERSION,
        "hash_schema_version": COVERAGE_HASH_SCHEMA_VERSION,
        "acquisition_policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
        "acquisition_policy_version": ACQUISITION_POLICY_VERSION,
        "asset_identifier": asset,
        "quote_currency": quote,
        "timeframe": timeframe.value,
        "requested_range_start": _canonical_timestamp(requested_start),
        "requested_range_end_exclusive": _canonical_timestamp(requested_end),
        "coverage_range_start": _canonical_timestamp(first_timestamp),
        "coverage_range_end": _canonical_timestamp(last_timestamp),
        "expected_candle_count": expected_count,
        "observed_candle_count": len(observations),
        "gap_timestamps": [
            _canonical_timestamp(value) for value in gap_timestamps
        ],
        "source_batch_count": len(ordered_batches),
        "validation_hash": validation_hash,
        "source_data_hash": source_data_hash,
        "source_provenance_hash": source_provenance_hash,
    }
    result_hash = _sha256(result_payload)

    return HistoricalCoverageSnapshot(
        schema_version=COVERAGE_SNAPSHOT_SCHEMA_VERSION,
        hash_schema_version=COVERAGE_HASH_SCHEMA_VERSION,
        acquisition_policy_identifier=ACQUISITION_POLICY_IDENTIFIER,
        acquisition_policy_version=ACQUISITION_POLICY_VERSION,
        asset_identifier=asset,
        quote_currency=quote,
        timeframe=timeframe,
        requested_range_start=requested_start,
        requested_range_end_exclusive=requested_end,
        coverage_range_start=first_timestamp,
        coverage_range_end=last_timestamp,
        expected_candle_count=expected_count,
        observed_candle_count=len(observations),
        gap_count=len(gap_timestamps),
        gap_timestamps=gap_timestamps,
        source_batch_count=len(ordered_batches),
        validation_report=validation_report,
        validation_hash=validation_hash,
        source_data_hash=source_data_hash,
        source_provenance_hash=source_provenance_hash,
        result_hash=result_hash,
        observations=observations,
        batches=ordered_batches,
        batch_memberships=batch_memberships,
        derivation_summary=derivation_summary,
    )


def verify_historical_coverage_snapshot(
    snapshot: HistoricalCoverageSnapshot,
) -> None:
    """Rebuild a snapshot and verify every semantic field and hash."""
    rebuilt = build_historical_coverage_snapshot(
        asset_identifier=snapshot.asset_identifier,
        quote_currency=snapshot.quote_currency,
        timeframe=snapshot.timeframe,
        observations=snapshot.observations,
        batches=snapshot.batches,
    )
    if rebuilt != snapshot:
        raise HistoricalCoverageError(
            "Historical coverage snapshot integrity verification failed."
        )


def _validate_observations(
    observations: tuple[CoverageObservation, ...],
    timeframe: CandleTimeframe,
) -> None:
    prior: datetime | None = None
    seen_ids: set[int] = set()
    seen_timestamps: set[datetime] = set()
    for item in observations:
        if item.candle_id <= 0 or item.candle_id in seen_ids:
            raise HistoricalCoverageError(
                "Coverage candle identities must be unique and positive."
            )
        if item.provider != "kraken":
            raise HistoricalCoverageError(
                "Coverage evidence must use the approved Kraken source."
            )
        if not item.is_complete:
            raise HistoricalCoverageError(
                "Incomplete candles cannot enter a coverage snapshot."
            )
        timestamp = _required_timestamp(item.candle.timestamp)
        if timestamp in seen_timestamps:
            raise HistoricalCoverageError(
                "Coverage candle timestamps must be unique."
            )
        if prior is not None and timestamp <= prior:
            raise HistoricalCoverageError(
                "Coverage candles must be strictly chronological."
            )
        seen_ids.add(item.candle_id)
        seen_timestamps.add(timestamp)
        prior = timestamp
        _canonical_candle(item.candle)


def _validate_batches(
    batches: tuple[CoverageBatchEvidence, ...],
    *,
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
) -> dict[UUID, CoverageBatchEvidence]:
    if not batches:
        raise HistoricalCoverageError(
            "Coverage snapshot requires source batch evidence."
        )
    batch_by_id: dict[UUID, CoverageBatchEvidence] = {}
    for batch in batches:
        if batch.ingestion_batch_id in batch_by_id:
            raise HistoricalCoverageError(
                "Coverage source batch identities must be unique."
            )
        if (
            batch.provider != "kraken"
            or batch.asset_identifier != asset_identifier
            or batch.quote_currency != quote_currency
            or batch.timeframe is not timeframe
        ):
            raise HistoricalCoverageError(
                "Coverage source batch scope is incompatible."
            )
        if not batch.validation_passed:
            raise HistoricalCoverageError(
                "Canonical coverage cannot reference a failed source batch."
            )
        _canonical_timestamp(batch.requested_start)
        _canonical_timestamp(batch.requested_end_exclusive)
        _canonical_timestamp(batch.retrieved_at)
        if batch.requested_start >= batch.requested_end_exclusive:
            raise HistoricalCoverageError(
                "Coverage source batch range is invalid."
            )
        derivation = (
            batch.source_timeframe,
            batch.derivation_method,
            batch.source_ingestion_batch_id,
        )
        if any(value is not None for value in derivation) != all(
            value is not None for value in derivation
        ):
            raise HistoricalCoverageError(
                "Coverage derivation provenance must be complete."
            )
        if timeframe is CandleTimeframe.MINUTE_10:
            if (
                batch.source_timeframe is not CandleTimeframe.MINUTE_5
                or batch.derivation_method is None
                or batch.source_ingestion_batch_id is None
            ):
                raise HistoricalCoverageError(
                    "10m coverage requires verified 5m derivation evidence."
                )
        elif any(value is not None for value in derivation):
            raise HistoricalCoverageError(
                "Native coverage cannot contain derivation provenance."
            )
        batch_by_id[batch.ingestion_batch_id] = batch
    return batch_by_id


def _batch_membership(
    batch_id: UUID,
    observations: tuple[CoverageObservation, ...],
) -> CoverageBatchMembership:
    members = tuple(
        item for item in observations if item.ingestion_batch_id == batch_id
    )
    if not members:
        raise HistoricalCoverageError(
            "Coverage source batch has no candle memberships."
        )
    payload = {
        "hash_schema_version": COVERAGE_HASH_SCHEMA_VERSION,
        "ingestion_batch_id": str(batch_id),
        "members": [
            {
                "ordinal": index,
                "candle_id": item.candle_id,
                "timestamp": _canonical_timestamp(item.candle.timestamp),
                "candle": _canonical_candle(item.candle),
            }
            for index, item in enumerate(members)
        ],
    }
    return CoverageBatchMembership(
        ingestion_batch_id=batch_id,
        candle_count=len(members),
        source_subset_hash=_sha256(payload),
    )


def _derivation_summary(
    timeframe: CandleTimeframe,
    batches: tuple[CoverageBatchEvidence, ...],
) -> tuple[Mapping[str, str], ...]:
    if timeframe is not CandleTimeframe.MINUTE_10:
        return ()
    return tuple(
        {
            "ingestion_batch_id": str(batch.ingestion_batch_id),
            "source_timeframe": _required_timeframe(
                batch.source_timeframe
            ).value,
            "derivation_method": _required_string(
                batch.derivation_method
            ),
            "source_ingestion_batch_id": str(
                _required_uuid(batch.source_ingestion_batch_id)
            ),
        }
        for batch in batches
    )


def _canonical_batch_validation(
    batch: CoverageBatchEvidence,
) -> dict[str, Any]:
    issues = sorted(
        (_canonical_mapping(value) for value in batch.validation_issues),
        key=lambda value: json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ),
    )
    return {
        "ingestion_batch_id": str(batch.ingestion_batch_id),
        "provider": batch.provider,
        "requested_start": _canonical_timestamp(batch.requested_start),
        "requested_end_exclusive": _canonical_timestamp(
            batch.requested_end_exclusive
        ),
        "retrieved_at": _canonical_timestamp(batch.retrieved_at),
        "validation_passed": batch.validation_passed,
        "validation_issues": issues,
    }


def _canonical_batch_provenance(
    batch: CoverageBatchEvidence,
) -> dict[str, Any]:
    return {
        "ingestion_batch_id": str(batch.ingestion_batch_id),
        "provider": batch.provider,
        "asset_identifier": batch.asset_identifier,
        "quote_currency": batch.quote_currency,
        "timeframe": batch.timeframe.value,
        "requested_start": _canonical_timestamp(batch.requested_start),
        "requested_end_exclusive": _canonical_timestamp(
            batch.requested_end_exclusive
        ),
        "retrieved_at": _canonical_timestamp(batch.retrieved_at),
        "source_timeframe": (
            batch.source_timeframe.value
            if batch.source_timeframe is not None
            else None
        ),
        "derivation_method": batch.derivation_method,
        "source_ingestion_batch_id": (
            str(batch.source_ingestion_batch_id)
            if batch.source_ingestion_batch_id is not None
            else None
        ),
    }


def _canonical_candle(candle: Candle) -> dict[str, str]:
    return {
        "timestamp": _canonical_timestamp(candle.timestamp),
        "open": _canonical_decimal(candle.open),
        "high": _canonical_decimal(candle.high),
        "low": _canonical_decimal(candle.low),
        "close": _canonical_decimal(candle.close),
        "volume": _canonical_decimal(candle.volume),
    }


def _canonical_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _canonical_value(item)
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
    }


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _canonical_timestamp(value)
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return _canonical_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise HistoricalCoverageError(
        "Coverage validation evidence contains an unsupported value."
    )


def _canonical_timestamp(value: datetime | None) -> str:
    timestamp = _required_timestamp(value)
    return timestamp.astimezone(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _canonical_decimal(value: Decimal | None) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise HistoricalCoverageError(
            "Coverage candle values must be finite Decimal values."
        )
    with localcontext() as context:
        context.prec = 50
        quantized = value.quantize(
            _DECIMAL_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )
    return format(quantized, "f")


def _required_timestamp(value: datetime | None) -> datetime:
    if (
        value is None
        or value.tzinfo is None
        or value.utcoffset() != timedelta(0)
    ):
        raise HistoricalCoverageError(
            "Coverage timestamps must be timezone-aware UTC."
        )
    return value


def _required_timeframe(
    value: CandleTimeframe | None,
) -> CandleTimeframe:
    if value is None:
        raise HistoricalCoverageError(
            "Coverage source timeframe is missing."
        )
    return value


def _required_uuid(value: UUID | None) -> UUID:
    if value is None:
        raise HistoricalCoverageError(
            "Coverage source batch identity is missing."
        )
    return value


def _required_string(value: str | None) -> str:
    if not value:
        raise HistoricalCoverageError(
            "Coverage derivation method is missing."
        )
    return value


def _sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
