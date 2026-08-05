"""Versioned contract-driven read API for Opportunity Intelligence."""

from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.opportunity_intelligence.domain import (
    DashboardItem,
    MarketScope,
    OpportunityStance,
)
from app.opportunity_intelligence.repositories import (
    ContractViolationError,
    DashboardProjectionRepository,
    EntityAsOfQuery,
    EntityId,
    EntityNotFoundError,
    OpportunityDetailRepository,
    MarketSnapshotRepository,
    RepositoryError,
    RuntimeGovernanceRepository,
    ScopedRepositoryQuery,
    StorageUnavailableError,
    ValidationError,
    VersionConflictError,
)


OPPORTUNITY_API_VERSION = "1.0.0"
DEFAULT_MVP_INSTRUMENT = "BTCUSDT"
DEFAULT_MVP_TIMEFRAME = "5m"
Clock = Callable[[], datetime]


def create_opportunity_intelligence_app(
    dashboard_repository: DashboardProjectionRepository,
    detail_repository: OpportunityDetailRepository,
    governance_repository: RuntimeGovernanceRepository | None = None,
    market_repository: MarketSnapshotRepository | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    """Create the read-only API with repository ports supplied by the caller."""
    app = FastAPI(
        title="AlphaLens Opportunity Intelligence API",
        version=OPPORTUNITY_API_VERSION,
        openapi_url="/api/v1/openapi.json",
        docs_url=None,
        redoc_url=None,
    )
    current_time = clock or _utc_now

    @app.exception_handler(RequestValidationError)
    async def request_validation_failure(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del request
        return _error_response(422, "request.invalid", str(error))

    @app.exception_handler(RepositoryError)
    async def repository_failure(
        request: Request,
        error: RepositoryError,
    ) -> JSONResponse:
        del request
        return _repository_error_response(error)

    @app.get("/api/v1/opportunities", response_model=dict[str, object])
    async def list_opportunities(
        instrument: Annotated[str, Query(min_length=1)],
        timeframe: Annotated[str, Query(min_length=1)],
        as_of: datetime,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        cursor: str | None = None,
        stance: OpportunityStance | None = None,
        search: str | None = None,
        sort: str = "canonical.rank",
    ) -> dict[str, object]:
        if sort != "canonical.rank":
            raise ValidationError("Unsupported sort; use canonical.rank.")
        scope = MarketScope(instrument=instrument, timeframe=timeframe)
        page = await dashboard_repository.get_latest(
            ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=1)
        )
        filtered = _filter_items(page.items, stance=stance, search=search)
        offset = _cursor_offset(cursor)
        items = filtered[offset : offset + limit]
        next_offset = offset + len(items)
        payload = page.to_dict()
        payload["items"] = tuple(item.to_dict() for item in items)
        payload["applied_filters"] = _applied_filters(stance, search)
        payload["sort"] = sort
        payload["next_cursor"] = (
            str(next_offset) if next_offset < len(filtered) else None
        )
        payload.pop("previous_cursor", None)
        return _success(payload)

    @app.get("/opportunities", response_model=dict[str, object])
    async def list_mvp_opportunities(
        instrument: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_INSTRUMENT,
        timeframe: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_TIMEFRAME,
        as_of: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        cursor: str | None = None,
        stance: OpportunityStance | None = None,
        search: str | None = None,
        sort: str = "canonical.rank",
    ) -> dict[str, object]:
        try:
            return await list_opportunities(
                instrument=instrument,
                timeframe=timeframe,
                as_of=_resolve_as_of(as_of, current_time),
                limit=limit,
                cursor=cursor,
                stance=stance,
                search=search,
                sort=sort,
            )
        except EntityNotFoundError:
            return _success(
                {
                    "contract_version": OPPORTUNITY_API_VERSION,
                    "scope": {
                        "instrument": instrument,
                        "timeframe": timeframe,
                    },
                    "items": (),
                    "applied_filters": _applied_filters(stance, search),
                    "sort": sort,
                    "coverage_status": "unavailable",
                    "partial_failures": (),
                }
            )

    @app.get(
        "/api/v1/opportunities/{opportunity_id}",
        response_model=dict[str, object],
    )
    async def get_opportunity_detail(
        opportunity_id: str,
        as_of: datetime,
    ) -> dict[str, object]:
        detail = await detail_repository.get_current(
            EntityAsOfQuery(EntityId(opportunity_id), as_of)
        )
        return _success(detail.to_dict())

    @app.get(
        "/opportunities/{opportunity_id}",
        response_model=dict[str, object],
    )
    async def get_mvp_opportunity_detail(
        opportunity_id: str,
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        return await get_opportunity_detail(
            opportunity_id,
            _resolve_as_of(as_of, current_time),
        )

    @app.get("/markets/live", response_model=dict[str, object])
    async def get_live_market(
        instrument: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_INSTRUMENT,
        timeframe: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_TIMEFRAME,
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        if market_repository is None:
            raise StorageUnavailableError(
                "Live market snapshot repository is not configured."
            )
        try:
            snapshot = await market_repository.get_latest(
                ScopedRepositoryQuery(
                    scope=MarketScope(instrument=instrument, timeframe=timeframe),
                    as_of=_resolve_as_of(as_of, current_time),
                    limit=1,
                )
            )
        except EntityNotFoundError:
            resolved_as_of = _resolve_as_of(as_of, current_time)
            payload = {
                "contract_version": OPPORTUNITY_API_VERSION,
                "snapshot_id": "market.unavailable",
                "scope": {
                    "instrument": instrument,
                    "timeframe": timeframe,
                },
                "candles": (),
                "complete": False,
                "audit": {
                    "created_at": resolved_as_of.isoformat(),
                    "evidence_cutoff": resolved_as_of.isoformat(),
                    "available_at": resolved_as_of.isoformat(),
                    "result_hash": sha256(
                        f"{instrument}:{timeframe}:{resolved_as_of.isoformat()}".encode(
                            "utf-8",
                        )
                    ).hexdigest(),
                },
            }
            return _success(payload)

        return _success(snapshot.to_dict())

    @app.get("/health", response_model=dict[str, object])
    async def get_mvp_health() -> dict[str, object]:
        market_repository_configured = market_repository is not None
        data = {
            "status": "ready" if market_repository_configured else "degraded",
            "service": "alphalens-mvp-api",
            "api_version": OPPORTUNITY_API_VERSION,
            "read_only": True,
            "authentication_required": False,
            "components": {
                "market_snapshots": (
                    "configured" if market_repository_configured else "unavailable"
                ),
                "opportunity_dashboard": "configured",
                "opportunity_detail": "configured",
            },
        }
        return _success(data)

    @app.get(
        "/api/v1/opportunity-intelligence/health",
        response_model=dict[str, object],
    )
    async def get_runtime_health(
        instrument: Annotated[str, Query(min_length=1)],
        timeframe: Annotated[str, Query(min_length=1)],
        as_of: datetime,
    ) -> dict[str, object]:
        if governance_repository is None:
            raise StorageUnavailableError(
                "Runtime governance repository is not configured."
            )
        record = await governance_repository.get_latest(
            ScopedRepositoryQuery(
                scope=MarketScope(instrument=instrument, timeframe=timeframe),
                as_of=as_of,
                limit=1,
            )
        )
        return _success(record.to_dict())

    return app


def _filter_items(
    items: tuple[DashboardItem, ...],
    *,
    stance: OpportunityStance | None,
    search: str | None,
) -> tuple[DashboardItem, ...]:
    needle = search.casefold().strip() if search else None
    return tuple(
        item
        for item in items
        if (stance is None or item.stance is stance)
        and (
            needle is None
            or needle in item.scope.instrument.casefold()
            or needle in item.opportunity_id.casefold()
            or any(needle in code.casefold() for code in item.reason_codes)
        )
    )


def _applied_filters(
    stance: OpportunityStance | None,
    search: str | None,
) -> tuple[str, ...]:
    filters: list[str] = []
    if stance is not None:
        filters.append(f"stance:{stance.value}")
    if search:
        filters.append(f"search:{search.strip()}")
    return tuple(filters)


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except (TypeError, ValueError) as error:
        raise ValidationError("Cursor is invalid.") from error
    if offset < 0 or str(offset) != cursor:
        raise ValidationError("Cursor is invalid.")
    return offset


def _success(data: dict[str, object]) -> dict[str, object]:
    return {
        "contract_version": OPPORTUNITY_API_VERSION,
        "data": data,
        "response_hash": _response_hash(data),
    }


def _repository_error_response(error: RepositoryError) -> JSONResponse:
    if isinstance(error, EntityNotFoundError):
        return _error_response(404, "entity.not_found", str(error))
    if isinstance(error, VersionConflictError):
        return _error_response(409, "version.conflict", str(error))
    if isinstance(error, (ValidationError, ContractViolationError)):
        return _error_response(422, "contract.invalid", str(error))
    if isinstance(error, StorageUnavailableError):
        return _error_response(503, "storage.unavailable", "Storage unavailable.")
    return _error_response(500, "repository.failure", "Repository operation failed.")


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    payload = {
        "contract_version": OPPORTUNITY_API_VERSION,
        "error": {"code": code, "message": message},
    }
    payload["response_hash"] = _response_hash(payload)
    return JSONResponse(status_code=status, content=payload)


def _response_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_as_of(value: datetime | None, clock: Clock) -> datetime:
    resolved = value if value is not None else clock()
    if resolved.tzinfo is None or resolved.utcoffset() is None:
        raise ValidationError("As-of timestamp must be timezone-aware.")
    return resolved.astimezone(timezone.utc)
