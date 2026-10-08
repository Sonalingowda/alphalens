"""Deterministic E2E coverage of the production live-ingestion path.

The test uses the production ingestion service, scheduler, runtime feature
engine, frozen detection service, V1.1 assessment/plan service, lifecycle,
dashboard projection, and outcome resolver with isolated in-memory repositories.
It does not change any policy or production implementation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from app.live_market_data import build_market_snapshot
from app.live_market_data.models import CompletedCandle
from app.market_data.models import CandleTimeframe
from app.opportunity_intelligence.domain import MarketScope, OpportunityOutcome
from app.opportunity_intelligence.orchestration import (
    OpportunityIntelligencePipeline,
)
from app.opportunity_intelligence.persistence import (
    DashboardProjectionMemoryRepository,
    DetectionMemoryRepository,
    EvidenceMemoryRepository,
    ExplanationMemoryRepository,
    FeatureSnapshotMemoryRepository,
    LifecycleMemoryRepository,
    MarketContextMemoryRepository,
    MarketSnapshotMemoryRepository,
    NotificationMemoryRepository,
    OpportunityDetailMemoryRepository,
    OpportunityMemoryRepository,
    OpportunityPlanMemoryRepository,
    OutcomeMemoryRepository,
    QualificationMemoryRepository,
    RankingMemoryRepository,
    ScoringMemoryRepository,
)
from app.outcome_resolution.service import OutcomeResolutionService
from app.runtime_assessment import RuntimeAssessmentService
from app.runtime_context import RuntimeMarketContextService
from app.runtime_dashboard import RuntimeDashboardProjectionService
from app.runtime_detection import RuntimeOpportunityDetectionService
from app.runtime_detail import RuntimeOpportunityDetailProjectionService
from app.runtime_evidence import RuntimeEvidenceService
from app.runtime_features import RuntimeFeatureEngine
from app.runtime_indicators import RuntimeIndicatorService
from app.runtime_lifecycle import RuntimeLifecycleService
from app.runtime_notification import RuntimeNotificationService
from app.runtime_opportunity_plan import RuntimeOpportunityPlanService
from app.runtime_qualification import RuntimeQualificationService
from app.runtime_ranking import RuntimeRankingService
from app.runtime_scoring import RuntimeScoringService
from app.runtime_pipeline import (
    RuntimeIntelligencePipeline,
    _StubExplanationService,
)
from app.prediction_api import (
    _PipelineAwareLiveMarketIngestionService,
    _pipeline_tasks,
)


START = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
SCOPE = MarketScope(instrument="BTCUSDT", timeframe="5m")


def _message(
    start: datetime,
    *,
    open_price: str,
    high: str,
    low: str,
    close: str,
    volume: str = "100.00000000",
) -> str:
    import json

    close_time = start + timedelta(minutes=5) - timedelta(milliseconds=1)
    payload = {
        "stream": "btcusdt@kline_5m",
        "data": {
            "e": "kline",
            "E": int((close_time + timedelta(milliseconds=1)).timestamp() * 1000),
            "s": "BTCUSDT",
            "k": {
                "t": int(start.timestamp() * 1000),
                "T": int(close_time.timestamp() * 1000),
                "s": "BTCUSDT",
                "i": "5m",
                "o": open_price,
                "c": close,
                "h": high,
                "l": low,
                "v": volume,
                "n": 100,
                "x": True,
            },
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _snapshot(index: int, *, flat: bool) -> object:
    timestamp = START + timedelta(minutes=5 * index)
    if flat:
        open_price = high = low = close = Decimal("100")
    else:
        open_price = Decimal(10_000 + index)
        high = open_price + Decimal("5")
        low = open_price - Decimal("5")
        close = open_price + Decimal("1")
    candle = CompletedCandle(
        provider="binance_spot",
        symbol="BTCUSDT",
        timeframe=CandleTimeframe.MINUTE_5,
        event_time=timestamp + timedelta(minutes=5),
        open_time=timestamp,
        close_time=timestamp + timedelta(minutes=5) - timedelta(milliseconds=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=Decimal("100"),
        number_of_trades=100,
        source_payload_hash=f"{index:064x}",
    )
    return build_market_snapshot(candle, code_version="e2e-fixture")


class _CandleQuery:
    def __init__(self, candle: dict[str, Decimal | datetime]) -> None:
        self.candle = candle
        self.calls: list[dict[str, object]] = []

    async def query(self, *, instrument, timeframe, after, up_to_and_including):
        self.calls.append(
            {
                "instrument": instrument,
                "timeframe": timeframe,
                "after": after,
                "up_to_and_including": up_to_and_including,
            }
        )
        return (self.candle,)


def _runtime_bundle() -> tuple[object, dict[str, object]]:
    markets = MarketSnapshotMemoryRepository()
    features = FeatureSnapshotMemoryRepository()
    contexts = MarketContextMemoryRepository()
    detections = DetectionMemoryRepository()
    evidence = EvidenceMemoryRepository()
    opportunities = OpportunityMemoryRepository()
    plans = OpportunityPlanMemoryRepository()
    qualifications = QualificationMemoryRepository()
    scores = ScoringMemoryRepository()
    rankings = RankingMemoryRepository()
    lifecycles = LifecycleMemoryRepository()
    outcomes = OutcomeMemoryRepository()
    notifications = NotificationMemoryRepository()
    dashboard = DashboardProjectionMemoryRepository()
    details = OpportunityDetailMemoryRepository()
    explanations = ExplanationMemoryRepository()

    feature_engine = RuntimeFeatureEngine(
        market_snapshots=markets,
        feature_snapshots=features,
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    context_service = RuntimeMarketContextService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        code_version="alphalens.runtime.1.0.0",
    )
    detection_service = RuntimeOpportunityDetectionService(
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        detections=detections,
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    evidence_service = RuntimeEvidenceService(
        candidates=detections,
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        evidence=evidence,
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    assessment_service = RuntimeAssessmentService(
        candidates=detections,
        evidence=evidence,
        market_snapshots=markets,
        feature_snapshots=features,
        market_contexts=contexts,
        opportunities=opportunities,
        plans_repository=plans,
        plans=RuntimeOpportunityPlanService(code_version="alphalens.runtime.1.0.0"),
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    qualification_service = RuntimeQualificationService(
        opportunities=opportunities,
        evidence=evidence,
        market_contexts=contexts,
        feature_snapshots=features,
        market_snapshots=markets,
        qualifications=qualifications,
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    scoring_service = RuntimeScoringService(
        opportunities=opportunities,
        qualifications=qualifications,
        evidence=evidence,
        market_contexts=contexts,
        scores=scores,
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    ranking_service = RuntimeRankingService(
        scores=scores,
        qualifications=qualifications,
        opportunities=opportunities,
        rankings=rankings,
        code_version="alphalens.runtime.1.0.0",
        scope=SCOPE,
    )
    lifecycle_service = RuntimeLifecycleService(lifecycles=lifecycles)
    pipeline = OpportunityIntelligencePipeline(
        market_scanner=SimpleNamespace(scan=markets.get_latest),
        feature_snapshots=feature_engine,
        market_contexts=context_service,
        detection=detection_service,
        evidence=evidence_service,
        assessment=assessment_service,
        qualification=qualification_service,
        scoring=scoring_service,
        ranking=ranking_service,
        lifecycle=lifecycle_service,
        notifications=RuntimeNotificationService(
            rankings=rankings,
            opportunities=opportunities,
            lifecycles=lifecycles,
            notifications=notifications,
            code_version="alphalens.runtime.1.0.0",
        ),
        dashboard=RuntimeDashboardProjectionService(
            rankings=rankings,
            opportunities=opportunities,
            lifecycles=lifecycles,
            dashboard=dashboard,
            plans=plans,
            scores=scores,
            code_version="alphalens.runtime.1.0.0",
        ),
        indicators=RuntimeIndicatorService(),
        explanation=_StubExplanationService(explanations),
        detail=RuntimeOpportunityDetailProjectionService(
            opportunities=opportunities,
            market_snapshots=markets,
            market_contexts=contexts,
            evidence=evidence,
            explanations=explanations,
            details=details,
            scores=scores,
            code_version="alphalens.runtime.1.0.0",
        ),
    )

    class RuntimeWrapper(RuntimeIntelligencePipeline):
        def __init__(self) -> None:
            super().__init__(pipeline=pipeline, scope=SCOPE)
            self.results: list[object] = []

        async def run_for_snapshot(self, snapshot, as_of):
            result = await super().run_for_snapshot(snapshot, as_of)
            self.results.append(result)
            return result

    return RuntimeWrapper(), {
        "markets": markets,
        "features": features,
        "contexts": contexts,
        "detections": detections,
        "opportunities": opportunities,
        "plans": plans,
        "lifecycles": lifecycles,
        "outcomes": outcomes,
        "lifecycle_service": lifecycle_service,
        "dashboard": dashboard,
        "wrapper": RuntimeWrapper,
    }


class ProductionLifecycleE2ETests(IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        for task in tuple(_pipeline_tasks):
            if not task.done():
                task.cancel()
        await asyncio.sleep(0)

    async def _run_case(self, *, flat: bool):
        wrapper, repos = _runtime_bundle()
        markets = repos["markets"]
        history = tuple(_snapshot(i, flat=flat) for i in range(100))
        await markets.save_batch(history)
        live_start = START + timedelta(minutes=500)
        if flat:
            raw = _message(
                live_start,
                open_price="100",
                high="101",
                low="99",
                close="100",
            )
        else:
            raw = _message(
                live_start,
                open_price="10100",
                high="10105",
                low="10095",
                close="10101",
            )
        service = _PipelineAwareLiveMarketIngestionService(
            repository=markets,
            code_version="alphalens.runtime.1.0.0",
        )
        await service.initialize(live_start)
        import app.prediction_api as prediction_api

        original = prediction_api._runtime_pipeline
        prediction_api._runtime_pipeline = wrapper
        try:
            await service.process_message(raw)
            for _ in range(100):
                if wrapper.results:
                    break
                await asyncio.sleep(0.01)
            self.assertTrue(wrapper.results, "scheduled production task did not finish")
        finally:
            prediction_api._runtime_pipeline = original
        return wrapper.results[-1], repos, live_start

    async def test_case_a_realistic_sequence_produces_no_opportunity(self) -> None:
        result, repos, _ = await self._run_case(flat=True)
        self.assertEqual(result.outcome.value, "NO_CANDIDATE")
        self.assertEqual(len(repos["opportunities"]._records), 0)
        self.assertEqual(len(repos["plans"]._records), 0)
        self.assertEqual(len(repos["dashboard"]._records), 0)
        self.assertTrue(repos["detections"]._attempts._records)

    async def test_case_b_realistic_sequence_persists_plan_lifecycle_and_outcome(self) -> None:
        result, repos, _ = await self._run_case(flat=False)
        self.assertEqual(result.outcome.value, "COMPLETED")
        self.assertIsNotNone(result.opportunity)
        assert result.opportunity is not None
        plan = result.opportunity.plan
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertIsNotNone(plan.valid_until)
        self.assertIsNotNone(plan.entry_zone)
        self.assertIsNotNone(plan.targets)
        self.assertIsNotNone(plan.invalidation_price)
        self.assertEqual(len(repos["opportunities"]._records), 1)
        self.assertEqual(len(repos["plans"]._records), 1)
        self.assertEqual(len(repos["dashboard"]._records), 1)
        self.assertIsNotNone(result.lifecycle)
        assert result.lifecycle is not None
        self.assertEqual(result.lifecycle.current_state.value, "RANKED")

        target = plan.targets[0].price
        signal = plan.audit.available_at
        future_candle = {
            "timestamp": signal + timedelta(minutes=5),
            "open": plan.reference_price,
            "high": target + Decimal("1"),
            "low": plan.reference_price,
            "close": target,
            "volume": Decimal("100"),
        }
        query = _CandleQuery(future_candle)
        outcome = await OutcomeResolutionService(candle_query=query).resolve(
            opportunity_id=result.opportunity.opportunity_id,
            opportunity_version_id=result.opportunity.opportunity_version_id,
            direction=result.opportunity.stance.value,
            signal_timestamp=signal,
            evidence_cutoff=signal,
            plan=plan,
        )
        await repos["outcomes"].save(outcome)
        self.assertEqual(outcome.outcome, OpportunityOutcome.TARGET_HIT)
        resolved_lifecycle = await repos["lifecycle_service"].resolve_outcome(
            result.lifecycle,
            outcome.outcome,
            outcome.resolved_at,
        )
        self.assertEqual(resolved_lifecycle.current_state.value, "RESOLVED")
        self.assertEqual(query.calls[0]["after"], signal)
        self.assertEqual(query.calls[0]["up_to_and_including"], plan.valid_until)
