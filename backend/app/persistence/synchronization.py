"""Persistence for exact 10m provenance and synchronized coverage."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.coverage import HistoricalCoverageSnapshot
from app.market_data.history import TEN_MINUTE_DERIVATION
from app.market_data.models import CandleTimeframe
from app.market_data.synchronization import (
    HistoricalSynchronizationError,
    SynchronizedCoverageSnapshot,
    SynchronizationDifferences,
    TenMinuteDerivationEvidence,
    build_ten_minute_derivation_evidence,
    verify_synchronized_coverage_snapshot,
    verify_ten_minute_derivation_evidence,
)
from app.persistence.models import (
    SynchronizedCoverageSnapshotRecord,
    TenMinuteDerivationRecord,
    TenMinuteDerivationSourceRecord,
)


@dataclass(frozen=True, slots=True)
class SynchronizedCoveragePersistenceResult:
    synchronization_id: UUID
    result_hash: str
    derivation_count: int
    reused: bool


def build_derivations_from_coverage(
    five_minute: HistoricalCoverageSnapshot,
    ten_minute: HistoricalCoverageSnapshot,
) -> tuple[TenMinuteDerivationEvidence, ...]:
    """Resolve every 10m observation to exact canonical 5m members."""
    if (
        five_minute.timeframe is not CandleTimeframe.MINUTE_5
        or ten_minute.timeframe is not CandleTimeframe.MINUTE_10
    ):
        raise HistoricalSynchronizationError(
            "Derivation provenance requires 5m and 10m coverage."
        )
    five_by_timestamp = {
        item.candle.timestamp: item for item in five_minute.observations
    }
    five_batches = {item.ingestion_batch_id: item for item in five_minute.batches}
    ten_batches = {item.ingestion_batch_id: item for item in ten_minute.batches}
    evidence: list[TenMinuteDerivationEvidence] = []
    for derived in ten_minute.observations:
        timestamp = derived.candle.timestamp
        if timestamp is None:
            raise HistoricalSynchronizationError("Canonical 10m timestamp is missing.")
        first = five_by_timestamp.get(timestamp)
        second = five_by_timestamp.get(timestamp + timedelta(minutes=5))
        if first is None or second is None:
            raise HistoricalSynchronizationError(
                "Canonical 10m candle is missing an exact 5m member."
            )
        first_batch = five_batches[first.ingestion_batch_id]
        second_batch = five_batches[second.ingestion_batch_id]
        derived_batch = ten_batches[derived.ingestion_batch_id]
        if (
            derived_batch.source_timeframe is not CandleTimeframe.MINUTE_5
            or derived_batch.derivation_method != TEN_MINUTE_DERIVATION
            or derived_batch.source_ingestion_batch_id is None
        ):
            raise HistoricalSynchronizationError(
                "Canonical 10m batch derivation provenance is incomplete."
            )
        first_available = max(
            first_batch.retrieved_at,
            timestamp + timedelta(minutes=5),
        )
        second_available = max(
            second_batch.retrieved_at,
            timestamp + timedelta(minutes=10),
        )
        derived_available = max(
            first_available,
            second_available,
            derived_batch.retrieved_at,
            timestamp + timedelta(minutes=10),
        )
        evidence.append(
            build_ten_minute_derivation_evidence(
                derived_candle_id=derived.candle_id,
                derived_ingestion_batch_id=derived.ingestion_batch_id,
                derived_candle=derived.candle,
                first_source_candle_id=first.candle_id,
                first_source_ingestion_batch_id=first.ingestion_batch_id,
                first_source_candle=first.candle,
                first_source_available_at=first_available,
                second_source_candle_id=second.candle_id,
                second_source_ingestion_batch_id=second.ingestion_batch_id,
                second_source_candle=second.candle,
                second_source_available_at=second_available,
                derived_available_at=derived_available,
                derivation_method=derived_batch.derivation_method,
            )
        )
    return tuple(evidence)


async def persist_ten_minute_derivations(
    session: AsyncSession,
    derivations: tuple[TenMinuteDerivationEvidence, ...],
) -> None:
    """Insert exact memberships once and verify every repeated execution."""
    for evidence in derivations:
        verify_ten_minute_derivation_evidence(evidence)
    async with session.begin():
        for evidence in derivations:
            existing = await session.get(
                TenMinuteDerivationRecord,
                evidence.derived_candle_id,
            )
            if existing is None:
                session.add(_derivation_record(evidence))
                session.add_all(
                    [
                        TenMinuteDerivationSourceRecord(
                            derived_candle_id=evidence.derived_candle_id,
                            ordinal=member.ordinal,
                            source_candle_id=member.candle_id,
                            source_ingestion_batch_id=member.ingestion_batch_id,
                            source_available_at=member.available_at,
                            source_candle_hash=member.candle_hash,
                        )
                        for member in evidence.source_members
                    ]
                )
                continue
            sources = tuple(
                (
                    await session.scalars(
                        select(TenMinuteDerivationSourceRecord)
                        .where(
                            TenMinuteDerivationSourceRecord.derived_candle_id
                            == evidence.derived_candle_id
                        )
                        .order_by(TenMinuteDerivationSourceRecord.ordinal)
                    )
                ).all()
            )
            _verify_stored_derivation(existing, sources, evidence)


async def persist_synchronized_coverage_snapshot(
    session: AsyncSession,
    snapshot: SynchronizedCoverageSnapshot,
) -> SynchronizedCoveragePersistenceResult:
    """Persist one semantic synchronization result idempotently."""
    verify_synchronized_coverage_snapshot(snapshot)
    async with session.begin():
        existing = await session.scalar(
            select(SynchronizedCoverageSnapshotRecord).where(
                SynchronizedCoverageSnapshotRecord.result_hash == snapshot.result_hash
            )
        )
        if existing is not None:
            _verify_stored_synchronization(existing, snapshot)
            return _result(existing.id, snapshot, reused=True)
        synchronization_id = uuid4()
        session.add(_synchronization_record(synchronization_id, snapshot))
        await session.flush()
    return _result(synchronization_id, snapshot, reused=False)


def _derivation_record(
    evidence: TenMinuteDerivationEvidence,
) -> TenMinuteDerivationRecord:
    return TenMinuteDerivationRecord(
        derived_candle_id=evidence.derived_candle_id,
        derived_ingestion_batch_id=evidence.derived_ingestion_batch_id,
        derivation_method=evidence.derivation_method,
        available_at=evidence.available_at,
        derived_candle_hash=evidence.derived_candle_hash,
        source_membership_hash=evidence.source_membership_hash,
        result_hash=evidence.result_hash,
        immutable=True,
    )


def _verify_stored_derivation(
    record: TenMinuteDerivationRecord,
    sources: tuple[TenMinuteDerivationSourceRecord, ...],
    evidence: TenMinuteDerivationEvidence,
) -> None:
    expected_record = {
        "derived_ingestion_batch_id": evidence.derived_ingestion_batch_id,
        "derivation_method": evidence.derivation_method,
        "available_at": evidence.available_at,
        "derived_candle_hash": evidence.derived_candle_hash,
        "source_membership_hash": evidence.source_membership_hash,
        "result_hash": evidence.result_hash,
        "immutable": True,
    }
    expected_sources = tuple(
        (
            member.ordinal,
            member.candle_id,
            member.ingestion_batch_id,
            member.available_at,
            member.candle_hash,
        )
        for member in evidence.source_members
    )
    stored_sources = tuple(
        (
            source.ordinal,
            source.source_candle_id,
            source.source_ingestion_batch_id,
            source.source_available_at,
            source.source_candle_hash,
        )
        for source in sources
    )
    if (
        any(getattr(record, name) != value for name, value in expected_record.items())
        or stored_sources != expected_sources
    ):
        raise HistoricalSynchronizationError(
            "Stored 10m derivation evidence conflicts with canonical provenance."
        )


def _synchronization_record(
    synchronization_id: UUID,
    snapshot: SynchronizedCoverageSnapshot,
) -> SynchronizedCoverageSnapshotRecord:
    return SynchronizedCoverageSnapshotRecord(
        id=synchronization_id,
        schema_version=snapshot.schema_version,
        hash_schema_version=snapshot.hash_schema_version,
        asset_identifier=snapshot.asset_identifier,
        quote_currency=snapshot.quote_currency,
        as_of=snapshot.as_of,
        five_minute_snapshot_id=snapshot.five_minute.snapshot_id,
        ten_minute_snapshot_id=snapshot.ten_minute.snapshot_id,
        fifteen_minute_snapshot_id=snapshot.fifteen_minute.snapshot_id,
        derivation_count=len(snapshot.derivations),
        differences=_differences(snapshot.differences),
        source_provenance_hash=snapshot.source_provenance_hash,
        result_hash=snapshot.result_hash,
        immutable=True,
    )


def _verify_stored_synchronization(
    record: SynchronizedCoverageSnapshotRecord,
    snapshot: SynchronizedCoverageSnapshot,
) -> None:
    expected: dict[str, Any] = {
        "schema_version": snapshot.schema_version,
        "hash_schema_version": snapshot.hash_schema_version,
        "asset_identifier": snapshot.asset_identifier,
        "quote_currency": snapshot.quote_currency,
        "as_of": snapshot.as_of,
        "five_minute_snapshot_id": snapshot.five_minute.snapshot_id,
        "ten_minute_snapshot_id": snapshot.ten_minute.snapshot_id,
        "fifteen_minute_snapshot_id": snapshot.fifteen_minute.snapshot_id,
        "derivation_count": len(snapshot.derivations),
        "differences": _differences(snapshot.differences),
        "source_provenance_hash": snapshot.source_provenance_hash,
        "result_hash": snapshot.result_hash,
        "immutable": True,
    }
    if any(getattr(record, name) != value for name, value in expected.items()):
        raise HistoricalSynchronizationError(
            "Stored synchronized coverage conflicts with its result hash."
        )


def _differences(value: SynchronizationDifferences) -> dict[str, list[str]]:
    return {
        "unpaired_five_minute_timestamps": [
            item.isoformat() for item in value.unpaired_five_minute_timestamps
        ],
        "missing_native_fifteen_minute_timestamps": [
            item.isoformat() for item in value.missing_native_fifteen_minute_timestamps
        ],
        "native_fifteen_minute_without_complete_five_minute": [
            item.isoformat()
            for item in value.native_fifteen_minute_without_complete_five_minute
        ],
    }


def _result(
    synchronization_id: UUID,
    snapshot: SynchronizedCoverageSnapshot,
    *,
    reused: bool,
) -> SynchronizedCoveragePersistenceResult:
    return SynchronizedCoveragePersistenceResult(
        synchronization_id=synchronization_id,
        result_hash=snapshot.result_hash,
        derivation_count=len(snapshot.derivations),
        reused=reused,
    )
