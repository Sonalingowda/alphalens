# AlphaLens Operational Validation

Status: isolated non-production validation only. No existing demo or localhost
database, Redis instance, collector, research artifact, or protected-test data
was used or changed.

Validation timestamp: 2026-10-23T20:13:30Z

## Candidate identity

- Branch: `release/local-candidate-20261024`
- Commit: `71796b815e9a8c0dfddd1d7ac1a28a673f87a8a1`
- Worktree: `/private/tmp/alphalens-local-release-candidate-20261024`
- Worktree status after commit: clean
- ORM metadata: `backend/app/persistence/models.py`
  - SHA-256 `caa85ea61fd4970b1f2b4548d189193c07a73f6c948f13aeaa1a22813e794d45`
- Python dependency declaration: `backend/pyproject.toml`
  - SHA-256 `549958cda8a13fdc019e3fe4e7b2ce44aae2b57158819719f9879dc1eb7e3610`
- Python lockfile: `backend/uv.lock`
  - SHA-256 `a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959`
- `pip-audit>=2.9.0` is included in the candidate dev dependency group.

## Migration graph and transaction behavior

- Alembic graph: one linear chain, 40 revisions, no branches.
- Head: `20261003_0040`.
- Disposable PostgreSQL image: pinned `postgres:16.8-alpine3.21` digest
  `sha256:3b057e1c2c6dfee60a30950096f3fab33be141dbb0fdd7af3d477083de94166c`.
- Isolated Compose project: `alphalens-ops-20261024`.
- Isolated volume: `alphalens-ops-20261024_alphalens_ops_postgres_20261024`.

Commands and outcomes:

```text
PYTHONPATH=. alembic upgrade head                 PASS
PYTHONPATH=. alembic current                     20261003_0040 (head)
PYTHONPATH=. alembic downgrade -1                PASS; current 20260929_0039
PYTHONPATH=. alembic upgrade head                 PASS; current 20261003_0040
PYTHONPATH=. alembic check                       PASS after ORM metadata repair
```

The initial `alembic check` identified real metadata drift: migration-owned
partial unique indexes and paper-record unique constraints were absent from the
ORM declarations. The candidate now declares those existing constraints and
indexes; no migration was rewritten or added. The final `alembic check` reports
`No new upgrade operations detected.`

## Persistence and backup/restore

- PostgreSQL head `20261003_0040` remained present after a disposable container
  restart.
- Redis image: `redis:7.4.2-alpine`; append-only persistence was enabled only in
  the disposable validation Compose project.
- A disposable Redis probe survived restart, and Redis returned `PONG` after
  restart.
- PostgreSQL custom-format backup SHA-256:
  `03cd2008de378bb79032127ab91e328a75c9e05432c76afc1dd0c95b8a6d426e`.
- The backup restored into a separate disposable database with migration head
  `20261003_0040` and 65 public tables.

No backup, restore, or restart touched an existing project volume.

## Least privilege

A disposable audit role was created only in the validation database:

```text
rolsuper=false
rolcreaterole=false
rolcreatedb=false
rolcanlogin=true
```

The role could read the schema and was denied schema creation. This proves the
candidate can operate with a non-superuser role, but it is not a production
least-privilege approval: its disposable grants were broad DML grants on the
current tables, and production role ownership/default privileges remain to be
reviewed separately.

## Redis failure recovery

- With Redis stopped, an API request returned HTTP 503 with
  `RATE_LIMITER_UNAVAILABLE`; request protection failed closed.
- After the disposable Redis service restarted, `PONG` returned and the API
  limiter became available again.
- Four concurrent requests against a two-request/60-second test limit produced
  two HTTP 200 responses and two HTTP 429 responses with `Retry-After: 60`.

## API contract and database-backed behavior

The correct production entrypoint was exercised: `app.prediction_api:app`, with
startup market-data acquisition explicitly disabled.

- `/health/readiness`: HTTP 200; PostgreSQL, Redis, and schema checks were
  `ready`.
- `/health` and `/api/v1/health`: HTTP 503 `ARTIFACT_UNAVAILABLE`; no approved
  inference artifact was fabricated or installed.
- `/api/v1/model`: HTTP 503 `ARTIFACT_UNAVAILABLE`.
- `/opportunities?instrument=BTCUSDT&timeframe=5m`: HTTP 200, genuine empty
  database-backed result, `coverage_status=unavailable`, zero items.
- `/markets/live?instrument=BTCUSDT&timeframe=5m`: HTTP 200, empty unavailable
  market snapshot; no external acquisition occurred during startup.
- `/api/v1/opportunities` without required query fields: HTTP 422
  `REQUEST_SCHEMA_INVALID`.
- `/api/v1/opportunities` with an empty requested scope: HTTP 404
  `entity.not_found`.
- `/api/v1/version`: HTTP 200 and `inference_mode=packaged_artifact_only`.

Requests carrying `X-Request-ID` returned matching `X-Request-ID` and
`X-Correlation-ID` headers. JSON logs contained the same identifiers and route
status. Uvicorn shutdown completed cleanly after SIGINT.

## Verification suites

Executed in the candidate backend project with Python 3.11.14 and `uv`:

```text
PYTHONPATH=. uv run --offline --group dev pytest tests -q
903 passed, 23 skipped, 497 subtests passed, 2 warnings

uv run --offline --group dev ruff check app tests
All checks passed

PYTHONPATH=. uv run --offline --group dev pytest \
  tests/test_clerk_paper_tracking.py \
  tests/test_production_infrastructure.py \
  tests/test_prediction_api.py \
  tests/test_deployment.py \
  tests/test_opportunity_api.py -q
67 passed, 1 warning
```

The warnings were a Starlette/httpx deprecation warning and an asyncpg
coroutine resource warning in an existing market-data test; neither caused a
test failure. The final security audit was:

```text
uv run --group dev pip-audit --progress-spinner off
No known vulnerabilities found
```

The audit found `certifi 2026.7.22` / `PYSEC-2026-4320` before repair; the
lockfile now contains `certifi 2026.10.23`.

## Remaining blockers

1. The production startup currently uses one database URL for both migrations
   and runtime. Separate migration/runtime roles and default privileges require
   a deployment-specific design and owner approval before production least
   privilege can be claimed.
2. No approved production inference artifact exists; health correctly remains
   unavailable and Section 6 remains not validated.
3. No production deployment, protected-test evaluation, or real trading-risk
   validation was performed.

This document is operational evidence for an isolated candidate only. It is
not production certification, Section 6 validation, or approval to deploy.
