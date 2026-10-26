"""Start, stop and inspect a private localhost AlphaLens stack.

The stack uses native disposable PostgreSQL/Redis processes and never touches
the protected Batch 6U ports or data directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
STATE = Path(os.getenv("ALPHALENS_LOCAL_STATE_DIR", "/private/tmp/alphalens-local-20261026"))
ENV_FILE = STATE / "runtime.env"
PIDS = STATE / "pids.json"
LOGS = STATE / "logs"
PGDATA = STATE / "postgres"
REDISDATA = STATE / "redis"
CHECKPOINT = STATE / "checkpoint.json"
STATUS = STATE / "worker-status.json"
SOURCE_IDENTITY = "alphalens.local.product.binance.btcusdt.5m.v1"
SOURCE_IDENTITY_DIGEST = hashlib.sha256(SOURCE_IDENTITY.encode("utf-8")).hexdigest()
PGPORT = int(os.getenv("ALPHALENS_LOCAL_PGPORT", "55448"))
REDISPORT = int(os.getenv("ALPHALENS_LOCAL_REDISPORT", "56395"))
APIPORT = int(os.getenv("ALPHALENS_LOCAL_APIPORT", "18003"))
FRONTENDPORT = int(os.getenv("ALPHALENS_LOCAL_FRONTENDPORT", "13003"))


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def _load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _base_env() -> dict[str, str]:
    values = os.environ.copy()
    values.update(_load_env())
    values.update(
        {
            "ALPHALENS_ENVIRONMENT": "development",
            "ALPHALENS_MARKET_DATA_STARTUP_ENABLED": "false",
            "ALPHALENS_CORS_ALLOWED_ORIGINS": f"http://127.0.0.1:{FRONTENDPORT},http://localhost:{FRONTENDPORT}",
            "ALPHALENS_LOCAL_RUNTIME_STATUS_PATH": str(STATUS),
            "PYTHONPATH": str(BACKEND),
        }
    )
    return values


def _start_process(command: list[str], *, name: str, env: dict[str, str], cwd: Path) -> int:
    log = (LOGS / f"{name}.log").open("a")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return process.pid


def _ensure_services(env: dict[str, str]) -> None:
    postgres_bin = Path("/opt/homebrew/opt/postgresql@16/bin")
    initdb = postgres_bin / "initdb" if (postgres_bin / "initdb").exists() else Path(shutil.which("initdb") or "initdb")
    pg_ctl = postgres_bin / "pg_ctl" if (postgres_bin / "pg_ctl").exists() else Path(shutil.which("pg_ctl") or "pg_ctl")
    psql = postgres_bin / "psql" if (postgres_bin / "psql").exists() else Path(shutil.which("psql") or "psql")
    if not (PGDATA / "PG_VERSION").exists():
        _run([initdb, "-D", str(PGDATA), "--no-locale", "--encoding=UTF8"])
    if _run([pg_ctl, "-D", str(PGDATA), "status"], check=False).returncode != 0:
        _run([pg_ctl, "-D", str(PGDATA), "-l", str(LOGS / "postgres.log"), "-o", f"-p {PGPORT} -h 127.0.0.1", "start"])
    _run([psql, "-h", "127.0.0.1", "-p", str(PGPORT), "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{env['ALPHALENS_LOCAL_PGUSER']}') THEN CREATE ROLE {env['ALPHALENS_LOCAL_PGUSER']} LOGIN PASSWORD '{env['ALPHALENS_LOCAL_PGPASS']}'; END IF; END $$;"])
    exists = _run(
        [psql, "-h", "127.0.0.1", "-p", str(PGPORT), "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{env['ALPHALENS_LOCAL_PGDB']}'"],
        check=False,
        capture_output=True,
    )
    if exists.stdout.strip() != "1":
        _run([psql, "-h", "127.0.0.1", "-p", str(PGPORT), "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {env['ALPHALENS_LOCAL_PGDB']} OWNER {env['ALPHALENS_LOCAL_PGUSER']};"])
    redis = shutil.which("redis-server")
    redis_pid = REDISDATA / "redis.pid"
    if not redis_pid.exists() or not _pid_alive(int(redis_pid.read_text())):
        _run([redis, "--bind", "127.0.0.1", "--port", str(REDISPORT), "--dir", str(REDISDATA), "--appendonly", "yes", "--requirepass", env["ALPHALENS_LOCAL_REDISPASS"], "--pidfile", str(redis_pid), "--logfile", str(LOGS / "redis.log"), "--daemonize", "yes"])


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _stop_process_group(pid: int) -> None:
    if not _pid_alive(pid):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 8
    while _pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    if _pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def start() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    PGDATA.mkdir(parents=True, exist_ok=True)
    REDISDATA.mkdir(parents=True, exist_ok=True)
    if PIDS.exists():
        record = json.loads(PIDS.read_text())
        if any(_pid_alive(int(pid)) for pid in record.get("pids", {}).values()):
            raise RuntimeError("AlphaLens local stack is already running; use status or stop first.")
        PIDS.unlink()
    env = _load_env()
    if not env:
        env = {
            "ALPHALENS_LOCAL_PGUSER": f"alphalens_local_{secrets.token_hex(4)}",
            "ALPHALENS_LOCAL_PGPASS": secrets.token_urlsafe(24),
            "ALPHALENS_LOCAL_PGDB": f"alphalens_local_{secrets.token_hex(4)}",
            "ALPHALENS_LOCAL_REDISPASS": secrets.token_urlsafe(24),
        }
        ENV_FILE.write_text("\n".join(f"{key}={value}" for key, value in env.items()) + "\n")
        ENV_FILE.chmod(0o600)
    env.update(
        {
            "ALPHALENS_DATABASE_URL": f"postgresql+asyncpg://{env['ALPHALENS_LOCAL_PGUSER']}:{env['ALPHALENS_LOCAL_PGPASS']}@127.0.0.1:{PGPORT}/{env['ALPHALENS_LOCAL_PGDB']}",
            "ALPHALENS_MIGRATION_DATABASE_URL": f"postgresql+asyncpg://{env['ALPHALENS_LOCAL_PGUSER']}:{env['ALPHALENS_LOCAL_PGPASS']}@127.0.0.1:{PGPORT}/{env['ALPHALENS_LOCAL_PGDB']}",
            "ALPHALENS_REDIS_URL": f"redis://:{env['ALPHALENS_LOCAL_REDISPASS']}@127.0.0.1:{REDISPORT}/0",
        }
    )
    _ensure_services(env)
    _run([str(BACKEND / ".venv/bin/python"), "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=_base_env() | env)
    runtime_env = _base_env() | env
    pids = {
        "api": _start_process([str(BACKEND / ".venv/bin/uvicorn"), "app.prediction_api:app", "--host", "127.0.0.1", "--port", str(APIPORT)], name="api", env=runtime_env, cwd=BACKEND),
        "worker": _start_process([str(BACKEND / ".venv/bin/python"), "scripts/local_market_worker.py", "--checkpoint", str(CHECKPOINT), "--status", str(STATUS), "--source-identity", SOURCE_IDENTITY_DIGEST, "--warmup-limit", "250"], name="worker", env=runtime_env, cwd=BACKEND),
    }
    node_bin = Path.home() / ".nvm/versions/node/v22.23.3/bin"
    frontend_env = runtime_env | {
        "ALPHALENS_API_BASE_URL": f"http://127.0.0.1:{APIPORT}",
        # Next.js only exposes NEXT_PUBLIC_* variables to browser bundles.  The
        # server-rendered page can use ALPHALENS_API_BASE_URL, but client-side
        # polling must receive the same isolated local API endpoint explicitly.
        "NEXT_PUBLIC_ALPHALENS_API_BASE_URL": f"http://127.0.0.1:{APIPORT}",
        "ALPHALENS_LOCAL_DEMO_MODE": "true",
        "NEXT_PUBLIC_ALPHALENS_LOCAL_DEMO_MODE": "true",
        "PATH": f"{node_bin}:{os.environ.get('PATH', '')}",
    }
    npm = str(node_bin / "npm") if (node_bin / "npm").exists() else "npm"
    pids["frontend"] = _start_process([npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(FRONTENDPORT)], name="frontend", env=frontend_env, cwd=FRONTEND)
    PIDS.write_text(json.dumps({"ports": {"api": APIPORT, "frontend": FRONTENDPORT, "postgres": PGPORT, "redis": REDISPORT}, "pids": pids}, indent=2) + "\n")
    print(f"AlphaLens local stack started: http://127.0.0.1:{FRONTENDPORT}")


def stop() -> None:
    if PIDS.exists():
        record = json.loads(PIDS.read_text())
        for pid in record.get("pids", {}).values():
            _stop_process_group(int(pid))
        PIDS.unlink()
    postgres_bin = Path("/opt/homebrew/opt/postgresql@16/bin")
    pg_ctl = postgres_bin / "pg_ctl" if (postgres_bin / "pg_ctl").exists() else Path(shutil.which("pg_ctl") or "pg_ctl")
    if (PGDATA / "PG_VERSION").exists():
        _run([pg_ctl, "-D", str(PGDATA), "-m", "fast", "stop"], check=False)
    redis_pid = REDISDATA / "redis.pid"
    if redis_pid.exists() and _pid_alive(int(redis_pid.read_text())):
        os.kill(int(redis_pid.read_text()), signal.SIGTERM)
    print("AlphaLens local stack stopped; persistent local state was retained.")


def status() -> None:
    record = json.loads(PIDS.read_text()) if PIDS.exists() else {"pids": {}}
    print(json.dumps({"frontend_url": f"http://127.0.0.1:{FRONTENDPORT}", "pids_alive": {name: _pid_alive(int(pid)) for name, pid in record.get("pids", {}).items()}, "state_dir": str(STATE), "worker_status": json.loads(STATUS.read_text()) if STATUS.exists() else None}, indent=2, default=str))


if __name__ == "__main__":
    command = argparse.ArgumentParser()
    command.add_argument("command", choices=("start", "stop", "status"))
    args = command.parse_args()
    {"start": start, "stop": stop, "status": status}[args.command]()

