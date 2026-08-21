"""Immutable V2 opportunity outcome resolution models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    PolicyReference,
    validate_decimal,
    validate_identifier,
    validate_utc,
)


class OpportunityOutcome(StrEnum):
    """Canonical terminal outcome for a V2 opportunity evaluation.

    Each resolved opportunity produces exactly one terminal outcome.
    """

    TARGET_HIT = "TARGET_HIT"
    STOP_HIT = "STOP_HIT"
    EXPIRED = "EXPIRED"
    UNRESOLVED = "UNRESOLVED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class OutcomeRecord(CanonicalModel):
    """Immutable record of a resolved V2 opportunity outcome.

    One record per opportunity. The outcome is determined strictly from
    post-signal candles after the signal timestamp and before valid_until.
    """

    contract_version: str
    outcome_id: str
    opportunity_id: str
    opportunity_version_id: str
    lifecycle_id: str
    outcome: OpportunityOutcome
    direction: str
    reference_price: Decimal
    entry_zone_lower: Decimal
    entry_zone_upper: Decimal
    invalidation_price: Decimal
    target_price: Decimal
    signal_timestamp: datetime
    outcome_interval_start: datetime
    outcome_interval_end: datetime
    resolved_at: datetime
    candles_evaluated: int
    first_touch_price: Decimal | None
    first_touch_timestamp: datetime | None
    first_touch_candle_index: int | None
    exclusion_reason: str | None
    policy: PolicyReference
    evidence_references: tuple[IntegrityReference, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_identifier(self.outcome_id, "Outcome identifier")
        validate_identifier(self.opportunity_id, "Outcome opportunity identifier")
        validate_identifier(
            self.opportunity_version_id, "Outcome opportunity version identifier"
        )
        validate_identifier(self.lifecycle_id, "Outcome lifecycle identifier")
        validate_identifier(self.direction, "Outcome direction")
        validate_decimal(self.reference_price, "Outcome reference price", positive=True)
        validate_decimal(
            self.entry_zone_lower, "Outcome entry zone lower", positive=True
        )
        validate_decimal(
            self.entry_zone_upper, "Outcome entry zone upper", positive=True
        )
        validate_decimal(
            self.invalidation_price, "Outcome invalidation price", positive=True
        )
        validate_decimal(self.target_price, "Outcome target price", positive=True)
        validate_utc(self.signal_timestamp, "Outcome signal timestamp")
        validate_utc(
            self.outcome_interval_start, "Outcome interval start"
        )
        validate_utc(self.outcome_interval_end, "Outcome interval end")
        validate_utc(self.resolved_at, "Outcome resolved at")

        if self.outcome_interval_start >= self.outcome_interval_end:
            raise DomainValidationError(
                "Outcome interval start must precede interval end."
            )
        if self.signal_timestamp > self.outcome_interval_start:
            raise DomainValidationError(
                "Outcome signal timestamp must not follow interval start."
            )
        if self.resolved_at < self.outcome_interval_end:
            raise DomainValidationError(
                "Outcome resolution must occur at or after interval end."
            )
        if self.candles_evaluated < 0:
            raise DomainValidationError(
                "Outcome candles evaluated must be non-negative."
            )
        if self.entry_zone_lower > self.entry_zone_upper:
            raise DomainValidationError(
                "Outcome entry zone lower must not exceed upper."
            )

        if self.outcome is OpportunityOutcome.INVALIDATED:
            if self.exclusion_reason is None:
                raise DomainValidationError(
                    "INVALIDATED outcome requires an exclusion reason."
                )
        else:
            if self.exclusion_reason is not None:
                raise DomainValidationError(
                    "Non-INVALIDATED outcome must not have an exclusion reason."
                )

        if self.outcome in (
            OpportunityOutcome.TARGET_HIT,
            OpportunityOutcome.STOP_HIT,
            OpportunityOutcome.UNRESOLVED,
        ):
            if self.first_touch_price is None:
                raise DomainValidationError(
                    f"{self.outcome.value} outcome requires a first touch price."
                )
            if self.first_touch_timestamp is None:
                raise DomainValidationError(
                    f"{self.outcome.value} outcome requires a first touch timestamp."
                )
            if self.first_touch_candle_index is None:
                raise DomainValidationError(
                    f"{self.outcome.value} outcome requires a first touch candle index."
                )
