"""Immutable opportunity scoring records without scoring policy logic."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DecimalRange,
    DomainValidationError,
    IntegrityReference,
    PolicyReference,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_non_empty_tuple,
    validate_semver,
    validate_sha256,
    validate_unique_identifiers,
)


class ScoreComponentAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ScoreComponent(CanonicalModel):
    component_id: str
    component_version: str
    meaning: str
    availability: ScoreComponentAvailability
    source_evidence: tuple[IntegrityReference, ...]
    raw_value: Decimal | None
    normalized_value: Decimal | None
    weight: Decimal | None
    contribution: Decimal | None
    normalization_reference: IntegrityReference | None
    weight_reference: IntegrityReference | None
    limitations: tuple[str, ...]
    component_hash: str

    def __post_init__(self) -> None:
        validate_identifier(self.component_id, "Score component identifier")
        validate_semver(self.component_version, "Score component version")
        validate_identifier(self.meaning, "Score component meaning")
        validate_sha256(self.component_hash, "Score component hash")
        validate_unique_identifiers(
            self.source_evidence, "artifact_id", "Score component evidence"
        )
        values = (
            self.raw_value,
            self.normalized_value,
            self.weight,
            self.contribution,
        )
        if self.availability is ScoreComponentAvailability.AVAILABLE:
            if any(value is None for value in values) or not self.source_evidence:
                raise DomainValidationError(
                    "Available score component requires all values and evidence."
                )
        elif any(value is not None for value in values):
            raise DomainValidationError(
                "Unavailable score component cannot contain numeric values."
            )
        for name, value in zip(
            ("raw", "normalized", "weight", "contribution"), values, strict=True
        ):
            if value is not None:
                validate_decimal(value, f"Score component {name}")
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError(
                "Score component limitation must not be empty."
            )


@dataclass(frozen=True, slots=True)
class ScoreResult(CanonicalModel):
    contract_version: str
    score_id: str
    opportunity_id: str
    qualification_reference: IntegrityReference
    policy: PolicyReference
    components: tuple[ScoreComponent, ...]
    aggregation_definition: str
    aggregate_value: Decimal
    aggregate_unit: str
    valid_domain: DecimalRange
    missing_input_disposition: str
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.score_id, "Score identifier")
        validate_identifier(self.opportunity_id, "Score opportunity identifier")
        validate_non_empty_tuple(self.components, "Score components")
        validate_unique_identifiers(self.components, "component_id", "Score components")
        validate_identifier(self.aggregation_definition, "Score aggregation")
        validate_decimal(self.aggregate_value, "Aggregate score")
        validate_identifier(self.aggregate_unit, "Aggregate score unit")
        validate_identifier(
            self.missing_input_disposition, "Score missing-input disposition"
        )
        if not self.valid_domain.lower <= self.aggregate_value <= self.valid_domain.upper:
            raise DomainValidationError("Aggregate score is outside its valid domain.")
        if any(
            component.availability is ScoreComponentAvailability.UNAVAILABLE
            for component in self.components
        ):
            raise DomainValidationError(
                "A score result cannot contain unavailable components."
            )
        if self.qualification_reference.available_at > self.audit.evidence_cutoff:
            raise DomainValidationError(
                "Score qualification is unavailable at the evidence cutoff."
            )
        component_references = tuple(
            reference
            for component in self.components
            for reference in (
                component.source_evidence
                + tuple(
                    item
                    for item in (
                        component.normalization_reference,
                        component.weight_reference,
                    )
                    if item is not None
                )
            )
        )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in component_references
        ):
            raise DomainValidationError(
                "Score component input is unavailable at the evidence cutoff."
            )

