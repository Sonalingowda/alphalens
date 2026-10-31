# AlphaLens Batch 6AA Recovery Manifest — 2026-10-31

Scope: local recovery and Batch 6Z feed-continuity diagnosis only. No Batch 6U/6Z observation was running at capture time.

## Git preservation

- Verified checkpoint ref: `checkpoint/local-opportunity-intelligence-20261027`
- Verified checkpoint commit: `20f3cf5ac6fce257b7b9a8001bc9f822c446720c`
- Original checkout: `/Users/sonalingowda/Downloads/alphalens` (dirty; not modified)
- Working snapshot: `/private/tmp/alphalens-batch6z-final-20261031`
- Actual original checkout branch/HEAD: `release/railway-0f7f460` / `ac298508fc55c8c53756caf68d78ef3d48aff3e3`

## Preserved evidence hashes

- Batch 6Z status: `ac58c134f0813a0d35f7a9e9489e873447e7853d6e1fac1f4be6ddd5eec15fce`
- Batch 6Z checkpoint: `2f592fcf5a2c785f84941f1aa1587585d2adab4d311d648199542b85895c10a5`
- Batch 6U checkpoint: `fb7c668015fd59e076267d813c92bcf612a0523cd7b17a9b273b6489e81b8d27`
- Owner backup: `5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`
- Durable owner backup copy: identical SHA-256

## Runtime inventory

- No worker, scheduler or browser observation process was active.
- Retained owner state `/private/tmp/alphalens-local-20261026/postgres` is not a cluster: root `PG_VERSION`, `global/pg_control` and `global/pg_filenode.map` are absent; `pg_ctl status` reports “not a database cluster directory.”
- Retained Batch 6Z PostgreSQL directory is a real cluster with root `PG_VERSION`, but its recorded PID is dead and its old shared-memory block prevents a clean restart. No shared-memory resource was removed.
- The owner backup is a PostgreSQL custom dump created by `pg_dump 18.6` from server `16.12`; PostgreSQL 16 `pg_restore` rejects its archive format `1.16`, while libpq/PostgreSQL 18 `pg_restore` reads it successfully.

## Safety decisions

- No existing database directory was deleted, overwritten, reset, reinitialized or WAL-repaired.
- Historical owner data will only be recovered into a new explicitly named disposable/recovery cluster from the verified dump.
- Empty replacement state will never be represented as historical recovery.

## Final recovery measurements

- Isolated recovery cluster: `/private/tmp/alphalens-batch6aa-local-recovery/postgres`, PostgreSQL `55460`.
- Isolated Redis: `56397`; owner-facing API/frontend: `18003`/`13003`.
- Canonical immutable market snapshots after genuine Binance warmup/live smoke: `1,295`.
- Durable theses/assessments/events: `28` / `28` / `84`.
- Legacy `market_data_candles`: `0`; the restored pre-trial dump contained no candle rows and no substitute rows were fabricated.
- Final recovered checkpoint observed: sequence `25`, last committed `2026-10-31T11:40:00Z`, status `QUARANTINED`, missing `2026-10-31T11:45:00Z` through `2026-10-31T16:30:00Z`.
- Owner-facing frontend, runtime status and live market endpoints returned HTTP 200.
- The model artifact remained explicitly unavailable; no predictive output or trading enablement was introduced.
