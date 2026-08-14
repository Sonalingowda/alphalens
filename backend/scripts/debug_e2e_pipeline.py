"""Complete end-to-end pipeline trace from detected candidate through dashboard."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

logging.basicConfig(
    level=logging.INFO,
    format='[%(name)s] %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("e2e_trace")

from app.live_market_data.models import CompletedCandle
from app.live_market_data.snapshots import build_market_snapshot
from app.market_data.models import CandleTimeframe

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
from app.runtime_qualification.service import RuntimeQualificationService
from app.runtime_scoring.service import RuntimeScoringService
from app.runtime_ranking.service import RuntimeRankingService
from app.runtime_notification.service import RuntimeNotificationService
from app.runtime_dashboard.service import RuntimeDashboardProjectionService
from app.runtime_detail.service import RuntimeOpportunityDetailProjectionService
from app.opportunity_intelligence.orchestration.pipeline import OpportunityIntelligencePipeline, PipelineRunRequest
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery

import httpx


async def main():
    logger.info("=" * 80)
    logger.info("END-TO-END PIPELINE TRACE")
    logger.info("=" * 80)

    # Create repos
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

    # Services
    feature_engine = RuntimeFeatureEngine(market_snapshots=markets, feature_snapshots=features, code_version="e2e.1.0.0")
    context_service = RuntimeMarketContextService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, code_version="e2e.1.0.0")
    detection_service = RuntimeOpportunityDetectionService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, detections=detections, code_version="e2e.1.0.0")
    evidence_service = RuntimeEvidenceService(candidates=detections, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, evidence=evidence_repo, code_version="e2e.1.0.0")
    assessment_service = RuntimeAssessmentService(candidates=detections, evidence=evidence_repo, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, opportunities=opportunities, code_version="e2e.1.0.0")
    qualification_service = RuntimeQualificationService(opportunities=opportunities, evidence=evidence_repo, market_contexts=contexts, feature_snapshots=features, market_snapshots=markets, qualifications=qualifications, code_version="e2e.1.0.0")
    scoring_service = RuntimeScoringService(opportunities=opportunities, qualifications=qualifications, evidence=evidence_repo, market_contexts=contexts, scores=scores, code_version="e2e.1.0.0")
    ranking_service = RuntimeRankingService(scores=scores, qualifications=qualifications, opportunities=opportunities, rankings=rankings, code_version="e2e.1.0.0")
    notification_service = RuntimeNotificationService(rankings=rankings, opportunities=opportunities, notifications=notifications, code_version="e2e.1.0.0")
    dashboard_service = RuntimeDashboardProjectionService(rankings=rankings, dashboard=dashboard_repo, code_version="e2e.1.0.0")
    detail_service = RuntimeOpportunityDetailProjectionService(opportunities=opportunities, market_snapshots=markets, market_contexts=contexts, evidence=evidence_repo, explanations=explanations, details=detail_repo, code_version="e2e.1.0.0")

    # Stub services for lifecycle, indicators, explanation
    class StubLifecycle:
        async def advance(self, *args, **kwargs):
            from app.opportunity_intelligence.domain import OpportunityLifecycle, LifecycleEvent, LifecycleEventType, AuditMetadata, Provenance, PolicyReference
            return OpportunityLifecycle(
                opportunity_id="test",
                current_state="ACTIVE",
                current_event_id="lifecycle.event.test.1",
                events=(LifecycleEvent(event_id="lifecycle.event.test.1", event_type=LifecycleEventType.INITIATED, occurred_at=datetime.now(timezone.utc), audit=AuditMetadata(created_at=datetime.now(timezone.utc), evidence_cutoff=datetime.now(timezone.utc), available_at=datetime.now(timezone.utc), provenance=Provenance(source_references=(), policy_references=(PolicyReference("test", "1.0.0", "0"*64),), code_version="test", configuration_hash="0"*64, lineage_hash="0"*64), result_hash="0"*64)),),
                audit=AuditMetadata(created_at=datetime.now(timezone.utc), evidence_cutoff=datetime.now(timezone.utc), available_at=datetime.now(timezone.utc), provenance=Provenance(source_references=(), policy_references=(PolicyReference("test", "1.0.0", "0"*64),), code_version="test", configuration_hash="0"*64, lineage_hash="0"*64), result_hash="0"*64),
            )

    class StubIndicators:
        async def project(self, features):
            return ()

    class StubExplanation:
        async def explain(self, *args, **kwargs):
            from app.opportunity_intelligence.domain import Explanation, AuditMetadata, Provenance, PolicyReference
            return Explanation(
                explanation_id="explanation.test.1",
                opportunity_id="test",
                summary="",
                reasoning=(),
                confidence_pct=Decimal("0"),
                limitations=(),
                audit=AuditMetadata(created_at=datetime.now(timezone.utc), evidence_cutoff=datetime.now(timezone.utc), available_at=datetime.now(timezone.utc), provenance=Provenance(source_references=(), policy_references=(PolicyReference("test", "1.0.0", "0"*64),), code_version="test", configuration_hash="0"*64, lineage_hash="0"*64), result_hash="0"*64),
            )

    class StubScanner:
        async def scan(self, query):
            market = await markets.get_latest(query)
            if not market:
                raise Exception("No market snapshot")
            return market

    pipeline = OpportunityIntelligencePipeline(
        market_scanner=StubScanner(),
        feature_snapshots=feature_engine,
        market_contexts=context_service,
        detection=detection_service,
        evidence=evidence_service,
        assessment=assessment_service,
        qualification=qualification_service,
        scoring=scoring_service,
        ranking=ranking_service,
        lifecycle=StubLifecycle(),
        notifications=notification_service,
        dashboard=dashboard_service,
        indicators=StubIndicators(),
        explanation=StubExplanation(),
        detail=detail_service,
    )

    # Prefill 600 5m candles
    logger.info("PREFILL: Fetching 600 5m candles from Binance...")
    now = datetime.now(timezone.utc)
    floor_minutes = (now.minute // 5) * 5
    end = now.replace(minute=floor_minutes, second=0, microsecond=0)
    end_ms = int(end.timestamp() * 1000)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": "5m", "limit": 600, "endTime": end_ms},
            timeout=30,
        )
        resp.raise_for_status()
        klines = resp.json()

    logger.info(f"PREFILL: Fetched {len(klines)} klines")

    for k in klines:
        open_ms = int(k[0])
        open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
        close_ms = int(k[6])
        close_time = datetime.fromtimestamp(close_ms / 1000, tz=timezone.utc)
        event_ms = close_ms + 1000
        event_time = datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc)
        payload = json.dumps(k, separators=(",", ":"), sort_keys=True)
        source_hash = sha256(payload.encode("utf-8")).hexdigest()

        candle = CompletedCandle(
            provider="binance_spot",
            symbol="BTCUSDT",
            timeframe=CandleTimeframe.MINUTE_5,
            event_time=event_time,
            open_time=open_time,
            close_time=close_time,
            open=Decimal(k[1]),
            high=Decimal(k[2]),
            low=Decimal(k[3]),
            close=Decimal(k[4]),
            volume=Decimal(k[5]),
            number_of_trades=int(k[8]),
            source_payload_hash=source_hash,
            source_candle_hashes=(),
        )

        try:
            snapshot = build_market_snapshot(candle, code_version="e2e.prefill")
            await markets.save(snapshot)
        except Exception:
            pass

    logger.info(f"PREFILL: Completed, saved to MarketSnapshotMemoryRepository")

    # Run pipeline
    logger.info("PIPELINE: Running full end-to-end pipeline...")
    query = ScopedRepositoryQuery(scope=MarketScope(instrument="BTCUSDT", timeframe="5m"), as_of=datetime.now(timezone.utc), limit=1)
    request = PipelineRunRequest(run_id="e2e.test.1", query=query)

    try:
        result = await pipeline.run(request)
        logger.info(f"PIPELINE_RESULT: outcome={result.outcome.name}")
        for stage in result.stages:
            logger.info(f"  STAGE: {stage.stage.name} = {stage.status.name} ({stage.reason_code})")

        # Check repos
        logger.info("FINAL_STATE:")
        try:
            opps = await opportunities.get_latest(query)
            logger.info(f"  Opportunities: {len(opps.items)} items")
            if opps.items:
                for opp in opps.items:
                    logger.info(f"    - {opp.opportunity_id} {opp.scope}")
        except Exception as e:
            logger.info(f"  Opportunities: error - {e}")

        try:
            dash = await dashboard_repo.get_latest(query)
            logger.info(f"  Dashboard: {len(dash.items)} items")
            if dash.items:
                for item in dash.items:
                    logger.info(f"    - {item.opportunity_id} rank={item.rank}")
        except Exception as e:
            logger.info(f"  Dashboard: error - {e}")

    except Exception as e:
        logger.exception(f"PIPELINE_ERROR: {e}")

    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
