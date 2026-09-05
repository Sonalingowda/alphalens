"""Production entry point for the read-only live prediction API."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
import logging
import random
from typing import Sequence, Callable
from dataclasses import dataclass

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
    OutcomePostgreSQLRepository,
    RuntimeGovernancePostgreSQLRepository,
)
from app.opportunity_intelligence.repositories import RepositoryError
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.features.contracts import FeatureValue, FeatureDependencyInput, FeatureComputationError
from app.features.intraday_pipeline import _verify_prefix_invariance
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


class _PrefixInvarianceCheckResult:
    """Result of a single prefix invariance check run."""

    violations: int = 0
    features_checked: int = 0
    candles_sampled: int = 0


_pipeline_health = _PipelineHealth()
_pipeline_tasks: set[asyncio.Task] = set()


async def _run_periodic_prefix_invariance_check(
    stop_event: asyncio.Event,
    *,
    candles_sample_size: int = 20,
    check_interval_seconds: int = 3600,
) -> _PrefixInvarianceCheckResult:
    """Background task that runs prefix invariance checks on random recent candle samples.

    Runs once per hour (default) as a non-blocking background task. On each cycle:
    1. Samples ``candles_sample_size`` recent candles from the market data pipeline.
    2. For each feature in the registry, verifies prefix invariance on increasing prefix lengths.
    3. Logs any violations (feature computation depending on future/non-prefix candles).
    4. Sleeps until the next cycle, respecting ``stop_event`` for graceful shutdown.

    This is additive — it does not affect the hot path (the main pipeline call site
    remains off-by-default per ``ALPHALENS_FEATURE_INVARIANCE_CHECK``).
    """
    from app.features.registry import INTRADAY_FEATURE_REGISTRY
    from app.features.contracts import FeatureValue, FeatureDependencyInput

    result = _PrefixInvarianceCheckResult()
    logger = logging.getLogger("alphalens.prefix_invariance_check")

    cycle_id = 0
    while not stop_event.is_set():
        try:
            cycle_id += 1
            # Sample recent candles: query recent feature snapshot values
            async with session_factory() as session:
                from app.opportunity_intelligence.persistence import (
                    FeatureSnapshotValuePostgreSQLRepository,
                )
                repo = FeatureSnapshotValuePostgreSQLRepository(session_factory=session)
                recent_values = await repo.query_recent(limit=candles_sample_size * 2)

            if len(recent_values) < candles_sample_size:
                logger.warning(
                    "Insufficient recent candles for prefix invariance check: got %d, need %d",
                    len(recent_values),
                    candles_sample_size,
                )
                await stop_event.wait(min(check_interval_seconds, 60))
                continue

            # Sort by timestamp and take the most recent `candles_sample_size`
            recent_values.sort(key=lambda v: v.candle_timestamp, reverse=True)
            sample_candles = recent_values[:candles_sample_size]
            result.candles_sampled += candles_sample_size

            # Sort chronologically (oldest first) for prefix computation
            sample_candles.sort(key=lambda v: v.candle_timestamp)

            # Verify prefix invariance for each feature in the registry
            for feature_meta in INTRADAY_FEATURE_REGISTRY.features:
                result.features_checked += 1
                try:
                    definition = feature_meta
                    # Compute feature values for the full sample (run in thread to avoid blocking event loop)
                    full_feature_values = await asyncio.to_thread(
                        _compute_feature_values_full, definition, tuple(sample_candles)
                    )

                    # Verify prefix invariance for each prefix length (run in thread)
                    for prefix_length in range(1, len(sample_candles) + 1):
                        prefix_candles = sample_candles[:prefix_length]
                        prefix_feature_values = await asyncio.to_thread(
                            _compute_feature_values_prefix, definition, tuple(prefix_candles)
                        )

                        # Determine prefix end timestamp
                        prefix_end = max(
                            (c.candle_timestamp for c in prefix_candles),
                            default=datetime.min.replace(tzinfo=timezone.utc),
                        )

                        # Filter full_feature_values to those at or before prefix_end
                        expected_for_prefix = tuple(
                            v
                            for v in full_feature_values
                            if v.candle_timestamp <= prefix_end
                        )

                        if prefix_feature_values != expected_for_prefix:
                            logger.error(
                                "Prefix invariance violation for feature %s "
                                "at prefix_length %d",
                                definition.identifier,
                                prefix_length,
                            )
                            result.violations += 1

                except Exception:
                    logger.exception(
                        "Error checking prefix invariance for feature %s",
                        feature_meta.identifier,
                    )

            # Sleep until next cycle, respecting stop_event
            await stop_event.wait(check_interval_seconds)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Unexpected error in prefix invariance check cycle %d", cycle_id
            )
            await asyncio.sleep(min(check_interval_seconds, 60))

    return result


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
    outcome_repository=OutcomePostgreSQLRepository(session_factory),
)
_mvp_paths = {
    "/api/v1/opportunities",
    "/api/v1/opportunities/{opportunity_id}",
    "/api/v1/opportunities/history",
    "/api/v1/opportunity-intelligence/health",
    "/api/v1/outcomes/{opportunity_id}",
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
    try:
        from app.market_configuration import get_default_scope
        from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
        from app.opportunity_intelligence.persistence import (
            FeatureSnapshotPostgreSQLRepository,
            MarketContextPostgreSQLRepository,
        )
        from app.runtime_detection.service import (
            _REQUIRED_FEATURES,
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
        features = await feature_repo.get_latest(
            ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=1)
        )
        context = await context_repo.get_latest(
            ScopedRepositoryQuery(scope=scope, as_of=as_of, limit=1)
        )
        inputs = await _runtime_pipeline._pipeline.detection._load_persisted_inputs(
            market, features, context
        )
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
        return payload
    except Exception as exc:  # noqa: BLE001 - diagnostic surface
        return {"diagnose_error": repr(exc), "error_type": type(exc).__name__}


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
                            lifecycle,
                            outcome_service,
                            plan_repo,
                            outcome_repo,
                            lifecycle_service,
                            lifecycle_repo,
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
    lifecycle_service,
    lifecycle_repo,
) -> None:
    """Best-effort outcome resolution for one expired lifecycle.

    Uses the first lifecycle event (DETECTED) as the signal timestamp, NOT the
    EXPIRED event. Resolution only runs when the opportunity has not already
    been resolved (guards against duplicate OutcomeRecords and duplicate
    lifecycle RESOLVED events), and never for future-valid opportunities.

    This path deliberately operates only on lifecycles returned by the
    staleness sweep (RANKED -> EXPIRED in the same pass), so pre-existing
    EXPIRED historical lifecycles from earlier deployments are NOT rewritten.
    """
    from app.opportunity_intelligence.domain import LifecycleState
    from app.opportunity_intelligence.repositories.queries import (
        EntityAsOfQuery,
        EntityId,
    )

    signal_event = lifecycle.events[0]
    opportunity_id = lifecycle.opportunity_id

    # Idempotency: if the outcome was already persisted, do not recreate it and
    # do not append another RESOLVED lifecycle event.
    try:
        existing = await outcome_repo.get_by_opportunity(
            EntityAsOfQuery(
                entity_id=EntityId(opportunity_id),
                as_of=datetime.now(timezone.utc),
            )
        )
    except Exception:
        existing = None
    if existing is not None:
        logger.info(
            "outcome_resolution_skipped_already_resolved opportunity_id=%s",
            opportunity_id,
        )
        return
    if lifecycle.current_state == LifecycleState.RESOLVED:
        logger.info(
            "outcome_resolution_skipped_already_resolved_lifecycle opportunity_id=%s",
            opportunity_id,
        )
        return

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
        # Defensive fallback: derive the resolution horizon from the established
        # 10-minute active-expiration policy when a plan carries no validity
        # window. New V1.1/V2 plans always persist valid_until.
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

    try:
        await lifecycle_service.resolve_outcome(
            lifecycle,
            outcome_record.outcome,
            datetime.now(timezone.utc),
        )
    except Exception:
        logger.exception(
            "outcome_lifecycle_resolution_failed opportunity_id=%s",
            opportunity_id,
        )
    else:
        try:
            await lifecycle_repo.save(lifecycle)
        except Exception:
            logger.exception(
                "outcome_lifecycle_save_failed opportunity_id=%s",
                opportunity_id,
            )




async def _supervise_warmup(
    stop_event: asyncio.Event,
    service: LiveMarketIngestionService,
    *,
    interval_seconds: int = 7200,
    limit: int = 1000,
    sleep_fn: Callable[[float], None] = asyncio.sleep,
) -> None:
    """Periodic warmup history supervisor.

    Calls service.warmup_history_with_retry() every interval_seconds (default 2 hours    to keep market_data_candles current and prevent
    candle-history gaps.  Idempotent: DuplicateEntityError from the
    repository is caught and skipped, so repeated calls are safe.

    Guarantees:
    * stop_event set -> the loop stops without restarting (graceful
      shutdown).
    * Only one warmup cycle runs at a time.
    * Bounded exponential backoff on transient failures; after 3 consecutive
      failures the loop sleeps for interval_seconds before retrying.

    This is safe to call frequently because warmup_history_with_retry()
    always resets _warmup_history_fetched before each attempt, so the
    underlying warmup_history() will always execute (unlike the bare
    warmup_history() which returns 0 after the first successful run).
    """
    backoff = 15.0
    max_backoff = 60.0
    while not stop_event.is_set():
        try:
            await service.warmup_history_with_retry(
                attempts=3,
                backoff_seconds=backoff,
            )
            backoff = 15.0  # reset backoff on success
            await sleep_fn(interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(
                "warmup supervisor cycle failed: %s; retrying in %0.1fs",
                type(e).__name__,
                backoff,
            )
            backoff = min(backoff * 2, max_backoff)
            await sleep_fn(backoff)

async def _supervise_ingestion(
    stop_event: asyncio.Event,
    service: LiveMarketIngestionService,
    *,
    backoff_initial_seconds: float = 1.0,
    backoff_max_seconds: float = 30.0,
    max_restarts: int | None = None,
) -> None:
    """Keep live market ingestion alive across unexpected failures.

    The ingestion loop is fail-closed and the WebSocket client only handles its
    own transport/timeout reconnect; an exception that escapes the client (e.g. a
    transient repository error surfaced from ``_persist``) must not silently
    terminate live processing forever.  On any unexpected exception we log the
    full traceback, wait with bounded exponential backoff, and restart exactly
    one ingestion loop.

    Guarantees:
    * ``stop_event`` set -> the loop stops without restarting (graceful shutdown).
    * ``asyncio.CancelledError`` propagates (no infinite restart on cancellation).
    * only one ingestion loop runs at a time (the previous one has returned
      before the next is started), so there are never duplicate WebSocket
      connections or concurrent ingestion loops.
    """
    restarts = 0
    while not stop_event.is_set():
        try:
            await service.run(stop_event)
        except asyncio.CancelledError:
            raise
        except Exception:
            if stop_event.is_set():
                break
            restarts += 1
            if max_restarts is not None and restarts > max_restarts:
                logger.exception(
                    "ingestion_supervisor_giving_up restarts=%d", restarts
                )
                break
            delay = min(
                backoff_initial_seconds * (2 ** (restarts - 1)),
                backoff_max_seconds,
            )
            logger.exception(
                "ingestion_task_crashed restarting_in_seconds=%s restart=%d",
                delay,
                restarts,
            )
            await asyncio.sleep(delay)
    logger.info("ingestion_supervisor_stopped")


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
                _supervise_ingestion(stop_event, live_market_ingestion),
                name="alphalens-live-market-ingestion",
            )
            application.state.live_market_ingestion = live_market_ingestion
            application.state.live_market_ingestion_task = ingestion_task
            lifecycle_sweep_task = asyncio.create_task(
                _run_lifecycle_sweep(stop_event),
                name="alphalens-lifecycle-sweep",
            )
            application.state.lifecycle_sweep_task = lifecycle_sweep_task
            prefix_invariance_task = asyncio.create_task(
                _run_periodic_prefix_invariance_check(
                    stop_event,
                    candles_sample_size=50,
                    check_interval_seconds=3600,
                ),
                name="alphalens-prefix-invariance-check",
            )
            application.state.prefix_invariance_task = prefix_invariance_task
            warmup_task = asyncio.create_task(
                _supervise_warmup(stop_event, live_market_ingestion),
                name="alphalens-warmup-supervisor",
            )
            application.state.warmup_task = warmup_task
            try:
                yield
            finally:
                stop_event.set()
                ingestion_task.cancel()
                lifecycle_sweep_task.cancel()
                prefix_invariance_task.cancel()
                warmup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await ingestion_task
                with suppress(asyncio.CancelledError):
                    await lifecycle_sweep_task
                with suppress(asyncio.CancelledError):
                    await prefix_invariance_task
                with suppress(asyncio.CancelledError):
                    await warmup_task
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
