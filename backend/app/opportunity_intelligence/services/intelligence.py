"""Service ports for context, detection, evidence, and assessment."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    DetectionAttempt,
    EvidencePackage,
    FeatureSnapshot,
    MarketContext,
    MarketSnapshot,
    Opportunity,
    OpportunityCandidate,
    QualificationRecord,
    ScoreResult,
)


@runtime_checkable
class MarketContextService(Protocol):
    """Build descriptive context without creating a recommendation."""

    async def build(
        self,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
    ) -> MarketContext:
        """Return immutable point-in-time context or fail closed."""
        ...


@runtime_checkable
class OpportunityDetectionService(Protocol):
    """Apply an approved detection policy without assessing quality or stance."""

    async def detect(
        self,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
        market_context: MarketContext,
    ) -> tuple[DetectionAttempt, OpportunityCandidate | None]:
        """Return an attempt and candidate only when deterministic detection passes."""
        ...


@runtime_checkable
class EvidenceService(Protocol):
    """Assemble canonical supporting, contradicting, and contextual evidence."""

    async def assemble(
        self,
        candidate: OpportunityCandidate,
        market_snapshot: MarketSnapshot,
        feature_snapshot: FeatureSnapshot,
        market_context: MarketContext,
    ) -> EvidencePackage:
        """Return a complete immutable evidence package or fail closed."""
        ...


@runtime_checkable
class OpportunityAssessmentService(Protocol):
    """Create the canonical BUY/SELL/WAIT assessment under an approved policy."""

    async def assess(
        self,
        candidate: OpportunityCandidate,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> Opportunity:
        """Return an immutable assessment or raise PolicyUnavailableError."""
        ...


@runtime_checkable
class QualificationService(Protocol):
    """Evaluate publication eligibility separately from scoring and ranking."""

    async def qualify(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> QualificationRecord:
        """Return a complete gate record or raise PolicyUnavailableError."""
        ...


@runtime_checkable
class ScoringService(Protocol):
    """Produce transparent score components only under an approved policy."""

    async def score(
        self,
        opportunity: Opportunity,
        qualification: QualificationRecord,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> ScoreResult:
        """Return a complete score result or raise PolicyUnavailableError."""
        ...

