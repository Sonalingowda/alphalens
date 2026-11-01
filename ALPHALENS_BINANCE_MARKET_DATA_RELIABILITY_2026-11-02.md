# AlphaLens Binance Market-Data Reliability Repair

Date: 2026-11-02  
Branch: `binance-market-reliability-20261102`  
Base: `38cd3a6e60619a39ba1944fceea318f5f17162f3`  
Scope: isolated localhost worktree only; no cloud deployment, protected-test access, model training, or strategy changes.

## Executive result

**Overall: PARTIAL.** The missing-candle failure is reproducibly handled by bounded, source-validated replay and fail-closed quarantine. A supervised local run ingested genuine Binance data and stopped cleanly. The run was intentionally short, so it does not establish long-duration reconnect reliability or replace the failed Batch 6Z observation.

## Batch 6Z forensic diagnosis

The preserved checkpoint at `/private/tmp/alphalens-batch6aa-local-recovery/checkpoint.json` records the last committed candle at `2026-10-31T11:40:00Z`, a missing range from `2026-10-31T11:45:00Z` through `2026-10-31T16:30:00Z` (58 five-minute intervals), sequence 25, and `QUARANTINED` with `missing_closed_candle_interval`.

The retained worker evidence reports 36 reconnects, 15 finalized candles, 2,739 incomplete updates, 13 pipeline runs, and quarantine after the feed resumed beyond the missing range. The worker configured `max_recoverable_gap_intervals=3`; therefore the first newer finalized candle after the transport outage exceeded the recovery bound. It was quarantined before REST recovery could be attempted, and newer data was not buffered for later replay. This explains the ordering failure: a valid future finalized candle arrived before its unresolved historical interval, while the processor had no admissible bounded recovery path for the 58-candle gap.

Independent Binance REST evidence:

- Request: `data-api.binance.vision/api/v3/klines`, `BTCUSDT`, `5m`, start `2026-10-31T11:45:00Z`, end `2026-10-31T16:30:00Z`, limit 1000.
- HTTP 200; 59 rows returned because the endpoint also returned the next candle.
- Exactly 58 repair rows are aligned, chronological, nonzero-volume, closed candles from `11:45Z` through `16:30Z`; the `16:35Z` row was excluded from the repair range.
- Raw response SHA-256: `79f8ba5dbcad64bab871e14147eced66e95ee708fda6e3e11cf6c1d64e7df17a`.
- Canonical 58-row repair-range SHA-256: `aecc339b536f990c9a2058c616a5fc1733079d504c3d3a8c39e79380503d8bb5`.

The original evidence remains preserved and was not rewritten.

## Repair implemented

- `ContinuousClosedCandleProcessor` now validates a complete REST repair before persisting any repaired candle: exact count, closed status, Binance provider, no duplicates, and exact five-minute chronology.
- The local worker's recovery bound is explicit and configurable with `--max-recoverable-gap-intervals`; the safe default is 120 intervals (10 hours), with a hard CLI limit of 1,000. Recovery remains bounded and fail-closed.
- A process-scoped advisory lock prevents two local workers from owning the same checkpoint stream. Stale lock files do not grant ownership; the OS lock is authoritative.
- Existing checkpoint persistence, transactional pipeline handling, original candle geometry, and quarantine behavior remain in place. No candle is fabricated, interpolated, or silently skipped.

## Tests and static verification

- Full backend: **957 passed, 30 skipped, 2 warnings**; 497 subtests passed.
- Focused repair/worker suite: **60 passed, 1 warning**.
- Focused Ruff: passed.
- Python compilation: passed.
- `git diff --check`: passed.
- The two warnings are existing dependency/resource warnings (Starlette/httpx deprecation and an asyncpg cancellation warning); no test failed.

Regression coverage includes multi-hour missing-range replay, invalid/partial recovery quarantine without processing the future candle, duplicate/out-of-order handling through the existing processor suite, checkpoint idempotency/restart behavior, and single-worker ownership.

## Bounded real-data acceptance

Preconditions were completed before launch:

- A current-runtime PostgreSQL custom-format backup was created at `/private/tmp/alphalens-binance-reliability-pretest-20261102.dump`; SHA-256 `ba052d4912ed87f35e8c3b84c63f111cfdacd2a22f9b3cadb1f9d31883e3b91b`, with a verified `pg_restore -l` archive TOC.
- PostgreSQL and Redis ownership was verified for the isolated runtime; no other worker owned its checkpoint.
- Binance REST returned HTTP 200 and Binance WebSocket returned a valid BTCUSDT/5m kline message.
- The worker was started once from this worktree and stopped by controlled SIGINT; no long-running observation was started.

Observed worker result:

- Warmup: 250 genuine Binance snapshots persisted.
- Finalized live candles: 1.
- Incomplete updates: 140.
- Pipeline runs: 1; processor `PROCESSED`: 1; reconnects: 0; errors: 0.
- Final status: `STOPPED`; checkpoint status `READY`, gap `CLEAR`, sequence `1`, last committed candle `2026-11-01T19:00:00Z`, persistence `AVAILABLE`.
- Model status remains `UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT`.

This proves bounded genuine ingestion and clean shutdown, but is **PARTIAL** for continuous reliability because one closed live candle and zero reconnects cannot demonstrate multi-hour continuity or reconnect recovery.

## Localhost and persistence

- Frontend login: `http://localhost:13013/local-login` returned HTTP 200.
- Unauthenticated dashboard access remained protected with HTTP 401.
- API local-runtime status returned HTTP 200 with `gap_status=CLEAR`, persistence available, and worker stopped.
- `/health` returned HTTP 503 with the truthful `ARTIFACT_UNAVAILABLE` response.
- PostgreSQL `127.0.0.1:55461` accepted connections; Redis `127.0.0.1:56398` returned `PONG`.
- Current isolated database post-run contains 250 `MarketSnapshot` aggregates plus one pipeline aggregate for the supervised run, one thesis, one assessment, two lifecycle events, and 15 audit records. Its pre-test opportunity tables were empty; no historical rows in this runtime were deleted or rewritten. The separately preserved historical recovery database and Batch 6Z evidence were not modified.

## Classification

| Workstream | Result | Basis |
|---|---|---|
| Batch 6Z root-cause identification | PASS | Checkpoint, logs, and source configuration agree on the 3-interval bound and unresolved 58-candle gap. |
| Binance REST evidence | PASS | 58 exact independently retrieved rows, validated chronology and provenance. |
| Bounded replay implementation | PASS | Deterministic tests replay the range before the newer candle. |
| Fail-closed validation | PASS | Partial, out-of-order, non-Binance, duplicate, or incomplete recovery is quarantined before persistence. |
| Single-worker ownership | PASS | Advisory lock and regression test. |
| Local persistence/restart safety | PASS | Backup verified; checkpoint and controlled stop succeeded. |
| Short real-data smoke test | PASS | Genuine warmup plus one finalized live candle. |
| Long-duration/reconnect acceptance | PARTIAL | Not claimed; run was intentionally bounded and saw zero reconnects. |
| Predictive accuracy or profitability | NOT VALIDATED | Operational ingestion does not establish predictive validity. |

## Remaining blockers

1. Run a separately approved longer bounded observation to validate reconnect recovery in live conditions; do not treat this as Batch 6Z replacement without an approved acceptance window.
2. The existing quarantined Batch 6Z state remains quarantined. Clearing it requires an auditable replay against the preserved historical database and owner-approved recovery procedure.
3. No approved predictive model artifact exists; `/health` correctly reports unavailable.

