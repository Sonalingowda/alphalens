"""Repository ports for read projections and explanations."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    DashboardPage,
    ExplanationArtifact,
    OpportunityDetail,
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
class DashboardProjectionRepository(
    ImmutableRepository[DashboardPage],
    Protocol,
):
    """Append-only access to snapshot-bound dashboard projections."""

    async def get_latest(self, query: ScopedRepositoryQuery) -> DashboardPage:
        """Return latest page at as-of or raise EntityNotFoundError."""
        ...

    async def get_by_ranking_snapshot(
        self,
        ranking_snapshot_id: EntityId,
    ) -> DashboardPage:
        """Return projection for one ranking snapshot or raise not found."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[DashboardPage]:
        """Return projections in stable contract order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[DashboardPage]:
        """Return immutable projection history in stable order."""
        ...


@runtime_checkable
class OpportunityDetailRepository(
    ImmutableRepository[OpportunityDetail],
    Protocol,
):
    """Append-only access to canonical opportunity-detail projections."""

    async def get_by_opportunity_version(
        self,
        opportunity_version_id: EntityId,
    ) -> OpportunityDetail:
        """Return exact revision detail or raise EntityNotFoundError."""
        ...

    async def get_current(self, query: EntityAsOfQuery) -> OpportunityDetail:
        """Return current detail or raise not-found/version conflict."""
        ...

    async def history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[OpportunityDetail]:
        """Return immutable detail history in stable order."""
        ...


@runtime_checkable
class ExplanationRepository(
    ImmutableRepository[ExplanationArtifact],
    Protocol,
):
    """Append-only access to deterministic explanation artifacts."""

    async def get_by_opportunity_version(
        self,
        opportunity_version_id: EntityId,
    ) -> ExplanationArtifact:
        """Return exact version explanation or raise EntityNotFoundError."""
        ...

    async def history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[ExplanationArtifact]:
        """Return immutable explanation history in stable order."""
        ...
