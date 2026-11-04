"""Supervise one explicit, loopback-only AlphaLens daily runtime.

This module intentionally does not initialize PostgreSQL, mutate checkpoints, or
repair a gap itself.  It verifies the owner runtime contract, starts only the
processes it owns, and delegates candle recovery to the existing worker and
bounded pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Literal
from urllib.request import urlopen
from urllib.parse import urlsplit
from uuid import uuid4

from app.live_market_data import FilesystemRuntimeCheckpointStore, RuntimeCheckpoint
from app.live_market_data.continuous import RuntimeCheckpointError


RuntimeState = Literal["LIVE", "RECOVERING", "STOPPED", "STALE", "FAILED"]
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_HEARTBEAT_FRESHNESS_SECONDS = 30.0
MAX_RECOVERY_BATCH_INTERVALS = 120


class DailyRuntimeError(RuntimeError):
    """Raised when the daily runtime cannot prove safe ownership/configuration."""


async def verify_owner_database_continuity(
    config: "DailyRuntimeConfig",
    checkpoint: RuntimeCheckpoint,
    *,
    connect: Any | None = None,
) -> None:
    """Read-only proof that the owner DB contains the checkpoint boundary."""
    if connect is None:
        import asyncpg

        connect = asyncpg.connect
    dsn = config.database_url.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    connection = await connect(dsn)
    try:
        database_name, schema_name = await connection.fetchrow(
            "SELECT current_database(), current_schema()"
        )
        if database_name != config.expected_database or schema_name != "public":
            raise DailyRuntimeError(
                "Connected database identity does not match the daily owner contract."
            )
        timestamp = checkpoint.last_committed_open_time.isoformat().replace(
            "+00:00", "Z"
        )
        count = await connection.fetchval(
            """
            SELECT count(*)
            FROM immutable_runtime_aggregates
            WHERE scope_instrument = 'BTCUSDT'
              AND scope_timeframe = '5m'
              AND canonical_payload->'candles'->0->>'timestamp' = $1
            """,
            timestamp,
        )
        if count != 1:
            raise DailyRuntimeError(
                "Owner database does not contain the authoritative checkpoint boundary."
            )
    finally:
        await connection.close()


@dataclass(frozen=True, slots=True)
class DailyRuntimeConfig:
    root: Path
    state_dir: Path
    checkpoint: Path
    status: Path
    manifest: Path
    source_identity: str
    database_url: str
    redis_url: str
    expected_database: str
    expected_database_port: int
    expected_redis_port: int
    api_host: str
    api_port: int
    frontend_port: int
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    heartbeat_freshness_seconds: float = DEFAULT_HEARTBEAT_FRESHNESS_SECONDS
    max_recoverable_gap_intervals: int = MAX_RECOVERY_BATCH_INTERVALS

    @classmethod
    def from_environment(
        cls,
        *,
        root: Path,
        state_dir: Path,
        checkpoint_path: Path,
        source_identity: str,
        heartbeat_freshness_seconds: float = DEFAULT_HEARTBEAT_FRESHNESS_SECONDS,
        heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    ) -> "DailyRuntimeConfig":
        database_url = os.environ.get("ALPHALENS_DATABASE_URL", "")
        redis_url = os.environ.get("ALPHALENS_REDIS_URL", "")
        expected_database = os.environ.get("ALPHALENS_DAILY_EXPECTED_DATABASE", "")
        expected_database_port = int(
            os.environ.get("ALPHALENS_DAILY_EXPECTED_DATABASE_PORT", "0")
        )
        expected_redis_port = int(
            os.environ.get("ALPHALENS_DAILY_EXPECTED_REDIS_PORT", "0")
        )
        config = cls(
            root=root.resolve(),
            state_dir=state_dir.resolve(),
            checkpoint=checkpoint_path.resolve(),
            status=state_dir.resolve() / "worker-status.json",
            manifest=state_dir.resolve() / "daily-runtime.json",
            source_identity=source_identity,
            database_url=database_url,
            redis_url=redis_url,
            expected_database=expected_database,
            expected_database_port=expected_database_port,
            expected_redis_port=expected_redis_port,
            api_host=os.environ.get("ALPHALENS_API_HOST", "127.0.0.1"),
            api_port=int(os.environ.get("ALPHALENS_API_PORT", "18023")),
            frontend_port=int(os.environ.get("ALPHALENS_FRONTEND_PORT", "13023")),
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            heartbeat_freshness_seconds=heartbeat_freshness_seconds,
        )
        config.validate()
        return config

    def validate(self) -> None:
        if os.environ.get("ALPHALENS_LOCAL_ONLY", "").lower() != "true":
            raise DailyRuntimeError("Daily runtime requires ALPHALENS_LOCAL_ONLY=true.")
        if os.environ.get("ALPHALENS_ENVIRONMENT", "development").lower() not in {
            "development",
            "test",
        }:
            raise DailyRuntimeError("Daily runtime is limited to local development/test.")
        if self.api_host not in {"127.0.0.1", "localhost", "::1"}:
            raise DailyRuntimeError("Daily runtime API must bind to loopback.")
        if not self.source_identity.strip():
            raise DailyRuntimeError("A non-empty Binance source identity is required.")
        if not self.database_url or not self.redis_url:
            raise DailyRuntimeError("Database and Redis URLs are required.")
        if not self.expected_database or self.expected_database_port <= 0 or self.expected_redis_port <= 0:
            raise DailyRuntimeError(
                "Daily owner database and Redis identity expectations are required."
            )
        database = urlsplit(self.database_url)
        redis = urlsplit(self.redis_url)
        if database.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise DailyRuntimeError("Daily runtime database must be loopback-only.")
        if redis.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise DailyRuntimeError("Daily runtime Redis must be loopback-only.")
        if database.path.lstrip("/") != self.expected_database:
            raise DailyRuntimeError("Configured database name does not match daily owner identity.")
        if database.port != self.expected_database_port:
            raise DailyRuntimeError("Configured database port does not match daily owner identity.")
        if redis.port != self.expected_redis_port:
            raise DailyRuntimeError("Configured Redis port does not match daily owner identity.")
        if not 1 <= self.max_recoverable_gap_intervals <= MAX_RECOVERY_BATCH_INTERVALS:
            raise DailyRuntimeError("Recovery batches may not exceed 120 intervals.")
        if self.heartbeat_interval_seconds <= 0:
            raise DailyRuntimeError("Heartbeat interval must be positive.")
        if self.heartbeat_freshness_seconds < self.heartbeat_interval_seconds * 3:
            raise DailyRuntimeError(
                "Heartbeat freshness must allow at least three heartbeat intervals."
            )
        if "acceptance" in str(self.state_dir).lower():
            raise DailyRuntimeError("Daily runtime state cannot reuse acceptance evidence.")
        if self.state_dir == self.root or self.state_dir in self.root.parents:
            raise DailyRuntimeError("Daily runtime state must be outside the source checkout.")
        if not self.checkpoint.is_absolute() or not self.checkpoint.is_file():
            raise DailyRuntimeError(
                "An existing authoritative checkpoint file is required; refusing implicit creation."
            )
        if self.checkpoint.is_symlink():
            raise DailyRuntimeError("Authoritative checkpoint must not be a symlink.")
        if self.checkpoint.parent == self.state_dir:
            raise DailyRuntimeError(
                "Authoritative checkpoint must be separate from daily runtime state."
            )
        path_parts = {part.lower() for part in self.checkpoint.parts}
        if "acceptance" in path_parts or any("acceptance" in part for part in path_parts):
            raise DailyRuntimeError(
                "Acceptance checkpoint is immutable; an audited checkpoint handoff is required."
            )
        try:
            checkpoint = FilesystemRuntimeCheckpointStore(
                self.checkpoint,
                source_dataset_sha256=self.source_identity,
            ).load()
        except RuntimeCheckpointError as error:
            raise DailyRuntimeError(
                "Authoritative checkpoint failed integrity or source validation."
            ) from error
        if checkpoint is None or checkpoint.last_committed_open_time is None:
            raise DailyRuntimeError(
                "Authoritative checkpoint must contain a durable committed boundary."
            )
        content_hash = checkpoint.last_committed_content_hash
        if (
            content_hash is None
            or len(content_hash) != 64
            or any(character not in "0123456789abcdef" for character in content_hash)
        ):
            raise DailyRuntimeError(
                "Authoritative checkpoint committed content hash is invalid."
            )


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def process_is_alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def derive_runtime_state(
    status: dict[str, Any] | None,
    *,
    now: datetime,
    heartbeat_freshness_seconds: float,
    expected_run_id: str | None = None,
) -> RuntimeState:
    """Classify status without treating historical acceptance telemetry as live."""
    if not status:
        return "STOPPED"
    if expected_run_id and status.get("run_id") != expected_run_id:
        return "STALE"
    heartbeat = _parse_timestamp(status.get("heartbeat_at") or status.get("updated_at"))
    if heartbeat is None or (now.astimezone(timezone.utc) - heartbeat).total_seconds() > heartbeat_freshness_seconds:
        return "STALE"
    worker_status = status.get("worker_status")
    if worker_status in {"WARMED", "STARTING"}:
        return "RECOVERING"
    if worker_status in {
        "WARMUP_FAILED",
        "RECOVERY_FAILED",
        "PROCESSING_ERROR",
        "STOPPED_PROTECTED_WINDOW",
    }:
        return "FAILED"
    if worker_status == "STOPPED":
        return "STOPPED"
    checkpoint = status.get("checkpoint") or {}
    connection = status.get("connection") or {}
    if checkpoint.get("gap_status") == "QUARANTINED":
        return "FAILED"
    if worker_status == "RUNNING" and process_is_alive(status.get("pid")):
        if connection.get("healthy") is True and connection.get("state") in {"connected", "running"}:
            return "LIVE"
        return "RECOVERING"
    return "FAILED"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


class DailySupervisor:
    """Own API/frontend/worker children and never take over unrelated PIDs."""

    def __init__(self, config: DailyRuntimeConfig, *, python: Path | None = None) -> None:
        self.config = config
        self.python = (python or Path(sys.executable)).resolve()
        self.run_id = uuid4().hex
        self._children: dict[str, subprocess.Popen[bytes]] = {}
        self._lock_handle = None

    def preflight(self) -> None:
        self.config.validate()
        checkpoint = FilesystemRuntimeCheckpointStore(
            self.config.checkpoint,
            source_dataset_sha256=self.config.source_identity,
        ).load()
        if checkpoint is None:
            raise DailyRuntimeError("Authoritative checkpoint disappeared during preflight.")
        try:
            asyncio.run(verify_owner_database_continuity(self.config, checkpoint))
        except DailyRuntimeError:
            raise
        except Exception as error:  # noqa: BLE001 - fail closed without DSN details
            raise DailyRuntimeError("Owner database continuity verification failed.") from error
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        self._acquire_checkpoint_lock()
        for port, name in ((self.config.api_port, "API"), (self.config.frontend_port, "frontend")):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.25)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    self.stop()
                    raise DailyRuntimeError(f"Refusing to start: {name} port {port} is occupied.")

    def _acquire_checkpoint_lock(self) -> None:
        lock_path = self.config.checkpoint.with_name(
            f".{self.config.checkpoint.name}.daily-supervisor.lock"
        )
        self._lock_handle = lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self._lock_handle.close()
            self._lock_handle = None
            raise DailyRuntimeError("Another daily supervisor owns this runtime.") from error

    def worker_command(self) -> list[str]:
        return [
            str(self.python),
            str(self.config.root / "backend/scripts/local_market_worker.py"),
            "--checkpoint", str(self.config.checkpoint),
            "--status", str(self.config.status),
            "--source-identity", self.config.source_identity,
            "--run-id", self.run_id,
            "--heartbeat-interval-seconds", str(self.config.heartbeat_interval_seconds),
            "--max-recoverable-gap-intervals", str(self.config.max_recoverable_gap_intervals),
        ]

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update({
            "PYTHONPATH": str(self.config.root / "backend"),
            "ALPHALENS_LOCAL_RUNTIME_STATUS_PATH": str(self.config.status),
            "ALPHALENS_LOCAL_DAILY_RUN_ID": self.run_id,
            "ALPHALENS_LOCAL_ONLY": "true",
            "ALPHALENS_MARKET_DATA_STARTUP_ENABLED": "false",
        })
        return environment

    def start(self) -> None:
        self.preflight()
        environment = self._environment()
        backend = self.config.root / "backend"
        frontend = self.config.root / "frontend"
        log_dir = self.config.state_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        def launch(name: str, command: list[str], cwd: Path) -> None:
            handle = (log_dir / f"{name}.log").open("ab")
            self._children[name] = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        launch("api", [str(self.python), "-m", "uvicorn", "app.prediction_api:app", "--host", self.config.api_host, "--port", str(self.config.api_port)], backend)
        _wait_http(f"http://127.0.0.1:{self.config.api_port}/api/v1/local-runtime/status")
        launch("frontend", ["npm", "run", "dev", "--", "--hostname", "localhost", "--port", str(self.config.frontend_port)], frontend)
        launch("worker", self.worker_command(), backend)
        self.config.manifest.write_text(json.dumps({
            "run_id": self.run_id,
            "source_identity": self.config.source_identity,
            "checkpoint": str(self.config.checkpoint),
            "status": str(self.config.status),
            "pids": {name: child.pid for name, child in self._children.items()},
            "started_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def stop(self) -> None:
        for name in ("worker", "frontend", "api"):
            child = self._children.get(name)
            if child is None or child.poll() is not None:
                continue
            child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        if self._lock_handle is not None:
            fcntl.flock(self._lock_handle.fileno(), fcntl.LOCK_UN)
            self._lock_handle.close()
            self._lock_handle = None


def _wait_http(url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:  # loopback URL only
                if response.status < 600:
                    return
        except OSError:
            time.sleep(0.25)
    raise DailyRuntimeError(f"Timed out waiting for local API: {url}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--daily-state-dir",
        "--state-dir",
        dest="state_dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--heartbeat-freshness-seconds", type=float, default=DEFAULT_HEARTBEAT_FRESHNESS_SECONDS)
    parser.add_argument("--heartbeat-interval-seconds", type=float, default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS)
    args = parser.parse_args()
    config = DailyRuntimeConfig.from_environment(
        root=args.root,
        state_dir=args.state_dir,
        checkpoint_path=args.checkpoint_path,
        source_identity=args.source_identity,
        heartbeat_freshness_seconds=args.heartbeat_freshness_seconds,
        heartbeat_interval_seconds=args.heartbeat_interval_seconds,
    )
    supervisor = DailySupervisor(config)
    supervisor.start()
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    finally:
        supervisor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
