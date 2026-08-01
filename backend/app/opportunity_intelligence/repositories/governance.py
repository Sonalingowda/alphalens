"""Repository port for immutable runtime-governance health records."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import RuntimeHealthRecord
from app.opportunity_intelligence.repositories.base import ImmutableRepository
from app.opportunity_intelligence.repositories.queries import (
    HistoryQuery,
    RepositoryPage,
    ScopedRepositoryQuery,
)


@runtime_checkable
class RuntimeGovernanceRepository(
    ImmutableRepository[RuntimeHealthRecord],
    Protocol,
):
    """Append-only access to runtime health, suspension, and recovery evidence."""

    async def get_latest(
        self,
        query: ScopedRepositoryQuery,
    ) -> RuntimeHealthRecord:
        """Return latest health record at as-of or raise EntityNotFoundError."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[RuntimeHealthRecord]:
        """Return health records in stable contract order."""
        ...

    async def history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[RuntimeHealthRecord]:
        """Return immutable health history in stable order."""
        ...
