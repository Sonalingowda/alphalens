"""Immutable opportunity detection attempt and candidate models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    PolicyReference,
    validate_contract_version,
    validate_identifier,
    validate_non_empty_tuple,
    validate_unique_identifiers,
    validate_utc,
)


class CandidateAttemptState(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DetectionAttempt(CanonicalModel):
    contract_version: str
    attempt_id: str
    scope: MarketScope
    state: CandidateAttemptState
    detection_policy: PolicyReference
    input_references: tuple[IntegrityReference, ...]
    reason_codes: tuple[str, ...]
    candidate_id: str | None
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.attempt_id, "Detection attempt identifier")
        validate_non_empty_tuple(self.input_references, "Detection attempt inputs")
        validate_unique_identifiers(
            self.input_references, "artifact_id", "Detection attempt inputs"
        )
        for code in self.reason_codes:
            validate_identifier(code, "Detection attempt reason code")
        if self.state is CandidateAttemptState.DETECTED:
            if self.candidate_id is None or not self.reason_codes:
                raise DomainValidationError(
                    "Detected attempt requires candidate identity and reasons."
                )
        elif self.candidate_id is not None:
            raise DomainValidationError(
                "Only a detected attempt may reference a candidate."
            )
        if self.candidate_id is not None:
            validate_identifier(self.candidate_id, "Detected candidate identifier")
        if self.state in {
            CandidateAttemptState.NOT_DETECTED,
            CandidateAttemptState.UNAVAILABLE,
        } and not self.reason_codes:
            raise DomainValidationError(
                "Terminal detection attempt requires a reason code."
            )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in self.input_references
        ):
            raise DomainValidationError(
                "Detection attempt contains future-unavailable input."
            )


@dataclass(frozen=True, slots=True)
class OpportunityCandidate(CanonicalModel):
    contract_version: str
    candidate_id: str
    scope: MarketScope
    detected_at: datetime
    detection_policy: PolicyReference
    market_snapshot_reference: IntegrityReference
    feature_snapshot_reference: IntegrityReference
    context_reference: IntegrityReference | None
    reason_codes: tuple[str, ...]
    evidence_references: tuple[IntegrityReference, ...]
    limitations: tuple[str, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.candidate_id, "Candidate identifier")
        validate_utc(self.detected_at, "Candidate detection time")
        if self.detected_at < self.audit.evidence_cutoff:
            raise DomainValidationError(
                "Candidate detection cannot precede its evidence cutoff."
            )
        validate_non_empty_tuple(self.reason_codes, "Candidate reason codes")
        for reason in self.reason_codes:
            validate_identifier(reason, "Candidate reason code")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise DomainValidationError("Candidate reason codes must be unique.")
        validate_non_empty_tuple(
            self.evidence_references, "Candidate evidence references"
        )
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Candidate evidence"
        )
        references = (
            self.market_snapshot_reference,
            self.feature_snapshot_reference,
        ) + ((self.context_reference,) if self.context_reference is not None else ())
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in references + self.evidence_references
        ):
            raise DomainValidationError(
                "Candidate contains evidence unavailable at its cutoff."
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError("Candidate limitation must not be empty.")

