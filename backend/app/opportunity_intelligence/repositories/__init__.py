"""Stable Version 1.0.0 Opportunity Intelligence repository interface exports."""

from app.opportunity_intelligence.repositories.base import (
    REPOSITORY_INTERFACE_VERSION,
    ImmutableRepository,
)
from app.opportunity_intelligence.repositories.delivery import (
    LifecycleRepository,
    NotificationRepository,
    OpportunityPlanRepository,
    RankingRepository,
)
from app.opportunity_intelligence.repositories.errors import (
    ContractViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidScopeError,
    RepositoryError,
    StorageUnavailableError,
    ValidationError,
    VersionConflictError,
)
from app.opportunity_intelligence.repositories.governance import (
    RuntimeGovernanceRepository,
)
from app.opportunity_intelligence.repositories.intelligence import (
    DetectionRepository,
    EvidenceRepository,
    OpportunityRepository,
    QualificationRepository,
    ScoringRepository,
)
from app.opportunity_intelligence.repositories.projections import (
    DashboardProjectionRepository,
    ExplanationRepository,
    OpportunityDetailRepository,
)
from app.opportunity_intelligence.repositories.queries import (
    EntityAsOfQuery,
    EntityId,
    HistoryQuery,
    RepositoryListQuery,
    RepositoryPage,
    ScopedRepositoryQuery,
)
from app.opportunity_intelligence.repositories.snapshots import (
    FeatureSnapshotRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
)

__all__ = (
    "ContractViolationError",
    "DashboardProjectionRepository",
    "DetectionRepository",
    "DuplicateEntityError",
    "EntityAsOfQuery",
    "EntityId",
    "EntityNotFoundError",
    "EvidenceRepository",
    "ExplanationRepository",
    "FeatureSnapshotRepository",
    "HistoryQuery",
    "ImmutableRepository",
    "InvalidScopeError",
    "LifecycleRepository",
    "MarketContextRepository",
    "MarketSnapshotRepository",
    "NotificationRepository",
    "OpportunityDetailRepository",
    "OpportunityPlanRepository",
    "OpportunityRepository",
    "QualificationRepository",
    "REPOSITORY_INTERFACE_VERSION",
    "RankingRepository",
    "RepositoryError",
    "RepositoryListQuery",
    "RepositoryPage",
    "RuntimeGovernanceRepository",
    "ScopedRepositoryQuery",
    "ScoringRepository",
    "StorageUnavailableError",
    "ValidationError",
    "VersionConflictError",
)
