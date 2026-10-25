"""Fixture-only reliability tests for the separately identified collector."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.section6_replacement_collector import (
    CANDLE_MS,
    CollectorState,
    CollectorValidationError,
    DEVELOPMENT_END_MS,
    FilesystemCollectorStore,
    PROTECTED_TEST_START_MS,
    append_response,
    checkpoint_document,
    decode_checkpoint,
    parse_engineering_fixture,
)


def engineering_candle(open_ms: int, *, closed: bool = True) -> dict:
    """Synthetic data only; this fixture is not historical market evidence."""

    return {
        "fixture_identity": "engineering-only-section6-replacement-v1",
        "stream": "btcusdt@kline_5m",
        "data": {
            "e": "kline",
            "E": open_ms + 299000,
            "s": "BTCUSDT",
            "k": {
                "t": open_ms,
                "T": open_ms + 299999,
                "s": "BTCUSDT",
                "i": "5m",
                "o": "100.00000000",
                "c": "101.00000000",
                "h": "102.00000000",
                "l": "99.00000000",
                "v": "10.00000000",
                "n": 3,
                "x": closed,
            },
        },
    }


class Section6ReplacementCollectorTests(unittest.TestCase):
    def test_fixture_requires_explicit_engineering_identity(self) -> None:
        fixture = engineering_candle(1_760_328_000_000)
        candle, raw_bytes = parse_engineering_fixture(fixture)
        self.assertTrue(candle.closed)
        self.assertGreater(len(raw_bytes), 0)
        fixture.pop("fixture_identity")
        with self.assertRaisesRegex(CollectorValidationError, "labeled engineering"):
            parse_engineering_fixture(fixture)

    def test_append_is_deterministic_and_checkpoint_round_trips(self) -> None:
        state = append_response(CollectorState(), engineering_candle(1_760_328_000_000))
        state = append_response(state, engineering_candle(1_760_328_000_000 + CANDLE_MS))
        checkpoint = checkpoint_document(state)
        self.assertEqual(checkpoint, checkpoint_document(decode_checkpoint(checkpoint)))
        self.assertEqual(state.checkpoint_sequence, 2)

    def test_exact_duplicate_is_idempotent(self) -> None:
        document = engineering_candle(1_760_328_000_000)
        state = append_response(CollectorState(), document)
        self.assertEqual(state, append_response(state, deepcopy(document)))

    def test_conflicting_duplicate_fails_closed(self) -> None:
        document = engineering_candle(1_760_328_000_000)
        state = append_response(CollectorState(), document)
        conflict = deepcopy(document)
        conflict["data"]["k"]["c"] = "100.50000000"
        with self.assertRaisesRegex(CollectorValidationError, "Conflicting duplicate"):
            append_response(state, conflict)

    def test_gap_fails_closed(self) -> None:
        state = append_response(CollectorState(), engineering_candle(1_760_328_000_000))
        with self.assertRaisesRegex(CollectorValidationError, "gap or reordering"):
            append_response(state, engineering_candle(1_760_328_000_000 + 2 * CANDLE_MS))

    def test_open_candle_and_protected_boundary_fail_closed(self) -> None:
        with self.assertRaisesRegex(CollectorValidationError, "Only closed"):
            append_response(CollectorState(), engineering_candle(1_760_328_000_000, closed=False))
        with self.assertRaisesRegex(CollectorValidationError, "protected-test"):
            append_response(CollectorState(), engineering_candle(PROTECTED_TEST_START_MS))

    def test_development_end_is_inclusive(self) -> None:
        state = append_response(CollectorState(), engineering_candle(DEVELOPMENT_END_MS))
        self.assertEqual(state.last_open_ms, DEVELOPMENT_END_MS)

    def test_checkpoint_tampering_fails_closed(self) -> None:
        checkpoint = checkpoint_document(
            append_response(CollectorState(), engineering_candle(1_760_328_000_000))
        )
        checkpoint["checkpoint_sequence"] = 99
        with self.assertRaisesRegex(CollectorValidationError, "Checkpoint hash"):
            decode_checkpoint(checkpoint)

    def test_filesystem_store_recovers_after_latest_checkpoint_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemCollectorStore(Path(directory))
            first = store.commit(CollectorState(), engineering_candle(1_760_328_000_000))
            store.commit(first, engineering_candle(1_760_328_000_000 + CANDLE_MS))
            store.latest_path.write_text("{not-json", encoding="utf-8")
            recovered = store.recover()
            self.assertEqual(recovered.checkpoint_sequence, 2)

    def test_filesystem_store_rejects_interrupted_checkpoint_and_uses_prior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemCollectorStore(Path(directory))
            first = store.commit(CollectorState(), engineering_candle(1_760_328_000_000))
            second = store.checkpoint_path(2)
            second.write_bytes(b"partial")
            store.latest_path.write_bytes(b"partial")
            recovered = store.recover()
            self.assertEqual(recovered.checkpoint_sequence, first.checkpoint_sequence)

    def test_filesystem_store_enforces_path_safety_and_raw_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FilesystemCollectorStore(Path(directory))
            state = store.commit(CollectorState(), engineering_candle(1_760_328_000_000))
            raw_hash = state.raw_response_hashes[0]
            self.assertEqual(json.loads(store.raw_path(raw_hash).read_bytes())["fixture_identity"], "engineering-only-section6-replacement-v1")
            with self.assertRaisesRegex(CollectorValidationError, "Unsafe"):
                store.raw_path("../outside")
            with self.assertRaisesRegex(CollectorValidationError, "Unsafe"):
                store.raw_path("a" * 63)


if __name__ == "__main__":
    unittest.main()
