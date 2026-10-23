"""Bounded, process-local request rate limiting for API safety."""

from collections import OrderedDict, deque
from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from time import monotonic

from redis.asyncio import Redis
from redis.exceptions import RedisError


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int


class RateLimitUnavailable(RuntimeError):
    """Raised when the shared limiter cannot establish a safe decision."""


class LocalRateLimiter:
    """Fixed-window limiter for one API process, not a distributed quota."""

    def __init__(
        self,
        *,
        requests: int,
        window_seconds: float,
        max_keys: int = 10_000,
    ) -> None:
        if requests <= 0:
            raise ValueError("Rate-limit request count must be positive.")
        if window_seconds <= 0:
            raise ValueError("Rate-limit window must be positive.")
        if max_keys <= 0:
            raise ValueError("Rate-limit key capacity must be positive.")
        self.requests = requests
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> RateLimitDecision:
        current = monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self.max_keys:
                    self._events.popitem(last=False)
                events = deque()
                self._events[key] = events
            else:
                self._events.move_to_end(key)
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.requests:
                retry_after = max(
                    1,
                    int(events[0] + self.window_seconds - current + 0.999),
                )
                return RateLimitDecision(False, retry_after)
            events.append(current)
            return RateLimitDecision(True, 0)

    async def async_check(
        self,
        key: str,
        *,
        now: float | None = None,
    ) -> RateLimitDecision:
        return self.check(key, now=now)


class RedisRateLimiter:
    """Atomic fixed-window limiter shared by API workers and replicas."""

    _SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""

    def __init__(
        self,
        client: Redis,
        *,
        requests: int,
        window_seconds: float,
        key_prefix: str = "alphalens:rate-limit:",
    ) -> None:
        if requests <= 0:
            raise ValueError("Rate-limit request count must be positive.")
        if window_seconds <= 0:
            raise ValueError("Rate-limit window must be positive.")
        self._client = client
        self.requests = requests
        self.window_seconds = window_seconds
        self._window_seconds = max(1, int(window_seconds + 0.999))
        self._key_prefix = key_prefix

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        requests: int,
        window_seconds: float,
    ) -> "RedisRateLimiter":
        return cls(
            Redis.from_url(url, decode_responses=False),
            requests=requests,
            window_seconds=window_seconds,
        )

    async def async_check(self, key: str) -> RateLimitDecision:
        digest = sha256(key.encode("utf-8")).hexdigest()
        redis_key = f"{self._key_prefix}{digest}"
        try:
            result = await self._client.eval(
                self._SCRIPT,
                1,
                redis_key,
                self._window_seconds,
            )
        except RedisError as error:
            raise RateLimitUnavailable("Shared rate limiter is unavailable.") from error
        count, ttl = (int(value) for value in result)
        if count > self.requests:
            return RateLimitDecision(False, max(1, ttl))
        return RateLimitDecision(True, 0)

    async def close(self) -> None:
        await self._client.aclose()
