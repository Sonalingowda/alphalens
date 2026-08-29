"""Integration tests for the real-market outcome resolution fix.

Covers the master-prompt requirements A-M:

A. BUY entry -> target first -> TARGET_HIT
B. BUY entry -> stop first -> STOP_HIT
C. BUY entry never reached -> EXPIRED_BEFORE_ENTRY
D. BUY entry -> neither barrier -> EXPIRED_AFTER_ENTRY
E. SELL target first
F. SELL stop first
G. both barriers in one candle -> AMBIGUOUS_INTRABAR
H. valid_until is correctly populated on new V1.1 opportunities
I. OutcomeRecord persists and links to the opportunity
J. repeated lifecycle resolution is idempotent (no duplicate RESOLVED event)
K. no duplicate OutcomeRecords for the same opportunity
L. existing (pre-RESOLVED) lifecycle records remain readable
M. assessment/detection behavior is unchanged (BUY/SELL still produced)

These tests never fabricate historical outcomes and never alter the detection,
EMA/RSI/ATR, SNR, or R:R semantics.
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.opportunity_intelligence.domain import (
    LifecycleState,
    OpportunityOutcome,
)
from app.opportunity_intelligence.persistence import (
    OutcomeMemoryRepository,
)
from app.opportunity_intelligence.repositories.queries import (
    EntityAsOfQuery,
    EntityId,
)
from app.opportunity_intelligence.services import ServiceContractError
from app.outcome_resolution.service import (
    OutcomeResolutionService,
    _determine_entry,
    _determine_outcome,
)

from tests.test_outcome_resolution import _make_plan
from tests.test_runtime_assessment import _assessment_fixture
from tests.test_runtime_lifecycle import _lifecycle_fixture


_NOW = datetime.now(timezone.utc)
_SIGNAL = _NOW - timedelta(minutes=5)


def _run(direction, candles, *, ref=Decimal("100"), entry_lower=Decimal("99.5"),
         entry_upper=Decimal("100.5"), inv=Decimal("98"), target=Decimal("103")):
    return _determine_outcome(
        direction=direction,
        reference_price=ref,
        entry_zone_lower=entry_lower,
        entry_zone_upper=entry_upper,
        invalidation_price=inv,
        target_price=target,
        signal_timestamp=_SIGNAL,
        valid_until=_NOW + timedelta(minutes=20),
        candles=candles,
    )


class GranularOutcomeTests(unittest.TestCase):
    def test_a_buy_target_first(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "BUY",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("100.1"),
              "high": Decimal("103.5"), "low": Decimal("99.8"),
              "close": Decimal("103.0"), "volume": Decimal("100")},),
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(price, Decimal("103"))

    def test_b_buy_stop_first(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "BUY",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("100.1"),
              "high": Decimal("101.0"), "low": Decimal("97.5"),
              "close": Decimal("98.0"), "volume": Decimal("100")},),
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)
        self.assertEqual(price, Decimal("98"))

    def test_c_buy_entry_never_reached(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "BUY",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("99.0"),
              "high": Decimal("99.0"), "low": Decimal("98.6"),
              "close": Decimal("98.8"), "volume": Decimal("100")},),
        )
        self.assertEqual(outcome, OpportunityOutcome.EXPIRED_BEFORE_ENTRY)
        self.assertIsNone(price)

    def test_d_buy_entry_no_barrier(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "BUY",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("100.1"),
              "high": Decimal("101.0"), "low": Decimal("99.0"),
              "close": Decimal("100.5"), "volume": Decimal("100")},),
        )
        self.assertEqual(outcome, OpportunityOutcome.EXPIRED_AFTER_ENTRY)
        self.assertIsNone(price)

    def test_e_sell_target_first(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "SELL",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("100.1"),
              "high": Decimal("100.5"), "low": Decimal("96.5"),
              "close": Decimal("97.0"), "volume": Decimal("100")},),
            inv=Decimal("102"), target=Decimal("97"),
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(price, Decimal("97"))

    def test_f_sell_stop_first(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "SELL",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("100.1"),
              "high": Decimal("102.5"), "low": Decimal("99.8"),
              "close": Decimal("102.0"), "volume": Decimal("100")},),
            inv=Decimal("102"), target=Decimal("97"),
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)
        self.assertEqual(price, Decimal("102"))

    def test_g_ambiguous_intrabar(self) -> None:
        outcome, count, price, ts, idx, reason = _run(
            "BUY",
            ({"timestamp": _SIGNAL + timedelta(minutes=1), "open": Decimal("100.1"),
              "high": Decimal("103.5"), "low": Decimal("97.5"),
              "close": Decimal("100.0"), "volume": Decimal("100")},),
        )
        self.assertEqual(outcome, OpportunityOutcome.AMBIGUOUS_INTRABAR)
        self.assertIsNone(price)
        self.assertEqual(reason, "ambiguous_intrabar")

    def test_determine_entry_reached_and_not(self) -> None:
        candle_in = {"timestamp": _SIGNAL + timedelta(minutes=1),
                     "open": Decimal("100.1"), "high": Decimal("103.5"),
                     "low": Decimal("99.8"), "close": Decimal("103.0"),
                     "volume": Decimal("100")}
        reached, ts, idx = _determine_entry(
            "BUY", Decimal("99.5"), Decimal("100.5"), _SIGNAL, (candle_in,))
        self.assertTrue(reached)
        self.assertEqual(ts, candle_in["timestamp"])
        self.assertEqual(idx, 0)

        candle_out = {"timestamp": _SIGNAL + timedelta(minutes=1),
                      "open": Decimal("99.0"), "high": Decimal("99.0"),
                      "low": Decimal("98.6"), "close": Decimal("98.8"),
                      "volume": Decimal("100")}
        reached, ts, idx = _determine_entry(
            "BUY", Decimal("99.5"), Decimal("100.5"), _SIGNAL, (candle_out,))
        self.assertFalse(reached)
        self.assertIsNone(ts)


class ValidUntilPopulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_h_v1_plan_persists_valid_until(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        opportunity = await service.assess(
            fixture.candidate, evidence, fixture.context
        )
        self.assertIsNotNone(opportunity.plan)
        self.assertIsNotNone(opportunity.plan.valid_until)
        self.assertIsNotNone(opportunity.valid_until)
        self.assertEqual(
            opportunity.plan.valid_until,
            opportunity.plan.audit.available_at + timedelta(minutes=10),
        )
        self.assertEqual(opportunity.valid_until, opportunity.plan.valid_until)


class OutcomeRecordPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def _resolve(self, direction="BUY", *, hit_target=True):
        if direction == "BUY":
            plan = _make_plan(direction="BUY")
            candle = {
                "timestamp": _SIGNAL + timedelta(minutes=1),
                "open": Decimal("100.1"),
                "high": Decimal("103.5") if hit_target else Decimal("101.0"),
                "low": Decimal("99.8") if hit_target else Decimal("97.5"),
                "close": Decimal("103.0") if hit_target else Decimal("98.0"),
                "volume": Decimal("100"),
            }
        else:
            plan = _make_plan(
                direction="SELL",
                invalidation=Decimal("102"),
                target=Decimal("97"),
            )
            candle = {
                "timestamp": _SIGNAL + timedelta(minutes=1),
                "open": Decimal("100.1"),
                "high": Decimal("102.5") if not hit_target else Decimal("100.5"),
                "low": Decimal("99.8") if not hit_target else Decimal("96.5"),
                "close": Decimal("102.0") if not hit_target else Decimal("97.0"),
                "volume": Decimal("100"),
            }

        class _FakeCandleQuery:
            async def query(self, instrument, timeframe, after, up_to_and_including):
                return (candle,)

        service = OutcomeResolutionService(candle_query=_FakeCandleQuery())
        return await service.resolve(
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            direction=direction,
            signal_timestamp=_SIGNAL,
            evidence_cutoff=_SIGNAL,
            plan=plan,
        )

    async def test_i_record_persists_and_links(self) -> None:
        record = await self._resolve()
        repo = OutcomeMemoryRepository()
        await repo.save(record)
        stored = await repo.get_by_opportunity(
            EntityAsOfQuery(EntityId("opp.test.12345"), record.resolved_at)
        )
        self.assertEqual(stored.opportunity_id, "opp.test.12345")
        self.assertEqual(stored.outcome, OpportunityOutcome.TARGET_HIT)
        self.assertTrue(stored.entry_reached)
        self.assertIsNotNone(stored.entry_timestamp)
        self.assertEqual(stored.first_barrier, "TARGET")

    async def test_k_no_duplicate_records(self) -> None:
        record = await self._resolve()
        repo = OutcomeMemoryRepository()
        await repo.save(record)
        await repo.save(record)
        stored = await repo.get_by_opportunity(
            EntityAsOfQuery(EntityId("opp.test.12345"), record.resolved_at)
        )
        self.assertEqual(stored.outcome_id, record.outcome_id)


class LifecycleResolutionIdempotencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_j_ranked_resolve_then_reject_duplicate(self) -> None:
        _, opportunity, qualification, ranking, service, lifecycles = (
            await _lifecycle_fixture()
        )
        lifecycle = await service.advance(opportunity, qualification, ranking, None)
        self.assertEqual(lifecycle.current_state, LifecycleState.RANKED)

        as_of = datetime.now(timezone.utc)
        resolved = await service.resolve_outcome(
            lifecycle, OpportunityOutcome.TARGET_HIT, as_of
        )
        self.assertEqual(resolved.current_state, LifecycleState.RESOLVED)
        self.assertEqual(
            resolved.events[-1].reason_code, "outcome.target_hit"
        )

        # Idempotency: a second resolution must raise, never append a second
        # RESOLVED event or create a duplicate OutcomeRecord.
        with self.assertRaises(ServiceContractError):
            await service.resolve_outcome(
                resolved, OpportunityOutcome.TARGET_HIT, as_of
            )
        stored = await lifecycles.get_current(
            EntityAsOfQuery(EntityId(lifecycle.opportunity_id), as_of)
        )
        resolved_events = [
            e for e in stored.events
            if e.resulting_state is LifecycleState.RESOLVED
        ]
        self.assertEqual(len(resolved_events), 1)

    async def test_j_expired_resolves_to_resolved(self) -> None:
        _, opportunity, qualification, ranking, service, lifecycles = (
            await _lifecycle_fixture()
        )
        lifecycle = await service.advance(opportunity, qualification, ranking, None)
        as_of = datetime.now(timezone.utc) + timedelta(minutes=20)
        await service.expire_stale(as_of=as_of, active_max_age_minutes=10)
        expired = await lifecycles.get_current(
            EntityAsOfQuery(EntityId(lifecycle.opportunity_id), as_of)
        )
        self.assertEqual(expired.current_state, LifecycleState.EXPIRED)

        resolved = await service.resolve_outcome(
            expired, OpportunityOutcome.EXPIRED_AFTER_ENTRY, as_of
        )
        self.assertEqual(resolved.current_state, LifecycleState.RESOLVED)

    async def test_l_pre_resolved_lifecycle_remains_readable(self) -> None:
        _, opportunity, qualification, ranking, service, lifecycles = (
            await _lifecycle_fixture()
        )
        lifecycle = await service.advance(opportunity, qualification, ranking, None)
        as_of = datetime.now(timezone.utc) + timedelta(minutes=20)
        await service.expire_stale(as_of=as_of, active_max_age_minutes=10)
        stored = await lifecycles.get_current(
            EntityAsOfQuery(EntityId(lifecycle.opportunity_id), as_of)
        )
        # No RESOLVED event was appended; the historical record stays EXPIRED
        # and remains readable.
        self.assertEqual(stored.current_state, LifecycleState.EXPIRED)
        self.assertNotIn(
            LifecycleState.RESOLVED,
            [e.resulting_state for e in stored.events],
        )


class AssessmentUnchangedTests(unittest.IsolatedAsyncioTestCase):
    async def test_m_buy_still_produced(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "101.000000000000000000",
            "100.000000000000000000",
            "55.000000000000000000",
        )
        opportunity = await service.assess(fixture.candidate, evidence, fixture.context)
        self.assertEqual(opportunity.stance.value, "BUY")

    async def test_m_sell_still_produced(self) -> None:
        fixture, service, evidence, opportunities = await _assessment_fixture(
            "99.000000000000000000",
            "100.000000000000000000",
            "45.000000000000000000",
        )
        opportunity = await service.assess(fixture.candidate, evidence, fixture.context)
        self.assertEqual(opportunity.stance.value, "SELL")


if __name__ == "__main__":
    unittest.main()
