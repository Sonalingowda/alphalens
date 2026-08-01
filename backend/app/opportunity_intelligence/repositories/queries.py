"""Immutable validated repository arguments and deterministic result pages."""

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable
from typing import Generic, TypeVar

from app.opportunity_intelligence.domain import MarketScope
from app.opportunity_intelligence.domain.primitives import (
    DomainValidationError,
    validate_identifier,
    validate_utc,
)
from app.opportunity_intelligence.repositories.errors import ValidationError


T = TypeVar("T")


def _translate_domain_validation(operation: Callable[[], None]) -> None:
    try:
        operation()
    except DomainValidationError as error:
        raise ValidationError(str(error)) from error


@dataclass(frozen=True, slots=True)
class EntityId:
    """Validated immutable canonical entity identifier."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValidationError("Repository entity identifier must be a string.")
        _translate_domain_validation(
            lambda: validate_identifier(self.value, "Repository entity identifier")
        )


@dataclass(frozen=True, slots=True)
class EntityAsOfQuery:
    """Exact identity query evaluated at an explicit point in time."""

    entity_id: EntityId
    as_of: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, EntityId):
            raise ValidationError("Entity as-of query requires a validated EntityId.")
        _validate_datetime(self.as_of, "Entity query as-of")


@dataclass(frozen=True, slots=True)
class RepositoryListQuery:
    """Point-in-time deterministic list query over an optional scope."""

    as_of: datetime
    limit: int
    scope: MarketScope | None = None
    cursor: str | None = None

    def __post_init__(self) -> None:
        if self.scope is not None and not isinstance(self.scope, MarketScope):
            raise ValidationError("Repository list scope must be a MarketScope.")
        _validate_datetime(self.as_of, "Repository list as-of")
        if (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or self.limit <= 0
        ):
            raise ValidationError("Repository list limit must be a positive integer.")
        _validate_cursor(self.cursor, "Repository cursor")


@dataclass(frozen=True, slots=True)
class ScopedRepositoryQuery:
    """Point-in-time deterministic query for one canonical market scope."""

    scope: MarketScope
    as_of: datetime
    limit: int
    cursor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, MarketScope):
            raise ValidationError("Scoped query scope must be a MarketScope.")
        _validate_datetime(self.as_of, "Scoped repository as-of")
        if (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or self.limit <= 0
        ):
            raise ValidationError("Scoped query limit must be a positive integer.")
        _validate_cursor(self.cursor, "Scoped query cursor")


@dataclass(frozen=True, slots=True)
class HistoryQuery:
    """Deterministic immutable-version history query."""

    entity_id: EntityId
    as_of: datetime
    limit: int
    cursor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, EntityId):
            raise ValidationError("History query requires a validated EntityId.")
        _validate_datetime(self.as_of, "Repository history as-of")
        if (
            not isinstance(self.limit, int)
            or isinstance(self.limit, bool)
            or self.limit <= 0
        ):
            raise ValidationError("History query limit must be a positive integer.")
        _validate_cursor(self.cursor, "History query cursor")


@dataclass(frozen=True, slots=True)
class RepositoryPage(Generic[T]):
    """Immutable ordered repository result bound to one point in time."""

    items: tuple[T, ...]
    as_of: datetime
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise ValidationError("Repository page items must be an immutable tuple.")
        _validate_datetime(self.as_of, "Repository page as-of")
        _validate_cursor(self.next_cursor, "Repository page cursor")


def _validate_cursor(value: str | None, name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValidationError(f"{name} must be a non-empty string when present.")


def _validate_datetime(value: datetime, name: str) -> None:
    if not isinstance(value, datetime):
        raise ValidationError(f"{name} must be a datetime.")
    _translate_domain_validation(lambda: validate_utc(value, name))
