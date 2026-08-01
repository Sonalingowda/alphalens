"""Immutable runtime health and suspension models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    validate_contract_version,
    validate_identifier,
    validate_unique_identifiers,
    validate_utc,
)


class HealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RECOVERING = "RECOVERING"


@dataclass(frozen=True, slots=True)
class ComponentHealthCheck(CanonicalModel):
    check_id: str
    component: str
    status: HealthStatus
    reason_codes: tuple[str, ...]
    observed_at: datetime
    evidence_references: tuple[IntegrityReference, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.check_id, "Health check identifier")
        validate_identifier(self.component, "Health check component")
        validate_utc(self.observed_at, "Health check observation")
        for reason in self.reason_codes:
            validate_identifier(reason, "Health reason code")
        if self.status is not HealthStatus.HEALTHY and not self.reason_codes:
            raise DomainValidationError(
                "Non-healthy check requires at least one reason code."
            )
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Health check evidence"
        )


@dataclass(frozen=True, slots=True)
class RuntimeHealthRecord(CanonicalModel):
    contract_version: str
    cycle_id: str
    scope: MarketScope | None
    expected_boundary: datetime
    observed_boundary: datetime | None
    checks: tuple[ComponentHealthCheck, ...]
    status: HealthStatus
    suspension_action: str | None
    recovery_prerequisites: tuple[str, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.cycle_id, "Runtime cycle identifier")
        validate_utc(self.expected_boundary, "Expected runtime boundary")
        if self.observed_boundary is not None:
            validate_utc(self.observed_boundary, "Observed runtime boundary")
        if not self.checks:
            raise DomainValidationError("Runtime health requires component checks.")
        validate_unique_identifiers(self.checks, "check_id", "Runtime health checks")
        if self.status is HealthStatus.HEALTHY and any(
            check.status is not HealthStatus.HEALTHY for check in self.checks
        ):
            raise DomainValidationError(
                "Healthy runtime record cannot contain a non-healthy check."
            )
        if self.status is HealthStatus.SUSPENDED and self.suspension_action is None:
            raise DomainValidationError(
                "Suspended runtime record requires a suspension action."
            )
        if self.suspension_action is not None:
            validate_identifier(self.suspension_action, "Runtime suspension action")
        for prerequisite in self.recovery_prerequisites:
            validate_identifier(prerequisite, "Recovery prerequisite")
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for check in self.checks
            for reference in check.evidence_references
        ):
            raise DomainValidationError(
                "Runtime health uses evidence unavailable at its cutoff."
            )

