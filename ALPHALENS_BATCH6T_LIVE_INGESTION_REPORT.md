# AlphaLens Batch 6T — Live Binance Ingestion Report

Date: 2026-10-26  
Scope: public Binance BTCUSDT / finalized 5-minute candles only

## Final decisions

- A. Live ingestion integrity: **PARTIAL**
- B. Continuous operation: **PARTIAL**
- C. Recovery and idempotency: **PARTIAL**
- D. Checkpoint 04 live verification: **PARTIAL**

The isolated live trial connected to the public Binance WebSocket, received genuine BTCUSDT market events, filtered incomplete updates, persisted finalized 5m candles through the existing ingestion and runtime pipeline, and produced a durable READY checkpoint. It did not complete the required 24-hour observation, so no live PASS is claimed.

Gate 6 remains NOT VALIDATED. Gate 7 remains BLOCKED. Public launch remains unauthorized.

## 1. Preservation and source identity

Worktree:

`/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`

Baseline retained:

- Commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Branch: detached `HEAD`
- Final state: uncommitted isolated changes.

The original dirty checkout `/Users/sonalingowda/Downloads/alphalens` was not modified. Existing Batch 6N–6S changes and evidence were preserved. No exchange account credentials, private endpoints, orders, notifications, production resources, protected data or research manifests were accessed.

Governing report hashes verified before execution:

- Batch 6S runtime report: `2beebb3d3f6ebacbaae772dc71f49d9b2b5a176427a0dd295cbc31a849309ef3`
- Checkpoint 04 matrix: `40e5d5351eaffe7daccb48051f6333fa5c402dd20d97fbaf8a8496b25ed88ccc`
- Checkpoint 03 report: `fdde7380cbae3ed32f84e87aa7583b936ff54fb9e14e91e4171e1bc55bade0c2`
- Batch 6P approval matrix: `328a5e5b9ad5c0a9cf5929bedf451c6b9cb12bce1a13a83978c81140c94a7b12`
- Batch 6O protocol package: `ab1c18f7f434e6971527a6ab48716ecfab102c41b64bb7ebe37af534bb5fcb53`

At trial start, UTC was `2026-10-26T16:51:30Z`, before the protected-test window. The runner checked every finalized candle against:

`2027-01-11T00:00:00Z` through `2027-02-09T23:55:00Z` inclusive.

No protected-period candle was collected or inspected.

## 2. Isolated environment

Fresh disposable services were created separately from prior checkpoints:

| Service | Identity | Isolation |
|---|---|---|
| PostgreSQL | 16.12, `127.0.0.1:55444`, database `alphalens_batch6t` | Data directory `/private/tmp/alphalens-batch6t-pg-20261026`, PID 13888, unique roles |
| Redis | 8.10.0, `127.0.0.1:56391` | Directory `/private/tmp/alphalens-batch6t-redis-20261026`, PID 13911, loopback-only, unique password |
| Migrations | Alembic head `20261003_0040` | 65 public tables; runtime role granted only to this disposable database |

No Docker, Colima, cloud, production, external demo or existing checkpoint services were used. Public Binance reachability was verified with `https://data-api.binance.vision/api/v3/time`, HTTP 200. No exchange credentials were supplied.

## 3. Implementation changes

Batch 6T added:

- `backend/scripts/checkpoint04_live_trial.py` — bounded public WebSocket runner with finality filtering, hard protected-window exclusion, no-backfill behavior, checkpoint binding, bounded runtime, redacted evidence and no trading/notification paths.
- `backend/app/live_market_data/binance.py` — explicit `stream_timeframes` parameter. Existing default behavior is preserved; the live trial now subscribes only to `btcusdt@kline_5m`.
- `backend/tests/test_continuous_runtime.py` — verifies 5m-only stream URL in addition to existing Batch 6S coverage.

The runner reuses `BinanceKlineParser`, `BinanceWebSocketClient`, `ContinuousClosedCandleProcessor`, `LiveMarketIngestionService`, PostgreSQL repositories and `build_runtime_pipeline`. It does not replace the runtime pipeline or create synthetic market data.

## 4. Trial timeline and results

### Initial smoke

- UTC: `2026-10-26T16:52:28.263359Z`–`2026-10-26T16:54:38.189183Z`
- Requested duration: 120 seconds
- WebSocket messages: 121
- Incomplete updates: 121
- Finalized candles: 0
- Network/parse errors: 0
- Purpose: verify public connection and closed-candle filtering before a close boundary.
- Report SHA-256: `c4610e3f2229e8cb2f1115971ca653a8f563bd59cb624bf3c01231cc30c8d1d`

### Pre-fix mixed-stream trial

The inherited client default subscribed to both 5m and 15m. The trial correctly rejected the 15m event under the BTCUSDT/5m scope and stopped. This exposed a real stream-scope defect; it was repaired by adding explicit stream-timeframe selection and configuring the trial to 5m only.

- UTC: `2026-10-26T16:54:46.829127Z`–`2026-10-26T17:00:10.295846Z`
- Finalized events: 3
- 5m candles processed: 2
- Processing error: one unsupported 15m event
- No protected data accessed
- Report SHA-256: `9b48677b6f52ac95497b51b1b8577ec1639acecfa446f2938f804f373c2d6a27`

### Corrected 5m-only trial

- Endpoint: `wss://data-stream.binance.vision`
- Actual stream: `btcusdt@kline_5m`
- UTC: `2026-10-26T17:00:46.073620Z`–`2026-10-26T17:06:56.116396Z`
- Requested duration: 360 seconds
- Actual duration: 370.04 seconds including orderly WebSocket shutdown
- Messages received: 179
- Incomplete updates: 178
- Finalized 5m candles: 1
- Processed finalized candles: 1
- Duplicate candles: 0
- Processing errors: 0
- Reconnects: 0
- Checkpoint: READY, sequence 1
- Last finalized candle: `2026-10-26T17:00:00Z`
- Checkpoint source identity SHA-256: `ab09e18c05fc8b2aa5ae1d7b4b1eb03839c1df3fef9969bf15f57809a1a1b48f`
- Checkpoint file SHA-256: `ff23ea61c8cf92ce0de273b391f9623d92e7540f18679e4935d502ec0883d0ca`
- Report SHA-256: `02d72802ac036f82f97cb1da872ad8877ac611e0aeaea2a2c13e32bf054b77c1`

Pipeline outcome for the finalized candle was `UNAVAILABLE` because the existing feature warm-up/model-dependent runtime contract was not available for a single live candle. No model score, confidence, rank, notification or trade was created.

## 5. Persistence and API evidence

The disposable PostgreSQL database contained:

| Entity | Count |
|---|---:|
| MarketSnapshot | 3 |
| FeatureSnapshot | 2 |
| MarketContext | 2 |
| DetectionAttempt | 2 |
| Opportunity/Plan/Qualification | 0 |

The three market snapshots were genuine live 5m candles at 16:50, 16:55 and 17:00 UTC from the short observations. The first two records arose from the pre-fix window and the third from the corrected trial; no protected or historical research data was imported.

The actual backend at `127.0.0.1:18002` returned:

- `/api/v1/pipeline/health`: HTTP 200 with pipeline task state.
- `/health`: HTTP 503 `ARTIFACT_UNAVAILABLE`, correctly preserving model-readiness separation.
- `/api/v1/opportunities?...`: assessment-only coverage with no qualified opportunities for the live one-candle window.
- Redis connectivity: `PONG`.

The frontend ran at `127.0.0.1:13002` using explicit local-demo mode. Settled dashboard screenshot:

[dashboard-settled.png](/private/tmp/alphalens-batch6t-screens-20261026/dashboard-settled.png)

SHA-256: `626076baae41acc6a1c4777433780703bf1396881d6112758633b73d0c2c3891`

It displayed BTCUSDT/5m snapshot availability, the actual live close, UTC availability, complete data integrity, no qualified opportunities, and the truthful API-unavailable/model-unavailable state. It displayed no fabricated signal or confidence.

## 6. Recovery and idempotency

The Batch 6S processor’s offline tests remain the recovery evidence: durable restart, concurrent duplicate delivery, gap quarantine, out-of-order rejection, bounded retry and interrupted checkpoint commit all pass. The live runner used the same processor and persisted a READY checkpoint.

A full live restart/reconnect recovery scenario was not completed within the short observation. The first pre-fix trial stopped on the unsupported 15m stream event; after the fix, the corrected trial had zero reconnects and no processing error, but it was not a 24-hour run.

## 7. Test results

| Check | Result |
|---|---|
| Focused live/continuous tests | PASS: 55 passed |
| Full backend suite | PASS: 934 passed, 23 skipped, 497 subtests |
| Backend Ruff (`app tests`) | PASS |
| Frontend Vitest | PASS: 32 tests |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Frontend build | PASS |
| `git diff --check` | PASS |
| Repository-wide `scripts/` Ruff | Existing unrelated findings remain; not used as a release pass |

Known existing warnings were reported: Starlette/httpx deprecation and an asyncpg cancellation resource warning. No warnings or failures were hidden.

## 8. Acceptance status

### A. Live ingestion integrity — PARTIAL

Public Binance connectivity, symbol/stream scope, finality filtering, timestamp boundary enforcement, persistence and checkpoint integrity were demonstrated. A full integrity PASS requires the complete 24-hour observation.

### B. Continuous operation — PARTIAL

The corrected runner operated continuously for 370 seconds with 179 messages and one finalized candle. It did not run 24 hours; continuous operation is therefore not verified.

### C. Recovery and idempotency — PARTIAL

The shared processor has passing offline recovery/idempotency tests and the live checkpoint was READY. A live restart/reconnect and 24-hour duplicate/gap observation remain outstanding.

### D. Checkpoint 04 live verification — PARTIAL

The full acceptance requirement explicitly requires a complete evidenced 24-hour live trial. This batch produced a shorter genuine live trial and does not claim PASS.

## 9. Remaining blockers and next step

- Complete a full 24-hour public Binance BTCUSDT/5m observation in the isolated environment.
- Include at least one controlled worker restart/reconnect during that observation and verify checkpoint continuation.
- Verify expected 5m finalized-candle count against the actual UTC interval, duplicate count, gaps and resource stability over the full period.
- Production authentication, approved model artifact, scoring/ranking, notifications, Gate 6 and Gate 7 remain independently blocked.

Report content SHA-256 (excluding this footer line): `71ebce1e3644ff6ded3c18a2b30d2e975a3294ec73888d8a009ba84f9b28e8d4`.
