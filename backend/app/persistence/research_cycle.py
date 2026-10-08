"""Canonical orchestration for one isolated chronological research cycle."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.candles import (
    get_stored_candle_summary,
)
from app.persistence.explainability import create_explainability_artifact
from app.persistence.experiments import run_and_persist_baseline_experiment
from app.persistence.features import compute_and_persist_features
from app.persistence.final_model_selection import (
    create_final_model_selection_report,
)
from app.persistence.holdout_evaluation import (
    create_official_holdout_evaluation_report,
)
from app.persistence.market_regimes import create_market_regime_report
from app.persistence.model_comparisons import create_model_comparison_report
from app.persistence.model_inference import package_selected_ridge_inference_once
from app.persistence.models import (
    ForwardLogReturnTargetRunRecord,
    IngestionBatchRecord,
    RegressionExperimentRecord,
    ValidationRunRecord,
)
from app.persistence.provenance import get_active_feature_run, get_active_ingestion_batch
from app.persistence.residual_diagnostics import create_residual_diagnostics_report
from app.persistence.statistical_validation import (
    create_statistical_validation_report,
)
from app.persistence.targets import generate_and_persist_forward_log_returns
from app.persistence.validation import (
    ValidationRunAudit,
    create_validation_run,
    get_validation_run,
)
from app.research.baseline_regression import ModelFamily
from app.research.dataset import build_model_ready_dataset
from app.research.final_model_selection import AutomatedTestEvidence
from app.persistence.research_cycle_lineage import (
    EXPLAINABILITY_MODEL_FAMILIES,
    MODEL_FAMILIES,
    current_cycle_experiments,
)
from app.validation.splits import WalkForwardConfig


ResearchCycleStopAfter = Literal[
    "features_targets",
    "validation",
    "experiments",
    "diagnostics",
    "final_model_selection",
    "official_holdout",
    "packaging",
]
_STOP_AFTER_VALUES = frozenset(
    {
        "features_targets",
        "validation",
        "experiments",
        "diagnostics",
        "final_model_selection",
        "official_holdout",
        "packaging",
    }
)


@dataclass(frozen=True, slots=True)
class ResearchCycleSummary:
    """Machine-readable outcome and identifiers for one research cycle."""

    research_cycle_id: str
    status: str
    final_stage: str
    candle_count: int | None = None
    candle_range_start: datetime | None = None
    candle_range_end: datetime | None = None
    ingestion_batch_id: UUID | None = None
    feature_run_id: UUID | None = None
    target_run_id: UUID | None = None
    validation_run_id: UUID | None = None
    experiment_ids: dict[str, UUID] | None = None
    explainability_artifact_ids: dict[str, UUID] | None = None
    statistical_validation_report_id: UUID | None = None
    model_comparison_report_id: UUID | None = None
    residual_diagnostics_report_id: UUID | None = None
    market_regime_report_id: UUID | None = None
    final_selection_report_id: UUID | None = None
    official_holdout_report_id: UUID | None = None
    packaged_artifact_id: UUID | None = None
    failure_stage: str | None = None
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe summary without changing persisted evidence."""

        def encode(value: Any) -> Any:
            if isinstance(value, UUID):
                return str(value)
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {str(key): encode(item) for key, item in value.items()}
            return value

        return {
            field: encode(getattr(self, field))
            for field in self.__dataclass_fields__
        }


async def run_research_cycle(
    session: AsyncSession,
    *,
    validation_config: WalkForwardConfig,
    test_evidence: AutomatedTestEvidence,
    stop_after: ResearchCycleStopAfter = "final_model_selection",
    authorize_holdout: bool = False,
) -> ResearchCycleSummary:
    """Run the canonical research sequence against a caller-supplied DB session.

    Normal execution stops after final model selection. Official holdout
    evaluation and packaging require both a later ``stop_after`` value and
    explicit ``authorize_holdout=True``.

    The caller must provide a session connected to the isolated research
    database with no transaction already in progress. Read-only preconditions
    are committed by this orchestrator before control is passed to persistence
    functions, which each own their ``session.begin()`` transaction. This
    entry point does not construct a database engine, select a URL, contact
    providers, or use production/evidence persistence.
    """

    cycle = ResearchCycleSummary(
        research_cycle_id="unresolved",
        status="failed",
        final_stage="not_started",
    )

    if stop_after not in _STOP_AFTER_VALUES:
        return _failed(
            cycle,
            "orchestration_configuration",
            ValueError(f"Unsupported stop_after stage: {stop_after}"),
        )
    if stop_after in {"official_holdout", "packaging"} and not authorize_holdout:
        return _failed(
            cycle,
            "holdout_authorization",
            PermissionError(
                "Official holdout execution requires explicit authorization."
            ),
        )

    if _has_active_transaction(session):
        return _failed(
            cycle,
            "transaction_boundary",
            RuntimeError(
                "Research-cycle orchestration requires a session with no "
                "pre-existing transaction."
            ),
        )

    try:
        batch, candle_summary = await _verify_market_candle_input(session)
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "market_candle_verification", exc)
    await _finish_read_transaction(session)

    cycle = _replace(
        cycle,
        research_cycle_id=(
            f"{batch.id}:{batch.source_data_hash or 'unhashed'}"
        ),
        final_stage="market_candle_verification",
        candle_count=candle_summary.row_count,
        candle_range_start=candle_summary.date_range_start,
        candle_range_end=candle_summary.date_range_end,
        ingestion_batch_id=batch.id,
        status="running",
    )

    try:
        feature_run = await _ensure_feature_run(session, batch)
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "feature_persistence", exc)
    await _finish_read_transaction(session)
    cycle = _replace(
        cycle,
        final_stage="feature_persistence",
        feature_run_id=feature_run.id,
    )

    try:
        target_run = await _ensure_target_run(session, batch, feature_run.id)
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "target_persistence", exc)
    await _finish_read_transaction(session)
    cycle = _replace(cycle, final_stage="target_persistence", target_run_id=target_run.id)
    if stop_after == "features_targets":
        return _succeeded(cycle)

    try:
        validation = await _ensure_validation_run(
            session,
            batch,
            feature_run.id,
            validation_config,
        )
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "validation_run", exc)
    await _finish_read_transaction(session)
    cycle = _replace(
        cycle,
        final_stage="validation_run",
        validation_run_id=validation.id,
    )
    if stop_after == "validation":
        return _succeeded(cycle)

    try:
        dataset = await build_model_ready_dataset(session)
        await _finish_read_transaction(session)
        experiments = await _ensure_baseline_experiments(session, dataset)
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "baseline_experiments", exc)
    await _finish_read_transaction(session)
    cycle = _replace(
        cycle,
        final_stage="baseline_experiments",
        experiment_ids={item.model_family: item.id for item in experiments},
    )
    if stop_after == "experiments":
        return _succeeded(cycle)

    explainability_ids: dict[str, UUID] = {}
    try:
        for family in EXPLAINABILITY_MODEL_FAMILIES:
            artifact = await create_explainability_artifact(session, family)
            explainability_ids[family] = artifact.artifact_id
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(
            _replace(cycle, explainability_artifact_ids=explainability_ids),
            "explainability",
            exc,
        )
    cycle = _replace(
        cycle,
        final_stage="explainability",
        explainability_artifact_ids=explainability_ids,
    )

    stages = (
        ("statistical_validation", create_statistical_validation_report, "statistical_validation_report_id"),
        ("model_comparison", create_model_comparison_report, "model_comparison_report_id"),
        ("residual_diagnostics", create_residual_diagnostics_report, "residual_diagnostics_report_id"),
        ("market_regime", create_market_regime_report, "market_regime_report_id"),
    )
    for stage, function, field in stages:
        try:
            result = await function(session)
        except Exception as exc:
            await _discard_read_transaction(session)
            return _failed(cycle, stage, exc)
        cycle = _replace(cycle, final_stage=stage, **{field: result.report_id})

    if stop_after == "diagnostics":
        return _succeeded(cycle)

    try:
        selection = await create_final_model_selection_report(
            session,
            test_evidence=test_evidence,
        )
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "final_model_selection", exc)
    cycle = _replace(
        cycle,
        final_stage="final_model_selection",
        final_selection_report_id=selection.report_id,
    )

    if stop_after == "final_model_selection":
        return _succeeded(cycle)

    try:
        holdout = await create_official_holdout_evaluation_report(session)
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "official_holdout_evaluation", exc)
    cycle = _replace(
        cycle,
        final_stage="official_holdout_evaluation",
        official_holdout_report_id=holdout.report_id,
    )

    if stop_after == "official_holdout":
        return _succeeded(cycle)

    try:
        artifact = await package_selected_ridge_inference_once(session)
    except Exception as exc:
        await _discard_read_transaction(session)
        return _failed(cycle, "ridge_inference_packaging", exc)
    return _replace(
        cycle,
        status="succeeded",
        final_stage="ridge_inference_packaging",
        packaged_artifact_id=artifact.artifact_id,
    )


async def _verify_market_candle_input(
    session: AsyncSession,
) -> tuple[IngestionBatchRecord, Any]:
    batch = await get_active_ingestion_batch(session)
    summary = await get_stored_candle_summary(session)
    if (
        summary.row_count != batch.candle_count
        or summary.latest_ingestion_batch_id != batch.id
        or summary.date_range_start != batch.available_range_start
        or summary.date_range_end != batch.available_range_end
    ):
        raise ValueError("Active ingestion batch does not cover the complete candle dataset.")
    return batch, summary


async def _ensure_feature_run(session: AsyncSession, batch: IngestionBatchRecord):
    try:
        return await get_active_feature_run(session, batch.id)
    except ValueError as exc:
        if str(exc) != (
            "No active point-in-time-valid feature run is available for "
            "the active ingestion batch."
        ):
            raise
        await _finish_read_transaction(session)
        result = await compute_and_persist_features(session)
        return await get_active_feature_run(session, result.source_ingestion_batch_id)


async def _ensure_target_run(
    session: AsyncSession,
    batch: IngestionBatchRecord,
    feature_run_id: UUID,
):
    existing = (
        await session.scalars(
            select(ForwardLogReturnTargetRunRecord).where(
                ForwardLogReturnTargetRunRecord.asset_identifier == "BTC",
                ForwardLogReturnTargetRunRecord.quote_currency == "USD",
                ForwardLogReturnTargetRunRecord.timeframe == "1d",
                ForwardLogReturnTargetRunRecord.source_ingestion_batch_id == batch.id,
                ForwardLogReturnTargetRunRecord.source_feature_run_id == feature_run_id,
                ForwardLogReturnTargetRunRecord.is_active.is_(True),
                ForwardLogReturnTargetRunRecord.point_in_time_validated.is_(True),
                ForwardLogReturnTargetRunRecord.persisted_label_count > 0,
            )
        )
    ).one_or_none()
    if existing is not None:
        return existing
    await _finish_read_transaction(session)
    result = await generate_and_persist_forward_log_returns(session)
    persisted = await session.get(
        ForwardLogReturnTargetRunRecord,
        result.generation_run_id,
    )
    if persisted is None:
        raise RuntimeError("Target run disappeared after persistence.")
    return persisted


async def _ensure_validation_run(
    session: AsyncSession,
    batch: IngestionBatchRecord,
    feature_run_id: UUID,
    config: WalkForwardConfig,
) -> ValidationRunAudit:
    existing = (
        await session.scalars(
            select(ValidationRunRecord).where(
                ValidationRunRecord.asset_identifier == "BTC",
                ValidationRunRecord.quote_currency == "USD",
                ValidationRunRecord.timeframe == "1d",
                ValidationRunRecord.source_ingestion_batch_id == batch.id,
                ValidationRunRecord.source_feature_run_id == feature_run_id,
                ValidationRunRecord.is_active.is_(True),
            )
        )
    ).one_or_none()
    if existing is not None and _matches_config(existing, config):
        return await get_validation_run(session, existing.id)
    await _finish_read_transaction(session)
    return await create_validation_run(session, config)


def _matches_config(record: ValidationRunRecord, config: WalkForwardConfig) -> bool:
    return (
        record.minimum_train_size == config.minimum_train_size
        and record.test_size == config.test_size
        and record.step_size == config.step_size
        and record.purge_gap_size == config.purge_gap_size
        and record.final_holdout_size == config.final_holdout_size
    )


async def _ensure_baseline_experiments(session: AsyncSession, dataset):
    records = tuple(
        (
            await session.scalars(
                select(RegressionExperimentRecord).where(
                    RegressionExperimentRecord.model_dataset_hash == dataset.model_dataset_hash,
                    RegressionExperimentRecord.validation_run_id == dataset.validation_run_id,
                    RegressionExperimentRecord.split_hash == dataset.validation_split_hash,
                )
            )
        ).all()
    )
    by_family = {record.model_family: record for record in records}
    if any(
        record.final_holdout_evaluated or not record.point_in_time_validated
        for record in records
    ):
        raise ValueError("Current-cycle baseline evidence is not development-only.")
    for family in MODEL_FAMILIES:
        if family not in by_family:
            await _finish_read_transaction(session)
            await _run_baseline(session, family)
    return await current_cycle_experiments(session, dataset)


async def _run_baseline(session: AsyncSession, family: ModelFamily) -> None:
    await run_and_persist_baseline_experiment(session, family)


def _failed(
    summary: ResearchCycleSummary,
    stage: str,
    exc: Exception,
) -> ResearchCycleSummary:
    return _replace(
        summary,
        status="failed",
        final_stage=stage,
        failure_stage=stage,
        failure_reason=f"{type(exc).__name__}: {exc}",
    )


def _succeeded(summary: ResearchCycleSummary) -> ResearchCycleSummary:
    return _replace(summary, status="succeeded")


async def _finish_read_transaction(session: AsyncSession) -> None:
    """Commit an implicit read transaction before a persistence boundary.

    SQLAlchemy autobegins a transaction for ordinary SELECTs. The research
    persistence functions deliberately own their transactions with
    ``async with session.begin()``; committing here closes only the
    orchestrator's read phase so those functions can establish their normal
    transaction boundary. Callers must therefore provide a session with no
    pre-existing transaction or uncommitted work.
    """

    if _has_active_transaction(session):
        await session.commit()


async def _discard_read_transaction(session: AsyncSession) -> None:
    """Roll back an open read phase when the next stage cannot start."""

    if _has_active_transaction(session):
        await session.rollback()


def _has_active_transaction(session: AsyncSession) -> bool:
    in_transaction = getattr(session, "in_transaction", None)
    return in_transaction is not None and in_transaction()


def _replace(summary: ResearchCycleSummary, **changes: Any) -> ResearchCycleSummary:
    values = {
        field: getattr(summary, field)
        for field in ResearchCycleSummary.__dataclass_fields__
    }
    values.update(changes)
    return ResearchCycleSummary(**values)
