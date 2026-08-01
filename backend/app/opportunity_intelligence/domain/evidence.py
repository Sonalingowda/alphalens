"""Canonical evidence ontology runtime models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    PriceRange,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_non_empty_tuple,
    validate_semver,
    validate_sha256,
    validate_unique_identifiers,
    validate_utc,
)


class EvidencePolarity(StrEnum):
    SUPPORTING = "SUPPORTING"
    CONTRADICTING = "CONTRADICTING"
    CONTEXTUAL = "CONTEXTUAL"


class EvidenceSeverity(StrEnum):
    INFORMATIONAL = "INFORMATIONAL"
    MATERIAL = "MATERIAL"
    DISQUALIFYING = "DISQUALIFYING"


class EvidenceCategory(StrEnum):
    MARKET_PRICE = "MARKET_PRICE"
    MARKET_VOLUME = "MARKET_VOLUME"
    FEATURE_TREND = "FEATURE_TREND"
    FEATURE_MOMENTUM = "FEATURE_MOMENTUM"
    FEATURE_VOLATILITY = "FEATURE_VOLATILITY"
    FEATURE_VOLUME = "FEATURE_VOLUME"
    CONTEXT_TREND = "CONTEXT_TREND"
    CONTEXT_MOMENTUM = "CONTEXT_MOMENTUM"
    CONTEXT_VOLATILITY = "CONTEXT_VOLATILITY"
    CONTEXT_STRUCTURE = "CONTEXT_STRUCTURE"
    CONTEXT_SESSION = "CONTEXT_SESSION"
    DATA_QUALITY = "DATA_QUALITY"
    POLICY_TRACE = "POLICY_TRACE"
    FORECAST = "FORECAST"
    RISK_CONTEXT = "RISK_CONTEXT"
    PLAN_VALUE = "PLAN_VALUE"
    CALIBRATION = "CALIBRATION"
    LIFECYCLE = "LIFECYCLE"
    LIMITATION = "LIMITATION"


EvidenceValue = Decimal | str | bool


@dataclass(frozen=True, slots=True)
class EvidenceItem(CanonicalModel):
    taxonomy_version: str
    evidence_id: str
    evidence_type: str
    category: EvidenceCategory
    description_code: str
    source_reference: IntegrityReference
    source_definition: str
    polarity: EvidencePolarity
    proposition: str
    severity: EvidenceSeverity
    observed_value: EvidenceValue
    unit: str | None
    scope: MarketScope
    time_start: datetime
    time_end: datetime
    available_at: datetime
    price_scope: PriceRange | None
    limitations: tuple[str, ...]
    integrity_digest: str

    def __post_init__(self) -> None:
        validate_semver(self.taxonomy_version, "Evidence taxonomy version")
        validate_identifier(self.evidence_id, "Evidence identifier")
        validate_identifier(self.evidence_type, "Evidence type")
        validate_identifier(self.description_code, "Evidence description code")
        validate_identifier(self.source_definition, "Evidence source definition")
        validate_identifier(self.proposition, "Evidence proposition")
        if isinstance(self.observed_value, str) and not self.observed_value.strip():
            raise DomainValidationError("Evidence string value must not be empty.")
        if not isinstance(self.observed_value, (Decimal, str, bool)):
            raise DomainValidationError("Evidence observed value type is invalid.")
        if isinstance(self.observed_value, Decimal):
            validate_decimal(self.observed_value, "Evidence Decimal value")
        if self.unit is not None:
            validate_identifier(self.unit, "Evidence unit")
        validate_utc(self.time_start, "Evidence time start")
        validate_utc(self.time_end, "Evidence time end")
        validate_utc(self.available_at, "Evidence availability")
        if self.time_start > self.time_end:
            raise DomainValidationError("Evidence time start exceeds time end.")
        if self.available_at < self.time_end:
            raise DomainValidationError(
                "Evidence availability must not precede its time scope."
            )
        if self.source_reference.available_at > self.available_at:
            raise DomainValidationError(
                "Evidence source is unavailable at evidence availability."
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError("Evidence limitation must not be empty.")
        validate_sha256(self.integrity_digest, "Evidence integrity digest")


@dataclass(frozen=True, slots=True)
class EvidencePackage(CanonicalModel):
    contract_version: str
    package_id: str
    candidate_id: str
    assessment_id: str | None
    items: tuple[EvidenceItem, ...]
    limitations: tuple[str, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.package_id, "Evidence package identifier")
        validate_identifier(self.candidate_id, "Evidence candidate identifier")
        if self.assessment_id is not None:
            validate_identifier(self.assessment_id, "Evidence assessment identifier")
        validate_non_empty_tuple(self.items, "Evidence package items")
        validate_unique_identifiers(self.items, "evidence_id", "Evidence package")
        ordering = tuple(
            (
                item.category.value,
                item.proposition,
                item.available_at,
                item.source_reference.artifact_id,
                item.evidence_id,
            )
            for item in self.items
        )
        if ordering != tuple(sorted(ordering)):
            raise DomainValidationError(
                "Evidence package items must use canonical ordering."
            )
        if any(item.available_at > self.audit.evidence_cutoff for item in self.items):
            raise DomainValidationError(
                "Evidence package contains future-unavailable evidence."
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError(
                "Evidence package limitation must not be empty."
            )
