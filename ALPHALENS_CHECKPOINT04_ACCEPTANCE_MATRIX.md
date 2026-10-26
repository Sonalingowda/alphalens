# AlphaLens Checkpoint 04 Acceptance Matrix

Date: 2026-10-26  
Scope: Binance BTCUSDT / closed 5-minute candles only

## Decision summary

| Decision | Status | Basis |
|---|---|---|
| A. Offline runtime engineering | **PASS** | Genuine bounded replay, durable checkpoint, failure/recovery tests, persistence/API/frontend checks, and regression suite passed |
| B. Full continuous/live operation | **NOT VERIFIED** | No live Binance acquisition was authorized or executed |

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Genuine retained dataset SHA verified | PASS | `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc` |
| Closed-candle processing works | PASS | Existing Binance parser plus `ContinuousClosedCandleProcessor`; incomplete candles rejected by contract |
| Durable checkpoints work | PASS | Atomic hash-bound filesystem checkpoint; final sequence 300, status READY |
| Idempotency and concurrency tested | PASS | Exact duplicate, concurrent delivery, immutable PostgreSQL identity tests |
| Restart recovery verified | PASS | Processor recreated at midpoint and resumed from checkpoint |
| Missing/out-of-order candles handled safely | PASS | Gap quarantine/recovery and unknown out-of-order rejection tests |
| Bounded offline sustained trial passes | PASS | 300 genuine candles, 1 duplicate, 112.52 seconds, 0 network requests |
| Backend/frontend checks pass | PASS | Backend 933 passed/23 skipped; frontend 32 passed; typecheck/lint/build passed |
| No fabricated model output | PASS | Model status remained unavailable; no score/rank/confidence/notification created |
| Original checkout/protected resources untouched | PASS | Original dirty state preserved; only isolated worktree and disposable services used |
| Full continuous live operation | NOT VERIFIED | Requires separate live Binance authorization and trial |

## Isolation evidence

- Worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`
- Baseline commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- PostgreSQL: `127.0.0.1:55443`, `alphalens_checkpoint04`, PID 8586
- Redis: `127.0.0.1:56390`, PID 9412
- Checkpoint: `/private/tmp/alphalens-checkpoint04-runtime-checkpoint.json`
- Browser evidence: `/private/tmp/alphalens-checkpoint04-screens-20261026/dashboard.png`

## Explicit non-claims

This matrix does not certify Gate 6 or Gate 7, predictive validity, confidence calibration, profitability, 24/7 live operation, external notification delivery, trading, deployment, or public launch readiness.

## Remaining owner authorization

The next required authorization is a separately reviewed live Binance BTCUSDT/5m operational trial. Model fitting, protected-test evaluation, artifact promotion, external notifications, trading, and deployment remain separately prohibited.

Report content SHA-256 (excluding this footer line): `4a34198c3ad405046c988de58c34bb7aafcad1584ce0e91884b6e3fcc83b9c02`.
