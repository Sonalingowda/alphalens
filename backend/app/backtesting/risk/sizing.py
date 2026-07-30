"""Percentage, fixed, and fractional position sizing."""

from decimal import Decimal

from app.backtesting.risk.config import (
    AllocationMode,
    PositionSizingConfig,
)


class PositionSizer:
    def __init__(self, configuration: PositionSizingConfig) -> None:
        self._configuration = configuration

    @property
    def allow_fractional_quantity(self) -> bool:
        return self._configuration.allow_fractional_quantity

    def requested_cash_allocation(
        self,
        portfolio_equity: Decimal,
    ) -> Decimal:
        if self._configuration.mode is AllocationMode.PERCENTAGE:
            return (
                portfolio_equity
                * self._configuration.allocation_value
            )
        return self._configuration.allocation_value

