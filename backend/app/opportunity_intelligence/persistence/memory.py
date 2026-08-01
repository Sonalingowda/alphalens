"""Deterministic in-process immutable repository implementations.

These adapters are storage implementations, not application services.  They are
useful for tests and single-process deployments and preserve every repository
contract without leaking storage mechanics above this package.
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Generic, TypeVar

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
    ValidationError,
    VersionConflictError,
)


T = TypeVar("T", bound=CanonicalModel)


class InMemoryImmutableRepository(Generic[T]):
    """Atomic append-only store with deterministic point-in-time reads."""

    def __init__(
        self,
        entity_type: type[T],
        identity: Callable[[T], str],
        logical_identity: Callable[[T], str] | None = None,
        scope: Callable[[T], MarketScope | None] | None = None,
    ) -> None:
        self._entity_type = entity_type
        self._identity = identity
        self._logical_identity = logical_identity or identity
        self._scope = scope or (lambda entity: None)
        self._records: dict[str, T] = {}
        self._lock = asyncio.Lock()

    async def save(self, entity: T) -> T:
        saved = await self.save_batch((entity,))
        return saved[0]

    async def save_batch(self, entities: tuple[T, ...]) -> tuple[T, ...]:
        self._validate_batch(entities)
        async with self._lock:
            pending: dict[str, T] = {}
            for entity in entities:
                identity = self._identity(entity)
                existing = pending.get(identity) or self._records.get(identity)
                if existing is not None and existing.canonical_sha256() != entity.canonical_sha256():
                    raise DuplicateEntityError(
                        f"Immutable identity {identity!r} already has different content."
                    )
                pending[identity] = entity
            self._records.update(pending)
        return entities

    async def get_by_id(self, entity_id: EntityId) -> T:
        self._require(entity_id, EntityId, "get_by_id")
        try:
            return self._records[entity_id.value]
        except KeyError as error:
            raise EntityNotFoundError(entity_id.value) from error

    async def exists(self, query: EntityAsOfQuery) -> bool:
        self._require(query, EntityAsOfQuery, "exists")
        entity = self._records.get(query.entity_id.value)
        return entity is not None and _available_at(entity) <= query.as_of

    async def list(self, query: RepositoryListQuery) -> RepositoryPage[T]:
        self._require(query, RepositoryListQuery, "list")
        candidates = tuple(
            entity
            for entity in self._records.values()
            if _available_at(entity) <= query.as_of
            and (query.scope is None or self._scope(entity) == query.scope)
        )
        return self._page(candidates, query.as_of, query.limit, query.cursor)

    async def get_latest(self, query: ScopedRepositoryQuery) -> T:
        page = await self.get_by_scope(query)
        if not page.items:
            raise EntityNotFoundError("No entity exists in the requested scope.")
        return page.items[0]

    async def get_by_scope(self, query: ScopedRepositoryQuery) -> RepositoryPage[T]:
        self._require(query, ScopedRepositoryQuery, "get_by_scope")
        candidates = tuple(
            entity
            for entity in self._records.values()
            if _available_at(entity) <= query.as_of
            and self._scope(entity) == query.scope
        )
        return self._page(candidates, query.as_of, query.limit, query.cursor)

    async def history(self, query: HistoryQuery) -> RepositoryPage[T]:
        self._require(query, HistoryQuery, "history")
        candidates = tuple(
            entity
            for entity in self._records.values()
            if self._logical_identity(entity) == query.entity_id.value
            and _available_at(entity) <= query.as_of
        )
        if not candidates:
            raise EntityNotFoundError(query.entity_id.value)
        return self._page(candidates, query.as_of, query.limit, query.cursor)

    async def latest_for_logical_id(self, query: EntityAsOfQuery) -> T:
        self._require(query, EntityAsOfQuery, "latest_for_logical_id")
        candidates = tuple(
            entity
            for entity in self._records.values()
            if self._logical_identity(entity) == query.entity_id.value
            and _available_at(entity) <= query.as_of
        )
        if not candidates:
            raise EntityNotFoundError(query.entity_id.value)
        return self._ordered(candidates)[0]

    def find_one(self, predicate: Callable[[T], bool]) -> T:
        matches = self._ordered(tuple(filter(predicate, self._records.values())))
        if not matches:
            raise EntityNotFoundError("No matching immutable entity exists.")
        if len(matches) > 1:
            raise VersionConflictError("Query does not identify a unique entity.")
        return matches[0]

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

    def _page(
        self,
        candidates: tuple[T, ...],
        as_of: datetime,
        limit: int,
        cursor: str | None,
    ) -> RepositoryPage[T]:
        ordered = self._ordered(candidates)
        offset = _cursor_offset(cursor)
        items = ordered[offset : offset + limit]
        next_offset = offset + len(items)
        next_cursor = str(next_offset) if next_offset < len(ordered) else None
        return RepositoryPage(items=items, as_of=as_of, next_cursor=next_cursor)

    def _ordered(self, entities: tuple[T, ...]) -> tuple[T, ...]:
        return tuple(
            sorted(
                entities,
                key=lambda entity: (_available_at(entity), self._identity(entity)),
                reverse=True,
            )
        )

    @staticmethod
    def _require(value: object, expected: type[object], operation: str) -> None:
        if not isinstance(value, expected):
            raise ValidationError(
                f"{operation} requires {expected.__name__}; received {type(value).__name__}."
            )


class MarketSnapshotMemoryRepository(InMemoryImmutableRepository[MarketSnapshot]):
    def __init__(self) -> None:
        super().__init__(MarketSnapshot, lambda item: item.snapshot_id, scope=lambda item: item.scope)


class FeatureSnapshotMemoryRepository(InMemoryImmutableRepository[FeatureSnapshot]):
    def __init__(self) -> None:
        super().__init__(FeatureSnapshot, lambda item: item.snapshot_id, scope=lambda item: item.scope)


class MarketContextMemoryRepository(InMemoryImmutableRepository[MarketContext]):
    def __init__(self) -> None:
        super().__init__(MarketContext, lambda item: item.context_id, scope=lambda item: item.scope)


class EvidenceMemoryRepository(InMemoryImmutableRepository[EvidencePackage]):
    def __init__(self) -> None:
        super().__init__(EvidencePackage, lambda item: item.package_id, lambda item: item.candidate_id)

    async def get_by_candidate_id(self, candidate_id: EntityId) -> EvidencePackage:
        self._require(candidate_id, EntityId, "get_by_candidate_id")
        return self.find_one(lambda item: item.candidate_id == candidate_id.value)

    async def get_by_assessment_id(self, assessment_id: EntityId) -> EvidencePackage:
        self._require(assessment_id, EntityId, "get_by_assessment_id")
        return self.find_one(lambda item: item.assessment_id == assessment_id.value)


class OpportunityMemoryRepository(InMemoryImmutableRepository[Opportunity]):
    def __init__(self) -> None:
        super().__init__(
            Opportunity,
            lambda item: item.opportunity_version_id,
            lambda item: item.opportunity_id,
            lambda item: item.scope,
        )

    async def get_current(self, query: EntityAsOfQuery) -> Opportunity:
        return await self.latest_for_logical_id(query)


class QualificationMemoryRepository(InMemoryImmutableRepository[QualificationRecord]):
    def __init__(self) -> None:
        super().__init__(
            QualificationRecord,
            lambda item: item.qualification_id,
            lambda item: item.assessment_reference.artifact_id,
        )

    async def get_latest_for_assessment(self, query: EntityAsOfQuery) -> QualificationRecord:
        return await self.latest_for_logical_id(query)


class ScoringMemoryRepository(InMemoryImmutableRepository[ScoreResult]):
    def __init__(self) -> None:
        super().__init__(ScoreResult, lambda item: item.score_id, lambda item: item.opportunity_id)

    async def get_latest_for_opportunity(self, query: EntityAsOfQuery) -> ScoreResult:
        return await self.latest_for_logical_id(query)


class RankingMemoryRepository(InMemoryImmutableRepository[RankingSnapshot]):
    def __init__(self) -> None:
        super().__init__(RankingSnapshot, lambda item: item.snapshot_id, scope=lambda item: item.scope)


class OpportunityPlanMemoryRepository(InMemoryImmutableRepository[OpportunityPlan]):
    def __init__(self) -> None:
        super().__init__(OpportunityPlan, lambda item: item.plan_id, lambda item: item.opportunity_id)

    async def get_latest_for_opportunity(self, query: EntityAsOfQuery) -> OpportunityPlan:
        return await self.latest_for_logical_id(query)


class DashboardProjectionMemoryRepository(InMemoryImmutableRepository[DashboardPage]):
    def __init__(self) -> None:
        super().__init__(
            DashboardPage,
            lambda item: item.ranking_snapshot_reference.artifact_id,
            scope=lambda item: item.scope,
        )

    async def get_by_ranking_snapshot(self, entity_id: EntityId) -> DashboardPage:
        return await self.get_by_id(entity_id)


class OpportunityDetailMemoryRepository(InMemoryImmutableRepository[OpportunityDetail]):
    def __init__(self) -> None:
        super().__init__(
            OpportunityDetail,
            lambda item: item.detail_id,
            lambda item: item.opportunity.opportunity_id,
        )

    async def get_by_opportunity_version(self, entity_id: EntityId) -> OpportunityDetail:
        self._require(entity_id, EntityId, "get_by_opportunity_version")
        return self.find_one(
            lambda item: item.opportunity.opportunity_version_id == entity_id.value
        )

    async def get_current(self, query: EntityAsOfQuery) -> OpportunityDetail:
        return await self.latest_for_logical_id(query)


class ExplanationMemoryRepository(InMemoryImmutableRepository[ExplanationArtifact]):
    def __init__(self) -> None:
        super().__init__(
            ExplanationArtifact,
            lambda item: item.explanation_id,
            lambda item: item.opportunity_version_id,
        )

    async def get_by_opportunity_version(self, entity_id: EntityId) -> ExplanationArtifact:
        self._require(entity_id, EntityId, "get_by_opportunity_version")
        return self.find_one(lambda item: item.opportunity_version_id == entity_id.value)


class RuntimeGovernanceMemoryRepository(InMemoryImmutableRepository[RuntimeHealthRecord]):
    def __init__(self) -> None:
        super().__init__(
            RuntimeHealthRecord,
            lambda item: item.cycle_id,
            scope=lambda item: item.scope,
        )


class DetectionMemoryRepository:
    def __init__(self) -> None:
        self._attempts = InMemoryImmutableRepository(
            DetectionAttempt,
            lambda item: item.attempt_id,
            scope=lambda item: item.scope,
        )
        self._candidates = InMemoryImmutableRepository(
            OpportunityCandidate,
            lambda item: item.candidate_id,
            scope=lambda item: item.scope,
        )

    async def save_attempt(self, attempt: DetectionAttempt) -> DetectionAttempt:
        return await self._attempts.save(attempt)

    async def save_attempt_batch(self, attempts: tuple[DetectionAttempt, ...]) -> tuple[DetectionAttempt, ...]:
        return await self._attempts.save_batch(attempts)

    async def save_candidate(self, candidate: OpportunityCandidate) -> OpportunityCandidate:
        return (await self.save_candidate_batch((candidate,)))[0]

    async def save_candidate_batch(self, candidates: tuple[OpportunityCandidate, ...]) -> tuple[OpportunityCandidate, ...]:
        self._candidates._validate_batch(candidates)
        detected_ids = {
            attempt.candidate_id
            for attempt in self._attempts._records.values()
            if attempt.candidate_id is not None
        }
        if any(candidate.candidate_id not in detected_ids for candidate in candidates):
            raise ContractViolationError("Candidate requires its matching detected attempt.")
        return await self._candidates.save_batch(candidates)

    async def get_attempt_by_id(self, entity_id: EntityId) -> DetectionAttempt:
        return await self._attempts.get_by_id(entity_id)

    async def get_candidate_by_id(self, entity_id: EntityId) -> OpportunityCandidate:
        return await self._candidates.get_by_id(entity_id)

    async def get_latest_candidate(self, query: ScopedRepositoryQuery) -> OpportunityCandidate:
        return await self._candidates.get_latest(query)

    async def list_attempts(self, query: RepositoryListQuery) -> RepositoryPage[DetectionAttempt]:
        return await self._attempts.list(query)

    async def list_candidates(self, query: RepositoryListQuery) -> RepositoryPage[OpportunityCandidate]:
        return await self._candidates.list(query)

    async def attempt_exists(self, query: EntityAsOfQuery) -> bool:
        return await self._attempts.exists(query)

    async def candidate_exists(self, query: EntityAsOfQuery) -> bool:
        return await self._candidates.exists(query)


class LifecycleMemoryRepository(InMemoryImmutableRepository[OpportunityLifecycle]):
    def __init__(self) -> None:
        super().__init__(
            OpportunityLifecycle,
            lambda item: item.current_event_id,
            lambda item: item.opportunity_id,
            lambda item: item.scope,
        )
        self._events = InMemoryImmutableRepository(
            LifecycleEvent,
            lambda item: item.event_id,
            lambda item: item.opportunity_id,
        )
        self._event_append_lock = asyncio.Lock()

    async def save_event(self, event: LifecycleEvent) -> LifecycleEvent:
        return (await self.save_event_batch((event,)))[0]

    async def save_event_batch(self, events: tuple[LifecycleEvent, ...]) -> tuple[LifecycleEvent, ...]:
        self._events._validate_batch(events)
        ordered = tuple(sorted(events, key=lambda item: item.sequence))
        if len({event.opportunity_id for event in ordered}) != 1:
            raise VersionConflictError("Lifecycle batch must target one opportunity.")
        for prior, current in zip(ordered, ordered[1:]):
            if current.sequence != prior.sequence + 1 or current.predecessor_event_id != prior.event_id:
                raise VersionConflictError("Lifecycle event batch is not contiguous.")
        async with self._event_append_lock:
            existing = tuple(
                event
                for event in self._events._records.values()
                if event.opportunity_id == ordered[0].opportunity_id
            )
            if existing:
                latest = max(existing, key=lambda item: item.sequence)
                first = ordered[0]
                if (
                    first.sequence != latest.sequence + 1
                    or first.predecessor_event_id != latest.event_id
                ):
                    raise VersionConflictError(
                        "Lifecycle append conflicts with the persisted tail."
                    )
            return await self._events.save_batch(events)

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


class NotificationMemoryRepository(InMemoryImmutableRepository[Notification]):
    def __init__(self) -> None:
        super().__init__(
            Notification,
            lambda item: item.notification_id,
            scope=lambda item: item.scope,
        )
        self._delivery: dict[str, tuple[DeliveryAttempt, ...]] = {}
        self._delivery_lock = asyncio.Lock()

    async def save_delivery_attempt(self, notification_id: EntityId, attempt: DeliveryAttempt) -> DeliveryAttempt:
        self._require(notification_id, EntityId, "save_delivery_attempt")
        if not isinstance(attempt, DeliveryAttempt):
            raise ContractViolationError("Delivery repository requires DeliveryAttempt.")
        await self.get_by_id(notification_id)
        async with self._delivery_lock:
            history = self._delivery.get(notification_id.value, ())
            if any(item.attempt_id == attempt.attempt_id for item in history):
                existing = next(item for item in history if item.attempt_id == attempt.attempt_id)
                if existing.canonical_sha256() != attempt.canonical_sha256():
                    raise DuplicateEntityError(attempt.attempt_id)
                return existing
            if attempt.sequence != len(history) + 1:
                raise VersionConflictError("Delivery sequence is not contiguous.")
            self._delivery[notification_id.value] = history + (attempt,)
        return attempt

    async def delivery_history(self, query: HistoryQuery) -> RepositoryPage[DeliveryAttempt]:
        self._require(query, HistoryQuery, "delivery_history")
        items = tuple(
            item
            for item in self._delivery.get(query.entity_id.value, ())
            if item.attempted_at <= query.as_of
        )
        if not items:
            raise EntityNotFoundError(query.entity_id.value)
        offset = _cursor_offset(query.cursor)
        selected = items[offset : offset + query.limit]
        next_offset = offset + len(selected)
        return RepositoryPage(
            items=selected,
            as_of=query.as_of,
            next_cursor=str(next_offset) if next_offset < len(items) else None,
        )


def _available_at(entity: CanonicalModel) -> datetime:
    audit = getattr(entity, "audit", None)
    available_at = getattr(audit, "available_at", None)
    if not isinstance(available_at, datetime):
        raise ContractViolationError("Persisted aggregate requires audit availability.")
    return available_at


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
