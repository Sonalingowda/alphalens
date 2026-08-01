# AlphaLens Environment Variable Reference

All variables are validated at process startup. `ALPHALENS_DATABASE_URL` and `ALPHALENS_REDIS_URL` also support a mutually exclusive `_FILE` suffix for Docker/Kubernetes secret mounts.

| Variable | Purpose | Default |
|---|---|---|
| `ALPHALENS_ENVIRONMENT` | `development`, `test`, `staging`, or `production` | `development` |
| `ALPHALENS_API_NAME` | OpenAPI application name | `AlphaLens API` |
| `ALPHALENS_API_HOST` | Bind address | `127.0.0.1` |
| `ALPHALENS_API_PORT` | API port | `8000` |
| `ALPHALENS_API_WORKERS` | Uvicorn process count, 1–16 | `1` |
| `ALPHALENS_LOG_LEVEL` | Structured log level | `INFO` |
| `ALPHALENS_CORS_ALLOWED_ORIGINS` | Comma-separated exact HTTP(S) origins | local frontend origins |
| `ALPHALENS_DATABASE_URL` | SQLAlchemy async PostgreSQL URL | local development URL |
| `ALPHALENS_DATABASE_URL_FILE` | File containing the database URL | unset |
| `ALPHALENS_DATABASE_POOL_SIZE` | Persistent async connection pool size, 1–100 | `5` |
| `ALPHALENS_DATABASE_MAX_OVERFLOW` | Temporary overflow connections, 0–200 | `10` |
| `ALPHALENS_DATABASE_POOL_TIMEOUT_SECONDS` | Pool checkout timeout, 1–300 seconds | `30` |
| `ALPHALENS_REDIS_URL` | Redis or TLS Redis URL | local Redis URL |
| `ALPHALENS_REDIS_URL_FILE` | File containing the Redis URL | unset |
| `ALPHALENS_METRICS_ENABLED` | Expose Prometheus endpoint | `true` |
| `ALPHALENS_WORKER_CONCURRENCY` | Worker task concurrency, 1–64 | `2` |
| `ALPHALENS_WORKER_POLL_SECONDS` | Queue polling interval | `1` |
| `ALPHALENS_WORKER_MAX_RETRIES` | Infrastructure retry limit, 0–20 | `3` |
| `ALPHALENS_MARKET_DATA_BASE_URL` | Historical source base URL | Kraken public API |
| `ALPHALENS_MARKET_DATA_TIMEOUT_SECONDS` | Source request timeout | `10` |
| `ALPHALENS_HISTORY_BACKFILL_START` | Earliest UTC backfill timestamp | `2010-01-01T00:00:00Z` |
| `ALPHALENS_HISTORY_BACKFILL_MAX_PAGES` | Backfill safety bound | `100` |
| `ALPHALENS_PREDICTION_API_MAX_REQUEST_BYTES` | Request-size limit | `32768` |
| `POSTGRES_DB` | Compose PostgreSQL database | `alphalens` |
| `POSTGRES_USER` | Compose PostgreSQL role | `alphalens` |
| `POSTGRES_PASSWORD` | Compose PostgreSQL password | development-only value |
| `REDIS_PASSWORD` | Compose Redis password | development-only value |

Production rejects loopback binding, localhost CORS, placeholder database credentials, and missing or placeholder Redis credentials. Secrets SHALL NOT be committed.
