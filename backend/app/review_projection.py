"""Read-only human review projection over immutable ranked opportunities."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    IntegrityReference,
    MarketScope,
    Opportunity,
    PriceRange,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.primitives import validate_utc
from app.opportunity_intelligence.repositories import RepositoryListQuery


REVIEW_CONTRACT_VERSION = "13A.1.0"
INFORMATIONAL_ONLY = "INFORMATIONAL_ONLY_NO_EXECUTION"


class ReviewProjectionIntegrityError(ValueError):
    """Raised when immutable review source lineage is inconsistent."""


class ReviewValidity(StrEnum):
    CURRENT = "CURRENT"
    EXPIRED = "EXPIRED"
    NOT_REVIEWABLE_MISSING_VALIDITY = "NOT_REVIEWABLE_MISSING_VALIDITY"


class _ListRepository(Protocol):
    async def list(self, query: RepositoryListQuery): ...


@dataclass(frozen=True, slots=True)
class HumanReviewItem(CanonicalModel):
    """One deterministic, non-persistent human review item."""

    review_contract_version: str
    as_of: datetime
    opportunity_id: str
    opportunity_version_id: str
    instrument: str
    timeframe: str
    direction: str
    signal_timestamp: datetime
    valid_until: datetime | None
    validity_status: ReviewValidity
    reference_price: Decimal
    entry_zone: PriceRange
    invalidation_price: Decimal
    target_price: Decimal
    ranking_snapshot_id: str
    rank: int
    candidate_set_size: int
    qualification_reference: IntegrityReference | None
    score_reference: IntegrityReference | None
    opportunity_version_hash: str
    opportunity_plan_id: str
    opportunity_plan_hash: str
    policy_id: str
    policy_version: str
    policy_hash: str
    evidence_references: tuple[IntegrityReference, ...]
    provenance_references: tuple[IntegrityReference, ...]
    safety_designation: str

    @property
    def payload_hash(self) -> str:
        return self.canonical_sha256()


@dataclass(frozen=True, slots=True)
class HumanReviewProjection(CanonicalModel):
    """An isolated read-only projection; it has no persistence adapter."""

    review_contract_version: str
    as_of: datetime
    scope: MarketScope
    ranking_snapshot_id: str | None
    items: tuple[HumanReviewItem, ...]

    @property
    def item_hashes(self) -> tuple[str, ...]:
        return tuple(item.payload_hash for item in self.items)

    @property
    def manifest_hash(self) -> str:
        return canonical_sha256(self.items)


class HumanReviewProjectionService:
    """Build a review projection using only immutable repository reads."""

    def __init__(
        self,
        *,
        opportunities: _ListRepository,
        rankings: _ListRepository,
    ) -> None:
        self._opportunities = opportunities
        self._rankings = rankings

    async def build(
        self,
        *,
        scope: MarketScope,
        as_of: datetime,
    ) -> HumanReviewProjection:
        validate_utc(as_of, "Review as-of")
        ranking_page = await self._rankings.list(
            RepositoryListQuery(as_of=as_of, limit=10_000, scope=scope)
        )
        rankings = tuple(ranking_page.items)
        if not rankings:
            return HumanReviewProjection(
                REVIEW_CONTRACT_VERSION, as_of, scope, None, ()
            )
        ranking = max(
            rankings,
            key=lambda item: (item.generated_at, item.snapshot_id),
        )
        opportunities_page = await self._opportunities.list(
            RepositoryListQuery(as_of=as_of, limit=10_000, scope=scope)
        )
        by_identity: dict[tuple[str, str], Opportunity] = {}
        for opportunity in opportunities_page.items:
            key = (opportunity.opportunity_id, opportunity.opportunity_version_id)
            if key in by_identity:
                raise ReviewProjectionIntegrityError(
                    f"Duplicate OpportunityVersion identity: {key!r}"
                )
            by_identity[key] = opportunity

        memberships = sorted(
            ranking.memberships,
            key=lambda item: (item.rank, item.opportunity_version_id),
        )
        items = tuple(
            self._item(
                opportunity=by_identity.get(
                    (membership.opportunity_id, membership.opportunity_version_id)
                ),
                membership=membership,
                ranking=ranking,
                scope=scope,
                as_of=as_of,
            )
            for membership in memberships
        )
        return HumanReviewProjection(
            REVIEW_CONTRACT_VERSION,
            as_of,
            scope,
            ranking.snapshot_id,
            items,
        )

    @staticmethod
    def _item(*, opportunity, membership, ranking, scope, as_of) -> HumanReviewItem:
        if opportunity is None:
            raise ReviewProjectionIntegrityError(
                "Ranking membership has no matching OpportunityVersion."
            )
        plan = opportunity.plan
        if plan is None:
            raise ReviewProjectionIntegrityError(
                "Ranking-admitted OpportunityVersion has no OpportunityPlan."
            )
        if opportunity.scope != scope or plan.scope != scope:
            raise ReviewProjectionIntegrityError("Opportunity scope does not match review scope.")
        if plan.opportunity_id != opportunity.opportunity_id:
            raise ReviewProjectionIntegrityError("OpportunityPlan identity mismatch.")
        if plan.assessment_id != opportunity.assessment_id or plan.decision_id != opportunity.decision_id:
            raise ReviewProjectionIntegrityError("OpportunityPlan lineage mismatch.")
        if membership.opportunity_id != opportunity.opportunity_id or membership.opportunity_version_id != opportunity.opportunity_version_id:
            raise ReviewProjectionIntegrityError("Ranking membership identity mismatch.")
        if not opportunity.audit.provenance.source_references or not plan.audit.provenance.source_references:
            raise ReviewProjectionIntegrityError("Missing immutable provenance references.")
        if plan.policy not in plan.audit.provenance.policy_references:
            raise ReviewProjectionIntegrityError("OpportunityPlan policy provenance mismatch.")
        if opportunity.decision_policy not in opportunity.audit.provenance.policy_references:
            raise ReviewProjectionIntegrityError("Opportunity policy provenance mismatch.")

        if plan.valid_until is None:
            status = ReviewValidity.NOT_REVIEWABLE_MISSING_VALIDITY
        elif as_of <= plan.valid_until:
            status = ReviewValidity.CURRENT
        else:
            status = ReviewValidity.EXPIRED

        evidence = {
            reference.artifact_id: reference
            for reference in (
                opportunity.evidence_package_reference,
                opportunity.context_reference,
                opportunity.qualification_reference,
                opportunity.score_reference,
            )
            if reference is not None
        }
        provenance = {
            reference.artifact_id: reference
            for reference in (
                *opportunity.audit.provenance.source_references,
                *plan.audit.provenance.source_references,
            )
        }
        return HumanReviewItem(
            review_contract_version=REVIEW_CONTRACT_VERSION,
            as_of=as_of,
            opportunity_id=opportunity.opportunity_id,
            opportunity_version_id=opportunity.opportunity_version_id,
            instrument=scope.instrument,
            timeframe=scope.timeframe,
            direction=plan.direction.value,
            signal_timestamp=plan.audit.available_at,
            valid_until=plan.valid_until,
            validity_status=status,
            reference_price=plan.reference_price,
            entry_zone=plan.entry_zone,
            invalidation_price=plan.invalidation_price,
            target_price=plan.targets[0].price,
            ranking_snapshot_id=ranking.snapshot_id,
            rank=membership.rank,
            candidate_set_size=membership.candidate_set_size,
            qualification_reference=opportunity.qualification_reference,
            score_reference=opportunity.score_reference,
            opportunity_version_hash=opportunity.canonical_sha256(),
            opportunity_plan_id=plan.plan_id,
            opportunity_plan_hash=plan.canonical_sha256(),
            policy_id=plan.policy.policy_id,
            policy_version=plan.policy.policy_version,
            policy_hash=plan.policy.integrity_digest,
            evidence_references=tuple(evidence[key] for key in sorted(evidence)),
            provenance_references=tuple(provenance[key] for key in sorted(provenance)),
            safety_designation=INFORMATIONAL_ONLY,
        )
