"""Repository-backed implementation of Assessment Policy v1.0.1."""

from dataclasses import dataclass, replace

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ContextStatus,
    EvidenceCategory,
    EvidencePackage,
    FeatureSnapshot,
    IntegrityReference,
    MarketContext,
    MarketSnapshot,
    Opportunity,
    OpportunityCandidate,
    OpportunityStance,
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
    OpportunityRepository,
)
from app.opportunity_intelligence.services import (
    PolicyUnavailableError,
    ServiceContractError,
    ServiceUnavailableError,
)


RUNTIME_ASSESSMENT_POLICY_ID = "alphalens_runtime_assessment_ema_rsi"
RUNTIME_ASSESSMENT_POLICY_VERSION = "1.0.1"
RUNTIME_ASSESSMENT_POLICY_HASH = (
    "4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d"
)
_DETECTION_POLICY_ID = "alphalens_runtime_detection_ema_rsi"
_DETECTION_POLICY_VERSION = "1.0.0"
_DETECTION_POLICY_HASH = (
    "d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a"
)
_EVIDENCE_POLICY_ID = "alphalens_runtime_evidence_ema_rsi"
_EVIDENCE_POLICY_VERSION = "1.0.0"
_EVIDENCE_POLICY_HASH = (
    "9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8"
)
_SCOPE_INSTRUMENT = "BTCUSDT"
_SCOPE_TIMEFRAME = "5m"
_REQUIRED_EVIDENCE = {
    "market_price_close": (
        EvidenceCategory.MARKET_PRICE,
        "market_snapshot.candle.close",
    ),
    "market_volume": (EvidenceCategory.MARKET_VOLUME, "market_snapshot.candle.volume"),
    "ema_12": (
        EvidenceCategory.FEATURE_TREND,
        "exponential_moving_average_12:1.0.0:exponential_moving_average_12",
    ),
    "ema_26": (
        EvidenceCategory.FEATURE_TREND,
        "exponential_moving_average_26:1.0.0:exponential_moving_average_26",
    ),
    "rsi": (
        EvidenceCategory.FEATURE_MOMENTUM,
        "relative_strength_index:1.0.0:relative_strength_index",
    ),
    "atr_true_range": (
        EvidenceCategory.FEATURE_VOLATILITY,
        "average_true_range:1.0.0:true_range",
    ),
    "ema_alignment": (
        EvidenceCategory.POLICY_TRACE,
        "alphalens_runtime_detection_ema_rsi:1.0.0",
    ),
    "rsi_state": (
        EvidenceCategory.POLICY_TRACE,
        "alphalens_runtime_detection_ema_rsi:1.0.0",
    ),
    "market_structure": (
        EvidenceCategory.CONTEXT_STRUCTURE,
        "market_context.structure",
    ),
}
_BUY_REASONS = (
    "detection.persisted_inputs_verified",
    "detection.ema12_above_ema26",
    "detection.rsi_ge_55",
)
_SELL_REASONS = (
    "detection.persisted_inputs_verified",
    "detection.ema12_below_ema26",
    "detection.rsi_le_45",
)


@dataclass(frozen=True, slots=True)
class _PersistedInputs:
    candidate: OpportunityCandidate
    evidence: EvidencePackage
    market: MarketSnapshot
    features: FeatureSnapshot
    context: MarketContext
    candidate_reference: IntegrityReference
    evidence_reference: IntegrityReference
    market_reference: IntegrityReference
    feature_reference: IntegrityReference
    context_reference: IntegrityReference


class RuntimeAssessmentService:
    """Persist a deterministic canonical Opportunity from immutable runtime input."""

    def __init__(
        self,
        *,
        candidates: DetectionRepository,
        evidence: EvidenceRepository,
        market_snapshots: MarketSnapshotRepository,
        feature_snapshots: FeatureSnapshotRepository,
        market_contexts: MarketContextRepository,
        opportunities: OpportunityRepository,
        code_version: str,
        policy: PolicyReference | None = None,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime assessment code version must be non-empty.")
        self._candidates = candidates
        self._evidence = evidence
        self._market_snapshots = market_snapshots
        self._feature_snapshots = feature_snapshots
        self._market_contexts = market_contexts
        self._opportunities = opportunities
        self._code_version = code_version
        self._policy = policy if policy is not None else _assessment_policy()

    async def assess(
        self,
        candidate: OpportunityCandidate,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> Opportunity:
        """Validate persisted evidence lineage and save one immutable assessment."""
        _validate_policy(self._policy)
        inputs = await self._load_persisted_inputs(candidate, evidence, market_context)
        _validate_inputs(inputs)
        stance, reason_codes = _decision(inputs)
        opportunity = _build_opportunity(
            inputs,
            stance=stance,
            reason_codes=reason_codes,
            policy=self._policy,
            code_version=self._code_version,
        )
        return await self._opportunities.save(opportunity)

    async def _load_persisted_inputs(
        self,
        candidate: OpportunityCandidate,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> _PersistedInputs:
        try:
            persisted_candidate = await self._candidates.get_candidate_by_id(
                EntityId(candidate.candidate_id)
            )
            persisted_evidence = await self._evidence.get_by_candidate_id(
                EntityId(candidate.candidate_id)
            )
            context = await self._market_contexts.get_by_id(
                EntityId(market_context.context_id)
            )
            market = await self._market_snapshots.get_by_id(
                EntityId(persisted_candidate.market_snapshot_reference.artifact_id)
            )
            features = await self._feature_snapshots.get_by_id(
                EntityId(persisted_candidate.feature_snapshot_reference.artifact_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Assessment requires all referenced persisted artifacts."
            ) from error

        for supplied, persisted, label in (
            (candidate, persisted_candidate, "candidate"),
            (evidence, persisted_evidence, "evidence package"),
            (market_context, context, "market context"),
        ):
            if supplied.canonical_sha256() != persisted.canonical_sha256():
                raise ServiceContractError(
                    f"Persisted {label} conflicts with assessment input."
                )

        return _PersistedInputs(
            candidate=persisted_candidate,
            evidence=persisted_evidence,
            market=market,
            features=features,
            context=context,
            candidate_reference=_reference(
                persisted_candidate.candidate_id,
                "opportunity_candidate",
                persisted_candidate,
            ),
            evidence_reference=_reference(
                persisted_evidence.package_id,
                "evidence_package",
                persisted_evidence,
            ),
            market_reference=_reference(market.snapshot_id, "market_snapshot", market),
            feature_reference=_reference(
                features.snapshot_id,
                "feature_snapshot",
                features,
            ),
            context_reference=_reference(context.context_id, "market_context", context),
        )


def _validate_policy(policy: PolicyReference) -> None:
    if policy != _assessment_policy():
        raise PolicyUnavailableError("Assessment policy v1.0.1 is unavailable.")


def _validate_inputs(inputs: _PersistedInputs) -> None:
    candidate, evidence, market, features, context = (
        inputs.candidate,
        inputs.evidence,
        inputs.market,
        inputs.features,
        inputs.context,
    )
    cutoff = candidate.audit.evidence_cutoff
    candle = market.candles[0] if len(market.candles) == 1 else None
    evidence_policy = evidence.audit.provenance.policy_references
    if (
        candidate.scope.instrument != _SCOPE_INSTRUMENT
        or candidate.scope.timeframe != _SCOPE_TIMEFRAME
        or market.scope != candidate.scope
        or features.scope != candidate.scope
        or context.scope != candidate.scope
        or candle is None
        or not market.complete
        or candidate.detection_policy
        != PolicyReference(
            _DETECTION_POLICY_ID,
            _DETECTION_POLICY_VERSION,
            _DETECTION_POLICY_HASH,
        )
        or evidence.assessment_id is not None
        or evidence.candidate_id != candidate.candidate_id
        or evidence.package_id != f"evidence.runtime.ema_rsi.{candidate.candidate_id}"
        or evidence_policy != (_evidence_policy(),)
        or candidate.market_snapshot_reference != inputs.market_reference
        or candidate.feature_snapshot_reference != inputs.feature_reference
        or candidate.context_reference != inputs.context_reference
        or features.market_snapshot != inputs.market_reference
        or context.context_timeframes != (_SCOPE_TIMEFRAME,)
        or context.data_quality.status is not ContextStatus.AVAILABLE
        or len(context.data_quality.observations) != 1
        or context.data_quality.observations[0].semantic_identifier
        != "data_quality.persisted_inputs_verified"
        or context.data_quality.observations[0].value is not True
        or evidence.audit.evidence_cutoff != cutoff
    ):
        raise ServiceContractError("Assessment inputs fail closed validation.")
    references = (
        inputs.candidate_reference,
        inputs.evidence_reference,
        inputs.market_reference,
        inputs.feature_reference,
        inputs.context_reference,
    )
    if any(reference.available_at > cutoff for reference in references):
        raise ServiceUnavailableError("Assessment input is unavailable at cutoff.")
    if any(item.available_at > cutoff for item in evidence.items):
        raise ServiceUnavailableError("Assessment evidence is unavailable at cutoff.")
    if any(value.candle_timestamp != candle.timestamp for value in features.values):
        raise ServiceUnavailableError("Assessment feature input is stale.")
    if any(
        observation.time_start != candle.timestamp
        or observation.time_end != candle.timestamp
        for observation in context.data_quality.observations
    ):
        raise ServiceUnavailableError("Assessment context input is stale.")
    _validate_evidence(inputs)


def _validate_evidence(inputs: _PersistedInputs) -> None:
    items = {
        item.evidence_id.rsplit(".", 1)[-1]: item for item in inputs.evidence.items
    }
    if len(items) != len(_REQUIRED_EVIDENCE) or set(items) != set(_REQUIRED_EVIDENCE):
        raise ServiceContractError("Assessment evidence records are incomplete.")
    candle = inputs.market.candles[0]
    expected_sources = {
        "market_price_close": inputs.market_reference,
        "market_volume": inputs.market_reference,
        "ema_alignment": inputs.candidate_reference,
        "rsi_state": inputs.candidate_reference,
        "market_structure": inputs.context_reference,
    }
    feature_values = {
        (value.feature_identifier, value.definition_version, value.output_name): value
        for value in inputs.features.values
    }
    for key, feature_key in (
        (
            "ema_12",
            ("exponential_moving_average_12", "1.0.0", "exponential_moving_average_12"),
        ),
        (
            "ema_26",
            ("exponential_moving_average_26", "1.0.0", "exponential_moving_average_26"),
        ),
        ("rsi", ("relative_strength_index", "1.0.0", "relative_strength_index")),
        ("atr_true_range", ("average_true_range", "1.0.0", "true_range")),
    ):
        try:
            expected_sources[key] = feature_values[feature_key].feature_record
        except KeyError as error:
            raise ServiceUnavailableError(
                "Assessment feature input is unavailable."
            ) from error
    expected_values = {
        "market_price_close": candle.close,
        "market_volume": candle.volume,
        "ema_12": feature_values[
            ("exponential_moving_average_12", "1.0.0", "exponential_moving_average_12")
        ].value,
        "ema_26": feature_values[
            ("exponential_moving_average_26", "1.0.0", "exponential_moving_average_26")
        ].value,
        "rsi": feature_values[
            ("relative_strength_index", "1.0.0", "relative_strength_index")
        ].value,
        "atr_true_range": feature_values[
            ("average_true_range", "1.0.0", "true_range")
        ].value,
        "ema_alignment": True,
        "rsi_state": _expected_rsi_state(inputs.candidate.reason_codes),
        "market_structure": "unavailable",
    }
    for key, item in items.items():
        category, source_definition = _REQUIRED_EVIDENCE[key]
        if (
            item.category is not category
            or item.source_definition != source_definition
            or item.source_reference != expected_sources[key]
            or item.observed_value != expected_values[key]
            or item.scope != inputs.candidate.scope
            or item.time_start != candle.timestamp
            or item.time_end != candle.timestamp
            or item.available_at != item.source_reference.available_at
            or item.integrity_digest
            != canonical_sha256(item, exclude=frozenset({"integrity_digest"}))
        ):
            raise ServiceContractError("Assessment evidence record is invalid.")
    if items["market_structure"].limitations != ("context.structure.unavailable",):
        raise ServiceContractError("Assessment structure limitation is invalid.")


def _decision(inputs: _PersistedInputs) -> tuple[OpportunityStance, tuple[str, ...]]:
    if inputs.candidate.reason_codes == _BUY_REASONS:
        return (
            OpportunityStance.BUY,
            (
                "assessment.persisted_inputs_verified",
                "assessment.evidence_lineage_verified",
                "assessment.buy_direction_confirmed",
            ),
        )
    if inputs.candidate.reason_codes == _SELL_REASONS:
        return (
            OpportunityStance.SELL,
            (
                "assessment.persisted_inputs_verified",
                "assessment.evidence_lineage_verified",
                "assessment.sell_direction_confirmed",
            ),
        )
    raise ServiceContractError("Assessment candidate direction is invalid.")


def _build_opportunity(
    inputs: _PersistedInputs,
    *,
    stance: OpportunityStance,
    reason_codes: tuple[str, ...],
    policy: PolicyReference,
    code_version: str,
) -> Opportunity:
    candidate_id = inputs.candidate.candidate_id
    references = (
        inputs.candidate_reference,
        inputs.evidence_reference,
        inputs.market_reference,
        inputs.feature_reference,
        inputs.context_reference,
    )
    audit = AuditMetadata(
        created_at=inputs.candidate.audit.evidence_cutoff,
        evidence_cutoff=inputs.candidate.audit.evidence_cutoff,
        available_at=inputs.candidate.audit.evidence_cutoff,
        provenance=Provenance(
            source_references=references,
            policy_references=(policy,),
            code_version=code_version,
            configuration_hash=RUNTIME_ASSESSMENT_POLICY_HASH,
            lineage_hash=canonical_sha256(references),
        ),
        result_hash="0" * 64,
    )
    opportunity = Opportunity(
        contract_version="1.0.0",
        opportunity_id=f"opportunity.runtime_ema_rsi.{candidate_id}",
        opportunity_version_id=f"opportunity.runtime_ema_rsi.{candidate_id}.v1",
        assessment_id=f"assessment.runtime_ema_rsi.{candidate_id}",
        decision_id=f"decision.runtime_ema_rsi.{candidate_id}",
        candidate_id=candidate_id,
        scope=inputs.candidate.scope,
        stance=stance,
        decision_policy=policy,
        evidence_package_reference=inputs.evidence_reference,
        context_reference=inputs.context_reference,
        reason_codes=reason_codes,
        limitations=inputs.evidence.limitations,
        qualification_reference=None,
        score_reference=None,
        confidence=None,
        plan=None,
        valid_until=None,
        supersedes_opportunity_version_id=None,
        audit=audit,
    )
    return replace(
        opportunity,
        audit=replace(
            audit,
            result_hash=canonical_sha256(
                opportunity,
                exclude=frozenset({"result_hash"}),
            ),
        ),
    )


def _expected_rsi_state(reason_codes: tuple[str, ...]) -> str:
    if reason_codes == _BUY_REASONS:
        return "buy_threshold_met"
    if reason_codes == _SELL_REASONS:
        return "sell_threshold_met"
    raise ServiceContractError("Assessment candidate reason codes are invalid.")


def _reference(
    artifact_id: str,
    artifact_type: str,
    entity: OpportunityCandidate
    | EvidencePackage
    | MarketSnapshot
    | FeatureSnapshot
    | MarketContext,
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
        _EVIDENCE_POLICY_ID,
        _EVIDENCE_POLICY_VERSION,
        _EVIDENCE_POLICY_HASH,
    )


def _assessment_policy() -> PolicyReference:
    return PolicyReference(
        RUNTIME_ASSESSMENT_POLICY_ID,
        RUNTIME_ASSESSMENT_POLICY_VERSION,
        RUNTIME_ASSESSMENT_POLICY_HASH,
    )
