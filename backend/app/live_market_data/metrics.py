"""Thread-safe operational metrics for live market ingestion."""

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class LiveIngestionMetricsSnapshot:
    connections: int
    disconnects: int
    reconnects: int
    messages_received: int
    messages_rejected: int
    incomplete_updates: int
    completed_candles: int
    persisted_snapshots: int
    duplicate_candles: int
    conflicting_candles: int
    gaps_detected: int
    missing_intervals: int
    persistence_failures: int
    heartbeat_timeouts: int


class LiveIngestionMetrics:
    """Minimal dependency-free counter registry with atomic snapshots."""

    _FIELDS = tuple(LiveIngestionMetricsSnapshot.__annotations__)

    def __init__(self) -> None:
        self._lock = Lock()
        self._values = {field: 0 for field in self._FIELDS}

    def increment(self, field: str, amount: int = 1) -> None:
        if field not in self._values:
            raise ValueError(f"Unknown live ingestion metric: {field}.")
        if isinstance(amount, bool) or amount < 0:
            raise ValueError("Metric increment must be a non-negative integer.")
        with self._lock:
            self._values[field] += amount

    def snapshot(self) -> LiveIngestionMetricsSnapshot:
        with self._lock:
            return LiveIngestionMetricsSnapshot(**self._values)
