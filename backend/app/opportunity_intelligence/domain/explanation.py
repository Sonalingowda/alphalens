"""Immutable deterministic explanation artifacts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_non_empty_tuple,
    validate_semver,
    validate_unique_identifiers,
    validate_utc,
)


BindingValue = Decimal | str | bool | datetime


@dataclass(frozen=True, slots=True)
class TemplateBinding(CanonicalModel):
    name: str
    value: BindingValue

    def __post_init__(self) -> None:
        validate_identifier(self.name, "Template binding name")
        if isinstance(self.value, Decimal):
            validate_decimal(self.value, "Template Decimal binding")
        elif isinstance(self.value, datetime):
            validate_utc(self.value, "Template timestamp binding")
        elif isinstance(self.value, str) and not self.value.strip():
            raise DomainValidationError("Template string binding must not be empty.")
        elif not isinstance(self.value, (str, bool)):
            raise DomainValidationError("Template binding type is invalid.")


@dataclass(frozen=True, slots=True)
class ExplanationSentence(CanonicalModel):
    sentence_id: str
    template_id: str
    bindings: tuple[TemplateBinding, ...]
    evidence_references: tuple[IntegrityReference, ...]
    rendered_text: str

    def __post_init__(self) -> None:
        validate_identifier(self.sentence_id, "Explanation sentence identifier")
        validate_identifier(self.template_id, "Explanation template identifier")
        validate_unique_identifiers(
            self.bindings, "name", "Explanation template bindings"
        )
        validate_non_empty_tuple(
            self.evidence_references, "Explanation sentence evidence"
        )
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Explanation sentence evidence"
        )
        if not self.rendered_text.strip():
            raise DomainValidationError("Rendered explanation must not be empty.")


@dataclass(frozen=True, slots=True)
class ExplanationSection(CanonicalModel):
    section_id: str
    ordinal: int
    sentences: tuple[ExplanationSentence, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.section_id, "Explanation section identifier")
        if self.ordinal <= 0:
            raise DomainValidationError("Explanation section ordinal must be positive.")
        validate_non_empty_tuple(self.sentences, "Explanation section sentences")
        validate_unique_identifiers(
            self.sentences, "sentence_id", "Explanation section sentences"
        )


@dataclass(frozen=True, slots=True)
class ExplanationArtifact(CanonicalModel):
    contract_version: str
    explanation_id: str
    opportunity_version_id: str
    language: str
    locale: str
    taxonomy_version: str
    template_set_version: str
    sections: tuple[ExplanationSection, ...]
    limitations: tuple[str, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.explanation_id, "Explanation identifier")
        validate_identifier(
            self.opportunity_version_id, "Explanation opportunity version"
        )
        validate_identifier(self.language, "Explanation language")
        validate_identifier(self.locale, "Explanation locale")
        validate_semver(self.taxonomy_version, "Explanation taxonomy version")
        validate_semver(self.template_set_version, "Template-set version")
        validate_non_empty_tuple(self.sections, "Explanation sections")
        validate_unique_identifiers(
            self.sections, "section_id", "Explanation sections"
        )
        ordinals = tuple(section.ordinal for section in self.sections)
        if ordinals != tuple(range(1, len(self.sections) + 1)):
            raise DomainValidationError(
                "Explanation sections must have contiguous canonical ordinals."
            )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for section in self.sections
            for sentence in section.sentences
            for reference in sentence.evidence_references
        ):
            raise DomainValidationError(
                "Explanation uses evidence unavailable at its cutoff."
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError(
                "Explanation limitation must not be empty."
            )

