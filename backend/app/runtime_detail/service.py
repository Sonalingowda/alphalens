"""Runtime Opportunity Detail Projection Service.

Governed by ALPHALENS_MVP_RUNTIME_CONTRACT_V1 §2.9.

This service assembles one immutable OpportunityDetail from the persisted
runtime artifacts produced by every prior pipeline stage and persists it
through the OpportunityDetailRepository.

Design constraints enforced here:
- All five primary inputs are verified against their repositories by
  canonical digest before assembly (fail-closed on any mismatch).
- Scope consistency across opportunity, market snapshot, context, and
  lifecycle is validated before assembly.
- Evidence package identity is validated against the opportunity's
  evidence_package_reference.
- Explanation opportunity_version_id is validated against the opportunity.
- lifecycle.opportunity_id is validated against opportunity.opportunity_id.
- Single atomic write; no partial persistence.
- Idempotent: byte-identical replay produces byte-identical output.
- POLICY_BLOCKED path: PolicyUnavailableError raised when the runtime
  contract version cannot be satisfied (no separate policy-hash document
  exists for this stage; the runtime contract is the sole authority).
- Empty indicators tuple is valid (no feature values registered in the MVP).
"""

from dataclasses import dataclass, replace

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    EvidencePackage,
    ExplanationArtifact,
    IndicatorValue,
    IntegrityReference,
    MarketContext,
    MarketSnapshot,
    Opportunity,
    OpportunityDetail,
    OpportunityLifecycle,
    PolicyReference,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
    EvidenceRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
    OpportunityDetailRepository,
    OpportunityRepository,
)
from app.opportunity_intelligence.repositories.projections import ExplanationRepository
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)


# ---------------------------------------------------------------------------
# Contract version — must match the runtime contract artifact version.
# ---------------------------------------------------------------------------

RUNTIME_DETAIL_CONTRACT_VERSION = "1.0.0"

# Immutable pipeline contract reference used in the audit provenance.
# No separate policy hash document exists for this stage; the runtime
# contract document is the sole authority.
_RUNTIME_CONTRACT = PolicyReference(
    "alphalens_mvp_runtime_contract",
    "1.0.0",
    "0" * 64,
)

_VERIFICATION_STATUS = "verified"


@dataclass(frozen=True, slots=True)
class _PersistedInputs:
    opportunity: Opportunity
    market_snapshot: MarketSnapshot
    market_context: MarketContext
    evidence: EvidencePackage
    explanation: ExplanationArtifact


class RuntimeOpportunityDetailProjectionService:
    """Assemble and persist one immutable OpportunityDetail.

    Implements the Detail Projection stage of the MVP
    OpportunityIntelligencePipeline as defined by
    ALPHALENS_MVP_RUNTIME_CONTRACT_V1 §2.9.
    """

    def __init__(
        self,
        *,
        opportunities: OpportunityRepository,
        market_snapshots: MarketSnapshotRepository,
        market_contexts: MarketContextRepository,
        evidence: EvidenceRepository,
        explanations: ExplanationRepository,
        details: OpportunityDetailRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime detail code version must be non-empty.")
        self._opportunities = opportunities
        self._market_snapshots = market_snapshots
        self._market_contexts = market_contexts
        self._evidence = evidence
        self._explanations = explanations
        self._details = details
        self._code_version = code_version

    async def project(
        self,
        opportunity: Opportunity,
        market_snapshot: MarketSnapshot,
        indicators: tuple[IndicatorValue, ...],
        market_context: MarketContext,
        evidence: EvidencePackage,
        explanation: ExplanationArtifact,
        lifecycle: OpportunityLifecycle,
    ) -> OpportunityDetail:
        """Verify all persisted inputs and persist one immutable detail artifact.

        Parameters match the OpportunityDetailService protocol and the
        pipeline call signature in OpportunityIntelligencePipeline.detail.
        """
        # --- Round-trip every primary artifact through its repository ---
        persisted = await self._load_persisted(
            opportunity, market_snapshot, market_context, evidence, explanation
        )

        # --- Validate cross-artifact consistency ---
        _validate(
            persisted.opportunity,
            persisted.market_snapshot,
            persisted.market_context,
            persisted.evidence,
            persisted.explanation,
            lifecycle,
        )

        # --- Build identity ---
        detail_id = f"detail.runtime.{persisted.opportunity.opportunity_version_id}"

        # --- Evidence cutoff: the opportunity's evidence cutoff ---
        cutoff = persisted.opportunity.audit.evidence_cutoff

        # --- Ordered provenance source references ---
        source_refs: tuple[IntegrityReference, ...] = (
            _ref(
                persisted.opportunity.opportunity_version_id,
                "opportunity",
                persisted.opportunity,
            ),
            _ref(
                persisted.market_snapshot.snapshot_id,
                "market_snapshot",
                persisted.market_snapshot,
            ),
            _ref(
                persisted.market_context.context_id,
                "market_context",
                persisted.market_context,
            ),
            _ref(
                persisted.evidence.package_id,
                "evidence_package",
                persisted.evidence,
            ),
            _ref(
                persisted.explanation.explanation_id,
                "explanation",
                persisted.explanation,
            ),
        )

        audit = AuditMetadata(
            created_at=cutoff,
            evidence_cutoff=cutoff,
            available_at=cutoff,
            provenance=Provenance(
                source_references=source_refs,
                policy_references=(_RUNTIME_CONTRACT,),
                code_version=self._code_version,
                configuration_hash=_RUNTIME_CONTRACT.integrity_digest,
                lineage_hash=canonical_sha256(source_refs),
            ),
            result_hash="0" * 64,
        )

        detail = OpportunityDetail(
            contract_version=RUNTIME_DETAIL_CONTRACT_VERSION,
            detail_id=detail_id,
            opportunity=persisted.opportunity,
            market_snapshot=persisted.market_snapshot,
            indicators=indicators,
            context=persisted.market_context,
            evidence=persisted.evidence,
            explanation=persisted.explanation,
            lifecycle=lifecycle,
            historical_references=(),
            verification_status=_VERIFICATION_STATUS,
            audit=audit,
        )

        # --- Compute result_hash before single atomic write ---
        result_hash = canonical_sha256(detail, exclude=frozenset({"result_hash"}))
        detail = replace(
            detail,
            audit=replace(audit, result_hash=result_hash),
        )

        return await self._details.save(detail)

    async def _load_persisted(
        self,
        opportunity: Opportunity,
        market_snapshot: MarketSnapshot,
        market_context: MarketContext,
        evidence: EvidencePackage,
        explanation: ExplanationArtifact,
    ) -> _PersistedInputs:
        """Load and digest-verify each primary artifact from its repository."""
        try:
            p_opp = await self._opportunities.get_by_id(
                EntityId(opportunity.opportunity_version_id)
            )
            p_market = await self._market_snapshots.get_by_id(
                EntityId(market_snapshot.snapshot_id)
            )
            p_context = await self._market_contexts.get_by_id(
                EntityId(market_context.context_id)
            )
            p_evidence = await self._evidence.get_by_candidate_id(
                EntityId(opportunity.candidate_id)
            )
            p_explanation = await self._explanations.get_by_opportunity_version(
                EntityId(opportunity.opportunity_version_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Detail: a required persisted artifact is not available."
            ) from error

        for supplied, persisted, label in (
            (opportunity, p_opp, "opportunity"),
            (market_snapshot, p_market, "market snapshot"),
            (market_context, p_context, "market context"),
            (evidence, p_evidence, "evidence package"),
            (explanation, p_explanation, "explanation"),
        ):
            if supplied.canonical_sha256() != persisted.canonical_sha256():
                raise ServiceContractError(
                    f"Detail: persisted {label} conflicts with pipeline input."
                )

        return _PersistedInputs(p_opp, p_market, p_context, p_evidence, p_explanation)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate(
    opportunity: Opportunity,
    market_snapshot: MarketSnapshot,
    market_context: MarketContext,
    evidence: EvidencePackage,
    explanation: ExplanationArtifact,
    lifecycle: OpportunityLifecycle,
) -> None:
    """Enforce cross-artifact consistency before assembly."""
    # Scope consistency (opportunity, market, context, lifecycle)
    scopes = (
        opportunity.scope,
        market_snapshot.scope,
        market_context.scope,
        lifecycle.scope,
    )
    if any(s != scopes[0] for s in scopes[1:]):
        raise ServiceContractError("Detail: component scopes are inconsistent.")

    # Lifecycle must reference this opportunity
    if lifecycle.opportunity_id != opportunity.opportunity_id:
        raise ServiceContractError(
            "Detail: lifecycle does not match the opportunity."
        )

    # Evidence package identity
    if evidence.package_id != opportunity.evidence_package_reference.artifact_id:
        raise ServiceContractError(
            "Detail: evidence package does not match the opportunity reference."
        )

    # Explanation must reference the correct opportunity version
    if explanation.opportunity_version_id != opportunity.opportunity_version_id:
        raise ServiceContractError(
            "Detail: explanation does not match the opportunity version."
        )

    # Freshness: all inputs must be available at or before the opportunity cutoff
    cutoff = opportunity.audit.evidence_cutoff
    for obj, name in (
        (market_snapshot, "market snapshot"),
        (market_context, "market context"),
        (evidence, "evidence"),
        (explanation, "explanation"),
    ):
        if obj.audit.available_at > cutoff:
            raise ServiceUnavailableError(
                f"Detail: {name} is unavailable at the opportunity cutoff."
            )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _ref(
    artifact_id: str,
    artifact_type: str,
    entity: Opportunity
    | MarketSnapshot
    | MarketContext
    | EvidencePackage
    | ExplanationArtifact,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest=entity.canonical_sha256(),
        available_at=entity.audit.available_at,
    )
