"""Chronological portfolio simulation with pre-order risk controls."""

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
from app.backtesting.portfolio import _validate_inputs
from app.backtesting.positions import PositionManager
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.manager import RiskManager
from app.backtesting.risk.models import (
    EntryRiskContext,
    RiskEvent,
    RiskEventType,
    RiskManagedBacktestResult,
)


def simulate_risk_managed_portfolio(
    *,
    bars: tuple[MarketBar, ...],
    signals: tuple[TradingSignal, ...],
    configuration: BacktestConfig,
    risk_configuration: RiskConfiguration,
) -> RiskManagedBacktestResult:
    _validate_inputs(bars, signals)
    scheduled = {
        bars[index + 1].timestamp: signal
        for signal in signals
        for index in range(len(bars) - 1)
        if bars[index].timestamp == signal.prediction_timestamp
    }
    risk_maximum = (
        risk_configuration.maximum_concurrent_positions
        .maximum_positions
        if risk_configuration.maximum_concurrent_positions is not None
        else configuration.maximum_concurrent_positions
    )
    positions = PositionManager(
        min(configuration.maximum_concurrent_positions, risk_maximum)
    )
    risk = RiskManager(
        risk_configuration,
        configuration.initial_capital,
    )
    executor = OrderExecutionSimulator(configuration)
    cash = configuration.initial_capital
    fills: list[ExecutionFill] = []
    trades: list[ClosedTrade] = []
    history: list[PortfolioSnapshot] = []
    events: list[RiskEvent] = []
    previous_value = configuration.initial_capital

    for index, bar in enumerate(bars):
        signal = scheduled.get(bar.timestamp)
        if signal is not None and signal.action is SignalAction.BUY:
            quantity = _quantity(positions)
            exposure = quantity * bar.open_price
            equity = cash + exposure
            decision = risk.evaluate_entry(
                EntryRiskContext(
                    timestamp=bar.timestamp,
                    observation_index=index,
                    cash=cash,
                    portfolio_equity=equity,
                    current_portfolio_exposure=exposure,
                    current_asset_exposure=exposure,
                    open_position_count=positions.open_position_count,
                    portfolio_peak=risk.portfolio_peak,
                    previous_close_equity=(
                        risk.previous_close_equity
                    ),
                    last_exit_observation_index=(
                        risk.last_exit_observation_index
                    ),
                )
            )
            if not decision.permitted:
                events.append(
                    _entry_event(
                        bar,
                        decision,
                        RiskEventType.REJECTED,
                        "buy_rejected",
                    )
                )
            else:
                if (
                    decision.approved_cash_allocation
                    < decision.requested_cash_allocation
                ):
                    events.append(
                        _entry_event(
                            bar,
                            decision,
                            RiskEventType.ALLOCATION_REDUCED,
                            "buy_allocation_reduced",
                        )
                    )
                fill = executor.execute_buy_allocation(
                    signal_timestamp=signal.prediction_timestamp,
                    execution_timestamp=bar.timestamp,
                    reference_price=bar.open_price,
                    cash_allocation=(
                        decision.approved_cash_allocation
                    ),
                    allow_fractional_quantity=(
                        risk.position_sizer
                        .allow_fractional_quantity
                    ),
                )
                cash += fill.cash_delta
                positions.open(fill)
                fills.append(fill)
                events.append(
                    _entry_event(
                        bar,
                        decision,
                        RiskEventType.ACCEPTED,
                        "buy_accepted",
                    )
                )
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
            risk.record_exit(index)
            events.append(
                _accepted_exit_event(
                    bar,
                    risk_configuration,
                    "strategy_exit_accepted",
                    bar.open_price,
                )
            )

        if positions.open_position is not None:
            high_watermark = positions.high_watermark
            if high_watermark is None:
                raise ValueError("Open position lacks a high watermark.")
            forced = risk.evaluate_open_position(
                bar=bar,
                entry_price=(
                    positions.open_position.entry_fill.execution_price
                ),
                quantity=positions.open_position.entry_fill.quantity,
                prior_high_watermark=high_watermark,
                cash=cash,
            )
            if forced.required:
                if forced.reference_price is None or forced.reason is None:
                    raise ValueError("Forced exit evidence is incomplete.")
                fill = executor.execute_sell(
                    signal_timestamp=bar.timestamp,
                    execution_timestamp=bar.timestamp,
                    reference_price=forced.reference_price,
                    quantity=(
                        positions.open_position.entry_fill.quantity
                    ),
                    reason=forced.reason,
                )
                cash += fill.cash_delta
                trades.append(positions.close(fill))
                fills.append(fill)
                risk.record_exit(index)
                events.append(
                    RiskEvent(
                        timestamp=bar.timestamp,
                        event_type=RiskEventType.FORCED_EXIT,
                        action="SELL",
                        rule_names=forced.triggered_rules,
                        reason=forced.reason,
                        requested_cash_allocation=None,
                        approved_cash_allocation=None,
                        reference_price=forced.reference_price,
                    )
                )
            else:
                positions.update_high_watermark(bar.high_price)

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
            risk.record_exit(index)
            events.append(
                _accepted_exit_event(
                    bar,
                    risk_configuration,
                    "terminal_liquidation_accepted",
                    bar.close_price,
                )
            )

        quantity = _quantity(positions)
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
        risk.record_completed_close(portfolio_value)
        previous_value = portfolio_value

    return RiskManagedBacktestResult(
        backtest_result=BacktestResult(
            signals=signals,
            fills=tuple(fills),
            closed_trades=tuple(trades),
            daily_history=tuple(history),
            initial_capital=configuration.initial_capital,
            final_portfolio_value=history[-1].portfolio_value,
        ),
        risk_events=tuple(events),
    )


def _quantity(positions: PositionManager) -> Decimal:
    return (
        positions.open_position.entry_fill.quantity
        if positions.open_position is not None
        else ZERO
    )


def _entry_event(
    bar,
    decision,
    event_type: RiskEventType,
    reason: str,
) -> RiskEvent:
    return RiskEvent(
        timestamp=bar.timestamp,
        event_type=event_type,
        action="BUY",
        rule_names=decision.triggered_rules,
        reason=reason,
        requested_cash_allocation=(
            decision.requested_cash_allocation
        ),
        approved_cash_allocation=(
            decision.approved_cash_allocation
        ),
        reference_price=bar.open_price,
    )


def _accepted_exit_event(
    bar: MarketBar,
    configuration: RiskConfiguration,
    reason: str,
    reference_price: Decimal,
) -> RiskEvent:
    return RiskEvent(
        timestamp=bar.timestamp,
        event_type=RiskEventType.ACCEPTED,
        action="SELL",
        rule_names=configuration.active_rule_names(),
        reason=reason,
        requested_cash_allocation=None,
        approved_cash_allocation=None,
        reference_price=reference_price,
    )
