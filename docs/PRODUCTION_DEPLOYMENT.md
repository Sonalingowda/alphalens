# AlphaLens Production Deployment Guide

## Deployment contract

Deployments MUST use immutable application image tags, externally managed secrets, durable PostgreSQL storage, and the frozen schema migration graph. Redis MUST remain non-canonical. TLS termination, network policy, backups, and secret rotation belong to the deployment environment.

## Preparation

1. Copy the variable names from `backend/.env.production.example` into a secret manager or a root-readable deployment environment file.
2. Use strong, URL-safe PostgreSQL and Redis credentials. If credentials contain reserved URI characters, percent-encode them before constructing URLs.
3. Set an explicit HTTPS CORS origin and a non-loopback bind address.
4. Back up PostgreSQL and verify restore procedures before migrating.
5. Ensure the approved immutable production model artifact required by the frozen prediction API is present.

## Compose deployment

The production override enforces required secrets:

```console
docker compose --env-file /secure/path/alphalens.env \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  config --quiet
docker compose --env-file /secure/path/alphalens.env \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  up --detach --build --wait
```

The backend startup sequence validates configuration, applies migrations, verifies PostgreSQL, verifies Redis, checks the migration head, validates the production artifact, and only then starts Uvicorn. A failure terminates startup.

Release images MUST embed the exact committed source SHA, application version,
and UTC build timestamp through the backend Docker build arguments
`ALPHALENS_BUILD_GIT_SHA`, `ALPHALENS_BUILD_APP_VERSION`, and
`ALPHALENS_BUILD_TIME`. The readiness response exposes them under `build`;
missing SHA or timestamp values remain `null` and are never inferred from a
mutable runtime working tree.

## Verification and rollback

- `/health/liveness` confirms the API process is responsive.
- `/health/readiness` confirms PostgreSQL, Redis, and schema readiness.
- `/metrics/prometheus` exports Prometheus metrics when enabled. The frozen API's `/metrics` contract remains unchanged.
- Application rollback SHALL use the previous immutable image only after confirming its schema compatibility. Schema rollback SHALL be exercised in staging and SHALL be preceded by a database backup.

## Release authorization and artifact replacement

The packaged artifact is not an authorization signal. A controlled external
release manifest must be explicitly approved by a human and must bind the
artifact ID/hash, Ridge model/configuration, feature and target versions,
dataset/validation/split lineage, holdout report and one-time consumption,
deterministic prediction hash, target-production identity, operator, approval
timestamp, intended action, backup checksum, and rollback reference. The
manifest's own SHA-256 is verified before import. Missing approval, tampering,
target mismatch, or any lineage mismatch fails closed.

The future sequence is:

1. Pre-release: take and checksum a complete PostgreSQL backup; verify the
   target identity with the read-only `verify-target` command in
   `DEPLOYMENT.md`; verify the artifact hash and complete lineage; validate the
   release manifest and its explicit approval.
2. Transfer: run the approved import-for-release-review; verify the transferred
   artifact hash and parent closure; confirm that repeating the transfer is
   idempotent and that conflicting identity is rejected.
3. Deploy: deploy an immutable application image compatible with the verified
   schema; validate startup and readiness.
4. Verify: check health, model/artifact identity, logs, and monitoring, then
   run a controlled prediction smoke test against the verified artifact.
5. Activate: obtain explicit human release sign-off, then activate separately.
   Artifact existence and deployment never activate live inference.

Rollback is triggered by any integrity, readiness, identity/hash, smoke-test,
or authorized operational failure. The exact normal operation is to stop
activation, restore the previous immutable artifact reference, and redeploy the
compatible previous image; then verify the previous artifact ID/hash,
readiness, and controlled prediction and record the rollback result. Database
restoration remains the fallback recovery mechanism, not the normal replacement
path: restore the preserved backup into an isolated recovery target, verify the
schema and deterministic lineage there, and only then follow the release
sign-off process for any recovery action.

This Compose topology is a reproducible reference deployment. Production operators SHOULD place PostgreSQL and Redis on managed private services and deploy application replicas behind a TLS load balancer.
