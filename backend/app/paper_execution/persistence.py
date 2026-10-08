"""Dedicated append-only persistence for the isolated paper namespace."""

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.paper_execution.domain import (
    PaperExecution,
    PaperExit,
    PaperOutcome,
    PaperPosition,
    PaperTrackingEvent,
    PaperTrackingEventType,
)
from app.paper_execution.successor import PaperSuccessorPlan
from app.persistence.models import (
    PaperExecutionRecord,
    PaperExitRecord,
    PaperOutcomeRecord,
    PaperPositionRecord,
    PaperSuccessorPlanRecord,
    PaperTrackingEventRecord,
)


class InMemoryPaperSuccessorPlanRepository:
    """Idempotent isolated successor storage used by focused tests."""

    def __init__(self) -> None:
        self._records: dict[str, PaperSuccessorPlan] = {}

    def save(self, successor: PaperSuccessorPlan) -> PaperSuccessorPlan:
        existing = self._records.get(successor.successor_plan_id)
        if existing is not None and existing.canonical_sha256() != successor.canonical_sha256():
            raise ValueError(f"Immutable successor identity conflict: {successor.successor_plan_id}")
        self._records[successor.successor_plan_id] = existing or successor
        return self._records[successor.successor_plan_id]


class PaperSuccessorPlanPersistence:
    """Append-only persistence for the isolated successor namespace."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save(self, successor: PaperSuccessorPlan) -> None:
        async with self._sessions.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"alphalens.paper_successor_plan:{successor.successor_plan_id}"},
            )
            existing = await session.scalar(
                select(PaperSuccessorPlanRecord).where(
                    PaperSuccessorPlanRecord.successor_plan_id == successor.successor_plan_id
                )
            )
            if existing is not None:
                if existing.successor_plan_canonical_hash != successor.successor_plan_canonical_hash:
                    raise ValueError(f"Immutable successor identity conflict: {successor.successor_plan_id}")
                return
            session.add(
                PaperSuccessorPlanRecord(
                    successor_plan_id=successor.successor_plan_id,
                    source_opportunity_version_id=successor.source_opportunity_version_id,
                    source_opportunity_id=successor.source_opportunity_id,
                    source_plan_id=successor.source_plan_id,
                    source_plan_canonical_hash=successor.source_plan_canonical_hash,
                    successor_plan_canonical_hash=successor.successor_plan_canonical_hash,
                    canonical_payload=successor.to_dict(),
                )
            )


class InMemoryPaperExecutionRepository:
    """Test/local adapter with the same immutable identity contract as SQL."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[PaperExecution, PaperPosition, PaperExit, PaperOutcome]] = {}
        self._active: dict[str, tuple[PaperExecution, PaperPosition, PaperTrackingEvent]] = {}
        self._events_by_key: dict[str, PaperTrackingEvent] = {}

    def save_selection(
        self,
        execution: PaperExecution,
        position: PaperPosition,
        event: PaperTrackingEvent,
    ) -> tuple[PaperExecution, PaperPosition, PaperTrackingEvent]:
        identity = execution.execution_id
        value = (execution, position, event)
        existing = self._active.get(identity)
        if existing is not None:
            if tuple(item.canonical_sha256() for item in existing[:2]) != tuple(
                item.canonical_sha256() for item in value[:2]
            ):
                raise ValueError(f"Immutable paper identity conflict: {identity}")
            if (
                existing[2].idempotency_key != event.idempotency_key
                or existing[2].payload.get("confirmed_scenario_hash")
                != event.payload.get("confirmed_scenario_hash")
            ):
                raise ValueError(f"Paper selection event conflict: {identity}")
            return existing
        if identity in self._records:
            raise ValueError(f"Paper execution already has a terminal record: {identity}")
        self._active[identity] = value
        self._events_by_key[event.idempotency_key] = event
        return value

    def save_events(
        self,
        execution: PaperExecution,
        position: PaperPosition,
        events: tuple[PaperTrackingEvent, ...],
        *,
        exit_record: PaperExit | None = None,
        outcome: PaperOutcome | None = None,
    ) -> tuple[PaperTrackingEvent, ...]:
        if not events:
            raise ValueError("At least one tracking event is required.")
        existing = tuple(self._events_by_key.get(event.idempotency_key) for event in events)
        if all(item is not None for item in existing):
            if tuple(item.canonical_sha256() for item in existing) != tuple(
                event.canonical_sha256() for event in events
            ):
                raise ValueError("Immutable paper event idempotency conflict.")
            return existing  # type: ignore[return-value]
        if any(item is not None for item in existing):
            raise ValueError("Partial paper event batch already exists.")
        active = self._active.get(execution.execution_id)
        if active is None or active[0].canonical_sha256() != execution.canonical_sha256():
            raise ValueError("Paper tracking selection does not exist or has changed.")
        if active[1].canonical_sha256() != position.canonical_sha256():
            raise ValueError("Paper position snapshot has changed.")
        last_sequence = max(
            (event.sequence for event in self._events_by_key.values() if event.execution_id == execution.execution_id),
            default=0,
        )
        if tuple(event.sequence for event in events) != tuple(
            range(last_sequence + 1, last_sequence + len(events) + 1)
        ):
            raise ValueError("Paper event sequence is not contiguous.")
        if (exit_record is None) != (outcome is None):
            raise ValueError("Terminal exit and outcome must be persisted together.")
        if outcome is not None:
            if execution.execution_id in self._records:
                raise ValueError("Paper outcome is already closed.")
            self._records[execution.execution_id] = (
                execution,
                position,
                exit_record,  # type: ignore[arg-type]
                outcome,
            )
        for event in events:
            self._events_by_key[event.idempotency_key] = event
        return events

    def save(self, execution: PaperExecution, position: PaperPosition,
             exit_record: PaperExit, outcome: PaperOutcome) -> tuple[PaperExecution, PaperPosition, PaperExit, PaperOutcome]:
        identity = execution.execution_id
        value = (execution, position, exit_record, outcome)
        existing = self._records.get(identity)
        if existing is not None:
            if tuple(item.canonical_sha256() for item in existing) != tuple(item.canonical_sha256() for item in value):
                raise ValueError(f"Immutable paper identity conflict: {identity}")
            return existing
        self._records[identity] = value
        return value


class PaperExecutionPersistence:
    """Persist one immutable lineage atomically and idempotently."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def save_selection(
        self,
        execution: PaperExecution,
        position: PaperPosition,
        event: PaperTrackingEvent,
    ) -> tuple[PaperExecution, PaperPosition, PaperTrackingEvent]:
        """Atomically create an active execution, position, and selection event."""
        if execution.state.value != "ACTIVE" or position.state.value != "ACTIVE":
            raise ValueError("A new paper selection must begin in ACTIVE snapshot state.")
        if position.entry_price is not None or position.entry_timestamp is not None:
            raise ValueError("A new paper selection cannot contain an evaluated entry.")
        async with self._sessions.begin() as session:
            await self._lock(session, execution.execution_id)
            existing_execution = await session.scalar(
                select(PaperExecutionRecord).where(
                    PaperExecutionRecord.identity == execution.execution_id
                )
            )
            existing_position = await session.scalar(
                select(PaperPositionRecord).where(
                    PaperPositionRecord.identity == position.position_id
                )
            )
            existing_event = await session.scalar(
                select(PaperTrackingEventRecord).where(
                    PaperTrackingEventRecord.idempotency_key == event.idempotency_key
                )
            )
            if any(item is not None for item in (existing_execution, existing_position, existing_event)):
                expected = (
                    (existing_execution, execution),
                    (existing_position, position),
                    (existing_event, event),
                )
                if any(item is None for item, _ in expected):
                    raise ValueError("Partial paper selection lineage exists; refusing repair by overwrite.")
                if existing_execution.canonical_hash != execution.canonical_sha256():
                    raise ValueError("Immutable paper execution identity conflict.")
                if existing_position.canonical_hash != position.canonical_sha256():
                    raise ValueError("Immutable paper position identity conflict.")
                stored_scenario = (existing_event.canonical_payload or {}).get("payload", {}).get(
                    "confirmed_scenario_hash"
                )
                if stored_scenario != event.payload.get("confirmed_scenario_hash"):
                    raise ValueError("Immutable paper selection event conflict.")
                return execution, position, _event_from_record(existing_event)
            session.add(_record(PaperExecutionRecord, execution.execution_id, execution))
            session.add(
                PaperPositionRecord(
                    **_record_values(position.position_id, position),
                    execution_id=execution.execution_id,
                )
            )
            session.add(_event_record(event))
            return execution, position, event

    async def save_events(
        self,
        execution: PaperExecution,
        position: PaperPosition,
        events: tuple[PaperTrackingEvent, ...],
        *,
        exit_record: PaperExit | None = None,
        outcome: PaperOutcome | None = None,
    ) -> None:
        """Persist a contiguous event batch and optional terminal lineage atomically."""
        if not events:
            raise ValueError("At least one tracking event is required.")
        if (exit_record is None) != (outcome is None):
            raise ValueError("Terminal exit and outcome must be persisted together.")
        async with self._sessions.begin() as session:
            await self._lock(session, execution.execution_id)
            stored_execution = await session.scalar(
                select(PaperExecutionRecord).where(PaperExecutionRecord.identity == execution.execution_id)
            )
            stored_position = await session.scalar(
                select(PaperPositionRecord).where(PaperPositionRecord.identity == position.position_id)
            )
            if stored_execution is None or stored_position is None:
                raise ValueError("Paper tracking selection does not exist.")
            if stored_execution.canonical_hash != execution.canonical_sha256() or stored_position.canonical_hash != position.canonical_sha256():
                raise ValueError("Paper tracking source snapshot changed.")

            existing_events = tuple(
                await session.scalars(
                    select(PaperTrackingEventRecord).where(
                        PaperTrackingEventRecord.idempotency_key.in_(
                            tuple(event.idempotency_key for event in events)
                        )
                    )
                )
            )
            if existing_events:
                by_key = {item.idempotency_key: item for item in existing_events}
                if len(by_key) != len(events) or any(
                    by_key.get(event.idempotency_key) is None
                    or by_key[event.idempotency_key].canonical_hash != event.canonical_sha256()
                    for event in events
                ):
                    raise ValueError("Paper event idempotency conflict or partial event batch.")
                return

            prior_sequence = await session.scalar(
                select(func.max(PaperTrackingEventRecord.sequence)).where(
                    PaperTrackingEventRecord.execution_id == execution.execution_id
                )
            )
            expected = int(prior_sequence or 0) + 1
            if tuple(event.sequence for event in events) != tuple(
                range(expected, expected + len(events))
            ):
                raise ValueError("Paper event sequence is not contiguous.")

            if outcome is not None and outcome.reason.value not in ("TARGET_HIT", "STOP_HIT"):
                raise ValueError("Only target or stop loss can close a human paper track.")
            if outcome is not None:
                existing_outcome = await session.scalar(
                    select(PaperOutcomeRecord).where(PaperOutcomeRecord.identity == outcome.outcome_id)
                )
                if existing_outcome is not None:
                    raise ValueError("Official paper outcome is already closed.")
                session.add(
                    PaperExitRecord(
                        **_record_values(exit_record.exit_id, exit_record),
                        position_id=exit_record.position_id,
                    )
                )
                session.add(
                    PaperOutcomeRecord(
                        **_record_values(outcome.outcome_id, outcome),
                        execution_id=outcome.execution_id,
                        position_id=outcome.position_id,
                        exit_id=outcome.exit_id,
                    )
                )
            for event in events:
                session.add(_event_record(event))

    @staticmethod
    async def _lock(session: AsyncSession, execution_id: str) -> None:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"alphalens.paper_execution:{execution_id}"},
        )

    async def save(self, execution: PaperExecution, position: PaperPosition,
                   exit_record: PaperExit, outcome: PaperOutcome) -> None:
        records = (
            (PaperExecutionRecord, execution.execution_id, execution),
            (PaperPositionRecord, position.position_id, position),
            (PaperExitRecord, exit_record.exit_id, exit_record),
            (PaperOutcomeRecord, outcome.outcome_id, outcome),
        )
        async with self._sessions.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"alphalens.paper_execution:{execution.execution_id}"},
            )
            for model, identity, entity in records:
                existing = await session.scalar(select(model).where(model.identity == identity))
                if existing is not None:
                    if existing.canonical_hash != entity.canonical_sha256():
                        raise ValueError(f"Immutable paper identity conflict: {identity}")
                    continue
                values = dict(
                    identity=identity,
                    opportunity_version_id=entity.opportunity_version_id,
                    canonical_payload=entity.to_dict(),
                    canonical_hash=entity.canonical_sha256(),
                )
                if model is PaperPositionRecord:
                    values["execution_id"] = entity.execution_id
                if model is PaperExitRecord:
                    values["position_id"] = entity.position_id
                if model is PaperOutcomeRecord:
                    values.update(
                        execution_id=entity.execution_id,
                        position_id=entity.position_id,
                        exit_id=entity.exit_id,
                    )
                session.add(model(**values))


def _record_values(identity: str, entity) -> dict:
    return {
        "identity": identity,
        "opportunity_version_id": entity.opportunity_version_id,
        "canonical_payload": entity.to_dict(),
        "canonical_hash": entity.canonical_sha256(),
    }


def _record(model, identity: str, entity):
    return model(**_record_values(identity, entity))


def _event_record(event: PaperTrackingEvent) -> PaperTrackingEventRecord:
    return PaperTrackingEventRecord(
        event_id=event.event_id,
        execution_id=event.execution_id,
        position_id=event.position_id,
        sequence=event.sequence,
        event_type=event.event_type.value,
        idempotency_key=event.idempotency_key,
        occurred_at=event.occurred_at,
        available_at=event.available_at,
        recorded_at=event.recorded_at,
        actor_id=event.actor_id,
        opportunity_id=event.opportunity_id,
        opportunity_version_id=event.opportunity_version_id,
        source_execution_hash=event.source_execution_hash,
        source_position_hash=event.source_position_hash,
        source_artifact_id=event.source_artifact_id,
        source_artifact_hash=event.source_artifact_hash,
        exit_id=event.exit_id,
        outcome_id=event.outcome_id,
        canonical_payload=event.to_dict(),
        canonical_hash=event.canonical_sha256(),
    )


def _event_from_record(record: PaperTrackingEventRecord) -> PaperTrackingEvent:
    payload = record.canonical_payload
    return PaperTrackingEvent(
        event_id=record.event_id,
        execution_id=record.execution_id,
        position_id=record.position_id,
        sequence=record.sequence,
        event_type=PaperTrackingEventType(record.event_type),
        idempotency_key=record.idempotency_key,
        occurred_at=record.occurred_at,
        available_at=record.available_at,
        recorded_at=record.recorded_at,
        actor_id=record.actor_id,
        opportunity_id=record.opportunity_id,
        opportunity_version_id=record.opportunity_version_id,
        source_execution_hash=record.source_execution_hash,
        source_position_hash=record.source_position_hash,
        source_artifact_id=record.source_artifact_id,
        source_artifact_hash=record.source_artifact_hash,
        exit_id=record.exit_id,
        outcome_id=record.outcome_id,
        payload=payload.get("payload", {}),
    )
