"""Focused Clerk authentication and protected paper-tracking boundary tests."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from app.paper_execution.api import create_paper_tracking_router
from app.paper_execution.auth import ClerkActor, ClerkPaperTrackingAuthenticator


def _request(headers: list[tuple[bytes, bytes]] | None = None):
    return SimpleNamespace(headers=dict(headers or []))


class ClerkAuthenticatorTests(unittest.TestCase):
    def test_missing_authentication_fails_closed(self) -> None:
        authenticator = ClerkPaperTrackingAuthenticator(
            secret_key="test-secret",
            authorized_parties=("http://localhost:3000",),
            authorized_user_id="user_authorized",
        )
        with self.assertRaisesRegex(Exception, "Authentication could not be verified"):
            authenticator.authenticate(_request())

    def test_invalid_or_expired_authentication_fails_closed(self) -> None:
        authenticator = ClerkPaperTrackingAuthenticator(
            secret_key="test-secret",
            authorized_parties=("http://localhost:3000",),
            authorized_user_id="user_authorized",
        )
        state = SimpleNamespace(is_authenticated=False, payload=None)
        with patch("app.paper_execution.auth.Clerk") as clerk:
            clerk.return_value.authenticate_request.return_value = state
            for _reason in ("invalid", "expired", "malformed"):
                with self.assertRaisesRegex(Exception, "Authentication could not be verified"):
                    authenticator.authenticate(
                        _request([(b"authorization", b"Bearer test-token")])
                    )

    def test_valid_but_unauthorized_user_is_rejected(self) -> None:
        authenticator = ClerkPaperTrackingAuthenticator(
            secret_key="test-secret",
            authorized_parties=("http://localhost:3000",),
            authorized_user_id="user_authorized",
        )
        state = SimpleNamespace(is_authenticated=True, payload={"sub": "user_other"})
        with patch("app.paper_execution.auth.Clerk") as clerk:
            clerk.return_value.authenticate_request.return_value = state
            with self.assertRaisesRegex(Exception, "not authorized"):
                authenticator.authenticate(
                    _request([(b"authorization", b"Bearer test-token")])
                )

    def test_valid_authorized_user_identity_is_derived_from_payload(self) -> None:
        authenticator = ClerkPaperTrackingAuthenticator(
            secret_key="test-secret",
            authorized_parties=("http://localhost:3000",),
            authorized_user_id="user_authorized",
        )
        state = SimpleNamespace(is_authenticated=True, payload={"sub": "user_authorized"})
        with patch("app.paper_execution.auth.Clerk") as clerk:
            clerk.return_value.authenticate_request.return_value = state
            actor = authenticator.authenticate(
                _request([(b"authorization", b"Bearer test-token")])
            )
        self.assertEqual(actor, ClerkActor(user_id="user_authorized"))


class ProtectedPaperTrackingRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_actor_field_is_rejected_and_authorized_actor_is_used(self) -> None:
        class _Authenticator:
            def authenticate(self, request):
                del request
                return ClerkActor(user_id="user_authorized")

        class _Service:
            def __init__(self):
                self.actor_id = None

            async def confirmation_by_reference(self, **kwargs):
                return {
                    "opportunity_id": kwargs["opportunity_id"],
                    "opportunity_version_id": kwargs["opportunity_version_id"],
                    "confirmed_scenario_hash": "a" * 64,
                }

            async def select_by_reference(self, **kwargs):
                self.actor_id = kwargs["actor_id"]
                return SimpleNamespace(
                    execution=SimpleNamespace(
                        execution_id="paper_execution:opportunity-version-1",
                        state=SimpleNamespace(value="ACTIVE"),
                    ),
                    position=SimpleNamespace(position_id="paper_position:opportunity-version-1"),
                    opportunity_id=kwargs["opportunity_id"],
                    opportunity_version_id=kwargs["opportunity_version_id"],
                    selected_at="2026-01-01T00:00:00Z",
                    selection_event=SimpleNamespace(actor_id="user_authorized"),
                )

        service = _Service()
        app = FastAPI()
        app.include_router(
            create_paper_tracking_router(
                selection_service=service,
                authenticator=_Authenticator(),
            )
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            rejected = await client.post(
                "/api/v1/paper-tracking/selections",
                json={
                    "opportunity_id": "opportunity-1",
                    "opportunity_version_id": "opportunity-version-1",
                    "confirmed_scenario_hash": "a" * 64,
                    "actor_id": "attacker",
                },
            )
            accepted = await client.post(
                "/api/v1/paper-tracking/selections",
                json={
                    "opportunity_id": "opportunity-1",
                    "opportunity_version_id": "opportunity-version-1",
                    "confirmed_scenario_hash": "a" * 64,
                },
            )
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(service.actor_id, "user_authorized")
        self.assertEqual(accepted.json()["status"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
