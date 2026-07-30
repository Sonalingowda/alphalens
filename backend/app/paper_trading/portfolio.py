"""Incremental paper portfolio, position, and risk accounting."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.backtesting.models import (
    ClosedTrade,
    ExecutionFill,
    MarketBar,
    PortfolioSnapshot,
    SignalAction,
    ZERO,
)
from app.backtesting.positions import PositionManager
from app.backtesting.risk.models import (
    EntryRiskContext,
    RiskEvent,
    RiskEventType,
)
from app.paper_trading.models import (
    PaperPosition,
    PaperTradingConfiguration,
    PaperTradingState,
)
from app.paper_trading.orders import PaperOrderExecutionService
from app.paper_trading.risk import load_risk_manager


@dataclass(frozen=True, slots=True)
class PortfolioCycleOutcome:
    cash: Decimal
    open_position: PaperPosition | None
    portfolio_peak: Decimal
    previous_close_equity: Decimal
    last_exit_observation_index: int | None
    fills: tuple[ExecutionFill, ...]
    closed_trades: tuple[ClosedTrade, ...]
    risk_events: tuple[RiskEvent, ...]
    snapshot: PortfolioSnapshot


class PaperPortfolioManager:
    def advance(
        self,
        *,
        state: PaperTradingState,
        bar: MarketBar,
        configuration: PaperTradingConfiguration,
    ) -> PortfolioCycleOutcome:
        positions = _load_positions(state, configuration)
        risk = load_risk_manager(configuration, state)
        orders = PaperOrderExecutionService(configuration.backtest)
        cash = state.cash
        fills: list[ExecutionFill] = []
        trades: list[ClosedTrade] = []
        events: list[RiskEvent] = []
        index = state.observation_sequence
        pending = state.pending_signal
        if (
            pending is not None
            and pending.prediction_timestamp >= bar.timestamp
        ):
            raise ValueError(
                "Paper orders must execute after their prediction timestamp."
            )

        if pending is not None and pending.action is SignalAction.BUY:
            if not positions.can_open():
                events.append(
                    RiskEvent(
                        timestamp=bar.timestamp,
                        event_type=RiskEventType.REJECTED,
                        action="BUY",
                        rule_names=("maximum_concurrent_positions",),
                        reason="buy_rejected",
                        requested_cash_allocation=None,
                        approved_cash_allocation=None,
                        reference_price=bar.open_price,
                    )
                )
            else:
                decision = risk.evaluate_entry(
                    EntryRiskContext(
                        timestamp=bar.timestamp,
                        observation_index=index,
                        cash=cash,
                        portfolio_equity=cash,
                        current_portfolio_exposure=ZERO,
                        current_asset_exposure=ZERO,
                        open_position_count=0,
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
                    fill = orders.buy(
                        signal_timestamp=pending.prediction_timestamp,
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
            pending is not None
            and pending.action is SignalAction.EXIT
            and positions.open_position is not None
        ):
            fill = orders.sell(
                signal_timestamp=pending.prediction_timestamp,
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
                RiskEvent(
                    timestamp=bar.timestamp,
                    event_type=RiskEventType.ACCEPTED,
                    action="SELL",
                    rule_names=configuration.risk.active_rule_names(),
                    reason="strategy_exit_accepted",
                    requested_cash_allocation=None,
                    approved_cash_allocation=None,
                    reference_price=bar.open_price,
                )
            )

        if positions.open_position is not None:
            high_watermark = positions.high_watermark
            if high_watermark is None:
                raise ValueError("Open paper position lacks a high watermark.")
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
                    raise ValueError("Forced-exit evidence is incomplete.")
                fill = orders.sell(
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
                portfolio_value
                / state.previous_close_equity
                - Decimal("1")
                if state.portfolio_history
                else ZERO
            )
        snapshot = PortfolioSnapshot(
            timestamp=bar.timestamp,
            cash=cash,
            position_quantity=quantity,
            position_market_value=market_value,
            portfolio_value=portfolio_value,
            daily_return=daily_return,
            open_position_count=positions.open_position_count,
        )
        risk.record_completed_close(portfolio_value)
        position = (
            PaperPosition(
                entry_fill=positions.open_position.entry_fill,
                high_watermark=_required_high_watermark(positions),
            )
            if positions.open_position is not None
            else None
        )
        return PortfolioCycleOutcome(
            cash=cash,
            open_position=position,
            portfolio_peak=risk.portfolio_peak,
            previous_close_equity=risk.previous_close_equity,
            last_exit_observation_index=(
                risk.last_exit_observation_index
            ),
            fills=tuple(fills),
            closed_trades=tuple(trades),
            risk_events=tuple(events),
            snapshot=snapshot,
        )


def _load_positions(
    state: PaperTradingState,
    configuration: PaperTradingConfiguration,
) -> PositionManager:
    manager = PositionManager(
        configuration.backtest.maximum_concurrent_positions
    )
    if state.open_position is not None:
        manager.open(state.open_position.entry_fill)
        manager.update_high_watermark(
            state.open_position.high_watermark
        )
    return manager


def _required_high_watermark(manager: PositionManager) -> Decimal:
    if manager.high_watermark is None:
        raise ValueError("Paper position high watermark is unavailable.")
    return manager.high_watermark


def _entry_event(
    bar: MarketBar,
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
        requested_cash_allocation=decision.requested_cash_allocation,
        approved_cash_allocation=decision.approved_cash_allocation,
        reference_price=bar.open_price,
    )

