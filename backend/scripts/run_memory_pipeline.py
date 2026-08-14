"""Run a full in-memory Opportunity Intelligence pipeline and print results.

This script uses the repository's in-memory persistence adapters and runtime
services to execute one pipeline cycle for a synthetic 5m BTCUSDT market
snapshot with features that should trigger a BUY detection.

It does not require external services and is intended for local debugging.
"""
import asyncio
from datetime import timezone
from dataclasses import replace
from decimal import Decimal

from app.opportunity_intelligence.orchestration.pipeline import OpportunityIntelligencePipeline
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.opportunity_intelligence.persistence.memory import (
    MarketSnapshotMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    OpportunityMemoryRepository,
    QualificationMemoryRepository,
    ScoringMemoryRepository,
    RankingMemoryRepository,
    DashboardProjectionMemoryRepository,
    OpportunityDetailMemoryRepository,
    ExplanationMemoryRepository,
    NotificationMemoryRepository,
)
from app.runtime_features.engine import RuntimeFeatureEngine
from app.runtime_context.service import RuntimeMarketContextService
from app.runtime_detection.service import RuntimeOpportunityDetectionService
from app.runtime_evidence.service import RuntimeEvidenceService
from app.runtime_assessment.service import RuntimeAssessmentService
from app.runtime_opportunity_plan.service import RuntimeOpportunityPlanService
from app.runtime_qualification.service import RuntimeQualificationService
from app.runtime_scoring.service import RuntimeScoringService
from app.runtime_ranking.service import RuntimeRankingService
from app.runtime_notification.service import RuntimeNotificationService
from app.runtime_dashboard.service import RuntimeDashboardProjectionService
from app.runtime_detail.service import RuntimeOpportunityDetailProjectionService
from app.opportunity_intelligence.domain import MarketScope

# Use the test fixtures to create a baseline market snapshot and feature snapshot
from tests.test_opportunity_domain_models import _market_snapshot, _feature_snapshot, CUTOFF

async def main():
    # Create in-memory repositories
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    detections = DetectionMemoryRepository()
    evidence_repo = EvidenceMemoryRepository()
    opportunities = OpportunityMemoryRepository()
    qualifications = QualificationMemoryRepository()
    scores = ScoringMemoryRepository()
    rankings = RankingMemoryRepository()
    dashboard_repo = DashboardProjectionMemoryRepository()
    detail_repo = OpportunityDetailMemoryRepository()
    explanations = ExplanationMemoryRepository()
    notifications = NotificationMemoryRepository()

    # Seed a market snapshot that matches BTCUSDT 5m
    base_market = _market_snapshot()
    market = replace(
        base_market,
        scope=MarketScope(instrument="BTCUSDT", timeframe="10m"),
    )

    # Persist market snapshot
    await markets.save(market)

    # Build a feature snapshot that will trigger a BUY: ema12 > ema26 and rsi >= 55
    # Create values by taking an existing feature snapshot and replacing values
    base_feature = _feature_snapshot()
    # Build new FeatureSnapshot with EMA12=101, EMA26=100, RSI=55
    from app.opportunity_intelligence.domain import FeatureSnapshotValue, IntegrityReference
    f_values = []
    # Use timestamps from market
    ts = market.candles[0].timestamp
    # Use the market's evidence cutoff as the availability for features so they are visible
    avail = market.audit.evidence_cutoff
    f_values.append(
        FeatureSnapshotValue(
            feature_identifier="exponential_moving_average_12",
            definition_version="1.0.0",
            output_name="exponential_moving_average_12",
            candle_timestamp=ts,
            available_at=avail,
            value=Decimal("101.000000000000000000"),
            feature_record=IntegrityReference(
                artifact_id="feature.ema12",
                artifact_type="runtime_feature_value",
                artifact_version="1.0.0",
                integrity_digest="a"*64,
                available_at=avail,
            ),
        )
    )
    f_values.append(
        FeatureSnapshotValue(
            feature_identifier="exponential_moving_average_26",
            definition_version="1.0.0",
            output_name="exponential_moving_average_26",
            candle_timestamp=ts,
            available_at=avail,
            value=Decimal("100.000000000000000000"),
            feature_record=IntegrityReference(
                artifact_id="feature.ema26",
                artifact_type="runtime_feature_value",
                artifact_version="1.0.0",
                integrity_digest="a"*64,
                available_at=avail,
            ),
        )
    )
    f_values.append(
        FeatureSnapshotValue(
            feature_identifier="relative_strength_index",
            definition_version="1.0.0",
            output_name="relative_strength_index",
            candle_timestamp=ts,
            available_at=avail,
            value=Decimal("55.000000000000000000"),
            feature_record=IntegrityReference(
                artifact_id="feature.rsi",
                artifact_type="runtime_feature_value",
                artifact_version="1.0.0",
                integrity_digest="a"*64,
                available_at=avail,
            ),
        )
    )
    # Add average true range (ATR) required by evidence assembly
    f_values.append(
        FeatureSnapshotValue(
            feature_identifier="average_true_range",
            definition_version="1.0.0",
            output_name="average_true_range",
            candle_timestamp=ts,
            available_at=avail,
            value=Decimal("1.000000000000000000"),
            feature_record=IntegrityReference(
                artifact_id="feature.atr",
                artifact_type="runtime_feature_value",
                artifact_version="1.0.0",
                integrity_digest="a"*64,
                available_at=avail,
            ),
        )
    )

    # Build feature snapshot and ensure its audit cutoff matches the feature availability
    from dataclasses import replace as _replace
    # Prepare a new audit for the feature snapshot so values are not future-unavailable
    new_audit = _replace(
        base_feature.audit,
        created_at=avail,
        evidence_cutoff=avail,
        available_at=avail,
    )
    # Ensure canonical ordering of feature values
    f_values = sorted(
        f_values,
        key=lambda v: (
            v.feature_identifier,
            v.definition_version,
            v.output_name,
            v.candle_timestamp,
        ),
    )

    feature = _replace(
        base_feature,
        scope=market.scope,
        market_snapshot=IntegrityReference(
            artifact_id=market.snapshot_id,
            artifact_type="market_snapshot",
            artifact_version="1.0.0",
            integrity_digest=market.canonical_sha256(),
            available_at=market.audit.available_at,
        ),
        values=tuple(f_values),
        audit=new_audit,
    )

    await features.save(feature)

    # Build market context using runtime context service
    context_service = RuntimeMarketContextService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        code_version="test.context",
    )
    context = await context_service.build(market, feature)
    await contexts.save(context)

    # Build runtime services wired to memory repos
    feature_engine = RuntimeFeatureEngine(market_snapshots=markets, feature_snapshots=features, code_version="test.features")
    detection_service = RuntimeOpportunityDetectionService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        detections=detections,
        code_version="test.detection",
    )
    evidence_service = RuntimeEvidenceService(
        candidates=detections,
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        evidence=evidence_repo,
        code_version="test.evidence",
    )
    plan_service = RuntimeOpportunityPlanService(code_version="test.plan")
    assessment_service = RuntimeAssessmentService(
        candidates=detections,
        evidence=evidence_repo,
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        opportunities=opportunities,
        plans=plan_service,
        code_version="test.assessment",
    )
    qualification_service = RuntimeQualificationService(
        opportunities=opportunities,
        evidence=evidence_repo,
        market_contexts=contexts,
        feature_snapshots=features,
        market_snapshots=markets,
        qualifications=qualifications,
        code_version="test.qualification",
    )
    scoring_service = RuntimeScoringService(
        opportunities=opportunities,
        qualifications=qualifications,
        evidence=evidence_repo,
        market_contexts=contexts,
        scores=scores,
        code_version="test.scoring",
    )
    ranking_service = RuntimeRankingService(
        scores=scores,
        qualifications=qualifications,
        opportunities=opportunities,
        rankings=rankings,
        code_version="test.ranking",
    )
    notification_service = RuntimeNotificationService(
        rankings=rankings,
        opportunities=opportunities,
        notifications=notifications,
        code_version="test.notification",
    )
    dashboard_service = RuntimeDashboardProjectionService(
        rankings=rankings, dashboard=dashboard_repo, code_version="test.dashboard"
    )
    detail_service = RuntimeOpportunityDetailProjectionService(
        opportunities=opportunities,
        market_snapshots=markets,
        market_contexts=contexts,
        evidence=evidence_repo,
        explanations=explanations,
        details=detail_repo,
        code_version="test.detail",
    )

    # Small async adapter classes wired to the in-memory repos
    from app.opportunity_intelligence.repositories import EntityId

    class Scanner:
        async def scan(self, query):
            return await markets.get_latest(query)

    from app.opportunity_intelligence.repositories import ScopedRepositoryQuery

    class FeatureResolver:
        async def resolve(self, market_snapshot):
            query = ScopedRepositoryQuery(scope=market_snapshot.scope, as_of=market_snapshot.audit.evidence_cutoff, limit=1)
            return await features.get_latest(query)

    class ContextBuilder:
        async def build(self, market_snapshot, feature_snapshot):
            return context

    from app.runtime_pipeline import _StubLifecycleService, _StubExplanationService

    class ExplanationSaver:
        def __init__(self, inner, repo):
            self._inner = inner
            self._repo = repo

        async def explain(self, *args, **kwargs):
            explanation = await self._inner.explain(*args, **kwargs)
            await self._repo.save(explanation)
            return explanation

    pipeline = OpportunityIntelligencePipeline(
        market_scanner=Scanner(),
        feature_snapshots=FeatureResolver(),
        market_contexts=ContextBuilder(),
        detection=detection_service,
        evidence=evidence_service,
        assessment=assessment_service,
        qualification=qualification_service,
        scoring=scoring_service,
        ranking=ranking_service,
        lifecycle=_StubLifecycleService(),
        notifications=notification_service,
        dashboard=dashboard_service,
        indicators=type("Indicators", (), {"project": (lambda self, f: asyncio.sleep(0, result=()))})(),
        explanation=ExplanationSaver(_StubExplanationService(), explanations),
        detail=detail_service,
    )

    # Build request
    query = ScopedRepositoryQuery(scope=market.scope, as_of=market.audit.available_at, limit=1)
    from app.opportunity_intelligence.orchestration.models import PipelineRunRequest
    request = PipelineRunRequest(run_id="run.test.1", query=query)

    # Run pipeline
    print("Running pipeline...")
    result = await pipeline.run(request)

    print("Outcome:", result.outcome)
    print("Stages:")
    for stage in result.stages:
        print(f" - {stage.sequence}. {stage.stage.name}: {stage.status.name} artifacts={stage.artifact_ids} reason={stage.reason_code}")

    # Also dump high-level outputs for debugging
    print("candidate:", bool(result.candidate), "evidence:", bool(result.evidence), "opportunity:", bool(result.opportunity), "ranking:", bool(result.ranking), "dashboard:", bool(result.dashboard), "explanation:", bool(result.explanation), "detail:", bool(result.detail))

    # Inspect dashboard and detail repositories
    try:
        page = await dashboard_repo.get_by_ranking_snapshot(EntityId(result.ranking.snapshot_id))
        print("Dashboard page stored, items:", len(page.items))
    except Exception as e:
        print("Dashboard retrieval failed:", e)

    try:
        detail = await detail_repo.get_by_opportunity_version(EntityId(result.opportunity.opportunity_version_id))
        print("Detail stored id:", detail.detail_id)
    except Exception as e:
        print("Detail retrieval failed:", e)


if __name__ == "__main__":
    asyncio.run(main())
