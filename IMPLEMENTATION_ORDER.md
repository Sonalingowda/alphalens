# AlphaLens v2 Implementation Order

This order is optimized for correctness and dependency safety. It assumes the
current repository is the baseline and that AlphaLens v2 will not reuse the
v1 trading-operations contract unchanged.

## Critical path

The critical path is:

1. product contract freeze;
2. intraday data foundation;
3. intraday feature engineering;
4. decision engine;
5. opportunity ranking;
6. scanner API;
7. chart overlay frontend.

The v1 simulation stack can only be removed safely after the v2 flow exists.

## Recommended execution order

| Order | Milestone | Goal | Depends on | Blockers | Risk | Critical path | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Scope freeze and contract alignment | Lock the v2 product boundary, supported timeframes, and decision semantics. | None | Human approval of the new product contract. | Medium | Yes | `README.md:1-49`, `AGENTS.md:43-109`, `RESEARCH_CONSTITUTION.md:1-71`, `ROADMAP.md:7-45` |
| 2 | Intraday data foundation | Add BTC/USD 5m, 10m, and 15m market data ingestion, validation, and persistence. | Milestone 1 | Provider availability, schema design, historical backfill policy. | High | Yes | `backend/app/market_data/*`, `backend/app/persistence/candles.py`, `backend/app/settings.py:45-62`, `backend/app/main.py:66-200` |
| 3 | Intraday feature engineering | Build the intraday feature set and persist versioned feature runs. | Milestone 2 | Feature definitions and lookback policy. | High | Yes | `backend/app/features/*`, `backend/app/persistence/features.py`, `backend/app/research/dataset.py:23-240` |
| 4 | Decision engine | Turn model evidence into BUY / SELL / WAIT outputs with no-trade support. | Milestone 3 | Final decision taxonomy and confidence policy. | High | Yes | `backend/app/api/application.py:308-355`, `backend/app/backtesting/strategy.py`, `backend/app/backtesting/signals.py` |
| 5 | Opportunity ranking engine | Rank setups by quality and select only the highest-quality candidates. | Milestone 4 | Rank metrics and tie-breaking policy. | Medium | Yes | `backend/app/research/model_selection_scoring.py`, `backend/app/research/final_model_selection.py` |
| 6 | Calibration and explainability gate | Make confidence display conditional on statistical calibration. | Milestones 3-5 | Calibration criteria, acceptance thresholds. | High | Yes | `backend/app/research/explainability.py`, `backend/app/research/statistical_validation.py`, `backend/app/persistence/dashboard.py` |
| 7 | AI opportunity scanner API | Expose ranked opportunities and chart-ready decision payloads. | Milestones 4-6 | API contract for scanner items and overlays. | High | Yes | `backend/app/api/application.py:49-355`, `frontend/lib/api.ts`, `frontend/lib/types.ts` |
| 8 | AI chart overlay frontend | Make the chart the primary workspace and render AI annotations. | Milestone 7 | Overlay/annotation schema and chart UX decisions. | High | Yes | `frontend/app/page.tsx`, `frontend/components/dashboard/time-series-chart.tsx`, `frontend/components/dashboard/app-shell.tsx` |
| 9 | Decommission v1 simulation surfaces | Remove or archive backtesting, risk management, paper trading, and v1 report pages from the main product boundary. | Milestones 1-8 | A working v2 path must already exist. | High | No | `backend/app/backtesting/*`, `backend/app/backtesting/risk/*`, `backend/app/paper_trading/*`, `frontend/app/backtest-reports/page.tsx`, `frontend/app/paper-trading/page.tsx`, `frontend/app/risk-events/page.tsx`, `frontend/app/portfolio/page.tsx` |
| 10 | Verification and regression hardening | Rebuild tests, CI expectations, and deployment checks against the v2 contract. | Milestones 1-9 | Final API/UI contracts. | Medium | No | `backend/tests/*`, `frontend/tests/*`, `.github/workflows/*`, `DEPLOYMENT.md` |

## Milestone details

### 1. Scope freeze and contract alignment

This phase should end with an explicit answer to the following questions:

- What does a v2 decision object look like?
- What is the canonical v2 confidence policy?
- What intraday timeframes are in Phase 1?
- What evidence is required before a confidence value can be rendered?

Without this, the rest of the migration is likely to drift back toward the
current regression/trading-operations contract.

### 2. Intraday data foundation

This is the highest-risk dependency because it affects:

- storage schema;
- validation logic;
- feature windows;
- ranking horizons; and
- dashboard chart granularity.

It is the first true product change because the current repository is daily
and BTC/USD only.

### 3. Intraday feature engineering

The feature layer should not be designed until the intraday candle model is
settled. Otherwise the lookback windows, leakage checks, and caching logic
will be wrong.

### 4. Decision engine

The decision engine is the product core. It must sit after the feature layer
and before the scanner/overlay layers.

### 5. Opportunity ranking engine

Ranking should be implemented after the decision semantics are stable. This
keeps ranking aligned to the final BUY / SELL / WAIT contract rather than a
transient modeling objective.

### 6. Calibration and explainability gate

Calibration is a blocker for any visible confidence value. The current
repository already treats confidence as unavailable in the dashboard bundle;
that is the correct default until calibration is proven.

### 7. AI opportunity scanner API

The scanner should expose a sorted opportunity feed and decision metadata.
The API should be the source of truth for the dashboard and any future
consumers.

### 8. AI chart overlay frontend

The overlay should be built only after the scanner API is stable. The chart
workspace must not be wired to guess at decision semantics locally.

### 9. Decommission v1 simulation surfaces

The backtesting, risk-management, and paper-trading subsystems are valuable
historical evidence of the current implementation, but they conflict with the
v2 product boundary and should leave the main product path once the v2 flow
exists.

### 10. Verification and regression hardening

Once the new contract is live, the tests should be rewritten to verify:

- intraday data correctness;
- decision consistency;
- scanner ranking stability;
- overlay rendering; and
- confidence gating.

## Prerequisites and blockers

### Prerequisites

- Final v2 product contract.
- Final intraday timeframe policy.
- Final decision semantics.
- Final confidence/calibration policy.

### Blockers

- Whether the existing simulation/reporting subsystems are archived or
  removed.
- Which model family or ensemble will back the new decision engine.
- Which evaluation metrics govern confidence display.
- Whether the scanner ranks all opportunities or only high-confidence ones.

### Low-risk work that can proceed early

- documentation rewrite;
- UI component refactoring;
- test harness restructuring;
- deployment / Docker file cleanup;
- schema draft work that does not touch live data.

## Evidence summary

The current repository evidence that drives this order is concentrated in:

- `backend/app/main.py:13-260`
- `backend/app/api/application.py:49-355`
- `backend/app/market_data/*`
- `backend/app/features/*`
- `backend/app/targets/forward_log_return.py`
- `backend/app/validation/splits.py`
- `backend/app/research/*`
- `backend/app/backtesting/*`
- `backend/app/paper_trading/*`
- `frontend/app/*`
- `frontend/components/dashboard/*`
- `frontend/lib/*`
- `README.md:15-49, 71-144`
- `frontend/README.md:3-57`

The migration sequence above is therefore a dependency-driven rewrite of the
current repository boundary, not a cosmetic rebrand.
