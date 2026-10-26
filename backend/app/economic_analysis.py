"""Deterministic, assumption-labelled economics for an opportunity plan.

This module deliberately does not estimate probability, expected value or
profitability.  It only evaluates the arithmetic consequences of a supplied
plan and explicit cost assumptions.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class EconomicAnalysisError(ValueError):
    """Raised when an economic scenario is malformed."""


@dataclass(frozen=True, slots=True)
class EconomicAssumptions:
    """Explicit scenario inputs; no exchange rates are inferred."""

    position_notional: Decimal
    currency: str = "USD"
    fx_to_usd: Decimal | None = None
    entry_fee_bps: Decimal = Decimal("0")
    exit_fee_bps: Decimal = Decimal("0")
    entry_slippage_bps: Decimal = Decimal("0")
    exit_slippage_bps: Decimal = Decimal("0")
    instrument_semantics: str = "spot"


@dataclass(frozen=True, slots=True)
class EconomicAnalysis:
    """Decimal-safe, assumption-labelled output."""

    status: str
    reason: str | None
    direction: str
    currency: str
    position_notional: Decimal | None
    position_notional_usd: Decimal | None
    entry_reference: Decimal | None
    target_price: Decimal | None
    invalidation_price: Decimal | None
    gross_target_movement_points: Decimal | None
    gross_target_movement_fraction: Decimal | None
    gross_stop_movement_fraction: Decimal | None
    gross_potential_profit: Decimal | None
    gross_potential_loss: Decimal | None
    entry_fee: Decimal | None
    exit_fee: Decimal | None
    estimated_slippage: Decimal | None
    total_modeled_costs: Decimal | None
    estimated_net_target_profit: Decimal | None
    estimated_net_stop_loss: Decimal | None
    estimated_net_return_fraction: Decimal | None
    estimated_net_risk_reward: Decimal | None
    break_even_movement_fraction: Decimal | None
    cost_to_gross_reward_ratio: Decimal | None
    assumptions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            key: (str(value) if isinstance(value, Decimal) else value)
            for key, value in asdict(self).items()
        }


def _decimal(value: object, field: str, *, non_negative: bool = False) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise EconomicAnalysisError(f"{field} must be a finite Decimal.") from error
    if not result.is_finite() or (non_negative and result < 0):
        raise EconomicAnalysisError(f"{field} must be finite and non-negative.")
    return result


def unavailable_analysis(direction: str, reason: str) -> EconomicAnalysis:
    """Return a truthful unavailable result instead of inventing economics."""
    return EconomicAnalysis(
        status="UNAVAILABLE",
        reason=reason,
        direction=direction,
        currency="USD",
        position_notional=None,
        position_notional_usd=None,
        entry_reference=None,
        target_price=None,
        invalidation_price=None,
        gross_target_movement_points=None,
        gross_target_movement_fraction=None,
        gross_stop_movement_fraction=None,
        gross_potential_profit=None,
        gross_potential_loss=None,
        entry_fee=None,
        exit_fee=None,
        estimated_slippage=None,
        total_modeled_costs=None,
        estimated_net_target_profit=None,
        estimated_net_stop_loss=None,
        estimated_net_return_fraction=None,
        estimated_net_risk_reward=None,
        break_even_movement_fraction=None,
        cost_to_gross_reward_ratio=None,
        assumptions={},
    )


def calculate_economics(
    *,
    direction: str,
    entry_lower: object,
    entry_upper: object,
    target_price: object,
    invalidation_price: object,
    assumptions: EconomicAssumptions,
) -> EconomicAnalysis:
    """Calculate conservative gross/net geometry for a supplied scenario.

    The entry reference is the midpoint of the immutable entry zone.  Fees and
    slippage are explicit assumptions, and the notional is fully funded.  SELL
    scenarios require non-spot semantics because AlphaLens does not claim that
    a spot account can open a naked short.
    """
    direction = direction.upper()
    if direction not in {"BUY", "SELL"}:
        return unavailable_analysis(direction, "unsupported_direction")
    semantics = assumptions.instrument_semantics.lower()
    if direction == "SELL" and semantics == "spot":
        return unavailable_analysis(
            direction,
            "spot_semantics_do_not_support_naked_short",
        )
    currency = assumptions.currency.upper()
    if currency not in {"USD", "INR"}:
        return unavailable_analysis(direction, "unsupported_currency")
    notional = _decimal(assumptions.position_notional, "position_notional")
    if notional <= 0:
        return unavailable_analysis(direction, "position_notional_must_be_positive")
    fx = assumptions.fx_to_usd
    if currency == "INR":
        if fx is None:
            return unavailable_analysis(direction, "explicit_inr_usd_rate_required")
        fx = _decimal(fx, "fx_to_usd")
        if fx <= 0:
            return unavailable_analysis(direction, "fx_to_usd_must_be_positive")
        notional_usd = notional / fx
    else:
        notional_usd = notional

    low = _decimal(entry_lower, "entry_lower")
    high = _decimal(entry_upper, "entry_upper")
    target = _decimal(target_price, "target_price")
    stop = _decimal(invalidation_price, "invalidation_price")
    if min(low, high, target, stop) <= 0 or low > high:
        return unavailable_analysis(direction, "invalid_price_geometry")
    entry = (low + high) / Decimal("2")
    if direction == "BUY" and not (stop < entry <= target):
        return unavailable_analysis(direction, "buy_geometry_order_invalid")
    if direction == "SELL" and not (target <= entry < stop):
        return unavailable_analysis(direction, "sell_geometry_order_invalid")

    fee_in = _decimal(assumptions.entry_fee_bps, "entry_fee_bps", non_negative=True)
    fee_out = _decimal(assumptions.exit_fee_bps, "exit_fee_bps", non_negative=True)
    slip_in = _decimal(assumptions.entry_slippage_bps, "entry_slippage_bps", non_negative=True)
    slip_out = _decimal(assumptions.exit_slippage_bps, "exit_slippage_bps", non_negative=True)
    target_fraction = (target - entry) / entry
    stop_fraction = (entry - stop) / entry
    if direction == "SELL":
        target_fraction = -target_fraction
        stop_fraction = -stop_fraction
    gross_profit = notional_usd * target_fraction
    gross_loss = notional_usd * abs(stop_fraction)
    entry_fee = notional_usd * fee_in / Decimal("10000")
    exit_fee = notional_usd * fee_out / Decimal("10000")
    slippage = notional_usd * (slip_in + slip_out) / Decimal("10000")
    costs = entry_fee + exit_fee + slippage
    net_profit = gross_profit - costs
    net_loss = -(gross_loss + costs)
    net_return = net_profit / notional_usd
    break_even = costs / notional_usd
    ratio = costs / gross_profit if gross_profit > 0 else None
    net_rr = net_profit / abs(net_loss) if net_loss != 0 else None
    status = "ECONOMICALLY_POSITIVE_UNDER_ASSUMPTIONS" if net_profit > 0 else "COSTS_EXCEED_GROSS_TARGET"
    return EconomicAnalysis(
        status=status,
        reason=None,
        direction=direction,
        currency=currency,
        position_notional=notional,
        position_notional_usd=notional_usd,
        entry_reference=entry,
        target_price=target,
        invalidation_price=stop,
        gross_target_movement_points=abs(target - entry),
        gross_target_movement_fraction=target_fraction,
        gross_stop_movement_fraction=abs(stop_fraction),
        gross_potential_profit=gross_profit,
        gross_potential_loss=gross_loss,
        entry_fee=entry_fee,
        exit_fee=exit_fee,
        estimated_slippage=slippage,
        total_modeled_costs=costs,
        estimated_net_target_profit=net_profit,
        estimated_net_stop_loss=net_loss,
        estimated_net_return_fraction=net_return,
        estimated_net_risk_reward=net_rr,
        break_even_movement_fraction=break_even,
        cost_to_gross_reward_ratio=ratio,
        assumptions={
            "instrument_semantics": semantics,
            "entry_fee_bps": str(fee_in),
            "exit_fee_bps": str(fee_out),
            "entry_slippage_bps": str(slip_in),
            "exit_slippage_bps": str(slip_out),
            "fx_to_usd": str(fx) if fx is not None else "not_applicable",
            "prediction_status": "unavailable_without_approved_artifact",
        },
    )
