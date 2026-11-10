"""Crash-safe Binance warmup manifests and post-commit checkpoint coordination."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Any, Literal
from uuid import UUID, uuid5, NAMESPACE_URL

from app.live_market_data.models import CompletedCandle, LiveMessageValidationError
from app.live_market_data.snapshots import CONFIGURATION_HASH


WarmupBatchState = Literal["PENDING", "ACCEPTED", "REJECTED", "RECOVERY_REQUIRED"]
WARMUP_ENDPOINT = "https://data-api.binance.vision/api/v3/klines"
WARMUP_INTERVAL = "5m"
WARMUP_SYMBOL = "BTCUSDT"
MINIMUM_WARMUP_CANDLES = 200


class WarmupBatchIntegrityError(ValueError):
    """Raised when a warmup manifest or member set cannot be verified."""


@dataclass(frozen=True, slots=True)
class BinanceWarmupMember:
    ordinal: int
    snapshot_id: str
    candle_timestamp: datetime
    source_payload_hash: str
    snapshot_result_hash: str
    member_hash: str


@dataclass(frozen=True, slots=True)
class BinanceWarmupBatch:
    batch_id: UUID
    lineage_id: str
    endpoint: str
    request_parameters: dict[str, Any]
    requested_start: datetime
    requested_end_exclusive: datetime
    retrieved_at: datetime
    source_response_hash: str
    candles: tuple[CompletedCandle, ...]
    code_version: str
    configuration_hash: str
    membership_hash: str
    batch_hash: str
    state: WarmupBatchState = "PENDING"
    accepted_at: datetime | None = None

    @property
    def candle_count(self) -> int:
        return len(self.candles)

    @property
    def contiguous_start(self) -> datetime:
        return self.candles[0].open_time

    @property
    def contiguous_end(self) -> datetime:
        return self.candles[-1].open_time

    @property
    def members(self) -> tuple[BinanceWarmupMember, ...]:
        return tuple(
            BinanceWarmupMember(
                ordinal=ordinal,
                snapshot_id=_snapshot_id(candle),
                candle_timestamp=candle.open_time,
                source_payload_hash=candle.source_payload_hash,
                snapshot_result_hash=_snapshot_result_hash(candle),
                member_hash=_member_hash(candle, ordinal),
            )
            for ordinal, candle in enumerate(self.candles)
        )


def build_warmup_batch(
    *,
    lineage_id: str,
    rows: list[list[object]],
    requested_start: datetime,
    requested_end_exclusive: datetime,
    retrieved_at: datetime,
    code_version: str,
    configuration_hash: str = CONFIGURATION_HASH,
    endpoint: str = WARMUP_ENDPOINT,
    request_parameters: dict[str, Any],
    now: datetime,
    minimum_candles: int = MINIMUM_WARMUP_CANDLES,
) -> BinanceWarmupBatch:
    """Validate a complete Binance response before any persistence occurs."""
    if not lineage_id.strip():
        raise WarmupBatchIntegrityError("Warmup lineage identity is required.")
    if not code_version.strip():
        raise WarmupBatchIntegrityError("Warmup code version is required.")
    _utc(requested_start, "requested_start")
    _utc(requested_end_exclusive, "requested_end_exclusive")
    _utc(retrieved_at, "retrieved_at")
    _utc(now, "now")
    if requested_start >= requested_end_exclusive:
        raise WarmupBatchIntegrityError("Warmup request range is invalid.")
    if minimum_candles < 1:
        raise WarmupBatchIntegrityError("Warmup minimum must be positive.")
    source_response_hash = _hash(rows)
    candles = tuple(_candle_from_row(row) for row in rows)
    if len(candles) < minimum_candles:
        raise WarmupBatchIntegrityError(
            f"Warmup returned {len(candles)} candles; minimum is {minimum_candles}."
        )
    previous: CompletedCandle | None = None
    for candle in candles:
        if candle.provider != "binance_spot" or candle.symbol != WARMUP_SYMBOL:
            raise WarmupBatchIntegrityError("Warmup candle source or symbol is invalid.")
        if candle.timeframe.value != WARMUP_INTERVAL:
            raise WarmupBatchIntegrityError("Warmup candle interval is invalid.")
        if candle.close_time >= now or candle.event_time < candle.close_time:
            raise WarmupBatchIntegrityError("Warmup contains an open candle.")
        if candle.open_time < requested_start or candle.open_time >= requested_end_exclusive:
            raise WarmupBatchIntegrityError("Warmup candle is outside requested bounds.")
        if candle.volume <= 0:
            raise WarmupBatchIntegrityError("Warmup candle volume must be positive.")
        if previous is not None:
            if candle.open_time <= previous.open_time:
                raise WarmupBatchIntegrityError("Warmup candles are not strictly ordered.")
            if candle.open_time != previous.open_time + timedelta(minutes=5):
                raise WarmupBatchIntegrityError("Warmup candles contain a missing interval.")
        previous = candle
    members = tuple(
        _member_hash(candle, ordinal)
        for ordinal, candle in enumerate(candles)
    )
    membership_hash = _hash(members)
    batch_payload = {
        "lineage_id": lineage_id,
        "endpoint": endpoint,
        "request_parameters": request_parameters,
        "requested_start": requested_start.astimezone(timezone.utc).isoformat(),
        "requested_end_exclusive": requested_end_exclusive.astimezone(timezone.utc).isoformat(),
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat(),
        "source_response_hash": source_response_hash,
        "candle_count": len(candles),
        "contiguous_start": candles[0].open_time.isoformat(),
        "contiguous_end": candles[-1].open_time.isoformat(),
        "code_version": code_version,
        "configuration_hash": configuration_hash,
        "membership_hash": membership_hash,
    }
    batch_hash = _hash(batch_payload)
    batch_id = uuid5(NAMESPACE_URL, f"alphalens.binance.warmup:{lineage_id}:{batch_hash}")
    return BinanceWarmupBatch(
        batch_id=batch_id,
        lineage_id=lineage_id,
        endpoint=endpoint,
        request_parameters=dict(request_parameters),
        requested_start=requested_start.astimezone(timezone.utc),
        requested_end_exclusive=requested_end_exclusive.astimezone(timezone.utc),
        retrieved_at=retrieved_at.astimezone(timezone.utc),
        source_response_hash=source_response_hash,
        candles=candles,
        code_version=code_version,
        configuration_hash=configuration_hash,
        membership_hash=membership_hash,
        batch_hash=batch_hash,
    )


@dataclass(frozen=True, slots=True)
class AcceptedWarmupCheckpoint:
    batch_id: UUID
    lineage_id: str
    membership_hash: str
    updated_at: datetime


class AcceptedWarmupCheckpointStore:
    """Atomic post-commit file marker; the database remains authoritative."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> AcceptedWarmupCheckpoint | None:
        if not self.path.exists():
            return None
        document = json.loads(self.path.read_text(encoding="utf-8"))
        supplied = document.pop("document_sha256", None)
        if supplied != _hash(document):
            raise WarmupBatchIntegrityError("Warmup checkpoint hash mismatch.")
        return AcceptedWarmupCheckpoint(
            batch_id=UUID(str(document["batch_id"])),
            lineage_id=str(document["lineage_id"]),
            membership_hash=str(document["membership_hash"]),
            updated_at=datetime.fromisoformat(str(document["updated_at"])),
        )

    def save_after_database_acceptance(self, batch: BinanceWarmupBatch) -> None:
        if batch.state != "ACCEPTED":
            raise WarmupBatchIntegrityError("Only an accepted database batch may reach the file checkpoint.")
        self.save_checkpoint(
            AcceptedWarmupCheckpoint(
                batch_id=batch.batch_id,
                lineage_id=batch.lineage_id,
                membership_hash=batch.membership_hash,
                updated_at=datetime.now(timezone.utc),
            )
        )

    def save_checkpoint(self, checkpoint: AcceptedWarmupCheckpoint) -> None:
        document: dict[str, Any] = {
            "batch_id": str(checkpoint.batch_id),
            "lineage_id": checkpoint.lineage_id,
            "membership_hash": checkpoint.membership_hash,
            "updated_at": checkpoint.updated_at.astimezone(timezone.utc).isoformat(),
        }
        document["document_sha256"] = _hash(document)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False
            ) as handle:
                temporary = handle.name
                json.dump(document, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
            Path(temporary).replace(self.path)
        except OSError as error:
            if temporary:
                Path(temporary).unlink(missing_ok=True)
            raise WarmupBatchIntegrityError("Warmup checkpoint replacement failed.") from error


def reconcile_warmup_checkpoint(
    store: AcceptedWarmupCheckpointStore,
    database_checkpoint: AcceptedWarmupCheckpoint | None,
) -> AcceptedWarmupCheckpoint | None:
    """Reconcile the post-commit marker without ever promoting it to authority."""
    file_checkpoint = store.load()
    if database_checkpoint is None:
        if file_checkpoint is not None:
            raise WarmupBatchIntegrityError(
                "Filesystem warmup checkpoint has no accepted database manifest."
            )
        return None
    if file_checkpoint is None:
        store.save_checkpoint(database_checkpoint)
        return database_checkpoint
    if file_checkpoint != database_checkpoint:
        raise WarmupBatchIntegrityError(
            "Filesystem warmup checkpoint does not match the accepted database manifest."
        )
    return database_checkpoint


def accepted_batch(batch: BinanceWarmupBatch, accepted_at: datetime | None) -> BinanceWarmupBatch:
    """Return the caller-visible accepted state after a committed transaction."""
    if accepted_at is None:
        raise WarmupBatchIntegrityError("Accepted batch is missing accepted_at.")
    return replace(batch, state="ACCEPTED", accepted_at=accepted_at)


def validate_warmup_batch(batch: BinanceWarmupBatch) -> None:
    """Recheck persisted-manifest invariants immediately before database use."""
    if batch.state != "PENDING" or batch.candle_count < MINIMUM_WARMUP_CANDLES:
        raise WarmupBatchIntegrityError("Warmup batch is not a valid pending manifest.")
    members = batch.members
    membership_hash = _hash(tuple(member.member_hash for member in members))
    if membership_hash != batch.membership_hash:
        raise WarmupBatchIntegrityError("Warmup membership hash mismatch.")
    payload = {
        "lineage_id": batch.lineage_id,
        "endpoint": batch.endpoint,
        "request_parameters": batch.request_parameters,
        "requested_start": batch.requested_start.astimezone(timezone.utc).isoformat(),
        "requested_end_exclusive": batch.requested_end_exclusive.astimezone(timezone.utc).isoformat(),
        "retrieved_at": batch.retrieved_at.astimezone(timezone.utc).isoformat(),
        "source_response_hash": batch.source_response_hash,
        "candle_count": batch.candle_count,
        "contiguous_start": batch.contiguous_start.isoformat(),
        "contiguous_end": batch.contiguous_end.isoformat(),
        "code_version": batch.code_version,
        "configuration_hash": batch.configuration_hash,
        "membership_hash": batch.membership_hash,
    }
    if _hash(payload) != batch.batch_hash:
        raise WarmupBatchIntegrityError("Warmup batch hash mismatch.")


def _candle_from_row(row: list[object]) -> CompletedCandle:
    from app.live_market_data.service import _completed_candle_from_rest_kline

    try:
        return _completed_candle_from_rest_kline(row)
    except (IndexError, TypeError, ValueError, ArithmeticError, LiveMessageValidationError) as error:
        raise WarmupBatchIntegrityError("Provider response row is malformed.") from error


def _snapshot_id(candle: CompletedCandle) -> str:
    from app.live_market_data.snapshots import build_market_snapshot

    return build_market_snapshot(candle, code_version="warmup.validation").snapshot_id


def _snapshot_result_hash(candle: CompletedCandle) -> str:
    from app.live_market_data.snapshots import build_market_snapshot

    return build_market_snapshot(candle, code_version="warmup.validation").audit.result_hash


def _member_hash(candle: CompletedCandle, ordinal: int) -> str:
    return _hash(
        {
            "ordinal": ordinal,
            "snapshot_id": _snapshot_id(candle),
            "candle_timestamp": candle.open_time.isoformat(),
            "source_payload_hash": candle.source_payload_hash,
            "snapshot_result_hash": _snapshot_result_hash(candle),
        }
    )


def _hash(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise WarmupBatchIntegrityError(f"{name} must be canonical UTC.")
