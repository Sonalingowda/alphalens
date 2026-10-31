# AlphaLens Batch 6AA — Localhost Verification

## Recovered stack

The isolated recovery state is `/private/tmp/alphalens-batch6aa-local-recovery`. The recovered stack is running on the requested owner-facing ports:

- Frontend: `http://127.0.0.1:13003/` — HTTP 200
- API runtime status: `http://127.0.0.1:18003/api/v1/local-runtime/status` — HTTP 200
- Live market endpoint: `/markets/live?instrument=BTCUSDT&timeframe=5m` — HTTP 200
- PostgreSQL: `127.0.0.1:55460` — accepting connections
- Redis: `127.0.0.1:56397` — accepting connections

The market response carries Binance source artifact IDs, integrity digests and a result hash. The runtime status reports `persistence_status=AVAILABLE`, `gap_status=CLEAR`, `closed_candles_only=true`, `trading=false`, and `model_artifact_status=UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT`. `/health` remains truthful and returns `503 ARTIFACT_UNAVAILABLE`; this is not hidden or reclassified as an infrastructure defect.

The recovered worker's bounded smoke evidence recorded genuine finalized candles, 13 pipeline runs, 36 reconnects and durable checkpoint progression. It ultimately quarantined an unverifiable five-hour gap; this is fail-closed behavior, not a replacement long-running observation. The isolated worker was stopped after quarantine while PostgreSQL, Redis, API and frontend remained running.

## UI and browser-facing configuration

The frontend received the isolated API base URL through `NEXT_PUBLIC_ALPHALENS_API_BASE_URL`. The dashboard loaded from the owner-facing port, and the patched opportunity/metric/detail values use wrapping rather than truncation for long entry, stop, target and lifecycle strings. Frontend tests also cover the opportunity-feed/detail rendering paths.

## Test results

- Frontend Vitest: **34 passed** across 8 files.
- Frontend typecheck: **passed**.
- Frontend lint: **passed**.
- Production build: **passed** after switching the layout to a local system font stack, removing the build-time Google Fonts dependency.

Classification: **PASS for local runtime persistence, endpoint verification and production build**.
