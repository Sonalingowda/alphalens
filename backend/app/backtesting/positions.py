"""Long-only position state and closed-trade accounting."""

from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.backtesting.models import (
    ClosedTrade,
    ExecutionFill,
    OrderSide,
)


@dataclass(frozen=True, slots=True)
class OpenPosition:
    entry_fill: ExecutionFill


class PositionManager:
    def __init__(self, maximum_concurrent_positions: int) -> None:
        self._maximum = maximum_concurrent_positions
        self._position: OpenPosition | None = None
        self._high_watermark: Decimal | None = None

    @property
    def open_position(self) -> OpenPosition | None:
        return self._position

    @property
    def open_position_count(self) -> int:
        return int(self._position is not None)

    @property
    def high_watermark(self) -> Decimal | None:
        return self._high_watermark

    def can_open(self) -> bool:
        return self._position is None and self._maximum >= 1

    def open(self, fill: ExecutionFill) -> None:
        if fill.side is not OrderSide.BUY or not self.can_open():
            raise ValueError("Position cannot be opened from this fill.")
        self._position = OpenPosition(entry_fill=fill)
        self._high_watermark = fill.execution_price

    def update_high_watermark(self, completed_high: Decimal) -> None:
        if self._position is None or self._high_watermark is None:
            raise ValueError("No open position has a high watermark.")
        self._high_watermark = max(
            self._high_watermark,
            completed_high,
        )

    def close(self, fill: ExecutionFill) -> ClosedTrade:
        if fill.side is not OrderSide.SELL or self._position is None:
            raise ValueError("Position cannot be closed from this fill.")
        entry = self._position.entry_fill
        if fill.quantity != entry.quantity:
            raise ValueError("Backtesting v1.0.0 requires a full exit.")
        entry_cash_out = -entry.cash_delta
        with localcontext() as context:
            context.prec = 50
            gross = (
                fill.execution_price - entry.execution_price
            ) * fill.quantity
            net = fill.cash_delta - entry_cash_out
            return_fraction = net / entry_cash_out
        trade = ClosedTrade(
            entry_signal_timestamp=entry.signal_timestamp,
            entry_timestamp=entry.execution_timestamp,
            exit_signal_timestamp=(
                fill.signal_timestamp
                if fill.reason == "strategy_exit_next_open"
                else None
            ),
            exit_timestamp=fill.execution_timestamp,
            quantity=fill.quantity,
            entry_price=entry.execution_price,
            exit_price=fill.execution_price,
            gross_profit_loss=gross,
            net_profit_loss=net,
            total_transaction_cost=(
                entry.transaction_cost + fill.transaction_cost
            ),
            return_fraction=return_fraction,
            holding_days=(
                fill.execution_timestamp.date()
                - entry.execution_timestamp.date()
            ).days,
            exit_reason=fill.reason,
        )
        self._position = None
        self._high_watermark = None
        return trade
