"""Immutable informational opportunity-plan models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    PolicyReference,
    PriceRange,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_non_empty_tuple,
    validate_unique_identifiers,
    validate_utc,
)
from app.opportunity_intelligence.domain.stances import OpportunityStance


@dataclass(frozen=True, slots=True)
class PlanTarget(CanonicalModel):
    target_id: str
    price: Decimal
    potential_reward: Decimal
    risk_reward: Decimal
    evidence_references: tuple[IntegrityReference, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.target_id, "Plan target identifier")
        validate_decimal(self.price, "Plan target price", positive=True)
        validate_decimal(
            self.potential_reward, "Plan potential reward", positive=True
        )
        validate_decimal(self.risk_reward, "Plan risk/reward", positive=True)
        validate_non_empty_tuple(self.evidence_references, "Plan target evidence")
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Plan target evidence"
        )


@dataclass(frozen=True, slots=True)
class OpportunityPlan(CanonicalModel):
    contract_version: str
    plan_id: str
    opportunity_id: str
    assessment_id: str
    decision_id: str
    policy: PolicyReference
    scope: MarketScope
    direction: OpportunityStance
    reference_price: Decimal
    reference_price_source: IntegrityReference
    entry_zone: PriceRange
    entry_semantics: str
    invalidation_price: Decimal
    invalidation_condition: str
    targets: tuple[PlanTarget, ...]
    risk: Decimal
    risk_unit: str
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    valid_until: datetime | None
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        for name, value in (
            ("Plan identifier", self.plan_id),
            ("Plan opportunity identifier", self.opportunity_id),
            ("Plan assessment identifier", self.assessment_id),
            ("Plan decision identifier", self.decision_id),
            ("Plan entry semantics", self.entry_semantics),
            ("Plan invalidation condition", self.invalidation_condition),
            ("Plan risk unit", self.risk_unit),
        ):
            validate_identifier(value, name)
        if self.direction is OpportunityStance.WAIT:
            raise DomainValidationError("WAIT cannot contain an opportunity plan.")
        validate_decimal(self.reference_price, "Plan reference price", positive=True)
        validate_decimal(
            self.invalidation_price, "Plan invalidation price", positive=True
        )
        validate_decimal(self.risk, "Plan risk", positive=True)
        validate_non_empty_tuple(self.targets, "Plan targets")
        validate_unique_identifiers(self.targets, "target_id", "Plan targets")
        if self.direction is OpportunityStance.BUY:
            if self.invalidation_price >= self.entry_zone.lower:
                raise DomainValidationError(
                    "BUY invalidation must be below the entry zone."
                )
            if any(target.price <= self.entry_zone.upper for target in self.targets):
                raise DomainValidationError("BUY targets must exceed the entry zone.")
        if self.direction is OpportunityStance.SELL:
            if self.invalidation_price <= self.entry_zone.upper:
                raise DomainValidationError(
                    "SELL invalidation must be above the entry zone."
                )
            if any(target.price >= self.entry_zone.lower for target in self.targets):
                raise DomainValidationError("SELL targets must be below the entry zone.")
        for text in self.assumptions + self.limitations:
            if not text.strip():
                raise DomainValidationError(
                    "Plan assumption or limitation must not be empty."
                )
        if self.valid_until is not None:
            validate_utc(self.valid_until, "Plan validity")
            if self.valid_until <= self.audit.available_at:
                raise DomainValidationError(
                    "Plan validity must be later than availability."
                )
        if self.reference_price_source.available_at > self.audit.evidence_cutoff:
            raise DomainValidationError(
                "Plan reference price is unavailable at the evidence cutoff."
            )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for target in self.targets
            for reference in target.evidence_references
        ):
            raise DomainValidationError(
                "Plan target evidence is unavailable at the evidence cutoff."
            )
