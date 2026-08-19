"""Focused Phase 4.6 tests for the contract-driven read API."""

from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.opportunity_intelligence.api import create_opportunity_intelligence_app
from app.opportunity_intelligence.domain import OpportunityStance
from app.opportunity_intelligence.repositories import EntityNotFoundError


AS_OF = "2025-01-01T00:05:01Z"


def _client(
    *,
    dashboard: object | None = None,
    detail: object | None = None,
    plans: object | None = None,
    include_market: bool = False,
) -> tuple[TestClient, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    dashboard_value = dashboard or SimpleNamespace(
        items=(),
        to_dict=lambda: {
            "contract_version": "1.0.0",
            "items": [],
            "applied_filters": [],
            "sort": "canonical.rank",
        },
    )
    detail_value = detail or SimpleNamespace(
        to_dict=lambda: {
            "contract_version": "1.0.0",
            "detail_id": "detail.1",
        }
    )
    dashboard_repository = SimpleNamespace(
        get_latest=AsyncMock(return_value=dashboard_value)
    )
    detail_repository = SimpleNamespace(get_current=AsyncMock(return_value=detail_value))
    market_repository = SimpleNamespace(
        get_latest=AsyncMock(
            return_value=SimpleNamespace(
                to_dict=lambda: {
                    "contract_version": "1.0.0",
                    "snapshot_id": "market.BTCUSDT.5m.1",
                    "scope": {"instrument": "BTCUSDT", "timeframe": "5m"},
                    "candles": [],
                }
            )
        )
    )
    app = create_opportunity_intelligence_app(
        dashboard_repository,  # type: ignore[arg-type]
        detail_repository,  # type: ignore[arg-type]
        plans_repository=plans,  # type: ignore[arg-type]
        market_repository=(
            market_repository if include_market else None  # type: ignore[arg-type]
        ),
        clock=lambda: datetime(2025, 1, 1, 0, 5, 1, tzinfo=timezone.utc),
    )
    return TestClient(app), dashboard_repository, detail_repository, market_repository


class OpportunityAPITests(unittest.TestCase):
    def test_dashboard_response_is_versioned_and_deterministically_hashed(self) -> None:
        client, repository, _, _ = _client()

        first = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTC/USD",
                "timeframe": "5m",
                "as_of": AS_OF,
            },
        )
        second = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTC/USD",
                "timeframe": "5m",
                "as_of": AS_OF,
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()["contract_version"], "1.0.0")
        self.assertEqual(len(first.json()["response_hash"]), 64)
        self.assertEqual(repository.get_latest.await_count, 2)

    def test_detail_endpoint_uses_point_in_time_repository_query(self) -> None:
        client, _, repository, _ = _client()

        response = client.get(
            "/api/v1/opportunities/opportunity.1",
            params={"as_of": AS_OF},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["detail_id"], "detail.1")
        query = repository.get_current.await_args.args[0]
        self.assertEqual(query.entity_id.value, "opportunity.1")

    def test_repository_errors_have_stable_public_translation(self) -> None:
        detail_repository = SimpleNamespace(
            get_current=AsyncMock(side_effect=EntityNotFoundError("missing"))
        )
        dashboard_repository = SimpleNamespace(get_latest=AsyncMock())
        client = TestClient(
            create_opportunity_intelligence_app(
                dashboard_repository,  # type: ignore[arg-type]
                detail_repository,  # type: ignore[arg-type]
            )
        )

        response = client.get(
            "/api/v1/opportunities/missing",
            params={"as_of": AS_OF},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "entity.not_found")
        self.assertEqual(len(response.json()["response_hash"]), 64)

    def test_invalid_sort_and_request_schema_fail_closed(self) -> None:
        client, _, _, _ = _client()

        invalid_sort = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTC/USD",
                "timeframe": "5m",
                "as_of": AS_OF,
                "sort": "score.desc",
            },
        )
        invalid_limit = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTC/USD",
                "timeframe": "5m",
                "as_of": AS_OF,
                "limit": 0,
            },
        )

        self.assertEqual(invalid_sort.status_code, 422)
        self.assertEqual(invalid_sort.json()["error"]["code"], "contract.invalid")
        self.assertEqual(invalid_limit.status_code, 422)
        self.assertEqual(invalid_limit.json()["error"]["code"], "request.invalid")

    def test_openapi_exposes_only_contract_routes(self) -> None:
        client, _, _, _ = _client()
        schema = client.get("/api/v1/openapi.json").json()

        self.assertIn("/api/v1/opportunities", schema["paths"])
        self.assertIn("/api/v1/opportunities/{opportunity_id}", schema["paths"])
        self.assertIn("/markets/live", schema["paths"])
        self.assertIn("/opportunities", schema["paths"])
        self.assertIn("/opportunities/{opportunity_id}", schema["paths"])
        self.assertIn("/health", schema["paths"])

    def test_mvp_routes_use_defaults_and_canonical_repository_queries(self) -> None:
        client, dashboard, detail, market = _client(include_market=True)

        market_response = client.get("/markets/live")
        opportunities_response = client.get("/opportunities")
        detail_response = client.get("/opportunities/opportunity.1")

        self.assertEqual(market_response.status_code, 200)
        self.assertEqual(
            market_response.json()["data"]["snapshot_id"],
            "market.BTCUSDT.5m.1",
        )
        market_query = market.get_latest.await_args.args[0]
        self.assertEqual(market_query.scope.instrument, "BTCUSDT")
        self.assertEqual(market_query.scope.timeframe, "5m")
        self.assertEqual(opportunities_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(dashboard.get_latest.await_count, 1)
        self.assertEqual(detail.get_current.await_count, 1)

    def test_dashboard_response_overlays_persisted_plan_presence(self) -> None:
        dashboard_item = SimpleNamespace(
            opportunity_id="opportunity.1",
            opportunity_version_id="opportunity.1.v1",
            scope=SimpleNamespace(instrument="BTCUSDT", timeframe="5m"),
            stance=OpportunityStance.SELL,
            lifecycle_state="DETECTED",
            evidence_cutoff=datetime(2025, 1, 1, 0, 5, 1, tzinfo=timezone.utc),
            available_at=datetime(2025, 1, 1, 0, 5, 1, tzinfo=timezone.utc),
            freshness_state="current",
            rank=1,
            ranking_snapshot_reference=SimpleNamespace(
                artifact_id="ranking.1",
                artifact_type="ranking_snapshot",
                artifact_version="1.0.0",
                available_at=datetime(2025, 1, 1, 0, 5, 1, tzinfo=timezone.utc),
                integrity_digest="a" * 64,
            ),
            score_reference=SimpleNamespace(
                artifact_id="score.1",
                artifact_type="score_result",
                artifact_version="1.0.0",
                available_at=datetime(2025, 1, 1, 0, 5, 1, tzinfo=timezone.utc),
                integrity_digest="b" * 64,
            ),
            confidence_reference=None,
            reason_codes=("assessment.persisted_inputs_verified",),
            has_plan=False,
            limitations=("confidence.unavailable",),
            detail_reference="opportunity.1.v1",
            to_dict=lambda: {
                "opportunity_id": "opportunity.1",
                "opportunity_version_id": "opportunity.1.v1",
                "scope": {
                    "instrument": "BTCUSDT",
                    "timeframe": "5m",
                },
                "stance": OpportunityStance.SELL.value,
                "lifecycle_state": "DETECTED",
                "evidence_cutoff": "2025-01-01T00:05:01+00:00",
                "available_at": "2025-01-01T00:05:01+00:00",
                "freshness_state": "current",
                "rank": 1,
                "ranking_snapshot_reference": {
                    "artifact_id": "ranking.1",
                    "artifact_type": "ranking_snapshot",
                    "artifact_version": "1.0.0",
                    "available_at": "2025-01-01T00:05:01+00:00",
                    "integrity_digest": "a" * 64,
                },
                "score_reference": {
                    "artifact_id": "score.1",
                    "artifact_type": "score_result",
                    "artifact_version": "1.0.0",
                    "available_at": "2025-01-01T00:05:01+00:00",
                    "integrity_digest": "b" * 64,
                },
                "confidence_reference": None,
                "reason_codes": ("assessment.persisted_inputs_verified",),
                "has_plan": False,
                "limitations": ("confidence.unavailable",),
                "detail_reference": "opportunity.1.v1",
            },
        )
        dashboard_page = SimpleNamespace(
            items=(dashboard_item,),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": (dashboard_item.to_dict(),),
                "applied_filters": [],
                "sort": "canonical.rank",
                "coverage_status": "complete",
                "partial_failures": (),
            },
        )
        plans_repository = SimpleNamespace(
            get_latest_for_opportunity=AsyncMock(return_value=SimpleNamespace())
        )
        client, _, _, _ = _client(
            dashboard=dashboard_page,
            plans=plans_repository,
        )

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": AS_OF,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["items"][0]["has_plan"])
        query = plans_repository.get_latest_for_opportunity.await_args.args[0]
        self.assertEqual(query.entity_id.value, "opportunity.1")

    def test_health_is_deterministic_and_reports_unwired_market_repository(self) -> None:
        client, _, _, _ = _client()

        first = client.get("/health")
        second = client.get("/health")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(first.json()["data"]["status"], "degraded")
        self.assertEqual(
            first.json()["data"]["components"]["market_snapshots"],
            "unavailable",
        )

    def test_live_market_fails_closed_when_repository_is_not_configured(self) -> None:
        client, _, _, _ = _client()

        response = client.get("/markets/live")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "storage.unavailable")


def _make_dashboard_item(
    *,
    opportunity_id: str = "opp.1",
    evidence_cutoff: datetime = datetime(2025, 1, 1, 0, 5, 1, tzinfo=timezone.utc),
    rank: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        opportunity_id=opportunity_id,
        opportunity_version_id=f"{opportunity_id}.v1",
        scope=SimpleNamespace(instrument="BTCUSDT", timeframe="5m"),
        stance=OpportunityStance.SELL,
        lifecycle_state="RANKED",
        evidence_cutoff=evidence_cutoff,
        available_at=evidence_cutoff,
        freshness_state="current",
        rank=rank,
        ranking_snapshot_reference=SimpleNamespace(
            artifact_id="ranking.1",
            artifact_type="ranking_snapshot",
            artifact_version="1.0.0",
            available_at=evidence_cutoff,
            integrity_digest="a" * 64,
        ),
        score_reference=SimpleNamespace(
            artifact_id="score.1",
            artifact_type="score_result",
            artifact_version="1.0.0",
            available_at=evidence_cutoff,
            integrity_digest="b" * 64,
        ),
        confidence_reference=None,
        reason_codes=("assessment.persisted_inputs_verified",),
        has_plan=False,
        limitations=("confidence.unavailable",),
        detail_reference=f"{opportunity_id}.v1",
        to_dict=lambda oid=opportunity_id, ec=evidence_cutoff, r=rank: {
            "opportunity_id": oid,
            "opportunity_version_id": f"{oid}.v1",
            "scope": {"instrument": "BTCUSDT", "timeframe": "5m"},
            "stance": "SELL",
            "lifecycle_state": "RANKED",
            "evidence_cutoff": ec.isoformat(),
            "available_at": ec.isoformat(),
            "freshness_state": "current",
            "rank": r,
            "ranking_snapshot_reference": {
                "artifact_id": "ranking.1",
                "artifact_type": "ranking_snapshot",
                "artifact_version": "1.0.0",
                "available_at": ec.isoformat(),
                "integrity_digest": "a" * 64,
            },
            "score_reference": {
                "artifact_id": "score.1",
                "artifact_type": "score_result",
                "artifact_version": "1.0.0",
                "available_at": ec.isoformat(),
                "integrity_digest": "b" * 64,
            },
            "confidence_reference": None,
            "reason_codes": ("assessment.persisted_inputs_verified",),
            "has_plan": False,
            "limitations": ("confidence.unavailable",),
            "detail_reference": f"{oid}.v1",
        },
    )


class OpportunityActiveExpirationTests(unittest.TestCase):
    """Verify that stale opportunities are excluded from the active view."""

    NOW = datetime(2025, 1, 1, 0, 20, 0, tzinfo=timezone.utc)

    def test_fresh_opportunity_appears_in_active_results(self) -> None:
        """Opportunity younger than 10 minutes appears in results."""
        fresh = _make_dashboard_item(
            opportunity_id="opp.fresh",
            evidence_cutoff=datetime(2025, 1, 1, 0, 15, 0, tzinfo=timezone.utc),
        )
        dashboard_page = SimpleNamespace(
            items=(fresh,),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": [],
                "applied_filters": [],
                "sort": "canonical.rank",
            },
        )
        client, _, _, _ = _client(dashboard=dashboard_page)

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": self.NOW.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["items"]), 1)
        self.assertEqual(response.json()["data"]["items"][0]["opportunity_id"], "opp.fresh")

    def test_stale_opportunity_excluded_from_active_results(self) -> None:
        """Opportunity at/over 10 minutes old does NOT appear in results."""
        stale = _make_dashboard_item(
            opportunity_id="opp.stale",
            evidence_cutoff=datetime(2025, 1, 1, 0, 5, 0, tzinfo=timezone.utc),
        )
        dashboard_page = SimpleNamespace(
            items=(stale,),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": [],
                "applied_filters": [],
                "sort": "canonical.rank",
            },
        )
        client, _, _, _ = _client(dashboard=dashboard_page)

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": self.NOW.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["items"]), 0)

    def test_mixed_fresh_and_stale_opportunities(self) -> None:
        """Only fresh opportunities appear; stale ones are filtered out."""
        fresh = _make_dashboard_item(
            opportunity_id="opp.fresh",
            evidence_cutoff=datetime(2025, 1, 1, 0, 15, 0, tzinfo=timezone.utc),
            rank=1,
        )
        stale = _make_dashboard_item(
            opportunity_id="opp.stale",
            evidence_cutoff=datetime(2025, 1, 1, 0, 5, 0, tzinfo=timezone.utc),
            rank=2,
        )
        dashboard_page = SimpleNamespace(
            items=(fresh, stale),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": [],
                "applied_filters": [],
                "sort": "canonical.rank",
            },
        )
        client, _, _, _ = _client(dashboard=dashboard_page)

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": self.NOW.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["opportunity_id"], "opp.fresh")

    def test_opportunity_at_exact_boundary_is_excluded(self) -> None:
        """Opportunity exactly at 10 minutes is excluded (not < 10)."""
        boundary = _make_dashboard_item(
            opportunity_id="opp.boundary",
            evidence_cutoff=datetime(2025, 1, 1, 0, 10, 0, tzinfo=timezone.utc),
        )
        dashboard_page = SimpleNamespace(
            items=(boundary,),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": [],
                "applied_filters": [],
                "sort": "canonical.rank",
            },
        )
        client, _, _, _ = _client(dashboard=dashboard_page)

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": self.NOW.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["items"]), 0)

    def test_just_under_boundary_included(self) -> None:
        """Opportunity at 9m59s is included."""
        almost_stale = _make_dashboard_item(
            opportunity_id="opp.almost",
            evidence_cutoff=datetime(2025, 1, 1, 0, 10, 1, tzinfo=timezone.utc),
        )
        dashboard_page = SimpleNamespace(
            items=(almost_stale,),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": [],
                "applied_filters": [],
                "sort": "canonical.rank",
            },
        )
        client, _, _, _ = _client(dashboard=dashboard_page)

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": self.NOW.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["items"]), 1)

    def test_empty_dashboard_after_expiration(self) -> None:
        """When all opportunities are stale, the dashboard returns empty items."""
        old = _make_dashboard_item(
            opportunity_id="opp.old",
            evidence_cutoff=datetime(2025, 1, 1, 0, 5, 0, tzinfo=timezone.utc),
        )
        dashboard_page = SimpleNamespace(
            items=(old,),
            to_dict=lambda: {
                "contract_version": "1.0.0",
                "items": [],
                "applied_filters": [],
                "sort": "canonical.rank",
            },
        )
        client, _, _, _ = _client(dashboard=dashboard_page)

        response = client.get(
            "/api/v1/opportunities",
            params={
                "instrument": "BTCUSDT",
                "timeframe": "5m",
                "as_of": datetime(2025, 1, 1, 1, 0, 0, tzinfo=timezone.utc).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["items"]), 0)
