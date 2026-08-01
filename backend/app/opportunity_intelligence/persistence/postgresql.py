"""PostgreSQL adapters for frozen immutable repository contracts."""

from collections.abc import Callable, Mapping
from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import UnionType
from typing import Any, Generic, TypeVar, Union, get_args, get_origin, get_type_hints

from sqlalchemy import Select, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    DashboardPage,
    DeliveryAttempt,
    DetectionAttempt,
    EvidencePackage,
    ExplanationArtifact,
    FeatureSnapshot,
    LifecycleEvent,
    MarketContext,
    MarketScope,
    MarketSnapshot,
    Notification,
    Opportunity,
    OpportunityCandidate,
    OpportunityDetail,
    OpportunityLifecycle,
    OpportunityPlan,
    QualificationRecord,
    RankingSnapshot,
    RuntimeHealthRecord,
    ScoreResult,
)
from app.opportunity_intelligence.repositories import (
    ContractViolationError,
    DuplicateEntityError,
    EntityAsOfQuery,
    EntityId,
    EntityNotFoundError,
    HistoryQuery,
    RepositoryListQuery,
    RepositoryPage,
    ScopedRepositoryQuery,
    StorageUnavailableError,
    ValidationError,
    VersionConflictError,
)
from app.persistence.models import ImmutableAggregateRecord


T = TypeVar("T", bound=CanonicalModel)
Identity = Callable[[T], str]
Scope = Callable[[T], MarketScope | None]
Availability = Callable[[T], datetime]


class PostgreSQLImmutableRepository(Generic[T]):
    """Append-only JSONB repository preserving canonical domain serialization."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        entity_type: type[T],
        identity: Identity[T],
        logical_identity: Identity[T] | None = None,
        scope: Scope[T] | None = None,
        availability: Availability[T] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._entity_type = entity_type
        self._type_name = f"{entity_type.__module__}.{entity_type.__qualname__}"
        self._identity = identity
        self._logical_identity = logical_identity or identity
        self._scope = scope or (lambda item: None)
        self._availability = availability or _audit_availability

    async def save(self, entity: T) -> T:
        return (await self.save_batch((entity,)))[0]

    async def save_batch(self, entities: tuple[T, ...]) -> tuple[T, ...]:
        self._validate_batch(entities)
        try:
            async with self._sessions.begin() as session:
                await self._save_batch(session, entities)
        except (DuplicateEntityError, ContractViolationError):
            raise
        except SQLAlchemyError as error:
            raise StorageUnavailableError("PostgreSQL immutable write failed.") from error
        return entities

    async def _save_batch(
        self,
        session: AsyncSession,
        entities: tuple[T, ...],
    ) -> None:
        identities = tuple(sorted(self._identity(item) for item in entities))
        for identity in identities:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"{self._type_name}:{identity}"},
            )
        existing_rows = (
            await session.scalars(
                select(ImmutableAggregateRecord).where(
                    ImmutableAggregateRecord.entity_type == self._type_name,
                    ImmutableAggregateRecord.entity_id.in_(identities),
                )
            )
        ).all()
        existing = {row.entity_id: row for row in existing_rows}
        for entity in entities:
            identity = self._identity(entity)
            current = existing.get(identity)
            digest = entity.canonical_sha256()
            if current is not None:
                if current.canonical_hash != digest:
                    raise DuplicateEntityError(
                        f"Immutable identity {identity!r} already has different content."
                    )
                continue
            scope = self._scope(entity)
            session.add(
                ImmutableAggregateRecord(
                    entity_type=self._type_name,
                    entity_id=identity,
                    logical_id=self._logical_identity(entity),
                    scope_instrument=scope.instrument if scope is not None else None,
                    scope_timeframe=scope.timeframe if scope is not None else None,
                    available_at=self._availability(entity),
                    canonical_payload=entity.to_dict(),
                    canonical_hash=digest,
                    revision=1,
                )
            )

    async def get_by_id(self, entity_id: EntityId) -> T:
        self._require(entity_id, EntityId, "get_by_id")
        statement = self._base_select().where(
            ImmutableAggregateRecord.entity_id == entity_id.value
        )
        row = await self._one(statement, entity_id.value)
        return self._decode(row)

    async def exists(self, query: EntityAsOfQuery) -> bool:
        self._require(query, EntityAsOfQuery, "exists")
        statement = self._base_select().where(
            ImmutableAggregateRecord.entity_id == query.entity_id.value,
            ImmutableAggregateRecord.available_at <= query.as_of,
        )
        try:
            async with self._sessions() as session:
                return (await session.scalar(statement)) is not None
        except SQLAlchemyError as error:
            raise StorageUnavailableError("PostgreSQL existence query failed.") from error

    async def list(self, query: RepositoryListQuery) -> RepositoryPage[T]:
        self._require(query, RepositoryListQuery, "list")
        statement = self._base_select().where(
            ImmutableAggregateRecord.available_at <= query.as_of
        )
        if query.scope is not None:
            statement = statement.where(*_scope_predicates(query.scope))
        return await self._page(statement, query.as_of, query.limit, query.cursor)

    async def get_latest(self, query: ScopedRepositoryQuery) -> T:
        page = await self.get_by_scope(query)
        if not page.items:
            raise EntityNotFoundError("No entity exists in the requested scope.")
        return page.items[0]

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[T]:
        self._require(query, ScopedRepositoryQuery, "get_by_scope")
        statement = self._base_select().where(
            *_scope_predicates(query.scope),
            ImmutableAggregateRecord.available_at <= query.as_of,
        )
        return await self._page(statement, query.as_of, query.limit, query.cursor)

    async def history(self, query: HistoryQuery) -> RepositoryPage[T]:
        self._require(query, HistoryQuery, "history")
        statement = self._base_select().where(
            ImmutableAggregateRecord.logical_id == query.entity_id.value,
            ImmutableAggregateRecord.available_at <= query.as_of,
        )
        page = await self._page(statement, query.as_of, query.limit, query.cursor)
        if not page.items:
            raise EntityNotFoundError(query.entity_id.value)
        return page

    async def latest_for_logical_id(self, query: EntityAsOfQuery) -> T:
        self._require(query, EntityAsOfQuery, "latest_for_logical_id")
        statement = self._ordered(
            self._base_select().where(
                ImmutableAggregateRecord.logical_id == query.entity_id.value,
                ImmutableAggregateRecord.available_at <= query.as_of,
            )
        ).limit(1)
        return self._decode(await self._one(statement, query.entity_id.value))

    async def find_by_payload_field(self, field: str, value: str) -> T:
        return await self.find_by_payload_path((field,), value)

    async def find_by_payload_path(self, path: tuple[str, ...], value: str) -> T:
        expression = ImmutableAggregateRecord.canonical_payload
        for field in path:
            expression = expression[field]
        statement = self._base_select().where(
            expression.astext == value
        )
        try:
            async with self._sessions() as session:
                rows = (await session.scalars(self._ordered(statement).limit(2))).all()
        except SQLAlchemyError as error:
            raise StorageUnavailableError("PostgreSQL payload query failed.") from error
        if not rows:
            raise EntityNotFoundError(value)
        if len(rows) > 1:
            raise VersionConflictError("Query does not identify a unique entity.")
        return self._decode(rows[0])

    def _validate_batch(self, entities: tuple[T, ...]) -> None:
        if not isinstance(entities, tuple) or not entities:
            raise ValidationError("Save batch requires a non-empty immutable tuple.")
        identities: set[str] = set()
        for entity in entities:
            if not isinstance(entity, self._entity_type):
                raise ContractViolationError(
                    f"Repository requires {self._entity_type.__name__} entities."
                )
            identity = self._identity(entity)
            if identity in identities:
                raise DuplicateEntityError(
                    f"Batch contains duplicate identity {identity!r}."
                )
            identities.add(identity)

    def _base_select(self) -> Select[tuple[ImmutableAggregateRecord]]:
        return select(ImmutableAggregateRecord).where(
            ImmutableAggregateRecord.entity_type == self._type_name
        )

    def _ordered(
        self,
        statement: Select[tuple[ImmutableAggregateRecord]],
    ) -> Select[tuple[ImmutableAggregateRecord]]:
        return statement.order_by(
            ImmutableAggregateRecord.available_at.desc(),
            ImmutableAggregateRecord.entity_id.desc(),
        )

    async def _one(
        self,
        statement: Select[tuple[ImmutableAggregateRecord]],
        identity: str,
    ) -> ImmutableAggregateRecord:
        try:
            async with self._sessions() as session:
                row = await session.scalar(statement)
        except SQLAlchemyError as error:
            raise StorageUnavailableError("PostgreSQL immutable read failed.") from error
        if row is None:
            raise EntityNotFoundError(identity)
        return row

    async def _page(
        self,
        statement: Select[tuple[ImmutableAggregateRecord]],
        as_of: datetime,
        limit: int,
        cursor: str | None,
    ) -> RepositoryPage[T]:
        offset = _cursor_offset(cursor)
        try:
            async with self._sessions() as session:
                rows = (
                    await session.scalars(
                        self._ordered(statement).offset(offset).limit(limit + 1)
                    )
                ).all()
        except SQLAlchemyError as error:
            raise StorageUnavailableError("PostgreSQL page query failed.") from error
        selected = rows[:limit]
        return RepositoryPage(
            items=tuple(self._decode(item) for item in selected),
            as_of=as_of,
            next_cursor=str(offset + limit) if len(rows) > limit else None,
        )

    def _decode(self, row: ImmutableAggregateRecord) -> T:
        entity = decode_canonical(self._entity_type, row.canonical_payload)
        if entity.canonical_sha256() != row.canonical_hash:
            raise ContractViolationError("Stored canonical aggregate hash mismatch.")
        return entity

    @staticmethod
    def _require(value: object, expected: type[object], operation: str) -> None:
        if not isinstance(value, expected):
            raise ValidationError(
                f"{operation} requires {expected.__name__}; received {type(value).__name__}."
            )


class MarketSnapshotPostgreSQLRepository(PostgreSQLImmutableRepository[MarketSnapshot]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, MarketSnapshot, lambda item: item.snapshot_id, scope=lambda item: item.scope)


class FeatureSnapshotPostgreSQLRepository(PostgreSQLImmutableRepository[FeatureSnapshot]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, FeatureSnapshot, lambda item: item.snapshot_id, scope=lambda item: item.scope)


class MarketContextPostgreSQLRepository(PostgreSQLImmutableRepository[MarketContext]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, MarketContext, lambda item: item.context_id, scope=lambda item: item.scope)


class EvidencePostgreSQLRepository(PostgreSQLImmutableRepository[EvidencePackage]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, EvidencePackage, lambda item: item.package_id, lambda item: item.candidate_id)

    async def get_by_candidate_id(self, entity_id: EntityId) -> EvidencePackage:
        self._require(entity_id, EntityId, "get_by_candidate_id")
        return await self.find_by_payload_field("candidate_id", entity_id.value)

    async def get_by_assessment_id(self, entity_id: EntityId) -> EvidencePackage:
        self._require(entity_id, EntityId, "get_by_assessment_id")
        return await self.find_by_payload_field("assessment_id", entity_id.value)


class OpportunityPostgreSQLRepository(PostgreSQLImmutableRepository[Opportunity]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, Opportunity, lambda item: item.opportunity_version_id, lambda item: item.opportunity_id, lambda item: item.scope)

    async def get_current(self, query: EntityAsOfQuery) -> Opportunity:
        return await self.latest_for_logical_id(query)


class QualificationPostgreSQLRepository(PostgreSQLImmutableRepository[QualificationRecord]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, QualificationRecord, lambda item: item.qualification_id, lambda item: item.assessment_reference.artifact_id)

    async def get_latest_for_assessment(self, query: EntityAsOfQuery) -> QualificationRecord:
        return await self.latest_for_logical_id(query)


class ScoringPostgreSQLRepository(PostgreSQLImmutableRepository[ScoreResult]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, ScoreResult, lambda item: item.score_id, lambda item: item.opportunity_id)

    async def get_latest_for_opportunity(self, query: EntityAsOfQuery) -> ScoreResult:
        return await self.latest_for_logical_id(query)


class RankingPostgreSQLRepository(PostgreSQLImmutableRepository[RankingSnapshot]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, RankingSnapshot, lambda item: item.snapshot_id, scope=lambda item: item.scope)


class OpportunityPlanPostgreSQLRepository(PostgreSQLImmutableRepository[OpportunityPlan]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, OpportunityPlan, lambda item: item.plan_id, lambda item: item.opportunity_id)

    async def get_latest_for_opportunity(self, query: EntityAsOfQuery) -> OpportunityPlan:
        return await self.latest_for_logical_id(query)


class DashboardProjectionPostgreSQLRepository(PostgreSQLImmutableRepository[DashboardPage]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, DashboardPage, lambda item: item.ranking_snapshot_reference.artifact_id, scope=lambda item: item.scope)

    async def get_by_ranking_snapshot(self, entity_id: EntityId) -> DashboardPage:
        return await self.get_by_id(entity_id)


class OpportunityDetailPostgreSQLRepository(PostgreSQLImmutableRepository[OpportunityDetail]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, OpportunityDetail, lambda item: item.detail_id, lambda item: item.opportunity.opportunity_id)

    async def get_by_opportunity_version(self, entity_id: EntityId) -> OpportunityDetail:
        self._require(entity_id, EntityId, "get_by_opportunity_version")
        return await self.find_by_payload_path(
            ("opportunity", "opportunity_version_id"), entity_id.value
        )

    async def get_current(self, query: EntityAsOfQuery) -> OpportunityDetail:
        return await self.latest_for_logical_id(query)


class ExplanationPostgreSQLRepository(PostgreSQLImmutableRepository[ExplanationArtifact]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, ExplanationArtifact, lambda item: item.explanation_id, lambda item: item.opportunity_version_id)

    async def get_by_opportunity_version(self, entity_id: EntityId) -> ExplanationArtifact:
        self._require(entity_id, EntityId, "get_by_opportunity_version")
        return await self.find_by_payload_field("opportunity_version_id", entity_id.value)


class RuntimeGovernancePostgreSQLRepository(PostgreSQLImmutableRepository[RuntimeHealthRecord]):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(sessions, RuntimeHealthRecord, lambda item: item.cycle_id, scope=lambda item: item.scope)


class DetectionPostgreSQLRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._attempts = PostgreSQLImmutableRepository(
            sessions,
            DetectionAttempt,
            lambda item: item.attempt_id,
            scope=lambda item: item.scope,
        )
        self._candidates = PostgreSQLImmutableRepository(
            sessions,
            OpportunityCandidate,
            lambda item: item.candidate_id,
            scope=lambda item: item.scope,
        )

    async def save_attempt(self, attempt: DetectionAttempt) -> DetectionAttempt:
        return await self._attempts.save(attempt)

    async def save_attempt_batch(
        self, attempts: tuple[DetectionAttempt, ...]
    ) -> tuple[DetectionAttempt, ...]:
        return await self._attempts.save_batch(attempts)

    async def save_candidate(
        self, candidate: OpportunityCandidate
    ) -> OpportunityCandidate:
        return (await self.save_candidate_batch((candidate,)))[0]

    async def save_candidate_batch(
        self, candidates: tuple[OpportunityCandidate, ...]
    ) -> tuple[OpportunityCandidate, ...]:
        self._candidates._validate_batch(candidates)
        for candidate in candidates:
            attempt = await self._attempts.find_by_payload_field(
                "candidate_id", candidate.candidate_id
            )
            if attempt.candidate_id != candidate.candidate_id:
                raise ContractViolationError(
                    "Candidate requires its matching detected attempt."
                )
        return await self._candidates.save_batch(candidates)

    async def get_attempt_by_id(self, entity_id: EntityId) -> DetectionAttempt:
        return await self._attempts.get_by_id(entity_id)

    async def get_candidate_by_id(
        self, entity_id: EntityId
    ) -> OpportunityCandidate:
        return await self._candidates.get_by_id(entity_id)

    async def get_latest_candidate(
        self, query: ScopedRepositoryQuery
    ) -> OpportunityCandidate:
        return await self._candidates.get_latest(query)

    async def list_attempts(
        self, query: RepositoryListQuery
    ) -> RepositoryPage[DetectionAttempt]:
        return await self._attempts.list(query)

    async def list_candidates(
        self, query: RepositoryListQuery
    ) -> RepositoryPage[OpportunityCandidate]:
        return await self._candidates.list(query)

    async def attempt_exists(self, query: EntityAsOfQuery) -> bool:
        return await self._attempts.exists(query)

    async def candidate_exists(self, query: EntityAsOfQuery) -> bool:
        return await self._candidates.exists(query)


class LifecyclePostgreSQLRepository(
    PostgreSQLImmutableRepository[OpportunityLifecycle]
):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(
            sessions,
            OpportunityLifecycle,
            lambda item: item.current_event_id,
            lambda item: item.opportunity_id,
            lambda item: item.scope,
        )
        self._events = PostgreSQLImmutableRepository(
            sessions,
            LifecycleEvent,
            lambda item: item.event_id,
            lambda item: item.opportunity_id,
        )

    async def save_event(self, event: LifecycleEvent) -> LifecycleEvent:
        return (await self.save_event_batch((event,)))[0]

    async def save_event_batch(
        self, events: tuple[LifecycleEvent, ...]
    ) -> tuple[LifecycleEvent, ...]:
        self._events._validate_batch(events)
        ordered = tuple(sorted(events, key=lambda item: item.sequence))
        if len({item.opportunity_id for item in ordered}) != 1:
            raise VersionConflictError("Lifecycle batch must target one opportunity.")
        for prior, current in zip(ordered, ordered[1:]):
            if (
                current.sequence != prior.sequence + 1
                or current.predecessor_event_id != prior.event_id
            ):
                raise VersionConflictError("Lifecycle event batch is not contiguous.")
        opportunity_id = ordered[0].opportunity_id
        try:
            async with self._events._sessions.begin() as session:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": f"lifecycle:{opportunity_id}"},
                )
                latest = await session.scalar(
                    self._events._ordered(
                        self._events._base_select().where(
                            ImmutableAggregateRecord.logical_id == opportunity_id
                        )
                    ).limit(1)
                )
                if latest is not None:
                    latest_event = self._events._decode(latest)
                    first = ordered[0]
                    if (
                        first.sequence != latest_event.sequence + 1
                        or first.predecessor_event_id != latest_event.event_id
                    ):
                        raise VersionConflictError(
                            "Lifecycle append conflicts with the persisted tail."
                        )
                await self._events._save_batch(session, events)
        except VersionConflictError:
            raise
        except SQLAlchemyError as error:
            raise StorageUnavailableError("Lifecycle append failed.") from error
        return events

    async def get_event_by_id(self, event_id: EntityId) -> LifecycleEvent:
        return await self._events.get_by_id(event_id)

    async def get_current(self, query: EntityAsOfQuery) -> OpportunityLifecycle:
        return await self.latest_for_logical_id(query)

    async def history(self, query: HistoryQuery) -> RepositoryPage[LifecycleEvent]:
        page = await self._events.history(query)
        return RepositoryPage(
            items=tuple(sorted(page.items, key=lambda item: item.sequence)),
            as_of=page.as_of,
            next_cursor=page.next_cursor,
        )


@dataclass(frozen=True, slots=True)
class _DeliveryAttemptEnvelope(CanonicalModel):
    notification_id: str
    attempt: DeliveryAttempt


class NotificationPostgreSQLRepository(
    PostgreSQLImmutableRepository[Notification]
):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(
            sessions,
            Notification,
            lambda item: item.notification_id,
            scope=lambda item: item.scope,
        )
        self._deliveries = PostgreSQLImmutableRepository(
            sessions,
            _DeliveryAttemptEnvelope,
            lambda item: item.attempt.attempt_id,
            lambda item: item.notification_id,
            availability=lambda item: item.attempt.attempted_at,
        )

    async def save_delivery_attempt(
        self,
        notification_id: EntityId,
        attempt: DeliveryAttempt,
    ) -> DeliveryAttempt:
        self._require(notification_id, EntityId, "save_delivery_attempt")
        if not isinstance(attempt, DeliveryAttempt):
            raise ContractViolationError(
                "Delivery repository requires DeliveryAttempt."
            )
        envelope = _DeliveryAttemptEnvelope(notification_id.value, attempt)
        try:
            async with self._sessions.begin() as session:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": f"delivery:{notification_id.value}"},
                )
                notification = await session.scalar(
                    self._base_select().where(
                        ImmutableAggregateRecord.entity_id == notification_id.value
                    )
                )
                if notification is None:
                    raise EntityNotFoundError(notification_id.value)
                existing = await session.scalar(
                    self._deliveries._base_select().where(
                        ImmutableAggregateRecord.entity_id == attempt.attempt_id
                    )
                )
                if existing is not None:
                    stored = self._deliveries._decode(existing).attempt
                    if stored.canonical_sha256() != attempt.canonical_sha256():
                        raise DuplicateEntityError(attempt.attempt_id)
                    return stored
                latest = await session.scalar(
                    self._deliveries._ordered(
                        self._deliveries._base_select().where(
                            ImmutableAggregateRecord.logical_id
                            == notification_id.value
                        )
                    ).limit(1)
                )
                expected_sequence = (
                    1
                    if latest is None
                    else self._deliveries._decode(latest).attempt.sequence + 1
                )
                if attempt.sequence != expected_sequence:
                    raise VersionConflictError("Delivery sequence is not contiguous.")
                await self._deliveries._save_batch(session, (envelope,))
        except (
            ContractViolationError,
            DuplicateEntityError,
            EntityNotFoundError,
            VersionConflictError,
        ):
            raise
        except SQLAlchemyError as error:
            raise StorageUnavailableError("Delivery append failed.") from error
        return attempt

    async def delivery_history(
        self, query: HistoryQuery
    ) -> RepositoryPage[DeliveryAttempt]:
        page = await self._deliveries.history(query)
        return RepositoryPage(
            items=tuple(item.attempt for item in reversed(page.items)),
            as_of=page.as_of,
            next_cursor=page.next_cursor,
        )

def decode_canonical(model_type: type[T], payload: Mapping[str, Any]) -> T:
    """Reconstruct one frozen dataclass from its canonical JSON representation."""
    return _decode_value(model_type, payload)


def _decode_value(expected: Any, value: Any) -> Any:
    origin = get_origin(expected)
    arguments = get_args(expected)
    if origin in {Union, UnionType}:
        if value is None and type(None) in arguments:
            return None
        failures: list[Exception] = []
        for member in arguments:
            if member is type(None):
                continue
            try:
                return _decode_value(member, value)
            except (TypeError, ValueError) as error:
                failures.append(error)
        raise TypeError(f"Canonical union value cannot be decoded: {failures!r}")
    if origin is tuple:
        member = arguments[0] if arguments else Any
        return tuple(_decode_value(member, item) for item in value)
    if origin in {dict, Mapping}:
        key_type, value_type = arguments or (str, Any)
        return {
            _decode_value(key_type, key): _decode_value(value_type, item)
            for key, item in value.items()
        }
    if expected is Any:
        return value
    if expected is datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if expected is Decimal:
        return Decimal(value)
    if isinstance(expected, type) and issubclass(expected, Enum):
        return expected(value)
    if isinstance(expected, type) and is_dataclass(expected):
        if not isinstance(value, Mapping):
            raise TypeError(f"{expected.__name__} requires an object payload.")
        hints = get_type_hints(expected)
        kwargs: dict[str, Any] = {}
        for field in fields(expected):
            field_type = hints[field.name]
            if field.name in value:
                kwargs[field.name] = _decode_value(field_type, value[field.name])
            elif field.default is not MISSING or field.default_factory is not MISSING:
                continue
            elif type(None) in get_args(field_type):
                kwargs[field.name] = None
            else:
                raise TypeError(f"Canonical payload is missing {field.name!r}.")
        return expected(**kwargs)
    if expected in {str, int, bool}:
        if not isinstance(value, expected):
            raise TypeError(f"Expected {expected.__name__} canonical value.")
        return value
    return value


def _audit_availability(entity: T) -> datetime:
    audit = getattr(entity, "audit", None)
    available_at = getattr(audit, "available_at", None)
    if not isinstance(available_at, datetime):
        raise ContractViolationError("Persisted aggregate requires audit availability.")
    return available_at


def _scope_predicates(scope: MarketScope) -> tuple[Any, Any]:
    return (
        ImmutableAggregateRecord.scope_instrument == scope.instrument,
        ImmutableAggregateRecord.scope_timeframe == scope.timeframe,
    )


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        offset = int(cursor)
    except (TypeError, ValueError) as error:
        raise ValidationError("Repository cursor is invalid.") from error
    if offset < 0 or str(offset) != cursor:
        raise ValidationError("Repository cursor is invalid.")
    return offset
