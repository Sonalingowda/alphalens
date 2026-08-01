"""Immutable opportunity ranking snapshot models."""

from dataclasses import dataclass
from datetime import datetime

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
    validate_sha256,
    validate_unique_identifiers,
    validate_utc,
)


@dataclass(frozen=True, slots=True)
class RankingMembership(CanonicalModel):
    opportunity_id: str
    opportunity_version_id: str
    qualification_reference: IntegrityReference
    score_reference: IntegrityReference
    rank: int
    candidate_set_size: int
    valid_until: datetime

    def __post_init__(self) -> None:
        validate_identifier(self.opportunity_id, "Ranked opportunity identifier")
        validate_identifier(
            self.opportunity_version_id, "Ranked opportunity version"
        )
        if self.rank <= 0:
            raise DomainValidationError("Rank must be positive.")
        if self.candidate_set_size <= 0 or self.rank > self.candidate_set_size:
            raise DomainValidationError("Rank exceeds its candidate-set size.")
        validate_utc(self.valid_until, "Ranking membership validity")


@dataclass(frozen=True, slots=True)
class RankingExclusion(CanonicalModel):
    exclusion_id: str
    candidate_id: str
    opportunity_id: str | None
    reason_codes: tuple[str, ...]
    evidence_references: tuple[IntegrityReference, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.exclusion_id, "Ranking exclusion identifier")
        validate_identifier(self.candidate_id, "Excluded candidate identifier")
        if self.opportunity_id is not None:
            validate_identifier(self.opportunity_id, "Excluded opportunity identifier")
        validate_non_empty_tuple(self.reason_codes, "Ranking exclusion reasons")
        for code in self.reason_codes:
            validate_identifier(code, "Ranking exclusion reason")
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Ranking exclusion evidence"
        )


@dataclass(frozen=True, slots=True)
class RankingSnapshot(CanonicalModel):
    contract_version: str
    snapshot_id: str
    policy: PolicyReference
    as_of: datetime
    generated_at: datetime
    scope: MarketScope | None
    eligible_candidate_references: tuple[IntegrityReference, ...]
    qualified_opportunity_references: tuple[IntegrityReference, ...]
    memberships: tuple[RankingMembership, ...]
    exclusions: tuple[RankingExclusion, ...]
    candidate_set_hash: str
    predecessor_snapshot_id: str | None
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.snapshot_id, "Ranking snapshot identifier")
        validate_utc(self.as_of, "Ranking snapshot as-of")
        validate_utc(self.generated_at, "Ranking snapshot generation")
        if self.as_of > self.generated_at:
            raise DomainValidationError(
                "Ranking snapshot as-of must not exceed generation time."
            )
        validate_sha256(self.candidate_set_hash, "Candidate-set hash")
        validate_unique_identifiers(
            self.eligible_candidate_references,
            "artifact_id",
            "Eligible ranking candidates",
        )
        validate_unique_identifiers(
            self.qualified_opportunity_references,
            "artifact_id",
            "Qualified ranking opportunities",
        )
        validate_unique_identifiers(
            self.memberships, "opportunity_id", "Ranking memberships"
        )
        validate_unique_identifiers(
            self.exclusions, "exclusion_id", "Ranking exclusions"
        )
        ranks = tuple(membership.rank for membership in self.memberships)
        if ranks != tuple(range(1, len(self.memberships) + 1)):
            raise DomainValidationError(
                "Ranking memberships must have contiguous ordered ranks."
            )
        candidate_count = len(self.eligible_candidate_references)
        if any(
            membership.candidate_set_size != candidate_count
            for membership in self.memberships
        ):
            raise DomainValidationError(
                "Ranking membership candidate-set size mismatch."
            )
        accounted = len(self.memberships) + len(self.exclusions)
        if accounted != candidate_count:
            raise DomainValidationError(
                "Ranking snapshot must account for every eligible candidate."
            )
        if self.predecessor_snapshot_id is not None:
            validate_identifier(
                self.predecessor_snapshot_id, "Predecessor ranking snapshot"
            )
            if self.predecessor_snapshot_id == self.snapshot_id:
                raise DomainValidationError("Ranking snapshot cannot supersede itself.")
        references = (
            self.eligible_candidate_references
            + self.qualified_opportunity_references
        )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in references
        ):
            raise DomainValidationError(
                "Ranking snapshot contains future-unavailable input."
            )
