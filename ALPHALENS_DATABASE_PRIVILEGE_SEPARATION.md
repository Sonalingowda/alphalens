# AlphaLens Database Privilege Separation

Status: ISOLATED CANDIDATE VERIFIED. Production-role verification remains
deferred until authorized staging access exists.

## Provenance

- Worktree: `/private/tmp/alphalens-local-release-candidate-20261024`
- Branch before this report commit: `release/local-candidate-20261024`
- Previous candidate commit: `6ee4989567a961f277080874548b3d63a5bfca90`
- Original dirty repository, demo data, research evidence, and Section 6
  collector were not modified.
- No production credentials were requested, read, printed, or stored.

## Configuration contract

- `ALPHALENS_DATABASE_URL` is the application/runtime URL.
- `ALPHALENS_MIGRATION_DATABASE_URL` is the schema-migration URL.
- Alembic selects the migration URL when present and otherwise retains the
  development fallback to the runtime URL.
- Production settings now fail closed unless the migration URL exists and its
  database username differs from the runtime username.
- Secret-file variants are supported for both URLs using the existing
  `*_FILE` convention.
- `backend/scripts/start-production.sh` still runs `alembic upgrade head`
  before readiness and application startup; the command now resolves the
  separate migration credential through Alembic configuration.
- Production Compose injects the migration URL only into the backend service.
  The worker receives only the runtime environment and cannot access the
  migration credential.

## Disposable role validation

Validation used the already isolated local PostgreSQL service and a new
disposable database. Roles were created with `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, and `NOREPLICATION`; passwords are intentionally omitted.

- Migration role: `alphalens_migrator_20261024`.
- Runtime role: `alphalens_runtime_20261024`.
- Disposable database: `alphalens_privilege_20261024`.
- Existing demo and research databases were not used.

Observed results:

- Alembic `upgrade head` completed using only the migration URL.
- Migration role reached the expected head `20261003_0040`.
- Runtime role could read the migration metadata and perform granted DML.
- Runtime `CREATE TABLE` was denied.
- Runtime `ALTER TABLE` was denied.
- Migration-owned disposable schema changes succeeded.
- Alembic `downgrade -1`, `upgrade head`, and `alembic check` completed after
  removing the temporary probe table.
- Runtime-only API startup with no migration URL succeeded.
- `/health/readiness` returned HTTP 200 with PostgreSQL, Redis, and schema
  ready.
- `/health` returned the truthful HTTP 503 `ARTIFACT_UNAVAILABLE`; no model
  artifact was created or promoted.

## Verification commands and results

```text
PYTHONPATH=. uv run alembic upgrade head                 PASS
PYTHONPATH=. uv run alembic downgrade -1                PASS
PYTHONPATH=. uv run alembic upgrade head                 PASS
PYTHONPATH=. uv run alembic check                        PASS
PYTHONPATH=. uv run --group dev pytest tests -q          PASS
                                                   905 passed, 23 skipped,
                                                   497 subtests, 2 warnings
uv run --group dev ruff check app tests                   PASS
uv run --group dev pip-audit --progress-spinner off      PASS
docker compose ... config --quiet                         PASS
```

The production Compose render confirmed:

- backend has `ALPHALENS_MIGRATION_DATABASE_URL`;
- worker does not have `ALPHALENS_MIGRATION_DATABASE_URL`.

## Files changed

- `backend/app/settings.py`
- `backend/alembic/env.py`
- `backend/.env.example`
- `backend/.env.production.example`
- `backend/tests/test_deployment.py`
- `backend/tests/test_production_infrastructure.py`
- `docker-compose.production.yml`

No migration file was changed. No database schema or existing persistent data
was changed outside the disposable validation database.

## Remaining authorization and deployment requirements

- An owner/operator must provision distinct production roles and secrets in the
  managed PostgreSQL environment.
- The migration role must be granted only the schema privileges required by
  the approved migration set; the runtime role must receive only application
  DML and sequence privileges.
- Production role verification requires authorized staging access and must be
  performed against the exact intended managed schema.
- No production deployment, migration, credential rotation, or real database
  connection was performed by this task.

This document does not certify production readiness, Section 6, Gate 7, or any
protected-test requirement.
