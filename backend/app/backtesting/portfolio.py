"""Chronological long-only portfolio simulation."""

from decimal import Decimal, localcontext

from app.backtesting.execution import OrderExecutionSimulator
from app.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    ClosedTrade,
    ExecutionFill,
    MarketBar,
    PortfolioSnapshot,
    SignalAction,
    TradingSignal,
    ZERO,
)
from app.backtesting.positions import PositionManager


def simulate_portfolio(
    *,
    bars: tuple[MarketBar, ...],
    signals: tuple[TradingSignal, ...],
    configuration: BacktestConfig,
) -> BacktestResult:
    """Execute close-time signals at the strictly subsequent bar open."""
    _validate_inputs(bars, signals)
    next_bar_by_timestamp = {
        bars[index].timestamp: bars[index + 1].timestamp
        for index in range(len(bars) - 1)
    }
    scheduled = {
        next_bar_by_timestamp[signal.prediction_timestamp]: signal
        for signal in signals
        if signal.prediction_timestamp in next_bar_by_timestamp
    }
    executor = OrderExecutionSimulator(configuration)
    positions = PositionManager(
        configuration.maximum_concurrent_positions
    )
    cash = configuration.initial_capital
    fills: list[ExecutionFill] = []
    trades: list[ClosedTrade] = []
    history: list[PortfolioSnapshot] = []
    previous_value = configuration.initial_capital

    for index, bar in enumerate(bars):
        signal = scheduled.get(bar.timestamp)
        if (
            signal is not None
            and signal.action is SignalAction.BUY
            and positions.can_open()
        ):
            fill = executor.execute_buy(
                signal_timestamp=signal.prediction_timestamp,
                execution_timestamp=bar.timestamp,
                reference_price=bar.open_price,
                available_cash=cash,
            )
            cash += fill.cash_delta
            positions.open(fill)
            fills.append(fill)
        elif (
            signal is not None
            and signal.action is SignalAction.EXIT
            and positions.open_position is not None
        ):
            fill = executor.execute_sell(
                signal_timestamp=signal.prediction_timestamp,
                execution_timestamp=bar.timestamp,
                reference_price=bar.open_price,
                quantity=positions.open_position.entry_fill.quantity,
                reason="strategy_exit_next_open",
            )
            cash += fill.cash_delta
            trades.append(positions.close(fill))
            fills.append(fill)

        if (
            index == len(bars) - 1
            and configuration.liquidate_at_end
            and positions.open_position is not None
        ):
            fill = executor.execute_sell(
                signal_timestamp=bar.timestamp,
                execution_timestamp=bar.timestamp,
                reference_price=bar.close_price,
                quantity=positions.open_position.entry_fill.quantity,
                reason="terminal_liquidation_at_close",
            )
            cash += fill.cash_delta
            trades.append(positions.close(fill))
            fills.append(fill)

        quantity = (
            positions.open_position.entry_fill.quantity
            if positions.open_position is not None
            else ZERO
        )
        market_value = quantity * bar.close_price
        portfolio_value = cash + market_value
        with localcontext() as context:
            context.prec = 50
            daily_return = (
                portfolio_value / previous_value - Decimal("1")
                if history
                else ZERO
            )
        history.append(
            PortfolioSnapshot(
                timestamp=bar.timestamp,
                cash=cash,
                position_quantity=quantity,
                position_market_value=market_value,
                portfolio_value=portfolio_value,
                daily_return=daily_return,
                open_position_count=positions.open_position_count,
            )
        )
        previous_value = portfolio_value

    return BacktestResult(
        signals=signals,
        fills=tuple(fills),
        closed_trades=tuple(trades),
        daily_history=tuple(history),
        initial_capital=configuration.initial_capital,
        final_portfolio_value=history[-1].portfolio_value,
    )


def _validate_inputs(
    bars: tuple[MarketBar, ...],
    signals: tuple[TradingSignal, ...],
) -> None:
    timestamps = tuple(item.timestamp for item in bars)
    if (
        len(bars) < 2
        or timestamps != tuple(sorted(set(timestamps)))
    ):
        raise ValueError(
            "Bars must contain at least two unique chronological values."
        )
    bar_timestamps = set(timestamps)
    signal_timestamps = tuple(
        item.prediction_timestamp for item in signals
    )
    if (
        not signals
        or signal_timestamps
        != tuple(sorted(set(signal_timestamps)))
        or any(timestamp not in bar_timestamps for timestamp in signal_timestamps)
    ):
        raise ValueError(
            "Signals must be unique, chronological, and aligned to bars."
        )
