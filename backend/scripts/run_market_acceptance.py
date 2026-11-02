"""Run one explicit, bounded Binance continuity acceptance observation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Any


DEFAULT_DURATION_SECONDS = 6 * 60 * 60
POLL_SECONDS = 10


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--duration-seconds", type=int, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--warmup-limit", type=int, default=250)
    parser.add_argument("--max-recoverable-gap-intervals", type=int, default=120)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    return parser


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _backup_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_backup(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Backup is missing or empty: {path}")
    restore = shutil.which("pg_restore")
    if restore is None:
        raise RuntimeError("pg_restore is required to verify the acceptance backup.")
    result = subprocess.run(
        [restore, "--list", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Backup archive verification failed: {path}")
    return _backup_sha256(path)


def _run_schema_migrations(python: Path, environment: dict[str, str]) -> None:
    """Bring the explicitly configured database to the reviewed Alembic head."""
    backend_directory = Path(__file__).resolve().parents[1]
    python_executable = python.resolve()
    result = subprocess.run(
        [str(python_executable), "-m", "alembic", "upgrade", "head"],
        cwd=backend_directory,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(
            "Database migration preflight failed: "
            + (detail[-1] if detail else "unknown Alembic error")
        )


def _stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _write_reports(
    report_dir: Path,
    *,
    report: dict[str, Any],
    samples: list[dict[str, Any]],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "continuity-acceptance.json").write_text(
        json.dumps({**report, "samples": samples}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    counters = report.get("final_counters", {})
    checkpoint = report.get("final_checkpoint", {})
    lines = [
        "# AlphaLens Binance Continuity Acceptance",
        "",
        f"- Result: **{report['result']}**",
        f"- Started: `{report['started_at']}`",
        f"- Ended: `{report['ended_at']}`",
        f"- Duration seconds: `{report['observed_duration_seconds']}`",
        f"- Requested duration seconds: `{report['requested_duration_seconds']}`",
        f"- Backup SHA-256: `{report['backup_sha256']}`",
        "",
        "## Worker evidence",
        "",
        f"- Final worker state: `{report['final_worker_status']}`",
        f"- Finalized candles: `{counters.get('finalized_candles', 0)}`",
        f"- Reconnects: `{report.get('reconnect_count', 0)}`",
        f"- Checkpoint sequence: `{checkpoint.get('sequence', 'Unavailable')}`",
        f"- Last committed candle: `{checkpoint.get('last_committed_open_time', 'Unavailable')}`",
        f"- Gap status: `{checkpoint.get('status', 'Unavailable')}`",
        f"- Early termination reason: `{report.get('early_termination_reason') or 'None'}`",
        "",
        "This report is operational evidence only. It does not establish predictive accuracy, profitability, or model validation.",
    ]
    (report_dir / "continuity-acceptance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = _parser().parse_args()
    if args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be positive")
    caffeinate = shutil.which("caffeinate")
    if caffeinate is None:
        raise SystemExit("macOS caffeinate is required; refusing to start observation")
    checkpoint = args.state_dir / "checkpoint.json"
    status = args.state_dir / "worker-status.json"
    log_path = args.report_dir / "worker.log"
    args.report_dir.mkdir(parents=True, exist_ok=True)
    backup_hash = _verify_backup(args.backup)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.setdefault("PYTHONPATH", str(Path(__file__).resolve().parents[1]))
    python_executable = args.python.resolve()
    _run_schema_migrations(python_executable, environment)
    command = [
        str(python_executable),
        str(Path(__file__).with_name("local_market_worker.py")),
        "--checkpoint",
        str(checkpoint),
        "--status",
        str(status),
        "--source-identity",
        args.source_identity,
        "--warmup-limit",
        str(args.warmup_limit),
        "--max-recoverable-gap-intervals",
        str(args.max_recoverable_gap_intervals),
    ]
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    samples: list[dict[str, Any]] = []
    process: subprocess.Popen[bytes] | None = None
    caffeinate_process: subprocess.Popen[bytes] | None = None
    early_reason: str | None = None
    observation_ended_monotonic = started_monotonic
    try:
        with log_path.open("ab") as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            caffeinate_process = subprocess.Popen([caffeinate, "-dimsu", "-w", str(process.pid)])
            deadline = time.monotonic() + args.duration_seconds
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    early_reason = f"worker_exit_{process.returncode}"
                    break
                snapshot = _read_json(status)
                if snapshot is not None:
                    samples.append({"observed_at": _utc_now(), "status": snapshot})
                    checkpoint_state = snapshot.get("checkpoint", {})
                    if checkpoint_state.get("gap_status") == "QUARANTINED":
                        early_reason = "quarantine_integrity_failure"
                        break
                time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        early_reason = "operator_interrupt"
    finally:
        observation_ended_monotonic = time.monotonic()
        _stop(process)
        _stop(caffeinate_process)
    ended_at = _utc_now()
    observed_duration = round(observation_ended_monotonic - started_monotonic, 3)
    final_status = _read_json(status) or {}
    final_checkpoint = _read_json(checkpoint) or {}
    result = "PASS" if early_reason is None and observed_duration >= args.duration_seconds else "PARTIAL"
    report = {
        "result": result,
        "started_at": started_at,
        "ended_at": ended_at,
        "observed_duration_seconds": observed_duration,
        "requested_duration_seconds": args.duration_seconds,
        "backup_path": str(args.backup),
        "backup_sha256": backup_hash,
        "final_worker_status": final_status.get("worker_status", "Unavailable"),
        "final_counters": final_status.get("counters", {}),
        "reconnect_count": final_status.get("connection", {}).get("reconnect_count", 0),
        "final_checkpoint": final_checkpoint,
        "early_termination_reason": early_reason,
        "log_path": str(log_path),
    }
    _write_reports(args.report_dir, report=report, samples=samples)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if result == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
