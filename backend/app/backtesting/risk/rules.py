"""Independent entry and open-position risk rule calculations."""

from decimal import Decimal

from app.backtesting.models import MarketBar, ZERO
from app.backtesting.risk.config import RiskConfiguration
from app.backtesting.risk.models import (
    EntryRiskContext,
    ForcedExitDecision,
)


def entry_rejections(
    configuration: RiskConfiguration,
    context: EntryRiskContext,
) -> tuple[str, ...]:
    reasons: list[str] = []
    concurrent = configuration.maximum_concurrent_positions
    if (
        concurrent is not None
        and context.open_position_count
        >= concurrent.maximum_positions
    ):
        reasons.append("maximum_concurrent_positions")
    cooldown = configuration.trading_cooldown
    if (
        cooldown is not None
        and context.last_exit_observation_index is not None
        and context.observation_index
        - context.last_exit_observation_index
        <= cooldown.observations_after_exit
    ):
        reasons.append("trading_cooldown")
    daily = configuration.daily_loss_limit
    if (
        daily is not None
        and context.portfolio_equity
        <= context.previous_close_equity
        * (Decimal("1") - daily.loss_fraction)
    ):
        reasons.append("daily_loss_limit")
    drawdown = configuration.maximum_drawdown
    if (
        drawdown is not None
        and context.portfolio_equity
        <= context.portfolio_peak
        * (Decimal("1") - drawdown.drawdown_fraction)
    ):
        reasons.append("maximum_drawdown")
    return tuple(reasons)


def allocation_caps(
    configuration: RiskConfiguration,
    context: EntryRiskContext,
) -> tuple[tuple[str, Decimal], ...]:
    caps: list[tuple[str, Decimal]] = [("available_cash", context.cash)]
    position = configuration.maximum_position_size
    if position is not None:
        caps.append(
            (
                "maximum_position_size_fraction",
                context.portfolio_equity * position.maximum_fraction,
            )
        )
        if position.maximum_fixed is not None:
            caps.append(
                (
                    "maximum_position_size_fixed",
                    position.maximum_fixed,
                )
            )
    portfolio = configuration.maximum_portfolio_exposure
    if portfolio is not None:
        caps.append(
            (
                "maximum_portfolio_exposure",
                max(
                    context.portfolio_equity
                    * portfolio.maximum_fraction
                    - context.current_portfolio_exposure,
                    ZERO,
                ),
            )
        )
    asset = configuration.maximum_asset_exposure
    if asset is not None:
        caps.append(
            (
                "maximum_asset_exposure",
                max(
                    context.portfolio_equity
                    * asset.maximum_fraction
                    - context.current_asset_exposure,
                    ZERO,
                ),
            )
        )
    reserve = configuration.minimum_cash_reserve
    if reserve is not None:
        caps.append(
            (
                "minimum_cash_reserve",
                max(context.cash - reserve.minimum_cash, ZERO),
            )
        )
    return tuple(caps)


def forced_exit_decision(
    *,
    configuration: RiskConfiguration,
    bar: MarketBar,
    entry_price: Decimal,
    quantity: Decimal,
    prior_high_watermark: Decimal,
    cash: Decimal,
    portfolio_peak: Decimal,
    previous_close_equity: Decimal,
) -> ForcedExitDecision:
    protective: list[tuple[str, Decimal]] = []
    stop = configuration.stop_loss
    if stop is not None:
        trigger = entry_price * (Decimal("1") - stop.loss_fraction)
        if bar.low_price <= trigger:
            protective.append(("stop_loss", trigger))
    trailing = configuration.trailing_stop
    if trailing is not None:
        trigger = prior_high_watermark * (
            Decimal("1") - trailing.drawdown_fraction
        )
        if bar.low_price <= trigger:
            protective.append(("trailing_stop", trigger))
    daily = configuration.daily_loss_limit
    if daily is not None:
        equity_floor = previous_close_equity * (
            Decimal("1") - daily.loss_fraction
        )
        trigger = (equity_floor - cash) / quantity
        if bar.low_price <= trigger:
            protective.append(("daily_loss_limit", trigger))
    drawdown = configuration.maximum_drawdown
    if drawdown is not None:
        equity_floor = portfolio_peak * (
            Decimal("1") - drawdown.drawdown_fraction
        )
        trigger = (equity_floor - cash) / quantity
        if bar.low_price <= trigger:
            protective.append(("maximum_drawdown", trigger))
    if protective:
        rules = tuple(item[0] for item in protective)
        trigger_price = min(item[1] for item in protective)
        reference = min(bar.open_price, trigger_price)
        return ForcedExitDecision(
            required=True,
            triggered_rules=rules,
            reference_price=reference,
            reason=f"risk_forced_exit:{'+'.join(rules)}",
        )
    take_profit = configuration.take_profit
    if take_profit is not None:
        trigger = entry_price * (
            Decimal("1") + take_profit.profit_fraction
        )
        if bar.high_price >= trigger:
            return ForcedExitDecision(
                required=True,
                triggered_rules=("take_profit",),
                reference_price=max(bar.open_price, trigger),
                reason="risk_forced_exit:take_profit",
            )
    return ForcedExitDecision(
        required=False,
        triggered_rules=(),
        reference_price=None,
        reason=None,
    )
