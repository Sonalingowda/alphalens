"""Fenced PostgreSQL notification delivery queue.

The queue is intentionally transport-neutral.  It owns durable job claims and
attempt audit; a provider adapter must be supplied by a separately authorized
caller.  Claims use row locks plus a lease token, and every completion is
fenced by worker identity and token so an expired worker cannot overwrite a
new owner.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


QUEUE_STATES = frozenset(
    {"PENDING", "CLAIMED", "RETRYABLE_FAILURE", "DELIVERED", "PERMANENT_FAILURE", "EXPIRED"}
)
TERMINAL_STATES = frozenset({"DELIVERED", "PERMANENT_FAILURE", "EXPIRED"})


class QueueError(RuntimeError):
    """Base queue error."""


class StaleWorkerError(QueueError):
    """The worker no longer owns the job lease."""


class QueueContractError(QueueError):
    """A queue argument or state transition is invalid."""


@dataclass(frozen=True, slots=True)
class DeliveryJob:
    job_id: str
    notification_id: str
    idempotency_key: str
    state: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime
    expires_at: datetime | None
    lease_owner: str | None
    lease_token: str | None
    lease_expires_at: datetime | None
    claim_version: int
    lease_expired_recoveries: int
    last_error: str | None
    provider_reference: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class QueueStats:
    pending: int
    active_leases: int
    retryable: int
    terminal_failures: int
    expired_lease_recoveries: int
    oldest_pending_age_seconds: float | None


class PostgreSQLNotificationQueue:
    """Durable queue with row-lock claims and lease-token fencing."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def enqueue(
        self,
        *,
        job_id: str,
        notification_id: str,
        idempotency_key: str,
        available_at: datetime | None = None,
        expires_at: datetime | None = None,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> DeliveryJob:
        now = _utc(now)
        available_at = _utc(available_at or now)
        if not job_id.strip() or not notification_id.strip() or not idempotency_key.strip():
            raise QueueContractError("Queue identities must not be empty.")
        if max_attempts <= 0:
            raise QueueContractError("Maximum attempts must be positive.")
        if expires_at is not None:
            expires_at = _utc(expires_at)
            if expires_at <= available_at:
                raise QueueContractError("Expiration must follow availability.")
        statement = text(
            """
            INSERT INTO notification_delivery_jobs
              (job_id, notification_id, idempotency_key, next_attempt_at,
               expires_at, max_attempts, created_at, updated_at)
            VALUES (:job_id, :notification_id, :idempotency_key, :next_attempt_at,
                    :expires_at, :max_attempts, :now, :now)
            ON CONFLICT (idempotency_key) DO UPDATE
              SET updated_at = notification_delivery_jobs.updated_at
            RETURNING *
            """
        )
        try:
            async with self._sessions.begin() as session:
                await session.execute(
                    text(
                        """
                        UPDATE notification_delivery_jobs
                        SET state = 'EXPIRED', lease_owner = NULL,
                            lease_token = NULL, lease_expires_at = NULL,
                            updated_at = :now
                        WHERE state IN ('PENDING', 'RETRYABLE_FAILURE')
                          AND expires_at IS NOT NULL AND expires_at <= :now
                        """
                    ),
                    {"now": now},
                )
                row = (
                    await session.execute(
                        statement,
                        {
                            "job_id": job_id,
                            "notification_id": notification_id,
                            "idempotency_key": idempotency_key,
                            "next_attempt_at": available_at,
                            "expires_at": expires_at,
                            "max_attempts": max_attempts,
                            "now": now,
                        },
                    )
                ).mappings().one()
        except SQLAlchemyError as error:
            raise QueueError("Notification queue enqueue failed.") from error
        return _job(row)

    async def claim(
        self,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> DeliveryJob | None:
        now = _utc(now)
        if not worker_id.strip() or lease_seconds <= 0:
            raise QueueContractError("Worker identity and lease duration are required.")
        token = uuid4().hex
        try:
            async with self._sessions.begin() as session:
                await session.execute(
                    text(
                        """
                        UPDATE notification_delivery_jobs
                        SET state = 'EXPIRED', lease_owner = NULL,
                            lease_token = NULL, lease_expires_at = NULL,
                            updated_at = :now
                        WHERE state IN ('PENDING', 'RETRYABLE_FAILURE')
                          AND expires_at IS NOT NULL AND expires_at <= :now
                        """
                    ),
                    {"now": now},
                )
                row = (
                    await session.execute(
                        text(
                            """
                            SELECT * FROM notification_delivery_jobs
                            WHERE (
                              (state IN ('PENDING', 'RETRYABLE_FAILURE')
                               AND next_attempt_at <= :now)
                              OR (state = 'CLAIMED' AND lease_expires_at <= :now)
                            )
                            AND (expires_at IS NULL OR expires_at > :now)
                            ORDER BY next_attempt_at, created_at, job_id
                            FOR UPDATE SKIP LOCKED
                            LIMIT 1
                            """
                        ),
                        {"now": now},
                    )
                ).mappings().first()
                if row is None:
                    return None
                recovering = row["state"] == "CLAIMED"
                updated = (
                    await session.execute(
                        text(
                            """
                            UPDATE notification_delivery_jobs
                            SET state = 'CLAIMED', lease_owner = :worker_id,
                                lease_token = :token,
                                lease_expires_at = :lease_expires_at,
                                attempt_count = attempt_count + 1,
                                claim_version = claim_version + 1,
                                lease_expired_recoveries = lease_expired_recoveries + :recovering,
                                updated_at = :now
                            WHERE job_id = :job_id
                            RETURNING *
                            """
                        ),
                        {
                            "worker_id": worker_id,
                            "token": token,
                            "lease_expires_at": now + timedelta(seconds=lease_seconds),
                            "recovering": int(recovering),
                            "now": now,
                            "job_id": row["job_id"],
                        },
                    )
                ).mappings().one()
        except SQLAlchemyError as error:
            raise QueueError("Notification queue claim failed.") from error
        return _job(updated)

    async def complete(
        self,
        *,
        job: DeliveryJob,
        worker_id: str,
        state: str,
        attempted_at: datetime | None = None,
        provider_reference: str | None = None,
        failure_category: str | None = None,
        next_attempt_at: datetime | None = None,
    ) -> DeliveryJob:
        attempted_at = _utc(attempted_at)
        if state not in {"DELIVERED", "RETRYABLE_FAILURE", "PERMANENT_FAILURE", "EXPIRED"}:
            raise QueueContractError("Completion state is not terminal or retryable.")
        if job.lease_token is None or job.lease_owner is None:
            raise QueueContractError("Job has no active lease.")
        if state == "RETRYABLE_FAILURE" and next_attempt_at is None:
            raise QueueContractError("Retryable failure requires a next attempt time.")
        if state in {"RETRYABLE_FAILURE", "PERMANENT_FAILURE"} and not failure_category:
            raise QueueContractError("Failure state requires a failure category.")
        attempt_id = f"{job.job_id}.{job.attempt_count}"
        try:
            async with self._sessions.begin() as session:
                current = (
                    await session.execute(
                        text("SELECT * FROM notification_delivery_jobs WHERE job_id = :job_id FOR UPDATE"),
                        {"job_id": job.job_id},
                    )
                ).mappings().one_or_none()
                if current is None:
                    raise QueueContractError("Delivery job does not exist.")
                if current["state"] in TERMINAL_STATES:
                    return _job(current)
                if current["state"] != "CLAIMED" or current["lease_owner"] != worker_id or current["lease_token"] != job.lease_token:
                    raise StaleWorkerError("Delivery lease is no longer owned by this worker.")
                await session.execute(
                    text(
                        """
                        INSERT INTO notification_delivery_attempts
                          (attempt_id, job_id, sequence, state, worker_id, lease_token,
                           attempted_at, provider_reference, failure_category)
                        VALUES (:attempt_id, :job_id, :sequence, :state, :worker_id,
                                :lease_token, :attempted_at, :provider_reference,
                                :failure_category)
                        ON CONFLICT (attempt_id) DO NOTHING
                        """
                    ),
                    {
                        "attempt_id": attempt_id,
                        "job_id": job.job_id,
                        "sequence": job.attempt_count,
                        "state": state,
                        "worker_id": worker_id,
                        "lease_token": job.lease_token,
                        "attempted_at": attempted_at,
                        "provider_reference": provider_reference,
                        "failure_category": failure_category,
                    },
                )
                updated = (
                    await session.execute(
                        text(
                            """
                            UPDATE notification_delivery_jobs
                            SET state = :state, lease_owner = NULL, lease_token = NULL,
                                lease_expires_at = NULL, next_attempt_at = :next_attempt_at,
                                last_error = :failure_category, provider_reference = :provider_reference,
                                updated_at = :attempted_at
                            WHERE job_id = :job_id AND state = 'CLAIMED'
                              AND lease_owner = :worker_id AND lease_token = :lease_token
                            RETURNING *
                            """
                        ),
                        {
                            "state": "PENDING" if state == "RETRYABLE_FAILURE" else state,
                            "next_attempt_at": next_attempt_at or attempted_at,
                            "failure_category": failure_category,
                            "provider_reference": provider_reference,
                            "attempted_at": attempted_at,
                            "job_id": job.job_id,
                            "worker_id": worker_id,
                            "lease_token": job.lease_token,
                        },
                    )
                ).mappings().one_or_none()
                if updated is None:
                    raise StaleWorkerError("Delivery lease was fenced during completion.")
        except (QueueContractError, StaleWorkerError):
            raise
        except SQLAlchemyError as error:
            raise QueueError("Notification queue completion failed.") from error
        return _job(updated)

    async def stats(self, *, now: datetime | None = None) -> QueueStats:
        now = _utc(now)
        try:
            async with self._sessions() as session:
                row = (
                    await session.execute(
                        text(
                            """
                            SELECT
                              count(*) FILTER (WHERE state = 'PENDING') AS pending,
                              count(*) FILTER (WHERE state = 'CLAIMED' AND lease_expires_at > :now) AS active_leases,
                              count(*) FILTER (WHERE state = 'RETRYABLE_FAILURE') AS retryable,
                              count(*) FILTER (WHERE state = 'PERMANENT_FAILURE') AS terminal_failures,
                              coalesce(sum(lease_expired_recoveries), 0) AS expired_lease_recoveries,
                              extract(epoch FROM (:now - min(created_at) FILTER (WHERE state = 'PENDING'))) AS oldest_pending_age_seconds
                            FROM notification_delivery_jobs
                            """
                        ),
                        {"now": now},
                    )
                ).mappings().one()
        except SQLAlchemyError as error:
            raise QueueError("Notification queue stats failed.") from error
        return QueueStats(
            pending=int(row["pending"] or 0),
            active_leases=int(row["active_leases"] or 0),
            retryable=int(row["retryable"] or 0),
            terminal_failures=int(row["terminal_failures"] or 0),
            expired_lease_recoveries=int(row["expired_lease_recoveries"] or 0),
            oldest_pending_age_seconds=(
                float(row["oldest_pending_age_seconds"])
                if row["oldest_pending_age_seconds"] is not None
                else None
            ),
        )


def _utc(value: datetime | None) -> datetime:
    resolved = value or datetime.now(timezone.utc)
    if resolved.tzinfo is None or resolved.utcoffset() is None:
        raise QueueContractError("Queue timestamps must be timezone-aware.")
    return resolved.astimezone(timezone.utc)


def _job(row) -> DeliveryJob:
    return DeliveryJob(**dict(row))

