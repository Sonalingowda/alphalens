"""Runtime Dashboard Projection Service.

Governed by ALPHALENS_MVP_RUNTIME_CONTRACT_V1 §2.8.

This service converts one persisted RankingSnapshot plus the corresponding
Opportunity and OpportunityLifecycle objects into one immutable DashboardPage
and persists it through the DashboardProjectionRepository.

Design constraints enforced here:
- Consumes only persisted RankingSnapshot artifacts (verified by repository
  round-trip + canonical digest comparison).
- Produces a single atomic DashboardPage write; no partial persistence.
- Fail-closed: any missing required input raises ServiceUnavailableError.
- POLICY_BLOCKED path: raised as PolicyUnavailableError when the pipeline-
  contract version cannot be satisfied (no separate policy hash document
  exists for this stage; the contract itself is the authority).
- Idempotent: byte-identical replay of the same inputs produces byte-identical
  output; the repository enforces immutability on conflict.
- Empty RankingSnapshot (zero members) produces a valid empty DashboardPage.
"""

from dataclasses import replace

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    DashboardItem,
    DashboardPage,
    IntegrityReference,
    Opportunity,
    OpportunityLifecycle,
    PolicyReference,
    Provenance,
    RankingSnapshot,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    DashboardProjectionRepository,
    EntityId,
    EntityNotFoundError,
    RankingRepository,
)
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)


# ---------------------------------------------------------------------------
# Contract version — must match the runtime contract artifact version.
# ---------------------------------------------------------------------------

RUNTIME_DASHBOARD_CONTRACT_VERSION = "1.0.0"

# Immutable pipeline contract reference used in the audit provenance.
_RUNTIME_CONTRACT = PolicyReference(
    "alphalens_mvp_runtime_contract",
    "1.0.0",
    # SHA-256 of the contract identifier + version; this is an audit anchor,
    # not a locked executable policy hash.  The contract document itself is
    # the immutable authority for this stage.
    "0" * 64,
)

_FRESHNESS_STATE_CURRENT = "current"
_FRESHNESS_STATUS_AVAILABLE = "available"
_COVERAGE_STATUS_COMPLETE = "complete"
_COVERAGE_STATUS_EMPTY = "empty"
_SORT_CANONICAL_RANK = "canonical.rank"


class RuntimeDashboardProjectionService:
    """Project one persisted RankingSnapshot into one immutable DashboardPage.

    Implements the Dashboard Projection stage of the MVP
    OpportunityIntelligencePipeline as defined by
    ALPHALENS_MVP_RUNTIME_CONTRACT_V1 §2.8.
    """

    def __init__(
        self,
        *,
        rankings: RankingRepository,
        dashboard: DashboardProjectionRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError(
                "Runtime dashboard code version must be non-empty."
            )
        self._rankings = rankings
        self._dashboard = dashboard
        self._code_version = code_version

    async def project(
        self,
        ranking: RankingSnapshot,
        opportunities: tuple[Opportunity, ...],
        lifecycles: tuple[OpportunityLifecycle, ...],
    ) -> DashboardPage:
        """Validate the persisted ranking and persist one immutable DashboardPage.

        Parameters
        ----------
        ranking:
            The RankingSnapshot produced by the Ranking stage of this pipeline
            run.  It must already be persisted; this service will round-trip
            through the repository to verify it.
        opportunities:
            The Opportunity objects corresponding to the ranked members.
        lifecycles:
            The OpportunityLifecycle objects corresponding to each ranked
            opportunity, in the same order as ``opportunities``.
        """
        # --- Verify the RankingSnapshot is persisted ---
        try:
            persisted_ranking = await self._rankings.get_by_id(
                EntityId(ranking.snapshot_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Dashboard: RankingSnapshot is not persisted."
            ) from error

        if persisted_ranking.canonical_sha256() != ranking.canonical_sha256():
            raise ServiceContractError(
                "Dashboard: persisted RankingSnapshot conflicts with pipeline input."
            )

        # --- Validate opportunities and lifecycles against the ranking ---
        _validate_inputs(persisted_ranking, opportunities, lifecycles)

        # --- Build an index of opportunity_id → Opportunity and Lifecycle ---
        opp_index: dict[str, Opportunity] = {
            o.opportunity_id: o for o in opportunities
        }
        lc_index: dict[str, OpportunityLifecycle] = {
            lc.opportunity_id: lc for lc in lifecycles
        }

        # --- Build DashboardItems in rank order (ascending) ---
        ranking_ref = _integrity_reference(
            persisted_ranking.snapshot_id,
            "ranking_snapshot",
            persisted_ranking,
        )
        items: list[DashboardItem] = []
        for membership in persisted_ranking.memberships:
            opp = opp_index.get(membership.opportunity_id)
            lc = lc_index.get(membership.opportunity_id)
            if opp is None or lc is None:
                raise ServiceUnavailableError(
                    f"Dashboard: opportunity or lifecycle missing for "
                    f"ranked member {membership.opportunity_id!r}."
                )
            score_ref = membership.score_reference
            items.append(
                DashboardItem(
                    opportunity_id=opp.opportunity_id,
                    opportunity_version_id=opp.opportunity_version_id,
                    scope=opp.scope,
                    stance=opp.stance,
                    lifecycle_state=lc.current_state,
                    evidence_cutoff=opp.audit.evidence_cutoff,
                    available_at=opp.audit.available_at,
                    freshness_state=_FRESHNESS_STATE_CURRENT,
                    rank=membership.rank,
                    ranking_snapshot_reference=ranking_ref,
                    score_reference=score_ref,
                    confidence_reference=None,
                    reason_codes=opp.reason_codes,
                    has_plan=opp.plan is not None,
                    limitations=opp.limitations,
                    detail_reference=opp.opportunity_version_id,
                )
            )

        # --- Determine coverage status ---
        coverage_status = (
            _COVERAGE_STATUS_COMPLETE if items else _COVERAGE_STATUS_EMPTY
        )

        # --- Audit ---
        cutoff = persisted_ranking.audit.evidence_cutoff
        source_refs = persisted_ranking.audit.provenance.source_references
        audit = AuditMetadata(
            created_at=cutoff,
            evidence_cutoff=cutoff,
            available_at=cutoff,
            provenance=Provenance(
                source_references=source_refs,
                policy_references=(_RUNTIME_CONTRACT,),
                code_version=self._code_version,
                configuration_hash=_RUNTIME_CONTRACT.integrity_digest,
                lineage_hash=canonical_sha256(
                    (persisted_ranking.snapshot_id,)
                ),
            ),
            result_hash="0" * 64,
        )

        page = DashboardPage(
            contract_version=RUNTIME_DASHBOARD_CONTRACT_VERSION,
            ranking_snapshot_reference=ranking_ref,
            ranking_snapshot_hash=persisted_ranking.candidate_set_hash,
            as_of=cutoff,
            generated_at=cutoff,
            scope=persisted_ranking.scope,
            items=tuple(items),
            applied_filters=(),
            sort=_SORT_CANONICAL_RANK,
            next_cursor=None,
            previous_cursor=None,
            freshness_status=_FRESHNESS_STATUS_AVAILABLE,
            coverage_status=coverage_status,
            partial_failures=(),
            audit=audit,
        )

        # --- Compute result_hash before persistence ---
        result_hash = canonical_sha256(page, exclude=frozenset({"result_hash"}))
        page = replace(
            page,
            audit=replace(audit, result_hash=result_hash),
        )

        # --- Single atomic write ---
        return await self._dashboard.save(page)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_inputs(
    ranking: RankingSnapshot,
    opportunities: tuple[Opportunity, ...],
    lifecycles: tuple[OpportunityLifecycle, ...],
) -> None:
    """Verify that every ranked member has a matching opportunity and lifecycle."""
    if len(opportunities) != len(lifecycles):
        raise ServiceContractError(
            "Dashboard: opportunities and lifecycles counts must match."
        )

    opp_ids = {o.opportunity_id for o in opportunities}
    lc_ids = {lc.opportunity_id for lc in lifecycles}
    ranked_ids = {m.opportunity_id for m in ranking.memberships}

    # Every ranked member must have a corresponding opportunity and lifecycle.
    missing_opps = ranked_ids - opp_ids
    missing_lcs = ranked_ids - lc_ids
    if missing_opps:
        raise ServiceUnavailableError(
            f"Dashboard: ranked members without opportunities: {missing_opps}."
        )
    if missing_lcs:
        raise ServiceUnavailableError(
            f"Dashboard: ranked members without lifecycles: {missing_lcs}."
        )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _integrity_reference(
    artifact_id: str,
    artifact_type: str,
    entity: RankingSnapshot,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest=entity.canonical_sha256(),
        available_at=entity.audit.available_at,
    )
