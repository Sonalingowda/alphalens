"""Single-owner protection for the local live-candle worker."""

from pathlib import Path
import tempfile
import unittest

from scripts.local_market_worker import WorkerOwnershipError, WorkerOwnershipLock


class WorkerOwnershipTests(unittest.TestCase):
    def test_second_worker_cannot_acquire_same_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            first = WorkerOwnershipLock(checkpoint)
            second = WorkerOwnershipLock(checkpoint)
            first.acquire()
            try:
                with self.assertRaises(WorkerOwnershipError):
                    second.acquire()
            finally:
                first.release()

            second.acquire()
            second.release()

