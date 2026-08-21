"""Repository-backed implementation of Runtime Qualification Policy v1.0 and v2.0."""

from dataclasses import replace
from decimal import Decimal

from app.inference.artifact import EXPECTED_MOVE_MIN_RR, EXPECTED_MOVE_MIN_SNR
from app.market_configuration import get_default_scope
from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ContextStatus,
    EvidencePackage,
    FeatureSnapshot,
    IntegrityReference,
    MarketContext,
    MarketScope,
    MarketSnapshot,
    Opportunity,
    OpportunityStance,
    PolicyReference,
    Provenance,
    QualificationGateResult,
    QualificationOutcome,
    QualificationRecord,
    QualificationStatus,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
    EvidenceRepository,
    FeatureSnapshotRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
    OpportunityRepository,
    QualificationRepository,
)
from app.opportunity_intelligence.services import (
    PolicyUnavailableError,
    ServiceContractError,
    ServiceUnavailableError,
)


RUNTIME_QUALIFICATION_POLICY_ID = "alphalens_runtime_qualification_ema_rsi"
RUNTIME_QUALIFICATION_POLICY_VERSION = "1.0.0"
RUNTIME_QUALIFICATION_POLICY_HASH = (
    "44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e"
)
_ASSESSMENT_POLICY = PolicyReference(
    "alphalens_runtime_assessment_ema_rsi",
    "1.0.1",
    "4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d",
)
_EVIDENCE_POLICY = PolicyReference(
    "alphalens_runtime_evidence_ema_rsi",
    "1.0.0",
    "9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8",
)
_SCOPE_TIMEFRAMES = ("5m", "10m", "15m")
_REQUIRED_EVIDENCE_KEYS = {
    "market_price_close",
    "market_volume",
    "ema_12",
    "ema_26",
    "rsi",
    "atr_true_range",
    "ema_alignment",
    "rsi_state",
    "market_structure",
}


class RuntimeQualificationService:
    """Persist deterministic structural qualification for a valid assessment."""

    def __init__(
        self,
        *,
        opportunities: OpportunityRepository,
        evidence: EvidenceRepository,
        market_contexts: MarketContextRepository,
        feature_snapshots: FeatureSnapshotRepository,
        market_snapshots: MarketSnapshotRepository,
        qualifications: QualificationRepository,
        code_version: str,
        policy: PolicyReference | None = None,
        scope: MarketScope | None = None,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime qualification code version must be non-empty.")
        self._opportunities = opportunities
        self._evidence = evidence
        self._market_contexts = market_contexts
        self._feature_snapshots = feature_snapshots
        self._market_snapshots = market_snapshots
        self._qualifications = qualifications
        self._code_version = code_version
        self._policy = policy if policy is not None else _policy()
        self._scope = scope or get_default_scope()

    async def qualify(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> QualificationRecord:
        """Verify persisted lineage and save one immutable qualification record."""
        if self._policy != _policy():
            raise PolicyUnavailableError("Qualification policy v1.0.0 is unavailable.")
        try:
            persisted_opportunity = await self._opportunities.get_by_id(
                EntityId(opportunity.opportunity_version_id)
            )
            persisted_evidence = await self._evidence.get_by_candidate_id(
                EntityId(opportunity.candidate_id)
            )
            context = await self._market_contexts.get_by_id(
                EntityId(market_context.context_id)
            )
            sources = _sources(persisted_opportunity)
            market = await self._market_snapshots.get_by_id(
                EntityId(sources["market_snapshot"].artifact_id)
            )
            features = await self._feature_snapshots.get_by_id(
                EntityId(sources["feature_snapshot"].artifact_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Qualification requires all referenced persisted artifacts."
            ) from error
        for supplied, persisted, label in (
            (opportunity, persisted_opportunity, "opportunity"),
            (evidence, persisted_evidence, "evidence package"),
            (market_context, context, "market context"),
        ):
            if supplied.canonical_sha256() != persisted.canonical_sha256():
                raise ServiceContractError(
                    f"Persisted {label} conflicts with qualification input."
                )
        _validate(persisted_opportunity, persisted_evidence, context, features, market, self._scope.instrument)
        record = _record(
            persisted_opportunity,
            persisted_evidence,
            context,
            features,
            market,
            self._policy,
            self._code_version,
        )
        return await self._qualifications.save(record)


def _sources(opportunity: Opportunity) -> dict[str, IntegrityReference]:
    sources = opportunity.audit.provenance.source_references
    expected = (
        "opportunity_candidate",
        "evidence_package",
        "market_snapshot",
        "feature_snapshot",
        "market_context",
    )
    if tuple(item.artifact_type for item in sources) != expected:
        raise ServiceContractError("Qualification assessment provenance is invalid.")
    return {item.artifact_type: item for item in sources}


def _validate(
    opportunity: Opportunity,
    evidence: EvidencePackage,
    context: MarketContext,
    features: FeatureSnapshot,
    market: MarketSnapshot,
    scope_instrument: str,
) -> None:
    sources = _sources(opportunity)
    cutoff = opportunity.audit.evidence_cutoff
    candle = market.candles[0] if len(market.candles) == 1 else None
    keys = {item.evidence_id.rsplit(".", 1)[-1] for item in evidence.items}
    candidate_reference = sources["opportunity_candidate"]
    evidence_reference = _reference(evidence.package_id, "evidence_package", evidence)
    market_reference = _reference(market.snapshot_id, "market_snapshot", market)
    feature_reference = _reference(features.snapshot_id, "feature_snapshot", features)
    context_reference = _reference(context.context_id, "market_context", context)
    expected_assessment_sources = (
        candidate_reference,
        evidence_reference,
        market_reference,
        feature_reference,
        context_reference,
    )
    if (
        opportunity.scope.instrument != scope_instrument
        or opportunity.scope.timeframe not in _SCOPE_TIMEFRAMES
        or opportunity.stance not in {OpportunityStance.BUY, OpportunityStance.SELL}
        or opportunity.decision_policy != _ASSESSMENT_POLICY
        or opportunity.audit.provenance.policy_references != (_ASSESSMENT_POLICY,)
        or opportunity.audit.provenance.configuration_hash
        != _ASSESSMENT_POLICY.integrity_digest
        or candidate_reference.artifact_id != opportunity.candidate_id
        or opportunity.evidence_package_reference != evidence_reference
        or opportunity.context_reference != context_reference
        or evidence.candidate_id != opportunity.candidate_id
        or evidence.assessment_id is not None
        or evidence.audit.provenance.policy_references != (_EVIDENCE_POLICY,)
        or evidence.audit.provenance.source_references
        != (
            candidate_reference,
            market_reference,
            feature_reference,
            context_reference,
        )
        or market.scope != opportunity.scope
        or features.scope != opportunity.scope
        or context.scope != opportunity.scope
        or features.market_snapshot != market_reference
        or candle is None
        or not market.complete
        or context.data_quality.status is not ContextStatus.AVAILABLE
        or len(context.data_quality.observations) != 1
        or context.data_quality.observations[0].semantic_identifier
        != "data_quality.persisted_inputs_verified"
        or context.data_quality.observations[0].value is not True
        or evidence.audit.evidence_cutoff != cutoff
        or keys != _REQUIRED_EVIDENCE_KEYS
        or tuple(opportunity.audit.provenance.source_references)
        != expected_assessment_sources
    ):
        raise ServiceContractError("Qualification inputs fail closed validation.")
    references = tuple(sources.values())
    if any(reference.available_at > cutoff for reference in references):
        raise ServiceUnavailableError("Qualification input is unavailable at cutoff.")
    if any(item.available_at > cutoff for item in evidence.items):
        raise ServiceUnavailableError(
            "Qualification evidence is unavailable at cutoff."
        )
    if any(value.candle_timestamp != candle.timestamp for value in features.values):
        raise ServiceUnavailableError("Qualification feature input is stale.")
    if any(
        observation.time_start != candle.timestamp
        or observation.time_end != candle.timestamp
        for observation in context.data_quality.observations
    ):
        raise ServiceUnavailableError("Qualification context input is stale.")
    structure = next(
        item
        for item in evidence.items
        if item.evidence_id.endswith(".market_structure")
    )
    if structure.observed_value != "unavailable" or structure.limitations != (
        "context.structure.unavailable",
    ):
        raise ServiceContractError("Qualification structure evidence is invalid.")


def _record(
    opportunity: Opportunity,
    evidence: EvidencePackage,
    context: MarketContext,
    features: FeatureSnapshot,
    market: MarketSnapshot,
    policy: PolicyReference,
    code_version: str,
) -> QualificationRecord:
    sources = opportunity.audit.provenance.source_references
    assessment_reference = _reference(
        opportunity.opportunity_version_id, "opportunity", opportunity
    )
    evidence_reference = _reference(evidence.package_id, "evidence_package", evidence)
    context_reference = _reference(context.context_id, "market_context", context)
    common_references = (
        assessment_reference,
        evidence_reference,
        context_reference,
        _reference(features.snapshot_id, "feature_snapshot", features),
        _reference(market.snapshot_id, "market_snapshot", market),
    )
    gates = (
        QualificationGateResult(
            "qualification.persisted_inputs",
            "persisted_inputs",
            QualificationStatus.PASS,
            common_references,
            "qualification.persisted_inputs_verified",
        ),
        QualificationGateResult(
            "qualification.assessment_policy",
            "assessment_policy",
            QualificationStatus.PASS,
            (assessment_reference,),
            "qualification.assessment_policy_verified",
        ),
        QualificationGateResult(
            "qualification.evidence_lineage",
            "evidence_lineage",
            QualificationStatus.PASS,
            common_references[1:],
            "qualification.evidence_lineage_verified",
        ),
        QualificationGateResult(
            "qualification.scope_chronology",
            "scope_chronology",
            QualificationStatus.PASS,
            common_references,
            "qualification.scope_chronology_verified",
        ),
    )
    audit = AuditMetadata(
        created_at=opportunity.audit.evidence_cutoff,
        evidence_cutoff=opportunity.audit.evidence_cutoff,
        available_at=opportunity.audit.evidence_cutoff,
        provenance=Provenance(
            source_references=sources,
            policy_references=(policy,),
            code_version=code_version,
            configuration_hash=RUNTIME_QUALIFICATION_POLICY_HASH,
            lineage_hash=canonical_sha256(sources),
        ),
        result_hash="0" * 64,
    )
    record = QualificationRecord(
        contract_version="1.0.0",
        qualification_id=f"qualification.runtime_ema_rsi.{opportunity.assessment_id}",
        assessment_reference=assessment_reference,
        context_reference=context_reference,
        evidence_package_reference=evidence_reference,
        policy=policy,
        gate_results=gates,
        outcome=QualificationOutcome.QUALIFIED,
        exclusions=(),
        limitations=opportunity.limitations,
        audit=audit,
    )
    return replace(
        record,
        audit=replace(
            audit,
            result_hash=canonical_sha256(record, exclude=frozenset({"result_hash"})),
        ),
    )


def _reference(
    artifact_id: str,
    artifact_type: str,
    entity: Opportunity
    | EvidencePackage
    | MarketContext
    | FeatureSnapshot
    | MarketSnapshot,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest=entity.canonical_sha256(),
        available_at=entity.audit.available_at,
    )


def _policy() -> PolicyReference:
    return PolicyReference(
        RUNTIME_QUALIFICATION_POLICY_ID,
        RUNTIME_QUALIFICATION_POLICY_VERSION,
        RUNTIME_QUALIFICATION_POLICY_HASH,
    )


# ---------------------------------------------------------------------------
# V2: Expected-Move Qualification Service
# ---------------------------------------------------------------------------

RUNTIME_QUALIFICATION_V2_POLICY_ID = "alphalens_runtime_qualification_v2"
RUNTIME_QUALIFICATION_V2_POLICY_VERSION = "2.0.0"
RUNTIME_QUALIFICATION_V2_POLICY_HASH = (
    "0" * 64  # placeholder until policy document is ratified
)
_V2_PLAN_CONTRACT_VERSION = "2.0.0"


class RuntimeQualificationServiceV2:
    """Persist deterministic structural qualification with expected-move gate.

    V2 adds a fifth gate to the V1.0 qualification:
        qualification.expected_move_viable  →  SNR >= 1.0

    All four V1.0 gates remain unchanged.
    """

    def __init__(
        self,
        *,
        opportunities: OpportunityRepository,
        evidence: EvidenceRepository,
        market_contexts: MarketContextRepository,
        feature_snapshots: FeatureSnapshotRepository,
        market_snapshots: MarketSnapshotRepository,
        qualifications: QualificationRepository,
        code_version: str,
        policy: PolicyReference | None = None,
        scope: MarketScope | None = None,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime qualification V2 code version must be non-empty.")
        self._opportunities = opportunities
        self._evidence = evidence
        self._market_contexts = market_contexts
        self._feature_snapshots = feature_snapshots
        self._market_snapshots = market_snapshots
        self._qualifications = qualifications
        self._code_version = code_version
        self._policy = policy if policy is not None else _v2_policy()
        self._scope = scope or get_default_scope()

    async def qualify(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> QualificationRecord:
        """Verify persisted lineage, apply V1.0 gates plus expected-move gate."""
        if self._policy != _v2_policy():
            raise PolicyUnavailableError("Qualification policy v2.0.0 is unavailable.")
        try:
            persisted_opportunity = await self._opportunities.get_by_id(
                EntityId(opportunity.opportunity_version_id)
            )
            persisted_evidence = await self._evidence.get_by_candidate_id(
                EntityId(opportunity.candidate_id)
            )
            context = await self._market_contexts.get_by_id(
                EntityId(market_context.context_id)
            )
            sources = _sources(persisted_opportunity)
            market = await self._market_snapshots.get_by_id(
                EntityId(sources["market_snapshot"].artifact_id)
            )
            features = await self._feature_snapshots.get_by_id(
                EntityId(sources["feature_snapshot"].artifact_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Qualification requires all referenced persisted artifacts."
            ) from error
        for supplied, persisted, label in (
            (opportunity, persisted_opportunity, "opportunity"),
            (evidence, persisted_evidence, "evidence package"),
            (market_context, context, "market context"),
        ):
            if supplied.canonical_sha256() != persisted.canonical_sha256():
                raise ServiceContractError(
                    f"Persisted {label} conflicts with qualification input."
                )
        _validate(persisted_opportunity, persisted_evidence, context, features, market, self._scope.instrument)
        snr_gate = _validate_expected_move(persisted_opportunity)
        rr_gate = _validate_risk_reward(persisted_opportunity)
        record = _record_v2(
            persisted_opportunity,
            persisted_evidence,
            context,
            features,
            market,
            self._policy,
            self._code_version,
            snr_gate,
            rr_gate,
        )
        return await self._qualifications.save(record)


def _validate_expected_move(
    opportunity: Opportunity,
) -> QualificationGateResult:
    """Fifth gate: expected-move SNR >= 1.0 when V2 plan is present."""
    plan = opportunity.plan
    if plan is None or plan.expected_move_confidence is None:
        raise ServiceContractError(
            "Qualification V2 requires a V2 plan with expected-move confidence."
        )
    snr = plan.expected_move_confidence
    if not isinstance(snr, Decimal):
        snr = Decimal(str(snr))
    references = (
        _reference(
            opportunity.opportunity_version_id, "opportunity", opportunity
        ),
    )
    if snr >= EXPECTED_MOVE_MIN_SNR:
        return QualificationGateResult(
            "qualification.expected_move_viable",
            "expected_move_viable",
            QualificationStatus.PASS,
            references,
            "qualification.expected_move_snr_above_threshold",
        )
    return QualificationGateResult(
        "qualification.expected_move_viable",
        "expected_move_viable",
        QualificationStatus.FAIL,
        references,
        "qualification.expected_move_snr_below_threshold",
    )


def _validate_risk_reward(
    opportunity: Opportunity,
) -> QualificationGateResult:
    """Sixth gate: risk-reward >= 2.0 when V2 plan is present."""
    plan = opportunity.plan
    if plan is None or not plan.targets:
        raise ServiceContractError(
            "Qualification V2 requires a V2 plan with at least one target."
        )
    risk_reward = plan.targets[0].risk_reward
    if not isinstance(risk_reward, Decimal):
        risk_reward = Decimal(str(risk_reward))
    references = (
        _reference(
            opportunity.opportunity_version_id, "opportunity", opportunity
        ),
    )
    if risk_reward >= EXPECTED_MOVE_MIN_RR:
        return QualificationGateResult(
            "qualification.risk_reward_viable",
            "risk_reward_viable",
            QualificationStatus.PASS,
            references,
            "qualification.risk_reward_above_threshold",
        )
    return QualificationGateResult(
        "qualification.risk_reward_viable",
        "risk_reward_viable",
        QualificationStatus.FAIL,
        references,
        "qualification.risk_reward_below_threshold",
    )


def _record_v2(
    opportunity: Opportunity,
    evidence: EvidencePackage,
    context: MarketContext,
    features: FeatureSnapshot,
    market: MarketSnapshot,
    policy: PolicyReference,
    code_version: str,
    snr_gate: QualificationGateResult,
    rr_gate: QualificationGateResult,
) -> QualificationRecord:
    sources = opportunity.audit.provenance.source_references
    assessment_reference = _reference(
        opportunity.opportunity_version_id, "opportunity", opportunity
    )
    evidence_reference = _reference(evidence.package_id, "evidence_package", evidence)
    context_reference = _reference(context.context_id, "market_context", context)
    common_references = (
        assessment_reference,
        evidence_reference,
        context_reference,
        _reference(features.snapshot_id, "feature_snapshot", features),
        _reference(market.snapshot_id, "market_snapshot", market),
    )
    gates = (
        QualificationGateResult(
            "qualification.persisted_inputs",
            "persisted_inputs",
            QualificationStatus.PASS,
            common_references,
            "qualification.persisted_inputs_verified",
        ),
        QualificationGateResult(
            "qualification.assessment_policy",
            "assessment_policy",
            QualificationStatus.PASS,
            (assessment_reference,),
            "qualification.assessment_policy_verified",
        ),
        QualificationGateResult(
            "qualification.evidence_lineage",
            "evidence_lineage",
            QualificationStatus.PASS,
            common_references[1:],
            "qualification.evidence_lineage_verified",
        ),
        QualificationGateResult(
            "qualification.scope_chronology",
            "scope_chronology",
            QualificationStatus.PASS,
            common_references,
            "qualification.scope_chronology_verified",
        ),
        snr_gate,
        rr_gate,
    )
    all_passed = all(
        gate.status is QualificationStatus.PASS for gate in gates
    )
    outcome = (
        QualificationOutcome.QUALIFIED
        if all_passed
        else QualificationOutcome.EXCLUDED
    )
    audit = AuditMetadata(
        created_at=opportunity.audit.evidence_cutoff,
        evidence_cutoff=opportunity.audit.evidence_cutoff,
        available_at=opportunity.audit.evidence_cutoff,
        provenance=Provenance(
            source_references=sources,
            policy_references=(policy,),
            code_version=code_version,
            configuration_hash=RUNTIME_QUALIFICATION_V2_POLICY_HASH,
            lineage_hash=canonical_sha256(sources),
        ),
        result_hash="0" * 64,
    )
    record = QualificationRecord(
        contract_version=_V2_PLAN_CONTRACT_VERSION,
        qualification_id=f"qualification.runtime_v2.{opportunity.assessment_id}",
        assessment_reference=assessment_reference,
        context_reference=context_reference,
        evidence_package_reference=evidence_reference,
        policy=policy,
        gate_results=gates,
        outcome=outcome,
        exclusions=(
            ()
            if all_passed
            else tuple(
                gate.reason_code
                for gate in gates
                if gate.status is not QualificationStatus.PASS
            )
        ),
        limitations=opportunity.limitations,
        audit=audit,
    )
    return replace(
        record,
        audit=replace(
            audit,
            result_hash=canonical_sha256(record, exclude=frozenset({"result_hash"})),
        ),
    )


def _v2_policy() -> PolicyReference:
    return PolicyReference(
        RUNTIME_QUALIFICATION_V2_POLICY_ID,
        RUNTIME_QUALIFICATION_V2_POLICY_VERSION,
        RUNTIME_QUALIFICATION_V2_POLICY_HASH,
    )
