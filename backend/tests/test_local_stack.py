"""Safe local PostgreSQL startup tests."""

from pathlib import Path
import tempfile
import unittest

from scripts import local_stack


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
