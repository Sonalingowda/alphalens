# AlphaLens Batch 6W-HOTFIX-01 — API Stability Report

Date: 2026-10-27 IST / observations recorded 2026-10-26 UTC

## Decision

**P0 hotfix: PASS for the bounded local reliability verification.**

The intermittent Opportunities error was a frontend state-transition defect. It did not correspond to an Opportunities API outage in the observed running stack. The fix is isolated to the frontend polling state machine and preserves truthful API errors, empty states and model-unavailable semantics.

## Reproduction and root cause

The observed frontend message was:

```text
Live Prediction API unavailable
Load failed
Start the API and refresh this page
```

The relevant original logic in `frontend/components/opportunities/opportunity-feed.tsx` rendered `ApiUnavailable` when:

```text
error !== null && (failureCount >= 3 || items.length === 0)
```

The backend can legitimately return a successful empty page when Detection has produced no opportunity. In that valid state, `items.length === 0`. One transient polling failure therefore immediately replaced the valid no-candidate state with an outage card. Refreshing caused the server-rendered successful empty response to be shown again until the next transient failure.

Observed backend evidence did not support backend instability:

- `/api/v1/opportunities` returned HTTP 200 repeatedly with `items: []` and `partial_failures: []`.
- The response correctly reported `coverage_status: assessment_only_model_unavailable`, `model_score_status: unavailable_without_approved_artifact`, and `notification_status: intent_persistence_only`.
- PostgreSQL/Redis readiness remained ready.
- The worker remained running with a clear gap state and current checkpoint.
- `/health` returned HTTP 503 with `ARTIFACT_UNAVAILABLE`; this is an intentional truthful model-health response and is independent of the Opportunities endpoint.

## Fix

Changed `frontend/components/opportunities/opportunity-feed.tsx`:

- Removed `items.length === 0` from the outage condition.
- A successful empty response remains the explicit `No qualified opportunities` state.
- A transient failure shows the reconnecting notice while preserving the last-good state, including an empty state.
- An outage card appears only after three consecutive failed polls.
- Added an in-flight guard so interval ticks cannot overlap requests.
- Added request epoch invalidation, `AbortController` cancellation and mounted-state checks so stale responses cannot update state after unmount or filter changes.

Changed `frontend/lib/api-client.ts`:

- Added optional `AbortSignal` propagation to the Opportunities request.

Changed `frontend/tests/opportunity-feed.test.tsx`:

- Replaced the incorrect immediate-empty-state outage expectation with a regression test for transient failure over a legitimate empty state.
- Added a regression test proving repeated failures eventually surface an outage even when the last-good state is empty.

## Running application evidence

Private local stack:

- Frontend: `http://127.0.0.1:13003`
- Backend: `127.0.0.1:18003`
- PostgreSQL: `127.0.0.1:55448`
- Redis: `127.0.0.1:56395`
- State: `/private/tmp/alphalens-local-20261026`

At final verification the local API, worker and frontend processes were alive. Batch6U PID `17902` remained alive and was not modified.

## Stability verification

The real Opportunities endpoint was polled at the frontend’s 15-second interval for 40 cycles over approximately 10 minutes:

- Cycles: 40
- Interval: 15 seconds
- HTTP 200 responses: 40
- HTTP failures: 0
- Response state: genuine empty/no-candidate, model scoring unavailable

The frontend root rendered successfully during the probe. An interactive browser automation binary was not installed in the available environment, so browser-console capture was unavailable; the actual Next.js-rendered HTML, real API responses and frontend Vitest/jsdom behavior were verified.

## Restart and recovery

The isolated local stack was stopped and restarted:

- During restart, the API correctly became unreachable (`curl` exit 7 / HTTP 000).
- After restart, `/health/readiness` returned HTTP 200.
- A correctly formed Opportunities request returned HTTP 200 with the same truthful empty/model-unavailable response.
- The one HTTP 422 observed immediately after restart was from an intentionally incomplete diagnostic request omitting required `as_of`; the backend logged `REQUEST_SCHEMA_INVALID`. The frontend always supplies `as_of`, so this was not a frontend failure.

## Test results

- Frontend Vitest: `33 passed` across 7 files.
- Frontend typecheck: passed.
- Frontend ESLint: passed.
- Frontend production build: passed.
- Existing backend baseline remains `938 passed, 27 skipped, 497 subtests`.
- Changed-file Ruff and `git diff --check`: passed.

## Boundaries preserved

- Original dirty checkout untouched.
- Batch6U and its independent ports/resources untouched.
- No model fitting, artifact promotion, trading, external notifications, protected data access or deployment.
- No fabricated candles, opportunities, confidence or ranking.

## Final status

The intermittent local Opportunities outage is fixed at its root cause. Legitimate empty results remain empty states, transient failures preserve successful UI state, repeated failures remain visible, and stale polling responses are cancelled/ignored. The local stack remains running.

Gate 6 remains NOT VALIDATED. Gate 7 remains BLOCKED. Public launch remains unauthorized.

Report SHA-256 (excluding this final hash line): `57ea2d8f9cbf786efa2bde8e5dc1596377442b44d348a3ac2eeb32c2d4396b4c`
