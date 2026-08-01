"""ASGI request tracing, Prometheus metrics, and operational health."""

from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


HealthCheck = Callable[[], Awaitable[bool]]
REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
CORRELATION_ID: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_TRACE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REQUESTS = Counter(
    "alphalens_http_requests_total",
    "AlphaLens HTTP requests",
    ("method", "path", "status"),
)
_LATENCY = Histogram(
    "alphalens_http_request_duration_seconds",
    "AlphaLens HTTP request latency",
    ("method", "path"),
)


def install_observability(
    app: FastAPI,
    *,
    readiness_checks: Mapping[str, HealthCheck],
    metrics_enabled: bool,
) -> None:
    """Install infrastructure-only middleware and operational endpoints."""

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = _trace_identifier(request.headers.get("X-Request-ID"))
        correlation_id = _trace_identifier(
            request.headers.get("X-Correlation-ID"), fallback=request_id
        )
        request_token = REQUEST_ID.set(request_id)
        correlation_token = CORRELATION_ID.set(correlation_id)
        started = perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            elapsed = max(perf_counter() - started, 0)
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            _REQUESTS.labels(request.method, path, status).inc()
            _LATENCY.labels(request.method, path).observe(elapsed)
            REQUEST_ID.reset(request_token)
            CORRELATION_ID.reset(correlation_token)

    @app.get("/health/liveness", include_in_schema=False)
    async def liveness() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/readiness", include_in_schema=False)
    async def readiness() -> JSONResponse:
        results: dict[str, str] = {}
        for name in sorted(readiness_checks):
            try:
                results[name] = "ready" if await readiness_checks[name]() else "failed"
            except Exception:
                results[name] = "failed"
        ready = all(value == "ready" for value in results.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "unavailable", "checks": results},
        )

    if metrics_enabled:

        @app.get("/metrics/prometheus", include_in_schema=False)
        async def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _trace_identifier(value: str | None, *, fallback: str | None = None) -> str:
    if value is not None and _TRACE_PATTERN.fullmatch(value):
        return value
    if fallback is not None:
        return fallback
    return uuid4().hex
