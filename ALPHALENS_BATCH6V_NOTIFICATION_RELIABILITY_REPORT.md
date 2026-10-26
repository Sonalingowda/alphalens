# AlphaLens Batch 6V — Notification Reliability Report

Date: 2026-10-26 (Asia/Kolkata)

## Final status

**Batch 6V isolated notification queue engineering: PASS.**

This PASS covers the PostgreSQL-backed queue, fenced leases, retry state machine, append-only queue attempts, disposable multi-worker tests, database restart, and migration rollback/re-upgrade. It does not authorize or verify an external notification provider, exactly-once provider delivery, production deployment, or public alerts.

Batch 6U was not interrupted, restarted, migrated, or connected to this queue database.

## Preservation and identities

- Worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`
- Baseline source commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Original dirty checkout was not modified.
- Active Batch 6U resources were treated as protected: PID `17902`, PostgreSQL `127.0.0.1:55446`, Redis `127.0.0.1:56394`, checkpoint and report paths.
- Batch 6V used separate PostgreSQL `127.0.0.1:55447`, a separate cluster/data directory, separate database and disposable credentials.

## Source changes

1. `backend/alembic/versions/20261026_0041_create_notification_delivery_queue.py`
   - Creates `notification_delivery_jobs` with stable idempotency key, state, retry schedule, worker identity, lease token, lease expiry, claim version, recovery count and terminal/provider fields.
   - Creates `notification_delivery_attempts` with immutable sequence, worker/token identity, state, failure category and provider reference.
   - Adds claim/observability indexes and foreign-key/uniqueness/check constraints.
   - SHA-256: `6f0081ddd1166747b244dee9b8f3f98b62f025ac59a1f97828d4e7765ee53a60`.

2. `backend/app/runtime_notification/queue.py`
   - Implements transactional `FOR UPDATE SKIP LOCKED` claims.
   - Uses worker identity plus lease token fencing.
   - Recovers expired claims and increments recovery counters.
   - Persists attempt and state transition atomically.
   - Prevents stale workers from completing a newer claim.
   - Supports bounded retry scheduling, permanent failure, expiry and queue statistics.
   - SHA-256: `7e7c0e286bb17e8301542f839f7dd6708600655c5740e453896482f870250a7f`.

3. `backend/app/runtime_notification/__init__.py`
   - Exports the queue contracts and error types.

4. `backend/tests/test_notification_queue_postgres.py`
   - Covers concurrent claims, lease expiry recovery, stale-worker rejection, retry scheduling, permanent failure, terminal idempotency and expiry visibility.
   - SHA-256: `54d89f1453f91532882cae3533c058f72c25514eca2224f6fecb0f61856fdb78`.

5. `backend/tests/test_production_infrastructure.py`
   - Updates the isolated migration-head expectation to `20261026_0041`.
   - SHA-256: `89970d2234c309f7fd1ef0eb7b9f1c90000a5a4d30db2d4ba7bbd9afd4a2d1f8`.

## State and lease semantics

| Transition | Mechanism | Evidence |
|---|---|---|
| PENDING → CLAIMED | Row lock, worker ID, unique lease token, expiry and claim version | PostgreSQL integration and process probes |
| CLAIMED → DELIVERED | Fenced transaction appends attempt and clears lease | Integration test |
| CLAIMED → RETRYABLE_FAILURE → PENDING | Fenced attempt append with next-attempt timestamp | Integration test |
| CLAIMED → PERMANENT_FAILURE | Fenced terminal update with failure category | Integration test |
| Expired lease → new CLAIMED owner | Expiry predicate plus recovery counter | Integration test and process probe |
| Stale worker completion | Worker/token predicate; raises `StaleWorkerError` | Integration test |
| Duplicate terminal update | Existing terminal job is returned without a second attempt | Integration test |
| Expired pending job | Claim transaction marks it `EXPIRED` before selecting work | Integration test |

External delivery remains at-least-once from AlphaLens’s perspective. Provider-side exactly-once delivery cannot be guaranteed without provider idempotency support and acknowledgement semantics. Ambiguous provider acknowledgements must remain retryable and use the stable queue idempotency key.

## Verification evidence

- Alembic upgrade head: `20261026_0041`.
- Downgrade to `20261003_0040`: passed.
- Re-upgrade to `20261026_0041`: passed.
- PostgreSQL stop/start and post-restart schema query: passed.
- Queue integration tests on isolated PostgreSQL: 4 passed.
- OS-process claim probe: worker A claimed `job.process2`; worker B returned `null`.
- OS-process lease recovery probe: a different worker reclaimed an abandoned lease with `lease_expired_recoveries=1`.
- Full backend suite: 938 passed, 27 skipped, 497 subtests, 2 known warnings.
- Backend Ruff: passed.
- `git diff --check`: passed.
- Existing frontend checks remain unchanged and previously passed under Node 22.23.3.

## Observability

`PostgreSQLNotificationQueue.stats()` reports pending depth, active leases, retryable jobs, terminal failures, expired-lease recovery count and oldest pending age. These values are available for a future authenticated operational endpoint or metrics adapter; no public notification endpoint was enabled in this batch.

## Limitations and remaining authorization

- No real provider was configured or contacted.
- No external notification was sent.
- No production database migration was executed.
- No cross-region or network-partition test was performed.
- The queue is ready for a separately reviewed provider adapter, but that adapter must preserve idempotency keys, ambiguous-ack handling, user opt-in, secret management and delivery privacy.
- Batch 6U remains in progress and must not be classified from this report.

## Report hash

Content SHA-256 (excluding this hash section): `819cea36f9999b6ccfa3cccb3fe8693a7c692e96b04562387dc59fe544c54b24`.

