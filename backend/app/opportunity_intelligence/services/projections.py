"""Service ports for explanation and immutable read projections."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    DashboardPage,
    EvidencePackage,
    ExplanationArtifact,
    FeatureSnapshot,
    IndicatorValue,
    MarketContext,
    MarketSnapshot,
    Opportunity,
    OpportunityDetail,
    OpportunityLifecycle,
    RankingSnapshot,
)


@runtime_checkable
class IndicatorProjectionService(Protocol):
    """Project registered feature values into typed detail indicator records."""

    async def project(
        self,
        feature_snapshot: FeatureSnapshot,
    ) -> tuple[IndicatorValue, ...]:
        """Return registry-backed indicators without recalculating features."""
        ...


@runtime_checkable
class ExplanationService(Protocol):
    """Render reproducible factual explanations from canonical evidence."""

    async def explain(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
        lifecycle: OpportunityLifecycle,
    ) -> ExplanationArtifact:
        """Return a deterministic template artifact or fail closed."""
        ...


@runtime_checkable
class DashboardService(Protocol):
    """Build a snapshot-bound read projection without changing canonical rank."""

    async def project(
        self,
        ranking: RankingSnapshot,
        opportunities: tuple[Opportunity, ...],
        lifecycles: tuple[OpportunityLifecycle, ...],
    ) -> DashboardPage:
        """Return an immutable dashboard page in canonical rank order."""
        ...


@runtime_checkable
class OpportunityDetailService(Protocol):
    """Build one complete immutable opportunity-detail projection."""

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
        """Return a consistent detail projection or fail closed."""
        ...
