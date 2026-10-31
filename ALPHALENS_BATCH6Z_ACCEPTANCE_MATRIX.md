# AlphaLens Batch 6Z — Acceptance Matrix

| Area | Status | Evidence | Remaining requirement |
|---|---|---|---|
| Original checkout preserved | PASS | Original path untouched; isolated worktree used. | Continue preserving inherited dirty changes. |
| Batch 6U preserved | PASS | PID `17902` remained alive on separate ports/resources. | None for this batch. |
| Owner-facing baseline backup | PASS | Custom dump hash `5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`; `pg_restore --list` succeeded. | Retain backup. |
| Durable backup copy | PASS | Identical dump copied to `/Users/sonalingowda/Library/Application Support/AlphaLens/local-state-backups/`. | Live state remains in `/private/tmp`; full state migration is not claimed. |
| Batch 6Z isolation | PASS | Separate state directory and PostgreSQL `55458`; no owner DB reuse. | Retain evidence until review. |
| Genuine BTCUSDT/5m feed | PARTIAL | Final retained status: 65 finalized messages, 9,680 incomplete updates filtered, 17 processed pipeline runs, 48 quarantined processor outcomes; genuine Binance source and closed-candle filtering remained enabled. | Complete a new separately approved observation only if required; do not reuse this failed window as a six-hour PASS. |
| Six-hour live operation | FAIL | Run began about `2026-10-26T19:49:33Z`, last committed candle `2026-10-26T21:05:00Z`, scheduled endpoint `2026-10-27T01:49:33Z`; final state `QUARANTINED` with `missing_closed_candle_interval`. | Six-hour evidence window was not completed. |
| Durable checkpoint | PASS for fail-closed progression | Final checkpoint sequence `17`, status `QUARANTINED`, last committed candle `2026-10-26T21:05:00Z`, missing interval recorded; no reset or overwrite. | Live restart-continuation was not demonstrated after quarantine. |
| Duplicate/gap handling | PARTIAL | 73 reconnects were retained and the missing interval caused quarantine; offline recovery/idempotency tests passed. | Live recovery after quarantine remains unverified. |
| Thesis identity | PARTIAL | Last readable DB snapshot: 9 theses, 9 relationships and 28 events; final counters: 15 `NEW_THESIS`; no exact match or overmerge evidenced. | Broader continuity evidence and final DB reopen remain outstanding. |
| Lifecycle integrity | PARTIAL | Genuine states include entry, monitoring, target reached and invalidated; no fills claimed. | Complete multi-hour continuity and outcome evidence. |
| Economic calculations | PASS locally | Genuine SELL plan produced unfavorable-cost classification under explicit assumptions. | No predictive/economic performance claim. |
| INR/USD analysis | PASS locally | Explicit FX requirement; no invented rate. | User-supplied or approved timestamped FX source for future scenarios. |
| Browser API polling | PASS for 30-minute window | `2026-10-26T19:50:17.002Z`–`20:20:21.888Z`: 1,800 seconds, 180 UI samples, 119 HTTP 200 responses, zero request failures and zero console errors; 300 JSONL records including completion. | Does not establish six-hour worker reliability or predictive validity. |
| Migration rollback/re-upgrade | PASS | Disposable `55459`: head → `0041` → head; thesis tables 3 → 0 → 3. | None for local migration mechanics. |
| Backend/frontend regressions | PASS baseline / pending UI patch verification | Backend 944 passed/27 skipped; frontend 34 passed; prior typecheck/lint/build/Ruff app/tests passed. Small wrapping-only UI patch added after baseline. | Re-run focused frontend checks on the patched snapshot. |
| Local stack restart safety | PARTIAL | Existing startup procedure refused to reinitialize non-empty retained PostgreSQL state; no deletion/reinitialization occurred. | Repair startup detection to recognize retained clusters without destructive fallback. |
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

Worker PID `34264`, browser observer PID `34353` and stop scheduler PID `34265` are no longer alive. The run ended in quarantine before its scheduled endpoint. No replacement observation was started.

Separate final classifications: engineering **PASS**; live reliability **FAIL**; thesis grouping **PARTIAL**; economic analysis **PASS locally**; browser stability **PASS for the captured 30-minute window**; local restart safety **PARTIAL**.

The parallel tests did not alter the active Batch 6Z worker, source-loaded process, schema or database.

The matrix is complete for the retained evidence. It does not authorize a replacement observation, predictive claims, Gate 6, Gate 7 or public launch.

The pre-addendum content hash was `3731b283556a3c67a1b7a6a6b3f4a28c4baf9a39d7410727ed0494ebe501624e`; it no longer covers this addendum.

## Batch 6AA finalization addendum — 2026-10-31

| Area | Status | Evidence | Remaining requirement |
|---|---|---|---|
| Batch 6Z original evidence | FAIL for six-hour acceptance | 65 finalized, 9,680 incomplete, 17 processed, 48 quarantined, 73 reconnects; checkpoint sequence 17 and missing interval recorded. | No replacement trial is claimed. |
| Batch 6U evidence | PARTIAL | Original checkpoint sequence 43, READY, last committed `2026-10-26T21:05:00Z`; ended about 3h35m into its 24h schedule. | No 24-hour acceptance evidence. |
| Missing-candle root cause | PASS for diagnosis | Processor quarantine preceded service repair; this explains 17/65 processed. | Live multi-hour confirmation requires separate approval. |
| Bounded gap repair | PASS for deterministic behavior | 13 focused backend tests passed, including bounded recovery and oversized-gap quarantine. | No new long-running observation started. |
| PostgreSQL safe startup | PASS | Non-empty non-cluster directories refuse initialization; isolated cluster restarted without data reset. | Original invalid directory remains unrepaired and preserved. |
| Recovered canonical market persistence | PASS locally | 1,295 immutable `MarketSnapshot` rows; 28 theses, 28 assessments, 84 events. Legacy `market_data_candles` is empty because current snapshot persistence uses immutable aggregates. | Do not represent backup as containing candle history. |
| Owner-facing localhost stack | PASS locally | Frontend 13003 and API 18003 HTTP 200; PostgreSQL 55460 and Redis 56397 live. | Build still needs an approved/offline font strategy if required. |
| Frontend regression checks | PASS | 34 tests passed; typecheck, lint and production build passed; wrapping fixes retained. | None for this local checkpoint. |
| Predictive accuracy | NOT VALIDATED | Approved model artifact remains unavailable. | Separate approved research/evaluation. |
