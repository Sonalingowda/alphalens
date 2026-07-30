"""Strongly typed contracts shared by the backtesting engine."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


ZERO = Decimal("0")
ONE = Decimal("1")
BASIS_POINTS = Decimal("10000")


class SignalAction(StrEnum):
    BUY = "BUY"
    HOLD = "HOLD"
    EXIT = "EXIT"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    initial_capital: Decimal
    position_size_fraction: Decimal
    long_only: bool
    transaction_cost_bps: Decimal
    slippage_bps: Decimal
    maximum_concurrent_positions: int
    daily_position_updates: bool
    liquidate_at_end: bool
    annualization_periods: int
    annual_risk_free_rate: Decimal

    def __post_init__(self) -> None:
        if self.initial_capital <= ZERO:
            raise ValueError("Initial capital must be positive.")
        if not ZERO < self.position_size_fraction <= ONE:
            raise ValueError("Position size fraction must be in (0, 1].")
        if not self.long_only:
            raise ValueError("Backtesting v1.0.0 supports long-only mode.")
        if self.transaction_cost_bps < ZERO or self.slippage_bps < ZERO:
            raise ValueError("Costs and slippage cannot be negative.")
        if self.maximum_concurrent_positions < 1:
            raise ValueError("Maximum concurrent positions must be positive.")
        if not self.daily_position_updates:
            raise ValueError("Backtesting v1.0.0 requires daily updates.")
        if self.annualization_periods < 1:
            raise ValueError("Annualization periods must be positive.")
        if self.annual_risk_free_rate <= -ONE:
            raise ValueError("Annual risk-free rate must exceed -100%.")


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    strategy_name: str
    strategy_version: str
    buy_threshold: Decimal
    exit_threshold: Decimal

    def __post_init__(self) -> None:
        if not self.strategy_name or not self.strategy_version:
            raise ValueError("Strategy identity is required.")
        if self.exit_threshold > self.buy_threshold:
            raise ValueError(
                "Exit threshold cannot exceed the buy threshold."
            )


@dataclass(frozen=True, slots=True)
class PredictionPoint:
    prediction_timestamp: datetime
    predicted_forward_return: Decimal
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class MarketBar:
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal

    def __post_init__(self) -> None:
        if (
            self.open_price <= ZERO
            or self.high_price <= ZERO
            or self.low_price <= ZERO
            or self.close_price <= ZERO
            or self.low_price > self.high_price
            or not self.low_price <= self.open_price <= self.high_price
            or not self.low_price <= self.close_price <= self.high_price
        ):
            raise ValueError("Market bar contains invalid OHLC values.")


@dataclass(frozen=True, slots=True)
class TradingSignal:
    prediction_timestamp: datetime
    action: SignalAction
    predicted_forward_return: Decimal
    strategy_name: str
    strategy_version: str
    source_prediction_hash: str


@dataclass(frozen=True, slots=True)
class ExecutionFill:
    signal_timestamp: datetime
    execution_timestamp: datetime
    side: OrderSide
    reference_price: Decimal
    execution_price: Decimal
    quantity: Decimal
    gross_notional: Decimal
    transaction_cost: Decimal
    cash_delta: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class ClosedTrade:
    entry_signal_timestamp: datetime
    entry_timestamp: datetime
    exit_signal_timestamp: datetime | None
    exit_timestamp: datetime
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    gross_profit_loss: Decimal
    net_profit_loss: Decimal
    total_transaction_cost: Decimal
    return_fraction: Decimal
    holding_days: int
    exit_reason: str


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    timestamp: datetime
    cash: Decimal
    position_quantity: Decimal
    position_market_value: Decimal
    portfolio_value: Decimal
    daily_return: Decimal
    open_position_count: int


@dataclass(frozen=True, slots=True)
class BacktestResult:
    signals: tuple[TradingSignal, ...]
    fills: tuple[ExecutionFill, ...]
    closed_trades: tuple[ClosedTrade, ...]
    daily_history: tuple[PortfolioSnapshot, ...]
    initial_capital: Decimal
    final_portfolio_value: Decimal

