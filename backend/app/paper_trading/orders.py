"""Paper-order execution using the approved backtesting simulator."""

from decimal import Decimal

from app.backtesting.execution import OrderExecutionSimulator
from app.backtesting.models import BacktestConfig, ExecutionFill


class PaperOrderExecutionService:
    def __init__(self, configuration: BacktestConfig) -> None:
        self._executor = OrderExecutionSimulator(configuration)

    def buy(
        self,
        *,
        signal_timestamp,
        execution_timestamp,
        reference_price: Decimal,
        cash_allocation: Decimal,
        allow_fractional_quantity: bool,
    ) -> ExecutionFill:
        return self._executor.execute_buy_allocation(
            signal_timestamp=signal_timestamp,
            execution_timestamp=execution_timestamp,
            reference_price=reference_price,
            cash_allocation=cash_allocation,
            allow_fractional_quantity=allow_fractional_quantity,
        )

    def sell(
        self,
        *,
        signal_timestamp,
        execution_timestamp,
        reference_price: Decimal,
        quantity: Decimal,
        reason: str,
    ) -> ExecutionFill:
        return self._executor.execute_sell(
            signal_timestamp=signal_timestamp,
            execution_timestamp=execution_timestamp,
            reference_price=reference_price,
            quantity=quantity,
            reason=reason,
        )

