"""Safety and telemetry tests for the owner-runtime daily supervisor."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from scripts.local_daily import (
    DailyRuntimeConfig,
    DailyRuntimeError,
    DailySupervisor,
    derive_runtime_state,
)
from app.opportunity_intelligence.api import _feed_snapshot
from app.live_market_data import FilesystemRuntimeCheckpointStore, RuntimeCheckpoint


ROOT = Path("/private/tmp/alphalens-final-localhost-integration-20261102")
SOURCE = "6f844a74e89537ff26c7195e895416b42bb78a31a01618eb3d1e44e3b09210c5"
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _status(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "run_id": "run-1",
        "pid": os.getpid(),
        "worker_status": "RUNNING",
        "heartbeat_at": NOW.isoformat(),
        "checkpoint": {"gap_status": "CLEAR"},
        "connection": {"healthy": True, "state": "connected"},
    }
    value.update(overrides)
    return value


def _write_checkpoint(path: Path, source: str = SOURCE) -> Path:
    FilesystemRuntimeCheckpointStore(path, source_dataset_sha256=source).save(
        RuntimeCheckpoint(
            source_dataset_sha256=source,
            symbol="BTCUSDT",
            timeframe="5m",
            sequence=567,
            status="READY",
            last_committed_open_time=datetime(2026, 11, 3, 18, 10, tzinfo=timezone.utc),
            last_committed_content_hash="a" * 64,
            in_flight_open_time=None,
            in_flight_content_hash=None,
            missing_start=None,
            missing_end=None,
            last_error=None,
            updated_at=datetime(2026, 11, 3, 18, 15, tzinfo=timezone.utc),
        )
    )
    return path


def _config(state_dir: Path, checkpoint_path: Path | None = None, **env: str) -> DailyRuntimeConfig:
    values = {
        "ALPHALENS_LOCAL_ONLY": "true",
        "ALPHALENS_ENVIRONMENT": "development",
        "ALPHALENS_API_HOST": "127.0.0.1",
        "ALPHALENS_DATABASE_URL": "postgresql+asyncpg://user:pass@127.0.0.1:55461/db",
        "ALPHALENS_REDIS_URL": "redis://:pass@127.0.0.1:56398/0",
        "ALPHALENS_DAILY_EXPECTED_DATABASE": "db",
        "ALPHALENS_DAILY_EXPECTED_DATABASE_PORT": "55461",
        "ALPHALENS_DAILY_EXPECTED_REDIS_PORT": "56398",
    }
    values.update(env)
    if checkpoint_path is None:
        checkpoint_path = _write_checkpoint(state_dir.parent / "owner-checkpoint.json")
    with patch.dict(os.environ, values, clear=True):
        return DailyRuntimeConfig.from_environment(
            root=ROOT,
            state_dir=state_dir,
            checkpoint_path=checkpoint_path,
            source_identity=SOURCE,
        )


def test_daily_config_requires_loopback_owner_services() -> None:
    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(DailyRuntimeError, match="database must be loopback"):
            _config(
                Path(directory) / "runtime",
                ALPHALENS_DATABASE_URL="postgresql+asyncpg://user:pass@remote/db",
            )


def test_daily_config_refuses_acceptance_state_and_short_heartbeat_window() -> None:
    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(DailyRuntimeError, match="cannot reuse acceptance"):
            _config(Path(directory) / "acceptance-runtime")
        with pytest.raises(DailyRuntimeError, match="three heartbeat intervals"):
            with patch.dict(
                os.environ,
                {
                    "ALPHALENS_LOCAL_ONLY": "true",
                    "ALPHALENS_ENVIRONMENT": "development",
                    "ALPHALENS_API_HOST": "127.0.0.1",
                    "ALPHALENS_DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:5432/db",
                    "ALPHALENS_REDIS_URL": "redis://:p@127.0.0.1:6379/0",
                    "ALPHALENS_DAILY_EXPECTED_DATABASE": "db",
                    "ALPHALENS_DAILY_EXPECTED_DATABASE_PORT": "5432",
                    "ALPHALENS_DAILY_EXPECTED_REDIS_PORT": "6379",
                },
                clear=True,
            ):
                DailyRuntimeConfig.from_environment(
                    root=ROOT,
                    state_dir=Path(directory) / "runtime",
                    checkpoint_path=_write_checkpoint(Path(directory) / "checkpoint.json"),
                    source_identity=SOURCE,
                    heartbeat_interval_seconds=5,
                    heartbeat_freshness_seconds=10,
                )


def test_runtime_state_requires_current_run_and_fresh_live_heartbeat() -> None:
    assert derive_runtime_state(
        _status(), now=NOW + timedelta(seconds=1), heartbeat_freshness_seconds=30,
        expected_run_id="run-1",
    ) == "LIVE"
    assert derive_runtime_state(
        _status(), now=NOW + timedelta(seconds=31), heartbeat_freshness_seconds=30,
        expected_run_id="run-1",
    ) == "STALE"
    assert derive_runtime_state(
        _status(), now=NOW, heartbeat_freshness_seconds=30,
        expected_run_id="different-run",
    ) == "STALE"


def test_runtime_state_is_fail_closed_for_recovery_and_quarantine() -> None:
    assert derive_runtime_state(
        _status(worker_status="WARMED"), now=NOW, heartbeat_freshness_seconds=30,
    ) == "RECOVERING"
    assert derive_runtime_state(
        _status(checkpoint={"gap_status": "QUARANTINED"}),
        now=NOW,
        heartbeat_freshness_seconds=30,
    ) == "FAILED"
    assert derive_runtime_state(
        _status(worker_status="STOPPED"), now=NOW, heartbeat_freshness_seconds=30,
    ) == "STOPPED"


def test_non_live_runtime_state_suppresses_actionable_feed() -> None:
    feed = _feed_snapshot(
        {"runtime_state": "RECOVERING", "worker_status": "RUNNING"}, NOW
    )
    assert feed["state"] == "stopped"
    assert "no current opportunities" in str(feed["warning"])


def test_supervisor_worker_command_keeps_recovery_batch_bounded() -> None:
    with tempfile.TemporaryDirectory() as directory:
        config = _config(Path(directory) / "runtime")
        supervisor = DailySupervisor(config, python=Path("/tmp/python"))
        command = supervisor.worker_command()
        assert "--max-recoverable-gap-intervals" in command
        index = command.index("--max-recoverable-gap-intervals")
        assert command[index + 1] == "120"
        assert "--run-id" in command
        assert "--heartbeat-interval-seconds" in command


def test_explicit_checkpoint_is_separate_from_daily_state() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / "daily"
        checkpoint = _write_checkpoint(Path(directory) / "owner" / "checkpoint.json")
        config = _config(state, checkpoint)
        assert config.checkpoint == checkpoint.resolve()
        assert config.status.parent == state.resolve()
        assert str(config.checkpoint) in DailySupervisor(config).worker_command()


def test_missing_malformed_source_mismatch_and_acceptance_checkpoints_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        with pytest.raises(DailyRuntimeError, match="existing authoritative checkpoint"):
            _config(root / "daily", root / "missing.json")

        malformed = root / "malformed.json"
        malformed.write_text("{}", encoding="utf-8")
        with pytest.raises(DailyRuntimeError, match="integrity or source"):
            _config(root / "daily", malformed)

        mismatch = _write_checkpoint(root / "mismatch.json", "b" * 64)
        with pytest.raises(DailyRuntimeError, match="integrity or source"):
            _config(root / "daily", mismatch)

        acceptance = _write_checkpoint(root / "alphalens-acceptance" / "state" / "checkpoint.json")
        with pytest.raises(DailyRuntimeError, match="Acceptance checkpoint is immutable"):
            _config(root / "daily", acceptance)


def test_supervisors_share_checkpoint_lock_not_daily_state_lock() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        checkpoint = _write_checkpoint(root / "owner" / "checkpoint.json")
        first = DailySupervisor(_config(root / "daily-one", checkpoint))
        second = DailySupervisor(_config(root / "daily-two", checkpoint))
        with patch.dict(os.environ, {"ALPHALENS_LOCAL_ONLY": "true", "ALPHALENS_ENVIRONMENT": "development"}):
            first.config.validate()
            second.config.validate()
            first.config.state_dir.mkdir(parents=True)
            second.config.state_dir.mkdir(parents=True)
            first._acquire_checkpoint_lock()
            try:
                with pytest.raises(DailyRuntimeError, match="Another daily supervisor"):
                    second._acquire_checkpoint_lock()
            finally:
                first.stop()
