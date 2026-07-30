"""Thread-safe in-process operational metrics for API health monitoring."""

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    request_count: int
    successful_request_count: int
    error_request_count: int
    prediction_count: int
    cumulative_latency_microseconds: int
    maximum_latency_microseconds: int

    @property
    def average_latency_microseconds(self) -> float:
        if self.request_count == 0:
            return 0.0
        return (
            self.cumulative_latency_microseconds
            / self.request_count
        )


class PredictionAPIMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._request_count = 0
        self._successful_request_count = 0
        self._error_request_count = 0
        self._prediction_count = 0
        self._cumulative_latency_microseconds = 0
        self._maximum_latency_microseconds = 0

    def record(
        self,
        *,
        status_code: int,
        latency_microseconds: int,
        prediction_generated: bool,
    ) -> None:
        with self._lock:
            self._request_count += 1
            if status_code < 400:
                self._successful_request_count += 1
            else:
                self._error_request_count += 1
            if prediction_generated:
                self._prediction_count += 1
            self._cumulative_latency_microseconds += (
                latency_microseconds
            )
            self._maximum_latency_microseconds = max(
                self._maximum_latency_microseconds,
                latency_microseconds,
            )

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                request_count=self._request_count,
                successful_request_count=(
                    self._successful_request_count
                ),
                error_request_count=self._error_request_count,
                prediction_count=self._prediction_count,
                cumulative_latency_microseconds=(
                    self._cumulative_latency_microseconds
                ),
                maximum_latency_microseconds=(
                    self._maximum_latency_microseconds
                ),
            )

