"""Production entry point for the read-only live prediction API."""

from contextlib import asynccontextmanager

from sqlalchemy import text

from app.api.application import create_prediction_app
from app.infrastructure.observability import install_observability
from app.infrastructure.redis import RedisInfrastructure
from app.infrastructure.schema import schema_is_current
from app.observability.logging import configure_structured_logging
from app.opportunity_intelligence.api import create_opportunity_intelligence_app
from app.opportunity_intelligence.persistence import (
    DashboardProjectionPostgreSQLRepository,
    MarketSnapshotPostgreSQLRepository,
    OpportunityDetailPostgreSQLRepository,
    RuntimeGovernancePostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import RepositoryError
from app.persistence.database import session_factory
from app.settings import load_settings


settings = load_settings()
configure_structured_logging(settings.log_level)
app = create_prediction_app(
    maximum_request_bytes=settings.prediction_api_max_request_bytes,
    cors_allowed_origins=settings.cors_allowed_origins,
)
opportunity_app = create_opportunity_intelligence_app(
    dashboard_repository=DashboardProjectionPostgreSQLRepository(session_factory),
    detail_repository=OpportunityDetailPostgreSQLRepository(session_factory),
    governance_repository=RuntimeGovernancePostgreSQLRepository(session_factory),
    market_repository=MarketSnapshotPostgreSQLRepository(session_factory),
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
    async with _application_lifespan(application):
        try:
            yield
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
