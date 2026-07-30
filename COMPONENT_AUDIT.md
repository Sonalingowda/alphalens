# AlphaLens Component Audit

This audit groups the repository into significant components and classifies
each one against the AlphaLens v2 product vision.

## Classification rules

- **KEEP** — the component already supports the v2 target state without
  material change.
- **MODIFY** — the component can be reused, but its contract, behavior, or
  shape must change.
- **REMOVE** — the component conflicts with the v2 product vision and should
  not remain part of the main product boundary.
- **ADD** — the component does not exist in the repository but is required for
  AlphaLens v2.

When a component is classified as MODIFY, the scale uses:

- **Minor**
- **Medium**
- **Major**
- **Rewrite**

Complexity uses:

- **XS**
- **S**
- **M**
- **L**
- **XL**

Risk uses:

- **Low**
- **Medium**
- **High**

---

## Table 1 — Platform foundations that can be reused

| Name | Purpose | Current State | Dependencies | KEEP / MODIFY / REMOVE / ADD | Modification Scale | Complexity | Risk | Reasoning | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Governance docs and phase rules | Repository-wide rules, research constitution, roadmap, API/deployment docs, and existing audit docs. | The repo already has detailed governance and subsystem documentation, but much of it describes the v1 research/trading stack rather than the v2 opportunity-scanner product. | All product and engineering components. | MODIFY | Major | M | Medium | The governance/documentation pattern is useful and should be retained, but the content must be rewritten to reflect the v2 product boundary and remove trading-platform assumptions. | `AGENTS.md:1-113`<br>`RESEARCH_CONSTITUTION.md:1-71`<br>`ROADMAP.md:1-45`<br>`README.md:1-220`<br>`frontend/README.md:1-57`<br>`API.md`<br>`BACKTESTING.md`<br>`PAPER_TRADING.md`<br>`RISK_MANAGEMENT.md`<br>`MODEL_INFERENCE_ARTIFACT.md`<br>`DEPLOYMENT.md` |
| Backend config, startup, and observability foundation | Load environment variables, validate runtime configuration, configure structured logging, and expose process-resource snapshots. | Existing code is cleanly separated and reusable, but the configuration surface is still sized for the current v1 stack. | Database, API application, deployment scripts. | MODIFY | Minor | S | Low | The settings/logging/resource patterns are worth keeping; they only need new v2 configuration keys and a few contract adjustments, not a rewrite. | `backend/app/settings.py:13-186`<br>`backend/app/startup.py`<br>`backend/app/observability/logging.py`<br>`backend/app/observability/resources.py`<br>`backend/app/prediction_api.py` |
| PostgreSQL async persistence base | Async engine/session factory and database access layer. | Present and already used throughout the repository. | SQLAlchemy, asyncpg, Alembic. | KEEP | N/A | S | Low | The database access layer is a clean foundation for the v2 product and does not conflict with the target state. | `backend/app/persistence/database.py`<br>`backend/app/persistence/models.py:32-3241`<br>`backend/alembic/env.py` |
| Containerization and CI scaffolding | Dockerfiles, Compose file, GitHub Actions workflows. | Present and already wired for backend, frontend, and container builds. | Backend, frontend, PostgreSQL, GitHub Actions, Docker. | KEEP | Minor | M | Low | The delivery scaffolding is directly reusable; the commands and health checks may change, but the overall packaging pattern is correct. | `backend/Dockerfile`<br>`frontend/Dockerfile`<br>`docker-compose.yml`<br>`.github/workflows/backend.yml`<br>`.github/workflows/frontend.yml`<br>`.github/workflows/containers.yml`<br>`DEPLOYMENT.md` |
| Frontend UI primitives | Base UI / shadcn-style primitives and chart primitives. | Present and reasonably reusable. | Next.js, React, Tailwind, Base UI, lightweight-charts. | KEEP | Minor | M | Low | The primitives are generic and valuable; they should survive the migration even though the page composition will change. | `frontend/components/ui/*`<br>`frontend/components/dashboard/time-series-chart.tsx`<br>`frontend/components/dashboard/chart-card.tsx`<br>`frontend/components/dashboard/metric-card.tsx` |

---

## Table 2 — v1 subsystems that require modification or removal

| Name | Purpose | Current State | Dependencies | KEEP / MODIFY / REMOVE / ADD | Modification Scale | Complexity | Risk | Reasoning | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Market-data ingestion and provider layer | Fetch current quotes, fetch historical OHLC candles, validate and persist BTC/USD data. | Implemented and working for Kraken public APIs, but hardwired to the current BTC/USD daily workflow. | Kraken public API, validation, persistence, settings. | MODIFY | Major | L | Medium | The provider abstraction is reusable, but the current asset/timeframe assumptions and daily-only history/backfill flow do not satisfy v2 intraday requirements. | `backend/app/market_data/models.py`<br>`backend/app/market_data/provider.py`<br>`backend/app/market_data/kraken.py`<br>`backend/app/market_data/history.py`<br>`backend/app/market_data/validation.py`<br>`backend/app/persistence/candles.py`<br>`backend/app/main.py:66-200` |
| Feature engineering pipeline | Compute deterministic technical features and persist versioned feature runs. | Implemented for 12 daily features (SMA/EMA/MACD/RSI/Bollinger/volume SMA) with point-in-time checks. | Market data, persistence, research dataset builder. | MODIFY | Major | L | Medium | The deterministic feature-engineering pattern is reusable, but the feature set and intraday timeframes must change for an AI chart overlay and opportunity scanner. | `backend/app/features/contracts.py`<br>`backend/app/features/moving_averages.py`<br>`backend/app/features/momentum.py`<br>`backend/app/features/volatility.py`<br>`backend/app/features/volume.py`<br>`backend/app/features/pipeline.py`<br>`backend/app/persistence/features.py`<br>`backend/app/research/dataset.py:23-240` |
| Target generation and walk-forward validation | Create forward-log-return labels and chronological validation splits with holdout isolation. | Implemented around 5-step forward log return and expanding walk-forward splits. | Features, candles, persistence, baseline research. | MODIFY | Major | L | High | v2 needs a decision engine and opportunity-ranking contract, not the current regression target. The chronology/validation scaffolding is reusable, but the target semantics must be replaced. | `backend/app/targets/forward_log_return.py:1-116`<br>`backend/app/validation/splits.py:1-174`<br>`backend/app/persistence/targets.py`<br>`backend/app/persistence/validation.py` |
| Research experiment and report stack | Run baselines, compare models, compute explainability, statistical validation, residual diagnostics, regime analysis, final selection, and holdout evaluation. | Implemented as a full deterministic research workflow anchored to the current regression problem. | Dataset builder, persistence, inference artifact, statistical libraries, SHAP, scikit-learn, XGBoost. | MODIFY | Major | XL | High | The research/report pattern is valuable, but the current target, metrics, and report contracts are tied to daily regression and must be redefined for v2 opportunity ranking and calibration. | `backend/app/research/baseline_regression.py`<br>`backend/app/research/model_comparison.py`<br>`backend/app/research/explainability.py`<br>`backend/app/research/statistical_validation.py`<br>`backend/app/research/residual_diagnostics.py`<br>`backend/app/research/market_regimes.py`<br>`backend/app/research/model_selection_scoring.py`<br>`backend/app/research/final_model_selection.py`<br>`backend/app/research/holdout_evaluation.py`<br>`backend/app/research/diagnostic_plots.py`<br>`backend/app/research/regime_plots.py` |
| Inference packaging and live prediction API | Package the selected Ridge model and serve deterministic predictions through a read-only API. | Implemented and production-shaped, but the artifact is Ridge-specific and the API contract is prediction-centric rather than opportunity-centric. | Research artifact, dashboard projection, persistence, audit logging. | MODIFY | Major | L | High | The read-only API shape is worth keeping, but the current payloads and artifact assumptions are specific to the selected Ridge model. v2 will need a different inference artifact and new route contracts. | `backend/app/model_packaging/ridge.py`<br>`backend/app/inference/artifact.py`<br>`backend/app/inference/interface.py`<br>`backend/app/inference/repository.py`<br>`backend/app/inference/service.py`<br>`backend/app/api/application.py:49-355`<br>`backend/app/api/schemas.py`<br>`backend/app/persistence/model_inference.py`<br>`backend/app/persistence/prediction_api.py` |
| Persistence schema and report registry | Store candles, features, targets, validation runs, experiments, reports, inference artifacts, and audit evidence. | Implemented as a very large immutable-evidence schema. | PostgreSQL, SQLAlchemy, Alembic, all backend subsystems. | MODIFY | Major | XL | High | The provenance-heavy storage model is the right foundation, but many tables are v1-specific (forward-return, regression experiments, backtesting, paper trading, holdout evaluation) and must be reshaped for v2. | `backend/app/persistence/models.py:32-3241`<br>`backend/app/persistence/dashboard.py`<br>`backend/app/persistence/provenance.py`<br>`backend/app/persistence/experiments.py`<br>`backend/app/persistence/backtests.py`<br>`backend/app/persistence/paper_trading.py`<br>`backend/app/persistence/model_inference.py` |
| Backtesting engine | Simulate strategies against immutable evidence and compute performance metrics. | Implemented as a deterministic long-only, single-instrument backtest stack. | Predictions, market bars, portfolio simulation, risk rules, persistence. | REMOVE | N/A | L | High | AlphaLens v2 is explicitly not a trading platform or order-execution system. The current backtesting subsystem conflicts with the target product boundary and should not remain in the v2 mainline. | `backend/app/backtesting/*`<br>`BACKTESTING.md:5-78`<br>`README.md:43-46, 135-140` |
| Risk management framework | Apply trade admission, allocation, stop, drawdown, and forced-exit rules to simulated orders. | Implemented as an extension of the backtesting engine. | Backtesting, order execution, portfolio state, persistence. | REMOVE | N/A | L | High | The v1 risk layer is designed for simulated trade management. v2 needs opportunity analysis and chart overlays, not a simulated portfolio risk engine. | `backend/app/backtesting/risk/*`<br>`RISK_MANAGEMENT.md:5-80`<br>`README.md:44-45` |
| Paper trading engine | Simulate trading with live public market data and the production inference artifact. | Implemented as a BTC/USD daily long-only paper trading stack. | Market data, inference, strategy, risk, orders, portfolio, persistence. | REMOVE | N/A | XL | High | This directly conflicts with the v2 product vision: AlphaLens never executes trades and is not a paper-trading application. | `backend/app/paper_trading/*`<br>`PAPER_TRADING.md:5-90`<br>`README.md:45-46` |
| Dashboard application and route set | Render read-only operational evidence and reports. | Implemented as a broad dashboard with pages for predictions, paper trading, portfolio, trade history, risk events, backtest reports, health, and settings. | Live API, dashboard bundle, chart primitives, UI components. | MODIFY | Major | XL | Medium | The dashboard framework is strong, but the current pages encode the v1 trading-ops product. v2 needs chart-first opportunity scanning and overlays instead. | `frontend/app/page.tsx`<br>`frontend/app/predictions/page.tsx`<br>`frontend/app/paper-trading/page.tsx`<br>`frontend/app/portfolio/page.tsx`<br>`frontend/app/trade-history/page.tsx`<br>`frontend/app/risk-events/page.tsx`<br>`frontend/app/backtest-reports/page.tsx`<br>`frontend/app/system-health/page.tsx`<br>`frontend/app/settings/page.tsx`<br>`frontend/components/dashboard/app-shell.tsx`<br>`frontend/lib/api.ts`<br>`frontend/lib/types.ts`<br>`frontend/README.md:33-57` |
| Backend and frontend tests | Verify the current research/inference/dashboard stack. | Broad coverage exists across market data, features, targets, validation, research, inference, deployment, frontend components, and API integration. | All product and platform packages. | MODIFY | Major | L | Medium | The testing culture is excellent, but the assertions are tied to the current v1 contract. Tests must be rewritten to validate the new v2 decision/scanner/overlay behavior. | `backend/tests/*`<br>`frontend/tests/*`<br>`backend/pyproject.toml`<br>`frontend/package.json` |

---

## Table 3 — Missing AlphaLens v2 components that must be added

| Name | Purpose | Current State | Dependencies | KEEP / MODIFY / REMOVE / ADD | Modification Scale | Complexity | Risk | Reasoning | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Intraday market-data pipeline | Persist and validate BTC/USD 5m, 10m, and 15m candles with provenance and backfill support. | Not present in the repository. | Market-data provider abstraction, PostgreSQL, validation, scheduler. | ADD | N/A | XL | High | The current implementation is daily-only. v2 phase 1 explicitly requires intraday data as the substrate for the scanner and overlay. | Current repo evidence only shows daily BTC/USD paths in `backend/app/market_data/*`, `backend/app/research/dataset.py:23-91`, and `README.md:28-32, 75-94`. |
| AI decision engine | Produce BUY / SELL / WAIT outputs from approved point-in-time evidence under a versioned decision policy. | Not present in the repository. | Feature evidence, approved decision policy, research/evaluation evidence. | ADD | N/A | L | High | The product vision centers on three decisions, with WAIT as a first-class outcome. No such decision engine exists in the current code. | Current API only exposes numeric prediction inference in `backend/app/api/application.py:308-355`. |
| Opportunity ranking engine | Rank candidate setups by quality and surface only the best setups. | Not present in the repository. | Decision engine, approved ranking policy, research/evaluation evidence, evidence store; optional approved calibration evidence. | ADD | N/A | L | High | AlphaLens v2 must maximize opportunity quality rather than signal count. The repository currently selects models, not trading opportunities. | `backend/app/research/model_selection_scoring.py` and `backend/app/research/final_model_selection.py` are model-selection oriented, not scanner ranking. |
| AI opportunity scanner | Continuously scan supported markets and rank opportunities. | Not present in the repository. | Intraday pipeline, ranking engine, decision engine, API layer. | ADD | N/A | L | High | This is one of the three core pillars of the v2 target state and does not exist in the current repository. | No route or module in `backend/app/main.py:61-260` or `backend/app/api/application.py:49-355` exposes scanner behavior. |
| AI chart overlay and annotation service | Overlay entry/stop/target/risk-reward/reasoning on the chart. | Not present in the repository. | Scanner, decision engine, chart data, frontend charting primitives. | ADD | N/A | M | Medium | The current frontend has charts, but not semantic AI overlays or annotations. v2 makes the chart the primary workspace. | `frontend/components/dashboard/time-series-chart.tsx` and `frontend/app/page.tsx` render charts and metrics, but no overlay/annotation service exists. |
| Confidence calibration / abstention service | Gate confidence values so they appear only when statistically validated. | Not present in the repository as a distinct subsystem. | Research evaluation, calibration metrics, decision engine, scanner. | ADD | N/A | M | High | The product vision says confidence must never appear unless statistically calibrated. The current API explicitly reports that calibrated confidence is unavailable. | `backend/app/persistence/dashboard.py` sets `confidence.available` to `False`; `backend/app/api/application.py:319-355` does not expose calibrated confidence. |

## Notes on dependency graph and coupling

The most important dependency chains to preserve or rebuild are:

- `market_data -> persistence -> feature engineering -> validation -> research -> API/dashboard`
- `inference artifact -> production API -> dashboard`
- `dashboard bundle -> frontend pages`

The most important chains to break are:

- `backtesting -> risk management -> paper trading`
- `daily regression target -> model selection -> holdout evaluation -> trading simulation`
- `paper-trading dashboard pages -> product identity`

Those chains are the clearest boundary between AlphaLens v1 and AlphaLens v2.
