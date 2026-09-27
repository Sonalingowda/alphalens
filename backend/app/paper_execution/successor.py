"""Immutable remediation successors for historical V1.1 paper execution."""

from dataclasses import dataclass, replace
from datetime import timedelta
from hashlib import sha256

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    Opportunity,
    OpportunityPlan,
    RankingMembership,
    canonical_sha256,
    canonical_json,
)
from app.opportunity_intelligence.domain.primitives import (
    DomainValidationError,
    IntegrityReference,
    validate_contract_version,
    validate_identifier,
    validate_sha256,
)


SUCCESSOR_POLICY_ID = "alphalens_opportunity_plan_v1"
SUCCESSOR_POLICY_VERSION = "1.1.0"
SUCCESSOR_POLICY_HASH = "145b25381be7912e3c363df5469e80fc1e1b9b64e787f07768c0feaee410a200"
SUCCESSOR_INSTRUMENT = "BTCUSDT"
SUCCESSOR_TIMEFRAME = "5m"
SUCCESSOR_HORIZON_MINUTES = 10
APPROVED_POPULATION_MANIFEST_SHA256 = "2daa4fc6a26030f30438bc38e9b2dbd982c859a51a0208476e645e8321beacdb"


@dataclass(frozen=True, slots=True)
class PaperSuccessorPlan(CanonicalModel):
    """A new immutable plan identity that never replaces its historical source."""

    contract_version: str
    successor_plan_id: str
    source_opportunity_version_id: str
    source_opportunity_id: str
    source_opportunity_hash: str
    source_plan_id: str
    source_plan_canonical_hash: str
    plan: OpportunityPlan

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        for value, name in (
            (self.successor_plan_id, "Successor plan identifier"),
            (self.source_opportunity_version_id, "Source opportunity version"),
            (self.source_opportunity_id, "Source opportunity identifier"),
            (self.source_plan_id, "Source plan identifier"),
        ):
            validate_identifier(value, name)
        for value, name in (
            (self.source_opportunity_hash, "Source opportunity hash"),
            (self.source_plan_canonical_hash, "Source plan hash"),
        ):
            validate_sha256(value, name)
        if self.plan.plan_id != self.successor_plan_id:
            raise DomainValidationError("Successor payload identity does not match plan identity.")
        if self.plan.opportunity_id != self.source_opportunity_id:
            raise DomainValidationError("Successor opportunity identity does not match source.")
        if self.plan.valid_until != self.plan.audit.available_at + timedelta(minutes=SUCCESSOR_HORIZON_MINUTES):
            raise DomainValidationError("Successor validity must use the frozen ten-minute V1.1 horizon.")
        policy = self.plan.policy
        if (policy.policy_id, policy.policy_version, policy.integrity_digest) != (
            SUCCESSOR_POLICY_ID,
            SUCCESSOR_POLICY_VERSION,
            SUCCESSOR_POLICY_HASH,
        ):
            raise DomainValidationError("Successor does not use the frozen V1.1 policy identity.")
        if (self.plan.scope.instrument, self.plan.scope.timeframe) != (
            SUCCESSOR_INSTRUMENT,
            SUCCESSOR_TIMEFRAME,
        ):
            raise DomainValidationError("Successor scope is outside the approved BTCUSDT/5m population.")

    @property
    def successor_plan_canonical_hash(self) -> str:
        return self.plan.canonical_sha256()

    @property
    def provenance(self) -> tuple[IntegrityReference, ...]:
        return self.plan.audit.provenance.source_references


def successor_plan_id(opportunity_version_id: str) -> str:
    validate_identifier(opportunity_version_id, "Opportunity version")
    return f"paper_successor_plan:{opportunity_version_id}"


def eligible_opportunities(
    opportunities: tuple[Opportunity, ...],
    memberships: tuple[RankingMembership, ...],
) -> tuple[Opportunity, ...]:
    """Select only persisted-looking ranked V1.1 BTCUSDT/5m source records."""

    admitted = {
        (membership.opportunity_id, membership.opportunity_version_id)
        for membership in memberships
    }
    selected = tuple(
        opportunity
        for opportunity in opportunities
        if opportunity.plan is not None
        and (opportunity.opportunity_id, opportunity.opportunity_version_id) in admitted
        and (opportunity.scope.instrument, opportunity.scope.timeframe)
        == (SUCCESSOR_INSTRUMENT, SUCCESSOR_TIMEFRAME)
        and (
            opportunity.plan.policy.policy_id,
            opportunity.plan.policy.policy_version,
            opportunity.plan.policy.integrity_digest,
        )
        == (SUCCESSOR_POLICY_ID, SUCCESSOR_POLICY_VERSION, SUCCESSOR_POLICY_HASH)
    )
    return tuple(sorted(selected, key=lambda item: item.opportunity_version_id))


def derive_successor_plan(
    *,
    opportunity: Opportunity,
    ranking_membership: RankingMembership,
) -> PaperSuccessorPlan:
    """Derive only the missing validity boundary from an immutable historical plan."""

    if ranking_membership.opportunity_version_id != opportunity.opportunity_version_id:
        raise ValueError("Ranking membership does not admit the source opportunity version.")
    if ranking_membership.opportunity_id != opportunity.opportunity_id:
        raise ValueError("Ranking membership does not admit the source opportunity.")
    if opportunity.plan is None:
        raise ValueError("A persisted source plan is required.")
    source_plan = opportunity.plan
    if (source_plan.scope.instrument, source_plan.scope.timeframe) != (
        SUCCESSOR_INSTRUMENT,
        SUCCESSOR_TIMEFRAME,
    ):
        raise ValueError("Source plan is outside the approved BTCUSDT/5m population.")
    if (source_plan.policy.policy_id, source_plan.policy.policy_version, source_plan.policy.integrity_digest) != (
        SUCCESSOR_POLICY_ID,
        SUCCESSOR_POLICY_VERSION,
        SUCCESSOR_POLICY_HASH,
    ):
        raise ValueError("Source plan is not the frozen V1.1 plan contract.")

    source_plan_hash = source_plan.canonical_sha256()
    successor_id = successor_plan_id(opportunity.opportunity_version_id)
    successor_without_hash = replace(
        source_plan,
        plan_id=successor_id,
        valid_until=source_plan.audit.available_at + timedelta(minutes=SUCCESSOR_HORIZON_MINUTES),
        audit=replace(source_plan.audit, result_hash="0" * 64),
    )
    successor_plan = replace(
        successor_without_hash,
        audit=replace(
            successor_without_hash.audit,
            result_hash=canonical_sha256(successor_without_hash, exclude=frozenset({"result_hash"})),
        ),
    )
    return PaperSuccessorPlan(
        contract_version="1.0.0",
        successor_plan_id=successor_id,
        source_opportunity_version_id=opportunity.opportunity_version_id,
        source_opportunity_id=opportunity.opportunity_id,
        source_opportunity_hash=opportunity.canonical_sha256(),
        source_plan_id=source_plan.plan_id,
        source_plan_canonical_hash=source_plan_hash,
        plan=successor_plan,
    )


def population_manifest_sha256(
    opportunities: tuple[Opportunity, ...],
    memberships: tuple[RankingMembership, ...],
) -> str:
    """Hash the deterministic selected source identities; never creates records."""

    membership_by_version = {item.opportunity_version_id: item for item in memberships}
    selected = []
    for opportunity in opportunities:
        membership = membership_by_version.get(opportunity.opportunity_version_id)
        if membership is None or opportunity.plan is None:
            continue
        if (opportunity.scope.instrument, opportunity.scope.timeframe) != (
            SUCCESSOR_INSTRUMENT,
            SUCCESSOR_TIMEFRAME,
        ):
            continue
        if (opportunity.plan.policy.policy_id, opportunity.plan.policy.policy_version, opportunity.plan.policy.integrity_digest) != (
            SUCCESSOR_POLICY_ID,
            SUCCESSOR_POLICY_VERSION,
            SUCCESSOR_POLICY_HASH,
        ):
            continue
        plan = opportunity.plan
        selected.append(
            {
                "opportunity_version_id": opportunity.opportunity_version_id,
                "opportunity_hash": opportunity.canonical_sha256(),
                "historical_plan_id": plan.plan_id,
                "historical_plan_hash": plan.canonical_sha256(),
                "policy_id": plan.policy.policy_id,
                "policy_version": plan.policy.policy_version,
                "policy_hash": plan.policy.integrity_digest,
                "signal_timestamp": plan.audit.available_at,
                "successor_valid_until": plan.audit.available_at + timedelta(minutes=SUCCESSOR_HORIZON_MINUTES),
                "reference_price": plan.reference_price,
                "entry_zone": plan.entry_zone,
                "invalidation_price": plan.invalidation_price,
                "target_price": plan.targets[0].price,
                "plan_lineage_hash": plan.audit.provenance.lineage_hash,
                "opportunity_lineage_hash": opportunity.audit.provenance.lineage_hash,
            }
        )
    encoded = canonical_json(tuple(sorted(selected, key=lambda item: item["opportunity_version_id"]))).encode()
    return sha256(encoded).hexdigest()
