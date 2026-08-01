"""Immutable Version 1.0.0 Opportunity Intelligence domain models."""

from app.opportunity_intelligence.domain.context import (
    ContextCategory,
    ContextComponent,
    ContextObservation,
    ContextStatus,
    MarketContext,
)
from app.opportunity_intelligence.domain.detection import (
    CandidateAttemptState,
    DetectionAttempt,
    OpportunityCandidate,
)
from app.opportunity_intelligence.domain.evidence import (
    EvidenceCategory,
    EvidenceItem,
    EvidencePackage,
    EvidencePolarity,
    EvidenceSeverity,
)
from app.opportunity_intelligence.domain.explanation import (
    ExplanationArtifact,
    ExplanationSection,
    ExplanationSentence,
    TemplateBinding,
)
from app.opportunity_intelligence.domain.governance import (
    ComponentHealthCheck,
    HealthStatus,
    RuntimeHealthRecord,
)
from app.opportunity_intelligence.domain.lifecycle import (
    LifecycleEvent,
    LifecycleState,
    OpportunityLifecycle,
)
from app.opportunity_intelligence.domain.market import (
    FeatureSnapshot,
    FeatureSnapshotValue,
    MarketCandleSnapshot,
    MarketSnapshot,
)
from app.opportunity_intelligence.domain.notification import (
    DeliveryAttempt,
    DeliveryState,
    Notification,
    NotificationEventType,
)
from app.opportunity_intelligence.domain.opportunity import ConfidenceRecord, Opportunity
from app.opportunity_intelligence.domain.plan import (
    OpportunityPlan,
    PlanTarget,
)
from app.opportunity_intelligence.domain.qualification import (
    QualificationGateResult,
    QualificationRecord,
    QualificationOutcome,
    QualificationStatus,
)
from app.opportunity_intelligence.domain.scoring import (
    ScoreComponent,
    ScoreComponentAvailability,
    ScoreResult,
)
from app.opportunity_intelligence.domain.ranking import (
    RankingExclusion,
    RankingMembership,
    RankingSnapshot,
)
from app.opportunity_intelligence.domain.presentation import (
    DashboardItem,
    DashboardPage,
    IndicatorValue,
    OpportunityDetail,
)
from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DecimalRange,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    PolicyReference,
    PriceRange,
    Provenance,
    canonical_json,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.stances import OpportunityStance

__all__ = (
    "AuditMetadata",
    "CandidateAttemptState",
    "CanonicalModel",
    "ComponentHealthCheck",
    "ContextCategory",
    "ContextComponent",
    "ContextObservation",
    "ContextStatus",
    "ConfidenceRecord",
    "DashboardItem",
    "DashboardPage",
    "DecimalRange",
    "DeliveryAttempt",
    "DeliveryState",
    "DetectionAttempt",
    "DomainValidationError",
    "EvidenceCategory",
    "EvidenceItem",
    "EvidencePackage",
    "EvidencePolarity",
    "EvidenceSeverity",
    "ExplanationArtifact",
    "ExplanationSection",
    "ExplanationSentence",
    "FeatureSnapshot",
    "FeatureSnapshotValue",
    "HealthStatus",
    "IndicatorValue",
    "IntegrityReference",
    "LifecycleEvent",
    "LifecycleState",
    "MarketCandleSnapshot",
    "MarketContext",
    "MarketScope",
    "MarketSnapshot",
    "Notification",
    "NotificationEventType",
    "Opportunity",
    "OpportunityCandidate",
    "OpportunityDetail",
    "OpportunityLifecycle",
    "OpportunityPlan",
    "OpportunityStance",
    "PlanTarget",
    "PolicyReference",
    "PriceRange",
    "Provenance",
    "QualificationGateResult",
    "QualificationRecord",
    "QualificationOutcome",
    "QualificationStatus",
    "RankingExclusion",
    "RankingMembership",
    "RankingSnapshot",
    "RuntimeHealthRecord",
    "ScoreComponent",
    "ScoreComponentAvailability",
    "ScoreResult",
    "TemplateBinding",
    "canonical_json",
    "canonical_sha256",
)
