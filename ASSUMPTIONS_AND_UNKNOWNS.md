# AlphaLens v2 Assumptions and Unknowns

This document distinguishes verified repository facts from items that are not
currently verifiable from the repository alone.

## Verified facts

The repository currently contains:

- a daily BTC/USD market-data pipeline;
- a feature pipeline with 12 technical features;
- a five-observation forward-log-return target;
- walk-forward validation with purge and holdout controls;
- multiple immutable research reports;
- a Ridge-based packaged inference artifact;
- a read-only production prediction API;
- backtesting, risk, and paper-trading subsystems;
- a dashboard that renders those reports; and
- Docker / GitHub Actions deployment scaffolding.

Evidence:

- `README.md:15-49, 71-144`
- `frontend/README.md:3-57`
- `backend/app/main.py:61-260`
- `backend/app/api/application.py:49-355`
- `backend/app/research/dataset.py:23-240`
- `backend/app/persistence/models.py:32-3241`

## Assumptions used in this blueprint

These are explicitly treated as assumptions, not verified product decisions:

1. AlphaLens v2 should preserve the current provenance / hashing discipline.
2. AlphaLens v2 should keep PostgreSQL and the current async persistence style.
3. AlphaLens v2 should keep the Next.js frontend stack and charting approach.
4. The v2 product boundary should exclude trading execution, broker
   connectivity, portfolio management, and paper trading.
5. The v2 decision engine should be surfaced through a read-only API.

Those assumptions are consistent with the product vision supplied in this
task, but they are not directly encoded in the current repository.

## Missing documentation

The repository does not currently contain the following v2-specific design
documents:

- an AlphaLens v2 product contract;
- a v2 target-label specification;
- a v2 calibration policy;
- an intraday data vendor comparison;
- a scanner / overlay API contract;
- a chart-annotation schema; and
- a migration ADR set.

No ADR directory or decision log was found in the repository.

Evidence:

- `rg --files .` did not show an ADR/decision-log directory.
- Existing technical docs are v1-oriented: `README.md`, `frontend/README.md`,
  `BACKTESTING.md`, `PAPER_TRADING.md`, `RISK_MANAGEMENT.md`,
  `MODEL_INFERENCE_ARTIFACT.md`, `DEPLOYMENT.md`, and `API.md`.

## Repository inconsistencies

### 1. Current implementation vs AlphaLens v2 product vision

The repository currently implements trading-adjacent artifacts that are in
direct conflict with the v2 vision:

- backtesting;
- risk management for simulated orders;
- paper trading;
- portfolio / trade-history / risk-event dashboard pages; and
- a holdout-evaluation / final-selection workflow centered on regression.

Evidence:

- `BACKTESTING.md:5-78`
- `PAPER_TRADING.md:5-90`
- `RISK_MANAGEMENT.md:5-80`
- `frontend/app/backtest-reports/page.tsx`
- `frontend/app/paper-trading/page.tsx`
- `frontend/app/portfolio/page.tsx`
- `frontend/app/trade-history/page.tsx`
- `frontend/app/risk-events/page.tsx`
- `backend/app/research/baseline_regression.py`
- `backend/app/research/final_model_selection.py`
- `backend/app/research/holdout_evaluation.py`

### 2. Documentation breadth vs workflow evidence

`README.md` claims the repository includes `actionlint` and `shellcheck`
testing support in the tech-stack section, but the currently inspected GitHub
Actions workflows only show backend, frontend, and container jobs.

Evidence:

- `README.md:146-158`
- `.github/workflows/backend.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/containers.yml`

### 3. Dashboard intent vs product vision

The current dashboard is a read-only reporting interface. AlphaLens v2
requires the chart to become the primary workspace and the opportunity scanner
to become first-class.

Evidence:

- `frontend/app/page.tsx`
- `frontend/components/dashboard/app-shell.tsx`
- `frontend/components/dashboard/time-series-chart.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`

## Human decisions required before implementation

1. Should the v1 backtesting / paper-trading / risk-management subsystems be
   archived only, or removed from the v2 mainline?
2. What is the canonical v2 decision contract for BUY / SELL / WAIT?
3. What is the confidence-calibration policy required before confidence can be
   rendered?
4. What is the canonical intraday timeframe set for Phase 1 beyond BTC/USD?
5. Should the v2 scanner rank every candidate or only candidates above a
   confidence threshold?
6. What chart-annotation ontology is required at launch?
7. Should the current v1 research artifacts be retained as read-only audit
   history or rewritten into the v2 research layer?
8. Should the current prediction API be versioned in place or replaced with a
   v2 scanner/overlay API namespace?

## Questions that must be answered before implementation

- What is the source of truth for the v2 target label definition?
- Which metrics gate confidence display?
- Which intraday candle intervals are required in Phase 1?
- Which data provider(s) are approved for intraday BTC/USD?
- How should the overlay represent entry, stop, take-profit, and reasoning?
- How should WAIT be encoded so that it is a first-class outcome rather than a
  fallback or null state?
- What should happen to the current daily regression / final-holdout workflow?

## Unknowns that could not be verified from the repository

- No ADRs or decision logs were found.
- No v2 architecture document was found.
- No v2 calibration spec was found.
- No scanner/overlay API contract was found.
- No explicit model-card / calibration artifact exists for the v2 vision.
- No license file is present in the repository.

## Practical reading of the current repository

The repository is internally coherent, but it is coherent around the wrong
product. It is a v1 research + simulation + reporting system. AlphaLens v2 is
a chart-first opportunity-ranking system. That gap is large enough that the
migration should be treated as a product replatforming, not a simple feature
extension.
