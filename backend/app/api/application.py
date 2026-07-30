"""Dedicated read-only FastAPI application for production inference."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import logging
from time import perf_counter_ns
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.errors import PredictionAPIError
from app.api.metrics import PredictionAPIMetrics
from app.api.schemas import PredictionRequest, PredictionResponse
from app.inference.artifact import hash_json
from app.inference.repository import (
    LoadedProductionArtifact,
    load_production_artifact,
)
from app.inference.service import (
    PREDICTION_API_VERSION,
    PredictionValidationError,
    ProductionPredictionService,
)
from app.observability.resources import resource_snapshot
from app.persistence.database import session_factory
from app.persistence.dashboard import load_dashboard_snapshot
from app.persistence.prediction_api import (
    PredictionAPIAudit,
    persist_prediction_api_audit,
)


logger = logging.getLogger("uvicorn.error")
ArtifactProvider = Callable[
    [],
    Awaitable[LoadedProductionArtifact],
]
AuditWriter = Callable[[PredictionAPIAudit], Awaitable[UUID]]
DashboardProvider = Callable[[], Awaitable[dict[str, Any]]]


def create_prediction_app(
    *,
    maximum_request_bytes: int = 32_768,
    cors_allowed_origins: tuple[str, ...] = (),
    artifact_provider: ArtifactProvider | None = None,
    audit_writer: AuditWriter | None = None,
    dashboard_provider: DashboardProvider | None = None,
) -> FastAPI:
    if maximum_request_bytes <= 0:
        raise ValueError("Maximum API request size must be positive.")
    app = FastAPI(
        title="AlphaLens Live Prediction API",
        version=PREDICTION_API_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.maximum_request_bytes = maximum_request_bytes
    app.state.artifact_provider = (
        artifact_provider or _database_artifact_provider
    )
    app.state.audit_writer = audit_writer or _database_audit_writer
    app.state.dashboard_provider = (
        dashboard_provider or _database_dashboard_provider
    )
    app.state.metrics = PredictionAPIMetrics()
    if cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Accept", "Content-Type"],
            max_age=600,
        )

    @app.exception_handler(PredictionAPIError)
    async def prediction_error(
        request: Request,
        exc: PredictionAPIError,
    ) -> JSONResponse:
        request.state.error_code = exc.code
        payload = _error_payload(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
        request.state.response_hash = hash_json(payload)
        logger.error(
            "Prediction API request rejected.",
            extra={
                "request_path": request.url.path,
                "http_method": request.method,
                "error_code": exc.code,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request.state.error_code = "REQUEST_SCHEMA_INVALID"
        details = [
            {
                "location": ".".join(str(item) for item in error["loc"]),
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        payload = _error_payload(
            code="REQUEST_SCHEMA_INVALID",
            message="Request body does not match the API schema.",
            details=details,
        )
        request.state.response_hash = hash_json(payload)
        logger.error(
            "Prediction API request schema validation failed.",
            extra={
                "request_path": request.url.path,
                "http_method": request.method,
                "error_code": "REQUEST_SCHEMA_INVALID",
                "status_code": 422,
            },
        )
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code = (
            "ROUTE_NOT_FOUND"
            if exc.status_code == 404
            else "METHOD_NOT_ALLOWED"
            if exc.status_code == 405
            else "HTTP_ERROR"
        )
        request.state.error_code = code
        payload = _error_payload(
            code=code,
            message=(
                "The requested API route does not exist."
                if exc.status_code == 404
                else "The HTTP method is not permitted for this route."
                if exc.status_code == 405
                else "The request cannot be completed."
            ),
            details=[],
        )
        request.state.response_hash = hash_json(payload)
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
        )

    @app.middleware("http")
    async def observe_and_limit(
        request: Request,
        call_next,
    ):
        received_at = datetime.now(timezone.utc)
        started_ns = perf_counter_ns()
        declared_size = _content_length(request)
        body = (
            b""
            if declared_size is not None
            and declared_size > app.state.maximum_request_bytes
            else await request.body()
        )
        request_size = (
            declared_size
            if declared_size is not None
            and declared_size > len(body)
            else len(body)
        )
        request_hash = (
            hash_json(
                {
                    "oversized_declared_request_bytes": declared_size,
                }
            )
            if not body and declared_size
            else sha256(body).hexdigest()
        )
        request.state.request_hash = request_hash
        request.state.prediction_generated = False
        request.state.error_code = None
        request.state.artifact_id = None
        request.state.artifact_sha256 = None
        request.state.configuration_hash = None
        request.state.schema_hash = None
        request.state.prediction_hash = None
        if request_size > app.state.maximum_request_bytes:
            request.state.error_code = "REQUEST_TOO_LARGE"
            payload = _error_payload(
                code="REQUEST_TOO_LARGE",
                message="Request body exceeds the configured size limit.",
                details=[],
            )
            request.state.response_hash = hash_json(payload)
            response = JSONResponse(status_code=413, content=payload)
        else:
            logger.info(
                "Prediction API request received.",
                extra={
                    "request_path": request.url.path,
                    "http_method": request.method,
                },
            )
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "Prediction API unhandled error.",
                    extra={
                        "request_path": request.url.path,
                        "http_method": request.method,
                        "error_code": "INTERNAL_ERROR",
                        "status_code": 500,
                    },
                )
                request.state.error_code = "INTERNAL_ERROR"
                payload = _error_payload(
                    code="INTERNAL_ERROR",
                    message="The prediction service encountered an error.",
                    details=[],
                )
                request.state.response_hash = hash_json(payload)
                response = JSONResponse(status_code=500, content=payload)
        completed_at = datetime.now(timezone.utc)
        latency_microseconds = max(
            (perf_counter_ns() - started_ns) // 1_000,
            0,
        )
        response_hash = getattr(
            request.state,
            "response_hash",
            hash_json({"status_code": response.status_code}),
        )
        audit = PredictionAPIAudit(
            api_version=PREDICTION_API_VERSION,
            http_method=request.method,
            request_path=request.url.path,
            request_size_bytes=request_size,
            request_hash=request_hash,
            response_status=response.status_code,
            response_hash=response_hash,
            outcome=(
                "success" if response.status_code < 400 else "error"
            ),
            error_code=request.state.error_code,
            artifact_id=request.state.artifact_id,
            artifact_sha256=request.state.artifact_sha256,
            configuration_hash=request.state.configuration_hash,
            schema_hash=request.state.schema_hash,
            prediction_hash=request.state.prediction_hash,
            latency_microseconds=latency_microseconds,
            received_at=received_at,
            completed_at=completed_at,
        )
        try:
            audit_id = await app.state.audit_writer(audit)
        except Exception:
            logger.exception(
                "Prediction API audit persistence failed.",
                extra={
                    "request_path": request.url.path,
                    "http_method": request.method,
                    "error_code": "AUDIT_PERSISTENCE_UNAVAILABLE",
                    "status_code": 503,
                },
            )
            payload = _error_payload(
                code="AUDIT_PERSISTENCE_UNAVAILABLE",
                message="Immutable request auditing is unavailable.",
                details=[],
            )
            response = JSONResponse(status_code=503, content=payload)
            request.state.error_code = "AUDIT_PERSISTENCE_UNAVAILABLE"
        app.state.metrics.record(
            status_code=response.status_code,
            latency_microseconds=latency_microseconds,
            prediction_generated=request.state.prediction_generated,
        )
        if "audit_id" in locals():
            response.headers["X-AlphaLens-Audit-ID"] = str(audit_id)
        response.headers["X-AlphaLens-API-Version"] = (
            PREDICTION_API_VERSION
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    async def version(request: Request) -> dict[str, Any]:
        payload = {
            "api_name": "AlphaLens Live Prediction API",
            "api_version": PREDICTION_API_VERSION,
            "route_version": "v1",
            "inference_mode": "packaged_artifact_only",
            "read_only": True,
        }
        request.state.response_hash = hash_json(payload)
        return payload

    async def health(request: Request) -> dict[str, Any]:
        artifact = await _artifact_or_error(request)
        payload = {
            "status": "healthy",
            "api_version": PREDICTION_API_VERSION,
            "artifact_status": "verified",
            "artifact_identifier": str(artifact.artifact_id),
            "read_only": True,
        }
        request.state.response_hash = hash_json(payload)
        return payload

    async def model(request: Request) -> dict[str, Any]:
        artifact = await _artifact_or_error(request)
        service = ProductionPredictionService(artifact)
        payload = {
            "api_version": PREDICTION_API_VERSION,
            "artifact_identifier": str(artifact.artifact_id),
            "model_family": artifact.model_family,
            "artifact_version": "1.0.0",
            "artifact_sha256": artifact.artifact_sha256,
            "configuration_hash": artifact.configuration_hash,
            "feature_pipeline_version": (
                artifact.feature_pipeline_version
            ),
            "target_version": artifact.target_version,
            "target_name": "forward_log_return",
            "horizon_observations": 5,
            "schema_hash": service.schema_hash,
            "feature_count": len(service.ordered_feature_names),
            "ordered_feature_names": list(
                service.ordered_feature_names
            ),
        }
        request.state.schema_hash = service.schema_hash
        request.state.response_hash = hash_json(payload)
        return payload

    async def metrics(request: Request) -> dict[str, Any]:
        snapshot = app.state.metrics.snapshot()
        payload = {
            "api_version": PREDICTION_API_VERSION,
            "request_count": snapshot.request_count,
            "successful_request_count": (
                snapshot.successful_request_count
            ),
            "error_request_count": snapshot.error_request_count,
            "prediction_count": snapshot.prediction_count,
            "average_latency_microseconds": (
                snapshot.average_latency_microseconds
            ),
            "maximum_latency_microseconds": (
                snapshot.maximum_latency_microseconds
            ),
            "health": "operational",
        }
        request.state.response_hash = hash_json(payload)
        return payload

    async def resources(request: Request) -> dict[str, Any]:
        payload = {
            "api_version": PREDICTION_API_VERSION,
            **resource_snapshot().to_dict(),
        }
        request.state.response_hash = hash_json(payload)
        return payload

    async def dashboard(request: Request) -> dict[str, Any]:
        await _artifact_or_error(request)
        try:
            payload = await request.app.state.dashboard_provider()
        except Exception as exc:
            raise PredictionAPIError(
                status_code=503,
                code="DASHBOARD_DATA_UNAVAILABLE",
                message="Verified dashboard evidence is unavailable.",
            ) from exc
        request.state.response_hash = hash_json(payload)
        return payload

    async def predict(
        request: Request,
        body: PredictionRequest,
    ) -> PredictionResponse:
        if body.api_version != PREDICTION_API_VERSION:
            raise PredictionAPIError(
                status_code=422,
                code="API_VERSION_MISMATCH",
                message="api_version must be 1.0.0.",
            )
        artifact = await _artifact_or_error(request)
        service = ProductionPredictionService(artifact)
        names = tuple(item.name for item in body.features)
        try:
            values = tuple(
                _decimal(item.value) for item in body.features
            )
            result = service.predict(
                prediction_timestamp=body.prediction_timestamp,
                feature_names=names,
                feature_values=values,
                schema_hash=body.schema_hash,
            )
        except PredictionValidationError as exc:
            raise PredictionAPIError(
                status_code=422,
                code=exc.code,
                message=exc.message,
            ) from exc
        except ValueError as exc:
            raise PredictionAPIError(
                status_code=422,
                code="FEATURE_VALUE_INVALID",
                message="Every feature value must be a finite decimal string.",
            ) from exc
        inference_timestamp = datetime.now(timezone.utc)
        payload = PredictionResponse(
            api_version=PREDICTION_API_VERSION,
            prediction_timestamp=result.prediction_timestamp,
            inference_timestamp=inference_timestamp,
            target_name="forward_log_return",
            target_version=artifact.target_version,
            horizon_observations=5,
            predicted_forward_log_return=format(
                result.predicted_forward_return,
                "f",
            ),
            predicted_float_hex=result.predicted_float_hex,
            prediction_hash=result.prediction_hash,
            feature_vector_hash=result.feature_vector_hash,
            schema_hash=result.schema_hash,
            artifact_identifier=artifact.artifact_id,
            artifact_sha256=artifact.artifact_sha256,
            configuration_hash=artifact.configuration_hash,
        )
        request.state.prediction_generated = True
        request.state.prediction_hash = result.prediction_hash
        request.state.schema_hash = result.schema_hash
        response_evidence = payload.model_dump(mode="json")
        response_evidence.pop("inference_timestamp")
        request.state.response_hash = hash_json(response_evidence)
        logger.info(
            "Prediction generated.",
            extra={
                "artifact_id": str(artifact.artifact_id),
                "prediction_hash": result.prediction_hash,
                "request_path": request.url.path,
                "http_method": request.method,
                "status_code": 200,
            },
        )
        return payload

    for prefix, include_in_schema in (
        ("/api/v1", True),
        ("", False),
    ):
        app.add_api_route(
            f"{prefix}/health",
            health,
            methods=["GET"],
            include_in_schema=include_in_schema,
        )
        app.add_api_route(
            f"{prefix}/version",
            version,
            methods=["GET"],
            include_in_schema=include_in_schema,
        )
        app.add_api_route(
            f"{prefix}/model",
            model,
            methods=["GET"],
            include_in_schema=include_in_schema,
        )
        app.add_api_route(
            f"{prefix}/metrics",
            metrics,
            methods=["GET"],
            include_in_schema=include_in_schema,
        )
        app.add_api_route(
            f"{prefix}/resources",
            resources,
            methods=["GET"],
            include_in_schema=include_in_schema,
        )
        app.add_api_route(
            f"{prefix}/predict",
            predict,
            methods=["POST"],
            response_model=PredictionResponse,
            include_in_schema=include_in_schema,
        )
        app.add_api_route(
            f"{prefix}/dashboard",
            dashboard,
            methods=["GET"],
            include_in_schema=include_in_schema,
        )
    return app


async def _database_artifact_provider() -> LoadedProductionArtifact:
    async with session_factory() as session:
        return await load_production_artifact(session)


async def _database_audit_writer(audit: PredictionAPIAudit) -> UUID:
    async with session_factory() as session:
        return await persist_prediction_api_audit(session, audit)


async def _database_dashboard_provider() -> dict[str, Any]:
    async with session_factory() as session:
        return await load_dashboard_snapshot(session)


async def _artifact_or_error(
    request: Request,
) -> LoadedProductionArtifact:
    try:
        artifact = await request.app.state.artifact_provider()
    except Exception as exc:
        raise PredictionAPIError(
            status_code=503,
            code="ARTIFACT_UNAVAILABLE",
            message="The verified production artifact is unavailable.",
        ) from exc
    request.state.artifact_id = artifact.artifact_id
    request.state.artifact_sha256 = artifact.artifact_sha256
    request.state.configuration_hash = artifact.configuration_hash
    return artifact


def _decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal.") from exc
    if not parsed.is_finite():
        raise ValueError("Non-finite decimal.")
    return parsed


def _content_length(request: Request) -> int | None:
    raw = request.headers.get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(value, 0)


def _error_payload(
    *,
    code: str,
    message: str,
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "api_version": PREDICTION_API_VERSION,
            "details": details,
        }
    }
