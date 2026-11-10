from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.live_market_data.warmup import (
    AcceptedWarmupCheckpoint,
    AcceptedWarmupCheckpointStore,
    WarmupBatchIntegrityError,
    build_warmup_batch,
    reconcile_warmup_checkpoint,
    validate_warmup_batch,
)


START = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
NOW = START + timedelta(hours=1)


def _rows(count: int = 240) -> list[list[object]]:
    base = START - timedelta(minutes=5 * count)
    result = []
    for index in range(count):
        opened = base + timedelta(minutes=5 * index)
        result.append([
            int(opened.timestamp() * 1000),
            "100.00000000", "112.00000000", "95.00000000", "108.00000000",
            "2.50000000",
            int((opened + timedelta(minutes=5) - timedelta(milliseconds=1)).timestamp() * 1000),
            "42.00000000", 42, "21.00000000", "20.00000000", "0",
        ])
    return result


def _batch(rows: list[list[object]]):
    count = len(rows)
    return build_warmup_batch(
        lineage_id="recovery-20261110-a",
        rows=rows,
        requested_start=START - timedelta(minutes=5 * count),
        requested_end_exclusive=START,
        retrieved_at=NOW,
        code_version="test-code",
        request_parameters={"symbol": "BTCUSDT", "interval": "5m", "limit": count},
        now=NOW,
    )


class BinanceWarmupManifestTests(unittest.TestCase):
    def test_exact_240_is_contiguous_and_valid(self) -> None:
        batch = _batch(_rows())
        self.assertEqual(batch.candle_count, 240)
        validate_warmup_batch(batch)

    def test_short_open_misaligned_and_missing_inputs_fail_closed(self) -> None:
        with self.assertRaises(WarmupBatchIntegrityError):
            _batch(_rows(199))

        open_rows = _rows()
        open_rows[-1][6] = int((NOW + timedelta(minutes=5)).timestamp() * 1000)
        with self.assertRaises(WarmupBatchIntegrityError):
            _batch(open_rows)

        misaligned = _rows()
        misaligned[10][0] += 1
        with self.assertRaises(WarmupBatchIntegrityError):
            _batch(misaligned)

        missing = _rows()
        del missing[100]
        with self.assertRaises(WarmupBatchIntegrityError):
            _batch(missing)

    def test_duplicate_and_manifest_hash_conflicts_fail_closed(self) -> None:
        duplicate = _rows()
        duplicate[100] = duplicate[99].copy()
        with self.assertRaises(WarmupBatchIntegrityError):
            _batch(duplicate)

        from dataclasses import replace
        batch = _batch(_rows())
        with self.assertRaises(WarmupBatchIntegrityError):
            validate_warmup_batch(replace(batch, source_response_hash="0" * 64))

    def test_checkpoint_reconciles_db_authority_and_rejects_orphans(self) -> None:
        checkpoint = AcceptedWarmupCheckpoint(
            batch_id=_batch(_rows()).batch_id,
            lineage_id="recovery-20261110-a",
            membership_hash=_batch(_rows()).membership_hash,
            updated_at=NOW,
        )
        with TemporaryDirectory() as directory:
            store = AcceptedWarmupCheckpointStore(Path(directory) / "warmup.json")
            self.assertEqual(reconcile_warmup_checkpoint(store, checkpoint), checkpoint)
            self.assertEqual(store.load(), checkpoint)
            store.path.write_text('{"batch_id":"00000000-0000-0000-0000-000000000000"}')
            with self.assertRaises(WarmupBatchIntegrityError):
                reconcile_warmup_checkpoint(store, checkpoint)


if __name__ == "__main__":
    unittest.main()
