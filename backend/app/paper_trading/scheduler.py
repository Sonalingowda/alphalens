"""Configurable cooperative scheduler for paper prediction cycles."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class PredictionScheduler:
    interval_seconds: int

    def __post_init__(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("Scheduler interval must be positive.")

    def next_run_after(self, completed_at: datetime) -> datetime:
        if completed_at.tzinfo is None or completed_at.utcoffset() is None:
            raise ValueError("Scheduler timestamps must be timezone-aware.")
        return completed_at + timedelta(seconds=self.interval_seconds)

    async def run(
        self,
        cycle: Callable[[], Awaitable[object]],
        stop_event: asyncio.Event,
    ) -> None:
        while not stop_event.is_set():
            await cycle()
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                continue
