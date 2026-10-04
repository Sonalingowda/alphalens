# AlphaLens Production Deployment

## Scope

This guide deploys the read-only Live Prediction API, AlphaLens Dashboard, and
PostgreSQL. Deployment never trains or modifies a model, changes research
artifacts, connects to a broker, or seeds fabricated data.

The API starts only when:

1. environment configuration is valid;
2. all Alembic migrations are current;
3. PostgreSQL is reachable; and
4. the immutable production Ridge artifact loads and passes hash verification.

A newly created empty database therefore is not ready for traffic. Restore the
approved production database before starting the API and frontend.

## Prerequisites

Local processes require Python 3.11, `uv`, Node.js 22, npm, and PostgreSQL 16.
Container deployment requires Docker Engine with Docker Compose v2.

Never store production credentials in Git. Environment examples contain
placeholders only.

## Environment Variables

The root [`.env.example`](.env.example) supplies Docker Compose variables.
Copy it to the Git-ignored `.env` and populate:

| Variable | Purpose |
| --- | --- |
| `POSTGRES_DB` | PostgreSQL database name. |
| `POSTGRES_USER` | Dedicated application/database owner. |
| `POSTGRES_PASSWORD` | Required non-placeholder secret. Use a URL-safe value because Compose embeds it in the async database URL. |
| `ALPHALENS_CORS_ALLOWED_ORIGINS` | Comma-separated HTTPS dashboard origins; no wildcard or localhost in production. |
| `ALPHALENS_API_WORKERS` | Uvicorn worker count, from 1 through 16. |
| `ALPHALENS_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `ALPHALENS_BIND_ADDRESS` | Host interface for published ports. It defaults to `127.0.0.1`; use a trusted reverse proxy for public access. |

Backend settings are documented in
[`backend/.env.production.example`](backend/.env.production.example).
Frontend settings are documented in
[`frontend/.env.production.example`](frontend/.env.production.example).

Production validation rejects:

- loopback-only API binding;
- missing, placeholder, or malformed database credentials;
- wildcard, duplicate, malformed, or localhost CORS origins;
- unsupported log levels;
- invalid worker counts, ports, timeouts, page limits, or request limits; and
- database URLs that are not `postgresql+asyncpg`.

## Local Deployment

Install the backend from the lockfile:

```shell
cd backend
uv sync --frozen --no-dev
cp .env.production.example .env.production
set -a
. ./.env.production
set +a
uv run python -m app.startup configuration
uv run alembic upgrade head
uv run python -m app.startup readiness
uv run uvicorn app.prediction_api:app \
  --host "$ALPHALENS_API_HOST" \
  --port "$ALPHALENS_API_PORT" \
  --workers "$ALPHALENS_API_WORKERS" \
  --no-access-log \
  --no-server-header \
  --no-proxy-headers
```

In a separate process:

```shell
cd frontend
npm ci
cp .env.production.example .env.production.local
npm run build
npm start
```

The dashboard is served on port `3000`; the API is served on port `8000`.

## Docker Deployment

Create the runtime environment without committing it:

```shell
cp .env.example .env
```

Set a strong URL-safe `POSTGRES_PASSWORD` and the real HTTPS dashboard origin.
Validate the resolved Compose model:

```shell
docker compose config --quiet
```

On first deployment, start PostgreSQL alone:

```shell
docker compose up -d postgres
docker compose ps
```

Restore the approved production backup as described below. Then build and
start the application:

```shell
docker compose build --pull
docker compose up -d
docker compose ps
```

Both application containers run as unprivileged users, drop Linux
capabilities, prevent privilege escalation, use read-only root filesystems,
and expose only ports `3000` and `8000` on the configured bind address.
PostgreSQL is not published to the host.

## Database Migration

The backend startup script runs `alembic upgrade head` before accepting
traffic. To run or inspect migrations explicitly:

```shell
docker compose run --rm --entrypoint alembic backend upgrade head
docker compose run --rm --entrypoint alembic backend current
```

Migrations are additive schema operations. They do not manufacture model,
research, prediction, or trading evidence.

## Production Startup and Health

The backend startup sequence validates configuration, applies migrations,
verifies database connectivity and the immutable artifact, and then executes
Uvicorn. Any failed check terminates the container.

Health and monitoring endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/health` | Database and immutable artifact readiness. |
| `GET /api/v1/version` | API version and read-only mode. |
| `GET /api/v1/metrics` | Request, error, prediction, and latency counters. |
| `GET /api/v1/resources` | Process uptime, CPU usage, and maximum resident memory. |
| Dashboard `/system-health` | End-to-end frontend rendering and API status. |

Verify:

```shell
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail http://127.0.0.1:8000/api/v1/resources
curl --fail http://127.0.0.1:3000/system-health
docker compose logs --tail=100 backend frontend
```

Production logs are newline-delimited JSON on standard output/error. Collect
them with the platform log driver. Do not log request bodies, feature values,
database credentials, or environment contents.

## Backup Strategy

Back up the complete PostgreSQL database because provenance, artifacts,
audits, reports, and operational evidence are relationally linked.

Recommended policy:

1. Run scheduled PostgreSQL custom-format backups with `pg_dump --format=custom`.
2. Encrypt backups at rest and in transit.
3. Store them outside the deployment host with restricted access.
4. Record a SHA-256 checksum and UTC creation time for every backup.
5. Retain daily, weekly, and monthly generations according to organizational
   retention requirements.
6. Perform periodic restore drills into an isolated PostgreSQL instance.
7. Verify migrations, artifact hashes, API readiness, and canonical provenance
   after every drill.

Example backup streamed to a protected operator path:

```shell
docker compose exec -T postgres \
  pg_dump --format=custom --no-owner \
  --username "$POSTGRES_USER" "$POSTGRES_DB" \
  > alphalens-production.dump
sha256sum alphalens-production.dump
```

The dump and checksum are sensitive operational artifacts and must never be
committed.

## Recovery Procedure

1. Stop backend and frontend traffic while leaving PostgreSQL available:

   ```shell
   docker compose stop frontend backend
   ```

2. Verify the selected backup's stored SHA-256 checksum.
3. Restore into a new empty database or isolated recovery instance. Do not
   overwrite the current database until the recovered copy is verified:

   ```shell
   docker compose exec -T postgres \
     pg_restore --no-owner --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     < alphalens-production.dump
   ```

4. Apply pending migrations and verify the immutable artifact:

   ```shell
   docker compose run --rm --entrypoint alembic backend upgrade head
   docker compose run --rm --entrypoint python backend \
     -m app.startup readiness
   ```

5. Start the API, confirm `/api/v1/health`, then start and confirm the
   dashboard.
6. Retain the pre-recovery database and all recovery logs until human review
   confirms provenance, record counts, artifact hashes, and audit continuity.

Never use recovery to rewrite, delete, or silently replace historical
experimental evidence.

## Artifact release boundary

Artifact existence never authorizes a release. The external controlled release
manifest must bind the artifact ID and SHA-256, Ridge model/configuration,
feature and target versions, dataset and validation lineage, split hash,
holdout report and irreversible consumption status, deterministic prediction
hash, target identity, operator, approval timestamp, intended action, backup
checksum, and rollback reference. Its own SHA-256 and explicit human approval
are required before import.

Before any future release, the operator must create and checksum a complete
PostgreSQL backup, run the read-only target identity check, independently run
the shared fail-closed lineage verifier, and validate the release manifest.
The target check does not print credentials or mutate the target:

```shell
cd backend
uv run python scripts/transfer_approved_state.py verify-target \
  --url "$TARGET_DATABASE_URL" --manifest /secure/release-manifest.json
```

Only then may the approved transfer preflight run. Transfer is an atomic,
idempotent import-for-release-review and rejects conflicting identity or hash.

For a new production database, use the canonical fresh-target bootstrap after
the database has reached the current Alembic head:

```shell
cd backend
uv run python scripts/transfer_approved_state.py bootstrap-release \
  --url "$TARGET_DATABASE_URL" \
  --closure /secure/approved-closure.json \
  --manifest /secure/render-release-manifest.json
```

The closure and manifest must be produced by the approved release process. The
manifest must bind the approved artifact, its complete parent closure (closure
hash, row-binding hash, record count, and source schema heads), the exact target
database identity, backup, rollback reference, and human release approval.
`bootstrap-release` accepts an empty target closure, inserts the closure and
activates the already-verified artifact in one transaction, then loads it
through the production readiness verifier. An exact repeat is a verified
no-op; partial or conflicting state is rejected. It does not create or modify
artifact content. The legacy `restore-release` command remains reserved for the
controlled replacement path with its explicitly bound predecessor.

After transfer, recheck the artifact hash and parent closure. Deploy an
immutable compatible application image, validate startup/readiness, and run a
controlled prediction smoke test. For replacement transfers, activation is
separate and requires a second explicit human release sign-off; the fresh-target
bootstrap is itself the explicitly approved activation transaction. Deployment
and artifact existence must never activate live inference automatically.

Monitor readiness, artifact identity/hash, prediction errors, latency, and
logs. A rollback trigger is any failed integrity/readiness check, unexpected
identity/hash, failed smoke test, or authorized operational stop. Normal
rollback restores the previous immutable artifact reference and compatible
image, then verifies the previous artifact ID/hash, readiness, and controlled
prediction and records the result. Database restoration is the fallback
recovery mechanism, not the normal artifact replacement path; restore only
into an isolated recovery target first and repeat readiness and deterministic
replay checks before traffic resumes.

The transfer command never deploys or activates an artifact.

## CI/CD

GitHub Actions run independently for:

- backend locked installation, Ruff linting, compilation, and tests;
- frontend locked installation, ESLint, type checking, tests, and production
  build; and
- Compose validation plus backend and frontend Docker image builds.

The workflows build images only. Publishing to a registry or deploying to an
environment requires separately approved credentials and release policy.

## Security Checklist

- No `.env`, database dump, private key, token, or credential is committed.
- Production database passwords and CORS origins are explicitly supplied.
- The prediction API exposes no training, fitting, tuning, broker, or
  configuration-mutation endpoint.
- Request bodies are bounded and schema validated.
- CORS is allowlist-only and credential-free.
- API responses disable caching.
- Containers run unprivileged with minimized capabilities.
- PostgreSQL is isolated from host networking.
- A trusted TLS-terminating reverse proxy should be placed in front of public
  services; TLS certificate management is environment-specific and is not
  stored in this repository.
