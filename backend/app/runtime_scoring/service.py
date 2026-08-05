"""Repository-backed implementation of Runtime Scoring Policy v1.0."""

from dataclasses import replace
from decimal import Decimal

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    DecimalRange,
    EvidencePackage,
    IntegrityReference,
    MarketContext,
    Opportunity,
    PolicyReference,
    Provenance,
    QualificationOutcome,
    QualificationRecord,
    QualificationStatus,
    ScoreComponent,
    ScoreComponentAvailability,
    ScoreResult,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    EntityAsOfQuery,
    EntityId,
    EntityNotFoundError,
    EvidenceRepository,
    MarketContextRepository,
    OpportunityRepository,
    QualificationRepository,
    ScoringRepository,
)
from app.opportunity_intelligence.services import (
    PolicyUnavailableError,
    ServiceContractError,
    ServiceUnavailableError,
)


RUNTIME_SCORING_POLICY_ID = "alphalens_runtime_scoring_ema_rsi"
RUNTIME_SCORING_POLICY_VERSION = "1.0.0"
RUNTIME_SCORING_POLICY_HASH = (
    "2e6b45f3d3f285b085677b647bfdb21bbf8359a4b184c84742025ec051f88328"
)
_QUALIFICATION_POLICY = PolicyReference(
    "alphalens_runtime_qualification_ema_rsi",
    "1.0.0",
    "44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e",
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
_SCOPE = ("BTCUSDT", "5m")
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
_QUALIFICATION_GATES = (
    ("qualification.persisted_inputs", "qualification.persisted_inputs_verified"),
    ("qualification.assessment_policy", "qualification.assessment_policy_verified"),
    ("qualification.evidence_lineage", "qualification.evidence_lineage_verified"),
    ("qualification.scope_chronology", "qualification.scope_chronology_verified"),
)
_UNAVAILABLE_DIMENSION_REASON_CODES = (
    "scoring.risk_unavailable",
    "scoring.confidence_unavailable",
    "scoring.reward_unavailable",
)


class RuntimeScoringService:
    """Persist the approved ordinal quality score for a qualified opportunity."""

    def __init__(
        self,
        *,
        opportunities: OpportunityRepository,
        qualifications: QualificationRepository,
        evidence: EvidenceRepository,
        market_contexts: MarketContextRepository,
        scores: ScoringRepository,
        code_version: str,
        policy: PolicyReference | None = None,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime scoring code version must be non-empty.")
        self._opportunities = opportunities
        self._qualifications = qualifications
        self._evidence = evidence
        self._market_contexts = market_contexts
        self._scores = scores
        self._code_version = code_version
        self._policy = policy if policy is not None else _policy()

    async def score(
        self,
        opportunity: Opportunity,
        qualification: QualificationRecord,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> ScoreResult:
        """Validate persisted lineage and save one immutable ordinal score."""
        if self._policy != _policy():
            raise PolicyUnavailableError("Scoring policy v1.0.0 is unavailable.")
        cutoff = qualification.audit.evidence_cutoff
        try:
            persisted_opportunity = await self._opportunities.get_by_id(
                EntityId(opportunity.opportunity_version_id)
            )
            persisted_qualification = (
                await self._qualifications.get_latest_for_assessment(
                    EntityAsOfQuery(
                        EntityId(opportunity.opportunity_version_id), cutoff
                    )
                )
            )
            persisted_evidence = await self._evidence.get_by_candidate_id(
                EntityId(opportunity.candidate_id)
            )
            persisted_context = await self._market_contexts.get_by_id(
                EntityId(market_context.context_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Scoring requires all referenced persisted artifacts."
            ) from error
        for supplied, persisted, label in (
            (opportunity, persisted_opportunity, "opportunity"),
            (qualification, persisted_qualification, "qualification"),
            (evidence, persisted_evidence, "evidence package"),
            (market_context, persisted_context, "market context"),
        ):
            if supplied.canonical_sha256() != persisted.canonical_sha256():
                raise ServiceContractError(
                    f"Persisted {label} conflicts with scoring input."
                )
        _validate(
            persisted_opportunity,
            persisted_qualification,
            persisted_evidence,
            persisted_context,
        )
        limitations = _optional_limitations(
            persisted_opportunity,
            persisted_qualification,
            persisted_evidence,
        )
        value = Decimal("50") if limitations else Decimal("100")
        record = _record(
            persisted_opportunity,
            persisted_qualification,
            persisted_evidence,
            value,
            limitations,
            self._policy,
            self._code_version,
        )
        return await self._scores.save(record)


def _validate(
    opportunity: Opportunity,
    qualification: QualificationRecord,
    evidence: EvidencePackage,
    market_context: MarketContext,
) -> None:
    cutoff = qualification.audit.evidence_cutoff
    opportunity_reference = _reference(
        opportunity.opportunity_version_id, "opportunity", opportunity
    )
    evidence_reference = _reference(evidence.package_id, "evidence_package", evidence)
    context_reference = _reference(
        market_context.context_id, "market_context", market_context
    )
    source_references = opportunity.audit.provenance.source_references
    expected_source_types = (
        "opportunity_candidate",
        "evidence_package",
        "market_snapshot",
        "feature_snapshot",
        "market_context",
    )
    evidence_keys = {item.evidence_id.rsplit(".", 1)[-1] for item in evidence.items}
    gate_mapping = tuple(
        (gate.gate_id, gate.reason_code) for gate in qualification.gate_results
    )
    if (
        opportunity.scope.instrument != _SCOPE[0]
        or opportunity.scope.timeframe != _SCOPE[1]
        or opportunity.decision_policy != _ASSESSMENT_POLICY
        or opportunity.audit.provenance.policy_references != (_ASSESSMENT_POLICY,)
        or opportunity.audit.provenance.configuration_hash
        != _ASSESSMENT_POLICY.integrity_digest
        or opportunity.evidence_package_reference != evidence_reference
        or qualification.policy != _QUALIFICATION_POLICY
        or qualification.outcome is not QualificationOutcome.QUALIFIED
        or qualification.assessment_reference != opportunity_reference
        or qualification.evidence_package_reference != evidence_reference
        or qualification.audit.provenance.policy_references != (_QUALIFICATION_POLICY,)
        or qualification.audit.provenance.configuration_hash
        != _QUALIFICATION_POLICY.integrity_digest
        or qualification.audit.provenance.lineage_hash
        != canonical_sha256(source_references)
        or qualification.audit.created_at != cutoff
        or qualification.audit.available_at != cutoff
        or gate_mapping != _QUALIFICATION_GATES
        or any(
            gate.status is not QualificationStatus.PASS
            for gate in qualification.gate_results
        )
        or evidence.candidate_id != opportunity.candidate_id
        or evidence.assessment_id is not None
        or evidence.audit.provenance.policy_references != (_EVIDENCE_POLICY,)
        or evidence.audit.evidence_cutoff != cutoff
        or evidence_keys != _REQUIRED_EVIDENCE_KEYS
        or tuple(item.artifact_type for item in source_references)
        != expected_source_types
    ):
        raise ServiceContractError("Scoring inputs fail closed validation.")
    all_references = (
        qualification.assessment_reference,
        qualification.evidence_package_reference,
        qualification.context_reference,
    ) + source_references
    if any(reference.available_at > cutoff for reference in all_references):
        raise ServiceUnavailableError("Scoring input is unavailable at cutoff.")
    if (
        opportunity.audit.available_at > cutoff
        or evidence.audit.available_at > cutoff
        or market_context.audit.available_at > cutoff
        or any(item.available_at > cutoff for item in evidence.items)
    ):
        raise ServiceUnavailableError("Scoring evidence is unavailable at cutoff.")
    if (
        opportunity.context_reference != context_reference
        or qualification.context_reference != context_reference
        or qualification.audit.provenance.source_references != source_references
        or qualification.audit.provenance.lineage_hash
        != canonical_sha256(source_references)
        or source_references[1] != evidence_reference
        or source_references[-1] != context_reference
    ):
        raise ServiceContractError("Scoring lineage fails closed validation.")


def _optional_limitations(
    opportunity: Opportunity,
    qualification: QualificationRecord,
    evidence: EvidencePackage,
) -> tuple[str, ...]:
    limitations = [
        limitation
        for limitation in (
            opportunity.limitations + qualification.limitations + evidence.limitations
        )
        if limitation.endswith(".unavailable")
    ]
    for item in evidence.items:
        if item.observed_value == "unavailable":
            limitations.extend(item.limitations)
    return tuple(dict.fromkeys(limitations))


def _record(
    opportunity: Opportunity,
    qualification: QualificationRecord,
    evidence: EvidencePackage,
    value: Decimal,
    limitations: tuple[str, ...],
    policy: PolicyReference,
    code_version: str,
) -> ScoreResult:
    qualification_reference = _reference(
        qualification.qualification_id,
        "qualification_record",
        qualification,
    )
    opportunity_reference = _reference(
        opportunity.opportunity_version_id, "opportunity", opportunity
    )
    evidence_reference = _reference(evidence.package_id, "evidence_package", evidence)
    component = ScoreComponent(
        component_id="opportunity_quality",
        component_version="1.0.0",
        meaning="ordinal_opportunity_priority",
        availability=ScoreComponentAvailability.AVAILABLE,
        source_evidence=(
            qualification_reference,
            opportunity_reference,
            evidence_reference,
        ),
        raw_value=value,
        normalized_value=value,
        weight=Decimal("1"),
        contribution=value,
        normalization_reference=None,
        weight_reference=None,
        limitations=limitations + _UNAVAILABLE_DIMENSION_REASON_CODES,
        component_hash="0" * 64,
    )
    component = replace(
        component,
        component_hash=canonical_sha256(
            component, exclude=frozenset({"component_hash"})
        ),
    )
    sources = opportunity.audit.provenance.source_references
    audit = AuditMetadata(
        created_at=qualification.audit.evidence_cutoff,
        evidence_cutoff=qualification.audit.evidence_cutoff,
        available_at=qualification.audit.evidence_cutoff,
        provenance=Provenance(
            source_references=sources,
            policy_references=(policy,),
            code_version=code_version,
            configuration_hash=RUNTIME_SCORING_POLICY_HASH,
            lineage_hash=canonical_sha256(sources),
        ),
        result_hash="0" * 64,
    )
    record = ScoreResult(
        contract_version="1.0.0",
        score_id=f"score.runtime_ema_rsi.{qualification.qualification_id}",
        opportunity_id=opportunity.opportunity_version_id,
        qualification_reference=qualification_reference,
        policy=policy,
        components=(component,),
        aggregation_definition="ordinal_quality_v1",
        aggregate_value=value,
        aggregate_unit="ordinal_priority",
        valid_domain=DecimalRange(Decimal("50"), Decimal("100")),
        missing_input_disposition="unavailable_no_score_result",
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
    entity: Opportunity | QualificationRecord | EvidencePackage | MarketContext,
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
        RUNTIME_SCORING_POLICY_ID,
        RUNTIME_SCORING_POLICY_VERSION,
        RUNTIME_SCORING_POLICY_HASH,
    )
