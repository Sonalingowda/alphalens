"""Read-only local release-readiness checks.

This command emits a secret-free evidence manifest and never writes to
PostgreSQL, Redis, market-data tables, model artifacts, or deployment targets.
Blocked scientific/deployment prerequisites remain explicit BLOCKED results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EXPECTED_BRANCH = "gate9d2/owner-infrastructure-20261105"
EXPECTED_SOURCE_SHA256 = (
    "f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc"
)
def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _http_status(url: str, *, method: str = "GET") -> tuple[str, str]:
    try:
        request = Request(url, method=method)
        with urlopen(request, timeout=3) as response:
            return "PASS", str(response.status)
    except HTTPError as error:
        return "HTTP", str(error.code)
    except URLError as error:
        return "UNKNOWN", type(error).__name__
    except OSError as error:
        return "UNKNOWN", type(error).__name__


def run(*, source: Path | None, backend: str | None) -> dict[str, object]:
    checks: list[dict[str, str]] = []
    branch = _git("branch", "--show-current")
    sha = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    checks.append(_check("repository_branch", "PASS" if branch == EXPECTED_BRANCH else "FAIL", branch))
    checks.append(_check("repository_clean", "PASS" if not dirty else "FAIL", "clean" if not dirty else "dirty"))

    if source is not None and source.exists():
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        source_status = "PASS" if digest == EXPECTED_SOURCE_SHA256 else "FAIL"
        checks.append(_check("development_source_hash", source_status, digest))
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            identity_ok = (
                payload.get("symbol") == "BTCUSDT"
                and payload.get("timeframe") == "5m"
                and payload.get("candle_count") == 25_920
            )
            checks.append(_check("development_source_identity", "PASS" if identity_ok else "FAIL", "BTCUSDT/5m/25920"))
        except (OSError, ValueError):
            checks.append(_check("development_source_identity", "FAIL", "invalid JSON"))
    else:
        checks.append(_check("development_source_hash", "UNKNOWN", "source unavailable"))

    if backend:
        readiness, readiness_detail = _http_status(f"{backend}/health/readiness")
        model, model_detail = _http_status(f"{backend}/health")
        protected, protected_detail = _http_status(f"{backend}/api/v1/paper-tracking/confirmation")
        checks.extend(
            [
                _check("backend_readiness", readiness if readiness == "PASS" and readiness_detail == "200" else readiness, readiness_detail),
                _check("model_fail_closed", "PASS" if model == "HTTP" and model_detail == "503" else "BLOCKED", f"status={model_detail}"),
                _check("protected_boundary", "PASS" if protected == "HTTP" and protected_detail == "401" else "BLOCKED", f"status={protected_detail}"),
            ]
        )

    checks.extend(
        [
            _check("gate06", "BLOCKED", "frozen criteria and protected evaluation unresolved"),
            _check("gate07", "BLOCKED", "validated model artifact unavailable"),
            _check("gate08", "BLOCKED", "no approved staging/deployment evidence"),
            _check("gate09", "BLOCKED", "mandatory gates and owner sign-off incomplete"),
        ]
    )
    overall = "PASS" if all(item["status"] == "PASS" for item in checks) else "BLOCKED"
    return {"schema": "alphalens.release-readiness.v1", "git_sha": sha, "checks": checks, "overall": overall}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Explicit permitted source artifact; omitted means UNKNOWN, never an implicit protected path",
    )
    parser.add_argument("--backend", default=None, help="Optional local backend origin, e.g. http://127.0.0.1:18000")
    args = parser.parse_args()
    print(json.dumps(run(source=args.source, backend=args.backend), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
