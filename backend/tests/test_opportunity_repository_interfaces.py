"""Focused Phase 4.2 tests for storage-agnostic repository interfaces."""

import ast
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import inspect
from pathlib import Path
import unittest
from typing import get_type_hints

from app.opportunity_intelligence.domain import MarketScope, MarketSnapshot
from app.opportunity_intelligence.repositories import (
    ContractViolationError,
    DashboardProjectionRepository,
    DetectionRepository,
    DuplicateEntityError,
    EntityAsOfQuery,
    EntityId,
    EntityNotFoundError,
    EvidenceRepository,
    ExplanationRepository,
    FeatureSnapshotRepository,
    HistoryQuery,
    ImmutableRepository,
    InvalidScopeError,
    LifecycleRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
    NotificationRepository,
    OpportunityDetailRepository,
    OpportunityPlanRepository,
    OpportunityRepository,
    QualificationRepository,
    RankingRepository,
    REPOSITORY_INTERFACE_VERSION,
    RepositoryError,
    RepositoryListQuery,
    RepositoryPage,
    RuntimeGovernanceRepository,
    ScopedRepositoryQuery,
    ScoringRepository,
    StorageUnavailableError,
    ValidationError,
    VersionConflictError,
)


UTC_NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)
SCOPE = MarketScope(instrument="BTC/USD", timeframe="5m")

REPOSITORY_TYPES = (
    MarketSnapshotRepository,
    FeatureSnapshotRepository,
    MarketContextRepository,
    DetectionRepository,
    EvidenceRepository,
    OpportunityRepository,
    QualificationRepository,
    ScoringRepository,
    RankingRepository,
    OpportunityPlanRepository,
    LifecycleRepository,
    NotificationRepository,
    DashboardProjectionRepository,
    OpportunityDetailRepository,
    ExplanationRepository,
    RuntimeGovernanceRepository,
)


class _MarketSnapshotRepositoryShape:
    async def save(self, entity: MarketSnapshot) -> MarketSnapshot:
        raise NotImplementedError

    async def save_batch(
        self,
        entities: tuple[MarketSnapshot, ...],
    ) -> tuple[MarketSnapshot, ...]:
        raise NotImplementedError

    async def get_by_id(self, entity_id: EntityId) -> MarketSnapshot:
        raise NotImplementedError

    async def exists(self, query: EntityAsOfQuery) -> bool:
        raise NotImplementedError

    async def list(
        self,
        query: RepositoryListQuery,
    ) -> RepositoryPage[MarketSnapshot]:
        raise NotImplementedError

    async def get_latest(self, query: ScopedRepositoryQuery) -> MarketSnapshot:
        raise NotImplementedError

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[MarketSnapshot]:
        raise NotImplementedError

    async def history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[MarketSnapshot]:
        raise NotImplementedError


class OpportunityRepositoryInterfaceTests(unittest.TestCase):
    def test_all_required_repositories_are_runtime_protocols(self) -> None:
        self.assertEqual(len(REPOSITORY_TYPES), 16)
        for repository_type in REPOSITORY_TYPES:
            with self.subTest(repository=repository_type.__name__):
                self.assertTrue(getattr(repository_type, "_is_protocol", False))
                self.assertTrue(
                    getattr(repository_type, "_is_runtime_protocol", False)
                )

    def test_structural_interface_compliance_requires_no_base_class(self) -> None:
        repository = _MarketSnapshotRepositoryShape()

        self.assertIsInstance(repository, MarketSnapshotRepository)
        self.assertIsInstance(repository, ImmutableRepository)

    def test_repository_methods_are_async_and_expose_no_delete(self) -> None:
        for repository_type in REPOSITORY_TYPES:
            methods = {
                name: member
                for name, member in inspect.getmembers(
                    repository_type,
                    predicate=inspect.isfunction,
                )
                if not name.startswith("_")
            }
            with self.subTest(repository=repository_type.__name__):
                self.assertTrue(methods)
                self.assertNotIn("delete", methods)
                self.assertFalse(any(name.startswith("delete_") for name in methods))
                self.assertTrue(
                    all(inspect.iscoroutinefunction(method) for method in methods.values())
                )

    def test_market_repository_signatures_use_domain_and_query_types(self) -> None:
        latest_hints = get_type_hints(MarketSnapshotRepository.get_latest)
        list_hints = get_type_hints(MarketSnapshotRepository.get_by_scope)

        self.assertIn(
            ImmutableRepository[MarketSnapshot],
            MarketSnapshotRepository.__orig_bases__,
        )
        self.assertIs(latest_hints["query"], ScopedRepositoryQuery)
        self.assertIs(latest_hints["return"], MarketSnapshot)
        self.assertEqual(
            list_hints["return"],
            RepositoryPage[MarketSnapshot],
        )

    def test_repository_interface_version_matches_frozen_contracts(self) -> None:
        self.assertEqual(REPOSITORY_INTERFACE_VERSION, "1.0.0")

    def test_entity_identity_validation_is_fail_closed(self) -> None:
        self.assertEqual(EntityId("opportunity.1").value, "opportunity.1")

        for invalid in ("", " contains-space", 123):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    EntityId(invalid)  # type: ignore[arg-type]

    def test_query_version_time_scope_limit_and_cursor_validation(self) -> None:
        valid = ScopedRepositoryQuery(
            scope=SCOPE,
            as_of=UTC_NOW,
            limit=10,
            cursor="cursor.1",
        )
        self.assertEqual(valid.scope, SCOPE)

        invalid_queries = (
            lambda: ScopedRepositoryQuery(SCOPE, UTC_NOW.replace(tzinfo=None), 10),
            lambda: ScopedRepositoryQuery(SCOPE, UTC_NOW, 0),
            lambda: ScopedRepositoryQuery(SCOPE, UTC_NOW, True),
            lambda: ScopedRepositoryQuery(SCOPE, UTC_NOW, 10, ""),
            lambda: ScopedRepositoryQuery("BTC/USD", UTC_NOW, 10),  # type: ignore[arg-type]
            lambda: EntityAsOfQuery("opportunity.1", UTC_NOW),  # type: ignore[arg-type]
        )
        for construct in invalid_queries:
            with self.subTest(construct=construct):
                with self.assertRaises(ValidationError):
                    construct()

    def test_query_and_page_objects_are_immutable(self) -> None:
        query = RepositoryListQuery(as_of=UTC_NOW, limit=10, scope=SCOPE)
        page = RepositoryPage(items=("one", "two"), as_of=UTC_NOW)

        with self.assertRaises(FrozenInstanceError):
            query.limit = 20  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            page.items = ()  # type: ignore[misc]
        with self.assertRaises(ValidationError):
            RepositoryPage(items=["mutable"], as_of=UTC_NOW)  # type: ignore[arg-type]

    def test_history_and_as_of_queries_require_validated_identity(self) -> None:
        entity_id = EntityId("opportunity.1")

        history = HistoryQuery(entity_id=entity_id, as_of=UTC_NOW, limit=10)
        exact = EntityAsOfQuery(entity_id=entity_id, as_of=UTC_NOW)

        self.assertEqual(history.entity_id, entity_id)
        self.assertEqual(exact.entity_id, entity_id)

    def test_exception_hierarchy_is_storage_neutral(self) -> None:
        exception_types = (
            EntityNotFoundError,
            DuplicateEntityError,
            VersionConflictError,
            InvalidScopeError,
            ContractViolationError,
            ValidationError,
            StorageUnavailableError,
        )
        for exception_type in exception_types:
            with self.subTest(exception=exception_type.__name__):
                self.assertTrue(issubclass(exception_type, RepositoryError))
                self.assertFalse(
                    any(
                        token in exception_type.__module__.lower()
                        for token in ("sql", "redis", "http", "fastapi")
                    )
                )

    def test_interface_package_has_no_forbidden_dependencies(self) -> None:
        repository_root = (
            Path(__file__).parents[1]
            / "app"
            / "opportunity_intelligence"
            / "repositories"
        )
        forbidden_roots = {
            "fastapi",
            "sqlalchemy",
            "redis",
            "celery",
            "httpx",
            "websockets",
            "asyncpg",
            "app.persistence",
            "app.api",
        }

        for source_path in repository_root.glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            imports = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module is not None
            }
            imports.update(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            with self.subTest(source=source_path.name):
                self.assertFalse(imports & forbidden_roots)
                self.assertFalse(
                    any(
                        imported.startswith(f"{root}.")
                        for imported in imports
                        for root in forbidden_roots
                    )
                )

    def test_deterministic_queries_require_explicit_as_of_and_limit(self) -> None:
        scoped_signature = inspect.signature(ScopedRepositoryQuery)
        history_signature = inspect.signature(HistoryQuery)

        self.assertIs(
            scoped_signature.parameters["as_of"].default,
            inspect.Parameter.empty,
        )
        self.assertIs(
            scoped_signature.parameters["limit"].default,
            inspect.Parameter.empty,
        )
        self.assertIs(
            history_signature.parameters["as_of"].default,
            inspect.Parameter.empty,
        )
        self.assertIs(
            history_signature.parameters["limit"].default,
            inspect.Parameter.empty,
        )
