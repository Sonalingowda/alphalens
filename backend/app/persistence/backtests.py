"""Persistence boundary for immutable official-holdout backtests."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.engine import run_backtest
from app.backtesting.models import (
    BacktestConfig,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)
from app.backtesting.reporting import (
    BACKTEST_ENGINE_VERSION,
    BACKTEST_REPORT_VERSION,
    BacktestProvenance,
    hash_json,
)
from app.persistence.models import (
    BacktestReportRecord,
    CandleRecord,
    HoldoutConsumptionRecord,
    HoldoutEvaluationReportRecord,
    HoldoutPredictionEvidenceRecord,
    RegressionExperimentRecord,
)


DATABASE_QUANTUM = Decimal("0.000000000000000001")


@dataclass(frozen=True, slots=True)
class PersistedBacktestReport:
    report_id: UUID
    generated_at: datetime
    configuration_hash: str
    result_hash: str
    payload: dict
    created: bool


async def run_and_persist_official_holdout_backtest(
    session: AsyncSession,
    *,
    configuration: BacktestConfig,
    strategy_configuration: StrategyConfig,
) -> PersistedBacktestReport:
    """Backtest immutable evidence without invoking the research pipeline."""
    async with session.begin():
        holdout = (
            await session.scalars(
                select(HoldoutEvaluationReportRecord).where(
                    HoldoutEvaluationReportRecord
                    .official_holdout_evaluation
                    .is_(True),
                    HoldoutEvaluationReportRecord.holdout_consumed.is_(True),
                )
            )
        ).one()
        consumption = await session.get(
            HoldoutConsumptionRecord,
            holdout.validation_run_id,
        )
        experiment = await session.get(
            RegressionExperimentRecord,
            holdout.selected_experiment_id,
        )
        if (
            consumption is None
            or not consumption.official
            or not consumption.irreversible
            or consumption.holdout_evaluation_report_id != holdout.id
            or experiment is None
            or experiment.model_family != "ridge_regression"
            or hash_json(holdout.report_configuration)
            != holdout.configuration_hash
            or hash_json(holdout.report_payload) != holdout.result_hash
        ):
            raise ValueError(
                "Official immutable holdout provenance failed verification."
            )
        evidence = tuple(
            (
                await session.scalars(
                    select(HoldoutPredictionEvidenceRecord)
                    .where(
                        HoldoutPredictionEvidenceRecord.report_id
                        == holdout.id
                    )
                    .order_by(
                        HoldoutPredictionEvidenceRecord
                        .prediction_timestamp
                    )
                )
            ).all()
        )
        if (
            len(evidence) != holdout.holdout_prediction_evidence_count
            or _sha256_lines(
                tuple(item.evidence_hash for item in evidence)
            )
            != holdout.holdout_prediction_evidence_set_hash
        ):
            raise ValueError("Holdout prediction evidence hash differs.")
        candle_rows = tuple(
            (
                await session.scalars(
                    select(CandleRecord)
                    .where(
                        CandleRecord.asset_identifier == "BTC",
                        CandleRecord.quote_currency == "USD",
                        CandleRecord.timeframe == "1d",
                        CandleRecord.candle_timestamp
                        >= holdout.registered_holdout_start,
                        CandleRecord.candle_timestamp
                        <= holdout.registered_holdout_end,
                        CandleRecord.is_complete.is_(True),
                    )
                    .order_by(CandleRecord.candle_timestamp)
                )
            ).all()
        )
        if (
            len(candle_rows)
            != holdout.registered_holdout_observation_count
            or candle_rows[0].candle_timestamp
            != holdout.registered_holdout_start
            or candle_rows[-1].candle_timestamp
            != holdout.registered_holdout_end
        ):
            raise ValueError("Registered holdout candles are incomplete.")
        predictions = tuple(
            PredictionPoint(
                prediction_timestamp=item.prediction_timestamp,
                predicted_forward_return=item.predicted_value,
                evidence_hash=item.evidence_hash,
            )
            for item in evidence
        )
        bars = tuple(
            MarketBar(
                timestamp=item.candle_timestamp,
                open_price=item.open_price,
                high_price=item.high_price,
                low_price=item.low_price,
                close_price=item.close_price,
            )
            for item in candle_rows
        )
        provenance = BacktestProvenance(
            holdout_evaluation_report_id=holdout.id,
            holdout_configuration_hash=holdout.configuration_hash,
            holdout_result_hash=holdout.result_hash,
            selected_experiment_id=experiment.id,
            selected_experiment_configuration_hash=(
                experiment.experiment_configuration_hash
            ),
            selected_experiment_result_hash=experiment.result_hash,
            model_dataset_hash=holdout.model_dataset_hash,
            feature_pipeline_version=holdout.feature_pipeline_version,
            target_version=holdout.target_version,
            validation_run_id=holdout.validation_run_id,
            split_hash=holdout.split_hash,
            prediction_evidence_set_hash=(
                holdout.holdout_prediction_evidence_set_hash
            ),
            candle_ingestion_batch_ids=tuple(
                sorted(
                    {item.ingestion_batch_id for item in candle_rows},
                    key=str,
                )
            ),
        )
        execution = run_backtest(
            predictions=predictions,
            bars=bars,
            configuration=configuration,
            strategy_configuration=strategy_configuration,
            provenance=provenance,
        )
        repeated = run_backtest(
            predictions=predictions,
            bars=bars,
            configuration=configuration,
            strategy_configuration=strategy_configuration,
            provenance=provenance,
        )
        report = execution.report
        if (
            report.configuration_hash
            != repeated.report.configuration_hash
            or report.result_hash != repeated.report.result_hash
        ):
            raise ValueError("Backtest report is not deterministic.")
        existing = (
            await session.scalars(
                select(BacktestReportRecord).where(
                    BacktestReportRecord.configuration_hash
                    == report.configuration_hash
                )
            )
        ).one_or_none()
        if existing is not None:
            if (
                existing.result_hash != report.result_hash
                or existing.input_evidence_hash
                != report.input_evidence_hash
                or existing.signal_hash != report.signal_hash
                or existing.trade_log_hash != report.trade_log_hash
                or existing.equity_curve_hash
                != report.equity_curve_hash
                or existing.daily_history_hash
                != report.daily_history_hash
            ):
                raise ValueError(
                    "Regenerated backtest differs from persisted evidence."
                )
            return _verified_existing(existing)

        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        record = BacktestReportRecord(
            id=report_id,
            report_version=BACKTEST_REPORT_VERSION,
            engine_version=BACKTEST_ENGINE_VERSION,
            report_configuration=report.configuration,
            report_payload=report.payload,
            configuration_hash=report.configuration_hash,
            result_hash=report.result_hash,
            source_holdout_report_id=holdout.id,
            selected_experiment_id=experiment.id,
            model_dataset_hash=holdout.model_dataset_hash,
            feature_pipeline_version=holdout.feature_pipeline_version,
            target_version=holdout.target_version,
            validation_run_id=holdout.validation_run_id,
            split_hash=holdout.split_hash,
            prediction_evidence_set_hash=(
                holdout.holdout_prediction_evidence_set_hash
            ),
            strategy_name=strategy_configuration.strategy_name,
            strategy_version=strategy_configuration.strategy_version,
            period_start=bars[0].timestamp,
            period_end=bars[-1].timestamp,
            initial_capital=_database_decimal(
                execution.result.initial_capital
            ),
            final_portfolio_value=_database_decimal(
                execution.result.final_portfolio_value
            ),
            signal_count=len(execution.result.signals),
            fill_count=len(execution.result.fills),
            trade_count=len(execution.result.closed_trades),
            daily_observation_count=len(execution.result.daily_history),
            input_evidence_hash=report.input_evidence_hash,
            signal_hash=report.signal_hash,
            trade_log_hash=report.trade_log_hash,
            equity_curve_hash=report.equity_curve_hash,
            daily_history_hash=report.daily_history_hash,
            research_artifacts_modified=False,
            deterministic=True,
            artifact_hashes_verified=True,
            generated_at=generated_at,
        )
        session.add(record)
        await session.flush()
    return PersistedBacktestReport(
        report_id=report_id,
        generated_at=generated_at,
        configuration_hash=report.configuration_hash,
        result_hash=report.result_hash,
        payload=report.payload,
        created=True,
    )


def _verified_existing(
    record: BacktestReportRecord,
) -> PersistedBacktestReport:
    artifact_hashes = record.report_payload["artifact_hashes"]
    if (
        hash_json(record.report_configuration)
        != record.configuration_hash
        or hash_json(record.report_payload) != record.result_hash
        or artifact_hashes["input_evidence_sha256"]
        != record.input_evidence_hash
        or artifact_hashes["signals_sha256"] != record.signal_hash
        or artifact_hashes["trade_log_sha256"]
        != record.trade_log_hash
        or artifact_hashes["equity_curve_sha256"]
        != record.equity_curve_hash
        or artifact_hashes["daily_portfolio_history_sha256"]
        != record.daily_history_hash
        or hash_json(record.report_payload["signals"])
        != record.signal_hash
        or hash_json(record.report_payload["trade_log"])
        != record.trade_log_hash
        or hash_json(record.report_payload["equity_curve"])
        != record.equity_curve_hash
        or hash_json(
            record.report_payload["daily_portfolio_history"]
        )
        != record.daily_history_hash
        or not record.deterministic
        or not record.artifact_hashes_verified
    ):
        raise ValueError("Persisted backtest report failed verification.")
    return PersistedBacktestReport(
        report_id=record.id,
        generated_at=record.generated_at,
        configuration_hash=record.configuration_hash,
        result_hash=record.result_hash,
        payload=record.report_payload,
        created=False,
    )


def _database_decimal(value: Decimal) -> Decimal:
    return value.quantize(
        DATABASE_QUANTUM,
        rounding=ROUND_HALF_EVEN,
    )


def _sha256_lines(values: tuple[str, ...]) -> str:
    digest = sha256()
    for value in values:
        digest.update((value + "\n").encode())
    return digest.hexdigest()
