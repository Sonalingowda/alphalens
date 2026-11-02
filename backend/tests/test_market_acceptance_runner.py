"""Regression coverage for acceptance database readiness."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_market_acceptance import _run_schema_migrations


def test_schema_migration_preflight_runs_before_worker_start(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("scripts.run_market_acceptance.subprocess.run", fake_run)
    python = Path("/tmp/alphalens-test-python")
    environment = {"ALPHALENS_MIGRATION_DATABASE_URL": "postgresql+asyncpg://redacted"}

    _run_schema_migrations(python, environment)

    assert calls == [{
        "command": [str(python.resolve()), "-m", "alembic", "upgrade", "head"],
        "cwd": Path(__file__).resolve().parents[1],
        "env": environment,
        "check": False,
        "capture_output": True,
        "text": True,
    }]


def test_schema_migration_preflight_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="UndefinedTableError: relation opportunity_thesis_assessments does not exist",
        )

    monkeypatch.setattr("scripts.run_market_acceptance.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Database migration preflight failed"):
        _run_schema_migrations(Path("/tmp/alphalens-test-python"), {})
