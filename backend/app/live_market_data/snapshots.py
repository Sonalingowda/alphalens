"""Mapping from validated live candles to frozen market snapshot contracts."""

from datetime import datetime
from hashlib import sha256
import json

from app.live_market_data.models import CompletedCandle, LIVE_INGESTION_VERSION
from app.opportunity_intelligence.domain import (
    AuditMetadata,
    IntegrityReference,
    MarketCandleSnapshot,
    MarketScope,
    MarketSnapshot,
    Provenance,
)


CONFIGURATION_HASH = sha256(
    b"alphalens.live.binance_spot.BTCUSDT.5m-derived10m-15m.v1"
).hexdigest()


def build_market_snapshot(
    candle: CompletedCandle,
    *,
    code_version: str,
) -> MarketSnapshot:
    """Build a deterministic single-candle immutable market snapshot."""
    if not code_version.strip():
        raise ValueError("Live ingestion code version must be non-empty.")
    open_milliseconds = _epoch_milliseconds(candle.open_time)
    prefix = (
        f"binance.spot.{candle.symbol}.{candle.timeframe.value}."
        f"{open_milliseconds}"
    )
    source = IntegrityReference(
        artifact_id=f"{prefix}.source",
        artifact_type="binance_spot_completed_kline",
        artifact_version=LIVE_INGESTION_VERSION,
        integrity_digest=candle.source_payload_hash,
        available_at=candle.event_time,
    )
    lineage_payload = {
        "source": candle.source_payload_hash,
        "members": candle.source_candle_hashes,
        "version": LIVE_INGESTION_VERSION,
    }
    lineage_hash = _hash(lineage_payload)
    result_hash = _hash(
        {
            "configuration_hash": CONFIGURATION_HASH,
            "lineage_hash": lineage_hash,
            "open": format(candle.open, "f"),
            "high": format(candle.high, "f"),
            "low": format(candle.low, "f"),
            "close": format(candle.close, "f"),
            "volume": format(candle.volume, "f"),
            "open_time": candle.open_time.isoformat(),
            "close_time": candle.close_time.isoformat(),
            "number_of_trades": candle.number_of_trades,
        }
    )
    audit = AuditMetadata(
        created_at=candle.event_time,
        evidence_cutoff=candle.event_time,
        available_at=candle.event_time,
        provenance=Provenance(
            source_references=(source,),
            policy_references=(),
            code_version=code_version,
            configuration_hash=CONFIGURATION_HASH,
            lineage_hash=lineage_hash,
        ),
        result_hash=result_hash,
    )
    market_candle = MarketCandleSnapshot(
        candle_id=f"{prefix}.candle",
        timestamp=candle.open_time,
        available_at=candle.event_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        source_reference=source,
    )
    return MarketSnapshot(
        contract_version="1.0.0",
        snapshot_id=f"{prefix}.snapshot",
        scope=MarketScope(
            instrument=candle.symbol,
            timeframe=candle.timeframe.value,
        ),
        candles=(market_candle,),
        complete=True,
        audit=audit,
    )


def _hash(payload: object) -> str:
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _epoch_milliseconds(value: datetime) -> int:
    timestamp = value.timestamp()
    return int(timestamp) * 1000 + value.microsecond // 1000
