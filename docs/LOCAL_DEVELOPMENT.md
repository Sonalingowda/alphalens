# AlphaLens Local Development Guide

## Scope

This guide starts the frozen AlphaLens API and frontend with PostgreSQL and Redis. PostgreSQL is the canonical store. Redis is limited to cache and runtime coordination.

## Prerequisites

- Docker Engine with Compose v2
- Git

## Start

From the repository root, run:

```console
docker compose up --build --wait
```

The API is available at `http://127.0.0.1:8000`, its Prometheus metrics at `/metrics/prometheus`, and the frontend at `http://127.0.0.1:3000`. The backend applies Alembic migrations before accepting traffic. Readiness requires PostgreSQL, Redis, and the current Alembic head.

Inspect status with `docker compose ps` and logs with `docker compose logs --follow backend worker`. Stop and retain PostgreSQL data with `docker compose down`; add `--volumes` only when intentionally discarding local data.

## Host-side verification

Backend commands run from `backend/`:

```console
uv sync --frozen --dev
uv run ruff check app tests
uv run python -m compileall -q app tests
uv run python -m unittest discover -s tests -p 'test_*.py'
```

Frontend commands run from `frontend/`:

```console
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

No development service is authorized to write canonical business records to Redis.
