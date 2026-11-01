"""Safe local PostgreSQL startup tests."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import local_stack
from app.settings import ConfigurationError, load_settings


class LocalStackSafetyTests(unittest.TestCase):
    def test_nonempty_noncluster_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "postgres"
            path.mkdir()
            (path / "partial-file").write_text("preserve", encoding="utf-8")
            original = local_stack.PGDATA
            try:
                local_stack.PGDATA = path
                with self.assertRaisesRegex(RuntimeError, "non-empty non-cluster"):
                    local_stack._ensure_services({})
            finally:
                local_stack.PGDATA = original

    def test_empty_directory_is_not_mistaken_for_a_cluster(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "postgres"
            path.mkdir()
            self.assertFalse((path / "PG_VERSION").exists())
            self.assertFalse((path / "global" / "pg_control").exists())

    def test_local_only_runtime_is_loopback_bound_and_explicit(self) -> None:
        with patch.dict(
            local_stack.os.environ,
            {
                "ALPHALENS_LOCAL_ONLY": "true",
                "ALPHALENS_LOCAL_BIND_ADDRESS": "localhost",
                "ALPHALENS_API_HOST": "127.0.0.1",
            },
            clear=True,
        ):
            settings = load_settings()
        self.assertTrue(settings.local_only)
        self.assertEqual(settings.local_bind_address, "localhost")
        self.assertEqual(settings.host, "127.0.0.1")

    def test_local_only_rejects_non_loopback_api_host(self) -> None:
        with patch.dict(
            local_stack.os.environ,
            {"ALPHALENS_LOCAL_ONLY": "true", "ALPHALENS_API_HOST": "0.0.0.0"},
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigurationError, "loopback API host"):
                load_settings()
