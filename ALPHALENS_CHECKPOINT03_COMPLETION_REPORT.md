# AlphaLens Checkpoint 03 Completion Report

Date: 2026-10-26  
Scope: genuine retained Binance BTCUSDT / closed 5-minute historical integration  
Final decision: **PARTIAL — genuine assessment journey verified; production authentication and model-dependent lifecycle remain blocked**

## Executive result

The authorized isolated execution proved the following real path:

`retained Binance BTCUSDT/5m candles → production candle parsing and ingestion → indicator/feature snapshot → market context → Detection → Assessment → Qualification → informational Plan → PostgreSQL persistence → actual API → Next.js browser dashboard and assessment detail`.

The replay emitted one genuine BUY Detection candidate. Its persisted assessment and geometric plan were rendered in the browser. No model score, confidence, rank, expected move, notification, or simulated outcome was created. The API and UI explicitly report those unavailable states.

Checkpoint 03 is **not a full PASS** because the isolated browser run used an explicit local-demo Clerk middleware bypass (no private Clerk credentials were available), and the normal trade-history endpoint correctly remains unavailable while the verified production artifact is absent. No protected or production authentication claim is made.

Gate 6 remains NOT VALIDATED. Gate 7 remains BLOCKED. No public launch or deployment was performed.

## 1. Preservation and source identity

Original checkout `/Users/sonalingowda/Downloads/alphalens` was not modified. Its dirty state, historical evidence, protected resources and prior worktrees were preserved.

Execution worktree:

`/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`

Baseline:

- Commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Branch: detached `HEAD`
- Final state: uncommitted isolated changes; no historical ref was rewritten.

The worktree already contained authorized Batch 6N–6Q changes and reports. This checkpoint added only the isolated integration changes and this report. `git diff --name-only` at completion listed:

- `backend/app/opportunity_intelligence/api.py`
- `backend/app/prediction_api.py`
- `backend/tests/test_opportunity_api.py`
- `frontend/app/page.tsx`
- `frontend/components/opportunities/opportunity-card.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/proxy.ts`
- `frontend/tests/api.integration.test.ts`

The isolated worktree also retained previously untracked Batch 6N–6Q reports, contract code/tests, and the assessment detail route. No original checkout file was reset, cleaned, overwritten or deleted.

## 2. Genuine dataset provenance

Dataset inspected read-only at:

`/Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json`

Complete-file SHA-256:

`f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`

The retained file contains the previously verified 25,920 Binance BTCUSDT 5-minute candles. The bounded replay selected the previously authorized October 10, 2026 window, dataset positions 25069–25368, exactly 300 genuine closed candles. No candles were fabricated, copied into the source checkout, altered, acquired from the network, or used for fitting, tuning or predictive acceptance.

The replay’s canonical bounded-window hash was recorded as:

`396f715032ef2e1a5d6f0325803eb0b4e7095b64c97c17fdf38ae9643f4531d4`

## 3. Disposable infrastructure

Existing Batch 6E services on ports 55432 and 56379 were not touched. New checkpoint-only services were created with native binaries and loopback bindings:

| Resource | Identity | Isolation evidence |
|---|---|---|
| PostgreSQL | PostgreSQL 16.12, `127.0.0.1:55442`, database `alphalens_checkpoint03` | New data directory `/private/tmp/alphalens-checkpoint03-pg-20261026`; PID 4322; separate migrator/runtime roles; no protected data directory reused |
| Redis | Redis 8.10.0, `127.0.0.1:56389` | New data directory `/private/tmp/alphalens-checkpoint03-redis-20261026`; PID 4340; loopback-only and separate password |
| Credentials | Disposable local credentials | Stored mode-600 at `/private/tmp/alphalens-checkpoint03-secrets-20261026`; no password is reproduced here |

Alembic migrations completed successfully against the new empty PostgreSQL database only. Verified result: one head `20261003_0040`, 65 public tables. Runtime-role connectivity and Redis connectivity were verified. No protected database, volume or existing service was modified.

## 4. Replay execution and lineage

The replay used locked Python 3.11 with offline `uv run --offline`, the existing production parser and ingestion implementation, `LiveMarketIngestionService._persist`, `MarketSnapshotPostgreSQLRepository`, and `_runtime_pipeline.run_for_snapshot`. The REST base was pointed at an unreachable loopback test port with an empty fallback so that no Binance network request could occur.

All 300 selected genuine candles were persisted. The final snapshot was:

`binance.spot.BTCUSDT.5m.1791634200000.snapshot`

Observed stage results:

| Stage | Result |
|---|---|
| Market snapshot | COMPLETED |
| Feature snapshot / indicators | COMPLETED |
| Market context | COMPLETED |
| Opportunity Detection | COMPLETED; one genuine candidate |
| Evidence package | COMPLETED |
| Assessment | COMPLETED |
| Qualification | COMPLETED |
| Informational planning | COMPLETED |
| Model scoring | BLOCKED: `scoring.input_unavailable` |
| Ranking/lifecycle/notification | Not executed; no approved model artifact and no live delivery authorization |

Candidate identity:

`candidate.runtime_detection_ema_rsi.BTCUSDT.5m.1791634200000`

Persisted opportunity identity:

`opportunity.runtime_ema_rsi.candidate.runtime_detection_ema_rsi.BTCUSDT.5m.1791634200000`

The genuine persisted plan contained:

- Direction: BUY, supplied by Detection; not supplied by a model.
- Reference/entry price: `82873.44000000`.
- Invalidation: `82850.750000000000000000`.
- Target 1: `82907.475000000000000000`.
- Geometric risk/reward: `1.500000000000000000`.
- Valid-until: `2026-10-10T12:25:00.999Z`.

These are informational geometric plan values. They do not establish executable fills, expectancy, profitability, confidence or a win probability.

Post-replay disposable PostgreSQL counts were:

| Entity | Count |
|---|---:|
| MarketSnapshot | 300 |
| FeatureSnapshot | 1 |
| MarketContext | 1 |
| DetectionAttempt | 1 |
| OpportunityCandidate | 1 |
| EvidencePackage | 1 |
| Opportunity | 1 |
| OpportunityPlan | 1 |
| QualificationRecord | 1 |
| Score / Ranking / Lifecycle / Notification | 0 |

## 5. Backend API evidence

The actual Uvicorn backend was run at `127.0.0.1:18000` against only the new disposable services. The authenticated production artifact health contract remained truthful:

`GET /health` → HTTP 503, `ARTIFACT_UNAVAILABLE`.

The assessment-only API projection was added because the existing dashboard projection requires ranking/model readiness. It does not bypass scoring; it exposes persisted Detection/Assessment/Plan data with explicit unavailable states.

`GET /api/v1/opportunities?instrument=BTCUSDT&timeframe=5m&as_of=2026-10-10T12:15:00.999Z` returned HTTP 200 with:

- `coverage_status`: `assessment_only_model_unavailable`
- `freshness_status`: `historical_replay`
- one BTCUSDT/5m BUY item
- `lifecycle_state`: `ASSESSMENT_ONLY`
- `rank`: `null`
- `model_score_status`: `unavailable_without_approved_artifact`
- `notification_status`: `intent_persistence_only`
- the persisted entry, invalidation, target and geometric risk/reward values above.

The assessment detail endpoint returned the same persisted opportunity, evidence references, context reference, plan and source cutoff. Response headers included API version `1.0.0`, request/correlation IDs and an audit ID.

## 6. Browser evidence

The actual Next.js development server ran under the isolated Node 22.23.3 environment at `127.0.0.1:13000` with:

`ALPHALENS_LOCAL_DEMO_MODE=true`

This mode is explicit and only bypasses Clerk server middleware for the local historical replay because no private Clerk secret was authorized or available. Production/non-demo mode still uses `clerkMiddleware()` and fails closed when credentials are absent.

Screenshots captured by headless Chrome:

- Dashboard: [dashboard-final.png](/private/tmp/alphalens-checkpoint03-screens-20261026/dashboard-final.png), SHA-256 `25b51b9ad11637a31fd85ed732e94cf1f2b58f4336c6b749c69a46fc3d6f8ef`.
- Assessment detail: [detail-final.png](/private/tmp/alphalens-checkpoint03-screens-20261026/detail-final.png), SHA-256 `c6a880cf7a648b3b07ff35af802a1ca6466be019ff9650035ed9fc219ef6626e`.
- Trade history truth-state: [history-final.png](/private/tmp/alphalens-checkpoint03-screens-20261026/history-final.png), SHA-256 `3613e68b0bb6a0f236a29a2db09c9f0f80eaa7ebad023403fff86b8c406e3eb3`.

Observed UI:

- Dashboard displayed the same BTCUSDT BUY assessment and plan.
- Card showed entry, current/reference price, invalidation, target and 1.5 risk/reward.
- Detail displayed the same candidate/opportunity provenance and timestamp.
- Detail explicitly stated “Assessment only”, “Unavailable” model output, and “Not created before ranking” lifecycle.
- Dashboard and detail displayed no confidence, ranking, expected move or notification delivery.
- Trade history displayed a truthful API-unavailable state because the normal production health contract is blocked by the absent approved artifact. No placeholder or fabricated history was shown.

## 7. Source changes

The focused changes were:

1. Added assessment-only list/detail projections backed by `OpportunityRepository`, preserving the ranked dashboard contract and exposing explicit model/notification unavailable statuses.
2. Wired the repository into the existing application factory.
3. Added backend regression coverage for the assessment-only, unranked projection.
4. Added frontend types/API support for assessment detail and embedded plans.
5. Updated opportunity cards/dashboard enrichment to link and render assessment-only records without requesting model detail.
6. Added the assessment detail route showing genuine plan/provenance and unavailable-state disclosures.
7. Added an explicit `ALPHALENS_LOCAL_DEMO_MODE` switch to `frontend/proxy.ts`; only this mode bypasses Clerk middleware for the offline local replay. Non-demo behavior remains Clerk-protected.

No model contract, strategy, Detection threshold, schema, migration, artifact, database migration history, notification delivery or production configuration was changed.

## 8. Verification matrix

| Check | Result |
|---|---|
| Dataset complete-file SHA | PASS; exact expected SHA |
| Disposable PostgreSQL/Redis identity and isolation | PASS |
| Alembic migration to disposable DB | PASS; head `20261003_0040`; 65 tables |
| Genuine 300-candle replay | PASS |
| Production indicators/context/Detection | PASS; one genuine candidate |
| Persistence and lineage | PASS |
| Actual API retrieval | PASS |
| Browser dashboard | PASS in explicit local-demo mode |
| Browser assessment detail | PASS in explicit local-demo mode |
| Browser trade history | Truthful unavailable state; no lifecycle history exists |
| Model prediction/confidence/ranking | Correctly not executed |
| Backend regression | PASS: 925 passed, 23 skipped, 497 subtests; 2 known warnings |
| Backend Ruff | PASS |
| Frontend Vitest | PASS: 32 tests |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Frontend production build | PASS |
| Original checkout/protected resources | PASS; untouched |

Known test warnings were a Starlette/httpx deprecation and an asyncpg cancellation resource warning in an existing failure-path test. They did not fail the suite and were not hidden.

## 9. Remaining blockers

P0 for a production/public PASS:

- Real Clerk credentials and an authenticated browser/API journey must be exercised in an approved isolated environment; this report does not claim authentication verification.
- An approved BTCUSDT/5m inference artifact is absent. Therefore scoring, ranking, confidence, model health, lifecycle creation and external notification eligibility remain unavailable.
- Production-grade continuous ingestion, restart recovery, deduplication and freshness monitoring remain unverified.

P1:

- Trade/opportunity history is not a substitute for the assessment-only record; no ranked lifecycle exists to display because scoring was correctly blocked.
- Notification delivery remains intent-only and was not sent.
- The replay is diagnostic historical evidence, not predictive validation or economic validation.

## 10. Required next step

The smallest safe next batch is authenticated isolated product verification after obtaining authorized Clerk development credentials, without changing the model boundary. Separately, the approved research protocol must produce and independently review a compatible BTCUSDT/5m artifact before any scoring, ranking, lifecycle, notification or public-launch claim is made.

## Final status

- Checkpoint 03: **PARTIAL**.
- Genuine historical integration: **VERIFIED through Detection, assessment, plan, persistence, API and browser dashboard/detail**.
- Production authentication: **NOT VERIFIED; external credential boundary**.
- Predictive scoring/ranking/lifecycle/notifications: **BLOCKED by absent approved artifact and intentionally not bypassed**.
- Gate 6: **NOT VALIDATED**.
- Gate 7: **BLOCKED**.
- Public launch: **NOT AUTHORIZED**.

Report content SHA-256 (excluding this footer line): `f01489a3165f5b3dc91b7e18117e5b51a5e58cccb95c08c247907398a33d4a10`.
