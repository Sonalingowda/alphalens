"""Stable Version 1.0.0 Opportunity Intelligence service interface exports."""

from app.opportunity_intelligence.services.acquisition import (
    FeatureSnapshotService,
    MarketScannerService,
)
from app.opportunity_intelligence.services.delivery import (
    LifecycleService,
    NotificationService,
    OpportunityPlanService,
    RankingService,
)
from app.opportunity_intelligence.services.errors import (
    PipelineSuspendedError,
    PolicyUnavailableError,
    ServiceContractError,
    ServiceError,
    ServiceUnavailableError,
)
from app.opportunity_intelligence.services.governance import RuntimeGovernanceService
from app.opportunity_intelligence.services.intelligence import (
    EvidenceService,
    MarketContextService,
    OpportunityAssessmentService,
    OpportunityDetectionService,
    QualificationService,
    ScoringService,
)
from app.opportunity_intelligence.services.projections import (
    DashboardService,
    ExplanationService,
    IndicatorProjectionService,
    OpportunityDetailService,
)


SERVICE_INTERFACE_VERSION = "1.0.0"

__all__ = (
    "DashboardService",
    "EvidenceService",
    "ExplanationService",
    "FeatureSnapshotService",
    "IndicatorProjectionService",
    "LifecycleService",
    "MarketContextService",
    "MarketScannerService",
    "NotificationService",
    "OpportunityAssessmentService",
    "OpportunityDetectionService",
    "OpportunityDetailService",
    "OpportunityPlanService",
    "PipelineSuspendedError",
    "PolicyUnavailableError",
    "QualificationService",
    "RankingService",
    "RuntimeGovernanceService",
    "SERVICE_INTERFACE_VERSION",
    "ScoringService",
    "ServiceContractError",
    "ServiceError",
    "ServiceUnavailableError",
)
