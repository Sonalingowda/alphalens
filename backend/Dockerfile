FROM ghcr.io/astral-sh/uv:0.12.0@sha256:606e70c71c852d03f611b1e56a195d08648507018a7057fab82c4974c4eae105 AS uv

FROM python:3.11.9-slim-bookworm@sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317 AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.11.9-slim-bookworm@sha256:8fb099199b9f2d70342674bd9dbccd3ed03a258f26bbd1d556822c6dfc60c317 AS runtime
ARG ALPHALENS_BUILD_GIT_SHA
ARG ALPHALENS_BUILD_APP_VERSION=1.0.0
ARG ALPHALENS_BUILD_TIME
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system --gid 10001 alphalens \
    && useradd --system --uid 10001 --gid alphalens --home /app alphalens
WORKDIR /app
RUN ALPHALENS_BUILD_GIT_SHA="${ALPHALENS_BUILD_GIT_SHA}" \
    ALPHALENS_BUILD_APP_VERSION="${ALPHALENS_BUILD_APP_VERSION}" \
    ALPHALENS_BUILD_TIME="${ALPHALENS_BUILD_TIME}" \
    python -c 'import json, os; payload = {"git_sha": os.getenv("ALPHALENS_BUILD_GIT_SHA") or None, "app_version": os.getenv("ALPHALENS_BUILD_APP_VERSION") or "1.0.0", "build_time": os.getenv("ALPHALENS_BUILD_TIME") or None}; open("/app/build-provenance.json", "w", encoding="utf-8").write(json.dumps(payload, sort_keys=True, separators=(",", ":")))'
COPY --from=dependencies /opt/venv /opt/venv
COPY --chown=alphalens:alphalens backend/alembic.ini ./
COPY --chown=alphalens:alphalens backend/alembic ./alembic
COPY --chown=alphalens:alphalens backend/app ./app
COPY --chown=alphalens:alphalens backend/scripts ./scripts
RUN chmod 0555 ./scripts/start-production.sh
USER alphalens
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.getenv('ALPHALENS_API_PORT', os.getenv('PORT', '8000')); urllib.request.urlopen(f'http://127.0.0.1:{port}/health/readiness', timeout=3)"
ENTRYPOINT ["./scripts/start-production.sh"]
