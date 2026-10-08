"""Immutable, non-economic paper execution records."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    IntegrityReference,
    MarketScope,
    OpportunityStance,
)
from app.opportunity_intelligence.domain.primitives import (
    DomainValidationError,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_sha256,
    validate_non_empty_tuple,
    validate_unique_identifiers,
    validate_utc,
)


class PaperExecutionState(StrEnum):
    ACTIVE = "ACTIVE"
    ELIGIBLE = "ELIGIBLE"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PaperExitReason(StrEnum):
    TARGET_HIT = "TARGET_HIT"
    STOP_HIT = "STOP_HIT"
    EXPIRED_BEFORE_ENTRY = "EXPIRED_BEFORE_ENTRY"
    EXPIRED_AFTER_ENTRY = "EXPIRED_AFTER_ENTRY"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    # Existing OHLCV semantics deliberately retain this non-orderable case.
    AMBIGUOUS_INTRABAR = "AMBIGUOUS_INTRABAR"


class PaperTrackingEventType(StrEnum):
    PAPER_TRACKING_SELECTED = "PAPER_TRACKING_SELECTED"
    ENTRY_REACHED = "ENTRY_REACHED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EXPIRED_BEFORE_ENTRY = "EXPIRED_BEFORE_ENTRY"
    EXPIRED_AFTER_ENTRY = "EXPIRED_AFTER_ENTRY"
    AMBIGUOUS_INTRABAR = "AMBIGUOUS_INTRABAR"
    TARGET_HIT = "TARGET_HIT"
    STOP_LOSS_HIT = "STOP_LOSS_HIT"
    POST_OUTCOME_OBSERVATION = "POST_OUTCOME_OBSERVATION"


def _id(value: str, name: str) -> None:
    validate_identifier(value, name)


@dataclass(frozen=True, slots=True)
class PaperExecution(CanonicalModel):
    contract_version: str
    execution_id: str
    opportunity_id: str
    opportunity_version_id: str
    opportunity_hash: str
    plan_hash: str
    source_references: tuple[IntegrityReference, ...]
    scope: MarketScope
    direction: OpportunityStance
    signal_timestamp: datetime
    valid_until: datetime
    state: PaperExecutionState
    all_or_none: bool = True
    spread_mode: str = "NOT_MODELED"
    slippage_mode: str = "NOT_MODELED"
    fees_mode: str = "NOT_MODELED"
    latency_mode: str = "NOT_MODELED"
    source_plan_id: str | None = None
    source_plan_hash: str | None = None
    successor_plan_id: str | None = None
    successor_plan_hash: str | None = None

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        _id(self.execution_id, "Paper execution identifier")
        _id(self.opportunity_id, "Paper opportunity identifier")
        _id(self.opportunity_version_id, "Paper opportunity version")
        validate_sha256(self.opportunity_hash, "Opportunity hash")
        validate_sha256(self.plan_hash, "Plan hash")
        validate_non_empty_tuple(self.source_references, "Paper source references")
        validate_unique_identifiers(
            self.source_references, "artifact_id", "Paper source references"
        )
        validate_utc(self.signal_timestamp, "Paper signal timestamp")
        validate_utc(self.valid_until, "Paper validity")
        if self.valid_until <= self.signal_timestamp:
            raise DomainValidationError("Paper validity must follow the signal.")
        if self.execution_id != f"paper_execution:{self.opportunity_version_id}":
            raise DomainValidationError("Paper execution identity is not canonical.")
        successor_fields = (
            self.source_plan_id,
            self.source_plan_hash,
            self.successor_plan_id,
            self.successor_plan_hash,
        )
        if any(value is not None for value in successor_fields) and not all(
            value is not None for value in successor_fields
        ):
            raise DomainValidationError("Successor lineage fields must be complete.")
        for value, name in (
            (self.source_plan_id, "Source plan identifier"),
            (self.successor_plan_id, "Successor plan identifier"),
        ):
            if value is not None:
                validate_identifier(value, name)
        if self.source_plan_hash is not None:
            validate_sha256(self.source_plan_hash, "Source plan hash")
        if self.successor_plan_hash is not None:
            validate_sha256(self.successor_plan_hash, "Successor plan hash")
        if self.successor_plan_id is not None and self.plan_hash != self.successor_plan_hash:
            raise DomainValidationError("Paper plan hash must be the successor hash.")
        if self.direction.value == "WAIT":
            raise DomainValidationError("WAIT cannot create paper execution.")
        if not self.all_or_none or any(
            value != "NOT_MODELED"
            for value in (self.spread_mode, self.slippage_mode, self.fees_mode, self.latency_mode)
        ):
            raise DomainValidationError("Paper execution economics must be excluded.")


@dataclass(frozen=True, slots=True)
class PaperPosition(CanonicalModel):
    contract_version: str
    position_id: str
    execution_id: str
    opportunity_version_id: str
    state: PaperExecutionState
    entry_price: Decimal | None
    entry_timestamp: datetime | None
    entry_candle_index: int | None

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        _id(self.position_id, "Paper position identifier")
        _id(self.execution_id, "Paper execution identifier")
        _id(self.opportunity_version_id, "Paper opportunity version")
        if self.position_id != f"paper_position:{self.opportunity_version_id}":
            raise DomainValidationError("Paper position identity is not canonical.")
        if self.entry_price is not None:
            validate_decimal(self.entry_price, "Paper entry price", positive=True)
        if self.entry_timestamp is not None:
            validate_utc(self.entry_timestamp, "Paper entry timestamp")
        if self.state is PaperExecutionState.OPEN and (
            self.entry_price is None or self.entry_timestamp is None
        ):
            raise DomainValidationError("OPEN paper position requires an entry.")


@dataclass(frozen=True, slots=True)
class PaperExit(CanonicalModel):
    contract_version: str
    exit_id: str
    position_id: str
    opportunity_version_id: str
    reason: PaperExitReason
    exit_price: Decimal | None
    exit_timestamp: datetime | None
    candle_index: int | None
    candles_evaluated: int

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        _id(self.exit_id, "Paper exit identifier")
        _id(self.position_id, "Paper position identifier")
        _id(self.opportunity_version_id, "Paper opportunity version")
        if self.exit_id != f"paper_exit:{self.opportunity_version_id}":
            raise DomainValidationError("Paper exit identity is not canonical.")
        if self.candles_evaluated < 0:
            raise DomainValidationError("Paper candles evaluated must be non-negative.")
        if self.exit_price is not None:
            validate_decimal(self.exit_price, "Paper exit price", positive=True)
        if self.exit_timestamp is not None:
            validate_utc(self.exit_timestamp, "Paper exit timestamp")
        if self.reason in (PaperExitReason.TARGET_HIT, PaperExitReason.STOP_HIT):
            if self.exit_price is None or self.exit_timestamp is None or self.candle_index is None:
                raise DomainValidationError("Barrier exit requires touch evidence.")


@dataclass(frozen=True, slots=True)
class PaperOutcome(CanonicalModel):
    contract_version: str
    outcome_id: str
    execution_id: str
    position_id: str
    exit_id: str
    opportunity_version_id: str
    reason: PaperExitReason
    source_execution_hash: str
    source_position_hash: str
    source_exit_hash: str
    source_selection_event_hash: str | None = None

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        _id(self.outcome_id, "Paper outcome identifier")
        _id(self.execution_id, "Paper execution identifier")
        _id(self.position_id, "Paper position identifier")
        _id(self.exit_id, "Paper exit identifier")
        _id(self.opportunity_version_id, "Paper opportunity version")
        if self.outcome_id != f"paper_outcome:{self.opportunity_version_id}":
            raise DomainValidationError("Paper outcome identity is not canonical.")
        for value, name in (
            (self.source_execution_hash, "Source execution hash"),
            (self.source_position_hash, "Source position hash"),
            (self.source_exit_hash, "Source exit hash"),
        ):
            validate_sha256(value, name)
        if self.source_selection_event_hash is not None:
            validate_sha256(self.source_selection_event_hash, "Source selection event hash")


@dataclass(frozen=True, slots=True)
class PaperTrackingEvent(CanonicalModel):
    """Append-only event in one human-selected paper tracking history."""

    event_id: str
    execution_id: str
    position_id: str
    sequence: int
    event_type: PaperTrackingEventType
    idempotency_key: str
    occurred_at: datetime
    available_at: datetime | None
    recorded_at: datetime
    actor_id: str | None
    opportunity_id: str
    opportunity_version_id: str
    source_execution_hash: str
    source_position_hash: str
    source_artifact_id: str | None
    source_artifact_hash: str | None
    exit_id: str | None
    outcome_id: str | None
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        for value, name in (
            (self.event_id, "Paper tracking event identifier"),
            (self.execution_id, "Paper execution identifier"),
            (self.position_id, "Paper position identifier"),
            (self.idempotency_key, "Paper event idempotency key"),
            (self.opportunity_id, "Paper opportunity identifier"),
            (self.opportunity_version_id, "Paper opportunity version"),
        ):
            _id(value, name)
        if self.sequence < 1:
            raise DomainValidationError("Paper event sequence must be positive.")
        validate_utc(self.occurred_at, "Paper event occurrence time")
        validate_utc(self.recorded_at, "Paper event recording time")
        if self.available_at is not None:
            validate_utc(self.available_at, "Paper event availability time")
        if self.actor_id is not None:
            _id(self.actor_id, "Paper tracking actor identity")
        if self.event_type is PaperTrackingEventType.PAPER_TRACKING_SELECTED and not self.actor_id:
            raise DomainValidationError("Paper selection event requires an actor identity.")
        for value, name in (
            (self.source_execution_hash, "Source execution hash"),
            (self.source_position_hash, "Source position hash"),
        ):
            validate_sha256(value, name)
        if (self.source_artifact_id is None) != (self.source_artifact_hash is None):
            raise DomainValidationError("Market source identity and hash must be paired.")
        if self.source_artifact_id is not None:
            _id(self.source_artifact_id, "Market source artifact identifier")
            validate_sha256(self.source_artifact_hash, "Market source artifact hash")
        for value, name in ((self.exit_id, "Paper exit identifier"), (self.outcome_id, "Paper outcome identifier")):
            if value is not None:
                _id(value, name)
        if not isinstance(self.payload, dict):
            raise DomainValidationError("Paper tracking event payload must be an object.")
