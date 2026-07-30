"""Backtesting orchestration without persistence or research dependencies."""

from dataclasses import dataclass

from app.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    MarketBar,
    PredictionPoint,
    StrategyConfig,
)
from app.backtesting.portfolio import simulate_portfolio
from app.backtesting.reporting import (
    BacktestProvenance,
    BuiltBacktestReport,
    build_backtest_report,
)
from app.backtesting.signals import generate_signals
from app.backtesting.strategy import RidgeThresholdLongOnlyStrategy


@dataclass(frozen=True, slots=True)
class BacktestExecution:
    result: BacktestResult
    report: BuiltBacktestReport


def run_backtest(
    *,
    predictions: tuple[PredictionPoint, ...],
    bars: tuple[MarketBar, ...],
    configuration: BacktestConfig,
    strategy_configuration: StrategyConfig,
    provenance: BacktestProvenance,
) -> BacktestExecution:
    """Run the fixed strategy and construct its immutable report."""
    strategy = RidgeThresholdLongOnlyStrategy(strategy_configuration)
    signals = generate_signals(predictions, strategy)
    result = simulate_portfolio(
        bars=bars,
        signals=signals,
        configuration=configuration,
    )
    report = build_backtest_report(
        configuration=configuration,
        strategy_configuration=strategy_configuration,
        provenance=provenance,
        predictions=predictions,
        bars=bars,
        result=result,
    )
    return BacktestExecution(result=result, report=report)

