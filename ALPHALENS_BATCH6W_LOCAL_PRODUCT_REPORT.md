# AlphaLens Batch 6W — Local Product Report

Date: 2026-10-26 (UTC)

## Decision

**LOCAL PRODUCT: PASS for the bounded private-local product slice.**

The localhost application is running on an isolated stack and has processed genuine finalized Binance BTCUSDT/5m candles through the existing ingestion, runtime pipeline and persistence path. The live opportunity result during this observation was a genuine no-candidate outcome. This is operational/product evidence only; it is not Gate 6 predictive validation or Gate 7 certification.

## Isolation and source identity

- Worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`
- Baseline HEAD: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Original dirty checkout was not modified.
- Batch 6U remained separate and alive as PID `17902`, using ports `55446` and `56394`.
- Local state: `/private/tmp/alphalens-local-20261026`
- Local runtime identity: `alphalens.local.product.binance.btcusdt.5m.v1`
- Checkpoint source descriptor digest: `6f844a74e89537ff26c7195e895416b42bb78a31a01618ab3d1e44e3b09210c5`.
  This is an operational identity digest, not a historical research-dataset hash.

## Running services

| Component | Identity | Result |
|---|---|---|
| Frontend | `127.0.0.1:13003` | Running; renders local owner mode and live runtime state |
| Backend | `127.0.0.1:18003` | Running; readiness returned PostgreSQL/Redis/schema ready |
| PostgreSQL | `127.0.0.1:55448`, state under local state directory | PostgreSQL 16.12, migration head `20261026_0041` |
| Redis | `127.0.0.1:56395`, loopback-only | Running with local password and isolated AOF state |
| Market worker | Local supervised PID recorded in `pids.json` | Running; Binance public WebSocket, BTCUSDT/5m only |

No production credentials, external notification provider, private exchange endpoint, trading endpoint or protected research resource was used.

## Genuine live path

The local worker used the existing `LiveMarketIngestionService`, `BinanceKlineParser`, `ContinuousClosedCandleProcessor` and `build_runtime_pipeline`.

Observed after startup/restart:

- Public source: `https://data-api.binance.vision` for bounded 250-candle warmup and Binance public WebSocket for new updates.
- Only closed 5-minute kline events were passed to the processor; interim updates were counted and ignored.
- Finalized candle `2026-10-26T18:10:00Z` was processed after the restart.
- Checkpoint sequence advanced to `2` with last committed candle `2026-10-26T18:10:00Z`.
- Worker reported `healthy: true`, `gap_status: CLEAR`, `processor:PROCESSED: 1`, and no processing error.
- Pipeline stages completed for the genuine candle: feature snapshot, market context and opportunity detection.
- Pipeline outcome: `NO_CANDIDATE`; no opportunity was fabricated.
- API market evidence exposed a finalized candle at `2026-10-26T18:10:00Z`, source digest `368dbde77110048c8c1cb9fb25e97f1577740e5bf1b7f26aa2ba200aadb7365e` and result hash `6297dc3efebd1ac795f282a41b0b466b2ad760b444dbb1c2a23219d737810ca0`.
- Opportunity API returned an empty list with `coverage_status: assessment_only_model_unavailable`, `model_score_status: unavailable_without_approved_artifact`, and `notification_status: intent_persistence_only`.
- Local PostgreSQL contained 1,009 immutable runtime aggregates after warmup and live processing.

The prior live candle `2026-10-26T18:05:00Z` was also processed before the final restart. The restart preserved its checkpoint and the next candle advanced it, demonstrating durable resume rather than a reset.

## Frontend verification

HTTP/browser-facing localhost verification passed:

- `http://127.0.0.1:13003` rendered successfully.
- The page displayed `Local owner mode`, `BTCUSDT · finalized 5m candles`, the last processed timestamp, connected feed state, current market data, and the explicit model-unavailable notice.
- The opportunity feed displayed the truthful empty/no-candidate state.
- The existing dashboard/detail/history routes remain available; no live opportunity was invented to exercise a detail page.

The local owner mode is deliberately separate from production Clerk. Production/non-demo frontend mode still requires Clerk configuration, and production authentication was not claimed as verified.

## Changes in this batch

- Added `backend/scripts/local_market_worker.py` for the private BTCUSDT/5m worker.
- Added `backend/scripts/local_stack.py` for isolated start, stop, status, native PostgreSQL/Redis initialization, migrations and supervised local processes.
- Added development-only `/api/v1/local-runtime/status` read-only status exposure.
- Added frontend runtime status display and explicit local owner-mode rendering without Clerk keys.
- Restricted the local opportunity filter to the authoritative 5m market scope.
- Added an optional warmup limit while preserving the existing default warmup API behavior.
- Added launcher protection against duplicate starts and bounded process-group shutdown.
- No approved model artifact, confidence, ranking, external notification or trading behavior was introduced.

## Verification commands and results

- `backend/.venv/bin/python backend/scripts/local_stack.py start` — passed.
- `backend/.venv/bin/python backend/scripts/local_stack.py status` — all local API, worker and frontend PIDs alive.
- `curl http://127.0.0.1:18003/health/readiness` — PostgreSQL, Redis and schema ready.
- `curl http://127.0.0.1:18003/api/v1/local-runtime/status` — connected worker, clear gap, finalized candle recorded.
- `curl http://127.0.0.1:18003/markets/live?instrument=BTCUSDT&timeframe=5m` — genuine finalized market response.
- `curl http://127.0.0.1:18003/api/v1/opportunities?...` — truthful empty assessment-only response.
- Node `v22.23.3`; frontend Vitest `32 passed`, typecheck passed, ESLint passed, production build passed.
- Backend focused tests: `49 passed`.
- Backend full suite from `backend/` with `PYTHONPATH=.`: `938 passed, 27 skipped, 497 subtests`; two existing async cleanup/deprecation warnings.
- Changed runtime files Ruff: passed.
- `git diff --check`: passed.
- Restart test: stop/start preserved checkpoint sequence `1` and `2026-10-26T18:05:00Z`; subsequent live processing advanced to sequence `2` at `18:10:00Z`.

## Remaining limitations

1. This is a local private product, not a 24/7 production guarantee. It depends on the Mac remaining awake, connected and running the documented process.
2. No approved BTCUSDT/5m predictive artifact exists. Model score, confidence, ranking, outcomes and predictive claims remain unavailable.
3. No live opportunity occurred during this bounded observation; the no-candidate result is valid.
4. Production Clerk authentication and authenticated browser sessions remain unverified.
5. Batch 6U’s separate 24-hour observation remains in progress and was not disturbed.
6. Gate 6 remains NOT VALIDATED, Gate 7 remains BLOCKED and public launch remains unauthorized.

## Report hash

Report SHA-256 (excluding this final hash line): `2ca6b725ee1e5f58c94a96b21b9b0da5aeadfc4caf07f5d577261c92dac5c80c`
