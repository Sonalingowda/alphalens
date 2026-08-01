"""Immutable dashboard and opportunity-detail projection models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.opportunity_intelligence.domain.context import MarketContext
from app.opportunity_intelligence.domain.evidence import EvidencePackage
from app.opportunity_intelligence.domain.explanation import ExplanationArtifact
from app.opportunity_intelligence.domain.lifecycle import (
    LifecycleState,
    OpportunityLifecycle,
)
from app.opportunity_intelligence.domain.market import MarketSnapshot
from app.opportunity_intelligence.domain.opportunity import Opportunity
from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_semver,
    validate_sha256,
    validate_unique_identifiers,
    validate_utc,
)
from app.opportunity_intelligence.domain.stances import OpportunityStance


@dataclass(frozen=True, slots=True)
class DashboardItem(CanonicalModel):
    opportunity_id: str
    opportunity_version_id: str
    scope: MarketScope
    stance: OpportunityStance
    lifecycle_state: LifecycleState
    evidence_cutoff: datetime
    available_at: datetime
    freshness_state: str
    rank: int
    ranking_snapshot_reference: IntegrityReference
    score_reference: IntegrityReference
    confidence_reference: IntegrityReference | None
    reason_codes: tuple[str, ...]
    has_plan: bool
    limitations: tuple[str, ...]
    detail_reference: str

    def __post_init__(self) -> None:
        validate_identifier(self.opportunity_id, "Dashboard opportunity identifier")
        validate_identifier(
            self.opportunity_version_id, "Dashboard opportunity version"
        )
        if self.stance is OpportunityStance.WAIT:
            raise DomainValidationError("Dashboard ranked item cannot be WAIT.")
        validate_utc(self.evidence_cutoff, "Dashboard evidence cutoff")
        validate_utc(self.available_at, "Dashboard availability")
        if self.evidence_cutoff > self.available_at:
            raise DomainValidationError(
                "Dashboard evidence cutoff exceeds availability."
            )
        validate_identifier(self.freshness_state, "Dashboard freshness state")
        if self.rank <= 0:
            raise DomainValidationError("Dashboard rank must be positive.")
        for code in self.reason_codes:
            validate_identifier(code, "Dashboard reason code")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise DomainValidationError("Dashboard reason codes must be unique.")
        if any(not limitation.strip() for limitation in self.limitations):
            raise DomainValidationError("Dashboard limitation must not be empty.")
        if not self.detail_reference.strip():
            raise DomainValidationError("Dashboard detail reference must not be empty.")


@dataclass(frozen=True, slots=True)
class DashboardPage(CanonicalModel):
    contract_version: str
    ranking_snapshot_reference: IntegrityReference
    ranking_snapshot_hash: str
    as_of: datetime
    generated_at: datetime
    scope: MarketScope | None
    items: tuple[DashboardItem, ...]
    applied_filters: tuple[str, ...]
    sort: str
    next_cursor: str | None
    previous_cursor: str | None
    freshness_status: str
    coverage_status: str
    partial_failures: tuple[str, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_sha256(self.ranking_snapshot_hash, "Ranking snapshot hash")
        validate_utc(self.as_of, "Dashboard page as-of")
        validate_utc(self.generated_at, "Dashboard page generation")
        if self.as_of > self.generated_at:
            raise DomainValidationError("Dashboard as-of exceeds generation time.")
        validate_unique_identifiers(self.items, "opportunity_id", "Dashboard items")
        ranks = tuple(item.rank for item in self.items)
        if ranks != tuple(sorted(ranks)):
            raise DomainValidationError("Dashboard items must preserve rank order.")
        for value, name in (
            (self.sort, "Dashboard sort"),
            (self.freshness_status, "Dashboard freshness status"),
            (self.coverage_status, "Dashboard coverage status"),
        ):
            validate_identifier(value, name)
        for filter_value in self.applied_filters:
            if not filter_value.strip():
                raise DomainValidationError("Dashboard filter must not be empty.")
        if any(not failure.strip() for failure in self.partial_failures):
            raise DomainValidationError(
                "Dashboard partial failure must not be empty."
            )


@dataclass(frozen=True, slots=True)
class IndicatorValue(CanonicalModel):
    feature_identifier: str
    definition_version: str
    output_name: str
    value: Decimal
    unit: str
    candle_timestamp: datetime
    available_at: datetime
    feature_record: IntegrityReference

    def __post_init__(self) -> None:
        validate_identifier(self.feature_identifier, "Indicator feature identifier")
        validate_semver(self.definition_version, "Indicator definition version")
        validate_identifier(self.output_name, "Indicator output name")
        validate_decimal(self.value, "Indicator value")
        validate_identifier(self.unit, "Indicator unit")
        validate_utc(self.candle_timestamp, "Indicator candle timestamp")
        validate_utc(self.available_at, "Indicator availability")
        if self.available_at < self.candle_timestamp:
            raise DomainValidationError(
                "Indicator availability must not precede its candle."
            )

    @property
    def indicator_id(self) -> str:
        return f"{self.feature_identifier}:{self.output_name}"


@dataclass(frozen=True, slots=True)
class OpportunityDetail(CanonicalModel):
    contract_version: str
    detail_id: str
    opportunity: Opportunity
    market_snapshot: MarketSnapshot
    indicators: tuple[IndicatorValue, ...]
    context: MarketContext
    evidence: EvidencePackage
    explanation: ExplanationArtifact
    lifecycle: OpportunityLifecycle
    historical_references: tuple[IntegrityReference, ...]
    verification_status: str
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.detail_id, "Opportunity detail identifier")
        validate_identifier(self.verification_status, "Detail verification status")
        opportunity_id = self.opportunity.opportunity_id
        if self.lifecycle.opportunity_id != opportunity_id:
            raise DomainValidationError("Detail lifecycle opportunity mismatch.")
        if self.explanation.opportunity_version_id != (
            self.opportunity.opportunity_version_id
        ):
            raise DomainValidationError("Detail explanation version mismatch.")
        if self.evidence.package_id != (
            self.opportunity.evidence_package_reference.artifact_id
        ):
            raise DomainValidationError("Detail evidence package mismatch.")
        scopes = (
            self.opportunity.scope,
            self.market_snapshot.scope,
            self.context.scope,
            self.lifecycle.scope,
        )
        if any(scope != scopes[0] for scope in scopes[1:]):
            raise DomainValidationError("Detail components have incompatible scopes.")
        validate_unique_identifiers(
            self.indicators, "indicator_id", "Detail indicator values"
        )
        validate_unique_identifiers(
            self.historical_references,
            "artifact_id",
            "Detail historical references",
        )
        latest_allowed = self.audit.evidence_cutoff
        if self.opportunity.audit.evidence_cutoff > latest_allowed:
            raise DomainValidationError(
                "Detail opportunity exceeds the response evidence cutoff."
            )
        if any(
            reference.available_at > latest_allowed
            for reference in self.historical_references
        ):
            raise DomainValidationError(
                "Detail historical reference exceeds the response cutoff."
            )
