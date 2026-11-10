# AlphaLens Checkpoint 04A — Market Data Readiness Audit

Audit date: 2026-11-10
Audit mode: read-only; no Binance network acquisition, ingestion, worker start, schema change, backup creation, or market-data write was performed.

## Decision

**Overall: PARTIAL**
**Ingestion approval: NO-GO pending owner remediation and a separate acquisition approval**

The code-level Binance candle contracts and regression coverage are substantially ready for a new lineage. The local runtime is not presently an acceptable acquisition surface because a legacy worker container is already running, legacy database/Redis containers are published on all interfaces, and the current Binance warmup writes each immutable snapshot independently rather than committing one acquisition batch and its lineage atomically.

## A. Trusted baseline

- Worktree: `/Users/sonalingowda/alphalens-rebuild-20261105`
- Branch: `gate9d2/owner-infrastructure-20261105`
- Starting HEAD and remote Checkpoint 03: `3273083d2b6b8747eed7a4d898bd763e4a07422d`
- Worktree was clean at audit start.
- Protected Downloads checkout was not accessed or modified.
- Backend: `127.0.0.1:18000`, local uvicorn process, loopback-only.
- PostgreSQL owner service: `127.0.0.1:55461`.
- Redis owner service: `127.0.0.1:56397`.
- Frontend verification container: `127.0.0.1:3000`.
- `/health/readiness`: HTTP 200.
- `/health`: HTTP 503 with `ARTIFACT_UNAVAILABLE`.
- `/api/v1/local-runtime/status`: `unconfigured` / `worker_status_path_missing`.
- `/api/v1/pipeline/health`: no pipeline run, no pending tasks.

The direct owner database identity was `alphalens_local_rebuild_20261105`, PostgreSQL 16.12, user `alphalens_owner_rebuild`.

## B. Database and migration state

Direct read-only counts from the owner database:

| Table/category | Rows | Result |
|---|---:|---|
| `market_data_candles` | 0 | No market candles |
| `market_data_ingestion_batches` | 0 | No ingestion batches |
| `historical_acquisition_attempts` | 0 | No acquisition attempts |
| `historical_acquisition_checkpoints` | 0 | No historical checkpoints |
| `historical_coverage_snapshots` | 0 | No coverage snapshots |
| `immutable_runtime_aggregates` | 0 | No immutable runtime aggregates |
| `opportunity_theses` | 0 | No theses |
| `opportunity_thesis_assessments` | 0 | No assessments |
| `opportunity_thesis_events` | 0 | No thesis events |
| `paper_tracking_events` | 0 | No paper-tracking events |
| `prediction_api_audits` | 479 | Operational API audit history |

The verified database Alembic revision is `20261027_0043`, matching the repository head. No migration was run.

The database has changed since the 2026-11-05 backup because operational API audit rows exist through the current audit window. Market-data and opportunity lineage tables remain empty.

## C. Binance source and request construction

The approved local worker uses:

- WebSocket: `wss://data-stream.binance.vision`
- Stream: `btcusdt@kline_5m`
- REST warmup: `https://data-api.binance.vision/api/v3/klines`
- Parameters: `symbol=BTCUSDT`, `interval=5m`, bounded `limit`, and `endTime` at the latest completed 5-minute boundary.
- The local worker explicitly supplies no REST fallback URLs, so it does not silently substitute another exchange.

There are other repository paths with historical Kraken contracts and debug scripts using other Binance hosts. Those are not approved for this recovery. The future acquisition must use the local worker path with its explicit Binance-only REST configuration.

No Binance endpoint was contacted during this audit.

## D. Candle finalization and integrity

**PASS by source inspection and tests:**

- Binance kline `x` must be true for WebSocket candles.
- REST candles are rejected when `close_time >= now`.
- BTCUSDT, 5-minute scope and UTC timestamps are enforced.
- Open times must align to the 5-minute UTC boundary.
- OHLCV values are parsed as finite `Decimal` values; no fallback prices exist.
- Positive OHLC prices and non-negative volume are enforced.
- BTCUSDT zero-volume warmup candles are rejected.
- Stable candle ordering is required by chronology and recovery checks.
- Duplicate identities are deduplicated by content hash.
- Conflicting duplicate content fails closed.
- Missing intervals are detected and bounded REST recovery is attempted.
- Immutable snapshot IDs, source payload hashes, lineage hashes and result hashes are generated deterministically.

## E. Proposed 240-candle warmup

**Conditionally supported; not executed.**

`local_market_worker.py` accepts `--warmup-limit 240`; its lower guard is 200 and the REST client caps requests at 1000. The endpoint therefore makes one bounded request for up to 240 most recent finalized 5-minute candles, ending at the last closed boundary.

The actual feature engine does not contain a universal hard-coded “200 candles required” contract. It requires a contiguous suffix and limits the retained prefix to 500. The worker’s 200-candle minimum is an operational startup guard, while 240 supplies a 40-candle margin. Any gap reduces the contiguous suffix and must keep runtime outputs unavailable until repaired.

## F. Lineage and checkpoint design

The new live path creates:

1. Binance raw kline payload SHA-256.
2. Deterministic market snapshot identity using symbol, timeframe and open-time milliseconds.
3. Snapshot source reference, code version, configuration hash, lineage hash and result hash.
4. A filesystem runtime checkpoint bound to an operator-supplied source identity and its own document hash.

This establishes a new lineage only if the owner supplies a newly verified source identity and preserves the resulting checkpoint and runtime evidence. Lost historical checkpoint IDs must not be reused.

The older database `historical_acquisition_checkpoints` lineage is empty and its implementation is associated with the older Kraken historical orchestration. It must not be presented as Binance recovery evidence.

## G. Persistence and recovery risk

The live repository writes one immutable market snapshot per transaction. Warmup is idempotent, but a process crash can leave a partial set of 240 snapshots without one atomic acquisition-batch record tying the complete request, response evidence and checkpoint together.

The continuous processor has strong per-candle checkpoint and gap controls, but this does not replace a transactional bounded warmup manifest. This is a material acquisition-readiness limitation and one reason for the current NO-GO.

## H. Retry and failure modes

- WebSocket reconnect backoff: 1 second initial, 30 second maximum; heartbeat timeout is 90 seconds in the local worker.
- Warmup retries: 3 attempts with 15-second backoff.
- REST request timeout: 30 seconds.
- REST response errors are fail-closed; the local worker has no alternate exchange fallback.
- HTTP 429/5xx and timeout failures surface through bounded retry and prevent successful warmup.
- Malformed, open, zero-volume, out-of-order, duplicate and conflicting candles are rejected or quarantined.
- Gap recovery is bounded to 1–120 intervals by the local worker.
- Database interruption propagates as a processing failure and does not advance the runtime checkpoint.
- Runtime model artifact remains unavailable; no predictive inference is activated.

## I. Backup and disaster recovery

The owner-approved backup exists:

`/Users/sonalingowda/alphalens-operational-20261105/backups/owner-baseline-20261105.dump`

- Size: 315,081 bytes.
- Timestamp: 2026-11-05 18:31:00 IST.
- SHA-256: `4e7e44ec3ccd0f1d40d44325040bca245fcdff0af3f1f5b04c7389a8ff092d0b`.
- Existing evidence records a successful restore test into a separate verification database at Alembic `20261027_0043`.
- Backup and operational data are on the same local APFS volume.
- Independent encrypted off-device backup: **not verified / not present in the operational recovery root**.
- Free disk space at audit: approximately 7.8 GiB. No new backup was created.

## J. Security and runtime blockers

**PASS:** current backend/frontend owner services are loopback-only; Clerk authorization remains intact; no unapproved model artifact is active; no market data was acquired by this audit.

**BLOCKED:** a pre-existing `alphalens-demo-worker-1` container is running `python -m app.background_worker`. It was not started or modified by this audit. It is not the local Binance worker, but its presence means the host cannot be certified as worker-free.

**BLOCKED:** pre-existing `alphalens-postgres-1` and `alphalens-redis-1` containers publish ports on `0.0.0.0`. They were not started or modified by this audit. They violate the required network-isolation posture until the owner stops/removes or rebinds them after confirming they are not needed.

## K. Test evidence

- Full backend suite: **976 passed, 30 skipped, 497 subtests passed**.
- Focused market-data/runtime suite: **91 passed**.
- Frontend Checkpoint 03 suite remains **39 passed**, with prior typecheck, lint and build passing.
- Two non-failing warnings remain: Starlette/httpx deprecation and an asyncpg cleanup warning in an existing test path.

No assertions were weakened and no live network acquisition test was run.

## L. Proposed future owner-approved command

After the blockers are resolved, the owner must independently create and retain a new source-identity manifest/hash. The value below is intentionally a placeholder and must not be invented:

```sh
cd /Users/sonalingowda/alphalens-rebuild-20261105/backend
source .venv/bin/activate
PYTHONPATH=. python scripts/local_market_worker.py \
  --checkpoint /Users/sonalingowda/alphalens-operational-20261105/checkpoints/binance-btcusdt-5m-<new-lineage>.json \
  --status /Users/sonalingowda/alphalens-operational-20261105/status/binance-btcusdt-5m.json \
  --source-identity <owner-verified-new-source-identity-sha256> \
  --warmup-limit 240 \
  --max-recoverable-gap-intervals 120
```

This command is proposed only; it was not run.

## M. Post-acquisition acceptance criteria

Before accepting the acquisition, the owner must verify:

1. Only the approved Binance worker is running.
2. All AlphaLens ports are loopback-only.
3. A new source identity, acquisition timestamp and request bounds are retained.
4. At least 240 finalized BTCUSDT/5m candles are returned and 200 contiguous candles remain after validation.
5. No gaps, conflicting duplicates or open candles exist.
6. Snapshot/source/result hashes verify from retained evidence.
7. The new checkpoint is durable and reloadable after restart.
8. Database counts and checkpoint membership match exactly.
9. Dashboard shows API readiness and real market snapshot availability only after persisted candles exist.
10. Model status remains `ARTIFACT_UNAVAILABLE` unless a separately approved artifact exists.

## N. Owner next action

Stop or isolate the pre-existing worker and wildcard-published legacy PostgreSQL/Redis containers after confirming ownership, then separately approve one bounded Binance acquisition using a newly generated lineage identity. Do not begin acquisition before that approval.
