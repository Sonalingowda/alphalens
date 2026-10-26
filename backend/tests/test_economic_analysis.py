from decimal import Decimal

from app.economic_analysis import EconomicAssumptions, calculate_economics


def scenario(**overrides):
    values = {
        "position_notional": Decimal("500"),
        "currency": "INR",
        "fx_to_usd": Decimal("83"),
        "entry_fee_bps": Decimal("10"),
        "exit_fee_bps": Decimal("10"),
        "entry_slippage_bps": Decimal("5"),
        "exit_slippage_bps": Decimal("5"),
        "instrument_semantics": "perpetual_derivative",
    }
    values.update(overrides)
    return EconomicAssumptions(**values)


def test_buy_uses_decimal_geometry_and_round_trip_costs():
    result = calculate_economics(
        direction="BUY",
        entry_lower=Decimal("100"),
        entry_upper=Decimal("102"),
        target_price=Decimal("110"),
        invalidation_price=Decimal("95"),
        assumptions=scenario(),
    )

    assert result.status == "ECONOMICALLY_POSITIVE_UNDER_ASSUMPTIONS"
    assert result.entry_reference == Decimal("101")
    assert result.position_notional_usd == Decimal("500") / Decimal("83")
    assert result.total_modeled_costs == (Decimal("500") / Decimal("83")) * Decimal("0.003")
    assert result.estimated_net_target_profit is not None


def test_sell_is_unavailable_for_spot_but_supported_for_explicit_short_semantics():
    spot = calculate_economics(
        direction="SELL",
        entry_lower=Decimal("100"),
        entry_upper=Decimal("102"),
        target_price=Decimal("90"),
        invalidation_price=Decimal("105"),
        assumptions=scenario(currency="USD", position_notional=Decimal("500"), instrument_semantics="spot"),
    )
    assert spot.status == "UNAVAILABLE"
    assert spot.reason == "spot_semantics_do_not_support_naked_short"

    derivative = calculate_economics(
        direction="SELL",
        entry_lower=Decimal("100"),
        entry_upper=Decimal("102"),
        target_price=Decimal("90"),
        invalidation_price=Decimal("105"),
        assumptions=scenario(currency="USD", position_notional=Decimal("500")),
    )
    assert derivative.direction == "SELL"
    assert derivative.gross_target_movement_fraction == Decimal("11") / Decimal("101")


def test_costs_can_exceed_reward_and_missing_fx_is_unavailable():
    expensive = calculate_economics(
        direction="BUY",
        entry_lower=Decimal("100"),
        entry_upper=Decimal("100"),
        target_price=Decimal("100.1"),
        invalidation_price=Decimal("99"),
        assumptions=scenario(
            currency="USD",
            position_notional=Decimal("500"),
            entry_fee_bps=Decimal("100"),
            exit_fee_bps=Decimal("100"),
            entry_slippage_bps=Decimal("100"),
            exit_slippage_bps=Decimal("100"),
        ),
    )
    assert expensive.status == "COSTS_EXCEED_GROSS_TARGET"
    assert expensive.estimated_net_target_profit is not None
    assert expensive.estimated_net_target_profit < 0

    missing_fx = calculate_economics(
        direction="BUY",
        entry_lower=Decimal("100"),
        entry_upper=Decimal("100"),
        target_price=Decimal("110"),
        invalidation_price=Decimal("95"),
        assumptions=scenario(fx_to_usd=None),
    )
    assert missing_fx.status == "UNAVAILABLE"
    assert missing_fx.reason == "explicit_inr_usd_rate_required"
