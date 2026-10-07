"""Focused Phase 12B tests for isolated OpportunityVersion paper execution."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    IntegrityReference,
    MarketScope,
    Opportunity,
    OpportunityPlan,
    OpportunityStance,
    PlanTarget,
    PolicyReference,
    PriceRange,
    Provenance,
    RankingMembership,
)
from app.paper_execution import (
    InMemoryPaperExecutionRepository,
    PaperExecutionService,
    PaperExitReason,
    PaperExecutionState,
    InMemoryPaperSuccessorPlanRepository,
    derive_successor_plan,
    eligible_opportunities,
    SUCCESSOR_POLICY_HASH,
    SUCCESSOR_POLICY_ID,
    SUCCESSOR_POLICY_VERSION,
)


NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
UNTIL = NOW + timedelta(minutes=20)
ZERO = "0" * 64
POLICY = PolicyReference("paper_test_policy", "1.0.0", ZERO)


def ref(identifier: str) -> IntegrityReference:
    return IntegrityReference(identifier, "test", "1.0.0", ZERO, NOW)


def opportunity(version: str = "opp.version.1") -> tuple[Opportunity, RankingMembership]:
    plan = OpportunityPlan(
        contract_version="2.0.0", plan_id=f"plan.{version}", opportunity_id="opp.1",
        assessment_id="assessment.1", decision_id="decision.1", policy=POLICY,
        scope=MarketScope("BTCUSDT", "5m"), direction=OpportunityStance.BUY,
        reference_price=Decimal("100.000000000000000000"), reference_price_source=ref("price"),
        entry_zone=PriceRange(Decimal("99.500000000000000000"), Decimal("100.500000000000000000")),
        entry_semantics="range_overlap", invalidation_price=Decimal("98.000000000000000000"),
        invalidation_condition="first_touch", targets=(PlanTarget(
            "target.1", Decimal("103.000000000000000000"), Decimal("2.500000000000000000"),
            Decimal("2.000000000000000000"), (ref("target"),)),),
        risk=Decimal("1.500000000000000000"), risk_unit="price", assumptions=("a",),
        limitations=("l",), valid_until=UNTIL,
        audit=AuditMetadata(NOW, NOW, NOW, Provenance((ref("plan-source"),), (POLICY,), "test", ZERO, ZERO), ZERO),
    )
    opp = Opportunity(
        contract_version="1.0.0", opportunity_id="opp.1", opportunity_version_id=version,
        assessment_id="assessment.1", decision_id="decision.1", candidate_id="candidate.1",
        scope=plan.scope, stance=OpportunityStance.BUY, decision_policy=POLICY,
        evidence_package_reference=ref("evidence"), context_reference=ref("context"),
        reason_codes=("ranked",), limitations=("l",), qualification_reference=ref("qualification"),
        score_reference=ref("score"), confidence=None, plan=plan, valid_until=UNTIL,
        supersedes_opportunity_version_id=None,
        audit=AuditMetadata(NOW, NOW, NOW, Provenance((ref("opportunity-source"),), (POLICY,), "test", ZERO, ZERO), ZERO),
    )
    membership = RankingMembership("opp.1", version, ref("qualification"), ref("score"), 1, 1, UNTIL)
    return opp, membership


def candle(minimum: str, maximum: str, minute: int = 1) -> dict:
    return {"timestamp": NOW + timedelta(minutes=minute), "open": Decimal("100"),
            "high": Decimal(maximum), "low": Decimal(minimum), "close": Decimal("100"),
            "volume": Decimal("1")}


class PaperExecutionTests(unittest.TestCase):
    def test_target_stop_expiry_data_and_ambiguous_semantics(self) -> None:
        service = PaperExecutionService()
        cases = (
            ((candle("99", "103.1"),), PaperExitReason.TARGET_HIT),
            ((candle("97.9", "100"),), PaperExitReason.STOP_HIT),
            ((candle("101", "102"),), PaperExitReason.EXPIRED_BEFORE_ENTRY),
            ((candle("99", "101"),), PaperExitReason.EXPIRED_AFTER_ENTRY),
            ((), PaperExitReason.DATA_INSUFFICIENT),
            ((candle("97", "103"),), PaperExitReason.AMBIGUOUS_INTRABAR),
        )
        for candles, expected in cases:
            with self.subTest(expected=expected):
                result = service.evaluate(opportunity=opportunity()[0], ranking_membership=opportunity()[1], candles=candles)
                self.assertEqual(result.outcome.reason, expected)
                self.assertEqual(result.execution.state, PaperExecutionState.CLOSED)

    def test_identity_lineage_and_overlapping_independence(self) -> None:
        service = PaperExecutionService()
        first, membership = opportunity("opp.version.1")
        second, membership2 = opportunity("opp.version.2")
        a = service.evaluate(opportunity=first, ranking_membership=membership, candles=(candle("99", "100.5"),))
        b = service.evaluate(opportunity=second, ranking_membership=membership2, candles=(candle("99", "100.5"),))
        self.assertEqual(a.execution.execution_id, "paper_execution:opp.version.1")
        self.assertEqual(a.position.position_id, "paper_position:opp.version.1")
        self.assertEqual(a.position.execution_id, a.execution.execution_id)
        self.assertEqual(a.exit.exit_id, "paper_exit:opp.version.1")
        self.assertEqual(a.exit.position_id, a.position.position_id)
        self.assertNotEqual(a.execution.execution_id, b.execution.execution_id)
        self.assertEqual(a.outcome.source_execution_hash, a.execution.canonical_sha256())
        self.assertEqual(a.outcome.source_position_hash, a.position.canonical_sha256())
        self.assertEqual(a.outcome.source_exit_hash, a.exit.canonical_sha256())
        self.assertTrue(a.execution.source_references)

    def test_signal_and_validity_boundaries_are_enforced(self) -> None:
        opp, membership = opportunity()
        service = PaperExecutionService()
        before_signal = candle("99", "103", minute=0)
        after_validity = candle("99", "103", minute=21)
        result = service.evaluate(
            opportunity=opp,
            ranking_membership=membership,
            candles=(before_signal, after_validity),
        )
        self.assertEqual(result.outcome.reason, PaperExitReason.DATA_INSUFFICIENT)

    def test_same_version_is_idempotent(self) -> None:
        opp, membership = opportunity()
        service = PaperExecutionService()
        repository = InMemoryPaperExecutionRepository()
        first = service.evaluate(opportunity=opp, ranking_membership=membership, candles=())
        second = service.evaluate(opportunity=opp, ranking_membership=membership, candles=())
        saved_first = repository.save(first.execution, first.position, first.exit, first.outcome)
        saved_second = repository.save(second.execution, second.position, second.exit, second.outcome)
        self.assertIs(saved_first, saved_second)

    def test_only_matching_real_ranking_membership_is_accepted(self) -> None:
        opp, membership = opportunity()
        with self.assertRaises(ValueError):
            PaperExecutionService().evaluate(opportunity=opp, ranking_membership=opportunity("opp.version.other")[1], candles=())

    def test_successor_preserves_source_and_derives_only_validity(self) -> None:
        source, membership = opportunity("opp.version.successor")
        policy = PolicyReference(SUCCESSOR_POLICY_ID, SUCCESSOR_POLICY_VERSION, SUCCESSOR_POLICY_HASH)
        plan = replace(source.plan, policy=policy, scope=MarketScope("BTCUSDT", "5m"))
        source = replace(source, plan=plan, decision_policy=policy)
        successor = derive_successor_plan(opportunity=source, ranking_membership=membership)
        self.assertEqual(successor.source_plan_id, plan.plan_id)
        self.assertEqual(successor.source_plan_canonical_hash, plan.canonical_sha256())
        self.assertEqual(successor.plan.audit.available_at, plan.audit.available_at)
        self.assertEqual(successor.plan.valid_until, plan.audit.available_at + timedelta(minutes=10))
        self.assertNotEqual(successor.successor_plan_canonical_hash, successor.source_plan_canonical_hash)
        self.assertEqual(successor.plan.reference_price, plan.reference_price)
        self.assertEqual(successor.plan.entry_zone, plan.entry_zone)
        self.assertEqual(successor.plan.invalidation_price, plan.invalidation_price)
        self.assertEqual(successor.plan.targets, plan.targets)

    def test_successor_is_idempotent_and_paper_service_accepts_it(self) -> None:
        source, membership = opportunity("opp.version.successor.idempotent")
        policy = PolicyReference(SUCCESSOR_POLICY_ID, SUCCESSOR_POLICY_VERSION, SUCCESSOR_POLICY_HASH)
        plan = replace(source.plan, policy=policy, scope=MarketScope("BTCUSDT", "5m"))
        source = replace(source, plan=plan, decision_policy=policy)
        successor = derive_successor_plan(opportunity=source, ranking_membership=membership)
        repository = InMemoryPaperSuccessorPlanRepository()
        self.assertIs(repository.save(successor), repository.save(successor))
        result = PaperExecutionService().evaluate_successor(
            opportunity=source,
            ranking_membership=membership,
            successor=successor,
            candles=(),
        )
        self.assertEqual(result.execution.execution_id, "paper_execution:opp.version.successor.idempotent")
        self.assertEqual(result.execution.source_plan_id, successor.source_plan_id)
        self.assertEqual(result.execution.successor_plan_id, successor.successor_plan_id)
        self.assertEqual(result.execution.plan_hash, successor.successor_plan_canonical_hash)

    def test_eligibility_requires_ranked_v11_matching_plan_and_scope(self) -> None:
        source, membership = opportunity("opp.version.eligible")
        policy = PolicyReference(SUCCESSOR_POLICY_ID, SUCCESSOR_POLICY_VERSION, SUCCESSOR_POLICY_HASH)
        source = replace(
            source,
            plan=replace(source.plan, policy=policy, scope=MarketScope("BTCUSDT", "5m")),
            decision_policy=policy,
        )
        v10, v10_membership = opportunity("opp.version.v10")
        missing_plan, missing_membership = opportunity("opp.version.missing")
        missing_plan = replace(missing_plan, plan=None, decision_policy=None, valid_until=None)
        self.assertEqual(
            eligible_opportunities((source, v10, missing_plan), (membership, v10_membership, missing_membership)),
            (source,),
        )


if __name__ == "__main__":
    unittest.main()
