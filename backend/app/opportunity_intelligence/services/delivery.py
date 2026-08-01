"""Service ports for ranking, plans, lifecycle, and notifications."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    EvidencePackage,
    MarketContext,
    Notification,
    Opportunity,
    OpportunityLifecycle,
    OpportunityPlan,
    QualificationRecord,
    RankingSnapshot,
    ScoreResult,
)


@runtime_checkable
class RankingService(Protocol):
    """Order qualified opportunities under an approved deterministic policy."""

    async def rank(
        self,
        opportunities: tuple[Opportunity, ...],
        qualifications: tuple[QualificationRecord, ...],
        scores: tuple[ScoreResult, ...],
        as_of: datetime,
    ) -> RankingSnapshot:
        """Return an immutable ranking snapshot or raise PolicyUnavailableError."""
        ...


@runtime_checkable
class OpportunityPlanService(Protocol):
    """Create optional complete informational plans under an approved policy."""

    async def create_plan(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> OpportunityPlan | None:
        """Return a complete plan, or absence when plan policy is unavailable."""
        ...


@runtime_checkable
class LifecycleService(Protocol):
    """Create immutable lifecycle histories and forward-only events."""

    async def advance(
        self,
        opportunity: Opportunity,
        qualification: QualificationRecord,
        ranking: RankingSnapshot,
        previous: OpportunityLifecycle | None,
    ) -> OpportunityLifecycle:
        """Return a successor lifecycle or fail closed on invalid transition."""
        ...


@runtime_checkable
class NotificationService(Protocol):
    """Create informational notification intents without delivering them."""

    async def create_intents(
        self,
        ranking: RankingSnapshot,
        opportunities: tuple[Opportunity, ...],
        lifecycles: tuple[OpportunityLifecycle, ...],
    ) -> tuple[Notification, ...]:
        """Return deterministic deduplicable intents under an approved policy."""
        ...
