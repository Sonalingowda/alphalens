"""Phase 4.8 integration and system compliance tests."""

import ast
from dataclasses import replace
from pathlib import Path
from time import perf_counter
import unittest

from fastapi.testclient import TestClient

from app.opportunity_intelligence.api import create_opportunity_intelligence_app
from app.opportunity_intelligence.domain import (
    DashboardItem,
    DashboardPage,
    IndicatorValue,
    LifecycleState,
    OpportunityDetail,
    OpportunityStance,
)
from app.opportunity_intelligence.persistence import (
    DashboardProjectionMemoryRepository,
    MarketSnapshotMemoryRepository,
    OpportunityDetailMemoryRepository,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    RepositoryListQuery,
)
from app.opportunity_intelligence.validation import verify_provenance
from tests.test_opportunity_domain_models import (
    AVAILABLE,
    CUTOFF,
    HASH_A,
    SCOPE,
    START,
    _audit,
    _context,
    _evidence_package,
    _explanation,
    _lifecycle,
    _market_snapshot,
    _opportunity,
    _reference,
)


def _dashboard_page() -> DashboardPage:
    ranking = _reference("ranking.1")
    score = _reference("score.1")
    item = DashboardItem(
        opportunity_id="opportunity.1",
        opportunity_version_id="opportunity.1.v1",
        scope=SCOPE,
        stance=OpportunityStance.BUY,
        lifecycle_state=LifecycleState.PUBLISHED,
        evidence_cutoff=CUTOFF,
        available_at=AVAILABLE,
        freshness_state="current",
        rank=1,
        ranking_snapshot_reference=ranking,
        score_reference=score,
        confidence_reference=None,
        reason_codes=("assessment.buy",),
        has_plan=False,
        limitations=(),
        detail_reference="/opportunities/opportunity.1",
    )
    return DashboardPage(
        contract_version="1.0.0",
        ranking_snapshot_reference=ranking,
        ranking_snapshot_hash=HASH_A,
        as_of=CUTOFF,
        generated_at=AVAILABLE,
        scope=SCOPE,
        items=(item,),
        applied_filters=(),
        sort="canonical.rank",
        next_cursor=None,
        previous_cursor=None,
        freshness_status="current",
        coverage_status="complete",
        partial_failures=(),
        audit=_audit(ranking),
    )


def _detail() -> OpportunityDetail:
    feature = _reference("feature.ema20")
    indicator = IndicatorValue(
        feature_identifier="ema_20",
        definition_version="1.0.0",
        output_name="ema_value",
        value=_market_snapshot().candles[0].close,
        unit="price",
        candle_timestamp=START,
        available_at=CUTOFF,
        feature_record=feature,
    )
    return OpportunityDetail(
        contract_version="1.0.0",
        detail_id="detail.1",
        opportunity=_opportunity(),
        market_snapshot=_market_snapshot(),
        indicators=(indicator,),
        context=_context(),
        evidence=_evidence_package(),
        explanation=_explanation(),
        lifecycle=_lifecycle(),
        historical_references=(),
        verification_status="verified",
        audit=_audit(_reference("detail.source")),
    )


class OpportunitySystemTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_repository_to_api_round_trip_preserves_hashes(self) -> None:
        dashboards = DashboardProjectionMemoryRepository()
        details = OpportunityDetailMemoryRepository()
        page = _dashboard_page()
        detail = _detail()
        await dashboards.save(page)
        await details.save(detail)
        client = TestClient(create_opportunity_intelligence_app(dashboards, details))

        listing = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTC/USD",
                "timeframe": "5m",
                "as_of": AVAILABLE.isoformat(),
                "search": "BTC",
            },
        )
        selected = client.get(
            "/api/v1/opportunities/opportunity.1",
            params={"as_of": AVAILABLE.isoformat()},
        )

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(listing.json()["data"]["items"][0]["rank"], 1)
        self.assertEqual(selected.json()["data"]["detail_id"], detail.detail_id)
        self.assertEqual(len(listing.json()["response_hash"]), 64)
        self.assertEqual(len(selected.json()["response_hash"]), 64)

    async def test_persistence_round_trip_retains_provenance_and_identity(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        snapshot = _market_snapshot()

        await repository.save(snapshot)
        restored = await repository.get_by_id(EntityId(snapshot.snapshot_id))

        self.assertEqual(restored.canonical_json(), snapshot.canonical_json())
        self.assertEqual(restored.canonical_sha256(), snapshot.canonical_sha256())
        self.assertIs(verify_provenance(restored), restored)

    async def test_repository_performance_sanity_and_stable_pagination(self) -> None:
        repository = MarketSnapshotMemoryRepository()
        seed = _market_snapshot()
        snapshots = tuple(
            replace(seed, snapshot_id=f"market.snapshot.performance.{index:03d}")
            for index in range(200)
        )

        started = perf_counter()
        await repository.save_batch(snapshots)
        first = await repository.list(
            RepositoryListQuery(as_of=AVAILABLE, limit=100, scope=SCOPE)
        )
        second = await repository.list(
            RepositoryListQuery(
                as_of=AVAILABLE,
                limit=100,
                scope=SCOPE,
                cursor=first.next_cursor,
            )
        )
        elapsed = perf_counter() - started

        self.assertEqual(len(first.items) + len(second.items), 200)
        self.assertEqual(len({item.snapshot_id for item in first.items + second.items}), 200)
        self.assertLess(elapsed, 2.0)

    def test_opportunity_package_dependency_graph_is_acyclic_and_inward(self) -> None:
        root = Path(__file__).parents[1] / "app" / "opportunity_intelligence"
        layers = {
            "domain": 0,
            "repositories": 1,
            "services": 2,
            "orchestration": 3,
            "persistence": 3,
        }
        edges: dict[str, set[str]] = {name: set() for name in layers}
        for layer in layers:
            for source in (root / layer).glob("*.py"):
                tree = ast.parse(source.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ImportFrom) or node.module is None:
                        continue
                    prefix = "app.opportunity_intelligence."
                    if not node.module.startswith(prefix):
                        continue
                    target = node.module.removeprefix(prefix).split(".", 1)[0]
                    if target in layers and target != layer:
                        edges[layer].add(target)

        self.assertEqual(edges["domain"], set())
        self.assertNotIn("persistence", edges["repositories"])
        self.assertNotIn("orchestration", edges["services"])
        self.assertNotIn("persistence", edges["orchestration"])
        self.assertFalse(_has_cycle(edges))


def _has_cycle(edges: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in edges[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in edges)


if __name__ == "__main__":
    unittest.main()
