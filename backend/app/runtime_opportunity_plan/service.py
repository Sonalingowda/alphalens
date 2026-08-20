"""Deterministic informational Opportunity Plan V1.1 and V2 runtime services."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from typing import Final

from app.inference.artifact import (
    EXPECTED_MOVE_MAX_RR,
    EXPECTED_MOVE_MIN_SNR,
    PackagedExpectedMoveInference,
)
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
from app.opportunity_intelligence.domain.primitives import DECIMAL_QUANTUM
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
        target_distance = (risk_distance * _REWARD_MULTIPLE).quantize(
            DECIMAL_QUANTUM
        )

        if risk_distance <= 0 or target_distance <= 0:
            raise ServiceContractError(
                "Opportunity plan computed a non-positive risk or reward distance."
            )

        if opportunity.stance is OpportunityStance.BUY:
            invalidation_price = (reference_price - risk_distance).quantize(
                DECIMAL_QUANTUM
            )
            target_price = (reference_price + target_distance).quantize(
                DECIMAL_QUANTUM
            )
        else:
            invalidation_price = (reference_price + risk_distance).quantize(
                DECIMAL_QUANTUM
            )
            target_price = (reference_price - target_distance).quantize(
                DECIMAL_QUANTUM
            )

        risk_reward = (target_distance / risk_distance).quantize(DECIMAL_QUANTUM)

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


# ---------------------------------------------------------------------------
# V2: Expected-Move Opportunity Plan Service
# ---------------------------------------------------------------------------

RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_ID: Final[str] = (
    "alphalens_opportunity_plan_v2"
)
RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_VERSION: Final[str] = "2.0.0"
RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_HASH: Final[str] = (
    "0" * 64  # placeholder until policy document is ratified
)

_V2_PLAN_CONTRACT_VERSION: Final[str] = "2.0.0"
_V2_HORIZON_MINUTES: Final[int] = 25


class RuntimeOpportunityPlanServiceV2:
    """Create one complete informational plan using expected-move geometry.

    V2:
        reference price = market_price_close evidence
        risk distance   = ATR (average_true_range) from evidence
        target distance = min(predicted_distance, ATR * 3R cap)
        SNR             = predicted / residual_std

        BUY:
            invalidation = entry - ATR
            target       = entry + capped_target_distance
        SELL:
            invalidation = entry + ATR
            target       = entry - capped_target_distance

        valid_until = available_at + 25 minutes

    Direction continues to come from the existing assessment pipeline.
    The magnitude model never determines BUY vs SELL.
    """

    def __init__(
        self,
        *,
        code_version: str,
        inference: PackagedExpectedMoveInference,
        policy: PolicyReference | None = None,
    ) -> None:
        if not code_version.strip():
            raise ValueError(
                "Runtime opportunity plan V2 code version must be non-empty."
            )
        self._code_version = code_version
        self._inference = inference
        self._policy = (
            policy
            if policy is not None
            else PolicyReference(
                RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_ID,
                RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_VERSION,
                RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_HASH,
            )
        )

    @property
    def inference(self) -> PackagedExpectedMoveInference:
        return self._inference

    async def create_plan(
        self,
        opportunity: Opportunity,
        evidence: EvidencePackage,
        market_context: MarketContext,
    ) -> OpportunityPlan | None:
        """Create a complete deterministic V2 plan or return None for WAIT."""

        self._validate_policy()

        if opportunity.stance is OpportunityStance.WAIT:
            return None

        if opportunity.stance not in (
            OpportunityStance.BUY,
            OpportunityStance.SELL,
        ):
            raise ServiceContractError(
                "Opportunity plan V2 requires BUY, SELL, or WAIT."
            )

        if evidence.candidate_id != opportunity.candidate_id:
            raise ServiceContractError(
                "Opportunity plan V2 evidence candidate does not match opportunity."
            )

        if market_context.context_id != (
            opportunity.context_reference.artifact_id
        ):
            raise ServiceContractError(
                "Opportunity plan V2 market context does not match opportunity."
            )

        if market_context.scope != opportunity.scope:
            raise ServiceContractError(
                "Opportunity plan V2 market context scope does not match opportunity."
            )

        if evidence.assessment_id not in (
            None,
            opportunity.assessment_id,
        ):
            raise ServiceContractError(
                "Opportunity plan V2 evidence assessment does not match opportunity."
            )

        reference_price, reference_price_source = _reference_price(evidence)

        entry_zone = PriceRange(
            lower=reference_price,
            upper=reference_price,
        )

        risk_distance = _atr_from_evidence(evidence)

        predicted_log_return, predicted_snr = self._predict_from_evidence(
            evidence
        )
        predicted_price_distance = (
            reference_price
            * (Decimal("2.718281828459045235") ** predicted_log_return - 1)
        ).quantize(DECIMAL_QUANTUM)

        cap_distance = (risk_distance * EXPECTED_MOVE_MAX_RR).quantize(
            DECIMAL_QUANTUM
        )
        target_distance = min(predicted_price_distance, cap_distance).quantize(
            DECIMAL_QUANTUM
        )

        if risk_distance <= 0 or target_distance <= 0:
            raise ServiceContractError(
                "Opportunity plan V2 computed a non-positive risk or reward distance."
            )

        if opportunity.stance is OpportunityStance.BUY:
            invalidation_price = (reference_price - risk_distance).quantize(
                DECIMAL_QUANTUM
            )
            target_price = (reference_price + target_distance).quantize(
                DECIMAL_QUANTUM
            )
        else:
            invalidation_price = (reference_price + risk_distance).quantize(
                DECIMAL_QUANTUM
            )
            target_price = (reference_price - target_distance).quantize(
                DECIMAL_QUANTUM
            )

        risk_reward = (target_distance / risk_distance).quantize(DECIMAL_QUANTUM)

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
            reference.available_at for reference in source_references
        )

        if any(
            reference.available_at > evidence_cutoff
            for reference in source_references
        ):
            raise ServiceContractError(
                "Opportunity plan V2 has evidence unavailable at the evidence cutoff."
            )

        plan_id = (
            f"plan.runtime.v2.opp.{opportunity.opportunity_version_id}"
        )

        target = PlanTarget(
            target_id=f"{plan_id}.tp1",
            price=target_price,
            potential_reward=target_distance,
            risk_reward=risk_reward,
            evidence_references=(
                reference_price_source,
                opportunity_reference,
            ),
        )

        entry_semantics = "reference_price_exact"

        if opportunity.stance is OpportunityStance.BUY:
            invalidation_condition = "price_below_invalidation"
        else:
            invalidation_condition = "price_above_invalidation"

        assumptions = (
            "reference_price_is_market_price_close",
            "entry_zone_collapses_to_reference_price",
            "risk_distance_is_average_true_range",
            "target_distance_derived_from_expected_move_model",
            "target_distance_capped_at_3R_reliability_limit",
            "prediction_horizon_is_25_minutes",
            "plan_is_informational_not_executable",
        )

        limitations = (
            "candle_price_does_not_establish_executable_fill",
            "geometric_risk_reward_is_not_expectancy",
            "terminal_levels_do_not_establish_intrabar_path",
            "expected_move_prediction_is_statistical_not_guaranteed",
            "model_residual_uncertainty_may_exceed_predicted_move",
        )

        result_hash_placeholder = "0" * 64
        valid_until = available_at + timedelta(minutes=_V2_HORIZON_MINUTES)

        plan = OpportunityPlan(
            contract_version=_V2_PLAN_CONTRACT_VERSION,
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
            valid_until=valid_until,
            audit=AuditMetadata(
                created_at=available_at,
                evidence_cutoff=evidence_cutoff,
                available_at=available_at,
                provenance=Provenance(
                    source_references=source_references,
                    policy_references=(self._policy,),
                    code_version=self._code_version,
                    configuration_hash=RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_HASH,
                    lineage_hash=lineage_hash,
                ),
                result_hash=result_hash_placeholder,
            ),
            expected_move_prediction=predicted_price_distance,
            expected_move_confidence=predicted_snr,
            prediction_horizon_minutes=_V2_HORIZON_MINUTES,
        )

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
            RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_ID,
            RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_VERSION,
            RUNTIME_OPPORTUNITY_PLAN_V2_POLICY_HASH,
        )
        if self._policy != expected:
            raise ServiceContractError(
                "Opportunity plan policy V2 is unavailable or does not match "
                "the approved policy identity."
            )

    def _predict_from_evidence(
        self,
        evidence: EvidencePackage,
    ) -> tuple[Decimal, Decimal]:
        """Compute expected-move prediction and SNR from evidence features."""
        items = {
            item.evidence_id.rsplit(".", 1)[-1]: item
            for item in evidence.items
        }
        feature_values = []
        for name in self._inference.feature_names:
            item = items.get(name)
            if item is None:
                raise ServiceContractError(
                    f"Expected-move evidence item '{name}' is absent."
                )
            value = getattr(item, "observed_value", None)
            if isinstance(value, bool) or value is None:
                raise ServiceContractError(
                    f"Expected-move evidence item '{name}' must contain a numeric value."
                )
            feature_values.append(
                Decimal(str(value)) if not isinstance(value, Decimal) else value
            )
        prediction = self._inference.predict(tuple(feature_values))
        return (
            Decimal(str(prediction.value)),
            Decimal(str(prediction.snr)),
        )
