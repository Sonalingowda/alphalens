"""Regression tests for fail-closed Active/Monitoring/History projections."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.opportunity_intelligence.api import create_opportunity_intelligence_app


NOW = datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc)


def thesis(thesis_id: str, state: str, minutes_old: int) -> dict[str, object]:
    observed = NOW - timedelta(minutes=minutes_old)
    return {
        "thesis_id": thesis_id,
        "original_opportunity_id": f"opp.{thesis_id}",
        "original_opportunity_version_id": f"opp.{thesis_id}.v1",
        "direction": "BUY",
        "original_created_at": observed,
        "last_observed_at": observed,
        "current_state": state,
        "original_plan": {"entry_zone": {"lower": "100", "upper": "101"}},
        "related_thesis_ids": [],
        "related_assessment_count": 1,
        "review_cluster_status": "SINGLE_THESIS",
    }


def client(items, status):
    thesis_service = SimpleNamespace(list=AsyncMock(return_value=items))
    app = create_opportunity_intelligence_app(
        SimpleNamespace(), SimpleNamespace(), thesis_service=thesis_service,
        clock=lambda: NOW, runtime_status_provider=lambda: status,
    )
    return TestClient(app)


def running_status():
    return {
        "worker": {"status": "RUNNING"},
        "connection": {"state": "connected", "last_message_at": NOW.isoformat()},
        "checkpoint": {"gap_status": "CLEAR"},
    }


def test_stopped_feed_hides_active_and_preserves_history():
    items = [thesis("stale", "ENTRY_MISSED", 1), thesis("old", "INVALIDATED", 1)]
    status = {"worker": {"status": "STOPPED"}, "connection": {"state": "stopped"}, "checkpoint": {"gap_status": "QUARANTINED"}}
    api = client(items, status)
    params = {"instrument": "BTCUSDT", "timeframe": "5m", "as_of": NOW.isoformat()}
    assert api.get("/api/v1/opportunities", params={**params, "view": "active"}).json()["data"]["items"] == []
    monitoring = api.get("/api/v1/opportunities", params={**params, "view": "monitoring"}).json()["data"]
    assert [item["thesis_id"] for item in monitoring["items"]] == ["stale"]
    assert monitoring["freshness_warning"]
    history = api.get("/api/v1/opportunities", params={**params, "view": "history"}).json()["data"]
    assert [item["thesis_id"] for item in history["items"]] == ["old"]
    assert history["freshness_warning"]


def test_running_feed_separates_actionable_monitoring_and_terminal_history():
    items = [
        thesis("active", "ENTRY_AVAILABLE", 1),
        thesis("monitor", "WAITING_FOR_ENTRY", 1),
        thesis("missed", "ENTRY_MISSED", 1),
        thesis("target", "INITIAL_TARGET_REACHED", 1),
    ]
    api = client(items, running_status())
    base = {"instrument": "BTCUSDT", "timeframe": "5m", "as_of": NOW.isoformat()}
    assert [x["thesis_id"] for x in api.get("/api/v1/opportunities", params={**base, "view": "active"}).json()["data"]["items"]] == ["active"]
    assert {x["thesis_id"] for x in api.get("/api/v1/opportunities", params={**base, "view": "monitoring"}).json()["data"]["items"]} == {"monitor", "missed"}
    history = api.get("/api/v1/opportunities", params={**base, "view": "history"}).json()["data"]["items"]
    assert [x["thesis_id"] for x in history] == ["target"]
    assert history[0]["entry_confirmation_status"] == "not_recorded"


def test_stale_observation_is_history_without_mutation():
    service = SimpleNamespace(list=AsyncMock(return_value=[thesis("old", "WAITING_FOR_ENTRY", 11)]))
    api = create_opportunity_intelligence_app(SimpleNamespace(), SimpleNamespace(), thesis_service=service, clock=lambda: NOW, runtime_status_provider=running_status)
    response = TestClient(api).get("/api/v1/opportunities", params={"instrument": "BTCUSDT", "timeframe": "5m", "as_of": NOW.isoformat(), "view": "active"})
    assert response.json()["data"]["items"] == []
    assert service.list.await_count == 1

