"""Deterministic immutable source-conflict evidence contracts."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from uuid import UUID

from app.market_data.models import Candle, CandleTimeframe


CONFLICT_SCHEMA_VERSION = "1.0.0"
CONFLICT_HASH_SCHEMA_VERSION = "1.0.0"
_DECIMAL_QUANTUM = Decimal("0.000000000000000001")


class SourceConflictError(RuntimeError):
    """Raised when incoming source evidence conflicts with canonical data."""


class SourceConflictIntegrityError(SourceConflictError):
    """Raised when immutable conflict evidence does not verify."""


@dataclass(frozen=True, slots=True)
class SourceConflictEvidence:
    schema_version: str
    hash_schema_version: str
    conflict_type: str
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    candle_timestamp: datetime
    canonical_candle_id: int
    canonical_ingestion_batch_id: UUID
    canonical_provider: str
    canonical_candle: Candle
    incoming_attempt_id: UUID | None
    incoming_ingestion_batch_id: UUID
    incoming_provider: str
    incoming_candle: Candle
    retrieved_at: datetime
    available_at: datetime
    canonical_candle_hash: str
    incoming_candle_hash: str
    incoming_batch_source_hash: str
    conflict_hash: str


@dataclass(frozen=True, slots=True)
class CanonicalSourceObservation:
    candle_id: int
    ingestion_batch_id: UUID
    provider: str
    candle: Candle


@dataclass(frozen=True, slots=True)
class SourceBatchComparison:
    reused_count: int
    conflicts: tuple[SourceConflictEvidence, ...]

    @property
    def canonical_insert_allowed(self) -> bool:
        return not self.conflicts


def candles_match_exactly(canonical: Candle, incoming: Candle) -> bool:
    """Compare timestamp and OHLCV after approved fixed-point normalization."""
    return _canonical_candle(canonical) == _canonical_candle(incoming)


def compare_source_batch(
    *,
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
    canonical_by_timestamp: dict[datetime, CanonicalSourceObservation],
    incoming_candles: tuple[Candle, ...],
    incoming_attempt_id: UUID | None,
    incoming_ingestion_batch_id: UUID,
    incoming_provider: str,
    retrieved_at: datetime,
    incoming_batch_source_hash: str,
    interval_duration_seconds: int,
) -> SourceBatchComparison:
    reused_count = 0
    conflicts: list[SourceConflictEvidence] = []
    for incoming in incoming_candles:
        timestamp = _required_datetime(incoming.timestamp)
        canonical = canonical_by_timestamp.get(timestamp)
        if canonical is None:
            continue
        if canonical.provider == incoming_provider and candles_match_exactly(
            canonical.candle, incoming
        ):
            reused_count += 1
            continue
        conflicts.append(
            build_source_conflict(
                asset_identifier=asset_identifier,
                quote_currency=quote_currency,
                timeframe=timeframe,
                canonical_candle_id=canonical.candle_id,
                canonical_ingestion_batch_id=canonical.ingestion_batch_id,
                canonical_provider=canonical.provider,
                canonical_candle=canonical.candle,
                incoming_attempt_id=incoming_attempt_id,
                incoming_ingestion_batch_id=incoming_ingestion_batch_id,
                incoming_provider=incoming_provider,
                incoming_candle=incoming,
                retrieved_at=retrieved_at,
                available_at=datetime.fromtimestamp(
                    timestamp.timestamp() + interval_duration_seconds,
                    tz=timezone.utc,
                ),
                incoming_batch_source_hash=incoming_batch_source_hash,
            )
        )
    return SourceBatchComparison(reused_count, tuple(conflicts))


def build_source_conflict(
    *,
    asset_identifier: str,
    quote_currency: str,
    timeframe: CandleTimeframe,
    canonical_candle_id: int,
    canonical_ingestion_batch_id: UUID,
    canonical_provider: str,
    canonical_candle: Candle,
    incoming_attempt_id: UUID | None,
    incoming_ingestion_batch_id: UUID,
    incoming_provider: str,
    incoming_candle: Candle,
    retrieved_at: datetime,
    available_at: datetime,
    incoming_batch_source_hash: str,
) -> SourceConflictEvidence:
    asset = asset_identifier.strip().upper()
    quote = quote_currency.strip().upper()
    if asset != "BTC" or quote != "USD":
        raise SourceConflictIntegrityError(
            "Source-conflict evidence supports only BTC/USD."
        )
    canonical_timestamp = _timestamp(canonical_candle.timestamp)
    incoming_timestamp = _timestamp(incoming_candle.timestamp)
    if canonical_timestamp != incoming_timestamp:
        raise SourceConflictIntegrityError(
            "Conflict evidence must share one canonical timestamp."
        )
    if canonical_candle_id <= 0 or len(incoming_batch_source_hash) != 64:
        raise SourceConflictIntegrityError(
            "Conflict evidence identity or source hash is invalid."
        )
    if canonical_provider != incoming_provider:
        conflict_type = "provider_identity_conflict"
    elif candles_match_exactly(canonical_candle, incoming_candle):
        raise SourceConflictIntegrityError(
            "Exact source replay cannot create conflict evidence."
        )
    else:
        conflict_type = "provider_revision_conflict"

    canonical_hash = candle_evidence_hash(canonical_candle)
    incoming_hash = candle_evidence_hash(incoming_candle)
    payload = {
        "hash_schema_version": CONFLICT_HASH_SCHEMA_VERSION,
        "conflict_type": conflict_type,
        "asset_identifier": asset,
        "quote_currency": quote,
        "timeframe": timeframe.value,
        "candle_timestamp": canonical_timestamp,
        "canonical_provider": canonical_provider,
        "incoming_provider": incoming_provider,
        "canonical_candle_hash": canonical_hash,
        "incoming_candle_hash": incoming_hash,
        "incoming_batch_source_hash": incoming_batch_source_hash,
    }
    return SourceConflictEvidence(
        schema_version=CONFLICT_SCHEMA_VERSION,
        hash_schema_version=CONFLICT_HASH_SCHEMA_VERSION,
        conflict_type=conflict_type,
        asset_identifier=asset,
        quote_currency=quote,
        timeframe=timeframe,
        candle_timestamp=canonical_candle.timestamp,
        canonical_candle_id=canonical_candle_id,
        canonical_ingestion_batch_id=canonical_ingestion_batch_id,
        canonical_provider=canonical_provider,
        canonical_candle=canonical_candle,
        incoming_attempt_id=incoming_attempt_id,
        incoming_ingestion_batch_id=incoming_ingestion_batch_id,
        incoming_provider=incoming_provider,
        incoming_candle=incoming_candle,
        retrieved_at=_utc(retrieved_at),
        available_at=_utc(available_at),
        canonical_candle_hash=canonical_hash,
        incoming_candle_hash=incoming_hash,
        incoming_batch_source_hash=incoming_batch_source_hash,
        conflict_hash=_sha256(payload),
    )


def verify_source_conflict(evidence: SourceConflictEvidence) -> None:
    rebuilt = build_source_conflict(
        asset_identifier=evidence.asset_identifier,
        quote_currency=evidence.quote_currency,
        timeframe=evidence.timeframe,
        canonical_candle_id=evidence.canonical_candle_id,
        canonical_ingestion_batch_id=evidence.canonical_ingestion_batch_id,
        canonical_provider=evidence.canonical_provider,
        canonical_candle=evidence.canonical_candle,
        incoming_attempt_id=evidence.incoming_attempt_id,
        incoming_ingestion_batch_id=evidence.incoming_ingestion_batch_id,
        incoming_provider=evidence.incoming_provider,
        incoming_candle=evidence.incoming_candle,
        retrieved_at=evidence.retrieved_at,
        available_at=evidence.available_at,
        incoming_batch_source_hash=evidence.incoming_batch_source_hash,
    )
    if rebuilt != evidence:
        raise SourceConflictIntegrityError(
            "Source-conflict evidence integrity verification failed."
        )


def candle_evidence_hash(candle: Candle) -> str:
    return _sha256(
        {
            "hash_schema_version": CONFLICT_HASH_SCHEMA_VERSION,
            "candle": _canonical_candle(candle),
        }
    )


def candle_sequence_hash(candles: tuple[Candle, ...]) -> str:
    """Hash ordered candles using the frozen 18-place Decimal contract."""
    return _sha256(
        {
            "hash_schema_version": CONFLICT_HASH_SCHEMA_VERSION,
            "candles": [_canonical_candle(candle) for candle in candles],
        }
    )


def _canonical_candle(candle: Candle) -> dict[str, str]:
    return {
        "timestamp": _timestamp(candle.timestamp),
        "open": _decimal(candle.open),
        "high": _decimal(candle.high),
        "low": _decimal(candle.low),
        "close": _decimal(candle.close),
        "volume": _decimal(candle.volume),
    }


def _decimal(value: Decimal | None) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise SourceConflictIntegrityError(
            "Conflict candle contains an invalid Decimal value."
        )
    with localcontext() as context:
        context.prec = max(80, len(value.as_tuple().digits) + 40)
        quantized = value.quantize(_DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN)
    return format(quantized, "f")


def _timestamp(value: datetime | None) -> str:
    if value is None:
        raise SourceConflictIntegrityError("Conflict candle timestamp is missing.")
    return _utc(value).isoformat(timespec="microseconds")


def _required_datetime(value: datetime | None) -> datetime:
    if value is None:
        raise SourceConflictIntegrityError("Conflict candle timestamp is missing.")
    return _utc(value)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SourceConflictIntegrityError(
            "Conflict timestamps must be timezone-aware."
        )
    return value.astimezone(timezone.utc)


def _sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
