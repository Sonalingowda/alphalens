# AlphaLens Batch 6Q — End-to-End Product Integration Report

Date: 2026-10-26  
Scope: Binance BTCUSDT, closed 5-minute candles only  
Worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`  
Baseline commit: `948913a7e2df47b785bef655deaa4843c7589bcf`  
Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`

## Result

Status: **PARTIALLY COMPLETE — truthful product-boundary integration fixed; full
new end-to-end replay blocked**.

The smallest safe integration repair was implemented: the opportunity health
contract and dashboard now explicitly state the BTCUSDT/5m closed-candle scope,
that model scoring is unavailable without an approved artifact, and that
notifications are currently persisted intents only. This prevents the public
surface from implying model approval or external alert delivery.

The previously authorized genuine retained-data execution remains valid and
was not repeated. Batch 6G–6I evidence already verified the production path
through genuine ingestion, features, context, Detection, persistence and a
reproducible October candidate. A new API/browser replay could not be safely
performed in this worktree because the disposable PostgreSQL listener requires
credentials unavailable to this shell. No fabricated data or substitute fixture
was used.

## Verified provenance

The retained dataset remains available at:

`/Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json`

Observed SHA-256:

`f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`

This matches the Batch 6G–6I recorded dataset identity. The prior genuine
replay evidence records 25,920 Binance BTCUSDT/5m candles and a bounded
production run through:

`CompletedCandle → MarketSnapshot persistence → RuntimeFeatureEngine →
MarketContext → RuntimeOpportunityDetectionService`.

Prior evidence also records a genuine October Detection candidate with matching
lineage hashes. It is Detection output, not proof of an approved model score,
calibrated confidence, profitability, or Gate 6 validation.

Authoritative prior records:

- [Batch 6G replay report](/private/tmp/alphalens-batch6d-isolated-infrastructure-20261026/ALPHALENS_BATCH6G_GENUINE_BTCUSDT_REPLAY_REPORT.md)
- [Batch 6H coverage report](/private/tmp/alphalens-batch6d-isolated-infrastructure-20261026/ALPHALENS_BATCH6H_REAL_DETECTION_COVERAGE_REPORT.md)
- [Batch 6I candidate report](/private/tmp/alphalens-batch6d-isolated-infrastructure-20261026/ALPHALENS_BATCH6I_CANDIDATE_INTEGRITY_AND_MODEL_READINESS_REPORT.md)

## Implemented changes

| File | Change |
|---|---|
| `backend/app/opportunity_intelligence/api.py` | Added explicit market scope, model-score status, and notification status to the read-surface health payload. |
| `backend/tests/test_opportunity_api.py` | Added regression assertions for all new health fields. |
| `frontend/lib/types.ts` | Added typed BTCUSDT/5m capability-boundary fields to `MvpHealth`. |
| `frontend/app/page.tsx` | Added a visible product-boundary notice explaining closed-candle scope, unavailable model scoring, and intent-only notifications. |
| `frontend/tests/api.integration.test.ts` | Added a client-contract test proving the capability boundary is preserved. |

These changes do not create model output, alter Detection, enable scoring,
rank opportunities, send notifications, or modify research thresholds.

## Verified API/product behavior

The backend opportunity API test verifies a deterministic health envelope with:

```json
{
  "market_scope": {
    "exchange": "binance",
    "instrument": "BTCUSDT",
    "timeframe": "5m",
    "candle_state": "closed"
  },
  "model_score_status": "unavailable_without_approved_artifact",
  "notification_status": "intent_persistence_only"
}
```

The frontend dashboard consumes these fields and renders a visible boundary
notice. Existing opportunity cards and detail views continue to render entry,
stop, target, risk/reward, lifecycle, freshness and provenance only when the
backend has persisted those fields; absent model values remain `Unavailable`.

No live browser screenshot or running API response is claimed in this batch.
The isolated database service was listening on `127.0.0.1:55432`, but direct
authentication was unavailable without the disposable runtime credential.
The protected/default database and Redis endpoints were not accessed.

## Tests and checks

| Command/check | Result |
|---|---|
| `PYTHONPATH=. uv run --offline pytest -q tests/test_opportunity_api.py` | **20 passed**, 1 dependency warning |
| `uv run --offline ruff check backend/app/opportunity_intelligence/api.py backend/tests/test_opportunity_api.py` | **Passed** |
| `git diff --check` | **Passed** |
| Dataset SHA-256 verification | **Passed**, matches `f17dfd…` |
| Frontend Vitest | **Not run**: `node_modules` absent; `vitest` unavailable |
| Frontend typecheck | **Not run**: `node_modules` absent; `tsc` unavailable |
| Browser/API live integration | **Not run**: disposable DB credential unavailable; no substitute data used |

The first attempted backend command without `PYTHONPATH` failed at collection
with `ModuleNotFoundError: app`; the corrected isolated command passed all 20
tests. No application failure was inferred from the environment invocation
mistake.

## Remaining P0 blockers

1. No approved BTCUSDT/5m runtime inference artifact exists. The new contract
   remains contract-only; scoring and ranking must remain unavailable.
2. Continuous Binance ingestion, durable public runtime persistence, restart
   recovery and freshness monitoring are not newly verified.
3. Gate 7 image/source provenance, migration/recovery, Redis and deployment
   evidence remain incomplete.
4. Frontend Vitest/typecheck need an isolated Node 22 dependency environment;
   installing it was not authorized under the current disk headroom.
5. A genuine API/browser verification requires the disposable runtime
   credentials to be supplied through the approved isolated configuration.

## Recommended next implementation batch

Batch 6Q-2 should be a narrowly bounded isolated integration run after the
owner provides the disposable PostgreSQL/Redis credentials and confirms disk
headroom for the existing Node 22 dependency tree:

1. Reverify service identity and credentials without touching protected
   endpoints.
2. Reuse the retained dataset and an already authorized bounded replay window.
3. Query the persisted Detection/candidate and opportunity read APIs.
4. Run the Next.js frontend under Node 22 and capture the truthful unavailable
   model/artifact states.
5. Verify pagination, filters, detail loading, stale/empty/error recovery and
   history using persisted records only.
6. Stop before scoring, ranking, external notification delivery, model fitting,
   deployment, or Gate 6/7 certification.

## Preservation and authorization

Original dirty checkout, historical evidence, retained dataset, protected
services, Docker resources and cloud resources were preserved. No source
dataset or database was modified by the replay attempt or this repair. No
Binance network request, model fitting, artifact promotion, live alert,
trading, deployment, or gate certification occurred.

Final status:

- Contract-neutral product truthfulness repair: **COMPLETE**.
- Genuine historical ingestion → Detection evidence: **VERIFIED from prior
  authorized reports; not newly replayed**.
- New persistence → API → frontend execution: **BLOCKED by isolated runtime
  credential/dependency availability**.
- Approved BTCUSDT/5m model artifact: **ABSENT**.
- Gate 6: **NOT VALIDATED**.
- Gate 7: **BLOCKED**.

