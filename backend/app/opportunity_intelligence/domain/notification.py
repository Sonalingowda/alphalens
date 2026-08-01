"""Immutable notification intent and delivery audit models."""

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
    validate_sha256,
    validate_unique_identifiers,
    validate_utc,
)
from app.opportunity_intelligence.domain.stances import OpportunityStance


class NotificationEventType(StrEnum):
    OPPORTUNITY_PUBLISHED = "OPPORTUNITY_PUBLISHED"
    OPPORTUNITY_UPDATED = "OPPORTUNITY_UPDATED"
    RANK_CHANGED = "RANK_CHANGED"
    PLAN_UPDATED = "PLAN_UPDATED"
    CONFIDENCE_STATUS_CHANGED = "CONFIDENCE_STATUS_CHANGED"
    OPPORTUNITY_INVALIDATED = "OPPORTUNITY_INVALIDATED"
    OPPORTUNITY_EXPIRED = "OPPORTUNITY_EXPIRED"
    OPPORTUNITY_SUPERSEDED = "OPPORTUNITY_SUPERSEDED"
    SYSTEM_SUSPENDED = "SYSTEM_SUSPENDED"


class DeliveryState(StrEnum):
    PENDING = "PENDING"
    SUPPRESSED = "SUPPRESSED"
    IN_FLIGHT = "IN_FLIGHT"
    DELIVERED = "DELIVERED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class DeliveryAttempt(CanonicalModel):
    attempt_id: str
    sequence: int
    state: DeliveryState
    attempted_at: datetime
    provider_reference: str | None
    failure_category: str | None

    def __post_init__(self) -> None:
        validate_identifier(self.attempt_id, "Delivery attempt identifier")
        if self.sequence <= 0:
            raise DomainValidationError("Delivery attempt sequence must be positive.")
        validate_utc(self.attempted_at, "Delivery attempt time")
        if self.provider_reference is not None:
            validate_identifier(self.provider_reference, "Delivery provider reference")
        if self.failure_category is not None:
            validate_identifier(self.failure_category, "Delivery failure category")
        if self.state in {
            DeliveryState.RETRYABLE_FAILURE,
            DeliveryState.PERMANENT_FAILURE,
        } and self.failure_category is None:
            raise DomainValidationError("Failed delivery requires a failure category.")


@dataclass(frozen=True, slots=True)
class Notification(CanonicalModel):
    contract_version: str
    notification_id: str
    event_type: NotificationEventType
    opportunity_id: str | None
    opportunity_version_id: str | None
    lifecycle_event_reference: IntegrityReference
    scope: MarketScope | None
    stance: OpportunityStance | None
    score_reference: IntegrityReference | None
    rank: int | None
    confidence_reference: IntegrityReference | None
    evidence_package_reference: IntegrityReference | None
    plan_reference: IntegrityReference | None
    limitation_codes: tuple[str, ...]
    deep_link: str
    policy: PolicyReference
    deduplication_hash: str
    expires_at: datetime | None
    delivery_state: DeliveryState
    delivery_attempts: tuple[DeliveryAttempt, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.notification_id, "Notification identifier")
        if self.opportunity_id is not None:
            validate_identifier(self.opportunity_id, "Notification opportunity")
        if self.opportunity_version_id is not None:
            validate_identifier(
                self.opportunity_version_id, "Notification opportunity version"
            )
        if (self.opportunity_id is None) != (self.opportunity_version_id is None):
            raise DomainValidationError(
                "Notification opportunity identity must be wholly present or absent."
            )
        if self.rank is not None and self.rank <= 0:
            raise DomainValidationError("Notification rank must be positive.")
        for code in self.limitation_codes:
            validate_identifier(code, "Notification limitation code")
        if not self.deep_link.strip():
            raise DomainValidationError("Notification deep link must not be empty.")
        validate_sha256(self.deduplication_hash, "Notification deduplication hash")
        if self.expires_at is not None:
            validate_utc(self.expires_at, "Notification expiration")
            if self.expires_at <= self.audit.available_at:
                raise DomainValidationError(
                    "Notification expiration must follow availability."
                )
        validate_unique_identifiers(
            self.delivery_attempts, "attempt_id", "Notification delivery attempts"
        )
        sequences = tuple(attempt.sequence for attempt in self.delivery_attempts)
        if sequences and sequences != tuple(range(1, len(sequences) + 1)):
            raise DomainValidationError(
                "Delivery attempts must have contiguous ordered sequences."
            )
        if self.delivery_attempts:
            if self.delivery_state is not self.delivery_attempts[-1].state:
                raise DomainValidationError(
                    "Notification state must match its latest delivery attempt."
                )
        elif self.delivery_state is not DeliveryState.PENDING:
            raise DomainValidationError(
                "Notification without attempts must remain pending."
            )
        references = tuple(
            reference
            for reference in (
                self.lifecycle_event_reference,
                self.score_reference,
                self.confidence_reference,
                self.evidence_package_reference,
                self.plan_reference,
            )
            if reference is not None
        )
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in references
        ):
            raise DomainValidationError(
                "Notification contains a future-unavailable reference."
            )
