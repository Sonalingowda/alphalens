"""Incremental adapter for the approved risk management framework."""

from app.backtesting.risk.manager import RiskManager
from app.paper_trading.models import (
    PaperTradingConfiguration,
    PaperTradingState,
)


def load_risk_manager(
    configuration: PaperTradingConfiguration,
    state: PaperTradingState,
) -> RiskManager:
    manager = RiskManager(
        configuration.risk,
        configuration.backtest.initial_capital,
    )
    manager.portfolio_peak = state.portfolio_peak
    manager.previous_close_equity = state.previous_close_equity
    manager.last_exit_observation_index = (
        state.last_exit_observation_index
    )
    return manager

