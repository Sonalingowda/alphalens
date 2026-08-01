"""Production lifecycle entry point for policy-neutral background workers."""

import asyncio
import logging
import signal

from app.infrastructure.redis import RedisInfrastructure
from app.infrastructure.workers import BackgroundWorker, WorkerConfiguration
from app.observability.logging import configure_structured_logging
from app.settings import load_settings


logger = logging.getLogger("alphalens.worker")


async def _reject_unconfigured_task(task_reference: str) -> None:
    raise RuntimeError(
        f"No approved infrastructure handler is registered for {task_reference!r}."
    )


async def run_worker() -> None:
    settings = load_settings()
    configure_structured_logging(settings.log_level)
    coordination = RedisInfrastructure.from_url(settings.redis_url)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop_event.set)
    workers = tuple(
        BackgroundWorker(
            coordination=coordination,
            configuration=WorkerConfiguration(
                queue="infrastructure",
                worker_id=f"worker.{index + 1}",
                poll_seconds=settings.worker_poll_seconds,
                max_retries=settings.worker_max_retries,
            ),
            handler=_reject_unconfigured_task,
        )
        for index in range(settings.worker_concurrency)
    )
    try:
        async with asyncio.TaskGroup() as tasks:
            for worker in workers:
                tasks.create_task(worker.run(stop_event))
    finally:
        await coordination.close()
        logger.info("background_worker_stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
