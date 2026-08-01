"""Runtime adapter from closed market snapshots to approved feature snapshots."""

from datetime import datetime
from hashlib import sha256
import json
from uuid import NAMESPACE_URL, uuid5

from app.features.atr import ATR_FEATURE_METADATA
from app.features.directional_movement import DIRECTIONAL_MOVEMENT_FEATURE_METADATA
from app.features.ema import EMA_FEATURE_METADATA
from app.features.intraday_pipeline import (
    PipelineFeatureDependency,
    PipelineFeatureValue,
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.features.macd import MACD_FEATURE_METADATA
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.features.rsi import RSI_FEATURE_METADATA
from app.features.statistical_volatility import BOLLINGER_IDENTIFIER
from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import timeframe_duration
from app.opportunity_intelligence.domain import (
    AuditMetadata,
    FeatureSnapshot,
    FeatureSnapshotValue,
    IntegrityReference,
    MarketSnapshot,
    Provenance,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
    FeatureSnapshotRepository,
    MarketSnapshotRepository,
    ScopedRepositoryQuery,
)
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)


RUNTIME_FEATURE_ENGINE_VERSION = "1.0.0"
_PAGE_SIZE = 1000
_EMA_IDENTIFIERS = frozenset(item.identifier for item in EMA_FEATURE_METADATA)
_ADX_IDENTIFIERS = frozenset(
    item.identifier for item in DIRECTIONAL_MOVEMENT_FEATURE_METADATA
)
_PUBLIC_DEFINITION_IDENTIFIERS = frozenset(
    {
        ATR_FEATURE_METADATA[0].identifier,
        RSI_FEATURE_METADATA[0].identifier,
        MACD_FEATURE_METADATA[0].identifier,
        BOLLINGER_IDENTIFIER,
    }
) | _EMA_IDENTIFIERS | _ADX_IDENTIFIERS
_CONFIGURATION_HASH = sha256(
    json.dumps(
        {
            "engine_version": RUNTIME_FEATURE_ENGINE_VERSION,
            "registry_hash": INTRADAY_FEATURE_REGISTRY.configuration_hash,
            "published_definitions": sorted(_PUBLIC_DEFINITION_IDENTIFIERS),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


class FeatureWarmupIncompleteError(ServiceUnavailableError):
    """Raised when no approved requested output is valid at the candle yet."""


class RuntimeFeatureEngine:
    """Compute approved indicators for one persisted completed candle prefix."""

    def __init__(
        self,
        *,
        market_snapshots: MarketSnapshotRepository,
        feature_snapshots: FeatureSnapshotRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime feature code version must be non-empty.")
        self._market_snapshots = market_snapshots
        self._feature_snapshots = feature_snapshots
        self._code_version = code_version

    async def resolve(self, market_snapshot: MarketSnapshot) -> FeatureSnapshot:
        """Compute and persist features at one closed market snapshot."""
        _validate_market_snapshot(market_snapshot)
        await self._verify_persisted_input(market_snapshot)
        history = await self._load_prefix(market_snapshot)
        source = _build_source(history, market_snapshot.scope.timeframe)
        pipeline_result = run_intraday_feature_pipeline(source)
        current_timestamp = market_snapshot.candles[0].timestamp
        current_values = tuple(
            value
            for value in pipeline_result.values
            if value.candle_timestamp == current_timestamp
            and value.feature_identifier in _PUBLIC_DEFINITION_IDENTIFIERS
        )
        if not current_values:
            raise FeatureWarmupIncompleteError(
                "No requested approved feature is valid at this warm-up prefix."
            )
        snapshot = _build_feature_snapshot(
            market_snapshot=market_snapshot,
            history=history,
            pipeline_values=current_values,
            pipeline_dependencies=pipeline_result.dependency_memberships,
            pipeline_result_hash=pipeline_result.result_hash,
            code_version=self._code_version,
        )
        return await self._feature_snapshots.save(snapshot)

    async def _verify_persisted_input(self, snapshot: MarketSnapshot) -> None:
        try:
            stored = await self._market_snapshots.get_by_id(
                EntityId(snapshot.snapshot_id)
            )
        except EntityNotFoundError as error:
            raise ServiceContractError(
                "Feature computation requires a persisted market snapshot."
            ) from error
        if stored.canonical_sha256() != snapshot.canonical_sha256():
            raise ServiceContractError(
                "Market snapshot conflicts with its immutable persisted identity."
            )

    async def _load_prefix(
        self,
        current: MarketSnapshot,
    ) -> tuple[MarketSnapshot, ...]:
        items: list[MarketSnapshot] = []
        cursor: str | None = None
        while True:
            page = await self._market_snapshots.get_by_scope(
                ScopedRepositoryQuery(
                    scope=current.scope,
                    as_of=current.audit.evidence_cutoff,
                    limit=_PAGE_SIZE,
                    cursor=cursor,
                )
            )
            items.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                break
        prefix = tuple(
            sorted(
                (
                    item
                    for item in items
                    if item.candles[0].timestamp <= current.candles[0].timestamp
                ),
                key=lambda item: (
                    item.candles[0].timestamp,
                    item.snapshot_id,
                ),
            )
        )
        if not prefix or prefix[-1].snapshot_id != current.snapshot_id:
            raise ServiceContractError(
                "Market history does not terminate at the requested snapshot."
            )
        timestamps = tuple(item.candles[0].timestamp for item in prefix)
        if len(timestamps) != len(set(timestamps)):
            raise ServiceContractError(
                "Market history contains multiple snapshots for one candle."
            )
        return prefix


def _validate_market_snapshot(snapshot: MarketSnapshot) -> None:
    if not isinstance(snapshot, MarketSnapshot):
        raise ServiceContractError("Feature engine requires MarketSnapshot input.")
    if snapshot.scope.instrument != "BTCUSDT":
        raise ServiceContractError("Runtime features support only BTCUSDT.")
    try:
        timeframe = CandleTimeframe(snapshot.scope.timeframe)
    except ValueError as error:
        raise ServiceContractError("Runtime feature timeframe is unsupported.") from error
    if timeframe not in {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    }:
        raise ServiceContractError("Runtime feature timeframe is unsupported.")
    if not snapshot.complete or len(snapshot.candles) != 1:
        raise ServiceContractError(
            "Runtime feature input must contain one completed candle."
        )
    candle = snapshot.candles[0]
    closed_at = candle.timestamp + timeframe_duration(timeframe)
    if candle.available_at < closed_at or snapshot.audit.evidence_cutoff < closed_at:
        raise ServiceContractError(
            "Runtime features cannot execute before the candle closes."
        )


def _build_source(
    history: tuple[MarketSnapshot, ...],
    timeframe_value: str,
):
    timeframe = CandleTimeframe(timeframe_value)
    observations = tuple(
        SourceCandleObservation(
            candle=Candle(
                timestamp=item.candles[0].timestamp,
                open=item.candles[0].open,
                high=item.candles[0].high,
                low=item.candles[0].low,
                close=item.candles[0].close,
                volume=item.candles[0].volume,
            ),
            ingestion_batch_id=uuid5(NAMESPACE_URL, item.snapshot_id),
            is_complete=item.complete,
        )
        for item in history
    )
    return build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USDT",
        timeframe=timeframe,
        observations=observations,
    )


def _build_feature_snapshot(
    *,
    market_snapshot: MarketSnapshot,
    history: tuple[MarketSnapshot, ...],
    pipeline_values: tuple[PipelineFeatureValue, ...],
    pipeline_dependencies: tuple[PipelineFeatureDependency, ...],
    pipeline_result_hash: str,
    code_version: str,
) -> FeatureSnapshot:
    current = market_snapshot.candles[0]
    market_reference = IntegrityReference(
        artifact_id=market_snapshot.snapshot_id,
        artifact_type="market_snapshot",
        artifact_version="1.0.0",
        integrity_digest=market_snapshot.canonical_sha256(),
        available_at=market_snapshot.audit.available_at,
    )
    dependency_by_consumer: dict[
        tuple[str, str, str, datetime], list[PipelineFeatureDependency]
    ] = {}
    for dependency in pipeline_dependencies:
        identity = (
            dependency.consumer_feature_identifier,
            dependency.consumer_definition_version,
            dependency.consumer_output_name,
            dependency.consumer_candle_timestamp,
        )
        dependency_by_consumer.setdefault(identity, []).append(dependency)

    feature_values = []
    for value in pipeline_values:
        identity = (
            value.feature_identifier,
            value.definition_version,
            value.output_name,
            value.candle_timestamp,
        )
        record_digest = _hash(
            {
                "pipeline_result_hash": pipeline_result_hash,
                "feature_identifier": value.feature_identifier,
                "definition_version": value.definition_version,
                "output_name": value.output_name,
                "candle_timestamp": _timestamp(value.candle_timestamp),
                "available_at": _timestamp(value.available_at),
                "value": format(value.value, "f"),
                "dependencies": [
                    _dependency_payload(item)
                    for item in dependency_by_consumer.get(identity, ())
                ],
            }
        )
        feature_values.append(
            FeatureSnapshotValue(
                feature_identifier=value.feature_identifier,
                definition_version=value.definition_version,
                output_name=value.output_name,
                candle_timestamp=value.candle_timestamp,
                available_at=value.available_at,
                value=value.value,
                feature_record=IntegrityReference(
                    artifact_id=(
                        f"feature.runtime.{market_snapshot.scope.instrument}."
                        f"{market_snapshot.scope.timeframe}."
                        f"{int(current.timestamp.timestamp())}."
                        f"{value.feature_identifier}.{value.output_name}"
                    ),
                    artifact_type="runtime_feature_value",
                    artifact_version=value.definition_version,
                    integrity_digest=record_digest,
                    available_at=value.available_at,
                ),
            )
        )
    ordered_values = tuple(
        sorted(
            feature_values,
            key=lambda item: (
                item.feature_identifier,
                item.definition_version,
                item.output_name,
                item.candle_timestamp,
            ),
        )
    )
    available_at = max(
        market_snapshot.audit.available_at,
        *(item.available_at for item in ordered_values),
    )
    lineage_hash = _hash(
        {
            "market_history": [
                {
                    "snapshot_id": item.snapshot_id,
                    "digest": item.canonical_sha256(),
                }
                for item in history
            ],
            "pipeline_result_hash": pipeline_result_hash,
        }
    )
    result_hash = _hash(
        {
            "market_snapshot": market_reference.integrity_digest,
            "registry_hash": INTRADAY_FEATURE_REGISTRY.configuration_hash,
            "values": [item.to_dict() for item in ordered_values],
            "lineage_hash": lineage_hash,
        }
    )
    source_references = (market_reference,) + tuple(
        item.feature_record for item in ordered_values
    )
    snapshot_id = (
        f"feature.runtime.{market_snapshot.scope.instrument}."
        f"{market_snapshot.scope.timeframe}."
        f"{int(current.timestamp.timestamp())}"
    )
    return FeatureSnapshot(
        contract_version="1.0.0",
        snapshot_id=snapshot_id,
        scope=market_snapshot.scope,
        market_snapshot=market_reference,
        registry_hash=INTRADAY_FEATURE_REGISTRY.configuration_hash,
        values=ordered_values,
        audit=AuditMetadata(
            created_at=available_at,
            evidence_cutoff=available_at,
            available_at=available_at,
            provenance=Provenance(
                source_references=source_references,
                policy_references=(),
                code_version=code_version,
                configuration_hash=_CONFIGURATION_HASH,
                lineage_hash=lineage_hash,
            ),
            result_hash=result_hash,
        ),
    )


def _dependency_payload(value: PipelineFeatureDependency) -> dict[str, object]:
    return {
        "ordinal": value.dependency_ordinal,
        "feature_identifier": value.dependency_feature_identifier,
        "definition_version": value.dependency_definition_version,
        "output_name": value.dependency_output_name,
        "candle_timestamp": _timestamp(value.dependency_candle_timestamp),
        "available_at": _timestamp(value.dependency_available_at),
        "value": format(value.dependency_value, "f"),
    }


def _hash(payload: object) -> str:
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
