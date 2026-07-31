"""P1-07 deterministic read-only operational inspection tests."""

from dataclasses import replace
from datetime import datetime, timezone
import asyncio
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx
from sqlalchemy.exc import SQLAlchemyError

from app.api.historical_inspection import create_historical_inspection_app
from app.market_data.inspection import (
    HistoricalInspectionError,
    build_historical_operational_inspection,
    verify_historical_operational_inspection,
)
from app.persistence.inspection import load_historical_operational_inspection


_AS_OF = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _inspection():
    return build_historical_operational_inspection(
        as_of=_AS_OF,
        acquisition=[
            {
                "timeframe": "5m",
                "operational_state": "SUCCESS_REUSE_ONLY",
                "checkpoint": {"checkpoint_hash": "a" * 64},
                "integrity_status": "VERIFIED",
            },
            {
                "timeframe": "15m",
                "operational_state": "NO_ATTEMPT",
                "checkpoint": None,
                "integrity_status": "UNAVAILABLE",
            },
        ],
        source_conflicts=[
            {
                "timeframe": "5m",
                "conflict_hash": "b" * 64,
                "integrity_status": "VERIFIED",
            }
        ],
        synchronized_coverage={
            "source_provenance_hash": "c" * 64,
            "result_hash": "d" * 64,
            "integrity_status": "VERIFIED",
        },
        historical_quality={
            "acquisition_policy_version": "1.0.0",
            "source_policy_version": "1.0.0",
            "result_hash": "e" * 64,
            "integrity_status": "VERIFIED",
        },
    )


class HistoricalInspectionContractTests(unittest.TestCase):
    def test_repeated_build_is_byte_identical_and_hash_stable(self) -> None:
        first = _inspection()
        second = _inspection()

        self.assertEqual(first, second)
        self.assertEqual(len(first.result_hash), 64)
        self.assertEqual(first.response()["result_hash"], first.result_hash)
        verify_historical_operational_inspection(first)

    def test_corrupted_canonical_evidence_fails_closed(self) -> None:
        inspection = _inspection()
        payload = json.loads(inspection.canonical_json)
        payload["integrity_status"] = "UNVERIFIED"
        corrupted = replace(
            inspection,
            canonical_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        )

        with self.assertRaisesRegex(
            HistoricalInspectionError,
            "integrity verification failed",
        ):
            verify_historical_operational_inspection(corrupted)

    def test_timezone_is_required_for_point_in_time_snapshot(self) -> None:
        with self.assertRaisesRegex(HistoricalInspectionError, "timezone-aware"):
            build_historical_operational_inspection(
                as_of=datetime(2026, 8, 1, 12, 0),
                acquisition=[],
                source_conflicts=[],
                synchronized_coverage=None,
                historical_quality=None,
            )


class HistoricalInspectionAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = AsyncMock(return_value=_inspection())
        self.client = TestClient(
            create_historical_inspection_app(
                inspection_provider=self.provider,
                maximum_request_bytes=1024,
            )
        )

    def test_get_exposes_verified_evidence_at_explicit_as_of(self) -> None:
        response = self.client.get(
            "/v1/historical-inspection/state",
            params={"as_of": "2026-08-01T17:30:00+05:30"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), _inspection().response())
        self.assertEqual(
            response.headers["X-AlphaLens-Evidence-SHA256"],
            _inspection().result_hash,
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.provider.assert_awaited_once_with(_AS_OF)

    def test_repeated_get_is_deterministic(self) -> None:
        url = "/v1/historical-inspection/state?as_of=2026-08-01T12:00:00Z"

        first = self.client.get(url)
        second = self.client.get(url)

        self.assertEqual(first.content, second.content)
        self.assertEqual(first.headers["content-type"], "application/json")

    def test_mutation_method_is_rejected_without_invoking_provider(self) -> None:
        response = self.client.post(
            "/v1/historical-inspection/state?as_of=2026-08-01T12:00:00Z"
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"]["code"], "METHOD_NOT_ALLOWED")
        self.provider.assert_not_awaited()

    def test_body_and_oversized_body_are_rejected(self) -> None:
        url = "/v1/historical-inspection/state?as_of=2026-08-01T12:00:00Z"

        body_response = self.client.request("GET", url, content=b"evidence")
        oversized_response = self.client.request("GET", url, content=b"x" * 1025)

        self.assertEqual(body_response.status_code, 400)
        self.assertEqual(
            body_response.json()["error"]["code"],
            "REQUEST_BODY_NOT_ALLOWED",
        )
        self.assertEqual(oversized_response.status_code, 413)
        self.provider.assert_not_awaited()

    def test_missing_timezone_and_unsupported_scope_are_rejected(self) -> None:
        naive = self.client.get(
            "/v1/historical-inspection/state",
            params={"as_of": "2026-08-01T12:00:00"},
        )
        scope = self.client.get(
            "/v1/historical-inspection/state",
            params={
                "as_of": "2026-08-01T12:00:00Z",
                "asset_identifier": "ETH",
            },
        )

        self.assertEqual(naive.status_code, 422)
        self.assertEqual(
            naive.json()["error"]["code"],
            "AS_OF_TIMEZONE_REQUIRED",
        )
        self.assertEqual(scope.status_code, 422)
        self.assertEqual(scope.json()["error"]["code"], "SCOPE_UNSUPPORTED")
        self.provider.assert_not_awaited()

    def test_integrity_failure_is_deterministic_and_closed(self) -> None:
        provider = AsyncMock(side_effect=HistoricalInspectionError("corrupt"))
        client = TestClient(
            create_historical_inspection_app(inspection_provider=provider)
        )

        response = client.get(
            "/v1/historical-inspection/state?as_of=2026-08-01T12:00:00Z"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "INTEGRITY_VALIDATION_FAILED",
        )

    def test_storage_unavailability_preserves_retryable_failure_semantics(self) -> None:
        provider = AsyncMock(side_effect=SQLAlchemyError("unavailable"))
        client = TestClient(
            create_historical_inspection_app(inspection_provider=provider)
        )

        response = client.get(
            "/v1/historical-inspection/state?as_of=2026-08-01T12:00:00Z"
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "INSPECTION_UNAVAILABLE",
        )


class HistoricalInspectionConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_reads_are_identical_and_side_effect_free(self) -> None:
        provider = AsyncMock(return_value=_inspection())
        app = create_historical_inspection_app(inspection_provider=provider)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://inspection.test",
        ) as client:
            first, second = await asyncio.gather(
                client.get(
                    "/v1/historical-inspection/state",
                    params={"as_of": "2026-08-01T12:00:00Z"},
                ),
                client.get(
                    "/v1/historical-inspection/state",
                    params={"as_of": "2026-08-01T12:00:00Z"},
                ),
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, second.content)
        self.assertEqual(provider.await_count, 2)


class HistoricalInspectionRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_repository_uses_only_verified_read_models(self) -> None:
        session = object()
        with (
            patch(
                "app.persistence.inspection._acquisition_evidence",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.persistence.inspection._conflict_evidence",
                AsyncMock(return_value=[]),
            ),
            patch(
                "app.persistence.inspection._synchronization_evidence",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.persistence.inspection._quality_evidence",
                AsyncMock(return_value=None),
            ),
        ):
            result = await load_historical_operational_inspection(
                session,  # type: ignore[arg-type]
                as_of=_AS_OF,
            )

        self.assertEqual(result.response()["integrity_status"], "VERIFIED")
        self.assertEqual(result.response()["source_conflicts"], [])

    def test_inspection_repository_contains_no_write_calls(self) -> None:
        source = inspect.getsource(load_historical_operational_inspection)
        module_source = Path(inspect.getfile(load_historical_operational_inspection)).read_text()

        self.assertNotIn("session.add", module_source)
        self.assertNotIn("session.commit", module_source)
        self.assertNotIn("session.delete", module_source)
        self.assertNotIn("session.execute", source)
