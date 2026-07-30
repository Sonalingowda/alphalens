"""Deterministic order execution with explicit costs and slippage."""

from decimal import Decimal, localcontext

from app.backtesting.models import (
    BASIS_POINTS,
    BacktestConfig,
    ExecutionFill,
    OrderSide,
    ZERO,
)


class OrderExecutionSimulator:
    def __init__(self, configuration: BacktestConfig) -> None:
        self._configuration = configuration

    def execute_buy(
        self,
        *,
        signal_timestamp,
        execution_timestamp,
        reference_price: Decimal,
        available_cash: Decimal,
    ) -> ExecutionFill:
        if available_cash <= ZERO:
            raise ValueError("Available cash must be positive.")
        budget = (
            available_cash
            * self._configuration.position_size_fraction
        )
        return self.execute_buy_allocation(
            signal_timestamp=signal_timestamp,
            execution_timestamp=execution_timestamp,
            reference_price=reference_price,
            cash_allocation=budget,
            allow_fractional_quantity=True,
        )

    def execute_buy_allocation(
        self,
        *,
        signal_timestamp,
        execution_timestamp,
        reference_price: Decimal,
        cash_allocation: Decimal,
        allow_fractional_quantity: bool,
    ) -> ExecutionFill:
        if cash_allocation <= ZERO:
            raise ValueError("Cash allocation must be positive.")
        execution_price = reference_price * (
            Decimal("1")
            + self._configuration.slippage_bps / BASIS_POINTS
        )
        cost_rate = (
            self._configuration.transaction_cost_bps / BASIS_POINTS
        )
        with localcontext() as context:
            context.prec = 50
            quantity = cash_allocation / (
                execution_price * (1 + cost_rate)
            )
            if not allow_fractional_quantity:
                quantity = quantity.to_integral_value(
                    rounding="ROUND_FLOOR"
                )
            if quantity <= ZERO:
                raise ValueError(
                    "Approved allocation cannot purchase one whole unit."
                )
            notional = quantity * execution_price
            cost = notional * cost_rate
        return ExecutionFill(
            signal_timestamp=signal_timestamp,
            execution_timestamp=execution_timestamp,
            side=OrderSide.BUY,
            reference_price=reference_price,
            execution_price=execution_price,
            quantity=quantity,
            gross_notional=notional,
            transaction_cost=cost,
            cash_delta=-(notional + cost),
            reason="strategy_buy_next_open",
        )

    def execute_sell(
        self,
        *,
        signal_timestamp,
        execution_timestamp,
        reference_price: Decimal,
        quantity: Decimal,
        reason: str,
    ) -> ExecutionFill:
        if quantity <= ZERO:
            raise ValueError("Sell quantity must be positive.")
        execution_price = reference_price * (
            Decimal("1")
            - self._configuration.slippage_bps / BASIS_POINTS
        )
        if execution_price <= ZERO:
            raise ValueError("Slippage produces a non-positive price.")
        cost_rate = (
            self._configuration.transaction_cost_bps / BASIS_POINTS
        )
        with localcontext() as context:
            context.prec = 50
            notional = quantity * execution_price
            cost = notional * cost_rate
        return ExecutionFill(
            signal_timestamp=signal_timestamp,
            execution_timestamp=execution_timestamp,
            side=OrderSide.SELL,
            reference_price=reference_price,
            execution_price=execution_price,
            quantity=quantity,
            gross_notional=notional,
            transaction_cost=cost,
            cash_delta=notional - cost,
            reason=reason,
        )
