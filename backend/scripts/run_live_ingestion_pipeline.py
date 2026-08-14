"""Run live Binance ingestion into in-memory repos and trigger the in-memory pipeline.

This script:
- constructs in-memory repositories
- constructs the runtime pipeline wired to those repos (same services used in run_memory_pipeline)
- runs LiveMarketIngestionService pointed at the in-memory MarketSnapshotMemoryRepository
- when a new 5m snapshot is persisted, triggers pipeline.run_for_snapshot in a background task
- monitors the DashboardProjectionMemoryRepository and OpportunityDetailMemoryRepository and prints when a Dashboard item and Detail appear

Run with: PYTHONPATH=backend /opt/homebrew/bin/python3.11 backend/scripts/run_live_ingestion_pipeline.py

Note: connects to Binance public websocket (wss://data-stream.binance.vision), no API keys required.
"""

import asyncio
import contextlib
from datetime import timezone, datetime
from decimal import Decimal
from hashlib import sha256
import logging
import os
from json import dumps
from typing import Sequence

from app.live_market_data.service import LiveMarketIngestionService
from app.live_market_data.binance import BinanceKlineParser, BinanceWebSocketClient
from app.live_market_data.models import CompletedCandle
from app.live_market_data.snapshots import build_market_snapshot
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import (
    MarketSnapshotPostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import DuplicateEntityError
from app.persistence.database import session_factory

from app.opportunity_intelligence.persistence.memory import (
    MarketSnapshotMemoryRepository,
    FeatureSnapshotMemoryRepository,
    MarketContextMemoryRepository,
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    OpportunityMemoryRepository,
    OpportunityPlanMemoryRepository,
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
from app.runtime_pipeline import _StubExplanationService, _StubLifecycleService
from app.opportunity_intelligence.orchestration.pipeline import OpportunityIntelligencePipeline
from app.opportunity_intelligence.orchestration.pipeline import PipelineRunRequest
from app.opportunity_intelligence.repositories import EntityId

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("run_live_ingestion_pipeline")

# reuse the same code version string used elsewhere
_CODE_VERSION = "alphalens.runtime.1.0.0"
_PREFILL_CODE_VERSION = "alphalens.live.prefill.1.0.0"


def _use_postgresql_backfill() -> bool:
    return os.getenv("ALPHALENS_BINANCE_BACKFILL_POSTGRESQL") == "1"


def _market_repository(backfill_only: bool):
    if backfill_only:
        return MarketSnapshotPostgreSQLRepository(session_factory)
    return MarketSnapshotMemoryRepository()


def _completed_candle_from_kline(kline: Sequence[object]) -> CompletedCandle:
    open_ms = int(kline[0])
    open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
    close_ms = int(kline[6])
    close_time = datetime.fromtimestamp(close_ms / 1000, tz=timezone.utc)
    event_time = datetime.fromtimestamp((close_ms + 1000) / 1000, tz=timezone.utc)
    payload = dumps(kline, separators=(",", ":"), sort_keys=True)
    source_hash = sha256(payload.encode("utf-8")).hexdigest()
    return CompletedCandle(
        provider="binance_spot",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=event_time,
        open_time=open_time,
        close_time=close_time,
        open=Decimal(kline[1]),
        high=Decimal(kline[2]),
        low=Decimal(kline[3]),
        close=Decimal(kline[4]),
        volume=Decimal(kline[5]),
        number_of_trades=int(kline[8]),
        source_payload_hash=source_hash,
        source_candle_hashes=(),
    )


async def _persist_binance_klines(
    repository,
    klines: Sequence[Sequence[object]],
    *,
    code_version: str,
) -> tuple[int, int]:
    persisted_count = 0
    duplicate_count = 0
    for kline in klines:
        candle = _completed_candle_from_kline(kline)
        snapshot = build_market_snapshot(candle, code_version=code_version)
        try:
            await repository.save(snapshot)
        except DuplicateEntityError:
            duplicate_count += 1
            logger.debug("prefill skip duplicate identity=%s", snapshot.snapshot_id)
        else:
            persisted_count += 1
    return persisted_count, duplicate_count


async def main():
    backfill_only = _use_postgresql_backfill()
    # create in-memory repos
    markets = _market_repository(backfill_only)
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    detections = DetectionMemoryRepository()
    evidence_repo = EvidenceMemoryRepository()
    opportunities = OpportunityMemoryRepository()
    plans = OpportunityPlanMemoryRepository()
    qualifications = QualificationMemoryRepository()
    scores = ScoringMemoryRepository()
    rankings = RankingMemoryRepository()
    dashboard_repo = DashboardProjectionMemoryRepository()
    detail_repo = OpportunityDetailMemoryRepository()
    explanations = ExplanationMemoryRepository()
    notifications = NotificationMemoryRepository()

    class _PersistingExplanationService:
        def __init__(self, repository, delegate):
            self._repository = repository
            self._delegate = delegate

        async def explain(self, opportunity, evidence, market_context, lifecycle):
            explanation = await self._delegate.explain(
                opportunity,
                evidence,
                market_context,
                lifecycle,
            )
            await self._repository.save(explanation)
            return explanation

    # build runtime services
    feature_engine = RuntimeFeatureEngine(market_snapshots=markets, feature_snapshots=features, code_version=_CODE_VERSION)
    context_service = RuntimeMarketContextService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, code_version=_CODE_VERSION)
    detection_service = RuntimeOpportunityDetectionService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, detections=detections, code_version=_CODE_VERSION)
    evidence_service = RuntimeEvidenceService(candidates=detections, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, evidence=evidence_repo, code_version=_CODE_VERSION)
    plan_service = RuntimeOpportunityPlanService(code_version=_CODE_VERSION)
    assessment_service = RuntimeAssessmentService(candidates=detections, evidence=evidence_repo, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, opportunities=opportunities, plans_repository=plans, plans=plan_service, code_version=_CODE_VERSION)
    qualification_service = RuntimeQualificationService(opportunities=opportunities, evidence=evidence_repo, market_contexts=contexts, feature_snapshots=features, market_snapshots=markets, qualifications=qualifications, code_version=_CODE_VERSION)
    scoring_service = RuntimeScoringService(opportunities=opportunities, qualifications=qualifications, evidence=evidence_repo, market_contexts=contexts, scores=scores, code_version=_CODE_VERSION)
    ranking_service = RuntimeRankingService(scores=scores, qualifications=qualifications, opportunities=opportunities, rankings=rankings, code_version=_CODE_VERSION)
    notification_service = RuntimeNotificationService(rankings=rankings, opportunities=opportunities, notifications=notifications, code_version=_CODE_VERSION)
    dashboard_service = RuntimeDashboardProjectionService(rankings=rankings, dashboard=dashboard_repo, code_version=_CODE_VERSION)
    detail_service = RuntimeOpportunityDetailProjectionService(opportunities=opportunities, market_snapshots=markets, market_contexts=contexts, evidence=evidence_repo, explanations=explanations, details=detail_repo, code_version=_CODE_VERSION)

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
        lifecycle=_StubLifecycleService(),
        notifications=notification_service,
        dashboard=dashboard_service,
        indicators=type("Indicators", (), {"project": (lambda self, f: asyncio.sleep(0, result=()))})(),
        explanation=_PersistingExplanationService(explanations, _StubExplanationService(explanations)),
        detail=detail_service,
    )

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
                # Run the runtime pipeline synchronously for visibility during debugging.
                try:
                    print(f"INVOCATION: invoking runtime pipeline for snapshot {snapshot.snapshot_id} as_of={snapshot.audit.available_at}")
                    result = await runtime_pipeline.run_for_snapshot(snapshot, snapshot.audit.available_at)
                    print("INVOCATION: pipeline returned:", result)
                    logger.info("pipeline_run_result run_id=%s outcome=%s", getattr(result, 'run_id', None), getattr(result, 'outcome', None))
                    # also log stage outcomes if present
                    try:
                        for s in getattr(result, 'stages', ()):
                            print(f"STAGE: {s.sequence} {s.stage.name} status={s.status.name} reason={s.reason_code} artifacts={s.artifact_ids}")
                            logger.debug("stage %s: %s status=%s reason=%s artifacts=%s", s.sequence, s.stage.name, s.status.name, s.reason_code, s.artifact_ids)
                    except Exception:
                        pass
                except Exception as e:
                    print("INVOCATION: runtime pipeline raised:", repr(e))
                    logger.exception("runtime pipeline failed: %s", e)
            return snapshot

    # Prefetch historical 5m candles from Binance REST to warm up feature engine
    import httpx

    async def prefill_history(limit: int = 1000):
        # fetch most recent `limit` 5m klines ending at the last closed timeframe
        # use public Binance API
        now = datetime.now(timezone.utc)
        # floor to 5m boundary
        floor_minutes = (now.minute // 5) * 5
        end = now.replace(minute=floor_minutes, second=0, microsecond=0)
        # Binance expects milliseconds
        end_ms = int(end.timestamp() * 1000)
        params = {"symbol": "BTCUSDT", "interval": "5m", "limit": min(limit,1000), "endTime": end_ms}
        url = "https://api.binance.com/api/v3/klines"
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(url, params=params, timeout=30)
            resp.raise_for_status()
            klines = resp.json()
        # klines are oldest->newest
        persisted, skipped = await _persist_binance_klines(
            markets,
            klines,
            code_version=_PREFILL_CODE_VERSION,
        )
        logger.info(
            "prefill_complete total=%s persisted=%s skipped=%s target=%s",
            len(klines),
            persisted,
            skipped,
            "postgresql" if backfill_only else "memory",
        )

    await prefill_history(limit=1000)

    if backfill_only:
        return

    # create client and parser
    client = BinanceWebSocketClient()
    parser = BinanceKlineParser()
    live_ingestion = _PipelineAwareLiveMarketIngestionService(repository=markets, code_version="live.run.1.0.0", client=client, parser=parser)

    # run ingestion and monitor dashboards
    stop_event = asyncio.Event()

    async def monitor():
        # wait until first dashboard item and detail for 5m appears
        deadline = datetime.now(timezone.utc).timestamp() + 600  # 10 minutes
        while datetime.now(timezone.utc).timestamp() < deadline:
            try:
                # Check latest 5m ranking snapshot -> dashboard
                query = ScopedRepositoryQuery(scope=runtime_scope, as_of=datetime.now(timezone.utc), limit=1)
                page = await dashboard_repo.get_latest(query)
                if page and page.items:
                    print("LIVE DASHBOARD: items=", len(page.items))
                    for it in page.items:
                        print("dashboard.item -> opportunity_version_id=", it.opportunity_version_id)
                    # also print detail for first item
                    first = page.items[0]
                    try:
                        detail = await detail_repo.get_by_opportunity_version(EntityId(first.opportunity_version_id))
                        print("LIVE DETAIL: detail_id=", detail.detail_id)
                    except Exception as e:
                        print("detail not found yet", e)
                    return
            except Exception:
                pass
            await asyncio.sleep(2)
        print("monitor: timeout waiting for live dashboard item")

    ingestion_task = asyncio.create_task(live_ingestion.run(stop_event), name="live-ingest")
    try:
        # Run monitor until success or timeout
        await monitor()
    finally:
        stop_event.set()
        ingestion_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await ingestion_task

if __name__ == "__main__":
    asyncio.run(main())
