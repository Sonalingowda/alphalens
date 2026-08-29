"""Production entry point for the read-only live prediction API."""

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import text

from app.api.application import create_prediction_app
from app.infrastructure.observability import install_observability
from app.infrastructure.redis import RedisInfrastructure
from app.infrastructure.schema import schema_is_current
from app.live_market_data import LiveMarketIngestionService
from app.observability.logging import configure_structured_logging
from app.opportunity_intelligence.api import create_opportunity_intelligence_app
from app.opportunity_intelligence.domain import MarketSnapshot
from app.opportunity_intelligence.persistence import (
    DashboardProjectionPostgreSQLRepository,
    LifecyclePostgreSQLRepository,
    MarketSnapshotPostgreSQLRepository,
    OpportunityDetailPostgreSQLRepository,
    OpportunityPlanPostgreSQLRepository,
    RuntimeGovernancePostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import RepositoryError
from app.persistence.database import session_factory
from app.runtime_pipeline import build_runtime_pipeline
from app.inference.repository import load_expected_move_artifact
from app.settings import load_settings


logger = logging.getLogger("alphalens.prediction_api")

settings = load_settings()
configure_structured_logging(settings.log_level)
market_snapshot_repository = MarketSnapshotPostgreSQLRepository(session_factory)

# Build the complete runtime intelligence pipeline wired to PostgreSQL.
_runtime_pipeline = build_runtime_pipeline(session_factory)


@dataclass
class _PipelineHealth:
    """Observable runtime pipeline execution state for production diagnostics."""

    last_run_at: str | None = None
    run_count: int = 0
    last_error: str | None = None
    last_snapshot_id: str | None = None
    last_outcome: str | None = None
    pending_tasks: int = 0


_pipeline_health = _PipelineHealth()
_pipeline_tasks: set[asyncio.Task] = set()


class _PipelineAwareLiveMarketIngestionService(LiveMarketIngestionService):
    """Extend live ingestion to trigger the runtime pipeline after each 5m persist."""

    async def _persist(self, candle) -> MarketSnapshot | None:
        snapshot = await super()._persist(candle)

        if snapshot is not None:
            self._schedule_pipeline(snapshot)

        return snapshot

    def _schedule_pipeline(self, snapshot: MarketSnapshot) -> None:
        logger.info(
            "pipeline_task_scheduled snapshot_id=%s",
            snapshot.snapshot_id,
        )
        task = asyncio.create_task(
            self._run_pipeline(snapshot),
            name=f"alphalens-runtime-pipeline-{snapshot.snapshot_id}",
        )
        _pipeline_tasks.add(task)
        task.add_done_callback(_pipeline_tasks.discard)

    async def _run_pipeline(self, snapshot: MarketSnapshot) -> None:
        _pipeline_health.last_run_at = datetime.now(timezone.utc).isoformat()
        _pipeline_health.run_count += 1
        _pipeline_health.last_snapshot_id = snapshot.snapshot_id
        _pipeline_health.pending_tasks = len(_pipeline_tasks)
        logger.info(
            "pipeline_task_started snapshot_id=%s",
            snapshot.snapshot_id,
        )
        try:
            result = await _runtime_pipeline.run_for_snapshot(
                snapshot,
                snapshot.audit.available_at,
            )
        except Exception:
            _pipeline_health.last_error = "pipeline_task_crashed"
            logger.exception(
                "pipeline_task_crashed snapshot_id=%s",
                snapshot.snapshot_id,
            )
        else:
            _pipeline_health.last_error = None
            _pipeline_health.last_outcome = (
                result.outcome.value if result is not None else None
            )
            logger.info(
                "pipeline_task_finished snapshot_id=%s outcome=%s",
                snapshot.snapshot_id,
                _pipeline_health.last_outcome,
            )


live_market_ingestion = _PipelineAwareLiveMarketIngestionService(
    repository=market_snapshot_repository,
    code_version="alphalens.prediction_api.1.0.0",
    rest_base_url=settings.market_data_rest_base_url,
)
app = create_prediction_app(
    maximum_request_bytes=settings.prediction_api_max_request_bytes,
    cors_allowed_origins=settings.cors_allowed_origins,
)
opportunity_app = create_opportunity_intelligence_app(
    dashboard_repository=DashboardProjectionPostgreSQLRepository(session_factory),
    detail_repository=OpportunityDetailPostgreSQLRepository(session_factory),
    plans_repository=OpportunityPlanPostgreSQLRepository(session_factory),
    governance_repository=RuntimeGovernancePostgreSQLRepository(session_factory),
    market_repository=market_snapshot_repository,
    lifecycle_repository=LifecyclePostgreSQLRepository(session_factory),
)
_mvp_paths = {
    "/api/v1/opportunities",
    "/api/v1/opportunities/{opportunity_id}",
    "/api/v1/opportunities/history",
    "/api/v1/opportunity-intelligence/health",
    "/health",
    "/markets/live",
    "/opportunities",
    "/opportunities/{opportunity_id}",
}
app.router.routes.extend(
    route
    for route in opportunity_app.router.routes
    if getattr(route, "path", None) in _mvp_paths
)
app.add_exception_handler(
    RepositoryError,
    opportunity_app.exception_handlers[RepositoryError],
)


@app.get("/api/v1/pipeline/health", include_in_schema=False)
async def pipeline_health() -> dict:
    """Read-only diagnostic: runtime pipeline execution state."""
    return {
        "contract_version": "1.0.0",
        "last_run_at": _pipeline_health.last_run_at,
        "run_count": _pipeline_health.run_count,
        "last_error": _pipeline_health.last_error,
        "last_snapshot_id": _pipeline_health.last_snapshot_id,
        "last_outcome": _pipeline_health.last_outcome,
        "pending_tasks": len(_pipeline_tasks),
        "warmup_rest_base_url": settings.market_data_rest_base_url,
    }


@app.post("/api/v1/pipeline/run-latest", include_in_schema=False)
async def pipeline_run_latest() -> dict:
    """Diagnostic: force one pipeline run for the latest BTCUSDT/5m snapshot.

    Surfaces the actual outcome or error so production failures are observable
    without log access.  May create a real opportunity if detection triggers.
    """
    from app.market_configuration import get_default_scope
    from app.opportunity_intelligence.repositories import ScopedRepositoryQuery

    scope = get_default_scope()
    try:
        latest = await market_snapshot_repository.get_latest(
            ScopedRepositoryQuery(
                scope=scope,
                as_of=datetime.now(timezone.utc),
                limit=1,
            )
        )
    except Exception as error:  # noqa: BLE001 - diagnostic surface
        return {"status": "snapshot_lookup_failed", "error": repr(error)}
    try:
        result = await _runtime_pipeline.run_for_snapshot(
            latest,
            latest.audit.available_at,
        )
    except Exception as error:  # noqa: BLE001 - diagnostic surface
        return {
            "status": "pipeline_failed",
            "snapshot_id": latest.snapshot_id,
            "error": repr(error),
        }
    stages = (
        [
            {
                "stage": record.stage.value,
                "status": record.status.value,
                "reason": record.reason_code,
            }
            for record in result.stages
        ]
        if result is not None
        else []
    )
    return {
        "status": "ok",
        "snapshot_id": latest.snapshot_id,
        "outcome": result.outcome.value if result is not None else None,
        "stages": stages,
    }


@app.post("/api/v1/pipeline/diagnose-latest", include_in_schema=False)
async def pipeline_diagnose_latest() -> dict:
    """Diagnostic: surface the exact detection input-validation reason for the
    latest BTCUSDT/5m snapshot. Reconstructs persisted inputs exactly as
    detection does; does not alter detection semantics.
    """
    from app.market_configuration import get_default_scope
    from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
    from app.opportunity_intelligence.persistence import (
        FeatureSnapshotPostgreSQLRepository,
        MarketContextPostgreSQLRepository,
    )
    from app.runtime_detection.service import (
        _REQUIRED_FEATURES,
        _load_persisted_inputs,
        _required_values,
        _validate_inputs,
    )

    scope = get_default_scope()
    now = datetime.now(timezone.utc)
    market = await market_snapshot_repository.get_latest(
        ScopedRepositoryQuery(scope=scope, as_of=now, limit=1)
    )
    feature_repo = FeatureSnapshotPostgreSQLRepository(session_factory)
    context_repo = MarketContextPostgreSQLRepository(session_factory)
    as_of = market.audit.available_at
    recent = await market_snapshot_repository.get_by_scope(
        ScopedRepositoryQuery(scope=scope, as_of=now, limit=600)
    )
    history_depth = len(recent.items)
    oldest_ts = (
        recent.items[-1].candles[0].timestamp.isoformat() if recent.items else None
    )
    newest_ts = (
        recent.items[0].candles[0].timestamp.isoformat() if recent.items else None
    )
    payload: dict = {
        "snapshot_id": market.snapshot_id,
        "history_depth": history_depth,
        "history_oldest": oldest_ts,
        "history_newest": newest_ts,
    }
    try:
        features = await feature_repo.get_latest(
            ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=1)
        )
        context = await context_repo.get_latest(
            ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=1)
        )
        inputs = await _load_persisted_inputs(market, features, context)
        reason = _validate_inputs(inputs, scope.instrument)
        present: set[tuple[str, str]] = set()
        try:
            values = _required_values(features)
            present = {(key[0], key[2]) for key in values}
        except Exception as exc:  # noqa: BLE001 - diagnostic surface
            payload["required_values_error"] = repr(exc)
        required = {(item[0], item[2]) for item in _REQUIRED_FEATURES}
        payload.update(
            {
                "validate_reason": reason,
                "market_complete": market.complete,
                "candle_count": len(market.candles),
                "required_features": sorted(f"{a}:{b}" for a, b in required),
                "required_features_present": sorted(f"{a}:{b}" for a, b in present),
                "context_data_quality_status": context.data_quality.status.value,
                "context_components": {
                    name: getattr(context, name).status.value
                    for name in (
                        "trend",
                        "momentum",
                        "volatility",
                        "structure",
                        "session",
                    )
                },
                "feature_cutoff": str(inputs.cutoff),
                "market_available_at": str(market.audit.available_at),
            }
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic surface
        payload["inputs_error"] = repr(exc)
    return payload


redis_infrastructure = RedisInfrastructure.from_url(settings.redis_url)
_application_lifespan = app.router.lifespan_context


async def _try_load_expected_move_inference():
    """Attempt to load the expected-move inference artifact from the database."""
    try:
        async with session_factory() as session:
            loaded = await load_expected_move_artifact(session)
            if loaded is not None:
                logger.info(
                    "expected_move_artifact_loaded artifact_id=%s",
                    loaded.artifact_id,
                )
                return loaded.inference
    except Exception:
        logger.exception("expected_move_artifact_load_failed")
    return None


_SWEEP_INTERVAL_SECONDS = 60
_ACTIVE_MAX_AGE_MINUTES = 10


async def _run_lifecycle_sweep(stop_event: asyncio.Event) -> None:
    """Periodically expire stale RANKED lifecycles to EXPIRED."""
    from app.runtime_lifecycle import RuntimeLifecycleService
    from app.opportunity_intelligence.persistence import (
        LifecyclePostgreSQLRepository,
        OpportunityPlanPostgreSQLRepository,
        OutcomePostgreSQLRepository,
    )
    from app.outcome_resolution.service import OutcomeResolutionService

    lifecycle_repo = LifecyclePostgreSQLRepository(session_factory)
    plan_repo = OpportunityPlanPostgreSQLRepository(session_factory)
    outcome_repo = OutcomePostgreSQLRepository(session_factory)

    class _CandleQueryAdapter:
        async def query(
            self,
            instrument: str,
            timeframe: str,
            after: datetime,
            up_to_and_including: datetime,
        ) -> tuple[dict, ...]:
            from app.persistence.models import CandleRecord
            from sqlalchemy import select

            async with session_factory() as session:
                rows = (
                    await session.scalars(
                        select(CandleRecord).where(
                            CandleRecord.asset_identifier == instrument,
                            CandleRecord.timeframe == timeframe,
                            CandleRecord.candle_timestamp > after,
                            CandleRecord.candle_timestamp <= up_to_and_including,
                        ).order_by(CandleRecord.candle_timestamp.asc())
                    )
                ).all()
                return tuple(
                    {
                        "timestamp": r.candle_timestamp,
                        "open": r.open_price,
                        "high": r.high_price,
                        "low": r.low_price,
                        "close": r.close_price,
                        "volume": r.volume,
                    }
                    for r in rows
                )

    outcome_service = OutcomeResolutionService(candle_query=_CandleQueryAdapter())
    lifecycle_service = RuntimeLifecycleService(lifecycles=lifecycle_repo)

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=_SWEEP_INTERVAL_SECONDS
            )
            break
        except asyncio.TimeoutError:
            pass

        try:
            as_of = datetime.now(timezone.utc)
            expired = await lifecycle_service.expire_stale(
                as_of=as_of,
                active_max_age_minutes=_ACTIVE_MAX_AGE_MINUTES,
            )
            if expired:
                logger.info(
                    "lifecycle_sweep_expired count=%d",
                    len(expired),
                )
                for lifecycle in expired:
                    try:
                        await _resolve_outcome_for_expired(
                            lifecycle, outcome_service, plan_repo, outcome_repo
                        )
                    except Exception:
                        logger.exception(
                            "outcome_resolution_failed opportunity_id=%s",
                            lifecycle.opportunity_id,
                        )
        except Exception:
            logger.exception("lifecycle_sweep_failed")


async def _resolve_outcome_for_expired(
    lifecycle,
    outcome_service,
    plan_repo,
    outcome_repo,
) -> None:
    """Best-effort outcome resolution for one expired lifecycle.

    Uses the first lifecycle event (DETECTED) as the signal timestamp,
    NOT the EXPIRED event.  Skips resolution if plan.valid_until is still
    in the future to prevent premature outcome determination.
    """
    from app.opportunity_intelligence.repositories.queries import (
        EntityAsOfQuery,
        EntityId,
    )

    signal_event = lifecycle.events[0]
    opportunity_id = lifecycle.opportunity_id

    plan = await plan_repo.get_latest_for_opportunity(
        EntityAsOfQuery(
            entity_id=EntityId(opportunity_id),
            as_of=signal_event.available_at,
        )
    )

    if plan is None:
        logger.warning(
            "outcome_resolution_skipped_no_plan opportunity_id=%s",
            opportunity_id,
        )
        return

    if plan.valid_until is not None and plan.valid_until > datetime.now(timezone.utc):
        logger.info(
            "outcome_resolution_skipped_premature opportunity_id=%s valid_until=%s",
            opportunity_id,
            plan.valid_until.isoformat(),
        )
        return

    if plan.valid_until is None:
        # Documented V1.1 exception: V1.1 plans carry no validity window, so
        # the resolution horizon is derived from the established 10-minute
        # active-expiration policy. The persisted plan artifact is unchanged.
        plan = replace(
            plan,
            valid_until=(
                signal_event.available_at
                + timedelta(minutes=_ACTIVE_MAX_AGE_MINUTES)
            ),
        )

    outcome_record = await outcome_service.resolve(
        opportunity_id=opportunity_id,
        opportunity_version_id=lifecycle.events[-1].opportunity_version_id,
        direction=lifecycle.direction.value,
        signal_timestamp=signal_event.available_at,
        evidence_cutoff=signal_event.audit.evidence_cutoff,
        plan=plan,
    )
    await outcome_repo.save(outcome_record)
    logger.info(
        "outcome_resolved opportunity_id=%s outcome=%s",
        opportunity_id,
        outcome_record.outcome.value,
    )


@asynccontextmanager
async def _infrastructure_lifespan(application):
    global _runtime_pipeline
    try:
        async with _application_lifespan(application):
            try:
                await live_market_ingestion.warmup_history_with_retry()
            except Exception:
                logger.exception("warmup_history_failed")
            em_inference = await _try_load_expected_move_inference()
            if em_inference is not None:
                _runtime_pipeline = build_runtime_pipeline(
                    session_factory,
                    expected_move_inference=em_inference,
                )
                logger.info("runtime_pipeline_upgraded_to_v2")
            stop_event = asyncio.Event()
            ingestion_task = asyncio.create_task(
                live_market_ingestion.run(stop_event),
                name="alphalens-live-market-ingestion",
            )
            application.state.live_market_ingestion = live_market_ingestion
            application.state.live_market_ingestion_task = ingestion_task
            lifecycle_sweep_task = asyncio.create_task(
                _run_lifecycle_sweep(stop_event),
                name="alphalens-lifecycle-sweep",
            )
            application.state.lifecycle_sweep_task = lifecycle_sweep_task
            try:
                yield
            finally:
                stop_event.set()
                ingestion_task.cancel()
                lifecycle_sweep_task.cancel()
                with suppress(asyncio.CancelledError):
                    await ingestion_task
                with suppress(asyncio.CancelledError):
                    await lifecycle_sweep_task
    finally:
        await redis_infrastructure.close()


app.router.lifespan_context = _infrastructure_lifespan


async def _database_ready() -> bool:
    async with session_factory() as session:
        return (await session.scalar(text("SELECT 1"))) == 1


async def _redis_ready() -> bool:
    return await redis_infrastructure.ping()


install_observability(
    app,
    readiness_checks={
        "postgresql": _database_ready,
        "redis": _redis_ready,
        "schema": schema_is_current,
    },
    metrics_enabled=settings.metrics_enabled,
)
