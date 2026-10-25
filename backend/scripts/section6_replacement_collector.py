"""Offline Section 6 replacement collector primitives and filesystem store.

This module is deliberately separate from the missing historical collector. It
does not perform network I/O, scheduling, launchd integration, acquisition, or
training. The filesystem store is a durable offline component for explicitly
supplied engineering fixtures only.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping


REPLACEMENT_IDENTITY = "section6-replacement-collector.v1"
SYMBOL = "BTCUSDT"
INTERVAL = "5m"
CANDLE_MS = 5 * 60 * 1000
CANDLE_END_OFFSET_MS = CANDLE_MS - 1
DEVELOPMENT_START_MS = 1_760_328_000_000
DEVELOPMENT_END_MS = 1_799_596_500_000
PROTECTED_TEST_START_MS = 1_799_596_800_000
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class CollectorValidationError(ValueError):
    """Raised when a response, checkpoint, or storage path is invalid."""


def canonical_json(value: object) -> bytes:
    """Encode JSON deterministically for raw-response and state hashes."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _finite_number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CollectorValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise CollectorValidationError(f"{field} must be finite")
    return number


@dataclass(frozen=True)
class Candle:
    open_ms: int
    close_ms: int
    symbol: str
    interval: str
    open_price: str
    high_price: str
    low_price: str
    close_price: str
    volume: str
    closed: bool

    def canonical(self) -> dict[str, object]:
        return {
            "open_ms": self.open_ms,
            "close_ms": self.close_ms,
            "symbol": self.symbol,
            "interval": self.interval,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "closed": self.closed,
        }


@dataclass(frozen=True)
class CollectorState:
    identity: str = REPLACEMENT_IDENTITY
    baseline_id: str = "new-provenance-baseline-pending"
    symbol: str = SYMBOL
    interval: str = INTERVAL
    development_start_ms: int = DEVELOPMENT_START_MS
    development_end_ms: int = DEVELOPMENT_END_MS
    protected_test_start_ms: int = PROTECTED_TEST_START_MS
    candles: tuple[Candle, ...] = ()
    raw_response_hashes: tuple[str, ...] = ()
    checkpoint_sequence: int = 0

    @property
    def last_open_ms(self) -> int | None:
        return self.candles[-1].open_ms if self.candles else None

    def canonical(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "baseline_id": self.baseline_id,
            "symbol": self.symbol,
            "interval": self.interval,
            "development_start_ms": self.development_start_ms,
            "development_end_ms": self.development_end_ms,
            "protected_test_start_ms": self.protected_test_start_ms,
            "candles": [candle.canonical() for candle in self.candles],
            "raw_response_hashes": list(self.raw_response_hashes),
            "checkpoint_sequence": self.checkpoint_sequence,
        }


def parse_engineering_fixture(document: Mapping[str, Any]) -> tuple[Candle, bytes]:
    """Parse one explicitly labeled Binance-shaped engineering fixture."""

    if document.get("fixture_identity") != "engineering-only-section6-replacement-v1":
        raise CollectorValidationError("Only labeled engineering fixtures are accepted")
    try:
        payload = document["data"]["k"]
        raw_bytes = canonical_json(document)
        candle = Candle(
            open_ms=int(payload["t"]),
            close_ms=int(payload["T"]),
            symbol=str(payload["s"]),
            interval=str(payload["i"]),
            open_price=str(payload["o"]),
            high_price=str(payload["h"]),
            low_price=str(payload["l"]),
            close_price=str(payload["c"]),
            volume=str(payload["v"]),
            closed=bool(payload["x"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CollectorValidationError("Malformed kline envelope") from exc
    return candle, raw_bytes


def validate_candle(candle: Candle, state: CollectorState) -> None:
    if candle.symbol != state.symbol or candle.interval != state.interval:
        raise CollectorValidationError("Candle scope does not match state scope")
    if not candle.closed:
        raise CollectorValidationError("Only closed candles are accepted")
    if candle.close_ms != candle.open_ms + CANDLE_END_OFFSET_MS:
        raise CollectorValidationError("Candle close boundary is invalid")
    if candle.open_ms >= state.protected_test_start_ms:
        raise CollectorValidationError("Candle reaches protected-test boundary")
    if not state.development_start_ms <= candle.open_ms <= state.development_end_ms:
        raise CollectorValidationError("Candle is outside development boundary")

    prices = (
        _finite_number(candle.open_price, "open_price"),
        _finite_number(candle.high_price, "high_price"),
        _finite_number(candle.low_price, "low_price"),
        _finite_number(candle.close_price, "close_price"),
    )
    volume = _finite_number(candle.volume, "volume")
    if min(prices) <= 0 or volume < 0:
        raise CollectorValidationError("Candle prices must be positive and volume nonnegative")
    if prices[1] < max(prices[0], prices[3]) or prices[2] > min(prices[0], prices[3]):
        raise CollectorValidationError("Candle OHLC ordering is invalid")


def append_response(state: CollectorState, document: Mapping[str, Any]) -> CollectorState:
    """Validate one response and return the next deterministic state."""

    candle, raw_bytes = parse_engineering_fixture(document)
    del raw_bytes
    validate_candle(candle, state)
    existing = next((item for item in state.candles if item.open_ms == candle.open_ms), None)
    if existing is not None:
        if existing != candle:
            raise CollectorValidationError("Conflicting duplicate timestamp")
        return state
    if state.candles:
        expected = state.candles[-1].open_ms + CANDLE_MS
        if candle.open_ms != expected:
            raise CollectorValidationError("Candle timestamp gap or reordering detected")
    response_hash = sha256_hex(canonical_json(document))
    return replace(
        state,
        candles=(*state.candles, candle),
        raw_response_hashes=(*state.raw_response_hashes, response_hash),
        checkpoint_sequence=state.checkpoint_sequence + 1,
    )


def checkpoint_document(state: CollectorState) -> dict[str, object]:
    body = state.canonical()
    return {**body, "state_sha256": sha256_hex(canonical_json(body))}


def encode_checkpoint(state: CollectorState) -> bytes:
    return canonical_json(checkpoint_document(state))


def decode_checkpoint(document: Mapping[str, Any]) -> CollectorState:
    supplied_hash = document.get("state_sha256")
    body = {key: value for key, value in document.items() if key != "state_sha256"}
    if supplied_hash != sha256_hex(canonical_json(body)):
        raise CollectorValidationError("Checkpoint hash mismatch")
    if body.get("identity") != REPLACEMENT_IDENTITY:
        raise CollectorValidationError("Checkpoint identity mismatch")
    try:
        candles = tuple(Candle(**item) for item in body["candles"])
        return CollectorState(
            identity=body["identity"],
            baseline_id=body["baseline_id"],
            symbol=body["symbol"],
            interval=body["interval"],
            development_start_ms=body["development_start_ms"],
            development_end_ms=body["development_end_ms"],
            protected_test_start_ms=body["protected_test_start_ms"],
            candles=candles,
            raw_response_hashes=tuple(body["raw_response_hashes"]),
            checkpoint_sequence=body["checkpoint_sequence"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CollectorValidationError("Malformed checkpoint") from exc


class FilesystemCollectorStore:
    """Atomic raw-response/checkpoint store for offline engineering fixtures."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_root = root / "raw"
        self.checkpoint_root = root / "checkpoints"
        self.latest_path = root / "checkpoint.json"
        for path in (self.raw_root, self.checkpoint_root):
            path.mkdir(parents=True, exist_ok=True)

    def _safe_hash_path(self, root: Path, value: str) -> Path:
        if not _HASH_RE.fullmatch(value):
            raise CollectorValidationError("Unsafe storage identifier")
        original = root / f"{value}.json"
        if original.is_symlink():
            raise CollectorValidationError("Symlinked storage path is not allowed")
        candidate = original.resolve()
        if root.resolve() not in candidate.parents:
            raise CollectorValidationError("Storage path escapes root")
        return candidate

    def raw_path(self, response_hash: str) -> Path:
        return self._safe_hash_path(self.raw_root, response_hash)

    def checkpoint_path(self, sequence: int) -> Path:
        if sequence < 1:
            raise CollectorValidationError("Checkpoint sequence must be positive")
        return self._safe_hash_path(self.checkpoint_root, f"{sequence:064x}")

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def commit(self, state: CollectorState, document: Mapping[str, Any]) -> CollectorState:
        """Persist raw bytes before the corresponding checkpoint atomically."""

        next_state = append_response(state, document)
        _, raw_bytes = parse_engineering_fixture(document)
        response_hash = sha256_hex(raw_bytes)
        raw_path = self.raw_path(response_hash)
        if raw_path.exists() and raw_path.read_bytes() != raw_bytes:
            raise CollectorValidationError("Raw response hash collision or tampering")
        if not raw_path.exists():
            self._atomic_write(raw_path, raw_bytes)
        if next_state == state:
            return state
        checkpoint_bytes = encode_checkpoint(next_state)
        self._atomic_write(self.checkpoint_path(next_state.checkpoint_sequence), checkpoint_bytes)
        self._atomic_write(self.latest_path, checkpoint_bytes)
        return next_state

    @staticmethod
    def _read_regular_file(path: Path) -> bytes:
        if path.is_symlink() or not path.is_file():
            raise CollectorValidationError("Storage file is not a regular file")
        return path.read_bytes()

    def _raw_response_is_intact(self, response_hash: str) -> bool:
        try:
            raw_path = self.raw_path(response_hash)
            raw_bytes = self._read_regular_file(raw_path)
        except (OSError, CollectorValidationError):
            return False
        return sha256_hex(raw_bytes) == response_hash

    def _valid_checkpoint(self, path: Path) -> CollectorState | None:
        try:
            state = decode_checkpoint(json.loads(self._read_regular_file(path)))
            if any(not self._raw_response_is_intact(item) for item in state.raw_response_hashes):
                return None
            return state
        except (OSError, ValueError, json.JSONDecodeError, CollectorValidationError):
            return None

    def recover(self) -> CollectorState:
        """Recover the newest complete checkpoint after interruption/corruption."""

        candidates: list[CollectorState] = []
        if self.latest_path.exists():
            state = self._valid_checkpoint(self.latest_path)
            if state is not None:
                candidates.append(state)
        for path in self.checkpoint_root.glob("*.json"):
            state = self._valid_checkpoint(path)
            if state is not None:
                candidates.append(state)
        if not candidates:
            return CollectorState()
        return max(candidates, key=lambda state: state.checkpoint_sequence)


def timestamp_iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


__all__ = [
    "CANDLE_MS",
    "CollectorState",
    "CollectorValidationError",
    "DEVELOPMENT_END_MS",
    "DEVELOPMENT_START_MS",
    "FilesystemCollectorStore",
    "INTERVAL",
    "PROTECTED_TEST_START_MS",
    "REPLACEMENT_IDENTITY",
    "SYMBOL",
    "append_response",
    "canonical_json",
    "checkpoint_document",
    "decode_checkpoint",
    "encode_checkpoint",
    "parse_engineering_fixture",
    "sha256_hex",
    "timestamp_iso",
    "validate_candle",
]
