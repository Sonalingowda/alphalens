"""Focused tests for the isolated Phase 13B review projection."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import asyncio
from types import SimpleNamespace

import pytest

from app.opportunity_intelligence.domain import (
    IntegrityReference,
    MarketScope,
    OpportunityStance,
    PolicyReference,
    PriceRange,
)
from app.review_projection import (
    HumanReviewProjectionService,
    ReviewValidity,
    ReviewProjectionIntegrityError,
)

UTC = timezone.utc
AS_OF = datetime(2026, 9, 25, 12, tzinfo=UTC)
SCOPE = MarketScope("BTCUSDT", "5m")
HASH = "a" * 64


def ref(identifier: str, available_at: datetime = AS_OF) -> IntegrityReference:
    return IntegrityReference(identifier, "evidence", "1.0.0", HASH, available_at)


@dataclass(frozen=True)
class FakePlan:
    plan_id: str
    opportunity_id: str
    assessment_id: str
    decision_id: str
    scope: MarketScope
    direction: OpportunityStance
    reference_price: Decimal
    entry_zone: PriceRange
    invalidation_price: Decimal
    targets: tuple[SimpleNamespace, ...]
    valid_until: datetime | None
    policy: PolicyReference
    audit: SimpleNamespace

    def canonical_sha256(self) -> str:
        return HASH


@dataclass(frozen=True)
class FakeOpportunity:
    opportunity_id: str
    opportunity_version_id: str
    assessment_id: str
    decision_id: str
    scope: MarketScope
    decision_policy: PolicyReference
    plan: FakePlan | None
    qualification_reference: IntegrityReference | None
    score_reference: IntegrityReference | None
    evidence_package_reference: IntegrityReference
    context_reference: IntegrityReference
    audit: SimpleNamespace

    def canonical_sha256(self) -> str:
        return HASH


def opportunity(version: str, rank: int, valid_until: datetime | None) -> FakeOpportunity:
    policy = PolicyReference("plan.policy", "1.0.0", HASH)
    decision_policy = PolicyReference("decision.policy", "1.0.0", HASH)
    provenance = SimpleNamespace(
        source_references=(ref(f"source.{version}"),),
        policy_references=(policy,),
    )
    audit = SimpleNamespace(provenance=provenance, available_at=AS_OF - timedelta(minutes=1))
    opportunity_provenance = SimpleNamespace(
        source_references=(ref(f"opportunity.source.{version}"),),
        policy_references=(decision_policy,),
    )
    plan = FakePlan(
        f"plan.{version}", f"opp.{version}", f"assessment.{version}", f"decision.{version}",
        SCOPE, OpportunityStance.BUY, Decimal("100"), PriceRange(Decimal("99"), Decimal("100")),
        Decimal("95"), (SimpleNamespace(price=Decimal("110")),), valid_until, policy, audit,
    )
    return FakeOpportunity(
        opportunity_id=f"opp.{version}",
        opportunity_version_id=version,
        assessment_id=f"assessment.{version}",
        decision_id=f"decision.{version}",
        scope=SCOPE,
        decision_policy=decision_policy,
        plan=plan,
        qualification_reference=ref(f"evidence.{version}"),
        score_reference=ref(f"context.{version}"),
        evidence_package_reference=ref(f"evidence.{version}"),
        context_reference=ref(f"context.{version}"),
        audit=SimpleNamespace(provenance=opportunity_provenance, available_at=AS_OF - timedelta(minutes=1)),
    )


def snapshot(items):
    memberships = tuple(SimpleNamespace(opportunity_id=o.opportunity_id, opportunity_version_id=o.opportunity_version_id, rank=rank, candidate_set_size=len(items)) for rank, o in enumerate(items, 1))
    return SimpleNamespace(snapshot_id="ranking.1", generated_at=AS_OF, memberships=memberships)


class Repo:
    def __init__(self, items):
        self.items = items

    async def list(self, query):
        return SimpleNamespace(items=self.items)


def service(items, ranked):
    return HumanReviewProjectionService(opportunities=Repo(items), rankings=Repo((snapshot(ranked),)))


def test_projection_filters_by_ranking_orders_and_hashes_deterministically():
    async def run():
        first = opportunity("version.b", 1, AS_OF + timedelta(minutes=5))
        second = opportunity("version.a", 2, AS_OF - timedelta(minutes=5))
        result = await service((first, second), (first, second)).build(scope=SCOPE, as_of=AS_OF)
        again = await service((first, second), (first, second)).build(scope=SCOPE, as_of=AS_OF)
        assert [item.opportunity_version_id for item in result.items] == ["version.b", "version.a"]
        assert result.items[0].validity_status is ReviewValidity.CURRENT
        assert result.items[1].validity_status is ReviewValidity.EXPIRED
        assert result.item_hashes == again.item_hashes
        assert result.manifest_hash == again.manifest_hash
        assert result.items[0].safety_designation == "INFORMATIONAL_ONLY_NO_EXECUTION"

    asyncio.run(run())


def test_missing_validity_is_explicitly_not_reviewable():
    async def run():
        item = opportunity("version.missing", 1, None)
        result = await service((item,), (item,)).build(scope=SCOPE, as_of=AS_OF)
        assert result.items[0].validity_status is ReviewValidity.NOT_REVIEWABLE_MISSING_VALIDITY

    asyncio.run(run())


@pytest.mark.parametrize("mutation", ["missing", "scope", "plan_identity", "lineage"])
def test_source_lineage_mismatch_fails_closed(mutation):
    async def run():
        item = opportunity("version.1", 1, AS_OF + timedelta(minutes=1))
        if mutation == "missing":
            ranked = (SimpleNamespace(opportunity_id="missing", opportunity_version_id="version.1", rank=1, candidate_set_size=1),)
            ranking = SimpleNamespace(snapshot_id="ranking.1", generated_at=AS_OF, memberships=ranked)
            projection = HumanReviewProjectionService(opportunities=Repo((item,)), rankings=Repo((ranking,)))
        else:
            if mutation == "scope":
                item = replace(item, scope=MarketScope("ETHUSDT", "5m"))
            if mutation == "plan_identity":
                item = replace(item, plan=replace(item.plan, opportunity_id="bad"))
            if mutation == "lineage":
                item = replace(item, plan=replace(item.plan, assessment_id="bad"))
            projection = service((item,), (item,))
        with pytest.raises(ReviewProjectionIntegrityError):
            await projection.build(scope=SCOPE, as_of=AS_OF)

    asyncio.run(run())


def test_policy_provenance_mismatch_fails_closed():
    async def run():
        item = opportunity("version.policy", 1, AS_OF + timedelta(minutes=1))
        bad_provenance = SimpleNamespace(
            source_references=item.plan.audit.provenance.source_references,
            policy_references=(),
        )
        bad_plan = replace(
            item.plan,
            audit=SimpleNamespace(
                provenance=bad_provenance,
                available_at=item.plan.audit.available_at,
            ),
        )
        bad_item = replace(item, plan=bad_plan)
        with pytest.raises(ReviewProjectionIntegrityError):
            await service((bad_item,), (bad_item,)).build(scope=SCOPE, as_of=AS_OF)

    asyncio.run(run())
