# AlphaLens Localhost-First Reliability Handover — 2026-11-02

## Scope and safety

Work was performed only in `/private/tmp/alphalens-localhost-first-20261102` on
branch `localhost-first-reliability-20261102`, based on integration commit
`ece17fa94a1b3def675c87311e407ece94290794`. The protected checkout at
`/Users/sonalingowda/Downloads/alphalens` was not modified. Existing localhost
processes on ports 13003/18003 were owned by earlier isolated worktrees, so they
were not stopped or taken over. Verification used separate loopback ports.

No database directory was deleted, reset, reinitialized, or overwritten. The
recovered Batch 6AA PostgreSQL cluster remained at
`/private/tmp/alphalens-batch6aa-local-recovery/postgres`. Its known backup
remains `/Users/sonalingowda/Library/Application Support/AlphaLens/local-state-backups/pre_batch6z_20261026T1948Z.dump`
with SHA-256
`5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`.

## Implementation

The local operator stack now has an explicit `ALPHALENS_LOCAL_ONLY=true` mode.
It is accepted only in development/test environments and only with loopback API
and frontend binding. It generates a private mode-600 access-token file,
requires that token through a HttpOnly local session cookie, rejects non-loopback
requests, and leaves Clerk middleware unchanged when local-only mode is off.
Paper-tracking controls remain unavailable without Clerk authentication; no
state-changing authorization was bypassed. The legacy demo-mode flag is no
longer an authentication bypass.

`local_stack.py` now starts PostgreSQL and Redis with persistent state, refuses
occupied API/frontend ports, waits for readiness, starts only the API and
frontend, and deliberately does not start the quarantined market-data worker.
The dashboard polling effect now fetches immediately on mount and view changes,
so Active/Monitoring/History does not wait for the 15-second interval.

## Verification matrix

| Workstream | Result | Evidence |
|---|---|---|
| Local-only auth boundary | PASS | Unauthenticated browser request redirected to `/local-login`; invalid/missing token rejected; valid token created HttpOnly `alphalens_local_session`; non-Clerk production path remains Clerk-based. |
| Local stack startup | PASS | Separate stack started at `http://localhost:13013/local-login`, API `127.0.0.1:18013`, PostgreSQL `55461`, Redis `56398`; readiness checks passed. |
| Controlled restart | PASS | The isolated stack stopped and restarted with the same runtime environment and persistent cluster; frontend returned HTTP 200, PostgreSQL returned `1`, Redis returned `PONG`. |
| Preserved recovered database | PASS | Existing cluster stayed online and queryable; counts remained 28 theses, 28 assessment relationships, 84 lifecycle events, 791 audits. No writes were made to historical opportunity tables. |
| Current backend source against recovered DB | PASS | Separate API on `127.0.0.1:18014` served the preserved records; Active returned 0 and History returned 2 (`ENTRY_MISSED`, `INVALIDATED`). |
| Browser dashboard | PASS | Real headless Chrome session authenticated with the generated local token. Dashboard rendered stopped-feed warning, zero Active, model-unavailable state, and History cards with both retained lifecycle outcomes. |
| Truthful model status | PASS | `/health` returned HTTP 503 `ARTIFACT_UNAVAILABLE`; no model artifact was invented or hidden. |
| Quarantined worker safety | PASS | Worker was not started, quarantine status was preserved, and local runtime status remained stopped/unconfigured for the disposable stack. |
| Genuine live feed restoration | PARTIAL | No new observation was launched. Preserved evidence still reports `QUARANTINED`, `missing_closed_candle_interval`, and stopped worker; no unverified replay or fabricated candle was introduced. |
| Predictive validity | NOT VALIDATED | Operational/browser reliability does not establish predictive accuracy or profitability. |

## Preserved feed evidence

The retained worker status reports Binance public WebSocket BTCUSDT/5m,
`closed_candles_only: true`, `worker_status: STOPPED`, `gap_status: QUARANTINED`,
`last_error: missing_closed_candle_interval`, 15 finalized candles, 2,739
incomplete updates, 13 processed pipelines, 2 quarantined pipeline outcomes,
36 reconnects, and 4 `NEW_THESIS` matches in that retained recovery snapshot.
The earlier Batch 6Z final evidence remains authoritative for the six-hour
failure (65 finalized candles, 73 reconnects, 17 checkpoints, and final
quarantine). This work did not relabel that observation as successful and did
not claim that the missing interval was repaired.

## Tests

- Backend: `954 passed, 30 skipped, 497 subtests passed`; two pre-existing
  warnings (Starlette/httpx deprecation and an asyncpg resource warning).
- Frontend: `34 passed`.
- Frontend typecheck: passed.
- Frontend lint: passed.
- Frontend production build: passed.
- Python compile and `git diff --check`: passed.
- Browser: authenticated local owner flow, stopped feed, Active/History views,
  and model-unavailable response verified.

## Files changed

- `backend/app/settings.py`
- `backend/scripts/local_stack.py`
- `backend/tests/test_local_stack.py`
- `backend/.env.example`
- `frontend/proxy.ts`
- `frontend/app/layout.tsx`
- `frontend/app/api/local-auth/login/route.ts`
- `frontend/app/api/local-auth/logout/route.ts`
- `frontend/app/local-login/page.tsx`
- `frontend/components/dashboard/app-shell.tsx`
- `frontend/components/opportunities/paper-track-control.tsx`
- `frontend/components/opportunities/opportunity-feed.tsx`
- `frontend/tests/opportunity-feed.test.tsx`
- `frontend/.env.example`
- `frontend/README.md`

## Remaining blockers and next action

The quarantined Binance worker and missing-candle root cause remain unresolved;
the worker must stay stopped until a bounded, evidence-backed replay/reconnect
repair is separately reviewed. The current localhost recovery stack uses a
disposable local database by default; the preserved historical cluster must be
selected explicitly when the owner wants historical records. Existing port
13003/18003 services were intentionally left undisturbed because their process
ownership belonged to another isolated worktree.

Recommended next milestone: **Multi-Horizon Economically Meaningful Opportunity
Research**. Prepare only a research execution proposal covering 10m, 30m, 1h,
2h, and 4h horizons; realistic fees/slippage; chronological entry, target,
stop, target-first/stop-first and same-candle rules; unfilled and censored
outcomes; time-to-target uncertainty; net return by position size; provenance;
and chronological train/validation/test separation. Do not acquire datasets,
fit models, tune thresholds, access protected-test data, or promote a strategy
without separate approval.
