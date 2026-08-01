"""Common immutable repository port contracts."""

from typing import Protocol, TypeVar, runtime_checkable

from app.opportunity_intelligence.domain import CanonicalModel
from app.opportunity_intelligence.repositories.queries import (
    EntityAsOfQuery,
    EntityId,
    RepositoryListQuery,
    RepositoryPage,
)


REPOSITORY_INTERFACE_VERSION = "1.0.0"

T = TypeVar("T", bound=CanonicalModel)


@runtime_checkable
class ImmutableRepository(Protocol[T]):
    """Common append-only operations supported by canonical repositories.

    Implementations MUST validate domain contracts and MUST treat a repeated
    byte-identical save as idempotent. A conflicting identity MUST raise
    DuplicateEntityError, VersionConflictError, or ContractViolationError.
    Storage failures MUST surface as StorageUnavailableError.
    """

    async def save(self, entity: T) -> T:
        """Persist one immutable entity and return its canonical stored value."""
        ...

    async def save_batch(self, entities: tuple[T, ...]) -> tuple[T, ...]:
        """Persist a non-empty ordered batch or fail without partial success."""
        ...

    async def get_by_id(self, entity_id: EntityId) -> T:
        """Return one entity or raise EntityNotFoundError."""
        ...

    async def exists(self, query: EntityAsOfQuery) -> bool:
        """Return whether the exact identity exists at the explicit as-of."""
        ...

    async def list(self, query: RepositoryListQuery) -> RepositoryPage[T]:
        """Return stable canonical ordering bound to the query's as-of time."""
        ...
