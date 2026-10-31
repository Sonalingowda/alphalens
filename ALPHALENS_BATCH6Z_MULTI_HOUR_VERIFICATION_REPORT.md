# AlphaLens Batch 6Z — Multi-hour Live Verification Report

Date: 2026-10-27
Scope: Binance BTCUSDT / closed 5-minute candles, local-only
Overall status: **PARTIAL / FAILED SIX-HOUR ACCEPTANCE** — the original observation was retained and finalized; no replacement trial was created.

## Finalization inspection snapshot

Final evidence inspection: `2026-10-31`.

- Worker PID `34264`, scheduler PID `34265` and browser observer PID `34353` are no longer alive.
- Verified connected start: approximately `2026-10-26T19:49:33Z`; last committed candle: `2026-10-26T21:05:00Z`; final worker status update: `2026-10-27T21:09:15Z`.
- Scheduled endpoint: `2026-10-27T01:49:33Z`; the retained run did not provide a complete six-hour window before entering quarantine/stopping.
- Final retained status: `65` finalized-candle messages, `9,680` incomplete updates filtered, `17` pipeline runs (`PROCESSED=17`), `48` processor quarantines, `15` `NEW_THESIS` matches, `73` reconnects, and `last_error=missing_closed_candle_interval`.
- Final checkpoint: sequence `17`, last committed open time `2026-10-26T21:05:00Z`, status `QUARANTINED`, missing interval `2026-10-26T21:10:00Z` through `2026-10-27T20:55:00Z`.
- The database was persisted on isolated PostgreSQL `55458`, but it could not be reopened during this acceptance run because the stopped cluster retained an orphaned shared-memory block. No reset, WAL manipulation, or data deletion was attempted. The last durable database measurement before finalization was `9` thesis rows, `9` assessment relationships and `28` lifecycle events at `2026-10-26T20:30:54Z`, with states `INITIAL_TARGET_REACHED=4`, `INVALIDATED=2`, `MONITORING=3`; all relationships were `NEW_THESIS`.
- The final status counters corroborate `15` raw thesis-assessment creations and `15` new thesis identities; no exact-geometry match, ambiguity relation, or overmerge is evidenced. Final lifecycle-state totals after the database became unavailable are **not claimed**.

This is an incomplete, fail-closed observation. It is not a six-hour reliability PASS.

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

## Final live observation

The corrected run began at approximately `2026-10-26T19:49:33Z`. It ended before the scheduled endpoint after reconnect/gap handling quarantined the stream:

- worker: `STOPPED` / `QUARANTINED`
- Binance connection: `stopped`, `healthy=false`
- source: public Binance market-data WebSocket
- symbol/timeframe: BTCUSDT / 5m
- closed-candle-only: true
- finalized candles: 65 retained finality messages
- incomplete updates quarantined: 9,680
- pipeline runs: 17; processor `PROCESSED=17`, `QUARANTINED=48`
- thesis match: `NEW_THESIS=15`
- last finalized candle: `2026-10-26T21:05:00Z`
- gap state: `QUARANTINED`; `missing_closed_candle_interval`
- reconnects: `73`
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

The browser observer completed normally from `2026-10-26T19:50:17.002Z` to `2026-10-26T20:20:21.888Z` (`1,800` seconds, `180` UI samples, `119` HTTP 200 responses, zero request failures and zero console errors). The JSONL evidence contains `300` records including the completion record. Browser stability therefore passes for the captured 30-minute window, but it does not prove six-hour worker reliability.

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
- Six-hour live operation: **FAIL**. The run ended/quarantined before six hours, with a missing closed-candle interval and 73 reconnects.
- Browser stability: **PASS for the captured 30-minute window**. The browser observer completed with 180 UI samples, 119 HTTP 200 responses, zero request failures and zero console errors; this is not a six-hour or predictive claim.
- Multi-hour predictive accuracy: **NOT VALIDATED**.
- Target-extension intelligence: **NOT VALIDATED**.
- Gate 6: **NOT VALIDATED**.
- Gate 7: **BLOCKED**.
- Public launch: **NOT AUTHORIZED**.

## Next evidence collection

No worker, scheduler, browser observer, replacement observation or long-running trial was started during this acceptance run.

Report content hash (excluding this final hash line): `684674a0dbf0dd29aeeaa8fbee3e2ee7a8857793fccaac34a7b0e2431318c2ff`
