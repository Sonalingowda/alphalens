"""Risk-managed backtesting orchestration."""

from dataclasses import dataclass

from app.backtesting.models import (
    BacktestConfig,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.models import RiskManagedBacktestResult
from app.backtesting.risk.portfolio import (
    simulate_risk_managed_portfolio,
)
from app.backtesting.risk.reporting import (
    BuiltRiskManagementReport,
    RiskReportProvenance,
    build_risk_management_report,
)
from app.backtesting.signals import generate_signals
from app.backtesting.strategy import RidgeThresholdLongOnlyStrategy


@dataclass(frozen=True, slots=True)
class RiskManagedBacktestExecution:
    result: RiskManagedBacktestResult
    report: BuiltRiskManagementReport


def run_risk_managed_backtest(
    *,
    predictions: tuple[PredictionPoint, ...],
    bars: tuple[MarketBar, ...],
    backtest_configuration: BacktestConfig,
    strategy_configuration: StrategyConfig,
    risk_configuration: RiskConfiguration,
    provenance: RiskReportProvenance,
) -> RiskManagedBacktestExecution:
    strategy = RidgeThresholdLongOnlyStrategy(strategy_configuration)
    signals = generate_signals(predictions, strategy)
    result = simulate_risk_managed_portfolio(
        bars=bars,
        signals=signals,
        configuration=backtest_configuration,
        risk_configuration=risk_configuration,
    )
    report = build_risk_management_report(
        backtest_configuration=backtest_configuration,
        strategy_configuration=strategy_configuration,
        risk_configuration=risk_configuration,
        provenance=provenance,
        predictions=predictions,
        bars=bars,
        result=result,
    )
    return RiskManagedBacktestExecution(
        result=result,
        report=report,
    )

