"""Immutable persistence for deterministic risk management reports."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.models import (
    BacktestConfig,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)
from app.backtesting.reporting import BacktestProvenance, hash_json
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.engine import run_risk_managed_backtest
from app.backtesting.risk.reporting import (
    RISK_FRAMEWORK_VERSION,
    RISK_REPORT_VERSION,
    RiskReportProvenance,
)
from app.persistence.models import (
    BacktestReportRecord,
    CandleRecord,
    HoldoutEvaluationReportRecord,
    HoldoutPredictionEvidenceRecord,
    RegressionExperimentRecord,
    RiskManagementReportRecord,
)


DATABASE_QUANTUM = Decimal("0.000000000000000001")


@dataclass(frozen=True, slots=True)
class PersistedRiskManagementReport:
    report_id: UUID
    generated_at: datetime
    configuration_hash: str
    result_hash: str
    payload: dict
    created: bool


async def run_and_persist_risk_management_report(
    session: AsyncSession,
    *,
    backtest_configuration: BacktestConfig,
    strategy_configuration: StrategyConfig,
    risk_configuration: RiskConfiguration,
) -> PersistedRiskManagementReport:
    async with session.begin():
        source_backtest = (
            await session.scalars(select(BacktestReportRecord))
        ).one()
        holdout = await session.get(
            HoldoutEvaluationReportRecord,
            source_backtest.source_holdout_report_id,
        )
        experiment = await session.get(
            RegressionExperimentRecord,
            source_backtest.selected_experiment_id,
        )
        if (
            holdout is None
            or experiment is None
            or hash_json(source_backtest.report_configuration)
            != source_backtest.configuration_hash
            or hash_json(source_backtest.report_payload)
            != source_backtest.result_hash
            or hash_json(holdout.report_configuration)
            != holdout.configuration_hash
            or hash_json(holdout.report_payload) != holdout.result_hash
            or source_backtest.research_artifacts_modified
            or not source_backtest.deterministic
        ):
            raise ValueError("Source backtest provenance failed verification.")
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
            raise ValueError("Prediction evidence failed verification.")
        candles = tuple(
            (
                await session.scalars(
                    select(CandleRecord)
                    .where(
                        CandleRecord.asset_identifier == "BTC",
                        CandleRecord.quote_currency == "USD",
                        CandleRecord.timeframe == "1d",
                        CandleRecord.candle_timestamp
                        >= source_backtest.period_start,
                        CandleRecord.candle_timestamp
                        <= source_backtest.period_end,
                        CandleRecord.is_complete.is_(True),
                    )
                    .order_by(CandleRecord.candle_timestamp)
                )
            ).all()
        )
        if len(candles) != source_backtest.daily_observation_count:
            raise ValueError("Backtest candle evidence is incomplete.")
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
            for item in candles
        )
        backtest_provenance = BacktestProvenance(
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
                    {item.ingestion_batch_id for item in candles},
                    key=str,
                )
            ),
        )
        provenance = RiskReportProvenance(
            backtest_provenance=backtest_provenance,
            source_backtest_report_id=source_backtest.id,
            source_backtest_configuration_hash=(
                source_backtest.configuration_hash
            ),
            source_backtest_result_hash=source_backtest.result_hash,
        )
        execution = run_risk_managed_backtest(
            predictions=predictions,
            bars=bars,
            backtest_configuration=backtest_configuration,
            strategy_configuration=strategy_configuration,
            risk_configuration=risk_configuration,
            provenance=provenance,
        )
        repeated = run_risk_managed_backtest(
            predictions=predictions,
            bars=bars,
            backtest_configuration=backtest_configuration,
            strategy_configuration=strategy_configuration,
            risk_configuration=risk_configuration,
            provenance=provenance,
        )
        report = execution.report
        if (
            report.configuration_hash
            != repeated.report.configuration_hash
            or report.result_hash != repeated.report.result_hash
            or report.configuration["backtest"]["portfolio"]
            != source_backtest.report_configuration["portfolio"]
            or report.configuration["backtest"]["strategy"]
            != source_backtest.report_configuration["strategy"]
        ):
            raise ValueError(
                "Risk report is non-deterministic or changes base settings."
            )
        existing = (
            await session.scalars(
                select(RiskManagementReportRecord).where(
                    RiskManagementReportRecord.configuration_hash
                    == report.configuration_hash
                )
            )
        ).one_or_none()
        if existing is not None:
            if existing.result_hash != report.result_hash:
                raise ValueError(
                    "Regenerated risk report differs from persistence."
                )
            return _verified_existing(existing)

        result = execution.result.backtest_result
        payload = report.payload
        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        record = RiskManagementReportRecord(
            id=report_id,
            report_version=RISK_REPORT_VERSION,
            framework_version=RISK_FRAMEWORK_VERSION,
            report_configuration=report.configuration,
            report_payload=payload,
            configuration_hash=report.configuration_hash,
            result_hash=report.result_hash,
            source_backtest_report_id=source_backtest.id,
            source_holdout_report_id=holdout.id,
            selected_experiment_id=experiment.id,
            model_dataset_hash=holdout.model_dataset_hash,
            feature_pipeline_version=holdout.feature_pipeline_version,
            target_version=holdout.target_version,
            validation_run_id=holdout.validation_run_id,
            split_hash=holdout.split_hash,
            period_start=bars[0].timestamp,
            period_end=bars[-1].timestamp,
            initial_capital=_database_decimal(result.initial_capital),
            final_portfolio_value=_database_decimal(
                result.final_portfolio_value
            ),
            risk_event_count=len(payload["risk_events"]),
            accepted_trade_count=len(payload["accepted_trades"]),
            rejected_trade_count=len(payload["rejected_trades"]),
            forced_exit_count=len(payload["forced_exits"]),
            protection_event_count=len(
                payload["portfolio_protection_events"]
            ),
            risk_event_hash=report.risk_event_hash,
            accepted_trade_hash=report.accepted_trade_hash,
            rejected_trade_hash=report.rejected_trade_hash,
            forced_exit_hash=report.forced_exit_hash,
            protection_event_hash=report.protection_event_hash,
            research_artifacts_modified=False,
            deterministic=True,
            artifact_hashes_verified=True,
            generated_at=generated_at,
        )
        session.add(record)
        await session.flush()
    return PersistedRiskManagementReport(
        report_id=report_id,
        generated_at=generated_at,
        configuration_hash=report.configuration_hash,
        result_hash=report.result_hash,
        payload=report.payload,
        created=True,
    )


def _verified_existing(
    record: RiskManagementReportRecord,
) -> PersistedRiskManagementReport:
    payload = record.report_payload
    if (
        hash_json(record.report_configuration)
        != record.configuration_hash
        or hash_json(payload) != record.result_hash
        or hash_json(payload["risk_events"]) != record.risk_event_hash
        or hash_json(payload["accepted_trades"])
        != record.accepted_trade_hash
        or hash_json(payload["rejected_trades"])
        != record.rejected_trade_hash
        or hash_json(payload["forced_exits"])
        != record.forced_exit_hash
        or hash_json(payload["portfolio_protection_events"])
        != record.protection_event_hash
        or not record.deterministic
        or not record.artifact_hashes_verified
    ):
        raise ValueError("Persisted risk report failed verification.")
    return PersistedRiskManagementReport(
        report_id=record.id,
        generated_at=record.generated_at,
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


def _sha256_lines(values: tuple[str, ...]) -> str:
    digest = sha256()
    for value in values:
        digest.update((value + "\n").encode())
    return digest.hexdigest()

