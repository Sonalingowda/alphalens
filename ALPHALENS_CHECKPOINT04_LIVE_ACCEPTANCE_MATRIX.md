# AlphaLens Checkpoint 04 — Live Acceptance Matrix

Date: 2026-10-26  
Scope: public Binance BTCUSDT / finalized 5-minute candles only

## Decisions

| Area | Status | Reason |
|---|---|---|
| A. Live ingestion integrity | **PARTIAL** | Genuine public WebSocket candle persisted, but observation was far shorter than 24 hours |
| B. Continuous operation | **PARTIAL** | Corrected 5m-only runner operated 370.04 seconds; no full-day evidence |
| C. Recovery/idempotency | **PARTIAL** | Offline recovery tests pass; live restart/reconnect not completed in a full observation |
| D. Checkpoint 04 live verification | **PARTIAL** | Mandatory 24-hour acceptance condition not met |

## Criteria

| Criterion | Result | Evidence |
|---|---|---|
| Isolated worktree and original preservation | PASS | Worktree baseline retained; original dirty checkout untouched |
| Disposable PostgreSQL/Redis isolation | PASS | `127.0.0.1:55444`, `127.0.0.1:56391`; Alembic head `20261003_0040`; 65 tables |
| Public Binance endpoint reachable | PASS | `data-api.binance.vision/api/v3/time`, HTTP 200; WebSocket connected |
| No exchange credentials/private endpoints | PASS | Public market-data endpoint only |
| Protected-test boundary enforced | PASS | Start before protected window; every candle checked; zero violations |
| BTCUSDT/5m stream only | PASS after repair | Explicit client `stream_timeframes=(MINUTE_5,)`; 5m-only URL test passed |
| Incomplete candles excluded | PASS | 178 incomplete updates ignored in corrected trial |
| Genuine finalized candle persisted | PASS | One live 5m candle, checkpoint READY, PostgreSQL MarketSnapshot |
| Durable checkpoint | PASS | Hash-bound checkpoint, sequence 1, READY |
| Model output truthful/unavailable | PASS | Pipeline `UNAVAILABLE`; `/health` returned `ARTIFACT_UNAVAILABLE` |
| API evidence | PASS | Pipeline health HTTP 200; opportunities API queried |
| Frontend evidence | PASS | Settled dashboard screenshot captured |
| Full 24-hour observation | NOT MET | Corrected trial lasted 370.04 seconds |
| Live restart/reconnect recovery | NOT MET | Not completed during full live observation |
| Full Checkpoint 04 live PASS | **NOT MET** | 24-hour criterion remains outstanding |

## Trial artifacts

- Corrected trial report JSON: `/private/tmp/alphalens-batch6t-fixed-report.json`
- Corrected checkpoint: `/private/tmp/alphalens-batch6t-fixed-checkpoint.json`
- Corrected trial report SHA-256: `02d72802ac036f82f97cb1da872ad8877ac611e0aeaea2a2c13e32bf054b77c1`
- Corrected checkpoint SHA-256: `ff23ea61c8cf92ce0de273b391f9623d92e7540f18679e4935d502ec0883d0ca`
- Frontend screenshot SHA-256: `626076baae41acc6a1c4777433780703bf1396881d6112758633b73d0c2c3891`

## Non-claims

This matrix does not claim 24/7 operation, predictive validity, confidence calibration, profitability, external notification delivery, trading, deployment, Gate 6 validation, Gate 7 certification, or public launch readiness.

## Next required batch

Run the same isolated runner for the full 24-hour duration with a preplanned controlled restart/reconnect and resource monitoring. Stop on a protected-window violation, unverified source, unrecovered gap, persistence failure or scope drift.

Report content SHA-256 (excluding this footer line): `215e4aa5566f11b6fac73461555612926bd6c9a4417f48c2581e2c6da470baef`.
