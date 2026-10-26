"""Versioned contract-driven read API for Opportunity Intelligence."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Annotated

from decimal import Decimal

from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.opportunity_intelligence.domain import (
    DashboardItem,
    MarketScope,
    OpportunityStance,
    OutcomeRecord,
)
from app.opportunity_intelligence.repositories import (
    ContractViolationError,
    DashboardProjectionRepository,
    EntityAsOfQuery,
    EntityId,
    EntityNotFoundError,
    LifecycleRepository,
    OpportunityDetailRepository,
    OpportunityPlanRepository,
    MarketSnapshotRepository,
    OpportunityRepository,
    RepositoryError,
    RuntimeGovernanceRepository,
    ScopedRepositoryQuery,
    StorageUnavailableError,
    ValidationError,
    VersionConflictError,
)
from app.opportunity_intelligence.persistence import OutcomePostgreSQLRepository
from app.economic_analysis import EconomicAssumptions, calculate_economics
from app.thesis_intelligence import ThesisIntelligenceService


OPPORTUNITY_API_VERSION = "1.0.0"
DEFAULT_MVP_INSTRUMENT = "BTCUSDT"
DEFAULT_MVP_TIMEFRAME = "5m"
_ACTIVE_MAX_AGE_MINUTES: int = 10
Clock = Callable[[], datetime]


def create_opportunity_intelligence_app(
    dashboard_repository: DashboardProjectionRepository,
    detail_repository: OpportunityDetailRepository,
    plans_repository: OpportunityPlanRepository | None = None,
    governance_repository: RuntimeGovernanceRepository | None = None,
    market_repository: MarketSnapshotRepository | None = None,
    lifecycle_repository: LifecycleRepository | None = None,
    outcome_repository: OutcomePostgreSQLRepository | None = None,
    opportunity_repository: OpportunityRepository | None = None,
    thesis_service: ThesisIntelligenceService | None = None,
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
        if thesis_service is not None:
            return await _thesis_page(
                thesis_service=thesis_service,
                scope=scope,
                as_of=as_of,
                limit=limit,
                cursor=cursor,
                stance=stance,
                search=search,
            )
        try:
            page = await dashboard_repository.get_latest(
                ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=1)
            )
        except EntityNotFoundError:
            if opportunity_repository is None:
                raise
            return await _assessment_page(
                opportunity_repository=opportunity_repository,
                scope=scope,
                as_of=as_of,
                limit=limit,
                cursor=cursor,
                stance=stance,
                search=search,
            )
        filtered = _filter_items(page.items, stance=stance, search=search)
        filtered = _filter_active_items(filtered, as_of=as_of)
        offset = _cursor_offset(cursor)
        items = filtered[offset : offset + limit]
        next_offset = offset + len(items)
        payload = page.to_dict()
        payload["items"] = tuple(item.to_dict() for item in items)
        if plans_repository is not None:
            resolved_items: list[dict[str, object]] = []
            for item in payload["items"]:
                resolved_items.append(
                    await _overlay_plan_presence(
                        item,
                        plans_repository=plans_repository,
                        as_of=as_of,
                    )
                )
            payload["items"] = tuple(resolved_items)
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
        "/api/v1/opportunities/assessments",
        response_model=dict[str, object],
    )
    async def list_assessed_opportunities(
        instrument: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_INSTRUMENT,
        timeframe: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_TIMEFRAME,
        as_of: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        cursor: str | None = None,
    ) -> dict[str, object]:
        """Expose persisted assessments before model-dependent ranking."""
        if opportunity_repository is None:
            raise StorageUnavailableError(
                "Opportunity assessment repository is not configured."
            )
        resolved_as_of = _resolve_as_of(as_of, current_time)
        scope = MarketScope(instrument=instrument, timeframe=timeframe)
        page = await opportunity_repository.get_by_scope(
            ScopedRepositoryQuery(
                scope=scope,
                as_of=resolved_as_of,
                limit=limit,
                cursor=cursor,
            )
        )
        return _success(
            {
                "contract_version": OPPORTUNITY_API_VERSION,
                "scope": {
                    "instrument": instrument,
                    "timeframe": timeframe,
                },
                "as_of": resolved_as_of.isoformat(),
                "items": tuple(_serialize_assessment(item) for item in page.items),
                "next_cursor": page.next_cursor,
                "projection_status": "assessment_only",
                "model_score_status": "unavailable_without_approved_artifact",
                "notification_status": "intent_persistence_only",
            }
        )

    @app.get(
        "/api/v1/opportunities/assessments/{opportunity_id}",
        response_model=dict[str, object],
    )
    async def get_assessed_opportunity(
        opportunity_id: str,
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        if opportunity_repository is None:
            raise StorageUnavailableError(
                "Opportunity assessment repository is not configured."
            )
        resolved_as_of = _resolve_as_of(as_of, current_time)
        opportunity = await opportunity_repository.get_current(
            EntityAsOfQuery(EntityId(opportunity_id), resolved_as_of)
        )
        return _success(
            {
                "projection_status": "assessment_only",
                "model_score_status": "unavailable_without_approved_artifact",
                "notification_status": "intent_persistence_only",
                "opportunity": opportunity.to_dict(),
            }
        )

    @app.get(
        "/api/v1/opportunities/history",
        response_model=dict[str, object],
    )
    async def list_history(
        instrument: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_INSTRUMENT,
        timeframe: Annotated[str, Query(min_length=1)] = DEFAULT_MVP_TIMEFRAME,
        as_of: datetime | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
    ) -> dict[str, object]:
        if lifecycle_repository is None:
            raise StorageUnavailableError(
                "Lifecycle repository is not configured."
            )
        resolved_as_of = _resolve_as_of(as_of, current_time)
        scope = MarketScope(instrument=instrument, timeframe=timeframe)
        terminal_lifecycles = await lifecycle_repository.list_terminal_lifecycles(
            scope=scope,
            as_of=resolved_as_of,
            limit=limit,
        )
        items: list[dict[str, object]] = []
        for lc in terminal_lifecycles:
            items.append({
                "opportunity_id": lc.opportunity_id,
                "scope": {"instrument": lc.scope.instrument, "timeframe": lc.scope.timeframe},
                "direction": lc.direction.value,
                "lifecycle_state": lc.current_state.value,
                "available_at": lc.audit.available_at.isoformat(),
                "event_count": len(lc.events),
            })
        payload = {
            "contract_version": OPPORTUNITY_API_VERSION,
            "scope": {"instrument": instrument, "timeframe": timeframe},
            "items": tuple(items),
            "as_of": resolved_as_of.isoformat(),
        }
        return _success(payload)

    @app.get(
        "/api/v1/opportunities/{opportunity_id}/economics",
        response_model=dict[str, object],
    )
    async def get_opportunity_economics(
        opportunity_id: str,
        as_of: datetime | None = None,
        position_notional: Decimal = Decimal("500"),
        currency: str = "INR",
        fx_to_usd: Decimal | None = None,
        entry_fee_bps: Decimal = Decimal("0"),
        exit_fee_bps: Decimal = Decimal("0"),
        entry_slippage_bps: Decimal = Decimal("0"),
        exit_slippage_bps: Decimal = Decimal("0"),
        instrument_semantics: str = "spot",
    ) -> dict[str, object]:
        """Calculate an explicit scenario without persisting or inventing a trade."""
        if plans_repository is None:
            raise StorageUnavailableError("Opportunity plan repository is not configured.")
        resolved_as_of = _resolve_as_of(as_of, current_time)
        plan = await plans_repository.get_latest_for_opportunity(
            EntityAsOfQuery(EntityId(opportunity_id), resolved_as_of)
        )
        result = calculate_economics(
            direction=plan.direction.value,
            entry_lower=plan.entry_zone.lower,
            entry_upper=plan.entry_zone.upper,
            target_price=plan.targets[0].price,
            invalidation_price=plan.invalidation_price,
            assumptions=EconomicAssumptions(
                position_notional=position_notional,
                currency=currency,
                fx_to_usd=fx_to_usd,
                entry_fee_bps=entry_fee_bps,
                exit_fee_bps=exit_fee_bps,
                entry_slippage_bps=entry_slippage_bps,
                exit_slippage_bps=exit_slippage_bps,
                instrument_semantics=instrument_semantics,
            ),
        )
        return _success({
            "opportunity_id": opportunity_id,
            "analysis": result.to_dict(),
            "predictive_status": "unavailable_without_approved_artifact",
            "actual_execution_status": "not_executed",
        })

    @app.get(
        "/api/v1/opportunities/{opportunity_id}",
        response_model=dict[str, object],
    )
    async def get_opportunity_detail(
        opportunity_id: str,
        as_of: datetime,
    ) -> dict[str, object]:
        logical_id = (
            opportunity_id.removesuffix(".v1")
            if opportunity_id.endswith(".v1")
            else opportunity_id
        )
        detail = await detail_repository.get_current(
            EntityAsOfQuery(EntityId(logical_id), as_of)
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

    @app.get("/api/v1/theses", response_model=dict[str, object])
    async def list_theses(
        instrument: str = DEFAULT_MVP_INSTRUMENT,
        timeframe: str = DEFAULT_MVP_TIMEFRAME,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict[str, object]:
        if thesis_service is None:
            raise StorageUnavailableError("Thesis service is not configured.")
        items = await thesis_service.list(
            instrument=instrument,
            timeframe=timeframe,
            limit=limit,
        )
        return _success({
            "scope": {"instrument": instrument, "timeframe": timeframe},
            "items": jsonable_encoder(items),
            "matching_policy": "diagnostic.exact_geometry.v1",
            "predictive_status": "unavailable_without_approved_artifact",
        })

    @app.get("/api/v1/theses/{thesis_id}", response_model=dict[str, object])
    async def get_thesis(thesis_id: str) -> dict[str, object]:
        if thesis_service is None:
            raise StorageUnavailableError("Thesis service is not configured.")
        item = await thesis_service.get(thesis_id)
        if item is None:
            raise EntityNotFoundError(thesis_id)
        return _success({
            "thesis": jsonable_encoder(item),
            "matching_policy": "diagnostic.exact_geometry.v1",
            "predictive_status": "unavailable_without_approved_artifact",
            "extension_status": "diagnostic_only_not_validated",
        })

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
            "market_scope": {
                "exchange": "binance",
                "instrument": DEFAULT_MVP_INSTRUMENT,
                "timeframe": DEFAULT_MVP_TIMEFRAME,
                "candle_state": "closed",
            },
            # This endpoint describes the opportunity-read surface. It must
            # not imply that an approved model artifact or external delivery
            # channel exists merely because repositories are configured.
            "model_score_status": "unavailable_without_approved_artifact",
            "notification_status": "intent_persistence_only",
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

    @app.get(
        "/api/v1/outcomes/{opportunity_id}",
        response_model=dict[str, object],
    )
    async def get_outcome(
        opportunity_id: str,
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        """Read-only inspection of a persisted outcome record.

        Exposes only data that outcome resolution has actually persisted from
        real market candles. This endpoint cannot create or modify outcomes.
        """
        if outcome_repository is None:
            raise StorageUnavailableError(
                "Outcome repository is not configured."
            )
        resolved_as_of = _resolve_as_of(as_of, current_time)
        record = await outcome_repository.get_by_opportunity(
            EntityAsOfQuery(EntityId(opportunity_id), resolved_as_of)
        )
        return _success(_serialize_outcome(record))

    return app


def _serialize_outcome(record: OutcomeRecord) -> dict[str, object]:
    """Convert an OutcomeRecord into a JSON-serializable read-only payload."""
    from decimal import Decimal as _Decimal

    def _field(value):
        if isinstance(value, _Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    return {
        "outcome_id": record.outcome_id,
        "opportunity_id": record.opportunity_id,
        "opportunity_version_id": record.opportunity_version_id,
        "lifecycle_id": record.lifecycle_id,
        "outcome": record.outcome.value,
        "direction": record.direction,
        "reference_price": _field(record.reference_price),
        "entry_zone_lower": _field(record.entry_zone_lower),
        "entry_zone_upper": _field(record.entry_zone_upper),
        "invalidation_price": _field(record.invalidation_price),
        "target_price": _field(record.target_price),
        "signal_timestamp": _field(record.signal_timestamp),
        "outcome_interval_start": _field(record.outcome_interval_start),
        "outcome_interval_end": _field(record.outcome_interval_end),
        "resolved_at": _field(record.resolved_at),
        "candles_evaluated": record.candles_evaluated,
        "first_touch_price": _field(record.first_touch_price),
        "first_touch_timestamp": _field(record.first_touch_timestamp),
        "first_touch_candle_index": record.first_touch_candle_index,
        "entry_reached": record.entry_reached,
        "entry_timestamp": _field(record.entry_timestamp),
        "entry_candle_index": record.entry_candle_index,
        "first_barrier": record.first_barrier,
        "resolution_reason": record.resolution_reason,
        "data_quality": record.data_quality,
        "risk_reward": _field(record.risk_reward),
        "exclusion_reason": record.exclusion_reason,
    }


def _serialize_assessment(opportunity) -> dict[str, object]:
    """Serialize genuine persisted assessment data without ranking semantics."""
    payload = opportunity.to_dict()
    payload.update(
        {
            "projection_status": "assessment_only",
            "model_score_status": "unavailable_without_approved_artifact",
            "notification_status": "intent_persistence_only",
        }
    )
    return payload


async def _assessment_page(
    *,
    opportunity_repository: OpportunityRepository,
    scope: MarketScope,
    as_of: datetime,
    limit: int,
    cursor: str | None,
    stance: OpportunityStance | None,
    search: str | None,
) -> dict[str, object]:
    """Build the public feed fallback without creating ranking semantics."""
    page = await opportunity_repository.get_by_scope(
        ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=500)
    )
    items = [
        _assessment_dashboard_item(item)
        for item in page.items
        if (stance is None or item.stance is stance)
        and (
            not search
            or search.casefold().strip() in item.opportunity_id.casefold()
            or search.casefold().strip() in item.scope.instrument.casefold()
        )
    ]
    offset = _cursor_offset(cursor)
    selected = items[offset : offset + limit]
    next_offset = offset + len(selected)
    return _success(
        {
            "contract_version": OPPORTUNITY_API_VERSION,
            "scope": {
                "instrument": scope.instrument,
                "timeframe": scope.timeframe,
            },
            "as_of": as_of.isoformat(),
            "generated_at": as_of.isoformat(),
            "items": tuple(selected),
            "applied_filters": _applied_filters(stance, search),
            "sort": "canonical.assessment_available_at",
            "next_cursor": str(next_offset) if next_offset < len(items) else None,
            "freshness_status": "historical_replay",
            "coverage_status": "assessment_only_model_unavailable",
            "partial_failures": (),
            "projection_status": "assessment_only",
            "model_score_status": "unavailable_without_approved_artifact",
            "notification_status": "intent_persistence_only",
        }
    )


def _assessment_dashboard_item(opportunity) -> dict[str, object]:
    payload = opportunity.to_dict()
    audit = payload["audit"]
    return {
        "opportunity_id": payload["opportunity_id"],
        "opportunity_version_id": payload["opportunity_version_id"],
        "scope": payload["scope"],
        "stance": payload["stance"],
        "lifecycle_state": "ASSESSMENT_ONLY",
        "evidence_cutoff": audit["evidence_cutoff"],
        "available_at": audit["available_at"],
        "freshness_state": "historical_replay",
        "rank": None,
        "reason_codes": payload["reason_codes"],
        "has_plan": payload.get("plan") is not None,
        "plan": payload.get("plan"),
        "limitations": payload["limitations"],
        "detail_reference": payload["opportunity_version_id"],
        "quality_score": None,
        "projection_status": "assessment_only",
        "model_score_status": "unavailable_without_approved_artifact",
        "notification_status": "intent_persistence_only",
    }


async def _thesis_page(
    *,
    thesis_service: ThesisIntelligenceService,
    scope: MarketScope,
    as_of: datetime,
    limit: int,
    cursor: str | None,
    stance: OpportunityStance | None,
    search: str | None,
) -> dict[str, object]:
    """Project one primary card per diagnostic detection family."""
    theses = await thesis_service.list(
        instrument=scope.instrument,
        timeframe=scope.timeframe,
        limit=500,
    )
    selected: list[dict[str, object]] = []
    for thesis in theses:
        if stance is not None and thesis["direction"] != stance.value:
            continue
        if search and search.casefold() not in str(thesis["thesis_id"]).casefold():
            continue
        available_at = thesis["original_created_at"]
        if available_at > as_of:
            continue
        plan = thesis.get("original_plan")
        selected.append({
            "opportunity_id": thesis["original_opportunity_id"],
            "opportunity_version_id": thesis["original_opportunity_version_id"],
            "scope": {"instrument": scope.instrument, "timeframe": scope.timeframe},
            "stance": thesis["direction"],
            "lifecycle_state": thesis["current_state"],
            "evidence_cutoff": available_at.isoformat(),
            "available_at": available_at.isoformat(),
            "freshness_state": "CURRENT",
            "rank": None,
            "reason_codes": [
                "thesis.primary_detection_family",
                f"thesis.related_assessments.{thesis['related_assessment_count']}",
            ],
            "has_plan": plan is not None,
            "limitations": [
                "model_score_unavailable_without_approved_artifact",
                "diagnostic_matching_policy_not_predictive_validation",
            ] + (["multiple_assessments_require_review"] if thesis["review_cluster_status"] != "SINGLE_THESIS" else []),
            "detail_reference": thesis["original_opportunity_id"],
            "projection_status": "assessment_only",
            "model_score_status": "unavailable_without_approved_artifact",
            "notification_status": "intent_persistence_only",
            "thesis_id": thesis["thesis_id"],
            "related_thesis_ids": thesis["related_thesis_ids"],
            "related_assessment_count": thesis["related_assessment_count"],
            "review_cluster_status": thesis["review_cluster_status"],
            "plan": plan,
        })
    offset = _cursor_offset(cursor)
    page = selected[offset : offset + limit]
    next_offset = offset + len(page)
    return _success({
        "contract_version": OPPORTUNITY_API_VERSION,
        "scope": {"instrument": scope.instrument, "timeframe": scope.timeframe},
        "as_of": as_of.isoformat(),
        "generated_at": as_of.isoformat(),
        "items": page,
        "applied_filters": _applied_filters(stance, search),
        "sort": "thesis.original_created_at",
        "next_cursor": str(next_offset) if next_offset < len(selected) else None,
        "freshness_status": "live_observation",
        "coverage_status": "thesis_primary_assessment_only",
        "partial_failures": (),
        "projection_status": "assessment_only",
        "model_score_status": "unavailable_without_approved_artifact",
        "notification_status": "intent_persistence_only",
    })


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


def _filter_active_items(
    items: tuple[DashboardItem, ...],
    *,
    as_of: datetime,
) -> tuple[DashboardItem, ...]:
    """Exclude opportunities whose signal age exceeds the active horizon."""
    max_age = timedelta(minutes=_ACTIVE_MAX_AGE_MINUTES)
    return tuple(
        item
        for item in items
        if as_of - item.evidence_cutoff < max_age
    )


async def _overlay_plan_presence(
    item: dict[str, object],
    *,
    plans_repository: OpportunityPlanRepository,
    as_of: datetime,
) -> dict[str, object]:
    """Mark a dashboard item as having a persisted plan when one exists."""
    query = EntityAsOfQuery(EntityId(str(item["opportunity_id"])), as_of)
    try:
        await plans_repository.get_latest_for_opportunity(query)
    except EntityNotFoundError:
        return {**item, "has_plan": False}
    return {**item, "has_plan": True}


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
