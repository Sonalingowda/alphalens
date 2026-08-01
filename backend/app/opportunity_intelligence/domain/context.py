"""Immutable descriptive market-context domain models."""

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


class ContextStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ContextCategory(StrEnum):
    TREND = "TREND"
    MOMENTUM = "MOMENTUM"
    VOLATILITY = "VOLATILITY"
    STRUCTURE = "STRUCTURE"
    SESSION = "SESSION"
    DATA_QUALITY = "DATA_QUALITY"


ContextValue = Decimal | str | bool


@dataclass(frozen=True, slots=True)
class ContextObservation(CanonicalModel):
    observation_id: str
    semantic_identifier: str
    value: ContextValue
    unit: str | None
    time_start: datetime
    time_end: datetime
    available_at: datetime
    source_references: tuple[IntegrityReference, ...]
    price_scope: PriceRange | None = None

    def __post_init__(self) -> None:
        validate_identifier(self.observation_id, "Context observation identifier")
        validate_identifier(self.semantic_identifier, "Context semantic identifier")
        if isinstance(self.value, str) and not self.value.strip():
            raise DomainValidationError("Context string value must not be empty.")
        if not isinstance(self.value, (Decimal, str, bool)):
            raise DomainValidationError("Context observation has an invalid value type.")
        if isinstance(self.value, Decimal):
            validate_decimal(self.value, "Context Decimal value")
        if self.unit is not None:
            validate_identifier(self.unit, "Context unit")
        validate_utc(self.time_start, "Context time start")
        validate_utc(self.time_end, "Context time end")
        validate_utc(self.available_at, "Context availability")
        if self.time_start > self.time_end:
            raise DomainValidationError("Context time start exceeds time end.")
        if self.available_at < self.time_end:
            raise DomainValidationError(
                "Context availability must not precede its time scope."
            )
        validate_non_empty_tuple(self.source_references, "Context sources")
        validate_unique_identifiers(
            self.source_references, "artifact_id", "Context sources"
        )
        if any(
            source.available_at > self.available_at
            for source in self.source_references
        ):
            raise DomainValidationError(
                "Context source is unavailable at observation availability."
            )


@dataclass(frozen=True, slots=True)
class ContextComponent(CanonicalModel):
    category: ContextCategory
    definition_id: str
    definition_version: str
    status: ContextStatus
    observations: tuple[ContextObservation, ...]
    evidence_references: tuple[IntegrityReference, ...]
    available_at: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.definition_id, "Context definition identifier")
        validate_semver(self.definition_version, "Context definition version")
        validate_utc(self.available_at, "Context component availability")
        if self.status is ContextStatus.AVAILABLE and not self.observations:
            raise DomainValidationError(
                "Available context component requires observations."
            )
        if self.status is not ContextStatus.AVAILABLE and self.observations:
            raise DomainValidationError(
                "Unavailable context component cannot contain observations."
            )
        if self.status is ContextStatus.AVAILABLE and not self.evidence_references:
            raise DomainValidationError(
                "Available context component requires evidence."
            )
        validate_unique_identifiers(
            self.observations, "observation_id", "Context observations"
        )
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Context evidence"
        )
        if any(
            observation.available_at > self.available_at
            for observation in self.observations
        ):
            raise DomainValidationError(
                "Context observation exceeds component availability."
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError("Context limitation must not be empty.")


@dataclass(frozen=True, slots=True)
class MarketContext(CanonicalModel):
    contract_version: str
    context_id: str
    scope: MarketScope
    context_timeframes: tuple[str, ...]
    trend: ContextComponent
    momentum: ContextComponent
    volatility: ContextComponent
    structure: ContextComponent
    session: ContextComponent
    data_quality: ContextComponent
    definition_set_hash: str
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.context_id, "Market context identifier")
        validate_non_empty_tuple(self.context_timeframes, "Context timeframes")
        if len(self.context_timeframes) != len(set(self.context_timeframes)):
            raise DomainValidationError("Context timeframes must be unique.")
        for timeframe in self.context_timeframes:
            validate_identifier(timeframe, "Context timeframe")
        expected = (
            (self.trend, ContextCategory.TREND),
            (self.momentum, ContextCategory.MOMENTUM),
            (self.volatility, ContextCategory.VOLATILITY),
            (self.structure, ContextCategory.STRUCTURE),
            (self.session, ContextCategory.SESSION),
            (self.data_quality, ContextCategory.DATA_QUALITY),
        )
        if any(component.category is not category for component, category in expected):
            raise DomainValidationError("Market context component category mismatch.")
        if self.data_quality.status is not ContextStatus.AVAILABLE:
            raise DomainValidationError("Data-quality context must be available.")
        if any(
            component.available_at > self.audit.evidence_cutoff
            for component, _ in expected
        ):
            raise DomainValidationError(
                "Market context contains a future-unavailable component."
            )
        validate_sha256(self.definition_set_hash, "Context definition-set hash")
