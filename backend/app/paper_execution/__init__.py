"""Isolated paper execution for ranking-admitted AlphaLens opportunities."""

from app.paper_execution.domain import (
    PaperExecution,
    PaperExecutionState,
    PaperExit,
    PaperExitReason,
    PaperOutcome,
    PaperPosition,
    PaperTrackingEvent,
    PaperTrackingEventType,
)
from app.paper_execution.service import PaperExecutionService
from app.paper_execution.selection import (
    PaperTrackingAuthoritativeLoader,
    PaperTrackingSelection,
    PaperTrackingSelectionError,
    PaperTrackingSelectionService,
    RepositoryBackedPaperTrackingAuthoritativeLoader,
    confirmed_scenario_hash,
)
from app.paper_execution.observation import (
    PaperObservationResult,
    PaperTrackingObservationService,
)
from app.paper_execution.persistence import InMemoryPaperExecutionRepository, PaperExecutionPersistence
from app.paper_execution.persistence import InMemoryPaperSuccessorPlanRepository, PaperSuccessorPlanPersistence
from app.paper_execution.successor import (
    APPROVED_POPULATION_MANIFEST_SHA256,
    SUCCESSOR_POLICY_HASH,
    SUCCESSOR_POLICY_ID,
    SUCCESSOR_POLICY_VERSION,
    PaperSuccessorPlan,
    derive_successor_plan,
    eligible_opportunities,
    population_manifest_sha256,
    successor_plan_id,
)

__all__ = (
    "PaperExecution",
    "PaperExecutionService",
    "PaperTrackingSelection",
    "PaperTrackingSelectionError",
    "PaperTrackingAuthoritativeLoader",
    "PaperTrackingSelectionService",
    "RepositoryBackedPaperTrackingAuthoritativeLoader",
    "confirmed_scenario_hash",
    "PaperTrackingEvent",
    "PaperTrackingEventType",
    "PaperObservationResult",
    "PaperTrackingObservationService",
    "PaperExecutionPersistence",
    "InMemoryPaperExecutionRepository",
    "PaperExecutionState",
    "PaperExit",
    "PaperExitReason",
    "PaperOutcome",
    "PaperPosition",
    "PaperSuccessorPlan",
    "derive_successor_plan",
    "eligible_opportunities",
    "population_manifest_sha256",
    "successor_plan_id",
    "APPROVED_POPULATION_MANIFEST_SHA256",
    "SUCCESSOR_POLICY_HASH",
    "SUCCESSOR_POLICY_ID",
    "SUCCESSOR_POLICY_VERSION",
    "InMemoryPaperSuccessorPlanRepository",
    "PaperSuccessorPlanPersistence",
)
