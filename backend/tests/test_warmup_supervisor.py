"""Tests for the periodic startup-warmup retry/backoff supervisor."""

import asyncio
from unittest import IsolatedAsyncioTestCase

from app.prediction_api import _supervise_warmup


class _FlakyService:
    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.call_count = 0

    async def warmup_history_with_retry(
        self, *, attempts: int = 3, backoff_seconds: float = 15.0
    ):
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise ConnectionError(f"simulated failure #{self.call_count}")
        return 42


class WarmupSupervisorTests(IsolatedAsyncioTestCase):
    async def test_supervisor_retries_and_backs_off(self) -> None:
        recorded_delays = []
        stop_event = asyncio.Event()

        async def fake_sleep(seconds):
            recorded_delays.append(seconds)
            if len(recorded_delays) >= 3:
                stop_event.set()

        service = _FlakyService(fail_times=2)
        task = asyncio.create_task(
            _supervise_warmup(
                stop_event, service, interval_seconds=1, sleep_fn=fake_sleep
            )
        )
        await asyncio.wait_for(task, timeout=2.0)

        self.assertGreaterEqual(
            service.call_count, 3, f"got {service.call_count}"
        )
        self.assertGreaterEqual(
            len(recorded_delays), 3, f"got {recorded_delays}"
        )
