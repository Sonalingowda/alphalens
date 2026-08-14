"""Trace one persisted live BTCUSDT 5m snapshot through the production pipeline.

This is an operational diagnostic harness.  It makes no policy decisions and
uses the same concrete services and PostgreSQL repositories as runtime_pipeline.
"""

import asyncio
import inspect
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.persistence import (
    DashboardProjectionPostgreSQLRepository,
    DetectionPostgreSQLRepository,
    EvidencePostgreSQLRepository,
    FeatureSnapshotPostgreSQLRepository,
    MarketContextPostgreSQLRepository,
    MarketSnapshotPostgreSQLRepository,
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
from app.runtime_detection import RuntimeOpportunityDetectionService
from app.runtime_evidence import RuntimeEvidenceService
from app.runtime_opportunity_plan import RuntimeOpportunityPlanService
from app.runtime_features import RuntimeFeatureEngine
from app.runtime_qualification import RuntimeQualificationService
from app.runtime_ranking import RuntimeRankingService
from app.runtime_scoring import RuntimeScoringService


_SCOPE = MarketScope(instrument="BTCUSDT", timeframe="5m")
_CODE_VERSION = "alphalens.runtime.1.0.0"
_FEATURE_KEYS = {
    "exponential_moving_average_12": "ema12",
    "exponential_moving_average_26": "ema26",
    "relative_strength_index": "rsi",
}


def _json(value: Any) -> str:
    def encode(item: Any) -> str:
        if isinstance(item, (datetime, Decimal)):
            return str(item)
        return repr(item)

    return json.dumps(value, default=encode, sort_keys=True)


def _artifact(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "items") and hasattr(value, "next_cursor"):
        items = value.items
        return {
            "page_item_count": len(items),
            "item_ids": tuple(
                next(
                    (
                        getattr(item, field)
                        for field in ("snapshot_id", "opportunity_version_id", "context_id")
                        if hasattr(item, field)
                    ),
                    repr(item),
                )
                for item in items[:5]
            ),
            "next_cursor": value.next_cursor,
        }
    fields = (
        "snapshot_id", "context_id", "attempt_id", "candidate_id", "package_id",
        "opportunity_id", "opportunity_version_id", "qualification_id", "score_id",
        "ranking_snapshot_id", "snapshot_id",
    )
    result = {field: getattr(value, field) for field in fields if hasattr(value, field)}
    if hasattr(value, "state"):
        result["state"] = str(value.state)
    if hasattr(value, "outcome"):
        result["outcome"] = str(value.outcome)
    if hasattr(value, "reason_codes"):
        result["reason_codes"] = tuple(value.reason_codes)
    return result or repr(value)


class TracedRepository:
    """Log every repository method the real services invoke."""

    def __init__(self, name: str, repository: Any) -> None:
        self._name = name
        self._repository = repository

    def __getattr__(self, method_name: str) -> Any:
        target = getattr(self._repository, method_name)
        if not inspect.iscoroutinefunction(target):
            return target

        async def traced(*args: Any, **kwargs: Any) -> Any:
            kind = "write" if method_name.startswith("save") else "read"
            print(f"REPOSITORY {kind} entered repo={self._name} method={method_name}")
            try:
                result = await target(*args, **kwargs)
            except Exception as error:
                print(
                    f"REPOSITORY {kind} raised repo={self._name} method={method_name} "
                    f"error={type(error).__name__}: {error}"
                )
                raise
            print(
                f"REPOSITORY {kind} returned repo={self._name} method={method_name} "
                f"object={_json(_artifact(result))}"
            )
            return result

        return traced


async def _run_stage(name: str, operation: Any) -> tuple[Any | None, Exception | None]:
    print(f"STAGE {name} entered")
    try:
        result = await operation()
    except Exception as error:
        print(f"STAGE {name} raised {type(error).__name__}: {error}")
        return None, error
    print(f"STAGE {name} returned object={_json(_artifact(result))}")
    return result, None


def _feature_values(snapshot: Any) -> dict[str, str | None]:
    values = {value.feature_identifier: str(value.value) for value in snapshot.values}
    return {label: values.get(identifier) for identifier, label in _FEATURE_KEYS.items()}


async def main() -> None:
    markets = TracedRepository("market_snapshots", MarketSnapshotPostgreSQLRepository(session_factory))
    features = TracedRepository("feature_snapshots", FeatureSnapshotPostgreSQLRepository(session_factory))
    contexts = TracedRepository("market_contexts", MarketContextPostgreSQLRepository(session_factory))
    detections = TracedRepository("detections", DetectionPostgreSQLRepository(session_factory))
    evidence_repo = TracedRepository("evidence", EvidencePostgreSQLRepository(session_factory))
    opportunities = TracedRepository("opportunities", OpportunityPostgreSQLRepository(session_factory))
    plans = TracedRepository("plans", OpportunityPlanPostgreSQLRepository(session_factory))
    qualifications = TracedRepository("qualifications", QualificationPostgreSQLRepository(session_factory))
    scores = TracedRepository("scores", ScoringPostgreSQLRepository(session_factory))
    rankings = TracedRepository("rankings", RankingPostgreSQLRepository(session_factory))
    dashboard = TracedRepository("dashboard", DashboardProjectionPostgreSQLRepository(session_factory))

    feature_engine = RuntimeFeatureEngine(market_snapshots=markets, feature_snapshots=features, code_version=_CODE_VERSION)
    context_service = RuntimeMarketContextService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, code_version=_CODE_VERSION)
    detection_service = RuntimeOpportunityDetectionService(market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, detections=detections, code_version=_CODE_VERSION)
    evidence_service = RuntimeEvidenceService(candidates=detections, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, evidence=evidence_repo, code_version=_CODE_VERSION)
    plan_service = RuntimeOpportunityPlanService(code_version=_CODE_VERSION)
    assessment_service = RuntimeAssessmentService(candidates=detections, evidence=evidence_repo, market_snapshots=markets, feature_snapshots=features, market_contexts=contexts, opportunities=opportunities, plans_repository=plans, plans=plan_service, code_version=_CODE_VERSION)
    qualification_service = RuntimeQualificationService(opportunities=opportunities, evidence=evidence_repo, market_contexts=contexts, feature_snapshots=features, market_snapshots=markets, qualifications=qualifications, code_version=_CODE_VERSION)
    scoring_service = RuntimeScoringService(opportunities=opportunities, qualifications=qualifications, evidence=evidence_repo, market_contexts=contexts, scores=scores, code_version=_CODE_VERSION)
    ranking_service = RuntimeRankingService(scores=scores, qualifications=qualifications, opportunities=opportunities, rankings=rankings, code_version=_CODE_VERSION)
    dashboard_service = RuntimeDashboardProjectionService(rankings=rankings, dashboard=dashboard, code_version=_CODE_VERSION)

    now = datetime.now(timezone.utc)
    query = ScopedRepositoryQuery(scope=_SCOPE, as_of=now, limit=1)
    market, error = await _run_stage("market snapshot", lambda: markets.get_latest(query))
    if error is not None:
        return
    print(f"SNAPSHOT id={market.snapshot_id} candle={market.candles[0].timestamp} available_at={market.audit.available_at}")

    feature_snapshot, error = await _run_stage("feature generation", lambda: feature_engine.resolve(market))
    if feature_snapshot is None:
        print("FEATURES number=0 EMA12=None EMA26=None RSI=None")
        for stage in ("market context", "detection", "evidence", "assessment", "qualification", "scoring", "ranking", "opportunity persistence", "dashboard projection"):
            print(f"STAGE {stage} entered=False returned_object=None repository_reads=[] repository_writes=[] rejection_reason=upstream.feature_generation_failed")
        await _run_stage("opportunities repository contents", lambda: opportunities.get_by_scope(ScopedRepositoryQuery(scope=_SCOPE, as_of=datetime.now(timezone.utc), limit=100)))
        return
    print(f"FEATURES number={len(feature_snapshot.values)} {_json(_feature_values(feature_snapshot))}")

    context, error = await _run_stage("market context", lambda: context_service.build(market, feature_snapshot))
    if context is None:
        return
    detection, error = await _run_stage("detection", lambda: detection_service.detect(market, feature_snapshot, context))
    if detection is None:
        return
    attempt, candidate = detection
    print(f"DETECTION detect_called=True attempt={_json(_artifact(attempt))} candidate={_json(_artifact(candidate))}")
    if candidate is None:
        print(f"DETECTION rejection_reason={_json(getattr(attempt, 'reason_codes', ())) }")
        for stage in ("evidence", "assessment", "qualification", "scoring", "ranking", "opportunity persistence", "dashboard projection"):
            print(f"STAGE {stage} entered=False returned_object=None repository_reads=[] repository_writes=[] rejection_reason=upstream.no_candidate")
        await _run_stage("opportunities repository contents", lambda: opportunities.get_by_scope(ScopedRepositoryQuery(scope=_SCOPE, as_of=datetime.now(timezone.utc), limit=100)))
        return

    evidence, error = await _run_stage("evidence", lambda: evidence_service.assemble(candidate, market, feature_snapshot, context))
    if evidence is None:
        return
    opportunity, error = await _run_stage("assessment", lambda: assessment_service.assess(candidate, evidence, context))
    if opportunity is None:
        return
    qualification, error = await _run_stage("qualification", lambda: qualification_service.qualify(opportunity, evidence, context))
    if qualification is None:
        return
    if str(qualification.outcome) != "QUALIFIED":
        print(f"QUALIFICATION rejection_reason={qualification.outcome}")
        for stage in ("scoring", "ranking", "dashboard projection"):
            print(f"STAGE {stage} entered=False returned_object=None repository_reads=[] repository_writes=[] rejection_reason=upstream.not_qualified")
        await _run_stage("opportunities repository contents", lambda: opportunities.get_by_scope(ScopedRepositoryQuery(scope=_SCOPE, as_of=datetime.now(timezone.utc), limit=100)))
        return
    score, error = await _run_stage("scoring", lambda: scoring_service.score(opportunity, qualification, evidence, context))
    if score is None:
        return
    ranking, error = await _run_stage("ranking", lambda: ranking_service.rank((opportunity,), (qualification,), (score,), market.audit.available_at))
    if ranking is None:
        return
    print("STAGE opportunity persistence entered=True returned_object=already_persisted_by_assessment")
    print("STAGE dashboard projection entered=False returned_object=None rejection_reason=lifecycle_required_for_dashboard")
    await _run_stage("opportunities repository contents", lambda: opportunities.get_by_scope(ScopedRepositoryQuery(scope=_SCOPE, as_of=datetime.now(timezone.utc), limit=100)))


if __name__ == "__main__":
    asyncio.run(main())
