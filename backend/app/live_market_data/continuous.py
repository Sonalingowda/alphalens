"""Durable sequential processing for closed BTCUSDT/5m candles.

This module is deliberately policy-neutral.  It coordinates the existing live
ingestion service and runtime pipeline; it does not create market signals or
model outputs.  A filesystem checkpoint is suitable for the isolated runtime
and replay driver.  Production deployment must place the checkpoint directory
on durable, single-owner storage and expose it through the operational
configuration rather than sharing it between workers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Awaitable, Callable

from app.live_market_data.models import CompletedCandle
from app.live_market_data.service import LiveMarketIngestionService
from app.live_market_data.snapshots import build_market_snapshot
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketSnapshot
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
)


RUNTIME_CHECKPOINT_VERSION = "1.0.0"
_FIVE_MINUTES = timedelta(minutes=5)


class RuntimeProcessingError(RuntimeError):
    """Base error for fail-closed continuous processing."""


class RuntimeGapError(RuntimeProcessingError):
    """A required candle interval is missing."""


class RuntimeOutOfOrderError(RuntimeProcessingError):
    """An unknown candle arrived before the durable processing boundary."""


class RuntimeCheckpointError(RuntimeProcessingError):
    """Checkpoint bytes or checkpoint transitions are invalid."""


class RuntimeProcessingOutcome(StrEnum):
    PROCESSED = "PROCESSED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True, slots=True)
class RuntimeCheckpoint:
    source_dataset_sha256: str
    symbol: str
    timeframe: str
    sequence: int
    status: str
    last_committed_open_time: datetime | None
    last_committed_content_hash: str | None
    in_flight_open_time: datetime | None
    in_flight_content_hash: str | None
    missing_start: datetime | None
    missing_end: datetime | None
    last_error: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        if len(self.source_dataset_sha256) != 64:
            raise RuntimeCheckpointError("Checkpoint source hash must be SHA-256.")
        if self.symbol != "BTCUSDT" or self.timeframe != "5m":
            raise RuntimeCheckpointError("Checkpoint scope must be BTCUSDT/5m.")
        if self.sequence < 0:
            raise RuntimeCheckpointError("Checkpoint sequence cannot be negative.")
        if self.status not in {"READY", "PROCESSING", "QUARANTINED", "ERROR"}:
            raise RuntimeCheckpointError("Checkpoint status is unsupported.")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() != timedelta(0):
            raise RuntimeCheckpointError("Checkpoint timestamp must be UTC.")


class FilesystemRuntimeCheckpointStore:
    """Atomic, hash-bound checkpoint storage for one isolated worker."""

    def __init__(self, path: str | Path, *, source_dataset_sha256: str) -> None:
        self._path = Path(path)
        self._source_hash = source_dataset_sha256
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def source_dataset_sha256(self) -> str:
        return self._source_hash

    def load(self) -> RuntimeCheckpoint | None:
        if not self._path.exists():
            return None
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("checkpoint root must be an object")
            supplied_hash = document.pop("document_sha256", None)
            expected_hash = _hash_document(document)
            if supplied_hash != expected_hash:
                raise ValueError("checkpoint document hash mismatch")
            if document.get("version") != RUNTIME_CHECKPOINT_VERSION:
                raise ValueError("checkpoint version mismatch")
            if document.get("source_dataset_sha256") != self._source_hash:
                raise ValueError("checkpoint source dataset mismatch")
            return _decode_checkpoint(document)
        except RuntimeCheckpointError:
            raise
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeCheckpointError("Runtime checkpoint is corrupt.") from error

    def save(self, checkpoint: RuntimeCheckpoint) -> None:
        if checkpoint.source_dataset_sha256 != self._source_hash:
            raise RuntimeCheckpointError("Checkpoint source dataset mismatch.")
        document = _encode_checkpoint(checkpoint)
        document["version"] = RUNTIME_CHECKPOINT_VERSION
        document["source_dataset_sha256"] = self._source_hash
        document["document_sha256"] = _hash_document(document)
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._path)
            directory_fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as error:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
            raise RuntimeCheckpointError("Runtime checkpoint write failed.") from error


@dataclass(frozen=True, slots=True)
class RuntimeHealthSnapshot:
    worker_status: str
    last_finalized_candle: datetime | None
    last_successful_processing: datetime | None
    processing_lag_seconds: float | None
    gap_status: str
    persistence_status: str
    retry_status: str
    model_artifact_status: str
    last_error: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "worker_status": self.worker_status,
            "last_finalized_candle": _iso(self.last_finalized_candle),
            "last_successful_processing": _iso(self.last_successful_processing),
            "processing_lag_seconds": self.processing_lag_seconds,
            "gap_status": self.gap_status,
            "persistence_status": self.persistence_status,
            "retry_status": self.retry_status,
            "model_artifact_status": self.model_artifact_status,
            "last_error": self.last_error,
        }


PipelineRunner = Callable[[MarketSnapshot, datetime], Awaitable[object]]


class ContinuousClosedCandleProcessor:
    """Process one ordered stream of genuine completed candles.

    The processor advances its durable checkpoint only after the existing
    ingestion persistence and runtime pipeline have returned successfully.
    An in-flight marker makes an interrupted commit recoverable: the next
    worker run replays the exact immutable candle and relies on repository
    identity constraints for idempotency.
    """

    def __init__(
        self,
        *,
        ingestion: LiveMarketIngestionService,
        checkpoint_store: FilesystemRuntimeCheckpointStore,
        pipeline: PipelineRunner,
        code_version: str,
        clock: Callable[[], datetime] | None = None,
        retry_attempts: int = 3,
        retry_backoff_seconds: float = 0.1,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime processor code version is required.")
        if retry_attempts < 1 or retry_backoff_seconds < 0:
            raise ValueError("Runtime retry configuration is invalid.")
        self._ingestion = ingestion
        self._store = checkpoint_store
        self._pipeline = pipeline
        self._code_version = code_version
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._lock = asyncio.Lock()
        self._checkpoint = checkpoint_store.load()
        self._retry_status = "idle"

    @property
    def checkpoint(self) -> RuntimeCheckpoint | None:
        return self._checkpoint

    @property
    def health(self) -> RuntimeHealthSnapshot:
        checkpoint = self._checkpoint
        now = self._clock().astimezone(timezone.utc)
        last = checkpoint.last_committed_open_time if checkpoint else None
        lag = (now - last).total_seconds() if last is not None else None
        return RuntimeHealthSnapshot(
            worker_status=(checkpoint.status if checkpoint else "READY"),
            last_finalized_candle=last,
            last_successful_processing=(checkpoint.updated_at if checkpoint else None),
            processing_lag_seconds=lag,
            gap_status=("QUARANTINED" if checkpoint and checkpoint.missing_start else "CLEAR"),
            persistence_status="AVAILABLE",
            retry_status=self._retry_status,
            model_artifact_status="UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT",
            last_error=checkpoint.last_error if checkpoint else None,
        )

    async def process(self, candle: CompletedCandle) -> RuntimeProcessingOutcome:
        async with self._lock:
            return await self._process_locked(candle)

    async def process_with_retry(self, candle: CompletedCandle) -> RuntimeProcessingOutcome:
        for attempt in range(1, self._retry_attempts + 1):
            self._retry_status = f"attempt_{attempt}_of_{self._retry_attempts}"
            try:
                result = await self.process(candle)
            except (RuntimeGapError, RuntimeOutOfOrderError, RuntimeCheckpointError):
                self._retry_status = "not_retryable"
                raise
            except Exception:
                if attempt == self._retry_attempts:
                    self._retry_status = "exhausted"
                    raise
                await asyncio.sleep(self._retry_backoff_seconds * attempt)
            else:
                self._retry_status = "idle"
                return result
        raise AssertionError("Runtime retry loop exited without a result.")

    async def _process_locked(
        self, candle: CompletedCandle
    ) -> RuntimeProcessingOutcome:
        _validate_closed_scope(candle)
        snapshot = build_market_snapshot(candle, code_version=self._code_version)
        checkpoint = self._checkpoint
        existing = await self._existing_snapshot(snapshot)
        if checkpoint is not None and checkpoint.last_committed_open_time is not None:
            if candle.open_time <= checkpoint.last_committed_open_time:
                if existing is None:
                    raise RuntimeOutOfOrderError(
                        "Older candle is absent from durable persistence."
                    )
                if not _same_snapshot_content(existing, snapshot):
                    raise RuntimeOutOfOrderError(
                        "Older candle conflicts with durable persistence."
                    )
                return RuntimeProcessingOutcome.DUPLICATE
            expected = checkpoint.last_committed_open_time + _FIVE_MINUTES
            if candle.open_time != expected:
                return await self._quarantine_gap(candle, expected)

        recovering_in_flight = bool(
            checkpoint is not None
            and checkpoint.in_flight_open_time == candle.open_time
            and checkpoint.in_flight_content_hash == candle.content_hash
        )
        in_flight = RuntimeCheckpoint(
            source_dataset_sha256=self._store.source_dataset_sha256,
            symbol="BTCUSDT",
            timeframe="5m",
            sequence=(
                checkpoint.sequence
                if recovering_in_flight and checkpoint is not None
                else (checkpoint.sequence + 1 if checkpoint else 1)
            ),
            status="PROCESSING",
            last_committed_open_time=(checkpoint.last_committed_open_time if checkpoint else None),
            last_committed_content_hash=(checkpoint.last_committed_content_hash if checkpoint else None),
            in_flight_open_time=candle.open_time,
            in_flight_content_hash=candle.content_hash,
            missing_start=None,
            missing_end=None,
            last_error=None,
            updated_at=self._clock().astimezone(timezone.utc),
        )
        self._store.save(in_flight)
        self._checkpoint = in_flight

        try:
            stored = await self._ingestion.persist_completed_candle(candle)
            canonical = stored or existing or snapshot
            await self._pipeline(canonical, canonical.audit.available_at)
        except Exception as error:
            failed = RuntimeCheckpoint(
                source_dataset_sha256=in_flight.source_dataset_sha256,
                symbol=in_flight.symbol,
                timeframe=in_flight.timeframe,
                sequence=in_flight.sequence,
                status="ERROR",
                last_committed_open_time=in_flight.last_committed_open_time,
                last_committed_content_hash=in_flight.last_committed_content_hash,
                in_flight_open_time=in_flight.in_flight_open_time,
                in_flight_content_hash=in_flight.in_flight_content_hash,
                missing_start=None,
                missing_end=None,
                last_error=type(error).__name__,
                updated_at=self._clock().astimezone(timezone.utc),
            )
            self._store.save(failed)
            self._checkpoint = failed
            raise
        committed = RuntimeCheckpoint(
            source_dataset_sha256=in_flight.source_dataset_sha256,
            symbol="BTCUSDT",
            timeframe="5m",
            sequence=in_flight.sequence,
            status="READY",
            last_committed_open_time=candle.open_time,
            last_committed_content_hash=candle.content_hash,
            in_flight_open_time=None,
            in_flight_content_hash=None,
            missing_start=None,
            missing_end=None,
            last_error=None,
            updated_at=self._clock().astimezone(timezone.utc),
        )
        self._store.save(committed)
        self._checkpoint = committed
        return RuntimeProcessingOutcome.PROCESSED

    async def _existing_snapshot(self, snapshot: MarketSnapshot) -> MarketSnapshot | None:
        try:
            return await self._ingestion.repository.get_by_id(EntityId(snapshot.snapshot_id))
        except EntityNotFoundError:
            return None

    async def _quarantine_gap(
        self, candle: CompletedCandle, expected: datetime
    ) -> RuntimeProcessingOutcome:
        missing_end = candle.open_time - _FIVE_MINUTES
        checkpoint = self._checkpoint
        quarantined = RuntimeCheckpoint(
            source_dataset_sha256=self._store.source_dataset_sha256,
            symbol="BTCUSDT",
            timeframe="5m",
            sequence=(checkpoint.sequence if checkpoint else 0),
            status="QUARANTINED",
            last_committed_open_time=(checkpoint.last_committed_open_time if checkpoint else None),
            last_committed_content_hash=(checkpoint.last_committed_content_hash if checkpoint else None),
            in_flight_open_time=None,
            in_flight_content_hash=None,
            missing_start=expected,
            missing_end=missing_end,
            last_error="missing_closed_candle_interval",
            updated_at=self._clock().astimezone(timezone.utc),
        )
        self._store.save(quarantined)
        self._checkpoint = quarantined
        return RuntimeProcessingOutcome.QUARANTINED


def _validate_closed_scope(candle: CompletedCandle) -> None:
    if candle.symbol != "BTCUSDT" or candle.timeframe is not CandleTimeframe.MINUTE_5:
        raise RuntimeProcessingError("Continuous processor accepts BTCUSDT/5m only.")
    if candle.event_time < candle.close_time:
        raise RuntimeProcessingError("Incomplete candle cannot enter processing.")


def _same_snapshot_content(first: MarketSnapshot, second: MarketSnapshot) -> bool:
    left = first.candles[0]
    right = second.candles[0]
    return (
        left.timestamp,
        left.open,
        left.high,
        left.low,
        left.close,
        left.volume,
    ) == (
        right.timestamp,
        right.open,
        right.high,
        right.low,
        right.close,
        right.volume,
    )


def _encode_checkpoint(checkpoint: RuntimeCheckpoint) -> dict[str, object]:
    return {
        "source_dataset_sha256": checkpoint.source_dataset_sha256,
        "symbol": checkpoint.symbol,
        "timeframe": checkpoint.timeframe,
        "sequence": checkpoint.sequence,
        "status": checkpoint.status,
        "last_committed_open_time": _iso(checkpoint.last_committed_open_time),
        "last_committed_content_hash": checkpoint.last_committed_content_hash,
        "in_flight_open_time": _iso(checkpoint.in_flight_open_time),
        "in_flight_content_hash": checkpoint.in_flight_content_hash,
        "missing_start": _iso(checkpoint.missing_start),
        "missing_end": _iso(checkpoint.missing_end),
        "last_error": checkpoint.last_error,
        "updated_at": _iso(checkpoint.updated_at),
    }


def _decode_checkpoint(document: dict[str, object]) -> RuntimeCheckpoint:
    return RuntimeCheckpoint(
        source_dataset_sha256=str(document["source_dataset_sha256"]),
        symbol=str(document["symbol"]),
        timeframe=str(document["timeframe"]),
        sequence=int(document["sequence"]),
        status=str(document["status"]),
        last_committed_open_time=_parse_time(document.get("last_committed_open_time")),
        last_committed_content_hash=_optional_string(document.get("last_committed_content_hash")),
        in_flight_open_time=_parse_time(document.get("in_flight_open_time")),
        in_flight_content_hash=_optional_string(document.get("in_flight_content_hash")),
        missing_start=_parse_time(document.get("missing_start")),
        missing_end=_parse_time(document.get("missing_end")),
        last_error=_optional_string(document.get("last_error")),
        updated_at=_parse_time(document.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc),
    )


def _hash_document(document: dict[str, object]) -> str:
    unsigned = {key: value for key, value in document.items() if key != "document_sha256"}
    return hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def _parse_time(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeCheckpointError("Checkpoint time must be an ISO string.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise RuntimeCheckpointError("Checkpoint time must be UTC.")
    return parsed.astimezone(timezone.utc)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeCheckpointError("Checkpoint string field is invalid.")
    return value
