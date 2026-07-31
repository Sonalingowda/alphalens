"""Deterministic 5m, derived 10m, and native 15m synchronization."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID

from app.market_data.conflicts import candle_evidence_hash
from app.market_data.coverage import (
    HistoricalCoverageSnapshot,
    verify_historical_coverage_snapshot,
)
from app.market_data.history import (
    TEN_MINUTE_DERIVATION,
    aggregate_btc_usd_10m_candle,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import timeframe_duration


SYNCHRONIZATION_SCHEMA_VERSION = "1.0.0"
SYNCHRONIZATION_HASH_SCHEMA_VERSION = "1.0.0"


class HistoricalSynchronizationError(ValueError):
    """Raised when cross-timeframe synchronization cannot be proven."""


@dataclass(frozen=True, slots=True)
class CoverageSnapshotReference:
    snapshot_id: UUID
    snapshot: HistoricalCoverageSnapshot


@dataclass(frozen=True, slots=True)
class TenMinuteSourceMember:
    ordinal: int
    candle_id: int
    ingestion_batch_id: UUID
    available_at: datetime
    candle_hash: str
    candle: Candle


@dataclass(frozen=True, slots=True)
class TenMinuteDerivationEvidence:
    derived_candle_id: int
    derived_ingestion_batch_id: UUID
    derivation_method: str
    available_at: datetime
    derived_candle_hash: str
    source_membership_hash: str
    result_hash: str
    derived_candle: Candle
    source_members: tuple[TenMinuteSourceMember, TenMinuteSourceMember]


@dataclass(frozen=True, slots=True)
class SynchronizationDifferences:
    unpaired_five_minute_timestamps: tuple[datetime, ...]
    missing_native_fifteen_minute_timestamps: tuple[datetime, ...]
    native_fifteen_minute_without_complete_five_minute: tuple[datetime, ...]


@dataclass(frozen=True, slots=True)
class SynchronizedCoverageSnapshot:
    schema_version: str
    hash_schema_version: str
    asset_identifier: str
    quote_currency: str
    as_of: datetime
    five_minute: CoverageSnapshotReference
    ten_minute: CoverageSnapshotReference
    fifteen_minute: CoverageSnapshotReference
    derivations: tuple[TenMinuteDerivationEvidence, ...]
    differences: SynchronizationDifferences
    source_provenance_hash: str
    result_hash: str


def build_ten_minute_derivation_evidence(
    *,
    derived_candle_id: int,
    derived_ingestion_batch_id: UUID,
    derived_candle: Candle,
    first_source_candle_id: int,
    first_source_ingestion_batch_id: UUID,
    first_source_candle: Candle,
    first_source_available_at: datetime,
    second_source_candle_id: int,
    second_source_ingestion_batch_id: UUID,
    second_source_candle: Candle,
    second_source_available_at: datetime,
    derived_available_at: datetime,
    derivation_method: str = TEN_MINUTE_DERIVATION,
) -> TenMinuteDerivationEvidence:
    """Build and verify immutable provenance for one canonical 10m candle."""
    if (
        derived_candle_id <= 0
        or first_source_candle_id <= 0
        or second_source_candle_id <= 0
    ):
        raise HistoricalSynchronizationError("Candle identities must be positive.")
    if derivation_method != TEN_MINUTE_DERIVATION:
        raise HistoricalSynchronizationError(
            "The 10m derivation method is not approved."
        )

    derived_timestamp = _timestamp(derived_candle)
    first_timestamp = _timestamp(first_source_candle)
    second_timestamp = _timestamp(second_source_candle)
    if (
        first_timestamp != derived_timestamp
        or second_timestamp != derived_timestamp + timedelta(minutes=5)
        or derived_timestamp.minute % 10 != 0
    ):
        raise HistoricalSynchronizationError(
            "10m evidence requires two adjacent UTC-aligned 5m members."
        )
    expected = aggregate_btc_usd_10m_candle(
        first_source_candle,
        second_source_candle,
        derived_timestamp,
    )
    if expected != derived_candle:
        raise HistoricalSynchronizationError(
            "Canonical 10m values do not match their exact 5m members."
        )

    first_available = _utc(first_source_available_at)
    second_available = _utc(second_source_available_at)
    available_at = _utc(derived_available_at)
    minimum_available = max(first_available, second_available)
    if available_at < minimum_available:
        raise HistoricalSynchronizationError(
            "10m evidence cannot be available before both source members."
        )

    members = (
        TenMinuteSourceMember(
            ordinal=0,
            candle_id=first_source_candle_id,
            ingestion_batch_id=first_source_ingestion_batch_id,
            available_at=first_available,
            candle_hash=candle_evidence_hash(first_source_candle),
            candle=first_source_candle,
        ),
        TenMinuteSourceMember(
            ordinal=1,
            candle_id=second_source_candle_id,
            ingestion_batch_id=second_source_ingestion_batch_id,
            available_at=second_available,
            candle_hash=candle_evidence_hash(second_source_candle),
            candle=second_source_candle,
        ),
    )
    membership_payload = {
        "hash_schema_version": SYNCHRONIZATION_HASH_SCHEMA_VERSION,
        "derived_candle_id": derived_candle_id,
        "members": [_canonical_member(member) for member in members],
    }
    source_membership_hash = _sha256(membership_payload)
    derived_hash = candle_evidence_hash(derived_candle)
    result_hash = _sha256(
        {
            "schema_version": SYNCHRONIZATION_SCHEMA_VERSION,
            "hash_schema_version": SYNCHRONIZATION_HASH_SCHEMA_VERSION,
            "derived_candle_id": derived_candle_id,
            "derived_ingestion_batch_id": str(derived_ingestion_batch_id),
            "derivation_method": derivation_method,
            "available_at": _canonical_timestamp(available_at),
            "derived_candle_hash": derived_hash,
            "source_membership_hash": source_membership_hash,
        }
    )
    return TenMinuteDerivationEvidence(
        derived_candle_id=derived_candle_id,
        derived_ingestion_batch_id=derived_ingestion_batch_id,
        derivation_method=derivation_method,
        available_at=available_at,
        derived_candle_hash=derived_hash,
        source_membership_hash=source_membership_hash,
        result_hash=result_hash,
        derived_candle=derived_candle,
        source_members=members,
    )


def verify_ten_minute_derivation_evidence(
    evidence: TenMinuteDerivationEvidence,
) -> None:
    rebuilt = build_ten_minute_derivation_evidence(
        derived_candle_id=evidence.derived_candle_id,
        derived_ingestion_batch_id=evidence.derived_ingestion_batch_id,
        derived_candle=evidence.derived_candle,
        first_source_candle_id=evidence.source_members[0].candle_id,
        first_source_ingestion_batch_id=evidence.source_members[0].ingestion_batch_id,
        first_source_candle=evidence.source_members[0].candle,
        first_source_available_at=evidence.source_members[0].available_at,
        second_source_candle_id=evidence.source_members[1].candle_id,
        second_source_ingestion_batch_id=evidence.source_members[1].ingestion_batch_id,
        second_source_candle=evidence.source_members[1].candle,
        second_source_available_at=evidence.source_members[1].available_at,
        derived_available_at=evidence.available_at,
        derivation_method=evidence.derivation_method,
    )
    if rebuilt != evidence:
        raise HistoricalSynchronizationError(
            "10m derivation evidence integrity verification failed."
        )


def build_synchronized_coverage_snapshot(
    *,
    as_of: datetime,
    five_minute: CoverageSnapshotReference,
    ten_minute: CoverageSnapshotReference,
    fifteen_minute: CoverageSnapshotReference,
    derivations: tuple[TenMinuteDerivationEvidence, ...],
) -> SynchronizedCoverageSnapshot:
    """Prove and hash one point-in-time three-timeframe membership set."""
    cutoff = _utc(as_of)
    references = (five_minute, ten_minute, fifteen_minute)
    expected_timeframes = (
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    )
    for reference, timeframe in zip(references, expected_timeframes, strict=True):
        verify_historical_coverage_snapshot(reference.snapshot)
        if reference.snapshot.timeframe is not timeframe:
            raise HistoricalSynchronizationError(
                "Coverage snapshots are not in deterministic 5m/10m/15m order."
            )
        if any(batch.retrieved_at > cutoff for batch in reference.snapshot.batches):
            raise HistoricalSynchronizationError(
                "Coverage contains evidence unavailable at the as-of cutoff."
            )
        duration = timeframe_duration(timeframe)
        if any(
            _timestamp(item.candle) + duration > cutoff
            for item in reference.snapshot.observations
        ):
            raise HistoricalSynchronizationError(
                "Coverage contains an incomplete interval at the as-of cutoff."
            )
    if any(
        reference.snapshot.asset_identifier != "BTC"
        or reference.snapshot.quote_currency != "USD"
        for reference in references
    ):
        raise HistoricalSynchronizationError("Synchronization supports only BTC/USD.")

    five_by_id = {item.candle_id: item for item in five_minute.snapshot.observations}
    five_by_timestamp = {
        _timestamp(item.candle): item for item in five_minute.snapshot.observations
    }
    ten_by_id = {item.candle_id: item for item in ten_minute.snapshot.observations}
    ten_by_timestamp = {
        _timestamp(item.candle): item for item in ten_minute.snapshot.observations
    }
    derivation_by_id: dict[int, TenMinuteDerivationEvidence] = {}
    referenced_five_ids: set[int] = set()
    for evidence in derivations:
        verify_ten_minute_derivation_evidence(evidence)
        if evidence.derived_candle_id in derivation_by_id:
            raise HistoricalSynchronizationError(
                "10m derivation identities must be unique."
            )
        derived = ten_by_id.get(evidence.derived_candle_id)
        if derived is None or derived.candle != evidence.derived_candle:
            raise HistoricalSynchronizationError(
                "10m derivation evidence is outside the 10m coverage snapshot."
            )
        for member in evidence.source_members:
            source = five_by_id.get(member.candle_id)
            if (
                source is None
                or source.ingestion_batch_id != member.ingestion_batch_id
                or source.candle != member.candle
            ):
                raise HistoricalSynchronizationError(
                    "10m source membership does not match 5m coverage evidence."
                )
            referenced_five_ids.add(member.candle_id)
        if evidence.available_at > cutoff:
            raise HistoricalSynchronizationError(
                "10m derivation was unavailable at the as-of cutoff."
            )
        derivation_by_id[evidence.derived_candle_id] = evidence
    if set(ten_by_id) != set(derivation_by_id):
        raise HistoricalSynchronizationError(
            "Every synchronized 10m candle requires exact two-candle provenance."
        )

    derivable_timestamps = {
        timestamp
        for timestamp in five_by_timestamp
        if timestamp.minute % 10 == 0
        and timestamp + timedelta(minutes=5) in five_by_timestamp
    }
    if derivable_timestamps != set(ten_by_timestamp):
        raise HistoricalSynchronizationError(
            "10m coverage diverges from complete canonical 5m pairs."
        )

    unpaired = tuple(
        _timestamp(item.candle)
        for item in five_minute.snapshot.observations
        if item.candle_id not in referenced_five_ids
    )
    complete_fifteen_buckets = {
        timestamp
        for timestamp in five_by_timestamp
        if timestamp.minute % 15 == 0
        and timestamp + timedelta(minutes=5) in five_by_timestamp
        and timestamp + timedelta(minutes=10) in five_by_timestamp
    }
    native_fifteen = {
        _timestamp(item.candle) for item in fifteen_minute.snapshot.observations
    }
    differences = SynchronizationDifferences(
        unpaired_five_minute_timestamps=unpaired,
        missing_native_fifteen_minute_timestamps=tuple(
            sorted(complete_fifteen_buckets - native_fifteen)
        ),
        native_fifteen_minute_without_complete_five_minute=tuple(
            sorted(native_fifteen - complete_fifteen_buckets)
        ),
    )
    ordered_derivations = tuple(
        sorted(derivations, key=lambda item: _timestamp(item.derived_candle))
    )
    provenance_payload = {
        "hash_schema_version": SYNCHRONIZATION_HASH_SCHEMA_VERSION,
        "coverage_result_hashes": [
            reference.snapshot.result_hash for reference in references
        ],
        "derivation_result_hashes": [item.result_hash for item in ordered_derivations],
    }
    provenance_hash = _sha256(provenance_payload)
    result_hash = _sha256(
        {
            "schema_version": SYNCHRONIZATION_SCHEMA_VERSION,
            "hash_schema_version": SYNCHRONIZATION_HASH_SCHEMA_VERSION,
            "asset_identifier": "BTC",
            "quote_currency": "USD",
            "as_of": _canonical_timestamp(cutoff),
            "source_provenance_hash": provenance_hash,
            "differences": _canonical_differences(differences),
        }
    )
    return SynchronizedCoverageSnapshot(
        schema_version=SYNCHRONIZATION_SCHEMA_VERSION,
        hash_schema_version=SYNCHRONIZATION_HASH_SCHEMA_VERSION,
        asset_identifier="BTC",
        quote_currency="USD",
        as_of=cutoff,
        five_minute=five_minute,
        ten_minute=ten_minute,
        fifteen_minute=fifteen_minute,
        derivations=ordered_derivations,
        differences=differences,
        source_provenance_hash=provenance_hash,
        result_hash=result_hash,
    )


def verify_synchronized_coverage_snapshot(
    snapshot: SynchronizedCoverageSnapshot,
) -> None:
    rebuilt = build_synchronized_coverage_snapshot(
        as_of=snapshot.as_of,
        five_minute=snapshot.five_minute,
        ten_minute=snapshot.ten_minute,
        fifteen_minute=snapshot.fifteen_minute,
        derivations=snapshot.derivations,
    )
    if rebuilt != snapshot:
        raise HistoricalSynchronizationError(
            "Synchronized coverage integrity verification failed."
        )


def _canonical_member(member: TenMinuteSourceMember) -> dict[str, object]:
    return {
        "ordinal": member.ordinal,
        "candle_id": member.candle_id,
        "ingestion_batch_id": str(member.ingestion_batch_id),
        "available_at": _canonical_timestamp(member.available_at),
        "candle_hash": member.candle_hash,
    }


def _canonical_differences(value: SynchronizationDifferences) -> dict[str, list[str]]:
    return {
        "unpaired_five_minute_timestamps": [
            _canonical_timestamp(item) for item in value.unpaired_five_minute_timestamps
        ],
        "missing_native_fifteen_minute_timestamps": [
            _canonical_timestamp(item)
            for item in value.missing_native_fifteen_minute_timestamps
        ],
        "native_fifteen_minute_without_complete_five_minute": [
            _canonical_timestamp(item)
            for item in value.native_fifteen_minute_without_complete_five_minute
        ],
    }


def _timestamp(candle: Candle) -> datetime:
    if candle.timestamp is None:
        raise HistoricalSynchronizationError("Candle timestamp is missing.")
    return _utc(candle.timestamp)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalSynchronizationError(
            "Synchronization timestamps must be aware."
        )
    return value.astimezone(timezone.utc)


def _canonical_timestamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
