"""Immutable canonical opportunity assessment models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.opportunity_intelligence.domain.plan import OpportunityPlan
from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    PolicyReference,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_non_empty_tuple,
    validate_utc,
)
from app.opportunity_intelligence.domain.stances import OpportunityStance


@dataclass(frozen=True, slots=True)
class ConfidenceRecord(CanonicalModel):
    contract_version: str
    confidence_id: str
    value: Decimal
    meaning: str
    population_scope: str
    calibration_reference: IntegrityReference
    approval_reference: PolicyReference
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.confidence_id, "Confidence identifier")
        validate_decimal(self.value, "Confidence value")
        validate_identifier(self.meaning, "Confidence meaning")
        validate_identifier(self.population_scope, "Confidence population scope")
        if self.calibration_reference.available_at > self.audit.evidence_cutoff:
            raise DomainValidationError(
                "Confidence calibration is unavailable at the evidence cutoff."
            )


@dataclass(frozen=True, slots=True)
class Opportunity(CanonicalModel):
    contract_version: str
    opportunity_id: str
    opportunity_version_id: str
    assessment_id: str
    decision_id: str
    candidate_id: str
    scope: MarketScope
    stance: OpportunityStance
    decision_policy: PolicyReference
    evidence_package_reference: IntegrityReference
    context_reference: IntegrityReference
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]
    qualification_reference: IntegrityReference | None
    score_reference: IntegrityReference | None
    confidence: ConfidenceRecord | None
    plan: OpportunityPlan | None
    valid_until: datetime | None
    supersedes_opportunity_version_id: str | None
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        for name, value in (
            ("Opportunity identifier", self.opportunity_id),
            ("Opportunity version identifier", self.opportunity_version_id),
            ("Assessment identifier", self.assessment_id),
            ("Decision identifier", self.decision_id),
            ("Candidate identifier", self.candidate_id),
        ):
            validate_identifier(value, name)
        validate_non_empty_tuple(self.reason_codes, "Opportunity reason codes")
        for code in self.reason_codes:
            validate_identifier(code, "Opportunity reason code")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise DomainValidationError("Opportunity reason codes must be unique.")
        if self.stance is OpportunityStance.WAIT and any(
            item is not None
            for item in (
                self.qualification_reference,
                self.score_reference,
                self.plan,
            )
        ):
            raise DomainValidationError(
                "WAIT cannot be qualified, scored, or contain a plan."
            )
        if self.plan is not None:
            if self.plan.opportunity_id != self.opportunity_id:
                raise DomainValidationError("Plan opportunity identity mismatch.")
            if self.plan.direction is not self.stance:
                raise DomainValidationError("Plan direction mismatch.")
        if self.confidence is not None and (
            self.confidence.audit.evidence_cutoff > self.audit.evidence_cutoff
        ):
            raise DomainValidationError(
                "Confidence uses evidence beyond the opportunity cutoff."
            )
        if self.valid_until is not None:
            validate_utc(self.valid_until, "Opportunity validity")
            if self.valid_until <= self.audit.available_at:
                raise DomainValidationError(
                    "Opportunity validity must follow availability."
                )
        if self.supersedes_opportunity_version_id is not None:
            validate_identifier(
                self.supersedes_opportunity_version_id,
                "Superseded opportunity version",
            )
            if self.supersedes_opportunity_version_id == self.opportunity_version_id:
                raise DomainValidationError("Opportunity cannot supersede itself.")
        references = (
            self.evidence_package_reference,
            self.context_reference,
        ) + tuple(
            reference
            for reference in (self.qualification_reference, self.score_reference)
            if reference is not None
        )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in references
        ):
            raise DomainValidationError(
                "Opportunity contains future-unavailable references."
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError("Opportunity limitation must not be empty.")
