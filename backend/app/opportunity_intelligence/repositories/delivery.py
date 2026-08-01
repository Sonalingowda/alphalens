"""Repository ports for ranking, plans, lifecycle, and notifications."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    DeliveryAttempt,
    LifecycleEvent,
    Notification,
    OpportunityLifecycle,
    OpportunityPlan,
    RankingSnapshot,
)
from app.opportunity_intelligence.repositories.base import ImmutableRepository
from app.opportunity_intelligence.repositories.queries import (
    EntityAsOfQuery,
    EntityId,
    HistoryQuery,
    RepositoryPage,
    ScopedRepositoryQuery,
)


@runtime_checkable
class RankingRepository(ImmutableRepository[RankingSnapshot], Protocol):
    """Append-only access to complete immutable ranking snapshots."""

    async def get_latest(self, query: ScopedRepositoryQuery) -> RankingSnapshot:
        """Return latest snapshot at as-of or raise EntityNotFoundError."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[RankingSnapshot]:
        """Return ranking snapshots in stable newest-first contract order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[RankingSnapshot]:
        """Return immutable ranking history in stable order."""
        ...


@runtime_checkable
class OpportunityPlanRepository(
    ImmutableRepository[OpportunityPlan],
    Protocol,
):
    """Append-only access to complete informational opportunity plans."""

    async def get_latest_for_opportunity(
        self,
        query: EntityAsOfQuery,
    ) -> OpportunityPlan:
        """Return latest complete plan or raise EntityNotFoundError."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[OpportunityPlan]:
        """Return immutable plan history in stable order."""
        ...


@runtime_checkable
class LifecycleRepository(
    ImmutableRepository[OpportunityLifecycle],
    Protocol,
):
    """Append-only access to lifecycle aggregates and individual events."""

    async def save_event(self, event: LifecycleEvent) -> LifecycleEvent:
        """Append one valid event or raise VersionConflictError."""
        ...

    async def save_event_batch(
        self,
        events: tuple[LifecycleEvent, ...],
    ) -> tuple[LifecycleEvent, ...]:
        """Append a contiguous non-empty event batch without partial success."""
        ...

    async def get_event_by_id(self, event_id: EntityId) -> LifecycleEvent:
        """Return one event or raise EntityNotFoundError."""
        ...

    async def get_current(self, query: EntityAsOfQuery) -> OpportunityLifecycle:
        """Return unique current lifecycle or raise not-found/version conflict."""
        ...

    async def history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[LifecycleEvent]:
        """Return contiguous immutable events in sequence order."""
        ...


@runtime_checkable
class NotificationRepository(ImmutableRepository[Notification], Protocol):
    """Append-only access to notification intents and delivery attempts."""

    async def save_delivery_attempt(
        self,
        notification_id: EntityId,
        attempt: DeliveryAttempt,
    ) -> DeliveryAttempt:
        """Append one delivery attempt or raise VersionConflictError."""
        ...

    async def get_latest(self, query: ScopedRepositoryQuery) -> Notification:
        """Return latest notification at as-of or raise EntityNotFoundError."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[Notification]:
        """Return notifications in stable contract order."""
        ...

    async def delivery_history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[DeliveryAttempt]:
        """Return immutable attempts in contiguous sequence order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[Notification]:
        """Return immutable notification versions in stable order."""
        ...
