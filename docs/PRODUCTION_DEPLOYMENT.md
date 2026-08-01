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

## Verification and rollback

- `/health/liveness` confirms the API process is responsive.
- `/health/readiness` confirms PostgreSQL, Redis, and schema readiness.
- `/metrics/prometheus` exports Prometheus metrics when enabled. The frozen API's `/metrics` contract remains unchanged.
- Application rollback SHALL use the previous immutable image only after confirming its schema compatibility. Schema rollback SHALL be exercised in staging and SHALL be preceded by a database backup.

This Compose topology is a reproducible reference deployment. Production operators SHOULD place PostgreSQL and Redis on managed private services and deploy application replicas behind a TLS load balancer.
