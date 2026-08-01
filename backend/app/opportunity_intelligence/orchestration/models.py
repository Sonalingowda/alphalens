"""Immutable messages and audit records for application orchestration."""

from dataclasses import dataclass
from enum import StrEnum

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    DashboardPage,
    DetectionAttempt,
    EvidencePackage,
    ExplanationArtifact,
    FeatureSnapshot,
    IndicatorValue,
    MarketContext,
    MarketSnapshot,
    Notification,
    Opportunity,
    OpportunityCandidate,
    OpportunityDetail,
    OpportunityLifecycle,
    QualificationRecord,
    RankingSnapshot,
    ScoreResult,
)
from app.opportunity_intelligence.domain.primitives import (
    DomainValidationError,
    validate_identifier,
    validate_sha256,
)
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery


class PipelineStage(StrEnum):
    MARKET_SNAPSHOT = "MARKET_SNAPSHOT"
    FEATURE_SNAPSHOT = "FEATURE_SNAPSHOT"
    MARKET_CONTEXT = "MARKET_CONTEXT"
    OPPORTUNITY_DETECTION = "OPPORTUNITY_DETECTION"
    EVIDENCE = "EVIDENCE"
    OPPORTUNITY_ASSESSMENT = "OPPORTUNITY_ASSESSMENT"
    QUALIFICATION = "QUALIFICATION"
    SCORING = "SCORING"
    RANKING = "RANKING"
    LIFECYCLE = "LIFECYCLE"
    NOTIFICATION = "NOTIFICATION"
    DASHBOARD = "DASHBOARD"
    INDICATORS = "INDICATORS"
    EXPLANATION = "EXPLANATION"
    OPPORTUNITY_DETAIL = "OPPORTUNITY_DETAIL"


class PipelineStageStatus(StrEnum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class PipelineOutcome(StrEnum):
    COMPLETED = "COMPLETED"
    NO_CANDIDATE = "NO_CANDIDATE"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    POLICY_BLOCKED = "POLICY_BLOCKED"


@dataclass(frozen=True, slots=True)
class PipelineRunRequest(CanonicalModel):
    run_id: str
    query: ScopedRepositoryQuery
    previous_lifecycle: OpportunityLifecycle | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.run_id, "Pipeline run identifier")


@dataclass(frozen=True, slots=True)
class PipelineStageRecord(CanonicalModel):
    sequence: int
    stage: PipelineStage
    status: PipelineStageStatus
    artifact_ids: tuple[str, ...]
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.sequence <= 0:
            raise DomainValidationError("Pipeline stage sequence must be positive.")
        for artifact_id in self.artifact_ids:
            validate_identifier(artifact_id, "Pipeline stage artifact")
        if len(self.artifact_ids) != len(set(self.artifact_ids)):
            raise DomainValidationError("Pipeline stage artifacts must be unique.")
        if self.status is PipelineStageStatus.BLOCKED:
            if self.reason_code is None:
                raise DomainValidationError("Blocked stage requires a reason code.")
            validate_identifier(self.reason_code, "Pipeline block reason")
        elif self.reason_code is not None:
            raise DomainValidationError(
                "Completed pipeline stage cannot contain a block reason."
            )


@dataclass(frozen=True, slots=True)
class PipelineRunResult(CanonicalModel):
    run_id: str
    outcome: PipelineOutcome
    stages: tuple[PipelineStageRecord, ...]
    trace_hash: str
    market_snapshot: MarketSnapshot
    feature_snapshot: FeatureSnapshot
    market_context: MarketContext
    detection_attempt: DetectionAttempt
    candidate: OpportunityCandidate | None = None
    evidence: EvidencePackage | None = None
    opportunity: Opportunity | None = None
    qualification: QualificationRecord | None = None
    score: ScoreResult | None = None
    ranking: RankingSnapshot | None = None
    lifecycle: OpportunityLifecycle | None = None
    notifications: tuple[Notification, ...] = ()
    dashboard: DashboardPage | None = None
    indicators: tuple[IndicatorValue, ...] = ()
    explanation: ExplanationArtifact | None = None
    detail: OpportunityDetail | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.run_id, "Pipeline result identifier")
        validate_sha256(self.trace_hash, "Pipeline trace hash")
        if not self.stages:
            raise DomainValidationError("Pipeline result requires stage records.")
        sequences = tuple(stage.sequence for stage in self.stages)
        if sequences != tuple(range(1, len(self.stages) + 1)):
            raise DomainValidationError(
                "Pipeline stages must have contiguous ordered sequences."
            )
        if self.outcome is PipelineOutcome.COMPLETED:
            required = (
                self.candidate,
                self.evidence,
                self.opportunity,
                self.qualification,
                self.score,
                self.ranking,
                self.lifecycle,
                self.dashboard,
                self.explanation,
                self.detail,
            )
            if any(item is None for item in required):
                raise DomainValidationError(
                    "Completed pipeline result requires every canonical output."
                )


class PipelineExecutionError(RuntimeError):
    """Fail-closed pipeline failure carrying its immutable partial audit trace."""

    def __init__(
        self,
        run_id: str,
        stage: PipelineStage,
        stages: tuple[PipelineStageRecord, ...],
        trace_hash: str,
    ) -> None:
        self.run_id = run_id
        self.stage = stage
        self.stages = stages
        self.trace_hash = trace_hash
        super().__init__(f"Pipeline {run_id} failed closed at {stage.value}.")
