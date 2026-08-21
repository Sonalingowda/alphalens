"""Deterministic replay verification for V2 outcome resolution.

Verifies the complete outcome resolution path with synthetic but realistic
candle data.  Each scenario is fully deterministic and auditable.
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.outcome_resolution.service import (
    OutcomeResolutionService,
    _determine_outcome,
)
from app.opportunity_intelligence.domain import (
    OpportunityOutcome,
    OutcomeRecord,
)


_UTC = timezone.utc
_SIGNAL = datetime(2025, 6, 15, 10, 0, tzinfo=_UTC)
_VALID_UNTIL = datetime(2025, 6, 15, 10, 25, tzinfo=_UTC)
_RESOLVED_AT = datetime(2025, 6, 15, 10, 30, tzinfo=_UTC)

# BUY setup: reference=100k, entry=[99.5k, 100.5k], stop=98k, target=103k
_BUY_REF = Decimal("100000.000000000000000000")
_BUY_ENTRY_LO = Decimal("99500.000000000000000000")
_BUY_ENTRY_HI = Decimal("100500.000000000000000000")
_BUY_STOP = Decimal("98000.000000000000000000")
_BUY_TARGET = Decimal("103000.000000000000000000")

# SELL setup: reference=100k, entry=[99.5k, 100.5k], stop=102k, target=97k
_SELL_STOP = Decimal("102000.000000000000000000")
_SELL_TARGET = Decimal("97000.000000000000000000")


def _candle(ts_offset_min: int, o: str, h: str, l: str, c: str) -> dict:
    return {
        "timestamp": _SIGNAL + timedelta(minutes=ts_offset_min),
        "open": Decimal(o),
        "high": Decimal(h),
        "low": Decimal(l),
        "close": Decimal(c),
        "volume": Decimal("1000"),
    }


class ReplayBuyTargetHit(unittest.TestCase):
    """BUY: price rises through entry zone, then hits target at minute 3."""

    def test_buy_target_hit(self) -> None:
        candles = (
            _candle(1, "100100", "100800", "99800", "100600"),
            _candle(2, "100600", "101500", "100400", "101200"),
            _candle(3, "101200", "103100", "101000", "102900"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(count, 3)
        self.assertEqual(price, _BUY_TARGET)
        self.assertEqual(ts, _SIGNAL + timedelta(minutes=3))
        self.assertEqual(idx, 2)
        self.assertIsNone(reason)


class ReplaySellTargetHit(unittest.TestCase):
    """SELL: price drops through entry zone, then hits target at minute 4."""

    def test_sell_target_hit(self) -> None:
        candles = (
            _candle(1, "100100", "100300", "99200", "99400"),
            _candle(2, "99400", "99800", "98500", "98800"),
            _candle(3, "98800", "99100", "97800", "98000"),
            _candle(4, "98000", "98200", "96900", "97100"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_SELL_STOP,
            target_price=_SELL_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(count, 4)
        self.assertEqual(price, _SELL_TARGET)


class ReplayBuyStopHit(unittest.TestCase):
    """BUY: price drops immediately to stop at minute 1."""

    def test_buy_stop_hit(self) -> None:
        candles = (
            _candle(1, "100100", "100200", "97900", "98100"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)
        self.assertEqual(count, 1)
        self.assertEqual(price, _BUY_STOP)


class ReplaySellStopHit(unittest.TestCase):
    """SELL: price spikes to stop at minute 2."""

    def test_sell_stop_hit(self) -> None:
        candles = (
            _candle(1, "100100", "100300", "99800", "100000"),
            _candle(2, "100000", "102100", "99900", "101800"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_SELL_STOP,
            target_price=_SELL_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)
        self.assertEqual(count, 2)
        self.assertEqual(price, _SELL_STOP)


class ReplayDualTouch(unittest.TestCase):
    """BUY: both barriers touched in the same candle."""

    def test_buy_dual_touch(self) -> None:
        candles = (
            _candle(1, "100100", "103200", "97800", "100500"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.UNRESOLVED)
        self.assertEqual(count, 1)
        self.assertEqual(price, _BUY_REF)


class ReplayExpired(unittest.TestCase):
    """BUY: price oscillates but never touches either barrier."""

    def test_expired(self) -> None:
        candles = (
            _candle(1, "100100", "100800", "99200", "100500"),
            _candle(2, "100500", "101000", "99800", "100200"),
            _candle(3, "100200", "100800", "99500", "100000"),
            _candle(4, "100000", "100500", "99000", "100300"),
            _candle(5, "100300", "100900", "99400", "100600"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.EXPIRED)
        self.assertEqual(count, 5)
        self.assertIsNone(price)


class ReplayChronology(unittest.TestCase):
    """BUY: stop touched first (minute 2), target touched later (minute 3)."""

    def test_stop_before_target(self) -> None:
        candles = (
            _candle(1, "100100", "100800", "99200", "100500"),
            _candle(2, "100500", "101000", "97800", "98100"),
            _candle(3, "98100", "103200", "98000", "102800"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)


class ReplayIdempotency(unittest.TestCase):
    """Same candle sequence always produces the same outcome."""

    def test_idempotency(self) -> None:
        candles = (
            _candle(1, "100100", "100800", "99800", "100600"),
            _candle(2, "100600", "101500", "100400", "101200"),
            _candle(3, "101200", "103100", "101000", "102900"),
        )
        kwargs = dict(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        r1 = _determine_outcome(**kwargs)
        r2 = _determine_outcome(**kwargs)
        self.assertEqual(r1, r2)


class ReplayRecordIntegrity(unittest.TestCase):
    """Output OutcomeRecord has correct field invariants."""

    def test_record_invariants(self) -> None:
        candles = (
            _candle(1, "100100", "103100", "99800", "102900"),
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=_BUY_REF,
            entry_zone_lower=_BUY_ENTRY_LO,
            entry_zone_upper=_BUY_ENTRY_HI,
            invalidation_price=_BUY_STOP,
            target_price=_BUY_TARGET,
            signal_timestamp=_SIGNAL,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertIsNotNone(price)
        self.assertIsNotNone(ts)
        self.assertIsNotNone(idx)
        self.assertIsNone(reason)
        self.assertGreaterEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
