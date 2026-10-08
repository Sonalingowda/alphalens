"""Post-selection observations over canonical real Binance candle snapshots."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from app.opportunity_intelligence.domain import (
    MarketCandleSnapshot,
    Opportunity,
    OpportunityOutcome,
)
from app.outcome_resolution.service import _determine_entry, _determine_outcome
from app.paper_execution.domain import (
    PaperExecutionState,
    PaperExit,
    PaperExitReason,
    PaperOutcome,
    PaperTrackingEvent,
    PaperTrackingEventType,
)
from app.paper_execution.selection import PaperTrackingSelection


class _EventWriter(Protocol):
    async def save_events(
        self,
        execution,
        position,
        events: tuple[PaperTrackingEvent, ...],
        *,
        exit_record: PaperExit | None = None,
        outcome: PaperOutcome | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class PaperObservationResult:
    status: str
    active: bool
    events: tuple[PaperTrackingEvent, ...]
    exit: PaperExit | None = None
    outcome: PaperOutcome | None = None


class PaperTrackingObservationService:
    """Resolve only approved outcomes from data after the durable selection."""

    def __init__(self, *, persistence: _EventWriter) -> None:
        self._persistence = persistence

    async def observe(
        self,
        *,
        selection: PaperTrackingSelection,
        opportunity: Opportunity,
        candles: tuple[MarketCandleSnapshot, ...],
        existing_events: tuple[PaperTrackingEvent, ...],
        observed_at: datetime,
    ) -> PaperObservationResult:
        _validate_source(selection, opportunity)
        _validate_utc(observed_at)
        terminal = _terminal_event(existing_events)
        if terminal is not None:
            raise ValueError("Official outcome is closed; use post_outcome_observations.")

        selection_at = selection.selection_event.occurred_at
        valid = tuple(
            candle
            for candle in candles
            if (
                selection_at <= candle.timestamp <= observed_at
                and selection_at <= candle.available_at <= observed_at
            )
        )
        _validate_binance_sources(selection, valid)
        if not valid:
            event = _build_event(
                selection=selection,
                sequence=_next_sequence(existing_events),
                event_type=PaperTrackingEventType.DATA_INSUFFICIENT,
                idempotency_key=f"paper_data_insufficient:{selection.opportunity_version_id}",
                occurred_at=observed_at,
                available_at=None,
                actor_id=None,
                source=None,
                exit_id=None,
                outcome_id=None,
                payload={"reason": "no_post_selection_market_candles_available"},
            )
            if any(item.idempotency_key == event.idempotency_key for item in existing_events):
                return PaperObservationResult("DATA_INSUFFICIENT", True, ())
            await self._persistence.save_events(
                selection.execution, selection.position, (event,)
            )
            return PaperObservationResult("DATA_INSUFFICIENT", True, (event,))

        plan = opportunity.plan
        if plan is None:
            raise ValueError("The immutable source plan is unavailable.")
        candle_dicts = tuple(_candle_dict(item) for item in valid)
        entry_reached, entry_timestamp, entry_index = _determine_entry(
            opportunity.stance.value,
            plan.entry_zone.lower,
            plan.entry_zone.upper,
            selection_at,
            candle_dicts,
        )
        resolution, evaluated, touch_price, touch_timestamp, touch_index, _ = _determine_outcome(
            direction=opportunity.stance.value,
            reference_price=plan.reference_price,
            entry_zone_lower=plan.entry_zone.lower,
            entry_zone_upper=plan.entry_zone.upper,
            invalidation_price=plan.invalidation_price,
            target_price=plan.targets[0].price,
            signal_timestamp=selection_at,
            # The original opportunity expiry is deliberately not a paper-track cutoff.
            valid_until=max(item.timestamp for item in valid),
            candles=candle_dicts,
        )

        events: list[PaperTrackingEvent] = []
        existing_types = {item.event_type for item in existing_events}
        if entry_reached and PaperTrackingEventType.ENTRY_REACHED not in existing_types:
            source = valid[entry_index]
            events.append(
                _build_event(
                    selection=selection,
                    sequence=_next_sequence(existing_events),
                    event_type=PaperTrackingEventType.ENTRY_REACHED,
                    idempotency_key=f"paper_entry:{selection.opportunity_version_id}:{source.candle_id}",
                    occurred_at=entry_timestamp,
                    available_at=source.available_at,
                    actor_id=None,
                    source=source,
                    exit_id=None,
                    outcome_id=None,
                    payload={"candle": source.to_dict(), "entry_index": entry_index},
                )
            )

        if resolution in (OpportunityOutcome.TARGET_HIT, OpportunityOutcome.STOP_HIT):
            if touch_timestamp is None or touch_index is None or touch_price is None:
                raise ValueError("Approved terminal resolution lacks real candle touch evidence.")
            source = valid[touch_index]
            reason = (
                PaperExitReason.TARGET_HIT
                if resolution is OpportunityOutcome.TARGET_HIT
                else PaperExitReason.STOP_HIT
            )
            exit_record = PaperExit(
                contract_version="1.0.0",
                exit_id=f"paper_exit:{selection.opportunity_version_id}",
                position_id=selection.position.position_id,
                opportunity_version_id=selection.opportunity_version_id,
                reason=reason,
                exit_price=touch_price,
                exit_timestamp=touch_timestamp,
                candle_index=touch_index,
                candles_evaluated=evaluated,
            )
            outcome = PaperOutcome(
                contract_version="1.0.0",
                outcome_id=f"paper_outcome:{selection.opportunity_version_id}",
                execution_id=selection.execution.execution_id,
                position_id=selection.position.position_id,
                exit_id=exit_record.exit_id,
                opportunity_version_id=selection.opportunity_version_id,
                reason=reason,
                source_execution_hash=selection.execution.canonical_sha256(),
                source_position_hash=selection.position.canonical_sha256(),
                source_exit_hash=exit_record.canonical_sha256(),
                source_selection_event_hash=selection.selection_event.canonical_sha256(),
            )
            event_type = (
                PaperTrackingEventType.TARGET_HIT
                if reason is PaperExitReason.TARGET_HIT
                else PaperTrackingEventType.STOP_LOSS_HIT
            )
            terminal_event = _build_event(
                selection=selection,
                sequence=_next_sequence(existing_events) + len(events),
                event_type=event_type,
                idempotency_key=f"paper_terminal:{selection.opportunity_version_id}:{source.candle_id}",
                occurred_at=touch_timestamp,
                available_at=source.available_at,
                actor_id=None,
                source=source,
                exit_id=exit_record.exit_id,
                outcome_id=outcome.outcome_id,
                payload={"candle": source.to_dict(), "official_reason": reason.value},
            )
            events.append(terminal_event)
            await self._persistence.save_events(
                selection.execution,
                selection.position,
                tuple(events),
                exit_record=exit_record,
                outcome=outcome,
            )
            return PaperObservationResult(reason.value, False, tuple(events), exit_record, outcome)

        if resolution is OpportunityOutcome.AMBIGUOUS_INTRABAR:
            ambiguous_index = max(evaluated - 1, 0)
            source = valid[ambiguous_index]
            event = _build_event(
                selection=selection,
                sequence=_next_sequence(existing_events) + len(events),
                event_type=PaperTrackingEventType.AMBIGUOUS_INTRABAR,
                idempotency_key=f"paper_ambiguous:{selection.opportunity_version_id}:{source.candle_id}",
                occurred_at=source.timestamp,
                available_at=source.available_at,
                actor_id=None,
                source=source,
                exit_id=None,
                outcome_id=None,
                payload={"candle": source.to_dict(), "resolution": "ordering_unavailable"},
            )
            if not any(item.idempotency_key == event.idempotency_key for item in existing_events):
                events.append(event)

        if resolution in (
            OpportunityOutcome.EXPIRED_BEFORE_ENTRY,
            OpportunityOutcome.EXPIRED_AFTER_ENTRY,
        ):
            source = valid[-1]
            event_type = (
                PaperTrackingEventType.EXPIRED_BEFORE_ENTRY
                if resolution is OpportunityOutcome.EXPIRED_BEFORE_ENTRY
                else PaperTrackingEventType.EXPIRED_AFTER_ENTRY
            )
            event = _build_event(
                selection=selection,
                sequence=_next_sequence(existing_events) + len(events),
                event_type=event_type,
                idempotency_key=f"paper_expiry:{selection.opportunity_version_id}:{source.candle_id}",
                occurred_at=source.timestamp,
                available_at=source.available_at,
                actor_id=None,
                source=source,
                exit_id=None,
                outcome_id=None,
                payload={"candle": source.to_dict(), "resolution": resolution.value},
            )
            if not any(item.idempotency_key == event.idempotency_key for item in existing_events):
                events.append(event)

        # Expiry before/after entry and ambiguity are non-terminal. Entry is
        # recorded as an event; the immutable PaperPosition remains ACTIVE.
        if events:
            await self._persistence.save_events(
                selection.execution, selection.position, tuple(events)
            )
        return PaperObservationResult(resolution.value, True, tuple(events))

    async def post_outcome_observations(
        self,
        *,
        selection: PaperTrackingSelection,
        terminal_event: PaperTrackingEvent,
        candles: tuple[MarketCandleSnapshot, ...],
        existing_events: tuple[PaperTrackingEvent, ...],
    ) -> tuple[PaperTrackingEvent, ...]:
        if terminal_event.event_type not in (
            PaperTrackingEventType.TARGET_HIT,
            PaperTrackingEventType.STOP_LOSS_HIT,
        ):
            raise ValueError("Post-outcome monitoring requires an approved terminal event.")
        candidates = tuple(
            candle
            for candle in candles
            if candle.timestamp > terminal_event.occurred_at
            and candle.timestamp >= selection.selected_at
            and candle.available_at >= selection.selected_at
        )
        _validate_binance_sources(selection, candidates)
        existing_keys = {item.idempotency_key for item in existing_events}
        sequence = _next_sequence(existing_events)
        events: list[PaperTrackingEvent] = []
        for candle in candidates:
            key = f"paper_post_outcome:{selection.opportunity_version_id}:{candle.candle_id}"
            if key in existing_keys:
                continue
            events.append(
                _build_event(
                    selection=selection,
                    sequence=sequence + len(events),
                    event_type=PaperTrackingEventType.POST_OUTCOME_OBSERVATION,
                    idempotency_key=key,
                    occurred_at=candle.timestamp,
                    available_at=candle.available_at,
                    actor_id=None,
                    source=candle,
                    exit_id=terminal_event.exit_id,
                    outcome_id=terminal_event.outcome_id,
                    payload={"candle": candle.to_dict()},
                )
            )

        if events:
            await self._persistence.save_events(
                selection.execution, selection.position, tuple(events)
            )
        return tuple(events)


def _validate_source(selection: PaperTrackingSelection, opportunity: Opportunity) -> None:
    if opportunity.plan is None:
        raise ValueError("The immutable source plan is unavailable.")
    if opportunity.canonical_sha256() != selection.execution.opportunity_hash:
        raise ValueError("Opportunity differs from the immutable selected snapshot.")
    if opportunity.plan.canonical_sha256() != selection.execution.plan_hash:
        raise ValueError("Plan differs from the immutable selected snapshot.")
    if selection.execution.state is not PaperExecutionState.ACTIVE:
        raise ValueError("Tracking snapshot state is invalid.")


def _validate_binance_sources(
    selection: PaperTrackingSelection,
    candles: tuple[MarketCandleSnapshot, ...],
) -> None:
    scope_prefix = (
        f"binance.spot.{selection.execution.scope.instrument}."
        f"{selection.execution.scope.timeframe}."
    )
    for candle in candles:
        source = candle.source_reference
        if source.artifact_type != "binance_spot_completed_kline" or not source.artifact_id.startswith(scope_prefix):
            raise ValueError("Paper observation requires the existing scoped Binance completed-kline source.")


def _candle_dict(candle: MarketCandleSnapshot) -> dict:
    return {
        "timestamp": candle.timestamp,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def _build_event(
    *,
    selection: PaperTrackingSelection,
    sequence: int,
    event_type: PaperTrackingEventType,
    idempotency_key: str,
    occurred_at: datetime,
    available_at: datetime | None,
    actor_id: str | None,
    source: MarketCandleSnapshot | None,
    exit_id: str | None,
    outcome_id: str | None,
    payload: dict,
) -> PaperTrackingEvent:
    return PaperTrackingEvent(
        event_id=f"paper_event:{selection.opportunity_version_id}:{sequence}",
        execution_id=selection.execution.execution_id,
        position_id=selection.position.position_id,
        sequence=sequence,
        event_type=event_type,
        idempotency_key=idempotency_key,
        occurred_at=occurred_at,
        available_at=available_at,
        recorded_at=datetime.now(timezone.utc),
        actor_id=actor_id,
        opportunity_id=selection.opportunity_id,
        opportunity_version_id=selection.opportunity_version_id,
        source_execution_hash=selection.execution.canonical_sha256(),
        source_position_hash=selection.position.canonical_sha256(),
        source_artifact_id=source.source_reference.artifact_id if source else None,
        source_artifact_hash=source.source_reference.integrity_digest if source else None,
        exit_id=exit_id,
        outcome_id=outcome_id,
        payload=payload,
    )


def _terminal_event(events: tuple[PaperTrackingEvent, ...]) -> PaperTrackingEvent | None:
    return next(
        (
            event
            for event in events
            if event.event_type in (
                PaperTrackingEventType.TARGET_HIT,
                PaperTrackingEventType.STOP_LOSS_HIT,
            )
        ),
        None,
    )


def _next_sequence(events: tuple[PaperTrackingEvent, ...]) -> int:
    return max((event.sequence for event in events), default=0) + 1


def _validate_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("Paper observation time must be UTC-aware.")
