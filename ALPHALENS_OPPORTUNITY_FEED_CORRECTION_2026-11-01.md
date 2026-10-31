# AlphaLens Opportunity Feed Correction — 2026-11-01

## Scope

This isolated change corrects presentation and read-side classification only. It does not change detection thresholds, plan geometry, model status, historical rows, lifecycle events, or market data.

## Result

- Active, Monitoring, and History are explicit API views and dashboard tabs.
- Active requires a fresh server-evaluated observation, a running/healthy feed, and `ENTRY_AVAILABLE` thesis state.
- Monitoring retains recent non-terminal setups, including missed-entry setups, but displays the stopped/quarantined warning and never calls them live.
- History contains terminal, expired, stale, and otherwise unavailable-feed records. Historical records are not deleted or rewritten.
- `INITIAL_TARGET_REACHED` is displayed as `TARGET REACHED / ENTRY UNCONFIRMED`; the system has no execution confirmation and does not infer a fill.
- Risk/reward is rounded to two decimal places in the UI only.
- Card age is calculated from server-provided `last_observed_at` and `age_minutes`, not browser wall-clock state.
- Runtime status is read from the existing local worker status file. The current preserved status is `STOPPED`/`QUARANTINED`, so it correctly yields no Active opportunities.

## Evidence

The preserved worker status reports `worker_status=STOPPED`, connection `state=stopped`, `healthy=false`, checkpoint `gap_status=QUARANTINED`, `last_error=missing_closed_candle_interval`, and 36 reconnects. The existing localhost stack returned frontend HTTP 200 and continued to report the unavailable approved model artifact truthfully. Its running API/frontend processes are from the prior recovery worktree; they were not interrupted or replaced by this isolated change.

## Verification

- Backend opportunity API regressions: 24 passed.
- Frontend tests: 34 passed across 8 files under Node 20.20.0.
- Frontend typecheck: passed.
- Frontend lint: passed.
- Frontend production build: passed under Node 20.20.0 after using a copied dependency directory in this isolated worktree.
- Python compile and `git diff --check`: passed.
- Live preserved frontend: HTTP 200.
- Live preserved API runtime status: stopped/quarantined as above.

The running localhost API was not hot-restarted from this worktree because its dependency environment lacks `clerk_backend_api` and its existing processes belong to the prior recovery stack. Therefore live browser verification of the new tabs is still pending a controlled stack restart with a complete dependency environment.

## Remaining blockers

1. The exact Batch 6Z transport/reconnect gap path remains an evidence-diagnosis item; this change does not replay candles or alter ingestion.
2. The historical PostgreSQL recovery remains dependent on the previously preserved recovery cluster and backups.
3. A controlled restart is required to expose this branch’s API/UI changes on ports 18003/13003.
4. Predictive accuracy and strategy validity remain unvalidated; operational feed classification is not predictive evidence.

## Next milestone proposal

Prepare a research-only Multi-Horizon Economically Meaningful Opportunity study for 10m, 30m, 1h, 2h, and 4h holding horizons. Define chronological entry/target/stop labeling, target-first versus stop-first ordering, same-candle ambiguity, unfilled and censored outcomes, realistic fees/slippage, position-size net returns, time-to-target distributions, provenance, and chronological train/validation/test separation. Do not acquire datasets, fit models, tune thresholds, access protected-test data, or promote a strategy until separately approved.
