"""Repository ports for immutable market, feature, and context snapshots."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    FeatureSnapshot,
    MarketContext,
    MarketSnapshot,
)
from app.opportunity_intelligence.repositories.base import ImmutableRepository
from app.opportunity_intelligence.repositories.queries import (
    HistoryQuery,
    RepositoryPage,
    ScopedRepositoryQuery,
)


@runtime_checkable
class MarketSnapshotRepository(
    ImmutableRepository[MarketSnapshot],
    Protocol,
):
    """Append-only access to canonical completed market snapshots."""

    async def get_latest(self, query: ScopedRepositoryQuery) -> MarketSnapshot:
        """Return latest snapshot at as-of or raise EntityNotFoundError."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[MarketSnapshot]:
        """Return snapshots in stable newest-first contract order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[MarketSnapshot]:
        """Return immutable versions or raise EntityNotFoundError."""
        ...


@runtime_checkable
class FeatureSnapshotRepository(
    ImmutableRepository[FeatureSnapshot],
    Protocol,
):
    """Append-only access to canonical feature snapshots."""

    async def get_latest(self, query: ScopedRepositoryQuery) -> FeatureSnapshot:
        """Return latest compatible snapshot or raise EntityNotFoundError."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[FeatureSnapshot]:
        """Return snapshots in stable newest-first contract order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[FeatureSnapshot]:
        """Return immutable versions or raise EntityNotFoundError."""
        ...


@runtime_checkable
class MarketContextRepository(
    ImmutableRepository[MarketContext],
    Protocol,
):
    """Append-only access to descriptive market-context snapshots."""

    async def get_latest(self, query: ScopedRepositoryQuery) -> MarketContext:
        """Return latest context at as-of or raise EntityNotFoundError."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[MarketContext]:
        """Return context snapshots in stable contract order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[MarketContext]:
        """Return immutable context versions or raise EntityNotFoundError."""
        ...

