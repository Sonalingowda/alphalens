"""Dedicated append-only persistence for the isolated paper namespace."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.paper_execution.domain import PaperExecution, PaperExit, PaperOutcome, PaperPosition
from app.paper_execution.successor import PaperSuccessorPlan
from app.persistence.models import (
    PaperExecutionRecord,
    PaperExitRecord,
    PaperOutcomeRecord,
    PaperPositionRecord,
    PaperSuccessorPlanRecord,
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
