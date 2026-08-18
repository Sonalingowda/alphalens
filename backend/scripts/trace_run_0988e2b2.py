"""Trace the exact run_id pipeline.run.binance.spot.BTCUSDT.5m.1787035500000.snapshot.0988e2b2."""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import (
    DashboardProjectionPostgreSQLRepository,
    DetectionPostgreSQLRepository,
    EvidencePostgreSQLRepository,
    ExplanationPostgreSQLRepository,
    FeatureSnapshotPostgreSQLRepository,
    LifecyclePostgreSQLRepository,
    MarketContextPostgreSQLRepository,
    MarketSnapshotPostgreSQLRepository,
    NotificationPostgreSQLRepository,
    OpportunityDetailPostgreSQLRepository,
    OpportunityPostgreSQLRepository,
    OpportunityPlanPostgreSQLRepository,
    QualificationPostgreSQLRepository,
    RankingPostgreSQLRepository,
    ScoringPostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.persistence.database import session_factory
from app.runtime_assessment import RuntimeAssessmentService
from app.runtime_context import RuntimeMarketContextService
from app.runtime_dashboard import RuntimeDashboardProjectionService
from app.runtime_detail import RuntimeOpportunityDetailProjectionService
from app.runtime_detection import RuntimeOpportunityDetectionService
from app.runtime_evidence import RuntimeEvidenceService
from app.runtime_features import RuntimeFeatureEngine
from app.runtime_indicators import RuntimeIndicatorService
from app.runtime_lifecycle import RuntimeLifecycleService
from app.runtime_notification import RuntimeNotificationService
from app.runtime_opportunity_plan import RuntimeOpportunityPlanService
from app.runtime_qualification import RuntimeQualificationService
from app.runtime_ranking import RuntimeRankingService
from app.runtime_scoring import RuntimeScoringService


SCOPE = MarketScope(instrument="BTCUSDT", timeframe="5m")
CODE_VERSION = "alphalens.runtime.1.0.0"
TARGET_SNAPSHOT_ID = "binance.spot.BTCUSDT.5m.1787035500000.snapshot"
TARGET_AVAILABLE_AT = datetime(2026, 8, 18, 6, 50, tzinfo=timezone.utc)
RUN_ID = "pipeline.run.binance.spot.BTCUSDT.5m.1787035500000.snapshot.0988e2b2"


def _json_safe(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return json.dumps([_json_safe(v) for v in value], sort_keys=True)
    return repr(value)


def _artifact_summary(value: Any) -> dict[str, Any]:
    if value is None:
        return {"status": "NONE"}
    summary = {}
    for field in ("snapshot_id", "context_id", "attempt_id", "candidate_id",
                  "package_id", "opportunity_version_id", "qualification_id",
                  "score_id", "snapshot_id", "detail_id", "explanation_id",
                  "notification_id", "current_event_id"):
        if hasattr(value, field):
            summary[field] = getattr(value, field)
    if hasattr(value, "state"):
        summary["state"] = str(value.state)
    if hasattr(value, "outcome"):
        summary["outcome"] = str(value.outcome)
    if hasattr(value, "reason_codes"):
        summary["reason_codes"] = tuple(value.reason_codes)
    return summary


async def _trace_stage(name: str, operation) -> tuple[Any, Exception | None]:
    print(f"\n{'='*70}")
    print(f"STAGE: {name}")
    print(f"{'='*70}")
    try:
        result = await operation()
        summary = _artifact_summary(result)
        print(f"  STATUS: OK")
        print(f"  ARTIFACT: {json.dumps(summary, default=str, sort_keys=True, indent=4)}")
        return result, None
    except Exception as error:
        print(f"  STATUS: FAILED")
        print(f"  ERROR: {type(error).__name__}: {error}")
        return None, error


async def main() -> None:
    print(f"TRACING RUN: {RUN_ID}")
    print(f"TARGET SNAPSHOT: {TARGET_SNAPSHOT_ID}")
    print(f"TARGET AVAILABLE_AT: {TARGET_AVAILABLE_AT.isoformat()}")
    print(f"SCOPE: {SCOPE.instrument} {SCOPE.timeframe}")

    # Initialize repositories
    market_snapshots = MarketSnapshotPostgreSQLRepository(session_factory)
    feature_snapshots = FeatureSnapshotPostgreSQLRepository(session_factory)
    market_contexts = MarketContextPostgreSQLRepository(session_factory)
    detections = DetectionPostgreSQLRepository(session_factory)
    evidence_repo = EvidencePostgreSQLRepository(session_factory)
    opportunities = OpportunityPostgreSQLRepository(session_factory)
    plans = OpportunityPlanPostgreSQLRepository(session_factory)
    qualifications = QualificationPostgreSQLRepository(session_factory)
    scores = ScoringPostgreSQLRepository(session_factory)
    rankings = RankingPostgreSQLRepository(session_factory)
    dashboard_repo = DashboardProjectionPostgreSQLRepository(session_factory)
    detail_repo = OpportunityDetailPostgreSQLRepository(session_factory)
    explanations = ExplanationPostgreSQLRepository(session_factory)
    notifications = NotificationPostgreSQLRepository(session_factory)
    lifecycles = LifecyclePostgreSQLRepository(session_factory)

    # Initialize services
    feature_engine = RuntimeFeatureEngine(
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        code_version=CODE_VERSION,
    )
    context_service = RuntimeMarketContextService(
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        code_version=CODE_VERSION,
    )
    detection_service = RuntimeOpportunityDetectionService(
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        detections=detections,
        code_version=CODE_VERSION,
    )
    evidence_service = RuntimeEvidenceService(
        candidates=detections,
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        evidence=evidence_repo,
        code_version=CODE_VERSION,
    )
    plan_service = RuntimeOpportunityPlanService(code_version=CODE_VERSION)
    assessment_service = RuntimeAssessmentService(
        candidates=detections,
        evidence=evidence_repo,
        market_snapshots=market_snapshots,
        feature_snapshots=feature_snapshots,
        market_contexts=market_contexts,
        opportunities=opportunities,
        plans_repository=plans,
        plans=plan_service,
        code_version=CODE_VERSION,
    )
    qualification_service = RuntimeQualificationService(
        opportunities=opportunities,
        evidence=evidence_repo,
        market_contexts=market_contexts,
        feature_snapshots=feature_snapshots,
        market_snapshots=market_snapshots,
        qualifications=qualifications,
        code_version=CODE_VERSION,
    )
    scoring_service = RuntimeScoringService(
        opportunities=opportunities,
        qualifications=qualifications,
        evidence=evidence_repo,
        market_contexts=market_contexts,
        scores=scores,
        code_version=CODE_VERSION,
    )
    ranking_service = RuntimeRankingService(
        scores=scores,
        qualifications=qualifications,
        opportunities=opportunities,
        rankings=rankings,
        code_version=CODE_VERSION,
    )
    notification_service = RuntimeNotificationService(
        rankings=rankings,
        opportunities=opportunities,
        notifications=notifications,
        code_version=CODE_VERSION,
    )
    dashboard_service = RuntimeDashboardProjectionService(
        rankings=rankings,
        dashboard=dashboard_repo,
        plans=plans,
        code_version=CODE_VERSION,
    )
    lifecycle_service = RuntimeLifecycleService(lifecycles=lifecycles)
    indicator_service = RuntimeIndicatorService()
    detail_service = RuntimeOpportunityDetailProjectionService(
        opportunities=opportunities,
        market_snapshots=market_snapshots,
        market_contexts=market_contexts,
        evidence=evidence_repo,
        explanations=explanations,
        details=detail_repo,
        code_version=CODE_VERSION,
    )

    # Stub explanation service (same as runtime_pipeline.py)
    from app.runtime_pipeline import _StubExplanationService
    explanation_service = _StubExplanationService(explanations)

    # Query to load the target snapshot
    query = ScopedRepositoryQuery(
        scope=SCOPE,
        as_of=TARGET_AVAILABLE_AT,
        limit=1,
    )

    errors = []

    # Stage 1: MarketSnapshot
    market, err = await _trace_stage(
        "MarketSnapshot",
        lambda: market_snapshots.get_latest(query),
    )
    if err:
        errors.append(("MarketSnapshot", err))
        print("\nFATAL: Cannot proceed without MarketSnapshot")
        return
    print(f"  Expected snapshot_id: {TARGET_SNAPSHOT_ID}")
    print(f"  Actual snapshot_id:   {market.snapshot_id}")
    print(f"  MATCH: {market.snapshot_id == TARGET_SNAPSHOT_ID}")

    # Stage 2: FeatureSnapshot
    features, err = await _trace_stage(
        "FeatureSnapshot",
        lambda: feature_engine.resolve(market),
    )
    if err:
        errors.append(("FeatureSnapshot", err))
        return

    # Stage 3: MarketContext
    context, err = await _trace_stage(
        "MarketContext",
        lambda: context_service.build(market, features),
    )
    if err:
        errors.append(("MarketContext", err))
        return

    # Stage 4: Detection
    detection_result, err = await _trace_stage(
        "Detection",
        lambda: detection_service.detect(market, features, context),
    )
    if err:
        errors.append(("Detection", err))
        return
    attempt, candidate = detection_result
    if candidate is None:
        print(f"\n  PIPELINE TERMINATED: No candidate detected (state={attempt.state})")
        return

    # Stage 5: Evidence
    evidence, err = await _trace_stage(
        "Evidence",
        lambda: evidence_service.assemble(candidate, market, features, context),
    )
    if err:
        errors.append(("Evidence", err))
        return

    # Stage 6: Assessment
    opportunity, err = await _trace_stage(
        "Assessment",
        lambda: assessment_service.assess(candidate, evidence, context),
    )
    if err:
        errors.append(("Assessment", err))
        return

    # Stage 7: Qualification
    qualification, err = await _trace_stage(
        "Qualification",
        lambda: qualification_service.qualify(opportunity, evidence, context),
    )
    if err:
        errors.append(("Qualification", err))
        return
    if str(qualification.outcome) != "QUALIFIED":
        print(f"\n  PIPELINE TERMINATED: {qualification.outcome}")
        return

    # Stage 8: Scoring
    score, err = await _trace_stage(
        "Scoring",
        lambda: scoring_service.score(opportunity, qualification, evidence, context),
    )
    if err:
        errors.append(("Scoring", err))
        return

    # Stage 9: Ranking
    ranking, err = await _trace_stage(
        "Ranking",
        lambda: ranking_service.rank(
            (opportunity,),
            (qualification,),
            (score,),
            market.audit.available_at,
        ),
    )
    if err:
        errors.append(("Ranking", err))
        return

    # Stage 10: LifecycleEvent
    lifecycle, err = await _trace_stage(
        "LifecycleEvent",
        lambda: lifecycle_service.advance(
            opportunity,
            qualification,
            ranking,
            None,  # no previous lifecycle
        ),
    )
    if err:
        errors.append(("LifecycleEvent", err))
        return

    # Stage 11: Notification
    notification_list, err = await _trace_stage(
        "Notification",
        lambda: notification_service.create_intents(
            ranking,
            (opportunity,),
            (lifecycle,),
        ),
    )
    if err:
        errors.append(("Notification", err))
        return
    print(f"  Notifications created: {len(notification_list)}")
    for n in notification_list:
        print(f"    - {n.notification_id}")

    # Stage 12: DashboardPage
    dashboard, err = await _trace_stage(
        "DashboardPage",
        lambda: dashboard_service.project(
            ranking,
            (opportunity,),
            (lifecycle,),
        ),
    )
    if err:
        errors.append(("DashboardPage", err))
        return

    # Stage 13: Indicators
    indicator_list, err = await _trace_stage(
        "Indicators",
        lambda: indicator_service.project(features),
    )
    if err:
        errors.append(("Indicators", err))
        return
    print(f"  Indicators created: {len(indicator_list)}")

    # Stage 14: ExplanationArtifact
    explanation, err = await _trace_stage(
        "ExplanationArtifact",
        lambda: explanation_service.explain(
            opportunity,
            evidence,
            context,
            lifecycle,
        ),
    )
    if err:
        errors.append(("ExplanationArtifact", err))
        return

    # Stage 15: OpportunityDetail
    detail, err = await _trace_stage(
        "OpportunityDetail",
        lambda: detail_service.project(
            opportunity,
            market,
            indicator_list,
            context,
            evidence,
            explanation,
            lifecycle,
        ),
    )
    if err:
        errors.append(("OpportunityDetail", err))
        return

    # Stage 16: Opportunity API (verify detail can be loaded)
    async def verify_api():
        from app.opportunity_intelligence.persistence import (
            OpportunityDetailPostgreSQLRepository,
        )
        repo = OpportunityDetailPostgreSQLRepository(session_factory)
        loaded = await repo.get_by_id(
            __import__(
                "app.opportunity_intelligence.repositories",
                fromlist=["EntityId"],
            ).EntityId(detail.detail_id)
        )
        return loaded

    api_result, err = await _trace_stage(
        "OpportunityDetail (API reload)",
        verify_api,
    )
    if err:
        errors.append(("Opportunity API", err))
        return

    # Summary
    print(f"\n{'='*70}")
    print(f"PIPELINE TRACE COMPLETE")
    print(f"{'='*70}")
    if errors:
        print(f"\nFAILURES:")
        for stage_name, error in errors:
            print(f"  {stage_name}: {type(error).__name__}: {error}")
    else:
        print(f"\nALL 16 STAGES PASSED")
        print(f"\nArtifacts produced:")
        print(f"  1. MarketSnapshot:      {market.snapshot_id}")
        print(f"  2. FeatureSnapshot:     {features.snapshot_id}")
        print(f"  3. MarketContext:       {context.context_id}")
        print(f"  4. DetectionAttempt:    {attempt.attempt_id}")
        print(f"  5. OpportunityCandidate: {candidate.candidate_id}")
        print(f"  6. EvidencePackage:     {evidence.package_id}")
        print(f"  7. OpportunityPlan:     (persisted by assessment)")
        print(f"  8. Opportunity:         {opportunity.opportunity_version_id}")
        print(f"  9. QualificationRecord: {qualification.qualification_id}")
        print(f" 10. ScoreResult:         {score.score_id}")
        print(f" 11. RankingSnapshot:     {ranking.snapshot_id}")
        print(f" 12. LifecycleEvent:      {lifecycle.current_event_id}")
        print(f" 13. Notifications:       {len(notification_list)} created")
        print(f" 14. DashboardPage:       ref={dashboard.ranking_snapshot_reference.artifact_id}")
        print(f" 15. Indicators:          {len(indicator_list)} projected")
        print(f" 16. ExplanationArtifact: {explanation.explanation_id}")
        print(f" 17. OpportunityDetail:   {detail.detail_id}")


if __name__ == "__main__":
    asyncio.run(main())
