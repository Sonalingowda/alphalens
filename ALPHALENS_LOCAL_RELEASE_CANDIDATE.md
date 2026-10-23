# AlphaLens Local Release Candidate

Status: isolated engineering candidate; not production-certified.

Source branch: `release/local-candidate-20261024`

This candidate contains reviewed runtime/API/UI/reliability changes from the dirty
working tree. Section 6 research scripts, historical results, evidence, receipts,
credentials, and generated directories are intentionally excluded.

## Reproducible local startup

Use Node 22.23.3 as declared by `.node-version` and `frontend/package.json`.

Start or verify isolated PostgreSQL and Redis with a unique Compose project. Do not
use the generic `alphalens` project or shared volumes:

```sh
export COMPOSE_PROJECT_NAME=alphalens-local-release-candidate-20261024
docker compose -f docker-compose.yml config --quiet
```

For a host-process backend, source a local ignored environment file explicitly and
keep startup market-data acquisition disabled:

```sh
set -a
. ./backend/.env
set +a
export PYTHONPATH="$PWD/backend"
backend/.venv/bin/python -m app.startup configuration
backend/.venv/bin/python -m app.startup readiness
backend/.venv/bin/uvicorn app.prediction_api:app \
  --host 127.0.0.1 --port 18000 --workers 1 \
  --no-access-log --no-server-header --no-proxy-headers
```

Start the worker in a separate terminal with the same environment:

```sh
set -a
. ./backend/.env
set +a
export PYTHONPATH="$PWD/backend"
backend/.venv/bin/python -m app.background_worker
```

Start the frontend with Node 22 and the isolated API URL:

```sh
export ALPHALENS_API_BASE_URL=http://127.0.0.1:18000
export NEXT_PUBLIC_ALPHALENS_API_BASE_URL=http://127.0.0.1:18000
npm ci
npm run dev -- --turbopack --hostname 127.0.0.1 --port 13000
```

The frontend requires an authorized Clerk development `pk_test_` key in an ignored
`.env.local`; no credential belongs in this candidate.

## Verification boundary

`/health/readiness` must report PostgreSQL, Redis, and schema readiness. `/health`
must remain `503 ARTIFACT_UNAVAILABLE` until an approved inference artifact exists.
No model fitting, protected-test access, research validation, production promotion,
or Command 4/4 is authorized by this candidate.
