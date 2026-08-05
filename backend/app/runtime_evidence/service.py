"""Repository-backed implementation of the approved runtime evidence policy."""

from dataclasses import dataclass, replace
from datetime import datetime

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ContextStatus,
    EvidenceCategory,
    EvidenceItem,
    EvidencePackage,
    EvidencePolarity,
    EvidenceSeverity,
    FeatureSnapshot,
    FeatureSnapshotValue,
    IntegrityReference,
    MarketContext,
    MarketSnapshot,
    OpportunityCandidate,
    PolicyReference,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    DetectionRepository,
    EntityId,
    EntityNotFoundError,
    EvidenceRepository,
    FeatureSnapshotRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
)
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)


RUNTIME_EVIDENCE_POLICY_ID = "alphalens_runtime_evidence_ema_rsi"
RUNTIME_EVIDENCE_POLICY_VERSION = "1.0.0"
RUNTIME_EVIDENCE_POLICY_HASH = (
    "9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8"
)
_DETECTION_POLICY_ID = "alphalens_runtime_detection_ema_rsi"
_DETECTION_POLICY_VERSION = "1.0.0"
_DETECTION_POLICY_HASH = (
    "d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a"
)
_SCOPE_INSTRUMENT = "BTCUSDT"
_SCOPE_TIMEFRAME = "5m"
_REQUIRED_FEATURES = (
    ("exponential_moving_average_12", "1.0.0", "exponential_moving_average_12"),
    ("exponential_moving_average_26", "1.0.0", "exponential_moving_average_26"),
    ("relative_strength_index", "1.0.0", "relative_strength_index"),
    ("average_true_range", "1.0.0", "true_range"),
)
_PROPOSITION = "opportunity.assessment"
_LIMITATION_CONFIDENCE = "confidence.unavailable"


@dataclass(frozen=True, slots=True)
class _PersistedInputs:
    candidate: OpportunityCandidate
    market: MarketSnapshot
    features: FeatureSnapshot
    context: MarketContext
    candidate_reference: IntegrityReference
    market_reference: IntegrityReference
    feature_reference: IntegrityReference
    context_reference: IntegrityReference
    cutoff: datetime


class RuntimeEvidenceService:
    """Assemble deterministic factual evidence from immutable persisted inputs."""

    def __init__(
        self,
        *,
        candidates: DetectionRepository,
        market_snapshots: MarketSnapshotRepository,
        feature_snapshots: FeatureSnapshotRepository,
        market_contexts: MarketContextRepository,
        evidence: EvidenceRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime evidence code version must be non-empty.")
        self._candidates = candidates
        self._market_snapshots = market_snapshots
        self._feature_snapshots = feature_snapshots
        self._market_contexts = market_contexts
        self._evidence = evidence
        self._code_version = code_version

    async def assemble(
        self,
        candidate: OpportunityCandidate,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
        market_context: MarketContext,
    ) -> EvidencePackage:
        """Verify persisted lineage and persist one complete evidence package."""
        inputs = await self._load_persisted_inputs(
            candidate,
            market_snapshot,
            feature_snapshot,
            market_context,
        )
        _validate_inputs(inputs)
        values = _required_values(inputs.features)
        items = _build_items(inputs, values)
        package_id = f"evidence.runtime.ema_rsi.{candidate.candidate_id}"
        lineage_hash = canonical_sha256(
            (
                inputs.candidate_reference,
                inputs.market_reference,
                inputs.feature_reference,
                inputs.context_reference,
            )
        )
        package_hash = canonical_sha256(
            {
                "package_id": package_id,
                "candidate_id": candidate.candidate_id,
                "policy": _evidence_policy(),
                "items": tuple(item.integrity_digest for item in items),
                "limitations": (_LIMITATION_CONFIDENCE,),
                "lineage_hash": lineage_hash,
            }
        )
        package = EvidencePackage(
            contract_version="1.0.0",
            package_id=package_id,
            candidate_id=candidate.candidate_id,
            assessment_id=None,
            items=items,
            limitations=(_LIMITATION_CONFIDENCE,),
            audit=AuditMetadata(
                created_at=inputs.cutoff,
                evidence_cutoff=candidate.audit.evidence_cutoff,
                available_at=inputs.cutoff,
                provenance=Provenance(
                    source_references=(
                        inputs.candidate_reference,
                        inputs.market_reference,
                        inputs.feature_reference,
                        inputs.context_reference,
                    ),
                    policy_references=(_evidence_policy(),),
                    code_version=self._code_version,
                    configuration_hash=RUNTIME_EVIDENCE_POLICY_HASH,
                    lineage_hash=lineage_hash,
                ),
                result_hash=package_hash,
            ),
        )
        return await self._evidence.save(package)

    async def _load_persisted_inputs(
        self,
        candidate: OpportunityCandidate,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
        market_context: MarketContext,
    ) -> _PersistedInputs:
        try:
            persisted_candidate = await self._candidates.get_candidate_by_id(
                EntityId(candidate.candidate_id)
            )
            market = await self._market_snapshots.get_by_id(
                EntityId(market_snapshot.snapshot_id)
            )
            features = await self._feature_snapshots.get_by_id(
                EntityId(feature_snapshot.snapshot_id)
            )
            context = await self._market_contexts.get_by_id(
                EntityId(market_context.context_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Evidence requires all referenced persisted artifacts."
            ) from error
        for supplied, persisted, label in (
            (candidate, persisted_candidate, "candidate"),
            (market_snapshot, market, "market snapshot"),
            (feature_snapshot, features, "feature snapshot"),
            (market_context, context, "market context"),
        ):
            if supplied.canonical_sha256() != persisted.canonical_sha256():
                raise ServiceContractError(
                    f"Persisted {label} conflicts with evidence input."
                )
        candidate_reference = _reference(
            candidate.candidate_id, "opportunity_candidate", candidate
        )
        market_reference = _reference(market.snapshot_id, "market_snapshot", market)
        feature_reference = _reference(
            features.snapshot_id, "feature_snapshot", features
        )
        context_reference = _reference(context.context_id, "market_context", context)
        return _PersistedInputs(
            candidate=persisted_candidate,
            market=market,
            features=features,
            context=context,
            candidate_reference=candidate_reference,
            market_reference=market_reference,
            feature_reference=feature_reference,
            context_reference=context_reference,
            cutoff=max(
                candidate.audit.evidence_cutoff,
                market.audit.available_at,
                features.audit.available_at,
                context.audit.available_at,
            ),
        )


def _validate_inputs(inputs: _PersistedInputs) -> None:
    candidate, market, features, context = (
        inputs.candidate,
        inputs.market,
        inputs.features,
        inputs.context,
    )
    candle = market.candles[0] if len(market.candles) == 1 else None
    if (
        candidate.scope.instrument != _SCOPE_INSTRUMENT
        or candidate.scope.timeframe != _SCOPE_TIMEFRAME
        or market.scope != candidate.scope
        or features.scope != candidate.scope
        or context.scope != candidate.scope
        or candle is None
        or not market.complete
        or candidate.detection_policy.policy_id != _DETECTION_POLICY_ID
        or candidate.detection_policy.policy_version != _DETECTION_POLICY_VERSION
        or candidate.detection_policy.integrity_digest != _DETECTION_POLICY_HASH
        or candidate.market_snapshot_reference != inputs.market_reference
        or candidate.feature_snapshot_reference != inputs.feature_reference
        or candidate.context_reference != inputs.context_reference
        or context.context_timeframes != (_SCOPE_TIMEFRAME,)
        or context.data_quality.status is not ContextStatus.AVAILABLE
        or len(context.data_quality.observations) != 1
        or context.data_quality.observations[0].semantic_identifier
        != "data_quality.persisted_inputs_verified"
        or context.data_quality.observations[0].value is not True
    ):
        raise ServiceUnavailableError("Evidence inputs fail closed validation.")
    if any(
        reference.available_at > candidate.audit.evidence_cutoff
        for reference in (
            inputs.candidate_reference,
            inputs.market_reference,
            inputs.feature_reference,
            inputs.context_reference,
        )
    ):
        raise ServiceUnavailableError("Evidence input is unavailable at cutoff.")
    _required_values(features, candle.timestamp)


def _required_values(
    features: FeatureSnapshot,
    timestamp: datetime | None = None,
) -> dict[tuple[str, str, str], FeatureSnapshotValue]:
    values = {
        (item.feature_identifier, item.definition_version, item.output_name): item
        for item in features.values
        if (item.feature_identifier, item.definition_version, item.output_name)
        in _REQUIRED_FEATURES
    }
    if len(values) != len(_REQUIRED_FEATURES):
        raise ServiceUnavailableError("Evidence required feature is unavailable.")
    if timestamp is not None and any(
        item.candle_timestamp != timestamp for item in values.values()
    ):
        raise ServiceUnavailableError("Evidence feature timestamp is stale.")
    return values


def _build_items(
    inputs: _PersistedInputs,
    values: dict[tuple[str, str, str], FeatureSnapshotValue],
) -> tuple[EvidenceItem, ...]:
    candle = inputs.market.candles[0]
    source_values = {
        "market_price_close": (inputs.market_reference, "price", candle.close),
        "market_volume": (inputs.market_reference, "volume", candle.volume),
        "ema_12": (
            values[_REQUIRED_FEATURES[0]].feature_record,
            "price",
            values[_REQUIRED_FEATURES[0]].value,
        ),
        "ema_26": (
            values[_REQUIRED_FEATURES[1]].feature_record,
            "price",
            values[_REQUIRED_FEATURES[1]].value,
        ),
        "rsi": (
            values[_REQUIRED_FEATURES[2]].feature_record,
            "ratio",
            values[_REQUIRED_FEATURES[2]].value,
        ),
        "atr_true_range": (
            values[_REQUIRED_FEATURES[3]].feature_record,
            "price",
            values[_REQUIRED_FEATURES[3]].value,
        ),
    }
    alignment = (
        "detection.ema12_above_ema26" in inputs.candidate.reason_codes
        or "detection.ema12_below_ema26" in inputs.candidate.reason_codes
    )
    if "detection.rsi_ge_55" in inputs.candidate.reason_codes:
        rsi_state = "buy_threshold_met"
    elif "detection.rsi_le_45" in inputs.candidate.reason_codes:
        rsi_state = "sell_threshold_met"
    else:
        rsi_state = "threshold_not_met"
    source_values.update(
        {
            "ema_alignment": (inputs.candidate_reference, None, alignment),
            "rsi_state": (inputs.candidate_reference, None, rsi_state),
            "market_structure": (
                inputs.context_reference,
                None,
                "unavailable",
            ),
        }
    )
    items = []
    for key, (source, unit, observed) in source_values.items():
        available_at = source.available_at
        limitations = (
            ("context.structure.unavailable",)
            if key == "market_structure"
            else (
                ("policy_trace.only",) if key in {"ema_alignment", "rsi_state"} else ()
            )
        )
        item_id = f"evidence.runtime.ema_rsi.{inputs.candidate.candidate_id}.{key}"
        item = EvidenceItem(
            taxonomy_version="1.0.0",
            evidence_id=item_id,
            evidence_type=f"runtime_{key}",
            category=_category(key),
            description_code=f"evidence.{key}",
            source_reference=source,
            source_definition=_source_definition(key),
            polarity=EvidencePolarity.CONTEXTUAL,
            proposition=_PROPOSITION,
            severity=EvidenceSeverity.INFORMATIONAL,
            observed_value=observed,
            unit=unit,
            scope=inputs.market.scope,
            time_start=inputs.market.candles[0].timestamp,
            time_end=inputs.market.candles[0].timestamp,
            available_at=available_at,
            price_scope=None,
            limitations=limitations,
            integrity_digest="0" * 64,
        )
        items.append(
            replace(
                item,
                integrity_digest=canonical_sha256(
                    item, exclude=frozenset({"integrity_digest"})
                ),
            )
        )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.category.value,
                item.proposition,
                item.available_at,
                item.source_reference.artifact_id,
                item.evidence_id,
            ),
        )
    )


def _category(key: str) -> EvidenceCategory:
    return {
        "market_price_close": EvidenceCategory.MARKET_PRICE,
        "market_volume": EvidenceCategory.MARKET_VOLUME,
        "ema_12": EvidenceCategory.FEATURE_TREND,
        "ema_26": EvidenceCategory.FEATURE_TREND,
        "rsi": EvidenceCategory.FEATURE_MOMENTUM,
        "atr_true_range": EvidenceCategory.FEATURE_VOLATILITY,
        "ema_alignment": EvidenceCategory.POLICY_TRACE,
        "rsi_state": EvidenceCategory.POLICY_TRACE,
        "market_structure": EvidenceCategory.CONTEXT_STRUCTURE,
    }[key]


def _source_definition(key: str) -> str:
    return {
        "market_price_close": "market_snapshot.candle.close",
        "market_volume": "market_snapshot.candle.volume",
        "ema_12": "exponential_moving_average_12:1.0.0:exponential_moving_average_12",
        "ema_26": "exponential_moving_average_26:1.0.0:exponential_moving_average_26",
        "rsi": "relative_strength_index:1.0.0:relative_strength_index",
        "atr_true_range": "average_true_range:1.0.0:true_range",
        "ema_alignment": "alphalens_runtime_detection_ema_rsi:1.0.0",
        "rsi_state": "alphalens_runtime_detection_ema_rsi:1.0.0",
        "market_structure": "market_context.structure",
    }[key]


def _reference(
    artifact_id: str,
    artifact_type: str,
    entity: OpportunityCandidate | MarketSnapshot | FeatureSnapshot | MarketContext,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest=entity.canonical_sha256(),
        available_at=entity.audit.available_at,
    )


def _evidence_policy() -> PolicyReference:
    return PolicyReference(
        policy_id=RUNTIME_EVIDENCE_POLICY_ID,
        policy_version=RUNTIME_EVIDENCE_POLICY_VERSION,
        integrity_digest=RUNTIME_EVIDENCE_POLICY_HASH,
    )
