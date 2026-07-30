#!/bin/sh
set -eu

python -m app.startup configuration
alembic upgrade head
python -m app.startup readiness

exec uvicorn app.prediction_api:app \
  --host "${ALPHALENS_API_HOST}" \
  --port "${ALPHALENS_API_PORT}" \
  --workers "${ALPHALENS_API_WORKERS}" \
  --no-access-log \
  --no-server-header \
  --no-proxy-headers
