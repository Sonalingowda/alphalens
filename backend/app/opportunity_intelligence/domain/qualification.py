"""Immutable opportunity qualification models."""

from dataclasses import dataclass
from enum import StrEnum

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    PolicyReference,
    validate_contract_version,
    validate_identifier,
    validate_non_empty_tuple,
    validate_unique_identifiers,
)


class QualificationStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


class QualificationOutcome(StrEnum):
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class QualificationGateResult(CanonicalModel):
    gate_id: str
    requirement_class: str
    status: QualificationStatus
    evidence_references: tuple[IntegrityReference, ...]
    reason_code: str

    def __post_init__(self) -> None:
        validate_identifier(self.gate_id, "Qualification gate identifier")
        validate_identifier(self.requirement_class, "Gate requirement class")
        validate_identifier(self.reason_code, "Gate reason code")
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Qualification gate evidence"
        )
        if self.status is QualificationStatus.PASS and not self.evidence_references:
            raise DomainValidationError("Passing gate requires evidence.")


@dataclass(frozen=True, slots=True)
class QualificationRecord(CanonicalModel):
    contract_version: str
    qualification_id: str
    assessment_reference: IntegrityReference
    context_reference: IntegrityReference
    evidence_package_reference: IntegrityReference
    policy: PolicyReference
    gate_results: tuple[QualificationGateResult, ...]
    outcome: QualificationOutcome
    exclusions: tuple[str, ...]
    limitations: tuple[str, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.qualification_id, "Qualification identifier")
        validate_non_empty_tuple(self.gate_results, "Qualification gate results")
        validate_unique_identifiers(
            self.gate_results, "gate_id", "Qualification gate results"
        )
        statuses = tuple(gate.status for gate in self.gate_results)
        if self.outcome is QualificationOutcome.QUALIFIED and any(
            status is not QualificationStatus.PASS for status in statuses
        ):
            raise DomainValidationError(
                "Qualified outcome requires every gate to pass."
            )
        if self.outcome is QualificationOutcome.NOT_QUALIFIED and not any(
            status is QualificationStatus.FAIL for status in statuses
        ):
            raise DomainValidationError(
                "Not-qualified outcome requires a failed gate."
            )
        if self.outcome is QualificationOutcome.UNAVAILABLE and not any(
            status is QualificationStatus.UNAVAILABLE for status in statuses
        ):
            raise DomainValidationError(
                "Unavailable outcome requires an unavailable gate."
            )
        for code in self.exclusions:
            validate_identifier(code, "Qualification exclusion")
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError(
                "Qualification limitation must not be empty."
            )
        references = (
            self.assessment_reference,
            self.context_reference,
            self.evidence_package_reference,
        )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in references
        ):
            raise DomainValidationError(
                "Qualification input is unavailable at the evidence cutoff."
            )
