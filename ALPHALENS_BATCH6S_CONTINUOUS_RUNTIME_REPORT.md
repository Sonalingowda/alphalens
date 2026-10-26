# AlphaLens Batch 6S — Continuous Runtime Report

Date: 2026-10-26  
Scope: Binance BTCUSDT / closed 5-minute candles only  
Offline runtime engineering: **PASS**  
Full continuous/live operation: **NOT VERIFIED**

## Executive result

Checkpoint 04 implemented a reusable continuous closed-candle processor around the existing `LiveMarketIngestionService`, PostgreSQL immutable repositories, and `RuntimeIntelligencePipeline`. It adds atomic hash-bound checkpoints, in-flight recovery, deterministic ordering, database-backed duplicate recognition, gap quarantine, bounded retry, and truthful health state without changing Detection, strategy, model, scoring, ranking, or notification semantics.

A genuine retained historical replay verified the mechanics against the actual production persistence and pipeline path. A timed repeat of the same window ran for **112.52 seconds**, processed 300 genuine candles plus one intentional duplicate delivery, and made zero network requests. The final checkpoint was READY at `2026-10-10T12:10:00Z` with sequence 300 and the expected dataset hash.

This is a bounded historical replay, not a 24/7 live market trial. Gate 6 remains NOT VALIDATED, Gate 7 remains BLOCKED, and public launch remains unauthorized.

## 1. Preservation and identity

Execution worktree:

`/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`

Baseline retained from Checkpoint 03:

- Commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Branch: detached `HEAD`
- Final state: uncommitted isolated changes; no historical ref rewritten.

The original dirty checkout `/Users/sonalingowda/Downloads/alphalens` was not modified. Existing Batch 6N–6Q and Checkpoint 03 files were preserved. No Docker/Colima, cloud, production, protected database, protected dataset, live exchange, model or notification resource was touched.

Checkpoint 04 delta files:

- `backend/app/live_market_data/continuous.py`
- `backend/app/live_market_data/service.py`
- `backend/app/live_market_data/__init__.py`
- `backend/scripts/checkpoint04_historical_replay.py`
- `backend/tests/test_continuous_runtime.py`

No migration was added. Existing Checkpoint 03 changes remained in the worktree but are not attributed to this batch.

## 2. Genuine data provenance

Read-only source:

`/Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json`

Complete-file SHA-256:

`f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`

The file identity was reverified as Binance BTCUSDT, 5-minute candles, 25,920 rows. The bounded window used dataset indexes 25069–25368, 300 rows, from `2026-10-09T11:15:00Z` through `2026-10-10T12:10:00Z`. No market data was fabricated, acquired, altered, copied into the repository, or used for fitting, tuning or acceptance.

## 3. Isolated services

New disposable services were created separately from the prior Checkpoint 03 services:

| Service | Identity | Isolation |
|---|---|---|
| PostgreSQL | 16.12, `127.0.0.1:55443`, database `alphalens_checkpoint04` | Data directory `/private/tmp/alphalens-checkpoint04-pg-20261026`, PID 8586; unique migrator/runtime roles |
| Redis | 8.10.0, `127.0.0.1:56390` | State/config directory `/private/tmp/alphalens-checkpoint04-redis-20261026`, PID 9412; loopback-only and unique password |
| Checkpoint | Filesystem store | `/private/tmp/alphalens-checkpoint04-runtime-checkpoint.json` |

Alembic completed successfully at `20261003_0040`; the disposable database contained 65 public tables. Runtime-role PostgreSQL access and Redis `PONG` were verified. Credentials were stored only in the mode-600 disposable secret file and are not reproduced here.

## 4. Continuous processor implementation

`backend/app/live_market_data/continuous.py` provides:

- Strict BTCUSDT/5m scope and completed-candle validation.
- Atomic temporary-file write, flush, `fsync`, `os.replace`, and directory `fsync`.
- SHA-256 document integrity and source-dataset binding.
- Durable `PROCESSING`, `READY`, `QUARANTINED`, and `ERROR` states.
- In-flight candle identity and sequence preservation across restart.
- Existing PostgreSQL immutable snapshot lookup for repeated/overlapping windows.
- Deterministic five-minute ordering.
- Missing interval quarantine without network backfill or silent continuation.
- Unknown out-of-order candle rejection.
- Bounded retry with explicit exhausted/not-retryable state.
- Runtime health fields for worker, finalized candle, processing time/lag, gap, persistence, retry, model artifact, and last error.

The processor advances its checkpoint only after the existing ingestion persistence and pipeline callback complete. A checkpoint commit interruption leaves an in-flight marker; recovery replays the immutable candle and preserves its sequence. Model artifact state is always reported as `UNAVAILABLE_WITHOUT_APPROVED_ARTIFACT`; this batch creates no prediction.

`LiveMarketIngestionService.persist_completed_candle()` is a narrow public coordination method over the existing `_persist` implementation. Canonical identity and PostgreSQL advisory-lock protections remain in the existing repository.

## 5. Replay driver and results

Driver:

`backend/scripts/checkpoint04_historical_replay.py`

It verifies the complete dataset hash before parsing rows, uses `_completed_candle_from_rest_kline`, the existing ingestion service, PostgreSQL repository and `build_runtime_pipeline`, and hard-points REST fallback to an unreachable loopback address. It performs no Binance request.

Timed repeat command:

```text
env PYTHONPATH=. uv run --offline python scripts/checkpoint04_historical_replay.py \
  /Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json \
  /private/tmp/alphalens-checkpoint04-runtime-checkpoint-repeat.json \
  --start-index 25069 --count 300
```

Measured wall time: `112.52 seconds`. Results:

- Genuine candles: 300.
- Processor outcomes: `PROCESSED=300`, `DUPLICATE=1`.
- Restart: processor recreated at the midpoint and resumed from the durable checkpoint.
- Network requests: 0.
- Final checkpoint status: `READY`.
- Final checkpoint sequence: 300.
- Final candle: `2026-10-10T12:10:00Z`.
- Final checkpoint SHA-256: `22dcc760677f0aa80f8df241fb8e4affab0ae21771336f27192fb61b557ce37b`.
- Repeat-run checkpoint was also READY with the same final candle and source hash.

The first full replay created 300 market snapshots. Its PostgreSQL immutable aggregate counts were:

| Entity | Count |
|---|---:|
| MarketSnapshot | 300 |
| FeatureSnapshot | 299 |
| MarketContext | 299 |
| DetectionAttempt | 299 |
| OpportunityCandidate | 174 |
| EvidencePackage | 174 |
| Opportunity | 174 |
| OpportunityPlan | 174 |
| QualificationRecord | 174 |

Feature/context processing began only when the existing warm-up contract permitted it. Early pipeline results were truthful `UNAVAILABLE` warm-up outcomes; later results were genuine `NO_CANDIDATE` or `UNAVAILABLE`. No model score, rank, confidence, lifecycle, notification, or outcome was generated.

## 6. Failure and recovery evidence

Focused tests in `backend/tests/test_continuous_runtime.py` verified:

- Sequential processing and exact duplicate idempotency.
- Durable checkpoint reload after worker recreation.
- Gap quarantine with no future-candle persistence before continuity is restored.
- Missing-candle recovery and quarantine clearance.
- Bounded retry after a transient pipeline failure.
- Same-process concurrent delivery serializes and persists once.
- Interrupted checkpoint commit leaves a recoverable in-flight state and preserves sequence on replay.
- Corrupt checkpoint bytes fail closed.

Unknown out-of-order input raises `RuntimeOutOfOrderError` unless the immutable snapshot already exists as a recognized duplicate. No silent gap repair or external fallback was invoked during replay.

## 7. API and frontend evidence

The actual backend ran at `127.0.0.1:18001` against the new disposable services. Verified API responses:

- `GET /api/v1/pipeline/health` returned the runtime pipeline state with zero live tasks and no fabricated success.
- `GET /health` returned HTTP 503 `ARTIFACT_UNAVAILABLE`, correctly separating operational API state from missing predictive artifact state.
- `GET /api/v1/opportunities?instrument=BTCUSDT&timeframe=5m&as_of=2026-10-10T12:15:00.999Z` returned 50 paginated genuine assessment-only records, `historical_replay` freshness, `rank=null`, `model_score_status=unavailable_without_approved_artifact`, and `notification_status=intent_persistence_only`.

The actual Next.js frontend ran under Node 22 at `127.0.0.1:13001` in explicit local-demo mode. Dashboard screenshot:

[dashboard.png](/private/tmp/alphalens-checkpoint04-screens-20261026/dashboard.png)

SHA-256: `5576837b7a292930da8760bca19105d0ad4e41737b02b5bebb4431dbc5a7091d`

The dashboard displayed genuine BTCUSDT assessment-only records, geometric plans, lifecycle/status states, and unavailable model indicators. It did not display fabricated scores, confidence, ranking, or notification delivery.

## 8. Test results

| Check | Result |
|---|---|
| Focused continuous runtime tests | PASS: 8 passed |
| Full backend suite | PASS: 933 passed, 23 skipped, 497 subtests |
| Backend application/tests Ruff | PASS |
| New replay script Ruff | PASS |
| Frontend Vitest | PASS: 32 tests |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Frontend production build | PASS |
| `git diff --check` | PASS |
| Existing repository `scripts/` Ruff scope | NOT CLEAN: 82 pre-existing findings outside this batch; no broad cosmetic cleanup applied |

The backend suite retained two known warnings: Starlette/httpx deprecation and an asyncpg cancellation resource warning in an existing failure-path test. No test failure was hidden.

## 9. Acceptance decisions

### A. Offline runtime engineering — PASS

All offline engineering criteria passed: genuine source identity, closed-candle enforcement, durable checkpoints, idempotency, concurrency, restart recovery, gap/out-of-order quarantine, timed bounded replay, persistence/API/frontend evidence, truthful model-unavailable state, and preservation of the original checkout/protected resources.

### B. Full continuous operation — NOT VERIFIED

No live Binance WebSocket or REST request was made. Therefore this batch does not establish 24/7 live ingestion, exchange connectivity stability, live restart recovery, live latency/freshness, or production operational stability.

## 10. Remaining P0 blockers

- Separately authorized live Binance BTCUSDT/5m trial is required for full continuous-operation verification.
- Approved BTCUSDT/5m predictive artifact remains absent; scoring, ranking, model confidence, lifecycle publication and notifications remain blocked.
- Production authenticated browser/API verification remains outstanding.
- Existing full `scripts/` Ruff scope requires a separate cleanup decision if repository-wide script lint is a release gate.

## 11. Recommended next smallest batch

Run an isolated operational-observability batch that exposes the durable runtime checkpoint and `RuntimeHealthSnapshot` through a read-only authenticated runtime-status endpoint and frontend health panel, using the same local-only services. Do not enable live acquisition or model scoring in that batch.

Final status: offline runtime engineering **PASS**; full continuous/live operation **NOT VERIFIED**; Gate 6 **NOT VALIDATED**; Gate 7 **BLOCKED**; public launch **NOT AUTHORIZED**.

Report content SHA-256 (excluding this footer line): `7cec4fafa5c37759b0c804445f6fb074d66816c9f3e227eb6683e48839617b7d`.
