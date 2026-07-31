"""Dedicated read-only FastAPI surface for Phase-1 operational evidence."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.market_data.coverage import HistoricalCoverageError
from app.market_data.inspection import (
    HistoricalInspectionError,
    HistoricalOperationalInspection,
    verify_historical_operational_inspection,
)
from app.market_data.orchestration import HistoricalOrchestrationError
from app.market_data.quality import HistoricalQualityError
from app.market_data.synchronization import HistoricalSynchronizationError
from app.persistence.conflicts import SourceConflictIntegrityError
from app.persistence.database import session_factory
from app.persistence.inspection import load_historical_operational_inspection


InspectionProvider = Callable[[datetime], Awaitable[HistoricalOperationalInspection]]


def create_historical_inspection_app(
    *,
    maximum_request_bytes: int = 32_768,
    inspection_provider: InspectionProvider | None = None,
) -> FastAPI:
    """Create the isolated GET-only historical inspection application."""
    if maximum_request_bytes <= 0:
        raise ValueError("Maximum inspection request size must be positive.")
    app = FastAPI(
        title="AlphaLens Historical Operational Inspection",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.maximum_request_bytes = maximum_request_bytes
    app.state.inspection_provider = inspection_provider or _database_provider

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request
        return _error_response(
            422,
            "REQUEST_SCHEMA_INVALID",
            "Inspection query parameters are invalid.",
            [
                {
                    "location": ".".join(str(item) for item in error["loc"]),
                    "type": error["type"],
                }
                for error in exc.errors()
            ],
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        del request
        if exc.status_code == 404:
            return _error_response(
                404,
                "ROUTE_NOT_FOUND",
                "The requested inspection route does not exist.",
            )
        if exc.status_code == 405:
            return _error_response(
                405,
                "METHOD_NOT_ALLOWED",
                "The inspection surface permits GET only.",
            )
        return _error_response(
            exc.status_code,
            "HTTP_ERROR",
            "The inspection request cannot be completed.",
        )

    @app.middleware("http")
    async def enforce_read_only_request(request: Request, call_next):
        declared_size = _content_length(request)
        if (
            declared_size is not None
            and declared_size > app.state.maximum_request_bytes
        ):
            return _error_response(
                413,
                "REQUEST_TOO_LARGE",
                "Request body exceeds the configured size limit.",
            )
        body = await request.body()
        if len(body) > app.state.maximum_request_bytes:
            return _error_response(
                413,
                "REQUEST_TOO_LARGE",
                "Request body exceeds the configured size limit.",
            )
        if body:
            return _error_response(
                400,
                "REQUEST_BODY_NOT_ALLOWED",
                "The read-only inspection request cannot contain a body.",
            )
        return await call_next(request)

    @app.get("/v1/historical-inspection/state")
    async def historical_state(
        as_of: datetime = Query(...),
        asset_identifier: str = Query("BTC"),
        quote_currency: str = Query("USD"),
    ) -> JSONResponse:
        if asset_identifier != "BTC" or quote_currency != "USD":
            return _error_response(
                422,
                "SCOPE_UNSUPPORTED",
                "Historical inspection supports BTC/USD only.",
            )
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            return _error_response(
                422,
                "AS_OF_TIMEZONE_REQUIRED",
                "Inspection as-of must include an explicit timezone.",
            )
        cutoff = as_of.astimezone(timezone.utc)
        try:
            inspection = await app.state.inspection_provider(cutoff)
            verify_historical_operational_inspection(inspection)
            return JSONResponse(
                content=inspection.response(),
                headers={
                    "Cache-Control": "no-store",
                    "X-AlphaLens-Evidence-SHA256": inspection.result_hash,
                },
            )
        except (
            HistoricalInspectionError,
            HistoricalOrchestrationError,
            HistoricalCoverageError,
            HistoricalSynchronizationError,
            HistoricalQualityError,
            SourceConflictIntegrityError,
            ValueError,
        ):
            return _error_response(
                409,
                "INTEGRITY_VALIDATION_FAILED",
                "Historical operational evidence could not be verified.",
            )
        except SQLAlchemyError:
            return _error_response(
                503,
                "INSPECTION_UNAVAILABLE",
                "Historical operational evidence is unavailable.",
            )

    return app


async def _database_provider(as_of: datetime) -> HistoricalOperationalInspection:
    async with session_factory() as session:
        return await load_historical_operational_inspection(session, as_of=as_of)


def _content_length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        size = int(value)
    except ValueError:
        return None
    return max(size, 0)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, str]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            }
        },
    )
