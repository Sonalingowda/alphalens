"""Tests for V2 opportunity outcome resolution.

Covers:
  - BUY TARGET_HIT
  - SELL TARGET_HIT
  - BUY STOP_HIT
  - SELL STOP_HIT
  - EXPIRED (no barrier touched)
  - UNRESOLVED (dual-touch in same candle)
  - UNRESOLVED (BUY dual-touch)
  - UNRESOLVED (SELL dual-touch)
  - Chronology: first-touch order matters
  - Chronology: stop before target
  - Chronology: target before stop
  - Exact equality on boundary (BUY target exact hit)
  - Exact equality on boundary (BUY stop exact hit)
  - Exact equality on boundary (SELL target exact hit)
  - Exact equality on boundary (SELL stop exact hit)
  - Idempotency: same input produces same output
  - No mutation: OutcomeRecord is frozen
  - Service: resolve produces valid OutcomeRecord
  - Service: no-plan raises error
  - Service: missing valid_until raises error
  - OutcomeMemoryRepository: save and retrieve
  - OutcomeMemoryRepository: idempotent save
"""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.outcome_resolution.service import (
    OutcomeResolutionService,
    OpportunityOutcomeError,
    _determine_outcome,
)
from app.opportunity_intelligence.domain import (
    AuditMetadata,
    IntegrityReference,
    MarketScope,
    OpportunityOutcome,
    OpportunityPlan,
    OpportunityStance,
    OutcomeRecord,
    PlanTarget,
    PolicyReference,
    PriceRange,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.persistence import (
    OutcomeMemoryRepository,
)
from app.opportunity_intelligence.repositories.queries import (
    EntityAsOfQuery,
    EntityId,
)


_POLICY = PolicyReference(
    policy_id="test_outcome_policy",
    policy_version="1.0.0",
    integrity_digest="0" * 64,
)

_NOW = datetime.now(timezone.utc)
_SIGNAL_TIME = _NOW - timedelta(minutes=5)
_VALID_UNTIL = _NOW + timedelta(minutes=20)
_RESOLVED_AT = _NOW + timedelta(minutes=25)


def _make_plan(
    *,
    direction: str = "BUY",
    reference_price: Decimal = Decimal("100.000000000000000000"),
    entry_lower: Decimal = Decimal("99.500000000000000000"),
    entry_upper: Decimal = Decimal("100.500000000000000000"),
    invalidation: Decimal = Decimal("98.000000000000000000"),
    target: Decimal = Decimal("103.000000000000000000"),
    valid_until: datetime | None = _VALID_UNTIL,
) -> OpportunityPlan:
    stance = OpportunityStance.BUY if direction == "BUY" else OpportunityStance.SELL
    return OpportunityPlan(
        contract_version="2.0.0",
        plan_id="plan.test.opp.v1",
        opportunity_id="opp.test.12345",
        assessment_id="assess.test.12345",
        decision_id="decision.test.12345",
        policy=_POLICY,
        scope=MarketScope(instrument="BTCUSDT", timeframe="5m"),
        direction=stance,
        reference_price=reference_price,
        reference_price_source=IntegrityReference(
            artifact_id="price.test.12345",
            artifact_type="market_price",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=_SIGNAL_TIME,
        ),
        entry_zone=PriceRange(lower=entry_lower, upper=entry_upper),
        entry_semantics="next_candle_open",
        invalidation_price=invalidation,
        invalidation_condition="first_touch",
        targets=(
            PlanTarget(
                target_id="target.1",
                price=target,
                potential_reward=target - entry_upper,
                risk_reward=Decimal("2.000000000000000000"),
                evidence_references=(
                    IntegrityReference(
                        artifact_id="ev.target.1",
                        artifact_type="expected_move",
                        artifact_version="1.0.0",
                        integrity_digest="0" * 64,
                        available_at=_SIGNAL_TIME,
                    ),
                ),
            ),
        ),
        risk=Decimal("1.500000000000000000"),
        risk_unit="ATR14",
        assumptions=("test assumption",),
        limitations=("test limitation",),
        valid_until=valid_until,
        audit=AuditMetadata(
            created_at=_SIGNAL_TIME,
            evidence_cutoff=_SIGNAL_TIME,
            available_at=_SIGNAL_TIME,
            provenance=Provenance(
                source_references=(
                    IntegrityReference(
                        artifact_id="src.plan",
                        artifact_type="plan_source",
                        artifact_version="1.0.0",
                        integrity_digest="0" * 64,
                        available_at=_SIGNAL_TIME,
                    ),
                ),
                policy_references=(_POLICY,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        ),
    )


class BuyTargetHitTests(unittest.TestCase):
    def test_buy_target_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("103.5"), "low": Decimal("99.8"), "close": Decimal("103.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(count, 1)
        self.assertEqual(price, Decimal("103"))
        self.assertIsNone(reason)

    def test_buy_target_hit_second_candle(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("101.0"), "low": Decimal("99.8"), "close": Decimal("100.5"), "volume": Decimal("100")},
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=2), "open": Decimal("100.5"), "high": Decimal("103.5"), "low": Decimal("100.2"), "close": Decimal("103.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(count, 2)


class SellTargetHitTests(unittest.TestCase):
    def test_sell_target_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("100.5"), "low": Decimal("96.5"), "close": Decimal("97.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("102"),
            target_price=Decimal("97"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(count, 1)
        self.assertEqual(price, Decimal("97"))
        self.assertIsNone(reason)


class BuyStopHitTests(unittest.TestCase):
    def test_buy_stop_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("101.0"), "low": Decimal("97.5"), "close": Decimal("98.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)
        self.assertEqual(count, 1)
        self.assertEqual(price, Decimal("98"))
        self.assertIsNone(reason)


class SellStopHitTests(unittest.TestCase):
    def test_sell_stop_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("102.5"), "low": Decimal("99.8"), "close": Decimal("102.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("102"),
            target_price=Decimal("97"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)
        self.assertEqual(count, 1)
        self.assertEqual(price, Decimal("102"))
        self.assertIsNone(reason)


class ExpiredTests(unittest.TestCase):
    def test_expired_no_barrier_touched(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("101.0"), "low": Decimal("99.0"), "close": Decimal("100.5"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.EXPIRED_AFTER_ENTRY)
        self.assertEqual(count, 1)
        self.assertIsNone(price)
        self.assertIsNone(ts)
        self.assertIsNone(reason)

    def test_expired_empty_candles(self) -> None:
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=(),
        )
        self.assertEqual(outcome, OpportunityOutcome.DATA_INSUFFICIENT)
        self.assertEqual(count, 0)


class DualTouchTests(unittest.TestCase):
    def test_buy_dual_touch_same_candle(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("103.5"), "low": Decimal("97.5"), "close": Decimal("100.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.AMBIGUOUS_INTRABAR)
        self.assertEqual(count, 1)
        self.assertIsNone(price)
        self.assertEqual(reason, "ambiguous_intrabar")

    def test_sell_dual_touch_same_candle(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("102.5"), "low": Decimal("96.5"), "close": Decimal("100.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("102"),
            target_price=Decimal("97"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.AMBIGUOUS_INTRABAR)
        self.assertEqual(count, 1)
        self.assertIsNone(price)
        self.assertEqual(reason, "ambiguous_intrabar")


class ChronologyTests(unittest.TestCase):
    def test_stop_before_target(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("101.0"), "low": Decimal("97.5"), "close": Decimal("98.0"), "volume": Decimal("100")},
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=2), "open": Decimal("98.0"), "high": Decimal("103.5"), "low": Decimal("97.8"), "close": Decimal("103.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)

    def test_target_before_stop(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("103.5"), "low": Decimal("99.8"), "close": Decimal("103.0"), "volume": Decimal("100")},
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=2), "open": Decimal("103.0"), "high": Decimal("103.5"), "low": Decimal("97.5"), "close": Decimal("98.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)


class ExactBoundaryTests(unittest.TestCase):
    def test_buy_exact_target_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("103.0"), "low": Decimal("99.8"), "close": Decimal("103.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)

    def test_buy_exact_stop_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("101.0"), "low": Decimal("98.0"), "close": Decimal("100.5"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)

    def test_sell_exact_target_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("100.5"), "low": Decimal("97.0"), "close": Decimal("97.0"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("102"),
            target_price=Decimal("97"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.TARGET_HIT)

    def test_sell_exact_stop_hit(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("102.0"), "low": Decimal("99.8"), "close": Decimal("100.5"), "volume": Decimal("100")},
        )
        outcome, count, price, ts, idx, reason = _determine_outcome(
            direction="SELL",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("102"),
            target_price=Decimal("97"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(outcome, OpportunityOutcome.STOP_HIT)


class IdempotencyTests(unittest.TestCase):
    def test_same_input_same_output(self) -> None:
        candles = (
            {"timestamp": _SIGNAL_TIME + timedelta(minutes=1), "open": Decimal("100.1"), "high": Decimal("103.5"), "low": Decimal("99.8"), "close": Decimal("103.0"), "volume": Decimal("100")},
        )
        result1 = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        result2 = _determine_outcome(
            direction="BUY",
            reference_price=Decimal("100"),
            entry_zone_lower=Decimal("99.5"),
            entry_zone_upper=Decimal("100.5"),
            invalidation_price=Decimal("98"),
            target_price=Decimal("103"),
            signal_timestamp=_SIGNAL_TIME,
            valid_until=_VALID_UNTIL,
            candles=candles,
        )
        self.assertEqual(result1, result2)


class NoMutationTests(unittest.TestCase):
    def test_outcome_record_is_frozen(self) -> None:
        record = OutcomeRecord(
            contract_version="2.0.0",
            outcome_id="outcome.test.v1",
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            lifecycle_id="opp.test.12345",
            outcome=OpportunityOutcome.TARGET_HIT,
            direction="BUY",
            reference_price=Decimal("100.000000000000000000"),
            entry_zone_lower=Decimal("99.500000000000000000"),
            entry_zone_upper=Decimal("100.500000000000000000"),
            invalidation_price=Decimal("98.000000000000000000"),
            target_price=Decimal("103.000000000000000000"),
            signal_timestamp=_SIGNAL_TIME,
            outcome_interval_start=_SIGNAL_TIME,
            outcome_interval_end=_VALID_UNTIL,
            resolved_at=_RESOLVED_AT,
            candles_evaluated=1,
            first_touch_price=Decimal("103.000000000000000000"),
            first_touch_timestamp=_SIGNAL_TIME + timedelta(minutes=1),
            first_touch_candle_index=0,
            exclusion_reason=None,
            policy=_POLICY,
            evidence_references=(),
            audit=AuditMetadata(
                created_at=_SIGNAL_TIME,
                evidence_cutoff=_SIGNAL_TIME,
                available_at=_SIGNAL_TIME,
                provenance=Provenance(
                    source_references=(
                        IntegrityReference(
                            artifact_id="src.outcome",
                            artifact_type="test",
                            artifact_version="1.0.0",
                            integrity_digest="0" * 64,
                            available_at=_SIGNAL_TIME,
                        ),
                    ),
                    policy_references=(_POLICY,),
                    code_version="test",
                    configuration_hash="0" * 64,
                    lineage_hash="0" * 64,
                ),
                result_hash="0" * 64,
            ),
        )
        with self.assertRaises(AttributeError):
            record.outcome = OpportunityOutcome.STOP_HIT  # type: ignore[misc]


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def _make_opportunity(self, plan: OpportunityPlan):
        from app.opportunity_intelligence.domain import Opportunity, OpportunityStance
        return Opportunity(
            contract_version="1.0.0",
            opportunity_id=plan.opportunity_id,
            opportunity_version_id=f"{plan.opportunity_id}.v1",
            stance=plan.direction,
            assessment_id="assess.test.12345",
            decision_id="decision.test.12345",
            candidate_id="candidate.test.12345",
            scope=plan.scope,
            decision_policy=_POLICY,
            evidence_package_reference=IntegrityReference(
                artifact_id="evpkg.test.12345",
                artifact_type="evidence_package",
                artifact_version="1.0.0",
                integrity_digest="0" * 64,
                available_at=_SIGNAL_TIME,
            ),
            context_reference=IntegrityReference(
                artifact_id="ctx.test.12345",
                artifact_type="market_context",
                artifact_version="1.0.0",
                integrity_digest="0" * 64,
                available_at=_SIGNAL_TIME,
            ),
            reason_codes=("test.reason",),
            limitations=("test limitation",),
            qualification_reference=None,
            score_reference=None,
            confidence=None,
            plan=plan,
            valid_until=plan.valid_until,
            supersedes_opportunity_version_id=None,
            audit=AuditMetadata(
                created_at=_SIGNAL_TIME,
                evidence_cutoff=_SIGNAL_TIME,
                available_at=_SIGNAL_TIME,
                provenance=Provenance(
                    source_references=(
                        IntegrityReference(
                            artifact_id="src.opp",
                            artifact_type="test",
                            artifact_version="1.0.0",
                            integrity_digest="0" * 64,
                            available_at=_SIGNAL_TIME,
                        ),
                    ),
                    policy_references=(_POLICY,),
                    code_version="test",
                    configuration_hash="0" * 64,
                    lineage_hash="0" * 64,
                ),
                result_hash="0" * 64,
            ),
        )

    async def test_resolve_produces_valid_record(self) -> None:
        plan = _make_plan()
        opportunity = self._make_opportunity(plan)
        candle = {
            "timestamp": _SIGNAL_TIME + timedelta(minutes=1),
            "open": Decimal("100.1"),
            "high": Decimal("103.5"),
            "low": Decimal("99.8"),
            "close": Decimal("103.0"),
            "volume": Decimal("100"),
        }

        class _FakeCandleQuery:
            async def query(self, instrument, timeframe, after, up_to_and_including):
                return (candle,)

        service = OutcomeResolutionService(candle_query=_FakeCandleQuery())
        result = await service.resolve(
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            direction="BUY",
            signal_timestamp=_SIGNAL_TIME,
            evidence_cutoff=_SIGNAL_TIME,
            plan=plan,
        )

        self.assertIsInstance(result, OutcomeRecord)
        self.assertEqual(result.outcome, OpportunityOutcome.TARGET_HIT)
        self.assertEqual(result.opportunity_id, "opp.test.12345")
        self.assertEqual(result.candles_evaluated, 1)
        self.assertIsNotNone(result.first_touch_price)

    async def test_resolve_expired(self) -> None:
        plan = _make_plan()
        opportunity = self._make_opportunity(plan)
        candle = {
            "timestamp": _SIGNAL_TIME + timedelta(minutes=1),
            "open": Decimal("100.1"),
            "high": Decimal("101.0"),
            "low": Decimal("99.0"),
            "close": Decimal("100.5"),
            "volume": Decimal("100"),
        }

        class _FakeCandleQuery:
            async def query(self, instrument, timeframe, after, up_to_and_including):
                return (candle,)

        service = OutcomeResolutionService(candle_query=_FakeCandleQuery())
        result = await service.resolve(
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            direction="BUY",
            signal_timestamp=_SIGNAL_TIME,
            evidence_cutoff=_SIGNAL_TIME,
            plan=plan,
        )

        self.assertEqual(result.outcome, OpportunityOutcome.EXPIRED_AFTER_ENTRY)
        self.assertIsNone(result.first_touch_price)

    async def test_resolve_no_plan_raises(self) -> None:
        from dataclasses import replace
        from app.opportunity_intelligence.domain.plan import OpportunityPlan

        plan_no_valid_until = replace(_make_plan(), valid_until=None)

        class _FakeCandleQuery:
            async def query(self, instrument, timeframe, after, up_to_and_including):
                return ()

        service = OutcomeResolutionService(candle_query=_FakeCandleQuery())
        with self.assertRaises(OpportunityOutcomeError):
            await service.resolve(
                opportunity_id="opp.test.12345",
                opportunity_version_id="opp.test.12345.v1",
                direction="BUY",
                signal_timestamp=_SIGNAL_TIME,
                evidence_cutoff=_SIGNAL_TIME,
                plan=plan_no_valid_until,
            )


class OutcomeMemoryRepositoryTests(unittest.IsolatedAsyncioTestCase):
    def _make_record(self, outcome: OpportunityOutcome = OpportunityOutcome.TARGET_HIT) -> OutcomeRecord:
        return OutcomeRecord(
            contract_version="2.0.0",
            outcome_id="outcome.test.v1",
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            lifecycle_id="opp.test.12345",
            outcome=outcome,
            direction="BUY",
            reference_price=Decimal("100.000000000000000000"),
            entry_zone_lower=Decimal("99.500000000000000000"),
            entry_zone_upper=Decimal("100.500000000000000000"),
            invalidation_price=Decimal("98.000000000000000000"),
            target_price=Decimal("103.000000000000000000"),
            signal_timestamp=_SIGNAL_TIME,
            outcome_interval_start=_SIGNAL_TIME,
            outcome_interval_end=_VALID_UNTIL,
            resolved_at=_RESOLVED_AT,
            candles_evaluated=1,
            first_touch_price=Decimal("103.000000000000000000") if outcome in (OpportunityOutcome.TARGET_HIT, OpportunityOutcome.STOP_HIT, OpportunityOutcome.UNRESOLVED) else None,
            first_touch_timestamp=_SIGNAL_TIME + timedelta(minutes=1) if outcome in (OpportunityOutcome.TARGET_HIT, OpportunityOutcome.STOP_HIT, OpportunityOutcome.UNRESOLVED) else None,
            first_touch_candle_index=0 if outcome in (OpportunityOutcome.TARGET_HIT, OpportunityOutcome.STOP_HIT, OpportunityOutcome.UNRESOLVED) else None,
            exclusion_reason=None,
            policy=_POLICY,
            evidence_references=(),
            audit=AuditMetadata(
                created_at=_SIGNAL_TIME,
                evidence_cutoff=_SIGNAL_TIME,
                available_at=_SIGNAL_TIME,
                provenance=Provenance(
                    source_references=(
                        IntegrityReference(
                            artifact_id="src.outcome",
                            artifact_type="test",
                            artifact_version="1.0.0",
                            integrity_digest="0" * 64,
                            available_at=_SIGNAL_TIME,
                        ),
                    ),
                    policy_references=(_POLICY,),
                    code_version="test",
                    configuration_hash="0" * 64,
                    lineage_hash="0" * 64,
                ),
                result_hash="0" * 64,
            ),
        )

    async def test_save_and_retrieve(self) -> None:
        repo = OutcomeMemoryRepository()
        record = self._make_record()
        await repo.save(record)
        result = await repo.get_by_opportunity(
            EntityAsOfQuery(
                entity_id=EntityId("opp.test.12345"),
                as_of=_NOW,
            )
        )
        self.assertEqual(result.outcome, OpportunityOutcome.TARGET_HIT)

    async def test_idempotent_save(self) -> None:
        repo = OutcomeMemoryRepository()
        record = self._make_record()
        await repo.save(record)
        await repo.save(record)
        result = await repo.get_by_opportunity(
            EntityAsOfQuery(
                entity_id=EntityId("opp.test.12345"),
                as_of=_NOW,
            )
        )
        self.assertEqual(result.outcome, OpportunityOutcome.TARGET_HIT)

    async def test_different_outcomes_saved_separately(self) -> None:
        from app.opportunity_intelligence.domain import OutcomeRecord as OR
        from dataclasses import replace

        repo = OutcomeMemoryRepository()
        record1 = self._make_record(OpportunityOutcome.TARGET_HIT)
        record2 = replace(
            record1,
            outcome_id="outcome.test.v2",
            outcome=OpportunityOutcome.STOP_HIT,
            first_touch_price=Decimal("98.000000000000000000"),
        )
        await repo.save(record1)
        await repo.save(record2)

        result1 = await repo.get_by_opportunity(
            EntityAsOfQuery(
                entity_id=EntityId("opp.test.12345"),
                as_of=_NOW,
            )
        )
        self.assertEqual(result1.outcome, OpportunityOutcome.STOP_HIT)


class OutcomeRecordValidationTests(unittest.TestCase):
    def test_invalidated_requires_reason(self) -> None:
        with self.assertRaises(Exception):
            OutcomeRecord(
                contract_version="2.0.0",
                outcome_id="outcome.test.v1",
                opportunity_id="opp.test.12345",
                opportunity_version_id="opp.test.12345.v1",
                lifecycle_id="opp.test.12345",
                outcome=OpportunityOutcome.INVALIDATED,
                direction="BUY",
                reference_price=Decimal("100.000000000000000000"),
                entry_zone_lower=Decimal("99.500000000000000000"),
                entry_zone_upper=Decimal("100.500000000000000000"),
                invalidation_price=Decimal("98.000000000000000000"),
                target_price=Decimal("103.000000000000000000"),
                signal_timestamp=_SIGNAL_TIME,
                outcome_interval_start=_SIGNAL_TIME,
                outcome_interval_end=_VALID_UNTIL,
                resolved_at=_RESOLVED_AT,
                candles_evaluated=0,
                first_touch_price=None,
                first_touch_timestamp=None,
                first_touch_candle_index=None,
                exclusion_reason=None,
                policy=_POLICY,
                evidence_references=(),
                audit=AuditMetadata(
                    created_at=_SIGNAL_TIME,
                    evidence_cutoff=_SIGNAL_TIME,
                    available_at=_SIGNAL_TIME,
                    provenance=Provenance(
                        source_references=(
                            IntegrityReference(
                                artifact_id="src.outcome",
                                artifact_type="test",
                                artifact_version="1.0.0",
                                integrity_digest="0" * 64,
                                available_at=_SIGNAL_TIME,
                            ),
                        ),
                        policy_references=(_POLICY,),
                        code_version="test",
                        configuration_hash="0" * 64,
                        lineage_hash="0" * 64,
                    ),
                    result_hash="0" * 64,
                ),
            )

    def test_target_hit_requires_first_touch(self) -> None:
        with self.assertRaises(Exception):
            OutcomeRecord(
                contract_version="2.0.0",
                outcome_id="outcome.test.v1",
                opportunity_id="opp.test.12345",
                opportunity_version_id="opp.test.12345.v1",
                lifecycle_id="opp.test.12345",
                outcome=OpportunityOutcome.TARGET_HIT,
                direction="BUY",
                reference_price=Decimal("100.000000000000000000"),
                entry_zone_lower=Decimal("99.500000000000000000"),
                entry_zone_upper=Decimal("100.500000000000000000"),
                invalidation_price=Decimal("98.000000000000000000"),
                target_price=Decimal("103.000000000000000000"),
                signal_timestamp=_SIGNAL_TIME,
                outcome_interval_start=_SIGNAL_TIME,
                outcome_interval_end=_VALID_UNTIL,
                resolved_at=_RESOLVED_AT,
                candles_evaluated=1,
                first_touch_price=None,
                first_touch_timestamp=None,
                first_touch_candle_index=None,
                exclusion_reason=None,
                policy=_POLICY,
                evidence_references=(),
                audit=AuditMetadata(
                    created_at=_SIGNAL_TIME,
                    evidence_cutoff=_SIGNAL_TIME,
                    available_at=_SIGNAL_TIME,
                    provenance=Provenance(
                        source_references=(
                            IntegrityReference(
                                artifact_id="src.outcome",
                                artifact_type="test",
                                artifact_version="1.0.0",
                                integrity_digest="0" * 64,
                                available_at=_SIGNAL_TIME,
                            ),
                        ),
                        policy_references=(_POLICY,),
                        code_version="test",
                        configuration_hash="0" * 64,
                        lineage_hash="0" * 64,
                    ),
                    result_hash="0" * 64,
                ),
            )

    def test_expired_no_first_touch(self) -> None:
        record = OutcomeRecord(
            contract_version="2.0.0",
            outcome_id="outcome.test.v1",
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            lifecycle_id="opp.test.12345",
            outcome=OpportunityOutcome.EXPIRED,
            direction="BUY",
            reference_price=Decimal("100.000000000000000000"),
            entry_zone_lower=Decimal("99.500000000000000000"),
            entry_zone_upper=Decimal("100.500000000000000000"),
            invalidation_price=Decimal("98.000000000000000000"),
            target_price=Decimal("103.000000000000000000"),
            signal_timestamp=_SIGNAL_TIME,
            outcome_interval_start=_SIGNAL_TIME,
            outcome_interval_end=_VALID_UNTIL,
            resolved_at=_RESOLVED_AT,
            candles_evaluated=1,
            first_touch_price=None,
            first_touch_timestamp=None,
            first_touch_candle_index=None,
            exclusion_reason=None,
            policy=_POLICY,
            evidence_references=(),
            audit=AuditMetadata(
                created_at=_SIGNAL_TIME,
                evidence_cutoff=_SIGNAL_TIME,
                available_at=_SIGNAL_TIME,
                provenance=Provenance(
                    source_references=(
                        IntegrityReference(
                            artifact_id="src.outcome",
                            artifact_type="test",
                            artifact_version="1.0.0",
                            integrity_digest="0" * 64,
                            available_at=_SIGNAL_TIME,
                        ),
                    ),
                    policy_references=(_POLICY,),
                    code_version="test",
                    configuration_hash="0" * 64,
                    lineage_hash="0" * 64,
                ),
                result_hash="0" * 64,
            ),
        )
        self.assertEqual(record.outcome, OpportunityOutcome.EXPIRED)
        self.assertIsNone(record.first_touch_price)


class V1Dot1SweepWindowDerivationTests(unittest.IsolatedAsyncioTestCase):
    """Documented V1.1 exception (authorized): when a V1.1 plan carries no
    validity window, the lifecycle sweep derives the resolution horizon from
    the established 10-minute active-expiration policy. The persisted plan
    artifact is unchanged; EXPIRED then resolves canonically and
    idempotently."""

    def _derivation(self, plan):
        from dataclasses import replace

        return replace(
            plan,
            valid_until=plan.audit.evidence_cutoff + timedelta(minutes=10),
        )

    async def test_v1_1_derived_window_resolves_expired_idempotently(self) -> None:
        plan = _make_plan(valid_until=None)
        self.assertIsNone(plan.valid_until)

        derived = self._derivation(plan)

        candles = tuple(
            {
                "timestamp": _SIGNAL_TIME + timedelta(minutes=1 + i),
                "open": Decimal("100.000000000000000000"),
                "high": Decimal("100.200000000000000000"),
                "low": Decimal("99.800000000000000000"),
                "close": Decimal("100.000000000000000000"),
                "volume": Decimal("10"),
            }
            for i in range(14)
        )

        evaluated = []

        class _WindowedCandleQuery:
            async def query(self, instrument, timeframe, after, up_to_and_including):
                selected = tuple(
                    candle
                    for candle in candles
                    if after < candle["timestamp"] <= up_to_and_including
                )
                evaluated.append(len(selected))
                return selected

        service = OutcomeResolutionService(candle_query=_WindowedCandleQuery())
        record_one = await service.resolve(
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            direction="BUY",
            signal_timestamp=_SIGNAL_TIME,
            evidence_cutoff=_SIGNAL_TIME,
            plan=derived,
            source_integrity_digest=derived.canonical_sha256(),
        )
        record_two = await service.resolve(
            opportunity_id="opp.test.12345",
            opportunity_version_id="opp.test.12345.v1",
            direction="BUY",
            signal_timestamp=_SIGNAL_TIME,
            evidence_cutoff=_SIGNAL_TIME,
            plan=derived,
            source_integrity_digest=derived.canonical_sha256(),
        )

        self.assertEqual(record_one.outcome, OpportunityOutcome.EXPIRED_AFTER_ENTRY)
        self.assertEqual(evaluated[-1], 10)
        self.assertEqual(record_one, record_two)
        self.assertEqual(record_one.outcome_id, "outcome.opp.test.12345.v1")
        self.assertIsNone(plan.valid_until)
        self.assertEqual(derived.valid_until, _SIGNAL_TIME + timedelta(minutes=10))

if __name__ == "__main__":
    unittest.main()
