# AlphaLens Checkpoint 04B — Runtime Isolation, Backup and Warmup Readiness

Audit date: 2026-11-10
Mode: controlled local remediation. No Binance network acquisition, market worker start, market-data write, schema migration, predictive inference, deployment, or volume deletion was performed.

## Decision

**Overall: PARTIAL**
**Future acquisition: NO-GO until the owner reviews the warmup transaction limitation and separately approves acquisition.**

## 1. Baseline

- Branch: `gate9d2/owner-infrastructure-20261105`
- Starting HEAD: `66642d18ae37311db1a94829db116b871853836b`
- Remote Checkpoint 04A: present at the expected branch.
- Owner database: PostgreSQL 16.12 at `127.0.0.1:55461`.
- Owner Redis: `127.0.0.1:56397`.
- Backend: `127.0.0.1:18000`.
- Frontend: `127.0.0.1:3000`.
- Owner readiness remained HTTP 200; model health remained HTTP 503 `ARTIFACT_UNAVAILABLE`.
- Owner migration revision: `20261027_0043`.
- Owner market-data tables remain empty; operational API audit rows increased during ordinary verification and backup testing but no market-data rows were written.

## 2. Legacy container isolation

Ownership and independence were established before modification.

| Container | ID prefix | Image/role | Original publication | Action |
|---|---|---|---|---|
| `alphalens-demo-worker-1` | `eca75b53f629` | `alphalens-backend:1.0.0`, Compose project `alphalens-demo`, `python -m app.background_worker` | none | stopped; restart disabled |
| `alphalens-postgres-1` | `79cf1266793e` | legacy PostgreSQL container, named volume `alphalens_postgres_data` | `0.0.0.0:5432->5432` | stopped; restart disabled |
| `alphalens-redis-1` | `e3d26a352946` | legacy Redis container, no mount | `0.0.0.0:6379->6379` | stopped; restart disabled |

The worker belongs to `/Users/sonalingowda/alphalens-release-work` and its `alphalens-demo_default` network. The wildcard PostgreSQL/Redis containers are separate legacy resources on `alphalens_default`; the approved backend uses the owner services on ports 55461/56397 and did not depend on them. No volumes, images, networks, or containers were removed.

The separate `alphalens-demo-postgres-1`, `alphalens-demo-redis-1`, and legacy backend remain on their private demo network; the backend is loopback-published on port 8000 and unhealthy. They were not needed to remove wildcard publication and were not modified.

After remediation:

- No Docker AlphaLens service is wildcard-published on 5432 or 6379.
- Owner PostgreSQL, Redis, backend, and frontend remained operational.
- No local Binance worker process is running.

Rollback, only if explicitly approved:

```sh
docker update --restart=unless-stopped alphalens-demo-worker-1 alphalens-postgres-1 alphalens-redis-1
docker start alphalens-postgres-1 alphalens-redis-1 alphalens-demo-worker-1
```

Starting the two legacy database containers would restore their prior wildcard port exposure; that rollback must not be used without an isolation review.

## 3. Backup and restore evidence

Existing owner baseline:

- File: `backups/owner-baseline-20261105.dump`
- Size: 315,081 bytes
- SHA-256: `4e7e44ec3ccd0f1d40d44325040bca245fcdff0af3f1f5b04c7389a8ff092d0b`
- Existing same-disk restore evidence: present; revision `20261027_0043`.

Fresh validated backup:

- File: `backups/owner-checkpoint04b-pg16.xWp0w3`
- Size: 369,342 bytes
- SHA-256: `dbbaccff1e35fd8a1dae557d74b7c0b970953965d5296c88f6c5b895d538605d`
- Permissions: `0600`
- PostgreSQL 16 custom format; 500 TOC entries.
- Restored into disposable database `alphalens_restore_verify_04b_final2_20261110`.
- Restore result: Alembic `20261027_0043`, `market_data_candles=0`, `prediction_api_audits=499`.
- Disposable database was explicitly verified and removed.

The first backup attempt used PostgreSQL 18 client tooling and was retained but was not used as the validated restore artifact because PostgreSQL 16 `pg_restore` rejected its newer format/configuration. The validated PostgreSQL 16 backup above is the acquisition-readiness artifact.

The host had approximately 7.8 GiB free. No off-device encrypted backup destination was available or verified. Disaster recovery remains same-disk only until the owner supplies an independently controlled encrypted destination and verifies its checksum.

## 4. Warmup crash consistency

The existing Binance local worker correctly validates a bounded 240-candle warmup, rejects open/zero-volume candles, hashes source payloads, persists immutable snapshots idempotently, and uses an atomic filesystem checkpoint for the continuous processor.

However, warmup currently calls the immutable repository once per snapshot. Each snapshot transaction is atomic, but the complete 240-candle acquisition is not one atomic database transaction and is not tied to one database acquisition-batch manifest. A crash can therefore leave a partial set of valid snapshots before the filesystem checkpoint advances.

This is not being misrepresented as batch atomicity. Making it truly atomic requires a reviewed persistence protocol, likely involving a batch manifest and coordinated commit/recovery semantics. No migration or nontrivial production redesign was silently introduced in Checkpoint 04B.

Current safe properties:

- Duplicate snapshot identity is idempotent.
- Conflicting immutable content fails closed.
- Restart skips already persisted identities.
- WebSocket checkpoint writes use temporary-file replacement and document hashes.
- Gap recovery is bounded to 120 intervals by the local worker.

Required owner-approved design before acquisition:

1. Create a new acquisition-lineage manifest containing source identity, request bounds, retrieval time, code/configuration hashes and expected response hash.
2. Persist a pending batch state before candle writes.
3. Commit the complete validated candle set and batch membership atomically, or mark the batch incomplete and quarantine it on restart.
4. Advance the runtime checkpoint only after batch verification.
5. Reconcile pending batches after crash without treating partial rows as accepted continuity.

## 5. Tests

Previously verified before this remediation:

- Full backend suite: 976 passed, 30 skipped, 497 subtests passed.
- Focused market-data/runtime suite: 91 passed.
- Frontend suite: 39 passed.
- Typecheck, lint and production build: passed.

Backup restore was independently verified with PostgreSQL 16 tools. No real market-data fixture was persisted into the owner database.

## 6. Security recheck

- Frontend publication: loopback-only.
- Backend listener: loopback-only.
- Owner PostgreSQL/Redis: loopback-only.
- Legacy wildcard services: stopped.
- Legacy volumes: preserved.
- Binance worker: not running.
- Predictive inference: still fail-closed with no approved artifact.
- Credentials, tokens and dumps: not staged in Git.

## 7. Owner next action

Review the stopped-container isolation, retain or independently encrypt the fresh backup, and approve a separate warmup persistence design before authorizing any Binance acquisition. Acquisition remains **NO-GO** until the batch-lineage/crash-recovery decision is approved.
