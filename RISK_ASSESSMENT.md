# AlphaLens v2 Risk Assessment

This register covers the major migrations required for AlphaLens v2.

## Risk register

| Migration | Risk level | Potential breakages | Migration strategy | Rollback strategy | Evidence |
| --- | --- | --- | --- | --- | --- |
| Replace the daily forward-return target with a v2 decision target | High | Model training contracts, evaluation metrics, report schemas, persistence tables, and API payloads that assume `forward_log_return`. | Freeze the current label contract; design the new target schema; add new versioned tables alongside old ones; migrate consumers only after the new contract is verified. | Keep the existing target tables and evaluation paths intact until the new target is proven; re-point consumers back to the old target if needed. | `backend/app/targets/forward_log_return.py:1-116`<br>`backend/app/persistence/targets.py`<br>`backend/app/research/baseline_regression.py`<br>`backend/app/persistence/models.py:468-710` |
| Expand from daily BTC/USD candles to intraday 5m/10m/15m | High | Candle schema, backfill logic, validation rules, feature windows, validation splits, and any code that assumes `1d`. | Add intraday support in a parallel path, validate exact timestamp alignment, and migrate one timeframe at a time under feature flags. | Preserve the daily pipeline so the system can still operate while intraday ingestion is rolled back or retried. | `backend/app/market_data/models.py`<br>`backend/app/market_data/history.py`<br>`backend/app/market_data/validation.py`<br>`backend/app/validation/splits.py`<br>`backend/app/research/dataset.py:23-91`<br>`README.md:28-32, 75-94` |
| Rebuild feature engineering for intraday decisioning | High | Feature-window off-by-one errors, leakage, different candle densities, and incompatible feature schemas. | Introduce versioned feature pipelines and verify prefix invariance against intraday timestamps before switching consumers. | Keep the old feature pipeline and storage tables available until the new feature vectors reproduce correctly. | `backend/app/features/*`<br>`backend/app/persistence/features.py`<br>`backend/app/research/dataset.py:125-240` |
| Introduce a decision engine with BUY / SELL / WAIT | High | API response contracts, dashboard expectations, ranking logic, confidence semantics, and consumer assumptions about predictions. | Define the decision contract first, then add the engine, then wire the scanner and overlay. | Keep the current prediction API and dashboard in place until the new decision path is proven. | `backend/app/api/application.py:308-355`<br>`frontend/components/dashboard/signal-badge.tsx`<br>`frontend/lib/types.ts` |
| Add opportunity ranking and scanner layers | Medium | Scanner freshness, pagination, sorting, tie-breaking, and ranking reproducibility. | Build the scanner as a pure read-model layer over decision evidence, with deterministic ranking rules and stable hashes. | Fall back to the unranked decision feed if the ranking layer fails. | `backend/app/research/model_selection_scoring.py`<br>`backend/app/research/final_model_selection.py`<br>`frontend/app/predictions/page.tsx` |
| Add calibration and confidence gating | High | Misleading confidence values, invalid overlays, and reputation risk if confidence appears before calibration is statistically validated. | Make confidence an opt-in output gated by calibration evidence and separate report artifacts. | Hide confidence entirely if calibration is not available or if hashes do not verify. | `backend/app/persistence/dashboard.py`<br>`backend/app/research/explainability.py`<br>`backend/app/research/statistical_validation.py` |
| Rework the frontend into a chart-first scanner/overlay workspace | High | Route changes, layout changes, API bundle changes, chart integration bugs, and broken assumptions in existing pages. | Replace page-by-page trading-report views incrementally with scanner/overlay views; keep chart primitives and the shell. | Maintain the existing dashboard routes until the new scanner UI is functional. | `frontend/app/page.tsx`<br>`frontend/app/backtest-reports/page.tsx`<br>`frontend/app/paper-trading/page.tsx`<br>`frontend/app/portfolio/page.tsx`<br>`frontend/app/risk-events/page.tsx`<br>`frontend/components/dashboard/app-shell.tsx` |
| Remove backtesting, risk management, and paper trading from the v2 product boundary | High | Documentation drift, deleted evidence pathways, and accidental reuse of trading-specific code in v2 features. | Archive or delete those surfaces after the v2 scanner path is operational; keep immutable historical evidence if needed for audit. | Restore the archived v1 branch or keep the code as a separate research-only line if the migration is rolled back. | `backend/app/backtesting/*`<br>`backend/app/backtesting/risk/*`<br>`backend/app/paper_trading/*`<br>`BACKTESTING.md:5-78`<br>`PAPER_TRADING.md:5-90`<br>`RISK_MANAGEMENT.md:5-80` |
| Rewrite the production API contracts for scanner and overlay consumers | Medium | API clients, response schemas, audit payloads, caching assumptions, and frontend fetch logic. | Version the new API separately, keep read-only semantics, and phase in new endpoints alongside old ones. | Keep the `/api/v1` prediction API operating until the new v2 contract is validated and deployed. | `backend/app/api/application.py:49-355`<br>`backend/app/api/schemas.py`<br>`frontend/lib/api.ts`<br>`frontend/lib/types.ts` |
| Reshape persistence tables for the new product contract | High | Schema migrations, report tables, provenance links, and orphaned v1 tables. | Use additive migrations and explicit deprecation markers; avoid destructive changes until the new tables are live. | Keep the old tables and read paths intact until the new schema is verified in production-like environments. | `backend/app/persistence/models.py:32-3241`<br>`backend/alembic/versions/20260729_0001_create_market_data_tables.py` through `20260730_0023_create_prediction_api_audits.py` |

## Migration-specific observations

### Highest risk

The highest-risk change is the intraday data model because it affects every
other layer:

- target construction;
- validation / embargo logic;
- feature lookbacks;
- ranking horizons;
- API freshness; and
- chart overlay timestamps.

### Medium risk

The scanner and overlay layers are conceptually new, but they can be added
without deleting the existing v1 code immediately if the migration is staged
carefully.

### Lower risk

Deployment, CI, and documentation rewrites are comparatively low risk because
they are contract changes rather than data-model changes.

## Rollback principles

Rollback should be staged at the contract boundary:

1. keep the old daily/v1 paths in place until v2 passes verification;
2. gate new consumers behind explicit feature switches;
3. prefer additive migrations; and
4. preserve immutable evidence rather than rewriting it.

## Evidence summary

The risk assessment is grounded in:

- `README.md:15-49, 71-144`
- `frontend/README.md:3-57`
- `BACKTESTING.md:5-78`
- `PAPER_TRADING.md:5-90`
- `RISK_MANAGEMENT.md:5-80`
- `backend/app/main.py:61-260`
- `backend/app/api/application.py:49-355`
- `backend/app/market_data/*`
- `backend/app/features/*`
- `backend/app/targets/forward_log_return.py`
- `backend/app/validation/splits.py`
- `backend/app/research/*`
- `backend/app/backtesting/*`
- `backend/app/paper_trading/*`
- `backend/app/persistence/models.py:32-3241`
- `frontend/app/*`
- `frontend/lib/*`

The dominant risk theme is simple: AlphaLens v2 is a different product
contract, not a small version bump.
