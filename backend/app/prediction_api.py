"""Production entry point for the read-only live prediction API."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
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


class _PipelineAwareLiveMarketIngestionService(LiveMarketIngestionService):
    """Extend live ingestion to trigger the runtime pipeline after each 5m persist."""

    async def _persist(self, candle) -> MarketSnapshot | None:
        snapshot = await super()._persist(candle)

        if snapshot is not None:
            logger.info(
                "pipeline_task_scheduled snapshot_id=%s",
                snapshot.snapshot_id,
            )

            async def _run_pipeline() -> None:
                logger.info(
                    "pipeline_task_started snapshot_id=%s",
                    snapshot.snapshot_id,
                )
                try:
                    await _runtime_pipeline.run_for_snapshot(
                        snapshot,
                        snapshot.audit.available_at,
                    )
                except Exception:
                    logger.exception(
                        "pipeline_task_crashed snapshot_id=%s",
                        snapshot.snapshot_id,
                    )
                else:
                    logger.info(
                        "pipeline_task_finished snapshot_id=%s",
                        snapshot.snapshot_id,
                    )

            asyncio.create_task(
                _run_pipeline(),
                name=f"alphalens-runtime-pipeline-{snapshot.snapshot_id}",
            )

        return snapshot


live_market_ingestion = _PipelineAwareLiveMarketIngestionService(
    repository=market_snapshot_repository,
    code_version="alphalens.prediction_api.1.0.0",
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
    from app.opportunity_intelligence.persistence import LifecyclePostgreSQLRepository

    lifecycle_repo = LifecyclePostgreSQLRepository(session_factory)
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
        except Exception:
            logger.exception("lifecycle_sweep_failed")


@asynccontextmanager
async def _infrastructure_lifespan(application):
    global _runtime_pipeline
    try:
        async with _application_lifespan(application):
            try:
                await live_market_ingestion.warmup_history()
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
