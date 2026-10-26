# AlphaLens Batch 6W Hotfix 02 — Browser API Stability

## Decision

**PASS for the recurring local Opportunities API defect.** The defect was reproduced in a real Chromium browser, fixed at its configuration boundary, regression-tested, and observed for a complete 30-minute browser polling window followed by an API-process restart and automatic recovery.

This is a local product reliability result only. Gate 6 remains NOT VALIDATED, Gate 7 remains BLOCKED, and public launch remains unauthorized.

## Scope and preservation

- Engineering worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`
- Baseline commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Original checkout was not modified.
- Batch 6U PID `17902` remained alive and was not restarted or modified.
- Local application resources remained isolated at PostgreSQL `127.0.0.1:55448`, Redis `127.0.0.1:56395`, API `127.0.0.1:18003`, and frontend `127.0.0.1:13003`.

## Reproduced browser failure

The initial server-rendered page loaded, but the real browser's client polling requested:

`GET http://127.0.0.1:8000/api/v1/opportunities?as_of=2026-10-26T18%3A43%3A48.685Z&instrument=BTCUSDT&timeframe=5m`

Chrome reported:

- CORS policy rejection: no `Access-Control-Allow-Origin` header for origin `http://127.0.0.1:13003`.
- Network failure: `net::ERR_FAILED`.
- The request was initiated by the client polling script.

This explains the symptom: server rendering used the local server environment and reached port 18003, while the browser bundle did not receive a public API-base variable and fell back to the client default port 8000.

## Root cause

`frontend/lib/api-client.ts` correctly prefers `NEXT_PUBLIC_ALPHALENS_API_BASE_URL`, then `ALPHALENS_API_BASE_URL`, then its default. The local launcher previously supplied only `ALPHALENS_API_BASE_URL` to Next.js. Next.js does not expose the non-public variable to the browser bundle, so browser polling used `http://127.0.0.1:8000`.

The defect was therefore a local launcher/browser configuration split, not a Detection, model-artifact, PostgreSQL, Redis, CORS-policy or polling-state failure.

## Changes

1. `backend/scripts/local_stack.py`
   - Added `NEXT_PUBLIC_ALPHALENS_API_BASE_URL=http://127.0.0.1:{APIPORT}` to the isolated frontend environment.
   - This keeps server-side and browser-side requests on the same isolated local API.
2. `frontend/tests/api-client.test.ts`
   - Added a regression test proving the public browser variable wins over the server-only fallback and produces an API request to port 18003.
3. `frontend/.env.example` and `frontend/README.md`
   - Documented the required public browser API variable.

No strategy, Detection threshold, model contract, authentication protection, notification provider or production configuration was changed.

## After-fix browser evidence

Real Chromium was connected to the running frontend through the Chrome DevTools Protocol. After restarting only the local application stack to rebuild the Next.js environment, the browser requested:

`GET http://127.0.0.1:18003/api/v1/opportunities?...&instrument=BTCUSDT&timeframe=5m`

The first post-fix trace received HTTP 200 and recorded no network failure. The complete stability observation ran for exactly 1,800 seconds (30 minutes):

| Evidence | Result |
|---|---:|
| Opportunity poll requests during 30-minute window | 120 |
| Responses completed by the exact cutoff | 119 |
| Final in-flight request completed immediately afterward | 1, HTTP 200 |
| Network failures | 0 |
| Browser console errors | 0 |
| Wrong-port requests after fix | 0 |

The final in-flight request was separately observed and completed with HTTP 200. The page remained usable without manual refresh.

## API restart and recovery

Only the local API process was restarted:

- Before: local API PID 26908.
- After: local API recovery PID 29766.
- Worker, PostgreSQL and Redis were not restarted.
- Browser recovery trace after the interruption: 5 opportunity requests, 5 HTTP 200 responses, 0 failed requests, 0 console errors.

The local runtime status after recovery reported API, worker and frontend alive; worker status `RUNNING`, persistence `AVAILABLE`, gap status `CLEAR`, and model status `UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT`. This model-unavailable state remained truthful and did not prevent Detection opportunity retrieval.

## Tests

Commands and results:

- `PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH" npm test -- --run` — **34 passed**, 8 test files.
- `PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH" npm run typecheck` — **passed**.
- `PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH" npm run lint` — **passed**.
- `PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH" npm run build` — **passed**.
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_opportunity_api.py` — **21 passed**.
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_prediction_api.py` — **18 passed**.
- `PYTHONPATH=. .venv/bin/pytest -q` — **938 passed, 27 skipped, 497 subtests passed**; two existing runtime warnings.
- `.venv/bin/ruff check backend/scripts/local_stack.py backend/tests/test_opportunity_api.py` — **passed**.
- `git diff --check` — **passed**.

An initial repository-root pytest invocation used an incorrect path/environment and collected no tests; it was corrected with the actual module paths and `PYTHONPATH=.`. It is not counted as a code failure.

## Current local state

- Frontend: `http://127.0.0.1:13003/`
- Backend: `http://127.0.0.1:18003`
- API, worker and frontend: running at final verification.
- Market worker: Binance public BTCUSDT/5m, finalized candles only.
- External notifications: disabled.
- Trading: disabled.
- Approved BTCUSDT/5m model artifact: unavailable; scores, ranking and confidence remain unavailable.

## Remaining limitations

This hotfix proves browser/API endpoint stability for the local Opportunities polling path. It does not prove production Clerk authentication, live 24/7 operation, model validation, notification delivery, Gate 6, Gate 7 or public launch readiness.

## Report hash

Content SHA-256 excluding this final hash line: `28e573efe410bd3ab4d6b5f382e8f94616130f15e1faedd9b9172e33cea92bcf`
