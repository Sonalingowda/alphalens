"""Fail-closed validators for frozen Opportunity Intelligence contracts."""

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    LifecycleEvent,
    OpportunityLifecycle,
    canonical_json,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import ContractViolationError


VALIDATION_VERSION = "1.0.0"


def validate_contract_model(
    entity: CanonicalModel,
    expected_type: type[CanonicalModel] | None = None,
) -> CanonicalModel:
    """Validate type, version, canonical schema, and deterministic serialization."""
    if not isinstance(entity, CanonicalModel):
        raise ContractViolationError("Boundary value must be a canonical model.")
    if expected_type is not None and not isinstance(entity, expected_type):
        raise ContractViolationError(
            f"Boundary requires {expected_type.__name__}; received {type(entity).__name__}."
        )
    contract_version = getattr(entity, "contract_version", "1.0.0")
    if contract_version != "1.0.0":
        raise ContractViolationError("Unsupported contract version.")
    try:
        first = canonical_json(entity)
        second = canonical_json(entity)
        digest = canonical_sha256(entity)
    except (TypeError, ValueError) as error:
        raise ContractViolationError("Canonical serialization failed.") from error
    if first != second or len(digest) != 64:
        raise ContractViolationError("Canonical serialization is not deterministic.")
    return entity


def verify_provenance(entity: CanonicalModel) -> CanonicalModel:
    """Verify structural provenance and point-in-time source availability."""
    validate_contract_model(entity)
    audit = getattr(entity, "audit", None)
    if audit is None:
        raise ContractViolationError("Persisted aggregate requires audit metadata.")
    provenance = getattr(audit, "provenance", None)
    if provenance is None or not provenance.source_references:
        raise ContractViolationError("Aggregate provenance requires source references.")
    if any(
        reference.available_at > audit.evidence_cutoff
        for reference in provenance.source_references
    ):
        raise ContractViolationError("Provenance contains future-unavailable input.")
    return entity


def validate_lifecycle_transition(
    lifecycle: OpportunityLifecycle,
    event: LifecycleEvent,
) -> LifecycleEvent:
    """Validate a proposed immutable successor against its complete history."""
    validate_contract_model(lifecycle, OpportunityLifecycle)
    validate_contract_model(event, LifecycleEvent)
    if event.opportunity_id != lifecycle.opportunity_id:
        raise ContractViolationError("Lifecycle transition identity mismatch.")
    if event.sequence != len(lifecycle.events) + 1:
        raise ContractViolationError("Lifecycle transition sequence is not contiguous.")
    if event.predecessor_event_id != lifecycle.current_event_id:
        raise ContractViolationError("Lifecycle transition predecessor mismatch.")
    if event.prior_state is not lifecycle.current_state:
        raise ContractViolationError("Lifecycle transition prior state mismatch.")
    return event
