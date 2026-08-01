"""Redis cache and coordination adapter; never canonical business storage."""

from dataclasses import dataclass
import json
from secrets import token_hex
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError


class CoordinationUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CoordinationLock:
    key: str
    token: str

    def __post_init__(self) -> None:
        _validate_key(self.key)
        if not self.token or any(character.isspace() for character in self.token):
            raise ValueError("Redis coordination lock token is invalid.")


class RedisInfrastructure:
    CACHE_PREFIX = "alphalens:cache:"
    LOCK_PREFIX = "alphalens:lock:"
    QUEUE_PREFIX = "alphalens:queue:"
    HEARTBEAT_PREFIX = "alphalens:heartbeat:"

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str) -> "RedisInfrastructure":
        return cls(Redis.from_url(url, decode_responses=True))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except RedisError as error:
            raise CoordinationUnavailableError("Redis ping failed.") from error

    async def cache_get(self, key: str) -> dict[str, Any] | None:
        _validate_key(key)
        try:
            value = await self._client.get(f"{self.CACHE_PREFIX}{key}")
        except RedisError as error:
            raise CoordinationUnavailableError("Redis cache read failed.") from error
        if value is None:
            return None
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError) as error:
            raise CoordinationUnavailableError(
                "Redis cache payload is invalid."
            ) from error
        if not isinstance(decoded, dict):
            raise CoordinationUnavailableError("Redis cache payload is invalid.")
        return decoded

    async def cache_set(
        self,
        key: str,
        value: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        _validate_key(key)
        if ttl_seconds <= 0:
            raise ValueError("Cache TTL must be positive.")
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        try:
            await self._client.set(
                f"{self.CACHE_PREFIX}{key}", payload, ex=ttl_seconds
            )
        except RedisError as error:
            raise CoordinationUnavailableError("Redis cache write failed.") from error

    async def acquire_lock(
        self,
        key: str,
        *,
        ttl_seconds: int,
    ) -> CoordinationLock | None:
        _validate_key(key)
        if ttl_seconds <= 0:
            raise ValueError("Lock TTL must be positive.")
        token = token_hex(16)
        try:
            acquired = await self._client.set(
                f"{self.LOCK_PREFIX}{key}",
                token,
                ex=ttl_seconds,
                nx=True,
            )
        except RedisError as error:
            raise CoordinationUnavailableError("Redis lock acquisition failed.") from error
        return CoordinationLock(key, token) if acquired else None

    async def release_lock(self, lock: CoordinationLock) -> bool:
        if not isinstance(lock, CoordinationLock):
            raise ValueError("A CoordinationLock is required.")
        script = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            released = await self._client.eval(
                script, 1, f"{self.LOCK_PREFIX}{lock.key}", lock.token
            )
        except RedisError as error:
            raise CoordinationUnavailableError("Redis lock release failed.") from error
        return bool(released)

    async def enqueue(self, queue: str, task_reference: str) -> None:
        _validate_key(queue)
        _validate_key(task_reference)
        try:
            await self._client.rpush(
                f"{self.QUEUE_PREFIX}{queue}", task_reference
            )
        except RedisError as error:
            raise CoordinationUnavailableError("Redis enqueue failed.") from error

    async def dequeue(
        self,
        queue: str,
        *,
        timeout_seconds: int,
    ) -> str | None:
        _validate_key(queue)
        if timeout_seconds < 0:
            raise ValueError("Queue timeout cannot be negative.")
        try:
            result = await self._client.blpop(
                f"{self.QUEUE_PREFIX}{queue}", timeout=timeout_seconds
            )
        except RedisError as error:
            raise CoordinationUnavailableError("Redis dequeue failed.") from error
        return None if result is None else str(result[1])

    async def heartbeat(
        self,
        worker_id: str,
        *,
        ttl_seconds: int,
    ) -> None:
        _validate_key(worker_id)
        if ttl_seconds <= 0:
            raise ValueError("Heartbeat TTL must be positive.")
        try:
            await self._client.set(
                f"{self.HEARTBEAT_PREFIX}{worker_id}", "alive", ex=ttl_seconds
            )
        except RedisError as error:
            raise CoordinationUnavailableError("Redis heartbeat failed.") from error

    async def close(self) -> None:
        await self._client.aclose()


def _validate_key(value: str) -> None:
    if not isinstance(value, str) or not value or any(
        character.isspace() for character in value
    ):
        raise ValueError("Redis coordination key must be non-empty without spaces.")
