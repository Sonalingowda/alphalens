"""Append-only persistence for artifact-only paper trading cycles."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.artifact import hash_json
from app.inference.repository import (
    LoadedProductionArtifact,
    load_production_artifact,
)
from app.inference.service import ProductionPredictionService
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.inference import PaperInferenceService
from app.paper_trading.models import (
    PAPER_TRADING_ENGINE_VERSION,
    PAPER_TRADING_REPORT_VERSION,
    PaperMarketSnapshot,
    PaperTradingConfiguration,
    PaperTradingProvenance,
    PaperTradingState,
)
from app.paper_trading.reporting import (
    build_paper_trading_report,
    paper_trading_configuration_payload,
    state_from_report,
)
from app.persistence.models import (
    PaperTradingReportRecord,
)


DATABASE_QUANTUM = Decimal("0.000000000000000001")


@dataclass(frozen=True, slots=True)
class PersistedPaperTradingReport:
    report_id: UUID
    generated_at: datetime
    cycle_sequence: int
    cycle_end: datetime
    configuration_hash: str
    result_hash: str
    payload: dict
    created: bool


async def persist_paper_trading_cycle(
    session: AsyncSession,
    *,
    snapshot: PaperMarketSnapshot,
    configuration: PaperTradingConfiguration,
) -> PersistedPaperTradingReport:
    """Run and atomically append one or more newly completed observations."""
    async with session.begin():
        artifact = await load_production_artifact(session)
        provenance = _provenance(artifact)
        configuration_payload = paper_trading_configuration_payload(
            configuration=configuration,
            provenance=provenance,
        )
        configuration_hash = hash_json(configuration_payload)
        previous = (
            await session.scalars(
                select(PaperTradingReportRecord)
                .where(
                    PaperTradingReportRecord.configuration_hash
                    == configuration_hash
                )
                .order_by(PaperTradingReportRecord.cycle_end.desc())
                .limit(1)
            )
        ).one_or_none()
        if (
            previous is not None
            and snapshot.completed_through <= previous.cycle_end
        ):
            if snapshot.completed_through != previous.cycle_end:
                raise ValueError(
                    "Paper market snapshot predates persisted state."
                )
            return _verified_existing(previous)
        prior_state = (
            state_from_report(previous.report_payload)
            if previous is not None
            else PaperTradingState.initial(
                configuration.backtest.initial_capital
            )
        )
        service = PaperInferenceService(
            ProductionPredictionService(artifact)
        )
        engine = PaperTradingEngine()
        first = engine.run_cycle(
            snapshot=snapshot,
            prior_state=prior_state,
            configuration=configuration,
            inference=service,
        )
        second = engine.run_cycle(
            snapshot=snapshot,
            prior_state=prior_state,
            configuration=configuration,
            inference=service,
        )
        if first is None or second is None or first != second:
            raise ValueError("Paper trading cycle is not deterministic.")
        report = build_paper_trading_report(
            configuration=configuration,
            provenance=provenance,
            cycle=first,
            previous_report_id=previous.id if previous else None,
            previous_result_hash=(
                previous.result_hash if previous else None
            ),
        )
        repeated = build_paper_trading_report(
            configuration=configuration,
            provenance=provenance,
            cycle=second,
            previous_report_id=previous.id if previous else None,
            previous_result_hash=(
                previous.result_hash if previous else None
            ),
        )
        if (
            report.configuration_hash != configuration_hash
            or report.configuration_hash
            != repeated.configuration_hash
            or report.result_hash != repeated.result_hash
        ):
            raise ValueError("Paper report repeatability failed.")
        state = first.state
        current = state.portfolio_history[-1]
        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        cycle_sequence = (
            previous.cycle_sequence + 1 if previous is not None else 1
        )
        record = PaperTradingReportRecord(
            id=report_id,
            report_version=PAPER_TRADING_REPORT_VERSION,
            engine_version=PAPER_TRADING_ENGINE_VERSION,
            report_configuration=report.configuration,
            report_payload=report.payload,
            configuration_hash=report.configuration_hash,
            result_hash=report.result_hash,
            previous_report_id=previous.id if previous else None,
            inference_artifact_id=artifact.artifact_id,
            selected_experiment_id=artifact.selected_experiment_id,
            holdout_evaluation_report_id=(
                artifact.holdout_evaluation_report_id
            ),
            validation_run_id=artifact.validation_run_id,
            session_name=configuration.session_name,
            cycle_sequence=cycle_sequence,
            cycle_start=first.cycle_start,
            cycle_end=first.cycle_end,
            processed_observation_count=(
                first.processed_observation_count
            ),
            model_dataset_hash=artifact.model_dataset_hash,
            training_dataset_hash=artifact.training_dataset_hash,
            feature_pipeline_version=(
                artifact.feature_pipeline_version
            ),
            target_version=artifact.target_version,
            split_hash=artifact.split_hash,
            inference_artifact_sha256=artifact.artifact_sha256,
            current_cash=_database_decimal(state.cash),
            current_equity=_database_decimal(
                current.portfolio_value
            ),
            open_position_count=current.open_position_count,
            prediction_count=len(state.predictions),
            signal_count=len(state.signals),
            order_count=len(state.fills),
            trade_count=len(state.closed_trades),
            risk_event_count=len(state.risk_events),
            portfolio_observation_count=len(
                state.portfolio_history
            ),
            audit_event_count=len(state.audit_log),
            market_data_hash=first.market_data_hash,
            feature_set_hash=first.feature_set_hash,
            prediction_hash=report.prediction_hash,
            signal_hash=report.signal_hash,
            order_hash=report.order_hash,
            trade_hash=report.trade_hash,
            risk_event_hash=report.risk_event_hash,
            portfolio_history_hash=(
                report.portfolio_history_hash
            ),
            audit_log_hash=report.audit_log_hash,
            artifact_only_inference=True,
            fit_invoked=False,
            live_orders_placed=False,
            research_artifacts_modified=False,
            deterministic=True,
            artifact_hashes_verified=True,
            generated_at=generated_at,
        )
        session.add(record)
        await session.flush()
    return PersistedPaperTradingReport(
        report_id=report_id,
        generated_at=generated_at,
        cycle_sequence=cycle_sequence,
        cycle_end=first.cycle_end,
        configuration_hash=report.configuration_hash,
        result_hash=report.result_hash,
        payload=report.payload,
        created=True,
    )


def _provenance(
    record: LoadedProductionArtifact,
) -> PaperTradingProvenance:
    return PaperTradingProvenance(
        inference_artifact_id=record.artifact_id,
        inference_artifact_sha256=record.artifact_sha256,
        inference_state_sha256=record.state_sha256,
        inference_configuration_hash=record.configuration_hash,
        selected_experiment_id=record.selected_experiment_id,
        holdout_evaluation_report_id=(
            record.holdout_evaluation_report_id
        ),
        model_dataset_hash=record.model_dataset_hash,
        training_dataset_hash=record.training_dataset_hash,
        feature_pipeline_version=record.feature_pipeline_version,
        target_version=record.target_version,
        validation_run_id=record.validation_run_id,
        split_hash=record.split_hash,
    )


def _verified_existing(
    record: PaperTradingReportRecord,
) -> PersistedPaperTradingReport:
    payload = record.report_payload
    hashes = payload["artifact_hashes"]
    if (
        hash_json(record.report_configuration)
        != record.configuration_hash
        or hash_json(payload) != record.result_hash
        or hash_json(payload["predictions"]) != record.prediction_hash
        or hash_json(payload["signals"]) != record.signal_hash
        or hash_json(payload["orders"]) != record.order_hash
        or hash_json(payload["trades"]) != record.trade_hash
        or hash_json(payload["risk_events"]) != record.risk_event_hash
        or hash_json(payload["portfolio_history"])
        != record.portfolio_history_hash
        or hash_json(payload["audit_log"]) != record.audit_log_hash
        or hashes["market_data_sha256"] != record.market_data_hash
        or hashes["cycle_feature_vectors_sha256"]
        != record.feature_set_hash
        or not record.artifact_only_inference
        or record.fit_invoked
        or record.live_orders_placed
        or record.research_artifacts_modified
        or not record.deterministic
        or not record.artifact_hashes_verified
    ):
        raise ValueError("Persisted paper report failed verification.")
    state_from_report(payload)
    return PersistedPaperTradingReport(
        report_id=record.id,
        generated_at=record.generated_at,
        cycle_sequence=record.cycle_sequence,
        cycle_end=record.cycle_end,
        configuration_hash=record.configuration_hash,
        result_hash=record.result_hash,
        payload=payload,
        created=False,
    )


def _database_decimal(value: Decimal) -> Decimal:
    return value.quantize(
        DATABASE_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )
