"""Focused Phase 4.3 tests for application-service interfaces."""

import ast
from pathlib import Path
import inspect
import unittest
from typing import get_type_hints

from app.opportunity_intelligence.domain import FeatureSnapshot, MarketSnapshot
from app.opportunity_intelligence.repositories import ScopedRepositoryQuery
from app.opportunity_intelligence.services import (
    DashboardService,
    EvidenceService,
    ExplanationService,
    FeatureSnapshotService,
    IndicatorProjectionService,
    LifecycleService,
    MarketContextService,
    MarketScannerService,
    NotificationService,
    OpportunityAssessmentService,
    OpportunityDetectionService,
    OpportunityDetailService,
    OpportunityPlanService,
    PipelineSuspendedError,
    PolicyUnavailableError,
    QualificationService,
    RankingService,
    RuntimeGovernanceService,
    ScoringService,
    SERVICE_INTERFACE_VERSION,
    ServiceContractError,
    ServiceError,
    ServiceUnavailableError,
)


SERVICE_TYPES = (
    MarketScannerService,
    FeatureSnapshotService,
    IndicatorProjectionService,
    MarketContextService,
    OpportunityDetectionService,
    EvidenceService,
    OpportunityAssessmentService,
    QualificationService,
    ScoringService,
    RankingService,
    OpportunityPlanService,
    LifecycleService,
    NotificationService,
    DashboardService,
    OpportunityDetailService,
    ExplanationService,
    RuntimeGovernanceService,
)


class _ScannerShape:
    async def scan(self, query: ScopedRepositoryQuery) -> MarketSnapshot:
        raise NotImplementedError


class OpportunityServiceInterfaceTests(unittest.TestCase):
    def test_required_service_ports_are_runtime_protocols(self) -> None:
        self.assertEqual(len(SERVICE_TYPES), 17)
        for service_type in SERVICE_TYPES:
            with self.subTest(service=service_type.__name__):
                self.assertTrue(getattr(service_type, "_is_protocol", False))
                self.assertTrue(getattr(service_type, "_is_runtime_protocol", False))

    def test_all_public_service_methods_are_async_and_typed(self) -> None:
        for service_type in SERVICE_TYPES:
            methods = {
                name: member
                for name, member in inspect.getmembers(
                    service_type,
                    predicate=inspect.isfunction,
                )
                if not name.startswith("_")
            }
            with self.subTest(service=service_type.__name__):
                self.assertTrue(methods)
                self.assertTrue(
                    all(inspect.iscoroutinefunction(method) for method in methods.values())
                )
                for method in methods.values():
                    hints = get_type_hints(method)
                    self.assertIn("return", hints)
                    parameters = inspect.signature(method).parameters
                    self.assertTrue(
                        all(
                            name == "self" or name in hints
                            for name in parameters
                        )
                    )

    def test_scanner_and_feature_ports_preserve_domain_boundaries(self) -> None:
        scan_hints = get_type_hints(MarketScannerService.scan)
        feature_hints = get_type_hints(FeatureSnapshotService.resolve)

        self.assertIs(scan_hints["query"], ScopedRepositoryQuery)
        self.assertIs(scan_hints["return"], MarketSnapshot)
        self.assertIs(feature_hints["market_snapshot"], MarketSnapshot)
        self.assertIs(feature_hints["return"], FeatureSnapshot)

    def test_structural_compliance_requires_no_service_base_class(self) -> None:
        self.assertIsInstance(_ScannerShape(), MarketScannerService)

    def test_service_interface_version_matches_frozen_contracts(self) -> None:
        self.assertEqual(SERVICE_INTERFACE_VERSION, "1.0.0")

    def test_service_exception_hierarchy_is_fail_closed(self) -> None:
        for exception_type in (
            ServiceContractError,
            PolicyUnavailableError,
            ServiceUnavailableError,
            PipelineSuspendedError,
        ):
            with self.subTest(exception=exception_type.__name__):
                self.assertTrue(issubclass(exception_type, ServiceError))

    def test_service_interfaces_have_no_infrastructure_dependencies(self) -> None:
        service_root = (
            Path(__file__).parents[1]
            / "app"
            / "opportunity_intelligence"
            / "services"
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
        allowed_application_roots = {
            "app.opportunity_intelligence.domain",
            "app.opportunity_intelligence.repositories",
            "app.opportunity_intelligence.services",
        }

        for source_path in service_root.glob("*.py"):
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
                        imported.startswith("app.")
                        and not any(
                            imported.startswith(root)
                            for root in allowed_application_roots
                        )
                        for imported in imports
                    )
                )

    def test_interfaces_expose_no_implementation_state(self) -> None:
        for service_type in SERVICE_TYPES:
            with self.subTest(service=service_type.__name__):
                annotations = getattr(service_type, "__annotations__", {})
                self.assertEqual(annotations, {})
