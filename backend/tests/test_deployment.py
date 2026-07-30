"""Production configuration and observability tests."""

import json
import logging
import os
from unittest import TestCase
from unittest.mock import patch

from app.observability.logging import JsonLogFormatter
from app.observability.resources import resource_snapshot
from app.settings import ConfigurationError, load_settings


class ProductionConfigurationTests(TestCase):
    def test_valid_production_configuration_loads(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ALPHALENS_ENVIRONMENT": "production",
                "ALPHALENS_API_HOST": "0.0.0.0",
                "ALPHALENS_API_WORKERS": "2",
                "ALPHALENS_CORS_ALLOWED_ORIGINS": (
                    "https://dashboard.example.com"
                ),
                "ALPHALENS_DATABASE_URL": (
                    "postgresql+asyncpg://app:strong-test-value@db/alphalens"
                ),
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.environment, "production")
        self.assertEqual(settings.api_workers, 2)
        self.assertEqual(
            settings.cors_allowed_origins,
            ("https://dashboard.example.com",),
        )

    def test_production_rejects_placeholder_database_password(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ALPHALENS_ENVIRONMENT": "production",
                "ALPHALENS_API_HOST": "0.0.0.0",
                "ALPHALENS_CORS_ALLOWED_ORIGINS": (
                    "https://dashboard.example.com"
                ),
                "ALPHALENS_DATABASE_URL": (
                    "postgresql+asyncpg://app:replace-me@db/alphalens"
                ),
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ConfigurationError,
                "non-placeholder",
            ):
                load_settings()

    def test_wildcard_cors_origin_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"ALPHALENS_CORS_ALLOWED_ORIGINS": "*"},
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigurationError, "wildcard"):
                load_settings()

    def test_invalid_request_limit_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES": "128"},
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigurationError, "between"):
                load_settings()


class ObservabilityTests(TestCase):
    def test_json_log_formatter_emits_structured_context(self) -> None:
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="alphalens.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Request failed.",
            args=(),
            exc_info=None,
        )
        record.request_path = "/api/v1/predict"
        record.status_code = 422
        record.error_code = "REQUEST_SCHEMA_INVALID"

        payload = json.loads(formatter.format(record))

        self.assertEqual(payload["level"], "ERROR")
        self.assertEqual(payload["request_path"], "/api/v1/predict")
        self.assertEqual(payload["status_code"], 422)
        self.assertEqual(
            payload["error_code"],
            "REQUEST_SCHEMA_INVALID",
        )

    def test_resource_snapshot_is_nonnegative(self) -> None:
        snapshot = resource_snapshot()

        self.assertGreaterEqual(snapshot.uptime_seconds, 0)
        self.assertGreaterEqual(snapshot.process_cpu_user_seconds, 0)
        self.assertGreaterEqual(snapshot.process_cpu_system_seconds, 0)
        self.assertGreater(snapshot.maximum_resident_set_bytes, 0)
