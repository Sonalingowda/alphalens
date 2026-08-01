"""Storage-agnostic repository exception hierarchy."""


class RepositoryError(Exception):
    """Base class for every repository boundary failure."""


class EntityNotFoundError(RepositoryError):
    """Raised when a requested immutable entity does not exist."""


class DuplicateEntityError(RepositoryError):
    """Raised when an identity already exists with different canonical content."""


class VersionConflictError(RepositoryError):
    """Raised when immutable version or successor expectations conflict."""


class InvalidScopeError(RepositoryError):
    """Raised when a scope is invalid or unsupported by a repository."""


class ContractViolationError(RepositoryError):
    """Raised when an entity violates its frozen repository contract."""


class ValidationError(RepositoryError):
    """Raised when a repository argument is structurally invalid."""


class StorageUnavailableError(RepositoryError):
    """Storage-neutral failure indicating that an operation cannot complete."""

