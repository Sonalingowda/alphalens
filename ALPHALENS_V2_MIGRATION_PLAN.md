# AlphaLens v2 Migration Blueprint

## Executive Summary

AlphaLens today is not a market-opportunity scanner. The repository currently
implements a BTC/USD daily research-and-simulation stack: deterministic market
data ingestion, feature engineering, forward-return target generation,
chronological validation, baseline regression experiments, immutable research
reports, a Ridge inference artifact, a read-only prediction API, a
backtesting engine, a risk framework, paper trading, and a dashboard that
renders those artifacts.

The AlphaLens v2 product vision changes the center of gravity completely. The
target product is an intraday opportunity-identification system, not a trading
platform:

- the user should see BUY / SELL / WAIT decisions;
- the chart is the primary workspace;
- the system should rank opportunities rather than maximize signal count;
- confidence should appear only when statistically validated; and
- AlphaLens must never execute trades.

That means the current v1 research/trading-ops architecture cannot be carried
forward unchanged. The parts that should survive are the platform
foundations:

- deterministic market-data ingestion and persistence patterns;
- explicit provenance and SHA-256 evidence chaining;
- reproducible feature and validation workflows;
- a versioned API surface;
- the dashboard shell and charting primitives; and
- Docker/CI/observability conventions.

The parts that conflict with v2 and should be removed or replaced from the
product boundary are the trading simulation stack, the daily-only regression
targeting model, and the paper-trading/risk/backtesting narrative that
anchors the current implementation.

### Bottom line

AlphaLens v2 should be migrated as a product realignment, not as a small
feature extension. The most important changes are:

1. move from daily regression evidence to intraday opportunity labeling;
2. add a decision engine that emits BUY / SELL / WAIT;
3. add a ranking/scanner layer that prioritizes the best setups;
4. add a chart overlay and annotation API as the primary UX;
5. keep the evidence/provenance stack, but stop treating trading simulation as
   core product behavior.

## Repository Assessment

### What is currently implemented

The repository is a mature, multi-layer system with three distinct surfaces:

1. `backend/app/main.py` — research/data-engineering orchestration for
   ingestion, features, targets, validation, baselines, and persisted
   reports.
2. `backend/app/prediction_api.py` and `backend/app/api/application.py` —
   the read-only production inference app.
3. `frontend/` — a read-only Next.js dashboard that renders persisted
   evidence.

The root documentation says the same thing in plain language. The current
`README.md:1-49` describes AlphaLens as a deterministic research, inference,
and trading-operations platform. `frontend/README.md:3-57` describes the
dashboard as a read-only interface for paper trading, portfolio, risk,
backtest, and system evidence. `BACKTESTING.md:5-25`,
`PAPER_TRADING.md:5-33`, and `RISK_MANAGEMENT.md:5-80` all define explicit
simulation-oriented subsystems.

### Where the current implementation conflicts with v2

The current codebase is specialized to a different product shape:

- **Timeframe mismatch**: the current market-data and validation stack is
  daily BTC/USD oriented.
  - Evidence: `backend/app/market_data/models.py`, `backend/app/market_data/history.py`,
    `backend/app/validation/splits.py`, `backend/app/research/dataset.py:23-91`,
    `README.md:28-46`.
- **Target mismatch**: the current target is forward five-day log return.
  - Evidence: `backend/app/targets/forward_log_return.py:1-116`,
    `backend/app/persistence/targets.py`.
- **Model mismatch**: the current production artifact is a Ridge regression
  model.
  - Evidence: `backend/app/model_packaging/ridge.py`,
    `backend/app/inference/artifact.py`, `backend/app/persistence/model_inference.py`,
    `README.md:19-22, 41-49`.
- **Simulation mismatch**: backtesting, risk management, and paper trading
  are implemented as first-class product surfaces.
  - Evidence: `backend/app/backtesting/*`, `backend/app/backtesting/risk/*`,
    `backend/app/paper_trading/*`, `BACKTESTING.md:5-25`,
    `PAPER_TRADING.md:5-33`, `RISK_MANAGEMENT.md:5-26`.
- **Dashboard mismatch**: the frontend currently exposes pages for paper
  trading, portfolio, trade history, risk events, and backtest reports.
  - Evidence: `frontend/app/page.tsx`, `frontend/app/backtest-reports/page.tsx`,
    `frontend/app/paper-trading/page.tsx`, `frontend/app/portfolio/page.tsx`,
    `frontend/app/trade-history/page.tsx`, `frontend/app/risk-events/page.tsx`,
    `frontend/app/settings/page.tsx`, `frontend/README.md:33-57`.

Those components are technically coherent for the current repository, but they
do not match the AlphaLens v2 product vision.

### What can be reused

The following are strong candidates for reuse:

- `backend/app/persistence/database.py` and the PostgreSQL/Alembic stack.
- `backend/app/persistence/provenance.py` and the SHA-256 content-addressing
  patterns in the persistence/report layers.
- `backend/app/observability/logging.py` and `backend/app/observability/resources.py`.
- `backend/app/settings.py` and the environment-validation pattern.
- `backend/app/api/application.py` request validation, hash verification, and
  read-only API shape.
- `frontend/components/ui/*` and the dashboard shell / chart primitives.
- `docker-compose.yml`, backend/frontend Dockerfiles, and GitHub Actions
  workflow structure.
- The research-pipeline habit of deterministic replay, explicit provenance,
  and immutable persistence.

## Architecture Assessment

### Current dependency shape

The current architecture is largely linear:

`market_data -> features -> targets -> validation -> research -> persistence -> prediction API / dashboard`

There is also a separate live-read path:

`prediction_api -> inference -> dashboard`

This is good for reproducibility, but it hardcodes the current product around
daily closed-candle research and a single packaged Ridge inference artifact.

### Tight coupling points

1. **`backend/app/main.py` is an orchestration hub.**
   It imports market data, persistence, validation, target generation, and
   baseline research in one file. The routes show a single process hosting a
   large chunk of the product surface.
   - Evidence: `backend/app/main.py:13-44, 61-260`.

2. **`backend/app/persistence/models.py` is a monolithic schema file.**
   The file defines the complete relational schema for ingestion batches,
   candles, features, targets, experiments, multiple report families, the
   inference artifact, paper trading, backtesting, and API audits.
   - Evidence: `backend/app/persistence/models.py:32-3241`.

3. **The dashboard is hardwired to the v1 evidence model.**
   It renders predictions, paper portfolio, risk, backtest, and system data,
   all fetched from the read-only dashboard bundle.
   - Evidence: `frontend/lib/api.ts`, `frontend/lib/types.ts`,
     `frontend/app/page.tsx`, `frontend/app/backtest-reports/page.tsx`,
     `frontend/app/paper-trading/page.tsx`, `frontend/app/portfolio/page.tsx`,
     `frontend/app/risk-events/page.tsx`, `frontend/app/system-health/page.tsx`.

4. **The production API is intentionally narrow.**
   It validates a full ordered feature vector and serves a single model family.
   - Evidence: `backend/app/api/application.py:49-355`,
     `backend/app/api/schemas.py`.

### Loose coupling already present

The codebase already has some reusable boundaries:

- market data is abstracted behind a protocol;
- feature definitions are modular by indicator family;
- persistence is split by artifact family;
- the API is versioned and read-only;
- the frontend uses a single data bundle rather than recomputing logic.

Those boundaries are valuable for AlphaLens v2. The problem is not that the
architecture is absent; the problem is that the current domain contracts point
at the wrong product.

## Migration Strategy

### Principle 1: preserve platform foundations

Keep and reuse the parts that make the repository trustworthy:

- deterministic hashing;
- provenance tracking;
- async PostgreSQL access;
- locked dependency management;
- CI and containerization;
- strict request validation; and
- immutable evidence storage.

### Principle 2: replace the product contract

Replace the v1 product contract of:

- daily candle regression;
- final holdout selection;
- backtest/paper-trading simulation; and
- portfolio/risk report-centric UX

with the v2 contract of:

- intraday opportunity detection;
- BUY / SELL / WAIT decisioning;
- scanner-driven ranking;
- chart overlay explanations; and
- confidence only when calibrated and statistically defensible.

### Principle 3: keep the system read-only from a market-execution standpoint

AlphaLens v2 must not become a trading platform. Any execution, order
management, or portfolio simulation logic that remains in the repository
should be treated as non-core and removed from the product boundary.

### Principle 4: make the scanner and overlay first-class

The current repository treats the dashboard as a report viewer. v2 should
make the chart the primary workspace and move opportunity ranking into a
scanner that can drive the overlay.

### Principle 5: make confidence conditional

The product vision explicitly says confidence values must never appear unless
statistically calibrated. That means the future architecture needs a
calibration gate before confidence can be rendered in the overlay or scanner.

## Phase-by-Phase Roadmap

### Phase 0 — Contract freeze and scope reset

**Goal:** define the v2 product contract, remove ambiguity around the no-trade
boundary, and finalize the new data/timeframe contract.

**Prerequisites:** human approval of the v2 scope.

**Why it exists:** the current repository is strongly optimized for a v1
research/trading workflow. v2 should not be built by accident from the old
assumptions.

**Critical outputs:**

- approved v2 data scope;
- approved decision labels (`BUY`, `SELL`, `WAIT`);
- approved confidence/calibration policy;
- approved supported timeframes for Phase 1 (`5m`, `10m`, `15m`).

### Phase 1 — Intraday data pipeline

**Goal:** extend market data ingestion, validation, storage, and provenance
to BTC/USD intraday candles.

**Prerequisites:** Phase 0 contract freeze.

**Why it exists:** the current data layer is daily and cannot support the
intraday scanner/overlay vision without schema and validation changes.

### Phase 2 — Intraday feature engineering

**Goal:** build the intraday feature set and store versioned feature outputs
for 5m/10m/15m evidence.

**Prerequisites:** Phase 1.

**Why it exists:** the AI overlay and ranking engine need feature vectors that
are computed at the correct intraday decision boundary.

### Phase 3 — Decision engine and opportunity ranking

**Goal:** create the core `BUY / SELL / WAIT` decision engine and the ranking
layer that orders candidate opportunities by quality.

**Prerequisites:** Phase 2.

**Why it exists:** this is the core product behavior of AlphaLens v2.

### Phase 4 — Calibration and explainability

**Goal:** introduce statistical calibration gates for confidence and produce
human-readable reason codes/annotations for decisions.

**Prerequisites:** Phase 3 and a validated evaluation protocol.

### Phase 5 — AI opportunity scanner and chart overlay

**Goal:** expose the ranked opportunity feed and connect it to a chart overlay
that shows entry, stop, target, risk/reward, hold time, and annotation layers.

**Prerequisites:** Phases 3 and 4.

### Phase 6 — API and frontend refactor

**Goal:** replace the current prediction-centric dashboard with a
scanner/chart-centric product UI.

**Prerequisites:** Phases 3 through 5.

### Phase 7 — Decommission v1 simulation surfaces

**Goal:** remove or archive backtesting, paper trading, and simulated risk
modules from the main product boundary.

**Prerequisites:** the new v2 scanner/overlay path must already exist.

## Top 10 Highest-Impact Recommendations

| # | Recommendation | Expected product impact | Engineering effort | Why it matters | Priority | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Replace the daily forward-return regression target with a v2 decision target that can support BUY / SELL / WAIT. | Very high | XL | The current `forward_log_return` target (`backend/app/targets/forward_log_return.py:1-116`) is aligned to a v1 regression workflow, not the v2 decision engine. | P0 | `backend/app/targets/forward_log_return.py`, `backend/app/research/baseline_regression.py:1-157`, `backend/app/persistence/targets.py`, `README.md:31-45` |
| 2 | Expand the data model from daily BTC/USD candles to intraday BTC/USD (`5m`, `10m`, `15m`) with timezone-safe provenance. | Very high | XL | The current data model and docs are daily-only (`backend/app/market_data/*`, `backend/app/research/dataset.py:23-91`). v2 cannot produce intraday overlays without this. | P0 | `backend/app/market_data/models.py`, `backend/app/market_data/history.py`, `backend/app/validation/splits.py`, `backend/app/research/dataset.py`, `README.md:28-32, 75-94` |
| 3 | Introduce an opportunity ranking engine that orders setups before they reach the chart. | Very high | L | The current system evaluates models and reports metrics; it does not rank live opportunities for a scanner workflow. | P0 | `backend/app/research/model_selection_scoring.py`, `backend/app/research/final_model_selection.py`, `frontend/app/predictions/page.tsx`, `frontend/app/page.tsx` |
| 4 | Introduce a first-class decision engine that emits BUY / SELL / WAIT and nothing else. | Very high | L | The v2 product vision explicitly requires WAIT as a first-class outcome. The current code emits numeric predictions and simulated BUY/HOLD/EXIT signals. | P0 | `backend/app/api/application.py:331-355`, `backend/app/backtesting/strategy.py`, `backend/app/backtesting/signals.py`, `backend/app/paper_trading/engine.py` |
| 5 | Build the AI opportunity scanner as a separate API/read-model layer. | High | M | The dashboard currently consumes one broad report bundle. A scanner needs its own ranked opportunity contract and pagination/filtering model. | P1 | `frontend/lib/api.ts`, `frontend/lib/types.ts`, `backend/app/persistence/dashboard.py`, `frontend/app/predictions/page.tsx` |
| 6 | Build the AI chart overlay and annotation service. | High | M | The current frontend is report-centric. The v2 chart is the primary workspace and must display entry/stop/target/reason overlays directly on the chart. | P1 | `frontend/components/dashboard/time-series-chart.tsx`, `frontend/components/dashboard/app-shell.tsx`, `frontend/app/page.tsx`, `frontend/app/portfolio/page.tsx` |
| 7 | Add calibration and confidence gating before rendering probability/confidence values. | High | M | The product vision explicitly prohibits unvalidated confidence values. Nothing in the current API guarantees calibrated confidence output. | P1 | `backend/app/research/explainability.py`, `backend/app/research/statistical_validation.py`, `backend/app/api/application.py:319-355`, `README.md:15-22` |
| 8 | Remove the trading simulation stack from the main product boundary. | High | XL | `backtesting`, `risk_management`, and `paper_trading` are core v1 features, but AlphaLens v2 is not a broker, portfolio manager, or trading platform. | P0 | `backend/app/backtesting/*`, `backend/app/backtesting/risk/*`, `backend/app/paper_trading/*`, `BACKTESTING.md:5-25`, `PAPER_TRADING.md:5-33`, `RISK_MANAGEMENT.md:5-26` |
| 9 | Rework the frontend from evidence dashboard to chart-first opportunity console. | High | XL | The existing pages center on portfolio, backtests, risk events, and paper trading. v2 requires a chart overlay and opportunity scanner as the primary UX. | P1 | `frontend/app/page.tsx`, `frontend/app/backtest-reports/page.tsx`, `frontend/app/paper-trading/page.tsx`, `frontend/app/risk-events/page.tsx`, `frontend/README.md:33-57` |
| 10 | Preserve the immutable evidence/provenance stack while generalizing the product contracts. | Very high | M | The repository’s strongest property is reproducibility. This should be retained while changing the product-level contracts around target, ranking, and overlay behavior. | P0 | `AGENTS.md:43-109`, `RESEARCH_CONSTITUTION.md:1-71`, `backend/app/persistence/provenance.py`, `backend/app/persistence/models.py:32-3241` |

## Why these recommendations are prioritized this way

The highest-priority work is the work that changes the product boundary:

- data/timeframe expansion;
- decision target redesign;
- opportunity ranking;
- no-trade-aware decisioning; and
- removal of trade simulation from the core product boundary.

Everything else depends on those contracts. The scanner and overlay should not
be designed against a daily regression artifact, and the dashboard should not
be redesigned before the backend can produce the correct intraday decision
objects.

## Evidence summary

The migration plan above is grounded in the following repository evidence:

- `README.md:3-49, 71-144`
- `frontend/README.md:3-57`
- `BACKTESTING.md:5-78`
- `PAPER_TRADING.md:5-90`
- `RISK_MANAGEMENT.md:5-80`
- `backend/app/main.py:13-260`
- `backend/app/api/application.py:49-355`
- `backend/app/settings.py:13-186`
- `backend/app/market_data/*`
- `backend/app/features/*`
- `backend/app/targets/forward_log_return.py:1-116`
- `backend/app/validation/splits.py:1-174`
- `backend/app/research/dataset.py:23-240`
- `backend/app/research/baseline_regression.py:1-157`
- `backend/app/persistence/models.py:32-3241`
- `frontend/app/*.tsx`
- `frontend/components/dashboard/*`
- `frontend/lib/api.ts`
- `.github/workflows/backend.yml`
- `.github/workflows/frontend.yml`
- `.github/workflows/containers.yml`

The current repository is therefore best described as a v1 deterministic
research-and-trading-ops stack that needs a deliberate product migration to
become AlphaLens v2.
