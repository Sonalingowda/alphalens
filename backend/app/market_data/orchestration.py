"""Resumable, bounded intraday historical acquisition contracts."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import logging
from typing import Callable, Protocol
from uuid import UUID, uuid4

from app.market_data.coverage import (
    ACQUISITION_POLICY_IDENTIFIER,
    ACQUISITION_POLICY_VERSION,
)
from app.market_data.history import (
    HistoricalSample,
    KRAKEN_OHLC_PAGE_LIMIT,
    fetch_btc_usd_intraday_native,
)
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.provider import MarketDataProvider, MarketDataProviderError
from app.persistence.candles import CandlePersistenceResult


ORCHESTRATION_SCHEMA_VERSION = "1.0.0"
ORCHESTRATION_HASH_SCHEMA_VERSION = "1.0.0"
ACQUISITION_POLICY_HASH = (
    "7582a39fa873d2eb5e534c3227c664946950571dd98d593a869daefaf90f535c"
)
KRAKEN_ENDPOINT_IDENTITY = "kraken_spot_rest_public_ohlc"
_SUPPORTED_TIMEFRAMES = frozenset({CandleTimeframe.MINUTE_5, CandleTimeframe.MINUTE_15})
logger = logging.getLogger("uvicorn.error")


class HistoricalOrchestrationError(RuntimeError):
    """Raised when acquisition cannot safely proceed or resume."""


class CheckpointIntegrityError(HistoricalOrchestrationError):
    """Raised when persisted checkpoint evidence does not verify."""


class CheckpointReconciliationRequired(HistoricalOrchestrationError):
    """Raised when committed candle evidence lacks a checkpoint."""


@dataclass(frozen=True, slots=True)
class AcquisitionAttempt:
    attempt_id: UUID
    timeframe: CandleTimeframe
    requested_start: datetime
    requested_end_exclusive: datetime
    started_at: datetime
    code_version: str
    configuration_hash: str
    attempt_hash: str


@dataclass(frozen=True, slots=True)
class AcquisitionCheckpoint:
    checkpoint_id: UUID
    schema_version: str
    hash_schema_version: str
    attempt_id: UUID
    predecessor_checkpoint_id: UUID | None
    timeframe: CandleTimeframe
    requested_start: datetime
    requested_end_exclusive: datetime
    provider_available_start: datetime
    provider_available_end: datetime
    provider_cursor: datetime
    provider_row_count: int
    accepted_count: int
    excluded_incomplete_count: int
    reused_count: int
    inserted_count: int
    conflict_count: int
    ingestion_batch_id: UUID
    validation_passed: bool
    provider_limit_reached: bool
    terminal_reason: str
    configuration_hash: str
    source_data_hash: str
    progress_hash: str
    checkpoint_hash: str


@dataclass(frozen=True, slots=True)
class HistoricalAcquisitionResult:
    attempt: AcquisitionAttempt
    sample: HistoricalSample
    persistence: CandlePersistenceResult
    checkpoint: AcquisitionCheckpoint


class HistoricalOrchestrationStore(Protocol):
    async def prepare_resume(
        self,
        timeframe: CandleTimeframe,
        configuration_hash: str,
        code_version: str,
    ) -> AcquisitionCheckpoint | None: ...

    async def record_attempt(self, attempt: AcquisitionAttempt) -> None: ...

    async def record_failure(
        self,
        attempt: AcquisitionAttempt,
        terminal_reason: str,
        failure_class: str,
        failure_summary: str,
        completed_at: datetime,
    ) -> None: ...

    async def persist_sample(
        self,
        attempt_id: UUID,
        sample: HistoricalSample,
    ) -> CandlePersistenceResult: ...

    async def record_checkpoint(
        self,
        attempt: AcquisitionAttempt,
        checkpoint: AcquisitionCheckpoint,
        completed_at: datetime,
    ) -> UUID: ...


async def orchestrate_intraday_historical_window(
    *,
    provider: MarketDataProvider,
    store: HistoricalOrchestrationStore,
    timeframe: CandleTimeframe,
    code_version: str,
    now: datetime,
    progress_callback: Callable[[AcquisitionCheckpoint], None] | None = None,
) -> HistoricalAcquisitionResult:
    """Acquire exactly one approved Kraken window and durably checkpoint it."""
    normalized_now = _utc(now, "Acquisition time")
    if timeframe not in _SUPPORTED_TIMEFRAMES:
        raise HistoricalOrchestrationError(
            "Historical orchestration supports only native 5m and 15m."
        )
    if not code_version.strip():
        raise HistoricalOrchestrationError("Code version must be non-empty.")

    configuration_hash = _configuration_hash(timeframe, code_version)
    predecessor = await store.prepare_resume(
        timeframe,
        configuration_hash,
        code_version,
    )
    requested_end = _requested_end(normalized_now, timeframe)
    duration_seconds = 300 if timeframe is CandleTimeframe.MINUTE_5 else 900
    requested_start = requested_end - timedelta(
        seconds=duration_seconds * KRAKEN_OHLC_PAGE_LIMIT
    )
    attempt = _build_attempt(
        timeframe=timeframe,
        requested_start=requested_start,
        requested_end=requested_end,
        started_at=normalized_now,
        code_version=code_version,
        configuration_hash=configuration_hash,
    )
    await store.record_attempt(attempt)

    try:
        sample = await fetch_btc_usd_intraday_native(
            provider,
            timeframe,
            now=normalized_now,
        )
    except MarketDataProviderError as exc:
        await store.record_failure(
            attempt,
            "PROVIDER_FAILED",
            type(exc).__name__,
            str(exc),
            normalized_now,
        )
        raise

    if not sample.validation_report.passed:
        await store.record_failure(
            attempt,
            "VALIDATION_FAILED",
            "CandleValidationError",
            ",".join(issue.code for issue in sample.validation_report.issues),
            sample.retrieved_at,
        )
        raise HistoricalOrchestrationError(
            "Provider window failed validation; no canonical checkpoint advanced."
        )

    try:
        persistence = await store.persist_sample(attempt.attempt_id, sample)
    except CheckpointReconciliationRequired:
        raise
    except Exception as exc:
        await store.record_failure(
            attempt,
            "PERSISTENCE_FAILED",
            type(exc).__name__,
            str(exc),
            sample.retrieved_at,
        )
        raise
    checkpoint = build_acquisition_checkpoint(
        attempt=attempt,
        sample=sample,
        persistence=persistence,
        predecessor_checkpoint_id=(
            predecessor.checkpoint_id if predecessor is not None else None
        ),
    )
    await store.record_checkpoint(attempt, checkpoint, sample.retrieved_at)
    if progress_callback is not None:
        progress_callback(checkpoint)
    logger.info(
        "Intraday historical checkpoint timeframe=%s rows=%s inserted=%s reused=%s terminal=%s hash=%s",
        timeframe.value,
        checkpoint.provider_row_count,
        checkpoint.inserted_count,
        checkpoint.reused_count,
        checkpoint.terminal_reason,
        checkpoint.checkpoint_hash,
    )
    return HistoricalAcquisitionResult(attempt, sample, persistence, checkpoint)


def verify_acquisition_attempt(attempt: AcquisitionAttempt) -> None:
    payload = {
        "hash_schema_version": ORCHESTRATION_HASH_SCHEMA_VERSION,
        "timeframe": attempt.timeframe.value,
        "requested_start": _timestamp(attempt.requested_start),
        "requested_end_exclusive": _timestamp(attempt.requested_end_exclusive),
        "code_version": attempt.code_version,
        "configuration_hash": attempt.configuration_hash,
    }
    if attempt.attempt_hash != _sha256(payload):
        raise CheckpointIntegrityError("Acquisition attempt hash verification failed.")


def build_acquisition_checkpoint(
    *,
    attempt: AcquisitionAttempt,
    sample: HistoricalSample,
    persistence: CandlePersistenceResult,
    predecessor_checkpoint_id: UUID | None,
) -> AcquisitionCheckpoint:
    if (
        not persistence.validation_passed
        or persistence.fetched_candle_count != len(sample.candles)
        or persistence.persisted_candle_count > len(sample.candles)
    ):
        raise HistoricalOrchestrationError(
            "Persisted acquisition evidence does not match the provider window."
        )
    if len(sample.progress) != 1:
        raise HistoricalOrchestrationError(
            "Kraken intraday acquisition must contain exactly one window."
        )
    timestamps = tuple(
        candle.timestamp for candle in sample.candles if candle.timestamp is not None
    )
    if not timestamps:
        raise HistoricalOrchestrationError("Checkpoint requires completed candles.")
    progress = sample.progress[0]
    reused_count = len(sample.candles) - persistence.persisted_candle_count
    terminal_reason = (
        "PROVIDER_HISTORY_EXHAUSTED"
        if sample.provider_limit_reached and sample.requested_start < timestamps[0]
        else (
            "SUCCESS_NEW_INSERTS"
            if persistence.persisted_candle_count
            else "SUCCESS_REUSE_ONLY"
        )
    )
    payload = {
        "hash_schema_version": ORCHESTRATION_HASH_SCHEMA_VERSION,
        "policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
        "policy_version": ACQUISITION_POLICY_VERSION,
        "policy_hash": ACQUISITION_POLICY_HASH,
        "provider": "kraken",
        "endpoint": KRAKEN_ENDPOINT_IDENTITY,
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "timeframe": attempt.timeframe.value,
        "requested_start": _timestamp(attempt.requested_start),
        "requested_end_exclusive": _timestamp(attempt.requested_end_exclusive),
        "provider_available_start": _timestamp(timestamps[0]),
        "provider_available_end": _timestamp(timestamps[-1]),
        "provider_cursor": _timestamp(progress.next_since),
        "provider_row_count": progress.provider_row_count,
        "accepted_count": len(sample.candles),
        "excluded_incomplete_count": sample.excluded_incomplete_candle_count,
        "reused_count": reused_count,
        "inserted_count": persistence.persisted_candle_count,
        "conflict_count": 0,
        "validation_passed": True,
        "provider_limit_reached": sample.provider_limit_reached,
        "terminal_reason": terminal_reason,
        "configuration_hash": attempt.configuration_hash,
        "source_data_hash": hash_candle_sequence(sample.candles),
    }
    progress_hash = _sha256(payload)
    checkpoint_hash = _sha256(
        {
            "schema_version": ORCHESTRATION_SCHEMA_VERSION,
            "progress_hash": progress_hash,
        }
    )
    return AcquisitionCheckpoint(
        uuid4(),
        ORCHESTRATION_SCHEMA_VERSION,
        ORCHESTRATION_HASH_SCHEMA_VERSION,
        attempt.attempt_id,
        predecessor_checkpoint_id,
        attempt.timeframe,
        attempt.requested_start,
        attempt.requested_end_exclusive,
        timestamps[0],
        timestamps[-1],
        progress.next_since,
        progress.provider_row_count,
        len(sample.candles),
        sample.excluded_incomplete_candle_count,
        reused_count,
        persistence.persisted_candle_count,
        0,
        persistence.ingestion_batch_id,
        True,
        sample.provider_limit_reached,
        terminal_reason,
        attempt.configuration_hash,
        payload["source_data_hash"],
        progress_hash,
        checkpoint_hash,
    )


def verify_acquisition_checkpoint(checkpoint: AcquisitionCheckpoint) -> None:
    if (
        checkpoint.schema_version != ORCHESTRATION_SCHEMA_VERSION
        or checkpoint.hash_schema_version != ORCHESTRATION_HASH_SCHEMA_VERSION
        or checkpoint.inserted_count < 0
        or checkpoint.reused_count < 0
        or checkpoint.inserted_count + checkpoint.reused_count
        != checkpoint.accepted_count
        or not checkpoint.validation_passed
        or len(checkpoint.source_data_hash) != 64
        or len(checkpoint.progress_hash) != 64
        or len(checkpoint.checkpoint_hash) != 64
    ):
        raise CheckpointIntegrityError("Checkpoint evidence is structurally invalid.")
    expected_progress_hash = _sha256(_checkpoint_payload(checkpoint))
    expected_checkpoint_hash = _sha256(
        {
            "schema_version": checkpoint.schema_version,
            "progress_hash": expected_progress_hash,
        }
    )
    if (
        checkpoint.progress_hash != expected_progress_hash
        or checkpoint.checkpoint_hash != expected_checkpoint_hash
    ):
        raise CheckpointIntegrityError("Checkpoint hash verification failed.")


def _checkpoint_payload(checkpoint: AcquisitionCheckpoint) -> dict[str, object]:
    return {
        "hash_schema_version": checkpoint.hash_schema_version,
        "policy_identifier": ACQUISITION_POLICY_IDENTIFIER,
        "policy_version": ACQUISITION_POLICY_VERSION,
        "policy_hash": ACQUISITION_POLICY_HASH,
        "provider": "kraken",
        "endpoint": KRAKEN_ENDPOINT_IDENTITY,
        "asset_identifier": "BTC",
        "quote_currency": "USD",
        "timeframe": checkpoint.timeframe.value,
        "requested_start": _timestamp(checkpoint.requested_start),
        "requested_end_exclusive": _timestamp(checkpoint.requested_end_exclusive),
        "provider_available_start": _timestamp(checkpoint.provider_available_start),
        "provider_available_end": _timestamp(checkpoint.provider_available_end),
        "provider_cursor": _timestamp(checkpoint.provider_cursor),
        "provider_row_count": checkpoint.provider_row_count,
        "accepted_count": checkpoint.accepted_count,
        "excluded_incomplete_count": checkpoint.excluded_incomplete_count,
        "reused_count": checkpoint.reused_count,
        "inserted_count": checkpoint.inserted_count,
        "conflict_count": checkpoint.conflict_count,
        "validation_passed": checkpoint.validation_passed,
        "provider_limit_reached": checkpoint.provider_limit_reached,
        "terminal_reason": checkpoint.terminal_reason,
        "configuration_hash": checkpoint.configuration_hash,
        "source_data_hash": checkpoint.source_data_hash,
    }


def hash_candle_sequence(candles: tuple[Candle, ...]) -> str:
    """Hash ordered fixed-point candle evidence without binary floats."""
    return _sha256(
        {
            "hash_schema_version": ORCHESTRATION_HASH_SCHEMA_VERSION,
            "candles": [
                {
                    "timestamp": _timestamp(candle.timestamp),
                    "open": _decimal(candle.open),
                    "high": _decimal(candle.high),
                    "low": _decimal(candle.low),
                    "close": _decimal(candle.close),
                    "volume": _decimal(candle.volume),
                }
                for candle in candles
            ],
        }
    )


def _decimal(value: object) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise HistoricalOrchestrationError("Hash Decimal value is invalid.")
    with localcontext() as context:
        context.prec = max(80, len(value.as_tuple().digits) + 40)
        quantized = value.quantize(
            Decimal("0.000000000000000001"),
            rounding=ROUND_HALF_EVEN,
        )
    return format(quantized, "f")


def _build_attempt(**values: object) -> AcquisitionAttempt:
    payload = {
        "hash_schema_version": ORCHESTRATION_HASH_SCHEMA_VERSION,
        "timeframe": values["timeframe"].value,
        "requested_start": _timestamp(values["requested_start"]),
        "requested_end_exclusive": _timestamp(values["requested_end"]),
        "code_version": values["code_version"],
        "configuration_hash": values["configuration_hash"],
    }
    return AcquisitionAttempt(
        attempt_id=uuid4(),
        timeframe=values["timeframe"],
        requested_start=values["requested_start"],
        requested_end_exclusive=values["requested_end"],
        started_at=values["started_at"],
        code_version=values["code_version"],
        configuration_hash=values["configuration_hash"],
        attempt_hash=_sha256(payload),
    )


def _configuration_hash(timeframe: CandleTimeframe, code_version: str) -> str:
    return _sha256(
        {
            "hash_schema_version": ORCHESTRATION_HASH_SCHEMA_VERSION,
            "policy_hash": ACQUISITION_POLICY_HASH,
            "provider": "kraken",
            "endpoint": KRAKEN_ENDPOINT_IDENTITY,
            "asset_identifier": "BTC",
            "quote_currency": "USD",
            "timeframe": timeframe.value,
            "provider_page_limit": KRAKEN_OHLC_PAGE_LIMIT,
            "retry_policy": "none_until_explicit_approval",
            "code_version": code_version,
        }
    )


def _requested_end(now: datetime, timeframe: CandleTimeframe) -> datetime:
    seconds = 300 if timeframe is CandleTimeframe.MINUTE_5 else 900
    return datetime.fromtimestamp(
        int(now.timestamp()) // seconds * seconds,
        tz=timezone.utc,
    )


def _utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HistoricalOrchestrationError(f"{label} must be timezone-aware.")
    return value.astimezone(timezone.utc)


def _timestamp(value: object) -> str:
    if not isinstance(value, datetime):
        raise HistoricalOrchestrationError("Hash timestamp is invalid.")
    return _utc(value, "Hash timestamp").isoformat(timespec="microseconds")


def _sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
