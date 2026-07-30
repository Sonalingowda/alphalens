"""Descriptive performance tracking for the paper portfolio."""

from app.backtesting.metrics import calculate_performance_metrics
from app.backtesting.models import BacktestResult
from app.paper_trading.models import (
    PaperTradingConfiguration,
    PaperTradingState,
)


class PaperPerformanceTracker:
    def summarize(
        self,
        state: PaperTradingState,
        configuration: PaperTradingConfiguration,
    ) -> dict:
        if len(state.portfolio_history) < 2:
            return {
                "total_return": None,
                "cagr": None,
                "annualized_volatility": None,
                "sharpe_ratio": None,
                "sortino_ratio": None,
                "maximum_drawdown": None,
                "win_rate": None,
                "profit_factor": None,
                "average_gain": None,
                "average_loss": None,
                "number_of_trades": len(state.closed_trades),
                "mean_daily_return": None,
            }
        result = BacktestResult(
            signals=state.signals,
            fills=state.fills,
            closed_trades=state.closed_trades,
            daily_history=state.portfolio_history,
            initial_capital=configuration.backtest.initial_capital,
            final_portfolio_value=(
                state.portfolio_history[-1].portfolio_value
            ),
        )
        return calculate_performance_metrics(
            result,
            configuration.backtest,
        )

