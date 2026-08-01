"""Deterministic policy-neutral Opportunity Intelligence orchestration."""

from dataclasses import dataclass

from app.opportunity_intelligence.domain import (
    CandidateAttemptState,
    DetectionAttempt,
    FeatureSnapshot,
    MarketContext,
    MarketSnapshot,
    QualificationOutcome,
    canonical_sha256,
)
from app.opportunity_intelligence.orchestration.models import (
    PipelineExecutionError,
    PipelineOutcome,
    PipelineRunRequest,
    PipelineRunResult,
    PipelineStage,
    PipelineStageRecord,
    PipelineStageStatus,
)
from app.opportunity_intelligence.services import (
    DashboardService,
    EvidenceService,
    ExplanationService,
    FeatureSnapshotService,
    IndicatorProjectionService,
    LifecycleService,
    MarketContextService,
    MarketScannerService,
    NotificationService,
    OpportunityAssessmentService,
    OpportunityDetectionService,
    OpportunityDetailService,
    PolicyUnavailableError,
    QualificationService,
    RankingService,
    ScoringService,
)


@dataclass(frozen=True, slots=True)
class OpportunityIntelligencePipeline:
    """Coordinate approved service ports without implementing their policies."""

    market_scanner: MarketScannerService
    feature_snapshots: FeatureSnapshotService
    market_contexts: MarketContextService
    detection: OpportunityDetectionService
    evidence: EvidenceService
    assessment: OpportunityAssessmentService
    qualification: QualificationService
    scoring: ScoringService
    ranking: RankingService
    lifecycle: LifecycleService
    notifications: NotificationService
    dashboard: DashboardService
    indicators: IndicatorProjectionService
    explanation: ExplanationService
    detail: OpportunityDetailService

    async def run(self, request: PipelineRunRequest) -> PipelineRunResult:
        records: list[PipelineStageRecord] = []
        active_stage = PipelineStage.MARKET_SNAPSHOT
        try:
            market = await self.market_scanner.scan(request.query)
            _complete(records, active_stage, market.snapshot_id)

            active_stage = PipelineStage.FEATURE_SNAPSHOT
            features = await self.feature_snapshots.resolve(market)
            _complete(records, active_stage, features.snapshot_id)

            active_stage = PipelineStage.MARKET_CONTEXT
            context = await self.market_contexts.build(market, features)
            _complete(records, active_stage, context.context_id)

            active_stage = PipelineStage.OPPORTUNITY_DETECTION
            attempt, candidate = await self.detection.detect(
                market,
                features,
                context,
            )
            detection_artifacts = (attempt.attempt_id,) + (
                (candidate.candidate_id,) if candidate is not None else ()
            )
            _complete(records, active_stage, *detection_artifacts)
            if candidate is None:
                outcome = (
                    PipelineOutcome.NO_CANDIDATE
                    if attempt.state is CandidateAttemptState.NOT_DETECTED
                    else PipelineOutcome.UNAVAILABLE
                )
                return _result(
                    request,
                    outcome,
                    records,
                    market,
                    features,
                    context,
                    attempt,
                )

            active_stage = PipelineStage.EVIDENCE
            evidence = await self.evidence.assemble(
                candidate,
                market,
                features,
                context,
            )
            _complete(records, active_stage, evidence.package_id)

            active_stage = PipelineStage.OPPORTUNITY_ASSESSMENT
            opportunity = await self.assessment.assess(candidate, evidence, context)
            _complete(records, active_stage, opportunity.opportunity_version_id)

            active_stage = PipelineStage.QUALIFICATION
            qualification = await self.qualification.qualify(
                opportunity,
                evidence,
                context,
            )
            _complete(records, active_stage, qualification.qualification_id)
            if qualification.outcome is not QualificationOutcome.QUALIFIED:
                outcome = (
                    PipelineOutcome.NOT_QUALIFIED
                    if qualification.outcome is QualificationOutcome.NOT_QUALIFIED
                    else PipelineOutcome.UNAVAILABLE
                )
                return _result(
                    request,
                    outcome,
                    records,
                    market,
                    features,
                    context,
                    attempt,
                    candidate=candidate,
                    evidence=evidence,
                    opportunity=opportunity,
                    qualification=qualification,
                )

            active_stage = PipelineStage.SCORING
            try:
                score = await self.scoring.score(
                    opportunity,
                    qualification,
                    evidence,
                    context,
                )
            except PolicyUnavailableError:
                _block(records, active_stage, "policy.unavailable")
                return _result(
                    request,
                    PipelineOutcome.POLICY_BLOCKED,
                    records,
                    market,
                    features,
                    context,
                    attempt,
                    candidate=candidate,
                    evidence=evidence,
                    opportunity=opportunity,
                    qualification=qualification,
                )
            _complete(records, active_stage, score.score_id)

            active_stage = PipelineStage.RANKING
            try:
                ranking = await self.ranking.rank(
                    (opportunity,),
                    (qualification,),
                    (score,),
                    request.query.as_of,
                )
            except PolicyUnavailableError:
                _block(records, active_stage, "policy.unavailable")
                return _result(
                    request,
                    PipelineOutcome.POLICY_BLOCKED,
                    records,
                    market,
                    features,
                    context,
                    attempt,
                    candidate=candidate,
                    evidence=evidence,
                    opportunity=opportunity,
                    qualification=qualification,
                    score=score,
                )
            _complete(records, active_stage, ranking.snapshot_id)

            active_stage = PipelineStage.LIFECYCLE
            lifecycle = await self.lifecycle.advance(
                opportunity,
                qualification,
                ranking,
                request.previous_lifecycle,
            )
            _complete(records, active_stage, lifecycle.current_event_id)

            active_stage = PipelineStage.NOTIFICATION
            notifications = await self.notifications.create_intents(
                ranking,
                (opportunity,),
                (lifecycle,),
            )
            _complete(
                records,
                active_stage,
                *(notification.notification_id for notification in notifications),
            )

            active_stage = PipelineStage.DASHBOARD
            dashboard = await self.dashboard.project(
                ranking,
                (opportunity,),
                (lifecycle,),
            )
            _complete(
                records,
                active_stage,
                dashboard.ranking_snapshot_reference.artifact_id,
            )

            active_stage = PipelineStage.INDICATORS
            indicators = await self.indicators.project(features)
            _complete(
                records,
                active_stage,
                *(indicator.indicator_id for indicator in indicators),
            )

            active_stage = PipelineStage.EXPLANATION
            explanation = await self.explanation.explain(
                opportunity,
                evidence,
                context,
                lifecycle,
            )
            _complete(records, active_stage, explanation.explanation_id)

            active_stage = PipelineStage.OPPORTUNITY_DETAIL
            detail = await self.detail.project(
                opportunity,
                market,
                indicators,
                context,
                evidence,
                explanation,
                lifecycle,
            )
            _complete(records, active_stage, detail.detail_id)

            return _result(
                request,
                PipelineOutcome.COMPLETED,
                records,
                market,
                features,
                context,
                attempt,
                candidate=candidate,
                evidence=evidence,
                opportunity=opportunity,
                qualification=qualification,
                score=score,
                ranking=ranking,
                lifecycle=lifecycle,
                notifications=notifications,
                dashboard=dashboard,
                indicators=indicators,
                explanation=explanation,
                detail=detail,
            )
        except PipelineExecutionError:
            raise
        except Exception as error:
            _block(records, active_stage, "service.failure")
            frozen_records = tuple(records)
            raise PipelineExecutionError(
                request.run_id,
                active_stage,
                frozen_records,
                _trace_hash(request.run_id, frozen_records),
            ) from error


def _complete(
    records: list[PipelineStageRecord],
    stage: PipelineStage,
    *artifact_ids: str,
) -> None:
    records.append(
        PipelineStageRecord(
            sequence=len(records) + 1,
            stage=stage,
            status=PipelineStageStatus.COMPLETED,
            artifact_ids=tuple(artifact_ids),
        )
    )


def _block(
    records: list[PipelineStageRecord],
    stage: PipelineStage,
    reason_code: str,
) -> None:
    records.append(
        PipelineStageRecord(
            sequence=len(records) + 1,
            stage=stage,
            status=PipelineStageStatus.BLOCKED,
            artifact_ids=(),
            reason_code=reason_code,
        )
    )


def _trace_hash(run_id: str, records: tuple[PipelineStageRecord, ...]) -> str:
    return canonical_sha256({"run_id": run_id, "stages": records})


def _result(
    request: PipelineRunRequest,
    outcome: PipelineOutcome,
    records: list[PipelineStageRecord],
    market_snapshot: MarketSnapshot,
    feature_snapshot: FeatureSnapshot,
    market_context: MarketContext,
    detection_attempt: DetectionAttempt,
    **outputs: object,
) -> PipelineRunResult:
    frozen_records = tuple(records)
    return PipelineRunResult(
        run_id=request.run_id,
        outcome=outcome,
        stages=frozen_records,
        trace_hash=_trace_hash(request.run_id, frozen_records),
        market_snapshot=market_snapshot,
        feature_snapshot=feature_snapshot,
        market_context=market_context,
        detection_attempt=detection_attempt,
        **outputs,  # type: ignore[arg-type]
    )
