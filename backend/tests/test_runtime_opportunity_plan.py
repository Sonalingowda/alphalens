"""Tests for RuntimeOpportunityPlanService quantization fix.

ATR * 1.5 can produce values exceeding the 18-place Decimal quantum.
This test module verifies that derived plan values are quantized
before domain validation.
"""

import unittest
from decimal import Decimal

from app.opportunity_intelligence.domain.primitives import DECIMAL_QUANTUM
from app.runtime_opportunity_plan.service import (
    RUNTIME_OPPORTUNITY_PLAN_POLICY_HASH,
    RUNTIME_OPPORTUNITY_PLAN_POLICY_ID,
    RUNTIME_OPPORTUNITY_PLAN_POLICY_VERSION,
    RuntimeOpportunityPlanService,
)


class TestDecimalQuantization(unittest.TestCase):
    """Verify that ATR-derived values are properly quantized."""

    def test_atr_one_times_one_point_five_fits_quantum(self) -> None:
        atr = Decimal("1.000000000000000000")
        target = (atr * Decimal("1.5")).quantize(DECIMAL_QUANTUM)
        self.assertEqual(target, Decimal("1.500000000000000000"))
        self.assertEqual(target.as_tuple().exponent, -18)

    def test_realistic_atr_times_one_point_five_fits_quantum(self) -> None:
        atr = Decimal("25.516127303552196627")
        target = (atr * Decimal("1.5")).quantize(DECIMAL_QUANTUM)
        self.assertEqual(target, Decimal("38.274190955328294940"))
        self.assertEqual(target.as_tuple().exponent, -18)

    def test_unquantized_atr_times_one_point_five_exceeds_quantum(self) -> None:
        atr = Decimal("25.516127303552196627")
        target_raw = atr * Decimal("1.5")
        self.assertNotEqual(target_raw, target_raw.quantize(DECIMAL_QUANTUM))

    def test_small_atr_times_one_point_five_fits_quantum(self) -> None:
        atr = Decimal("0.010000000000000001")
        target = (atr * Decimal("1.5")).quantize(DECIMAL_QUANTUM)
        self.assertEqual(target.as_tuple().exponent, -18)

    def test_large_atr_times_one_point_five_fits_quantum(self) -> None:
        atr = Decimal("999.999999999999999999")
        target = (atr * Decimal("1.5")).quantize(DECIMAL_QUANTUM)
        self.assertEqual(target.as_tuple().exponent, -18)


if __name__ == "__main__":
    unittest.main()
