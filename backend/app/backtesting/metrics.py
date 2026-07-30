"""Deterministic backtest performance calculations."""

from decimal import Decimal, localcontext
import math

from app.backtesting.models import (
    BacktestConfig,
    BacktestResult,
    ZERO,
)


def calculate_performance_metrics(
    result: BacktestResult,
    configuration: BacktestConfig,
) -> dict[str, Decimal | int | None]:
    history = result.daily_history
    if len(history) < 2:
        raise ValueError("At least two daily snapshots are required.")
    returns = tuple(item.daily_return for item in history[1:])
    total_return = (
        result.final_portfolio_value / result.initial_capital
        - Decimal("1")
    )
    elapsed_days = (
        history[-1].timestamp.date() - history[0].timestamp.date()
    ).days
    cagr = _cagr(total_return, elapsed_days)
    mean_return = _mean(returns)
    return_std = _sample_standard_deviation(returns)
    annualized_volatility = return_std * _sqrt_decimal(
        Decimal(configuration.annualization_periods)
    )
    daily_risk_free = (
        configuration.annual_risk_free_rate
        / Decimal(configuration.annualization_periods)
    )
    excess_returns = tuple(
        value - daily_risk_free for value in returns
    )
    excess_std = _sample_standard_deviation(excess_returns)
    sharpe = (
        _mean(excess_returns)
        / excess_std
        * _sqrt_decimal(Decimal(configuration.annualization_periods))
        if excess_std != ZERO
        else None
    )
    downside = tuple(
        min(value - daily_risk_free, ZERO)
        for value in returns
    )
    downside_deviation = _sqrt_decimal(
        _mean(tuple(value * value for value in downside))
    )
    sortino = (
        _mean(excess_returns)
        / downside_deviation
        * _sqrt_decimal(Decimal(configuration.annualization_periods))
        if downside_deviation != ZERO
        else None
    )
    trade_returns = tuple(
        item.net_profit_loss for item in result.closed_trades
    )
    gains = tuple(value for value in trade_returns if value > ZERO)
    losses = tuple(value for value in trade_returns if value < ZERO)
    profit_factor = (
        sum(gains, ZERO) / abs(sum(losses, ZERO))
        if losses
        else None
    )
    return {
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "maximum_drawdown": _maximum_drawdown(
            tuple(item.portfolio_value for item in history)
        ),
        "win_rate": (
            Decimal(len(gains)) / Decimal(len(trade_returns))
            if trade_returns
            else None
        ),
        "profit_factor": profit_factor,
        "average_gain": _mean(gains) if gains else None,
        "average_loss": _mean(losses) if losses else None,
        "number_of_trades": len(trade_returns),
        "mean_daily_return": mean_return,
    }


def _mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        return ZERO
    return sum(values, ZERO) / Decimal(len(values))


def _sample_standard_deviation(
    values: tuple[Decimal, ...],
) -> Decimal:
    if len(values) < 2:
        return ZERO
    mean = _mean(values)
    variance = sum(
        ((item - mean) ** 2 for item in values),
        ZERO,
    ) / Decimal(len(values) - 1)
    return _sqrt_decimal(variance)


def _sqrt_decimal(value: Decimal) -> Decimal:
    if value < ZERO:
        raise ValueError("Cannot calculate the square root of a negative.")
    with localcontext() as context:
        context.prec = 50
        return value.sqrt()


def _cagr(total_return: Decimal, elapsed_days: int) -> Decimal | None:
    if elapsed_days <= 0 or total_return <= Decimal("-1"):
        return None
    annualized = math.pow(
        float(Decimal("1") + total_return),
        365.25 / elapsed_days,
    ) - 1
    if not math.isfinite(annualized):
        return None
    return Decimal(str(annualized))


def _maximum_drawdown(values: tuple[Decimal, ...]) -> Decimal:
    peak = values[0]
    maximum = ZERO
    for value in values:
        peak = max(peak, value)
        drawdown = (peak - value) / peak
        maximum = max(maximum, drawdown)
    return maximum
