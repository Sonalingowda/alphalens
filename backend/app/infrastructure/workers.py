"""Policy-neutral scheduler and background worker lifecycle."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

from app.infrastructure.redis import RedisInfrastructure


TaskHandler = Callable[[str], Awaitable[None]]
logger = logging.getLogger("alphalens.worker")


@dataclass(frozen=True, slots=True)
class WorkerConfiguration:
    queue: str
    worker_id: str
    poll_seconds: float
    max_retries: int
    heartbeat_ttl_seconds: int = 30

    def __post_init__(self) -> None:
        if not self.queue or not self.worker_id:
            raise ValueError("Worker queue and identity are required.")
        if self.poll_seconds <= 0 or self.max_retries < 0:
            raise ValueError("Worker retry configuration is invalid.")


class BackgroundWorker:
    """Consume task references only; task behavior is injected by type."""

    def __init__(
        self,
        *,
        coordination: RedisInfrastructure,
        configuration: WorkerConfiguration,
        handler: TaskHandler,
    ) -> None:
        self._coordination = coordination
        self._configuration = configuration
        self._handler = handler

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._coordination.heartbeat(
                self._configuration.worker_id,
                ttl_seconds=self._configuration.heartbeat_ttl_seconds,
            )
            task_reference = await self._coordination.dequeue(
                self._configuration.queue,
                timeout_seconds=max(int(self._configuration.poll_seconds), 1),
            )
            if task_reference is None:
                continue
            await self._execute_with_retry(task_reference, stop_event)

    async def _execute_with_retry(
        self, task_reference: str, stop_event: asyncio.Event
    ) -> None:
        for attempt in range(self._configuration.max_retries + 1):
            if stop_event.is_set():
                return
            try:
                await self._handler(task_reference)
                logger.info(
                    "background_task_completed",
                    extra={"task_reference": task_reference, "attempt": attempt + 1},
                )
                return
            except Exception:
                logger.exception(
                    "background_task_failed",
                    extra={"task_reference": task_reference, "attempt": attempt + 1},
                )
                if attempt == self._configuration.max_retries:
                    raise
                await _wait_or_stop(
                    stop_event,
                    self._configuration.poll_seconds * (2**attempt),
                )


class InfrastructureScheduler:
    """Schedule pre-existing task references without interpreting their content."""

    def __init__(self, coordination: RedisInfrastructure) -> None:
        self._coordination = coordination

    async def schedule(
        self,
        *,
        queue: str,
        task_reference: str,
        not_before: datetime,
    ) -> None:
        if (
            not_before.tzinfo is None
            or not_before.utcoffset() != timezone.utc.utcoffset(not_before)
        ):
            raise ValueError("Scheduled time must use UTC.")
        delay = max((not_before - datetime.now(timezone.utc)).total_seconds(), 0)
        if delay:
            await asyncio.sleep(delay)
        await self._coordination.enqueue(queue, task_reference)


async def _wait_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except TimeoutError:
        return
