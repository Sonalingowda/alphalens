"""Comprehensive trace of the pipeline execution from market snapshot through /opportunities."""

import asyncio
from datetime import datetime, timezone
import logging
import os
import sys

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("pipeline_trace")

from app.live_market_data.service import LiveMarketIngestionService
from app.live_market_data.binance import BinanceKlineParser, BinanceWebSocketClient
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope

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
from app.opportunity_intelligence.orchestration.pipeline import OpportunityIntelligencePipeline
from app.opportunity_intelligence.orchestration.pipeline import PipelineRunRequest
from app.opportunity_intelligence.repositories import EntityId

_CODE_VERSION = "alphalens.runtime.1.0.0"

async def main():
    logger.info("=" * 80)
    logger.info("PIPELINE TRACE: Starting comprehensive execution trace")
    logger.info("=" * 80)

    # Create in-memory repos
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

    logger.info("REPOS: All in-memory repositories created")

    # Build runtime services
    feature_engine = RuntimeFeatureEngine(market_snapshots=markets, feature_snapshots=features, code_version=_CODE_VERSION)
    context_service = RuntimeMarketContextService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, code_version=_CODE_VERSION)
    detection_service = RuntimeOpportunityDetectionService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, detections=detections, code_version=_CODE_VERSION)
    evidence_service = RuntimeEvidenceService(candidates=detections, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, evidence=evidence_repo, code_version=_CODE_VERSION)
    assessment_service = RuntimeAssessmentService(candidates=detections, evidence=evidence_repo, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, opportunities=opportunities, code_version=_CODE_VERSION)
    qualification_service = RuntimeQualificationService(opportunities=opportunities, evidence=evidence_repo, market_contexts=contexts, feature_snapshots=features, market_snapshots=markets, qualifications=qualifications, code_version=_CODE_VERSION)
    scoring_service = RuntimeScoringService(opportunities=opportunities, qualifications=qualifications, evidence=evidence_repo, market_contexts=contexts, scores=scores, code_version=_CODE_VERSION)
    ranking_service = RuntimeRankingService(scores=scores, qualifications=qualifications, opportunities=opportunities, rankings=rankings, code_version=_CODE_VERSION)
    notification_service = RuntimeNotificationService(rankings=rankings, opportunities=opportunities, notifications=notifications, code_version=_CODE_VERSION)
    dashboard_service = RuntimeDashboardProjectionService(rankings=rankings, dashboard=dashboard_repo, code_version=_CODE_VERSION)
    detail_service = RuntimeOpportunityDetailProjectionService(opportunities=opportunities, market_snapshots=markets, market_contexts=contexts, evidence=evidence_repo, explanations=explanations, details=detail_repo, code_version=_CODE_VERSION)

    logger.info("SERVICES: All runtime services created")

    pipeline = OpportunityIntelligencePipeline(
        market_scanner=type("Scanner", (), {"scan": (lambda self, q: markets.get_latest(q))})(),
        feature_snapshots=feature_engine,
        market_contexts=context_service,
        detection=detection_service,
        evidence=evidence_service,
        assessment=assessment_service,
        qualification=qualification_service,
        scoring=scoring_service,
        ranking=ranking_service,
        lifecycle=type("LS", (), {"advance": (lambda *a, **k: asyncio.sleep(0, result=None))})(),
        notifications=notification_service,
        dashboard=dashboard_service,
        indicators=type("Indicators", (), {"project": (lambda self, f: asyncio.sleep(0, result=()))})(),
        explanation=type("Expl", (), {"explain": (lambda self, *a, **k: asyncio.sleep(0, result=None))})(),
        detail=detail_service,
    )

    logger.info("PIPELINE: OpportunityIntelligencePipeline constructed")

    # Prefetch historical 5m candles from Binance REST to warm up feature engine
    import httpx
    from decimal import Decimal
    from hashlib import sha256
    from json import dumps
    from app.live_market_data.models import CompletedCandle
    from app.live_market_data.snapshots import build_market_snapshot

    async def prefill_history(limit: int = 600):
        logger.info("PREFILL: Starting prefill of historical 5m candles from Binance REST")
        now = datetime.now(timezone.utc)
        floor_minutes = (now.minute // 5) * 5
        end = now.replace(minute=floor_minutes, second=0, microsecond=0)
        end_ms = int(end.timestamp() * 1000)
        params = {"symbol": "BTCUSDT", "interval": "5m", "limit": min(limit, 1000), "endTime": end_ms}
        url = "https://api.binance.com/api/v3/klines"
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(url, params=params, timeout=30)
            resp.raise_for_status()
            klines = resp.json()
        logger.info(f"PREFILL: Fetched {len(klines)} klines from Binance")
        for i, k in enumerate(klines):
            open_ms = int(k[0])
            open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
            close_ms = int(k[6])
            close_time = datetime.fromtimestamp(close_ms / 1000, tz=timezone.utc)
            event_ms = close_ms + 1000
            event_time = datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc)
            payload = dumps(k, separators=(",", ":"), sort_keys=True)
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
                snapshot = build_market_snapshot(candle, code_version="live.prefill")
                await markets.save(snapshot)
            except Exception as e:
                pass
        logger.info(f"PREFILL: Completed, saved {len(klines)} market snapshots")

    await prefill_history(limit=600)

    runtime_scope = MarketScope(instrument="BTCUSDT", timeframe="5m")

    class RuntimeWrapper:
        def __init__(self, pipeline, scope):
            self._pipeline = pipeline
            self._scope = scope

        async def run_for_snapshot(self, snapshot, as_of):
            if snapshot.scope != self._scope:
                return None
            request = PipelineRunRequest(run_id=f"live.run.{snapshot.snapshot_id}", query=ScopedRepositoryQuery(scope=self._scope, as_of=as_of, limit=1))
            return await self._pipeline.run(request)

    runtime_pipeline = RuntimeWrapper(pipeline, runtime_scope)

    # Create a specialized ingestion service subclass that triggers the pipeline
    class _PipelineAwareLiveMarketIngestionService(LiveMarketIngestionService):
        async def _persist(self, candle):
            snapshot = await super()._persist(candle)
            if snapshot is not None and snapshot.scope.timeframe == "5m":
                logger.info(f"PERSIST: 5m snapshot persisted, triggering pipeline")
                try:
                    result = await runtime_pipeline.run_for_snapshot(snapshot, snapshot.audit.available_at)

                    # Comprehensive trace output
                    if result:
                        logger.info("=" * 80)
                        logger.info(f"PIPELINE_RESULT: run_id={result.run_id}")
                        logger.info(f"OUTCOME: {result.outcome}")
                        logger.info(f"STAGES:")
                        for stage in result.stages:
                            logger.info(f"  {stage.sequence}. {stage.stage.name}: {stage.status.name} reason={stage.reason_code}")

                        # Check what was persisted in each repo
                        logger.info("REPO_INSPECTION:")

                        # Opportunities
                        try:
                            query_opp = ScopedRepositoryQuery(scope=runtime_scope, as_of=snapshot.audit.available_at, limit=10)
                            opp_page = await opportunities.get_by_scope(query_opp)
                            logger.info(f"  Opportunities: {len(opp_page.items)} items")
                            for opp in opp_page.items:
                                logger.info(f"    - {opp.opportunity_id} version={opp.opportunity_version_id}")
                        except Exception as e:
                            logger.info(f"  Opportunities: error - {e}")

                        # Evidence
                        try:
                            if result.candidate:
                                evidence_pkg = await evidence_repo.get_by_candidate_id(EntityId(result.candidate.candidate_id))
                                logger.info(f"  Evidence: found for candidate {result.candidate.candidate_id}")
                            else:
                                logger.info(f"  Evidence: no candidate")
                        except Exception as e:
                            logger.info(f"  Evidence: error - {e}")

                        # Dashboard
                        try:
                            dash_page = await dashboard_repo.get_by_scope(ScopedRepositoryQuery(scope=runtime_scope, as_of=snapshot.audit.available_at, limit=10))
                            logger.info(f"  Dashboard: {len(dash_page.items)} items")
                        except Exception as e:
                            logger.info(f"  Dashboard: error - {e}")

                        logger.info("=" * 80)

                except Exception as e:
                    logger.exception(f"PIPELINE_ERROR: {e}")
            return snapshot

    # Binance ingestion
    client = BinanceWebSocketClient()
    parser = BinanceKlineParser()
    live_ingestion = _PipelineAwareLiveMarketIngestionService(repository=markets, code_version="live.run.1.0.0", client=client, parser=parser)

    # Monitor for opportunities
    stop_event = asyncio.Event()

    async def monitor():
        deadline = datetime.now(timezone.utc).timestamp() + 300  # 5 minutes
        while datetime.now(timezone.utc).timestamp() < deadline:
            try:
                query = ScopedRepositoryQuery(scope=runtime_scope, as_of=datetime.now(timezone.utc), limit=1)
                opp_page = await opportunities.get_by_scope(query)
                if opp_page.items:
                    logger.info("SUCCESS: Found opportunity in repository!")
                    for opp in opp_page.items:
                        logger.info(f"  Opportunity: {opp.opportunity_id}")
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
        logger.info("MONITOR: Timeout - no opportunities found")
        return False

    ingestion_task = asyncio.create_task(live_ingestion.run(stop_event), name="live-ingest")
    try:
        await monitor()
    finally:
        stop_event.set()
        ingestion_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ingestion_task

if __name__ == "__main__":
    import contextlib
    asyncio.run(main())
