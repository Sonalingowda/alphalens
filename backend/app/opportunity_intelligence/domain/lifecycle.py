"""Immutable opportunity lifecycle identity and event models."""

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
from app.opportunity_intelligence.domain.stances import OpportunityStance


class LifecycleState(StrEnum):
    DETECTED = "DETECTED"
    QUALIFIED = "QUALIFIED"
    RANKED = "RANKED"
    PUBLISHED = "PUBLISHED"
    UPDATED = "UPDATED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


_ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.DETECTED: frozenset(
        {
            LifecycleState.QUALIFIED,
            LifecycleState.EXPIRED,
            LifecycleState.ARCHIVED,
        }
    ),
    LifecycleState.QUALIFIED: frozenset(
        {
            LifecycleState.RANKED,
            LifecycleState.INVALIDATED,
            LifecycleState.EXPIRED,
            LifecycleState.ARCHIVED,
        }
    ),
    LifecycleState.RANKED: frozenset(
        {
            LifecycleState.PUBLISHED,
            LifecycleState.SUPERSEDED,
            LifecycleState.INVALIDATED,
            LifecycleState.EXPIRED,
        }
    ),
    LifecycleState.PUBLISHED: frozenset(
        {
            LifecycleState.UPDATED,
            LifecycleState.SUPERSEDED,
            LifecycleState.INVALIDATED,
            LifecycleState.EXPIRED,
        }
    ),
    LifecycleState.UPDATED: frozenset(
        {
            LifecycleState.RANKED,
            LifecycleState.PUBLISHED,
            LifecycleState.SUPERSEDED,
            LifecycleState.INVALIDATED,
            LifecycleState.EXPIRED,
        }
    ),
    LifecycleState.SUPERSEDED: frozenset({LifecycleState.ARCHIVED}),
    LifecycleState.INVALIDATED: frozenset({LifecycleState.ARCHIVED}),
    LifecycleState.EXPIRED: frozenset({LifecycleState.ARCHIVED}),
    LifecycleState.ARCHIVED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class LifecycleEvent(CanonicalModel):
    contract_version: str
    event_id: str
    opportunity_id: str
    opportunity_version_id: str
    prior_state: LifecycleState | None
    resulting_state: LifecycleState
    sequence: int
    policy: PolicyReference
    reason_code: str
    occurred_at: datetime
    available_at: datetime
    assessment_reference: IntegrityReference
    evidence_references: tuple[IntegrityReference, ...]
    predecessor_event_id: str | None
    successor_opportunity_version_id: str | None
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        for name, value in (
            ("Lifecycle event identifier", self.event_id),
            ("Lifecycle opportunity identifier", self.opportunity_id),
            ("Lifecycle opportunity version", self.opportunity_version_id),
            ("Lifecycle reason code", self.reason_code),
        ):
            validate_identifier(value, name)
        if self.sequence <= 0:
            raise DomainValidationError("Lifecycle sequence must be positive.")
        validate_utc(self.occurred_at, "Lifecycle occurrence")
        validate_utc(self.available_at, "Lifecycle availability")
        if self.occurred_at > self.available_at:
            raise DomainValidationError(
                "Lifecycle occurrence must not follow availability."
            )
        if self.sequence == 1:
            if self.prior_state is not None or self.resulting_state is not LifecycleState.DETECTED:
                raise DomainValidationError(
                    "First lifecycle event must enter DETECTED without prior state."
                )
            if self.predecessor_event_id is not None:
                raise DomainValidationError(
                    "First lifecycle event cannot have a predecessor."
                )
        else:
            if self.prior_state is None or self.predecessor_event_id is None:
                raise DomainValidationError(
                    "Subsequent lifecycle event requires prior state and predecessor."
                )
            validate_identifier(
                self.predecessor_event_id, "Lifecycle predecessor event"
            )
            if self.resulting_state not in _ALLOWED_TRANSITIONS[self.prior_state]:
                raise DomainValidationError("Lifecycle transition is not allowed.")
        if self.successor_opportunity_version_id is not None:
            validate_identifier(
                self.successor_opportunity_version_id,
                "Lifecycle successor opportunity version",
            )
            if self.resulting_state not in {
                LifecycleState.UPDATED,
                LifecycleState.SUPERSEDED,
            }:
                raise DomainValidationError(
                    "Successor version is valid only for update or supersession."
                )
        validate_unique_identifiers(
            self.evidence_references, "artifact_id", "Lifecycle evidence"
        )
        references = (self.assessment_reference,) + self.evidence_references
        if any(
            reference.available_at > self.audit.evidence_cutoff
            for reference in references
        ):
            raise DomainValidationError(
                "Lifecycle evidence is unavailable at the event cutoff."
            )


@dataclass(frozen=True, slots=True)
class OpportunityLifecycle(CanonicalModel):
    contract_version: str
    opportunity_id: str
    scope: MarketScope
    direction: OpportunityStance
    identity_policy: PolicyReference
    originating_candidate_id: str
    initial_evidence_cutoff: datetime
    events: tuple[LifecycleEvent, ...]
    current_event_id: str
    current_state: LifecycleState
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.opportunity_id, "Lifecycle opportunity identifier")
        validate_identifier(
            self.originating_candidate_id, "Lifecycle candidate identifier"
        )
        if self.direction is OpportunityStance.WAIT:
            raise DomainValidationError("WAIT does not have an opportunity lifecycle.")
        validate_utc(self.initial_evidence_cutoff, "Initial evidence cutoff")
        validate_non_empty_tuple(self.events, "Lifecycle events")
        validate_unique_identifiers(self.events, "event_id", "Lifecycle events")
        sequences = tuple(event.sequence for event in self.events)
        if sequences != tuple(range(1, len(self.events) + 1)):
            raise DomainValidationError(
                "Lifecycle events must have contiguous ordered sequences."
            )
        for index, event in enumerate(self.events):
            if event.opportunity_id != self.opportunity_id:
                raise DomainValidationError("Lifecycle event opportunity mismatch.")
            if index > 0:
                previous = self.events[index - 1]
                if event.predecessor_event_id != previous.event_id:
                    raise DomainValidationError(
                        "Lifecycle event predecessor is not the prior event."
                    )
                if event.prior_state is not previous.resulting_state:
                    raise DomainValidationError(
                        "Lifecycle event prior state does not match history."
                    )
                if event.available_at < previous.available_at:
                    raise DomainValidationError(
                        "Lifecycle availability must not regress."
                    )
        current = self.events[-1]
        if self.current_event_id != current.event_id:
            raise DomainValidationError("Lifecycle current event mismatch.")
        if self.current_state is not current.resulting_state:
            raise DomainValidationError("Lifecycle current state mismatch.")
        if self.initial_evidence_cutoff != self.events[0].audit.evidence_cutoff:
            raise DomainValidationError("Lifecycle initial cutoff mismatch.")
