"""Independent risk-rule and position-sizing configuration."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.backtesting.models import ONE, ZERO


class AllocationMode(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"


def _fraction(name: str, value: Decimal) -> None:
    if not ZERO < value <= ONE:
        raise ValueError(f"{name} must be in (0, 1].")


@dataclass(frozen=True, slots=True)
class PositionSizingConfig:
    mode: AllocationMode
    allocation_value: Decimal
    allow_fractional_quantity: bool

    def __post_init__(self) -> None:
        if self.allocation_value <= ZERO:
            raise ValueError("Allocation value must be positive.")
        if (
            self.mode is AllocationMode.PERCENTAGE
            and self.allocation_value > ONE
        ):
            raise ValueError(
                "Percentage allocation cannot exceed 100%."
            )


@dataclass(frozen=True, slots=True)
class MaximumPositionSizeRule:
    maximum_fraction: Decimal
    maximum_fixed: Decimal | None

    def __post_init__(self) -> None:
        _fraction("Maximum position fraction", self.maximum_fraction)
        if self.maximum_fixed is not None and self.maximum_fixed <= ZERO:
            raise ValueError("Fixed position maximum must be positive.")


@dataclass(frozen=True, slots=True)
class MaximumPortfolioExposureRule:
    maximum_fraction: Decimal

    def __post_init__(self) -> None:
        _fraction("Maximum portfolio exposure", self.maximum_fraction)


@dataclass(frozen=True, slots=True)
class MaximumAssetExposureRule:
    maximum_fraction: Decimal

    def __post_init__(self) -> None:
        _fraction("Maximum asset exposure", self.maximum_fraction)


@dataclass(frozen=True, slots=True)
class MaximumConcurrentPositionsRule:
    maximum_positions: int

    def __post_init__(self) -> None:
        if self.maximum_positions < 1:
            raise ValueError("Maximum positions must be positive.")


@dataclass(frozen=True, slots=True)
class StopLossRule:
    loss_fraction: Decimal

    def __post_init__(self) -> None:
        _fraction("Stop-loss fraction", self.loss_fraction)


@dataclass(frozen=True, slots=True)
class TakeProfitRule:
    profit_fraction: Decimal

    def __post_init__(self) -> None:
        if self.profit_fraction <= ZERO:
            raise ValueError("Take-profit fraction must be positive.")


@dataclass(frozen=True, slots=True)
class TrailingStopRule:
    drawdown_fraction: Decimal

    def __post_init__(self) -> None:
        _fraction("Trailing-stop fraction", self.drawdown_fraction)


@dataclass(frozen=True, slots=True)
class DailyLossLimitRule:
    loss_fraction: Decimal

    def __post_init__(self) -> None:
        _fraction("Daily loss fraction", self.loss_fraction)


@dataclass(frozen=True, slots=True)
class MaximumDrawdownRule:
    drawdown_fraction: Decimal

    def __post_init__(self) -> None:
        _fraction("Maximum drawdown fraction", self.drawdown_fraction)


@dataclass(frozen=True, slots=True)
class MinimumCashReserveRule:
    minimum_cash: Decimal

    def __post_init__(self) -> None:
        if self.minimum_cash < ZERO:
            raise ValueError("Minimum cash reserve cannot be negative.")


@dataclass(frozen=True, slots=True)
class TradingCooldownRule:
    observations_after_exit: int

    def __post_init__(self) -> None:
        if self.observations_after_exit < 0:
            raise ValueError("Cooldown observations cannot be negative.")


@dataclass(frozen=True, slots=True)
class RiskConfiguration:
    position_sizing: PositionSizingConfig
    maximum_position_size: MaximumPositionSizeRule | None
    maximum_portfolio_exposure: MaximumPortfolioExposureRule | None
    maximum_asset_exposure: MaximumAssetExposureRule | None
    maximum_concurrent_positions: (
        MaximumConcurrentPositionsRule | None
    )
    stop_loss: StopLossRule | None
    take_profit: TakeProfitRule | None
    trailing_stop: TrailingStopRule | None
    daily_loss_limit: DailyLossLimitRule | None
    maximum_drawdown: MaximumDrawdownRule | None
    minimum_cash_reserve: MinimumCashReserveRule | None
    trading_cooldown: TradingCooldownRule | None

    def active_rule_names(self) -> tuple[str, ...]:
        fields = (
            ("maximum_position_size", self.maximum_position_size),
            (
                "maximum_portfolio_exposure",
                self.maximum_portfolio_exposure,
            ),
            ("maximum_asset_exposure", self.maximum_asset_exposure),
            (
                "maximum_concurrent_positions",
                self.maximum_concurrent_positions,
            ),
            ("stop_loss", self.stop_loss),
            ("take_profit", self.take_profit),
            ("trailing_stop", self.trailing_stop),
            ("daily_loss_limit", self.daily_loss_limit),
            ("maximum_drawdown", self.maximum_drawdown),
            ("minimum_cash_reserve", self.minimum_cash_reserve),
            ("trading_cooldown", self.trading_cooldown),
        )
        return tuple(name for name, rule in fields if rule is not None)

