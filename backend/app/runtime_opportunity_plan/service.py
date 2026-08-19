"""Deterministic informational Opportunity Plan V1 runtime service."""

from dataclasses import replace
from decimal import Decimal
from typing import Final

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    EvidencePackage,
    IntegrityReference,
    MarketContext,
    Opportunity,
    OpportunityPlan,
    PlanTarget,
    PolicyReference,
    PriceRange,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.stances import OpportunityStance
from app.opportunity_intelligence.services import ServiceContractError


RUNTIME_OPPORTUNITY_PLAN_POLICY_ID: Final[str] = (
    "alphalens_opportunity_plan_v1"
)
RUNTIME_OPPORTUNITY_PLAN_POLICY_VERSION: Final[str] = "1.1.0"
RUNTIME_OPPORTUNITY_PLAN_POLICY_HASH: Final[str] = (
    "145b25381be7912e3c363df5469e80fc1e1b9b64e787f07768c0feaee410a200"
)

_PLAN_CONTRACT_VERSION: Final[str] = "1.0.0"

# Approved V1.1 policy:
#   risk distance = ATR (average_true_range) from evidence
#   target distance = risk distance * 1.5
_REWARD_MULTIPLE: Final[Decimal] = Decimal("1.5")
_ATR_EVIDENCE_SUFFIX: Final[str] = "atr_true_range"

_TARGET_ID_SUFFIX: Final[str] = "tp1"


class RuntimeOpportunityPlanService:
    """Create one complete informational plan for BUY/SELL.

    WAIT produces no plan.

    V1.1:
        reference price = market_price_close evidence
        risk distance   = ATR (average_true_range) from evidence
        entry zone = exact reference price
        BUY:
            invalidation = entry - ATR
            target      = entry + 1.5 * ATR
        SELL:
            invalidation = entry + ATR
            target       = entry - 1.5 * ATR

    The resulting plan is informational only and is never an executable order.
    """

    def __init__(
        self,
        *,
        code_version: str,
        policy: PolicyReference | None = None,
    ) -> None:
        if not code_version.strip():
            raise ValueError(
                "Runtime opportunity plan code version must be non-empty."
            )

        self._code_version = code_version
        self._policy = (
            policy
            if policy is not None
            else PolicyReference(
                RUNTIME_OPPORTUNITY_PLAN_POLICY_ID,
                RUNTIME_OPPORTUNITY_PLAN_POLICY_VERSION,
                RUNTIME_OPPORTUNITY_PLAN_POLICY_HASH,
            )
        )

    async def create_plan(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> OpportunityPlan | None:
        """Create a complete deterministic plan or return None for WAIT."""

        self._validate_policy()

        # ---------------------------------------------------------------
        # 1. Direction gate
        # ---------------------------------------------------------------

        if opportunity.stance is OpportunityStance.WAIT:
            return None

        if opportunity.stance not in (
            OpportunityStance.BUY,
            OpportunityStance.SELL,
        ):
            raise ServiceContractError(
                "Opportunity plan requires BUY, SELL, or WAIT."
            )

        # ---------------------------------------------------------------
        # 2. Lineage / scope validation
        # ---------------------------------------------------------------

        if evidence.candidate_id != opportunity.candidate_id:
            raise ServiceContractError(
                "Opportunity plan evidence candidate does not match opportunity."
            )

        if market_context.context_id != (
            opportunity.context_reference.artifact_id
        ):
            raise ServiceContractError(
                "Opportunity plan market context does not match opportunity."
            )

        if market_context.scope != opportunity.scope:
            raise ServiceContractError(
                "Opportunity plan market context scope does not match opportunity."
            )

        if evidence.assessment_id not in (
            None,
            opportunity.assessment_id,
        ):
            raise ServiceContractError(
                "Opportunity plan evidence assessment does not match opportunity."
            )

        # ---------------------------------------------------------------
        # 3. Reference price
        # ---------------------------------------------------------------

        reference_price, reference_price_source = _reference_price(evidence)

        # ---------------------------------------------------------------
        # 4. ATR-derived geometry
        # ---------------------------------------------------------------

        entry_zone = PriceRange(
            lower=reference_price,
            upper=reference_price,
        )

        risk_distance = _atr_from_evidence(evidence)
        target_distance = risk_distance * _REWARD_MULTIPLE

        if risk_distance <= 0 or target_distance <= 0:
            raise ServiceContractError(
                "Opportunity plan computed a non-positive risk or reward distance."
            )

        if opportunity.stance is OpportunityStance.BUY:
            invalidation_price = reference_price - risk_distance
            target_price = reference_price + target_distance
        else:
            invalidation_price = reference_price + risk_distance
            target_price = reference_price - target_distance

        risk_reward = target_distance / risk_distance

        # ---------------------------------------------------------------
        # 5. Evidence references
        # ---------------------------------------------------------------

        opportunity_reference = _reference(
            opportunity.opportunity_id,
            "opportunity",
            opportunity,
        )

        evidence_reference = _reference(
            evidence.package_id,
            "evidence_package",
            evidence,
        )

        context_reference = _reference(
            market_context.context_id,
            "market_context",
            market_context,
        )

        source_references = (
            opportunity_reference,
            evidence_reference,
            context_reference,
            reference_price_source,
        )

        lineage_hash = canonical_sha256(source_references)

        evidence_cutoff = min(
            opportunity.audit.evidence_cutoff,
            evidence.audit.evidence_cutoff,
            market_context.audit.evidence_cutoff,
        )

        available_at = max(
            reference.available_at
            for reference in source_references
        )

        if any(
            reference.available_at > evidence_cutoff
            for reference in source_references
        ):
            raise ServiceContractError(
                "Opportunity plan has evidence unavailable at the evidence cutoff."
            )

        # ---------------------------------------------------------------
        # 6. Plan identity
        # ---------------------------------------------------------------

        plan_id = (
            f"plan.runtime.opp.{opportunity.opportunity_version_id}"
        )

        target = PlanTarget(
            target_id=f"{plan_id}.{_TARGET_ID_SUFFIX}",
            price=target_price,
            potential_reward=target_distance,
            risk_reward=risk_reward,
            evidence_references=(
                reference_price_source,
                opportunity_reference,
            ),
        )

        # ---------------------------------------------------------------
        # 7. Complete canonical OpportunityPlan
        # ---------------------------------------------------------------

        entry_semantics = "reference_price_exact"

        if opportunity.stance is OpportunityStance.BUY:
            invalidation_condition = "price_below_invalidation"
        else:
            invalidation_condition = "price_above_invalidation"

        assumptions = (
            "reference_price_is_market_price_close",
            "entry_zone_collapses_to_reference_price",
            "risk_distance_is_average_true_range",
            "target_distance_is_1.5_times_risk_distance",
            "plan_is_informational_not_executable",
        )

        limitations = (
            "candle_price_does_not_establish_executable_fill",
            "geometric_risk_reward_is_not_expectancy",
            "terminal_levels_do_not_establish_intrabar_path",
        )

        result_hash_placeholder = "0" * 64

        plan = OpportunityPlan(
            contract_version=_PLAN_CONTRACT_VERSION,
            plan_id=plan_id,
            opportunity_id=opportunity.opportunity_id,
            assessment_id=opportunity.assessment_id,
            decision_id=opportunity.decision_id,
            policy=self._policy,
            scope=opportunity.scope,
            direction=opportunity.stance,
            reference_price=reference_price,
            reference_price_source=reference_price_source,
            entry_zone=entry_zone,
            entry_semantics=entry_semantics,
            invalidation_price=invalidation_price,
            invalidation_condition=invalidation_condition,
            targets=(target,),
            risk=risk_distance,
            risk_unit="price_distance",
            assumptions=assumptions,
            limitations=limitations,
            valid_until=None,
            audit=AuditMetadata(
                created_at=available_at,
                evidence_cutoff=evidence_cutoff,
                available_at=available_at,
                provenance=Provenance(
                    source_references=source_references,
                    policy_references=(self._policy,),
                    code_version=self._code_version,
                    configuration_hash=RUNTIME_OPPORTUNITY_PLAN_POLICY_HASH,
                    lineage_hash=lineage_hash,
                ),
                result_hash=result_hash_placeholder,
            ),
        )

        # ---------------------------------------------------------------
        # 8. Canonical result hash
        # ---------------------------------------------------------------

        return replace(
            plan,
            audit=replace(
                plan.audit,
                result_hash=canonical_sha256(
                    plan,
                    exclude=frozenset({"result_hash"}),
                ),
            ),
        )

    def _validate_policy(self) -> None:
        expected = PolicyReference(
            RUNTIME_OPPORTUNITY_PLAN_POLICY_ID,
            RUNTIME_OPPORTUNITY_PLAN_POLICY_VERSION,
            RUNTIME_OPPORTUNITY_PLAN_POLICY_HASH,
        )

        if self._policy != expected:
            raise ServiceContractError(
                "Opportunity plan policy V1 is unavailable or does not match "
                "the approved policy identity."
            )


def _reference_price(
    evidence: EvidencePackage,
) -> tuple[Decimal, IntegrityReference]:
    """Extract market_price_close from the canonical evidence package."""

    matches = [
        item
        for item in evidence.items
        if item.evidence_id.rsplit(".", 1)[-1] == "market_price_close"
    ]

    if len(matches) != 1:
        raise ServiceContractError(
            "Opportunity plan requires exactly one market_price_close evidence item."
        )

    item = matches[0]
    value = getattr(item, "observed_value", None)

    if isinstance(value, bool):
        raise ServiceContractError(
            "market_price_close evidence must contain a positive numeric value."
        )

    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as error:
        raise ServiceContractError(
            "market_price_close evidence contains a non-numeric value."
        ) from error

    if parsed <= 0:
        raise ServiceContractError(
            "market_price_close evidence must be positive."
        )

    return (
        parsed,
        IntegrityReference(
            artifact_id=item.evidence_id,
            artifact_type="evidence_item",
            artifact_version=item.taxonomy_version,
            integrity_digest=item.integrity_digest,
            available_at=item.available_at,
        ),
    )


def _atr_from_evidence(evidence: EvidencePackage) -> Decimal:
    """Extract ATR from the evidence package for risk-distance calculation."""

    matches = [
        item
        for item in evidence.items
        if item.evidence_id.rsplit(".", 1)[-1] == _ATR_EVIDENCE_SUFFIX
    ]

    if len(matches) != 1:
        raise ServiceContractError(
            "Opportunity plan requires exactly one atr_true_range evidence item."
        )

    item = matches[0]
    value = getattr(item, "observed_value", None)

    if isinstance(value, bool):
        raise ServiceContractError(
            "atr_true_range evidence must contain a positive numeric value."
        )

    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as error:
        raise ServiceContractError(
            "atr_true_range evidence contains a non-numeric value."
        ) from error

    if parsed <= 0:
        raise ServiceContractError(
            "atr_true_range evidence must be positive."
        )

    return parsed


def _reference(
    artifact_id: str,
    artifact_type: str,
    entity: Opportunity | EvidencePackage | MarketContext,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest=entity.canonical_sha256(),
        available_at=entity.audit.available_at,
    )
