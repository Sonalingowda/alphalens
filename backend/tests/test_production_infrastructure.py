"""Focused tests for production infrastructure boundaries."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.infrastructure.observability import install_observability
from app.infrastructure.redis import (
    CoordinationUnavailableError,
    RedisInfrastructure,
)
from app.infrastructure.schema import expected_schema_heads
from app.infrastructure.workers import BackgroundWorker, WorkerConfiguration
from app.settings import ConfigurationError, load_settings


class ConfigurationSecretTests(TestCase):
    def test_database_and_redis_urls_load_from_secret_files(self) -> None:
        database_url = "postgresql+asyncpg://app:secret@database/alphalens"
        redis_url = "redis://:secret@redis:6379/0"
        with TemporaryDirectory() as directory:
            database = Path(directory) / "database"
            redis = Path(directory) / "redis"
            database.write_text(f"{database_url}\n", encoding="utf-8")
            redis.write_text(f"{redis_url}\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "ALPHALENS_DATABASE_URL_FILE": str(database),
                    "ALPHALENS_REDIS_URL_FILE": str(redis),
                },
                clear=True,
            ):
                settings = load_settings()

        self.assertEqual(settings.database_url, database_url)
        self.assertEqual(settings.redis_url, redis_url)

    def test_direct_value_and_secret_file_fail_closed(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ALPHALENS_DATABASE_URL": "postgresql+asyncpg://a:b@db/name",
                "ALPHALENS_DATABASE_URL_FILE": "/not-used",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigurationError, "only one"):
                load_settings()


class OperationalEndpointTests(TestCase):
    def test_trace_headers_metrics_and_health_are_deterministic(self) -> None:
        app = FastAPI()

        async def ready() -> bool:
            return True

        install_observability(
            app,
            readiness_checks={"redis": ready, "postgresql": ready},
            metrics_enabled=True,
        )

        with TestClient(app) as client:
            liveness = client.get(
                "/health/liveness",
                headers={"X-Request-ID": "request-1", "X-Correlation-ID": "trace-1"},
            )
            readiness = client.get("/health/readiness")
            metrics = client.get("/metrics/prometheus")

        self.assertEqual(liveness.status_code, 200)
        self.assertEqual(liveness.headers["X-Request-ID"], "request-1")
        self.assertEqual(liveness.headers["X-Correlation-ID"], "trace-1")
        self.assertEqual(
            readiness.json(),
            {
                "status": "ready",
                "checks": {"postgresql": "ready", "redis": "ready"},
            },
        )
        self.assertIn("alphalens_http_requests_total", metrics.text)

    def test_readiness_fails_closed(self) -> None:
        app = FastAPI()

        async def failed() -> bool:
            return False

        install_observability(
            app,
            readiness_checks={"postgresql": failed},
            metrics_enabled=False,
        )
        with TestClient(app) as client:
            response = client.get("/health/readiness")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unavailable")


class MigrationGraphTests(TestCase):
    def test_migration_graph_has_one_current_head(self) -> None:
        self.assertEqual(expected_schema_heads(), frozenset({"20260803_0035"}))


class ProductionCompositionTests(TestCase):
    def test_frozen_public_routes_and_operational_routes_are_composed(self) -> None:
        from app.prediction_api import app

        paths = {getattr(route, "path", "") for route in app.routes}
        self.assertTrue(
            {
                "/health",
                "/health/liveness",
                "/health/readiness",
                "/markets/live",
                "/metrics/prometheus",
                "/opportunities",
                "/opportunities/{opportunity_id}",
            }.issubset(paths)
        )


class RedisInfrastructureTests(IsolatedAsyncioTestCase):
    async def test_cache_payload_is_canonical_and_expiring(self) -> None:
        client = AsyncMock()
        infrastructure = RedisInfrastructure(client)

        await infrastructure.cache_set("key", {"z": 1, "a": 2}, ttl_seconds=10)

        client.set.assert_awaited_once_with(
            "alphalens:cache:key",
            json.dumps({"a": 2, "z": 1}, separators=(",", ":")),
            ex=10,
        )

    async def test_redis_failures_use_infrastructure_exception(self) -> None:
        client = AsyncMock()
        client.ping.side_effect = RedisConnectionError("unavailable")

        with self.assertRaises(CoordinationUnavailableError):
            await RedisInfrastructure(client).ping()

    async def test_corrupt_cache_payload_fails_closed(self) -> None:
        client = AsyncMock()
        client.get.return_value = "not-json"

        with self.assertRaises(CoordinationUnavailableError):
            await RedisInfrastructure(client).cache_get("key")

    async def test_invalid_coordination_keys_fail_before_io(self) -> None:
        client = AsyncMock()
        with self.assertRaises(ValueError):
            await RedisInfrastructure(client).enqueue("queue", "has spaces")
        client.rpush.assert_not_awaited()


class WorkerLifecycleTests(IsolatedAsyncioTestCase):
    async def test_worker_retries_without_interpreting_task_reference(self) -> None:
        coordination = AsyncMock()
        handler = AsyncMock(side_effect=[RuntimeError("transient"), None])
        worker = BackgroundWorker(
            coordination=coordination,
            configuration=WorkerConfiguration(
                queue="infra",
                worker_id="worker-1",
                poll_seconds=0.001,
                max_retries=1,
            ),
            handler=handler,
        )

        await worker._execute_with_retry("task-123", asyncio.Event())

        self.assertEqual(handler.await_count, 2)
        handler.assert_awaited_with("task-123")

    async def test_worker_honors_shutdown_before_task_execution(self) -> None:
        handler = AsyncMock()
        worker = BackgroundWorker(
            coordination=AsyncMock(),
            configuration=WorkerConfiguration(
                queue="infra",
                worker_id="worker-1",
                poll_seconds=0.001,
                max_retries=1,
            ),
            handler=handler,
        )
        stopped = asyncio.Event()
        stopped.set()

        await worker._execute_with_retry("task-123", stopped)

        handler.assert_not_awaited()
