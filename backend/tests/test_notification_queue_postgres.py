"""PostgreSQL multi-worker queue tests; run with an isolated queue database."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.runtime_notification import (
    PostgreSQLNotificationQueue,
    StaleWorkerError,
)


DATABASE_URL = os.getenv("ALPHALENS_QUEUE_DATABASE_URL")


def _now() -> datetime:
    return datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)


@unittest.skipUnless(
    DATABASE_URL,
    "requires an explicitly isolated PostgreSQL queue database",
)
class NotificationQueuePostgreSQLTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine(DATABASE_URL)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.queue = PostgreSQLNotificationQueue(self.sessions)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def test_concurrent_workers_have_one_valid_claim(self) -> None:
        first = PostgreSQLNotificationQueue(self.sessions)
        second = PostgreSQLNotificationQueue(self.sessions)
        await first.enqueue(
            job_id="job.concurrent",
            notification_id="notification.concurrent",
            idempotency_key="notification.concurrent.v1",
            now=_now(),
        )
        claims = await asyncio.gather(
            first.claim(worker_id="worker-a", lease_seconds=60, now=_now()),
            second.claim(worker_id="worker-b", lease_seconds=60, now=_now()),
        )
        self.assertEqual(sum(claim is not None for claim in claims), 1)

    async def test_expired_lease_recovery_fences_stale_worker(self) -> None:
        now = _now()
        await self.queue.enqueue(
            job_id="job.recovery",
            notification_id="notification.recovery",
            idempotency_key="notification.recovery.v1",
            now=now,
        )
        stale = await self.queue.claim(worker_id="worker-old", lease_seconds=1, now=now)
        self.assertIsNotNone(stale)
        recovered = await self.queue.claim(
            worker_id="worker-new",
            lease_seconds=60,
            now=now + timedelta(seconds=2),
        )
        self.assertIsNotNone(recovered)
        with self.assertRaises(StaleWorkerError):
            await self.queue.complete(
                job=stale,
                worker_id="worker-old",
                state="DELIVERED",
                attempted_at=now + timedelta(seconds=2),
                provider_reference="provider.stale",
            )
        delivered = await self.queue.complete(
            job=recovered,
            worker_id="worker-new",
            state="DELIVERED",
            attempted_at=now + timedelta(seconds=2),
            provider_reference="provider.new",
        )
        self.assertEqual(delivered.state, "DELIVERED")
        self.assertEqual(delivered.lease_expired_recoveries, 1)

    async def test_retry_then_permanent_failure_and_terminal_idempotency(self) -> None:
        now = _now()
        await self.queue.enqueue(
            job_id="job.retry",
            notification_id="notification.retry",
            idempotency_key="notification.retry.v1",
            max_attempts=2,
            now=now,
        )
        first = await self.queue.claim(worker_id="worker-a", now=now)
        self.assertIsNotNone(first)
        pending = await self.queue.complete(
            job=first,
            worker_id="worker-a",
            state="RETRYABLE_FAILURE",
            attempted_at=now,
            failure_category="provider_timeout",
            next_attempt_at=now + timedelta(seconds=10),
        )
        self.assertEqual(pending.state, "PENDING")
        self.assertIsNone(await self.queue.claim(worker_id="worker-a", now=now + timedelta(seconds=5)))
        second = await self.queue.claim(worker_id="worker-b", now=now + timedelta(seconds=10))
        self.assertIsNotNone(second)
        terminal = await self.queue.complete(
            job=second,
            worker_id="worker-b",
            state="PERMANENT_FAILURE",
            attempted_at=now + timedelta(seconds=10),
            failure_category="retry_exhausted",
        )
        self.assertEqual(terminal.state, "PERMANENT_FAILURE")
        duplicate = await self.queue.complete(
            job=second,
            worker_id="worker-b",
            state="PERMANENT_FAILURE",
            attempted_at=now + timedelta(seconds=11),
            failure_category="retry_exhausted",
        )
        self.assertEqual(duplicate.state, "PERMANENT_FAILURE")

    async def test_expired_pending_job_is_terminal_and_visible(self) -> None:
        now = _now()
        await self.queue.enqueue(
            job_id="job.expired",
            notification_id="notification.expired",
            idempotency_key="notification.expired.v1",
            expires_at=now + timedelta(seconds=1),
            now=now,
        )
        self.assertIsNone(await self.queue.claim(worker_id="worker-a", now=now + timedelta(seconds=2)))
        stats = await self.queue.stats(now=now + timedelta(seconds=2))
        self.assertEqual(stats.pending, 0)
        self.assertEqual(stats.terminal_failures, 0)

