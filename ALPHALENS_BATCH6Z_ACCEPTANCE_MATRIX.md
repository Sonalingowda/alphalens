# AlphaLens Batch 6Z — Acceptance Matrix

| Area | Status | Evidence | Remaining requirement |
|---|---|---|---|
| Original checkout preserved | PASS | Original path untouched; isolated worktree used. | Continue preserving inherited dirty changes. |
| Batch 6U preserved | PASS | PID `17902` remained alive on separate ports/resources. | None for this batch. |
| Owner-facing baseline backup | PASS | Custom dump hash `5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`; `pg_restore --list` succeeded. | Retain backup. |
| Durable backup copy | PASS | Identical dump copied to `/Users/sonalingowda/Library/Application Support/AlphaLens/local-state-backups/`. | Live state remains in `/private/tmp`; full state migration is not claimed. |
| Batch 6Z isolation | PASS | Separate state directory and PostgreSQL `55458`; no owner DB reuse. | Retain evidence until review. |
| Genuine BTCUSDT/5m feed | PARTIAL | At `2026-10-26T20:01:28Z`: 3 finalized candles, 306 incomplete updates filtered, 0 errors, 0 gaps, 0 reconnects; checkpoint sequence 3. | Six-hour end not reached. |
| Durable checkpoint | PARTIAL | Isolated worker checkpoint/status paths configured; one candle committed. | Verify final progression and restart/recovery during completed window. |
| Duplicate/gap handling | IN PROGRESS | Existing processor and gap state `CLEAR`; offline recovery tests previously passed. | Capture live six-hour counts and any reconnect/gap events. |
| Thesis identity | PARTIAL | Live Batch 6Z has 3 theses, 3 assessments and 8 events; all 3 relationships are `NEW_THESIS`, with no overmerge. | Exercise and evidence exact continuity matching; current sample has no exact match. |
| Lifecycle integrity | PARTIAL | Genuine states include entry, monitoring, target reached and invalidated; no fills claimed. | Complete multi-hour continuity and outcome evidence. |
| Economic calculations | PASS locally | Genuine SELL plan produced unfavorable-cost classification under explicit assumptions. | No predictive/economic performance claim. |
| INR/USD analysis | PASS locally | Explicit FX requirement; no invented rate. | User-supplied or approved timestamped FX source for future scenarios. |
| Browser API polling | PARTIAL | At `2026-10-26T20:01:28Z`: observer PID `34353`, 112 JSONL records, 44 HTTP 200 API responses, zero request failures and console errors. | 30-minute observation and recovery exercises incomplete. |
| Migration rollback/re-upgrade | PASS | Disposable `55459`: head → `0041` → head; thesis tables 3 → 0 → 3. | None for local migration mechanics. |
| Backend/frontend regressions | PASS baseline | Backend 944 passed/27 skipped; frontend 34 passed; typecheck/lint/build/Ruff app/tests passed. | Re-run after any source change. |
| Parallel thesis regression tests | PASS | Disposable PostgreSQL: 3 passed; targeted thesis suite: 3 passed/3 skipped; Ruff and diff checks passed. | Live observation remains separate and incomplete. |
| Predictive artifact | BLOCKED | No approved BTCUSDT/5m artifact. | Complete approved research and independent evaluation. |
| Target extensions | NOT VALIDATED | No extension displayed as actionable. | Separate validated policy. |
| Gate 6 | NOT VALIDATED | Protected evaluation absent. | Independent research approval. |
| Gate 7 | BLOCKED | Production provenance/runtime evidence incomplete. | Complete release certification. |
| Public launch | NOT AUTHORIZED | Explicit project boundary. | Owner approval after all gates. |

## Current observation identities

- Worker PID: `34264`
- Stop scheduler PID: `34265`
- Browser observer PID: `34353`
- Live state: `/private/tmp/alphalens-batch6z-live-20261026`
- Owner app URL: `http://127.0.0.1:13003/`
- API URL: `http://127.0.0.1:18003/`

## Finalization status

Worker PID `34264`, browser observer PID `34353` and stop scheduler PID `34265` were all alive at the finalization inspection. No end timestamp exists because the scheduled windows have not elapsed. No replacement observation was started because the existing run is healthy and evidence is not invalidated.

Separate final classifications: engineering **PASS**; live reliability **PARTIAL**; thesis grouping **PARTIAL**; economic analysis **PASS locally**; browser stability **PARTIAL**.

The parallel tests did not alter the active Batch 6Z worker, source-loaded process, schema or database.

The matrix is intentionally not marked complete while the six-hour and 30-minute observations are active.

Report content hash (excluding this final hash line): `3961886b657d600d650aa6d7177ec3264f2806648481d597f3d98b0c10d87b9d`
