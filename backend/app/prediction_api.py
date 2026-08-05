"""Production entry point for the read-only live prediction API."""

import asyncio
from contextlib import asynccontextmanager, suppress
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
    MarketSnapshotPostgreSQLRepository,
    OpportunityDetailPostgreSQLRepository,
    RuntimeGovernancePostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import RepositoryError
from app.persistence.database import session_factory
from app.runtime_pipeline import build_runtime_pipeline
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
            # Fire-and-forget: pipeline errors are logged inside run_for_snapshot
            # and must never crash the ingestion loop.
            asyncio.create_task(
                _runtime_pipeline.run_for_snapshot(
                    snapshot,
                    snapshot.audit.available_at,
                ),
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
    governance_repository=RuntimeGovernancePostgreSQLRepository(session_factory),
    market_repository=market_snapshot_repository,
)
_mvp_paths = {
    "/api/v1/opportunities",
    "/api/v1/opportunities/{opportunity_id}",
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


@asynccontextmanager
async def _infrastructure_lifespan(application):
    try:
        async with _application_lifespan(application):
            stop_event = asyncio.Event()
            ingestion_task = asyncio.create_task(
                live_market_ingestion.run(stop_event),
                name="alphalens-live-market-ingestion",
            )
            application.state.live_market_ingestion = live_market_ingestion
            application.state.live_market_ingestion_task = ingestion_task
            try:
                yield
            finally:
                stop_event.set()
                ingestion_task.cancel()
                with suppress(asyncio.CancelledError):
                    await ingestion_task
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
