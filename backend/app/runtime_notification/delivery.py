"""Audited notification delivery orchestration.

This module deliberately stops at a transport interface.  It records durable
delivery attempts through the existing append-only repository and is suitable
for isolated test transports.  It does not configure or invoke an external
provider by itself.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol

from app.opportunity_intelligence.domain import (
    DeliveryAttempt,
    DeliveryState,
    Notification,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
    HistoryQuery,
    NotificationRepository,
)


class NotificationTransport(Protocol):
    """Isolated or externally implemented notification transport."""

    async def send(self, notification: Notification) -> str:
        """Deliver one intent and return a provider reference."""
        ...


class RetryableDeliveryError(RuntimeError):
    """Transport failure that may be retried."""


class PermanentDeliveryError(RuntimeError):
    """Transport failure that must not be retried."""


Clock = Callable[[], datetime]
Sleeper = Callable[[float], Awaitable[None]]


class NotificationDeliveryService:
    """Deliver one persisted intent with durable, audited retry attempts.

    The repository remains the source of truth.  A repeated call after a
    terminal attempt performs no transport call.  The lock prevents duplicate
    work within this service instance; cross-process claiming still requires a
    queue/lease contract and is intentionally not claimed here.
    """

    def __init__(
        self,
        *,
        notifications: NotificationRepository,
        clock: Clock | None = None,
        sleeper: Sleeper = asyncio.sleep,
    ) -> None:
        self._notifications = notifications
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sleeper = sleeper
        self._locks: dict[str, asyncio.Lock] = {}

    async def deliver(
        self,
        *,
        notification_id: str,
        transport: NotificationTransport,
        max_attempts: int = 3,
        base_backoff_seconds: float = 1.0,
    ) -> tuple[DeliveryAttempt, ...]:
        """Deliver one intent, returning its complete persisted attempt audit."""
        if not notification_id.strip():
            raise ValueError("Notification identifier must not be empty.")
        if max_attempts <= 0:
            raise ValueError("Maximum delivery attempts must be positive.")
        if base_backoff_seconds < 0:
            raise ValueError("Delivery backoff must not be negative.")
        if not callable(getattr(transport, "send", None)):
            raise TypeError("Notification transport must provide send().")

        lock = self._locks.setdefault(notification_id, asyncio.Lock())
        async with lock:
            notification = await self._notifications.get_by_id(
                EntityId(notification_id)
            )
            now = self._clock()
            attempts = await self._history(notification_id, now)
            if attempts and attempts[-1].state in {
                DeliveryState.DELIVERED,
                DeliveryState.PERMANENT_FAILURE,
                DeliveryState.EXPIRED,
            }:
                return attempts
            if notification.expires_at is not None and notification.expires_at <= now:
                return await self._append(
                    notification_id,
                    attempts,
                    state=DeliveryState.EXPIRED,
                    attempted_at=now,
                    failure_category="notification_expired",
                )

            for delivery_number in range(1, max_attempts + 1):
                attempts = await self._append(
                    notification_id,
                    attempts,
                    state=DeliveryState.IN_FLIGHT,
                    attempted_at=self._clock(),
                )
                try:
                    provider_reference = await transport.send(notification)
                    if not isinstance(provider_reference, str) or not provider_reference.strip():
                        raise PermanentDeliveryError(
                            "Transport returned an empty provider reference."
                        )
                except PermanentDeliveryError as error:
                    return await self._append(
                        notification_id,
                        attempts,
                        state=DeliveryState.PERMANENT_FAILURE,
                        attempted_at=self._clock(),
                        failure_category=_failure_category(error),
                    )
                except Exception as error:  # noqa: BLE001 - transport boundary
                    attempts = await self._append(
                        notification_id,
                        attempts,
                        state=(
                            DeliveryState.PERMANENT_FAILURE
                            if delivery_number == max_attempts
                            else DeliveryState.RETRYABLE_FAILURE
                        ),
                        attempted_at=self._clock(),
                        failure_category=_failure_category(error),
                    )
                    if delivery_number == max_attempts:
                        return attempts
                    await self._sleeper(base_backoff_seconds * (2 ** (delivery_number - 1)))
                    continue
                return await self._append(
                    notification_id,
                    attempts,
                    state=DeliveryState.DELIVERED,
                    attempted_at=self._clock(),
                    provider_reference=provider_reference,
                )
            return attempts

    async def _history(
        self,
        notification_id: str,
        as_of: datetime,
    ) -> tuple[DeliveryAttempt, ...]:
        try:
            page = await self._notifications.delivery_history(
                HistoryQuery(
                    entity_id=EntityId(notification_id),
                    as_of=as_of,
                    limit=500,
                )
            )
        except EntityNotFoundError:
            return ()
        return page.items

    async def _append(
        self,
        notification_id: str,
        attempts: tuple[DeliveryAttempt, ...],
        *,
        state: DeliveryState,
        attempted_at: datetime,
        provider_reference: str | None = None,
        failure_category: str | None = None,
    ) -> tuple[DeliveryAttempt, ...]:
        sequence = len(attempts) + 1
        attempt = DeliveryAttempt(
            attempt_id=f"delivery.{notification_id}.{sequence}",
            sequence=sequence,
            state=state,
            attempted_at=attempted_at,
            provider_reference=provider_reference,
            failure_category=failure_category,
        )
        stored = await self._notifications.save_delivery_attempt(
            EntityId(notification_id), attempt
        )
        return (*attempts, stored)


def _failure_category(error: BaseException) -> str:
    return f"transport_{type(error).__name__.lower()}"

