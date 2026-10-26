"""Offline delivery-audit tests using an in-memory transport and repository."""

import asyncio
import unittest
from datetime import datetime, timezone

from app.opportunity_intelligence.domain import DeliveryState
from app.runtime_notification import (
    NotificationDeliveryService,
    RetryableDeliveryError,
)
from tests.test_runtime_notification import _notification_fixture


class _Transport:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0

    async def send(self, notification):
        del notification
        self.calls += 1
        if self.calls <= self.failures:
            raise RetryableDeliveryError("test transport unavailable")
        return f"provider.ref.{self.calls}"


class NotificationDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivery_is_durable_and_idempotent_after_success(self) -> None:
        _, opportunity, lifecycle, ranking, service, repository = (
            await _notification_fixture()
        )
        notifications = await service.create_intents(
            ranking,
            (opportunity,),
            (lifecycle,),
        )
        transport = _Transport()
        delivery = NotificationDeliveryService(notifications=repository)
        attempts = await delivery.deliver(
            notification_id=notifications[0].notification_id,
            transport=transport,
        )
        repeated = await delivery.deliver(
            notification_id=notifications[0].notification_id,
            transport=transport,
        )
        self.assertEqual(transport.calls, 1)
        self.assertEqual(attempts, repeated)
        self.assertEqual(attempts[-1].state, DeliveryState.DELIVERED)

    async def test_concurrent_calls_share_one_instance_claim_lock(self) -> None:
        _, opportunity, lifecycle, ranking, service, repository = (
            await _notification_fixture()
        )
        notifications = await service.create_intents(
            ranking,
            (opportunity,),
            (lifecycle,),
        )
        transport = _Transport()
        delivery = NotificationDeliveryService(notifications=repository)

        results = await asyncio.gather(
            delivery.deliver(
                notification_id=notifications[0].notification_id,
                transport=transport,
            ),
            delivery.deliver(
                notification_id=notifications[0].notification_id,
                transport=transport,
            ),
        )

        self.assertEqual(transport.calls, 1)
        self.assertEqual(results[0], results[1])

    async def test_retry_backoff_and_delivery_audit_are_durable(self) -> None:
        _, opportunity, lifecycle, ranking, service, repository = (
            await _notification_fixture()
        )
        notifications = await service.create_intents(
            ranking,
            (opportunity,),
            (lifecycle,),
        )
        self.assertEqual(len(notifications), 1)

        # The fixture's service already persisted the intent; use its stable
        # identifier and a deterministic fake clock for delivery orchestration.
        notification = notifications[0]
        now = datetime(2026, 10, 26, 17, 0, tzinfo=timezone.utc)
        sleeps: list[float] = []

        async def sleeper(delay: float) -> None:
            sleeps.append(delay)

        transport = _Transport(failures=2)
        delivery = NotificationDeliveryService(
            notifications=repository,
            clock=lambda: now,
            sleeper=sleeper,
        )
        attempts = await delivery.deliver(
            notification_id=notification.notification_id,
            transport=transport,
            max_attempts=3,
            base_backoff_seconds=0.25,
        )

        self.assertEqual(transport.calls, 3)
        self.assertEqual(sleeps, [0.25, 0.5])
        self.assertEqual(attempts[-1].state, DeliveryState.DELIVERED)
        self.assertEqual(attempts[-1].provider_reference, "provider.ref.3")
        self.assertEqual(len(attempts), 6)

        repeated = await delivery.deliver(
            notification_id=notification.notification_id,
            transport=transport,
            max_attempts=3,
        )
        self.assertEqual(transport.calls, 3)
        self.assertEqual(repeated, attempts)

