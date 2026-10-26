# AlphaLens Batch 6Z — Multi-hour Live Verification Report

Date: 2026-10-27
Scope: Binance BTCUSDT / closed 5-minute candles, local-only
Overall status: IN PROGRESS — no six-hour PASS claimed.

## Finalization inspection snapshot

Inspection time: `2026-10-26T20:01:28Z`.

- Worker PID `34264`: alive, elapsed approximately 11 minutes 55 seconds from the verified connected start.
- Browser observer PID `34353`: alive, elapsed approximately 11 minutes 14 seconds from its first browser sample.
- Stop scheduler PID `34265`: alive; scheduled observation end approximately `2026-10-27T01:49:33Z`.
- Live run end timestamp: not yet reached.
- Finalized candles: 3.
- Incomplete updates: 306.
- Processing errors: 0.
- Gap events: 0; checkpoint gap state `CLEAR`.
- Reconnects: 0; connection remained healthy.
- Pipeline runs: 3; processor outcomes `PROCESSED=3`.
- Checkpoint sequence: 3; last committed candle `2026-10-26T19:55:00Z`.
- Batch 6Z database: 3 thesis rows, 3 assessment relationships and 8 lifecycle events; current states are one `ENTRY_AVAILABLE` and two `MONITORING`.
- Browser JSONL evidence: 112 records at inspection, including 44 HTTP 200 opportunity polls, 68 UI samples, no request failures and no console errors.

Because the required six hours and 30 minutes have not elapsed, these are finalization measurements but not completed-duration acceptance evidence.

## Parallel thesis regression tests

The active Batch 6Z worker/database were not used or modified. A separate disposable PostgreSQL instance on `127.0.0.1:55459` was used for `backend/tests/test_thesis_intelligence_postgres.py`:

- identical qualifying geometry/evidence: PASS; two assessments attached to one thesis and the original entry, stop and target remained unchanged;
- materially changed geometry: PASS; the result remained a separate thesis or an explicit ambiguous relationship, with no silent merge;
- process restart and concurrent duplicate ingestion: PASS; one thesis, one assessment relationship and one creation event remained idempotent;
- PostgreSQL-backed tests: `3 passed`;
- targeted thesis suite: `3 passed, 3 skipped` (the PostgreSQL file is skipped without an explicit test database URL);
- Ruff for `app tests`: passed;
- `git diff --check`: passed.

The current implementation returns a new thesis for the changed-geometry fixture because no exact geometry match exists; this is safe under the approved rule but less informative than recording an explicit ambiguous relation. A follow-up refinement is recommended after the live observation and does not affect the active worker.

## Baseline and isolation

- Engineering worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`
- Source commit/tree: `948913a7e2df47b785bef655deaa4843c7589bcf` / `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Owner-facing local app: frontend `127.0.0.1:13003`, API `127.0.0.1:18003`, PostgreSQL `127.0.0.1:55448`, Redis `127.0.0.1:56395`.
- Batch 6Z live observation database: PostgreSQL `127.0.0.1:55458`, state `/private/tmp/alphalens-batch6z-live-20261026`.
- Batch 6Z worker PID: `34264`; stop scheduler PID: `34265`; scheduled duration: 21,600 seconds.
- Batch 6U PID `17902` remained alive on its independent resources and was not interrupted.
- Original checkout was not modified.
- Owner-facing database backup before this batch: `/private/tmp/alphalens-local-20261026/backups/pre_batch6z_20261026T1948Z.dump`; SHA-256 `5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`; `pg_restore --list` succeeded with 500 entries.
- Durable recovery copy: `/Users/sonalingowda/Library/Application Support/AlphaLens/local-state-backups/pre_batch6z_20261026T1948Z.dump`; identical SHA-256. The live database remains in its existing temporary state directory; no live-state move was attempted.

The first Batch 6Z launch attempt failed before ingestion because its environment omitted `PYTHONPATH`; it produced no market evidence. It was not counted. The detached relaunch was verified independently by PID, status file and logs.

## Current live observation

The corrected run began at approximately `2026-10-26T19:49:33Z` and is scheduled to end at approximately `2026-10-27T01:49:33Z`. At the latest inspection:

- worker: `RUNNING`
- Binance connection: healthy
- source: public Binance market-data WebSocket
- symbol/timeframe: BTCUSDT / 5m
- closed-candle-only: true
- finalized candles: 1
- incomplete updates quarantined: 12
- pipeline runs: 1
- processor result: `PROCESSED` 1
- thesis match: `NEW_THESIS` 1
- last finalized candle: `2026-10-26T19:45:00Z`
- gap state: `CLEAR`
- persistence: `AVAILABLE`
- model artifact: `UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT`
- external notifications: disabled
- trading: disabled

The one processed candle executed the existing pipeline through market snapshot, features, context, Detection, evidence, assessment and qualification. Scoring stopped at `scoring.input_unavailable`, as required. No confidence, expected value, ranking or profit prediction was generated.

This is early-progress evidence only. The six-hour acceptance window has not completed.

## Persistent thesis observations

Before the isolated live run, the owner-facing database contained 13 persistent thesis rows, 13 assessment relationships and 38 append-only events. The records covered two registered detection-family strings:

| Measurement | Observed |
|---|---:|
| Raw persisted assessment relationships | 13 |
| Persistent thesis rows | 13 |
| Detection-family clusters | 2 |
| Exact-geometry matches | 0 |
| Ambiguous/exact relationship statuses | 0 / 0; all 13 recorded as `NEW_THESIS` |
| Current active/non-terminal thesis rows | 5 |
| Terminal invalidated/target-resolved rows | 8 |
| Append-only lifecycle events | 38 |

The live data shows changing entry/stop/target geometry at each assessment. Because the existing diagnostic policy requires exact geometry and excludes terminal theses from reuse, the service correctly did not silently merge these records. The API projection nevertheless presents one primary card per detection family and exposes related review information. This is conservative presentation, not proof that all 13 records are one thesis.

Representative genuine states included `ENTRY_AVAILABLE`, `ENTRY_MISSED`, `MONITORING`, `INITIAL_TARGET_REACHED` and `INVALIDATED`. No actual fills, P&L or target probabilities were claimed. Same-candle target/stop ambiguity remains covered by focused tests.

## Economic verification

The existing genuine SELL plan was evaluated through the local economics API with USD 500 notional, 10 bps entry/exit fees, 5 bps entry/exit slippage and explicitly short-capable derivative semantics:

- gross target movement: `114.521785714285714286` price points;
- gross target profit: `$0.7141721277300862723315622740`;
- modeled costs: `$1.5`;
- estimated net target: `-$0.7858278722699137276684377260`;
- estimated net stop: `-$1.976114751820057514885629474`;
- cost-to-gross-reward ratio: `2.100333997586235931398953202`;
- classification: `COSTS_EXCEED_GROSS_TARGET`.

This is deterministic arithmetic under stated assumptions, not an expectancy or profitability claim. Spot SELL remains explicitly unavailable because AlphaLens does not execute or assume naked shorts. INR 500 requires an explicitly entered FX rate; no FX value was invented.

## Browser observation

A real Chromium page was connected through the existing CDP browser session and navigated to `http://127.0.0.1:13003/`. Evidence:

- screenshot: `/private/tmp/alphalens-batch6z-live-20261026/dashboard.png`;
- observer PID: `34353`;
- JSONL evidence: `/private/tmp/alphalens-batch6z-live-20261026/browser-observation-2.jsonl`;
- early samples: repeated API HTTP 200 responses, no request failures, no console errors, and no `Load failed` marker.

The required 30-minute browser observation is still in progress and therefore not marked PASS.

## Migration safety

An independent disposable PostgreSQL instance on `127.0.0.1:55459` was used. Results:

```text
upgrade head       20261027_0043; thesis tables 3
downgrade 0041     20261026_0041; thesis tables 0
re-upgrade head    20261027_0043; thesis tables 3
```

The disposable instance was stopped after verification. The owner-facing database was not downgraded.

## Tests

Prior verified regression baseline remains backend `944 passed, 27 skipped, 497 subtests`, frontend `34 passed`, typecheck/lint/build passed, app/tests Ruff passed and `git diff --check` passed. Batch 6Z additionally verified migration upgrade/downgrade/re-upgrade and live worker startup on isolated resources.

Repository-wide scripts Ruff still has 82 inherited diagnostics and is not represented as cleared.

## Acceptance decisions

- Engineering infrastructure: **PASS**. Isolated resources, backup, migration rollback/re-upgrade and protected-resource checks passed.
- Persistent thesis engineering: **PARTIAL**. Identity, append-only events, conservative non-merging and lifecycle persistence are evidenced; no live exact-match continuity was observed and the six-hour evidence is incomplete.
- Economic viability: **PASS locally**. Genuine persisted plans, deterministic assumptions, API/UI behavior and unfavorable-cost classification were verified. This does not validate profitability.
- Six-hour live operation: **PARTIAL**. Three finalized candles were processed with zero errors, gaps or reconnects, but the six-hour window has not ended.
- Browser stability: **PARTIAL**. Polling remained clean, but the 30-minute observation and recovery exercises are incomplete.
- Multi-hour predictive accuracy: **NOT VALIDATED**.
- Target-extension intelligence: **NOT VALIDATED**.
- Gate 6: **NOT VALIDATED**.
- Gate 7: **BLOCKED**.
- Public launch: **NOT AUTHORIZED**.

## Next evidence collection

The existing worker and browser observer remain active. After the scheduled windows, record final status, checkpoint, candle/assessment/thesis/event counts, reconnects, gaps, errors, browser completion and report hashes. Do not convert this incomplete observation into a PASS.

Report content hash (excluding this final hash line): `05e1a0e6a7dbf64bc711a7969744cd2d794b8949f6f08bfd97d702afefd54f01`
