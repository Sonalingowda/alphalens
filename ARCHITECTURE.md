# AlphaLens Repository Technical Audit

This document is a read-only technical audit of the repository as inspected in
the current workspace. It describes what actually exists in the codebase,
without proposing a redesign or future architecture.

## 1. Repository overview

AlphaLens is a full-stack quantitative market intelligence and research system
centered on BTC/USD daily market data. The repository now contains:

- a deterministic market-data ingestion and validation layer;
- point-in-time feature engineering and target generation;
- chronological validation and experiment tracking;
- multiple immutable research reports and comparisons;
- a packaged Ridge inference artifact and read-only prediction API;
- backtesting, risk management, and paper trading engines;
- a read-only Next.js dashboard that renders persisted evidence; and
- Docker and GitHub Actions support for local/CI deployment.

The project is not a toy scaffold. The codebase is a fairly complete
end-to-end internal platform with a strong emphasis on reproducibility,
auditability, and immutability. The implementation is also highly specialized:
most of the data flow is hardwired to BTC/USD daily evidence, the approved
feature set, and the selected Ridge regression artifact.

At a high level, the architecture separates into three operational layers:

1. Research/data-engineering workflows in `backend/app/main.py`.
2. Read-only live inference in `backend/app/prediction_api.py` and
   `backend/app/api/application.py`.
3. Read-only presentation in `frontend/`.

The repository is mature in the sense that the core workflow is implemented
and verified in code, but it still has a narrow domain focus, no
authentication, and no external broker connectivity.

## 2. Complete folder structure

The tree below shows the major repository structure and the files that matter
for understanding the current implementation.

```text
.
├── AGENTS.md
├── API.md
├── ARCHITECTURE.md
├── BACKTESTING.md
├── DEPLOYMENT.md
├── EXECUTIVE_SUMMARY.md
├── MODEL_INFERENCE_ARTIFACT.md
├── PAPER_TRADING.md
├── README.md
├── RESEARCH_CONSTITUTION.md
├── RESEARCH_SPECIFICATION.md
├── RISK_MANAGEMENT.md
├── ROADMAP.md
├── .env.example
├── .dockerignore
├── .gitignore
├── .github/
│   └── workflows/
│       ├── backend.yml
│       ├── containers.yml
│       └── frontend.yml
├── backend/
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .env.example
│   ├── .env.production.example
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 20260729_0001_create_market_data_tables.py
│   │       ├── 20260729_0002_create_engineered_features.py
│   │       ├── 20260729_0003_create_validation_runs.py
│   │       ├── 20260729_0004_expand_ingestion_audit.py
│   │       ├── 20260729_0005_audit_pagination_overlaps.py
│   │       ├── 20260729_0006_synchronize_active_provenance.py
│   │       ├── 20260729_0007_create_forward_log_return_targets.py
│   │       ├── 20260729_0008_create_regression_experiments.py
│   │       ├── 20260729_0009_add_baseline_evaluation_policy.py
│   │       ├── 20260729_0010_add_random_forest_baseline.py
│   │       ├── 20260729_0011_add_xgboost_baseline.py
│   │       ├── 20260729_0012_create_model_comparison_reports.py
│   │       ├── 20260729_0013_create_explainability_artifacts.py
│   │       ├── 20260729_0014_create_statistical_validation_reports.py
│   │       ├── 20260729_0015_create_residual_diagnostics.py
│   │       ├── 20260729_0016_create_market_regime_reports.py
│   │       ├── 20260729_0017_create_final_model_selection_reports.py
│   │       ├── 20260729_0018_create_holdout_evaluation.py
│   │       ├── 20260729_0019_create_backtest_reports.py
│   │       ├── 20260730_0020_create_risk_management_reports.py
│   │       ├── 20260730_0021_create_model_inference_artifacts.py
│   │       ├── 20260730_0022_create_paper_trading_reports.py
│   │       └── 20260730_0023_create_prediction_api_audits.py
│   ├── scripts/
│   │   └── start-production.sh
│   ├── app/
│   │   ├── main.py
│   │   ├── prediction_api.py
│   │   ├── startup.py
│   │   ├── settings.py
│   │   ├── api/
│   │   │   ├── application.py
│   │   │   ├── errors.py
│   │   │   ├── metrics.py
│   │   │   └── schemas.py
│   │   ├── observability/
│   │   │   ├── logging.py
│   │   │   └── resources.py
│   │   ├── inference/
│   │   │   ├── artifact.py
│   │   │   ├── interface.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   ├── model_packaging/
│   │   │   └── ridge.py
│   │   ├── market_data/
│   │   │   ├── models.py
│   │   │   ├── provider.py
│   │   │   ├── kraken.py
│   │   │   ├── history.py
│   │   │   └── validation.py
│   │   ├── features/
│   │   │   ├── contracts.py
│   │   │   ├── moving_averages.py
│   │   │   ├── momentum.py
│   │   │   ├── volatility.py
│   │   │   ├── volume.py
│   │   │   └── pipeline.py
│   │   ├── targets/
│   │   │   └── forward_log_return.py
│   │   ├── validation/
│   │   │   └── splits.py
│   │   ├── research/
│   │   │   ├── dataset.py
│   │   │   ├── baseline_regression.py
│   │   │   ├── model_comparison.py
│   │   │   ├── explainability.py
│   │   │   ├── statistical_validation.py
│   │   │   ├── residual_diagnostics.py
│   │   │   ├── market_regimes.py
│   │   │   ├── model_selection_scoring.py
│   │   │   ├── final_model_selection.py
│   │   │   ├── holdout_evaluation.py
│   │   │   ├── diagnostic_plots.py
│   │   │   └── regime_plots.py
│   │   ├── persistence/
│   │   │   ├── database.py
│   │   │   ├── models.py
│   │   │   ├── provenance.py
│   │   │   ├── candles.py
│   │   │   ├── features.py
│   │   │   ├── targets.py
│   │   │   ├── validation.py
│   │   │   ├── experiments.py
│   │   │   ├── explainability.py
│   │   │   ├── statistical_validation.py
│   │   │   ├── residual_diagnostics.py
│   │   │   ├── market_regimes.py
│   │   │   ├── model_comparisons.py
│   │   │   ├── final_model_selection.py
│   │   │   ├── holdout_evaluation.py
│   │   │   ├── model_inference.py
│   │   │   ├── backtests.py
│   │   │   ├── risk_management.py
│   │   │   ├── paper_trading.py
│   │   │   ├── dashboard.py
│   │   │   └── prediction_api.py
│   │   ├── backtesting/
│   │   │   ├── models.py
│   │   │   ├── strategy.py
│   │   │   ├── signals.py
│   │   │   ├── execution.py
│   │   │   ├── positions.py
│   │   │   ├── portfolio.py
│   │   │   ├── metrics.py
│   │   │   ├── reporting.py
│   │   │   ├── engine.py
│   │   │   └── risk/
│   │   │       ├── config.py
│   │   │       ├── models.py
│   │   │       ├── rules.py
│   │   │       ├── sizing.py
│   │   │       ├── portfolio.py
│   │   │       ├── manager.py
│   │   │       ├── engine.py
│   │   │       └── reporting.py
│   │   └── paper_trading/
│   │       ├── models.py
│   │       ├── market_data.py
│   │       ├── features.py
│   │       ├── inference.py
│   │       ├── scheduler.py
│   │       ├── orders.py
│   │       ├── portfolio.py
│   │       ├── performance.py
│   │       ├── risk.py
│   │       ├── audit.py
│   │       ├── reporting.py
│   │       ├── engine.py
│   │       └── service.py
│   └── tests/
│       ├── test_backtesting.py
│       ├── test_baseline_regression.py
│       ├── test_deployment.py
│       ├── test_explainability.py
│       ├── test_features.py
│       ├── test_final_model_selection.py
│       ├── test_forward_log_return_targets.py
│       ├── test_historical_backfill.py
│       ├── test_holdout_evaluation.py
│       ├── test_market_regimes.py
│       ├── test_model_comparison.py
│       ├── test_model_inference.py
│       ├── test_paper_trading.py
│       ├── test_prediction_api.py
│       ├── test_residual_diagnostics.py
│       ├── test_risk_management.py
│       ├── test_statistical_validation.py
│       └── test_validation_splits.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── package-lock.json
    ├── next.config.ts
    ├── eslint.config.mjs
    ├── postcss.config.mjs
    ├── tsconfig.json
    ├── vitest.config.mts
    ├── vitest.setup.ts
    ├── .env.production.example
    ├── app/
    │   ├── layout.tsx
    │   ├── globals.css
    │   ├── page.tsx
    │   ├── predictions/page.tsx
    │   ├── paper-trading/page.tsx
    │   ├── portfolio/page.tsx
    │   ├── trade-history/page.tsx
    │   ├── risk-events/page.tsx
    │   ├── backtest-reports/page.tsx
    │   ├── system-health/page.tsx
    │   └── settings/page.tsx
    ├── components/
    │   ├── dashboard/
    │   │   ├── app-shell.tsx
    │   │   ├── chart-card.tsx
    │   │   ├── data-states.tsx
    │   │   ├── metric-card.tsx
    │   │   ├── page-header.tsx
    │   │   ├── signal-badge.tsx
    │   │   ├── theme-toggle.tsx
    │   │   └── time-series-chart.tsx
    │   └── ui/
    │       ├── badge.tsx
    │       ├── button.tsx
    │       ├── card.tsx
    │       ├── dropdown-menu.tsx
    │       ├── progress.tsx
    │       ├── scroll-area.tsx
    │       ├── select.tsx
    │       ├── separator.tsx
    │       ├── sheet.tsx
    │       ├── skeleton.tsx
    │       ├── switch.tsx
    │       ├── table.tsx
    │       ├── tabs.tsx
    │       └── tooltip.tsx
    ├── lib/
    │   ├── api.ts
    │   ├── format.ts
    │   ├── types.ts
    │   └── utils.ts
    └── tests/
        ├── api.integration.test.ts
        ├── components.test.tsx
        └── server-only.ts
```

### Folder responsibilities

#### Repository root

The root contains repository governance, research/legal documentation, Docker
composition, and environment templates. Important files:

- `README.md`: public landing page for the repository.
- `AGENTS.md`: operating manual for future coding agents.
- `RESEARCH_CONSTITUTION.md`: immutable quantitative rules.
- `RESEARCH_SPECIFICATION.md`: research-target design discussion.
- `ROADMAP.md`: phase roadmap and approval gates.
- `API.md`, `BACKTESTING.md`, `PAPER_TRADING.md`, `RISK_MANAGEMENT.md`,
  `MODEL_INFERENCE_ARTIFACT.md`, `DEPLOYMENT.md`: subsystem documentation.
- `.env.example`: Compose-level local/production variable template.
- `.dockerignore`, `.gitignore`: build and repository hygiene rules.
- `docker-compose.yml`: local development stack for PostgreSQL, backend, and
  frontend.

#### `.github/workflows`

Contains three CI workflows:

- `backend.yml`: locked Python install, Ruff, bytecode compilation, and unit
  tests.
- `frontend.yml`: locked Node install, linting, type checking, tests, and
  production build.
- `containers.yml`: Compose validation and Docker image builds for backend
  and frontend.

#### `backend/`

Contains the Python backend, Alembic migrations, research pipeline, live API,
and all backend tests. It is the main implementation surface of the project.

Key files:

- `pyproject.toml` / `uv.lock`: Python dependency and lockfile management.
- `Dockerfile`: multi-stage container image for the backend.
- `alembic.ini`, `alembic/env.py`, `alembic/versions/*`: database migration
  configuration and history.
- `scripts/start-production.sh`: production startup sequence.
- `.env.example`, `.env.production.example`: backend runtime templates.

#### `backend/app/`

This is the core backend application package. The directory is organized by
concern rather than as a single monolith:

- `main.py`: research/engineering FastAPI app for ingestion, feature
  computation, targets, validation, and baseline experiments.
- `prediction_api.py`: production read-only inference entrypoint.
- `settings.py`: environment-driven configuration and validation.
- `startup.py`: configuration/readiness checks used at startup.
- `api/`: production API request/response layer, errors, metrics, and schemas.
- `observability/`: structured JSON logging and process resource snapshots.
- `inference/`: packaged Ridge inference artifact loading and validation.
- `model_packaging/`: one-time authorized packaging replay for the selected
  Ridge model.
- `market_data/`: provider abstraction, Kraken implementation, historical
  sample/backfill fetchers, and candle validation.
- `features/`: point-in-time feature contracts and the feature pipeline.
- `targets/`: forward-log-return target definition and generation.
- `validation/`: chronological walk-forward split generation and holdout
  controls.
- `research/`: baseline experiments, explainability, statistical validation,
  residual diagnostics, regime analysis, holdout evaluation, and report
  synthesis.
- `persistence/`: SQLAlchemy models plus the persistence and report-writing
  logic for every domain object.
- `backtesting/`: deterministic backtest engine and risk extension.
- `paper_trading/`: deterministic paper trading simulation using the packaged
  inference artifact.

#### `backend/tests/`

Contains the backend unit/integration coverage. The tests are organized by
subsystem: features, market data, validation, targets, baselines,
explainability, statistical validation, residual diagnostics, regime
analysis, final model selection, holdout evaluation, backtesting, risk
management, paper trading, prediction API, and deployment/configuration.

#### `frontend/`

Contains the Next.js dashboard, styling, client utilities, and frontend
tests. It is read-only from a business-logic perspective: it consumes API
projections and persisted evidence.

#### `frontend/app/`

Contains the actual routed pages:

- `/`: dashboard overview.
- `/predictions`: prediction evidence and history.
- `/paper-trading`: simulated signal/order flow.
- `/portfolio`: equity, returns, drawdown, exposure.
- `/trade-history`: completed simulated trades.
- `/risk-events`: risk audit trail.
- `/backtest-reports`: immutable backtest reports.
- `/system-health`: API, database, artifact, and test status.
- `/settings`: read-only paper-session configuration.

#### `frontend/components/`

Two groups of components exist:

- `components/dashboard/`: dashboard-specific presentation components and
  the application shell.
- `components/ui/`: reusable Base UI / shadcn-style primitives such as
  cards, buttons, badges, tables, selects, sheets, switches, tooltips,
  progress, separators, skeletons, scroll areas, dropdown menus, and tabs.

#### `frontend/lib/`

Client-side/server-component utilities:

- `api.ts`: fetches the dashboard bundle from the live API.
- `types.ts`: TypeScript contracts for all dashboard/API payloads.
- `format.ts`: formatting helpers for money, numbers, hashes, timestamps, and
  bytes.
- `utils.ts`: `cn()` helper for CSS class composition.

#### `frontend/tests/`

Contains component tests and API integration tests for the dashboard.

## 3. Frontend

### Framework

The frontend is a Next.js application using the App Router and React 19.
`frontend/next.config.ts` builds standalone output for container deployment.

### Routing

Routes are file-based under `frontend/app/`:

- `/` dashboard homepage
- `/predictions`
- `/paper-trading`
- `/portfolio`
- `/trade-history`
- `/risk-events`
- `/backtest-reports`
- `/system-health`
- `/settings`

There is no client-side router state beyond standard Next navigation.

### State management

There is no global client state library such as Redux, Zustand, or React
Query. Data is fetched server-side through `getDashboardBundle()` and passed
into server-rendered pages. The only local client state of note is the theme
toggle, which writes a `dark` class and persists the selected theme in
`window.localStorage`.

### Components

Most pages are assembled from reusable dashboard components:

- `AppShell` provides responsive navigation and branding.
- `PageHeader` standardizes section titles.
- `MetricCard`, `ChartCard`, `SignalBadge`, and `TimeSeriesChart` render the
  common dashboard surface.
- `ApiUnavailable` and `EmptyState` represent failure/empty states.

The `components/ui` folder contains the low-level primitives used to build the
rest of the interface.

### Pages

Each page is read-only and derives its data from the dashboard bundle:

- Dashboard: latest prediction, signal, portfolio summary, P&L, open/closed
  positions, risk events, latest API health, and artifact metadata.
- Predictions: prediction history table plus chart.
- Paper Trading: signal/order flow and position history.
- Portfolio: equity curve, daily returns, drawdown, and exposure.
- Trade History: ledger of completed simulated trades.
- Risk Events: accepted/rejected/forced risk events.
- Backtest Reports: persisted backtest summaries and equity curves.
- System Health: API/database/model/runtime/test status.
- Settings: read-only runtime configuration for the paper session.

### Charts

Charts use `lightweight-charts`. The chart component supports area, line, and
histogram series and is used for equity curves, prediction histories, daily
returns, drawdowns, and position history.

### Authentication

There is no user authentication, session management, role model, or identity
provider in the frontend.

### UI libraries

The frontend uses:

- Next.js / React
- Tailwind CSS 4
- shadcn-style primitives built on Base UI packages
- `lucide-react` icons
- `lightweight-charts`
- `clsx` and `tailwind-merge`

### Data flow

The frontend is a thin read-model client:

1. server components call `getDashboardBundle()`;
2. `getDashboardBundle()` fetches `/api/v1/dashboard`, `/api/v1/health`,
   `/api/v1/model`, `/api/v1/metrics`, and `/api/v1/resources`;
3. the API response is rendered into charts, tables, and cards; and
4. no local business logic computes model predictions, signals, or portfolio
   state.

### API calls

All frontend API calls are read-only `GET` requests to the live prediction API.
The base URL defaults to `http://127.0.0.1:8000` and can be overridden with
`ALPHALENS_API_BASE_URL`.

### Styling

Styling is Tailwind-first, with CSS variables defining a dark/institutional
theme. The dashboard uses a responsive grid system and card-based layouts. The
root document loads the Geist font.

### Responsive design

The app uses:

- a fixed desktop sidebar and mobile sheet navigation;
- responsive grids for metric cards and charts;
- mobile-friendly tables with horizontal overflow;
- theme-aware color tokens; and
- a dark theme by default.

## 4. Backend

### Framework

The backend uses FastAPI, SQLAlchemy 2.x async sessions, Alembic migrations,
Uvicorn, and Pydantic models.

### Architecture

The backend is intentionally split into two applications:

1. `app.main` — the research/data-engineering application.
2. `app.prediction_api` / `app.api.application` — the production read-only
   inference application.

This separation is one of the most important architectural boundaries in the
repository.

### Services

Major service areas:

- `settings.py`: environment configuration and validation.
- `startup.py`: configuration and readiness checks.
- `observability/`: structured logging and runtime resource snapshots.
- `inference/`: immutable model artifact loading and deterministic inference.
- `market_data/`: Kraken market-data provider and validation.
- `features/`: feature contracts, indicators, and pipeline.
- `targets/`: forward-log-return target generation.
- `validation/`: chronological split generation and holdout controls.
- `research/`: baseline regression, explainability, diagnostics, regime
  analysis, model selection, and holdout evaluation.
- `persistence/`: database persistence and audit/report writing.
- `backtesting/`: simulation engine and risk overlay.
- `paper_trading/`: live-data paper execution.

### Controllers / route handlers

The research application in `backend/app/main.py` exposes routes for:

- `GET /health`
- `GET /market-data/ping`
- `GET /market-data/history/validate`
- `POST /market-data/history/ingest`
- `GET /market-data/history/stored`
- `POST /features/compute`
- `GET /features/stored`
- `POST /targets/forward-log-return/generate`
- `POST /validation/splits`
- `GET /validation/runs/{run_id}`
- `POST /research/baselines/{model_family}`

The production inference app in `backend/app/api/application.py` exposes:

- `GET /api/v1/health`
- `GET /api/v1/version`
- `GET /api/v1/model`
- `GET /api/v1/metrics`
- `GET /api/v1/resources`
- `GET /api/v1/dashboard`
- `POST /api/v1/predict`

The same inference routes are also mounted as root aliases for compatibility.

### Business logic

The backend contains the project’s substantive logic:

- market-data ingestion and validation;
- feature engineering with point-in-time correctness checks;
- forward-log-return target generation;
- walk-forward validation and holdout isolation;
- deterministic baseline regression;
- explainability, statistical validation, residual diagnostics, regime
  analysis, and final model selection;
- official holdout evaluation;
- backtesting and risk management;
- paper trading simulation;
- prediction API request validation and immutable auditing.

### Middleware

The production API uses middleware for:

- request size limiting;
- request/response hashing;
- audit logging;
- CORS allowlisting when configured; and
- latency measurement / in-process metrics.

### Authentication

There is no auth system in the backend. The API is read-only and does not
expose mutation endpoints for production inference. Research endpoints are
also unauthenticated.

### Validation

Validation exists in several distinct places:

- environment/config validation in `settings.py`;
- market-data candle validation in `market_data/validation.py`;
- feature validation in the feature pipeline;
- target generation validation in `targets/forward_log_return.py`;
- chronological split validation in `validation/splits.py`;
- prediction request validation in `api/schemas.py` and
  `inference/service.py`;
- database/hash/provenance validation in persistence modules.

### Error handling

The production API defines structured deterministic errors via
`PredictionAPIError`. The research app converts domain exceptions into
explicit HTTP status codes.

### Logging

Logging is structured JSON through `observability/logging.py`. It is designed
for machine consumption and includes request path, method, status, latency,
error code, prediction hash, and artifact identifiers where applicable.

## 5. Machine learning

This repository contains a complete deterministic research workflow for a
single approved prediction target: forward five-day log return.

### Training pipeline

The baseline training workflow is in `backend/app/research/baseline_regression.py`.
It evaluates four approved baseline families:

- Linear Regression
- Ridge Regression
- Random Forest Regression
- XGBoost Regression

The training/evaluation policy is explicit:

- walk-forward chronological splits only;
- no random or shuffled splitting;
- a minimum training sample size before evaluation;
- split-by-split preprocessing fit inside the train partition only; and
- holdout exclusion from development evaluation.

### Inference pipeline

The deployed inference path is the packaged Ridge artifact. It is loaded by
`backend/app/inference/repository.py` and executed by
`backend/app/inference/service.py`.

Key properties:

- no `fit()` at inference time;
- exact feature ordering and schema validation;
- deterministic decimal-to-float conversion;
- immutable artifact and state hashes; and
- read-only prediction output.

### Models used

The repository currently contains:

- the selected Ridge regression model for production inference;
- Linear Regression as a baseline;
- Ridge Regression as a baseline and selected production model;
- Random Forest Regression as a nonlinear baseline; and
- XGBoost Regression as a nonlinear baseline.

### Target variables

The approved target is `forward_log_return` with a five-observation horizon:

`ln(C[t+H] / C[t])`

where `C[t]` is the completed close at the prediction timestamp and `H = 5`.

### Features

The approved feature set has twelve inputs:

- `bollinger_20_2_lower`
- `bollinger_20_2_middle`
- `bollinger_20_2_upper`
- `ema_20`
- `ema_50`
- `macd_12_26_9_histogram`
- `macd_12_26_9_line`
- `macd_12_26_9_signal`
- `rsi_14`
- `sma_20`
- `sma_50`
- `volume_sma_20`

### Feature engineering

The feature pipeline is deterministic and point-in-time safe:

- moving averages: SMA(20), SMA(50), EMA(20), EMA(50)
- momentum: RSI(14), MACD(12, 26, 9)
- volatility: Bollinger Bands(20, 2)
- volume: rolling volume SMA(20)

The pipeline rejects malformed candle input and only emits values when the
relevant historical lookback exists.

### Validation

Chronological validation uses expanding walk-forward splits with purge/embargo
and a final holdout period. The validation policy is designed to prevent
future information from leaking into training or feature calculation.

### Cross validation / walk-forward validation

The implementation is a chronological expanding-window walk-forward plan.
Each split has:

- a training range;
- a purge gap;
- a test range; and
- a final holdout excluded from iteration.

### Backtesting

The repository includes a separate deterministic backtesting engine. It is
not part of the model-training pipeline and is used for simulation and report
generation only.

### Evaluation metrics

The baseline and report stack uses:

- MAE
- RMSE
- Directional accuracy
- Statistical validation metrics
- Residual diagnostics
- Regime-conditioned metrics

### Saved models

The selected model is stored as a packaged inference artifact with:

- Ridge coefficients and intercept;
- StandardScaler state;
- ordered feature schema;
- artifact, state, configuration, and verification hashes; and
- provenance to the selected experiment and official holdout evidence.

### Model versioning

Versioning is explicit and immutable across the stack:

- feature pipeline version: `1.1.0`
- target version: `1.0.0`
- baseline evaluation policy version: `1.1.0`
- training pipeline version: `1.3.0`
- inference artifact version: `1.0.0`
- report versions: `1.0.0` for the major research reports

### Prediction pipeline

The production prediction pipeline validates:

- API version;
- schema hash;
- feature count;
- feature ordering;
- feature names;
- decimal values;
- artifact hashes; and
- request size.

### Data leakage prevention

Leakage prevention is implemented through:

- point-in-time feature computation;
- target generation with only future-horizon labels that become available
  after the prediction timestamp;
- walk-forward validation;
- purge gaps;
- final holdout isolation;
- prefix-invariance verification for features and targets; and
- deterministic replay checks of downstream experiments.

### Explainability

Explainability exists for the approved tree-based baselines:

- impurity-based feature importance for Random Forest;
- permutation importance; and
- TreeSHAP for Random Forest and XGBoost.

The explainability artifacts are persisted immutably and linked to the
approved experiments.

## 6. Market data

### Data sources

The live and historical market-data provider is Kraken’s public API. The
implementation uses no API key for the currently implemented endpoints.

### Historical data

The repository supports:

- a 90-day BTC/USD daily sample fetch; and
- paginated backfill up to Kraken’s public OHLC page limit.

Historical candles are validated for chronology, duplicates, gaps, incomplete
candles, invalid prices, and invalid volume before persistence.

### Live data

Current quote retrieval is implemented for BTC and ETH via Kraken’s public
ticker endpoint.

### APIs

The provider abstraction is defined by `market_data/provider.py`. The Kraken
implementation normalizes the provider responses into typed dataclasses in
`market_data/models.py`.

### Streaming

There is no streaming market-data subsystem.

### Caching

There is no dedicated market-data cache layer.

### Timeframes

The current implementation is daily BTC/USD (`1d`).

### Indicators

Market data itself does not compute technical indicators. Indicators are
derived later by the feature pipeline.

### Feature generation

Feature generation is downstream of market data and depends on complete,
validated daily candles.

## 7. Database

### Database type

The repository uses PostgreSQL, accessed asynchronously through SQLAlchemy and
`asyncpg`.

### ORM and migrations

SQLAlchemy declarative models live in `backend/app/persistence/models.py`.
Alembic drives schema evolution. There are 23 migration revisions in
`backend/alembic/versions/`.

### Core tables

The schema is intentionally broad and immutable-evidence oriented. Major
tables include:

- `market_data_ingestion_batches`
- `market_data_candles`
- `feature_pipeline_runs`
- `engineered_features`
- `validation_runs`
- `forward_log_return_target_runs`
- `forward_log_return_targets`
- `regression_experiments`
- `regression_experiment_splits`
- `model_comparison_reports`
- `model_comparison_report_experiments`
- `model_explainability_artifacts`
- `statistical_validation_reports`
- `statistical_validation_report_experiments`
- `statistical_validation_report_explainability`
- `experiment_prediction_evidence`
- `residual_diagnostics_reports`
- `residual_diagnostics_report_experiments`
- `residual_diagnostics_report_explainability`
- `residual_diagnostic_plots`
- `market_regime_analysis_reports`
- `market_regime_report_experiments`
- `market_regime_report_explainability`
- `market_regime_assignments`
- `market_regime_plots`
- `final_model_selection_reports`
- `final_model_selection_report_experiments`
- `final_model_selection_report_explainability`
- `holdout_evaluation_reports`
- `holdout_prediction_evidence`
- `holdout_consumptions`
- `backtest_reports`
- `risk_management_reports`
- `model_inference_artifacts`
- `paper_trading_reports`
- `prediction_api_audits`

### Relationships and keys

The schema is built around provenance and immutability rather than mutable
operational state.

Important relationships and constraints include:

- candles are unique by asset, quote currency, timeframe, and timestamp;
- features are unique by asset, quote currency, timeframe, timestamp,
  feature name, and pipeline version;
- targets are unique by asset, quote currency, timeframe, prediction
  timestamp, target name, and target version;
- validation runs reference both the active ingestion batch and active
  feature run;
- experiments reference the synchronized dataset, split hash, and validation
  run;
- report tables use link tables to preserve provenance to source experiments
  and artifact records; and
- holdout consumption is tracked separately so the official holdout can be
  marked consumed exactly once.

### Indexes

Key indexes and constraints are present on:

- ingestion batch identifiers;
- feature run provenance identifiers;
- experiment and report provenance fields;
- market regime assignment and plot tables;
- holdout evidence tables; and
- unique/validation constraints on the core data tables.

## 8. API documentation

### Production Live Prediction API

The production API is read-only, versioned, and audit-driven. It loads only
the packaged Ridge artifact.

| Endpoint | Purpose | Request | Response | Authentication | Dependencies |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v1/health` | Verify DB access and artifact hash validity. | None | Health/status JSON. | None | DB session, immutable artifact loader. |
| `GET /api/v1/version` | Report API version and read-only mode. | None | Version metadata JSON. | None | None beyond app startup. |
| `GET /api/v1/model` | Return model metadata and exact prediction schema. | None | Artifact/model metadata JSON. | None | Artifact loader, prediction service schema. |
| `GET /api/v1/metrics` | Return process-local operational counters. | None | Request/latency counters JSON. | None | In-process metrics snapshot. |
| `GET /api/v1/resources` | Return runtime resource snapshot. | None | Uptime/CPU/RSS JSON. | None | Resource snapshot helper. |
| `GET /api/v1/dashboard` | Return the read-only dashboard projection. | None | Dashboard bundle JSON. | None | DB dashboard projection, artifact verification. |
| `POST /api/v1/predict` | Generate a deterministic prediction. | Ordered feature vector request. | Prediction payload JSON. | None | Schema validation, artifact loader, audit persistence. |

Compatibility root aliases exist for the same routes outside `/api/v1`.

### Research / engineering API

The research app in `backend/app/main.py` exposes the following endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Basic application health check. |
| `GET /market-data/ping` | Verify live Kraken quote connectivity. |
| `GET /market-data/history/validate` | Fetch and validate a BTC/USD historical sample. |
| `POST /market-data/history/ingest` | Fetch, validate, and persist historical candles. |
| `GET /market-data/history/stored` | Summarize stored candle evidence. |
| `POST /features/compute` | Compute and persist engineered features. |
| `GET /features/stored` | Summarize stored feature evidence. |
| `POST /targets/forward-log-return/generate` | Generate and persist target labels. |
| `POST /validation/splits` | Create and persist a validation run. |
| `GET /validation/runs/{run_id}` | Retrieve a persisted validation run. |
| `POST /research/baselines/{model_family}` | Run a deterministic baseline experiment. |

## 9. Features

The table below describes the major implemented product features. Completion
percentages are approximate repository-state indicators, not performance
claims.

| Feature | Status | Description | Files | Dependencies | Completion % |
| --- | --- | --- | --- | --- | --- |
| Deterministic market-data ingestion | Implemented | Kraken quote/history fetch, validation, and persistence. | `backend/app/market_data/*`, `backend/app/persistence/candles.py`, `backend/app/main.py` | Kraken public API, PostgreSQL, SQLAlchemy | 100% |
| Feature engineering | Implemented | Point-in-time indicators and pipeline versioning. | `backend/app/features/*`, `backend/app/persistence/features.py` | Validated candles, target-free prefix inputs | 100% |
| Forward-log-return targets | Implemented | Five-step target generation with provenance and exclusions. | `backend/app/targets/forward_log_return.py`, `backend/app/persistence/targets.py` | Validated candles, active feature run | 100% |
| Chronological validation | Implemented | Expanding walk-forward splits with purge and holdout. | `backend/app/validation/splits.py`, `backend/app/persistence/validation.py` | Active candles/features, max feature window | 100% |
| Baseline ML experiments | Implemented | Linear, Ridge, Random Forest, XGBoost evaluation. | `backend/app/research/baseline_regression.py`, `backend/app/persistence/experiments.py` | Model-ready dataset, validation run | 100% |
| Explainability | Implemented | Permutation importance, impurity importance, TreeSHAP. | `backend/app/research/explainability.py`, `backend/app/persistence/explainability.py` | Tree baselines, verification evidence | 100% |
| Statistical validation | Implemented | Paired tests, bootstrap CIs, effect sizes, Holm correction. | `backend/app/research/statistical_validation.py`, `backend/app/persistence/statistical_validation.py` | Baseline experiments, explainability artifacts | 100% |
| Residual diagnostics | Implemented | Residual stats, autocorrelation, heteroscedasticity, plots. | `backend/app/research/residual_diagnostics.py`, `backend/app/persistence/residual_diagnostics.py` | Approved experiments, replayed predictions | 100% |
| Market regime analysis | Implemented | Deterministic bull/bear/sideways and volatility regimes. | `backend/app/research/market_regimes.py`, `backend/app/persistence/market_regimes.py` | Approved experiments, explainability artifacts | 100% |
| Final model selection | Implemented | Deterministic scoring and selection report. | `backend/app/research/final_model_selection.py`, `backend/app/persistence/final_model_selection.py` | Comparison, statistical, residual, regime evidence | 100% |
| Holdout evaluation | Implemented | One-time official holdout evaluation of selected Ridge. | `backend/app/research/holdout_evaluation.py`, `backend/app/persistence/holdout_evaluation.py` | Selected experiment, held-out timestamps | 100% |
| Inference packaging | Implemented | Immutable Ridge inference artifact and verification. | `backend/app/model_packaging/ridge.py`, `backend/app/inference/*`, `backend/app/persistence/model_inference.py` | Selected experiment, official holdout evidence | 100% |
| Backtesting engine | Implemented | Deterministic single-instrument long-only backtest engine. | `backend/app/backtesting/*`, `backend/app/persistence/backtests.py` | Holdout predictions, market bars, strategy config | 100% |
| Risk management | Implemented | Modular risk rules and risk-aware backtesting. | `backend/app/backtesting/risk/*`, `backend/app/persistence/risk_management.py` | Backtest engine, immutable evidence | 100% |
| Paper trading | Implemented | Simulated trading using live public data and packaged inference. | `backend/app/paper_trading/*`, `backend/app/persistence/paper_trading.py` | Kraken data, packaged inference, risk manager | 100% |
| Live prediction API | Implemented | Read-only REST API for deterministic predictions. | `backend/app/api/*`, `backend/app/prediction_api.py`, `backend/app/persistence/prediction_api.py` | Packaged inference artifact, audit DB | 100% |
| Dashboard | Implemented | Read-only Next.js dashboard with charts and tables. | `frontend/app/*`, `frontend/components/*`, `frontend/lib/*` | Live Prediction API, persisted reports | 100% |
| Docker deployment | Implemented | Backend, frontend, and Compose deployment images. | `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | Docker, PostgreSQL | 100% |
| CI/CD | Implemented | GitHub Actions for backend, frontend, and containers. | `.github/workflows/*` | GitHub Actions, Docker, locked installs | 100% |
| SHA-256 provenance | Implemented | Content-addressed evidence across reports and artifacts. | `backend/app/inference/*`, `backend/app/persistence/*`, research modules | Deterministic serialization | 100% |
| Automated tests | Implemented | Unit/integration coverage across backend and frontend. | `backend/tests/*`, `frontend/tests/*` | Backend and frontend toolchains | 100% |

Features that are not implemented include user authentication, broker
connectivity, live trading, WebSockets, and a mutable multi-user workflow.

## 10. Dependencies

### Backend major dependencies

The backend’s `pyproject.toml` declares these main runtime packages:

- `fastapi`: HTTP framework for the research app and production API.
- `uvicorn`: ASGI server.
- `sqlalchemy[asyncio]`: ORM and async database access.
- `asyncpg`: PostgreSQL driver.
- `alembic`: database migrations.
- `scikit-learn`: baseline models and preprocessing.
- `xgboost`: XGBoost baseline and explainability.
- `scipy`: statistical testing and diagnostics.
- `shap`: TreeSHAP explainability.
- `httpx`: external HTTP client for Kraken and related checks.

### Frontend major dependencies

The frontend depends on:

- `next`
- `react`
- `react-dom`
- `tailwindcss` and `@tailwindcss/postcss`
- `lightweight-charts`
- `lucide-react`
- `clsx`
- `tailwind-merge`
- `@base-ui/react` primitives used by the dashboard UI
- `vitest`, `@testing-library/react`, `jsdom` for tests

### Tooling

Repository tooling includes:

- `uv` for Python dependency locking and execution;
- `npm` for frontend dependency installation and scripts;
- Ruff for Python linting;
- ESLint and TypeScript for frontend quality gates;
- Alembic for schema migration management; and
- GitHub Actions / Docker Compose for CI and local deployment.

## 11. External integrations

### Present integrations

- **Kraken public API**: source of live quotes and OHLC candles.
- **PostgreSQL**: canonical storage for market data, features, targets,
  validation, experiments, reports, inference artifacts, and audits.
- **Docker / Docker Compose**: local and production container packaging.
- **GitHub Actions**: CI for backend, frontend, and container builds.
- **Next.js / lightweight-charts**: frontend rendering and charting.

### Not present

The repository does not currently integrate with:

- Supabase
- Redis
- live broker APIs
- authentication providers
- cloud deployment platforms
- WebSocket infrastructure
- message queues

## 12. Technical debt

The repository is strong on determinism, but there are clear maintainability
and scope constraints.

### Structural debt

- `backend/app/persistence/models.py` is a very large monolithic schema file.
- Several research modules are also large and domain-dense.
- `backend/app/main.py` is a substantial orchestration module that combines
  multiple workflows in one file.
- The frontend is intentionally thin and read-only; it has no mutable client
  state model.

### Scope debt

- Most pipelines are specialized to BTC/USD daily data.
- The research stack is tuned to a single approved target and a narrow set of
  baselines.
- There is no generic multi-asset or multi-timeframe abstraction.

### Operational debt

- There is no authentication or authorization layer.
- There is no live broker connectivity.
- There is no external monitoring platform wired in.
- The production API intentionally exposes no OpenAPI/Swagger docs.

### Quality risks

- The repository relies heavily on long deterministic modules, which makes
  navigation harder than in a more decomposed codebase.
- Some outputs are stored as JSON blobs, which is good for immutability but
  harder to query analytically than fully normalized structures.
- Extension to new assets or targets would require synchronized changes across
  persistence, research, validation, and dashboard layers.

## 13. Keep / Modify / Remove

### Keep

- Deterministic, content-addressed research artifacts.
- The hard boundary between research workflows and read-only production
  inference.
- The synchronized market-data → features → targets → validation → experiments
  provenance chain.
- SQLAlchemy/Alembic/PostgreSQL as the persistence stack.
- The dashboard’s read-only model of the system.
- The current test-driven reproducibility approach.

### Modify

- Break up `backend/app/persistence/models.py` and similarly large research
  modules if maintainability becomes a bottleneck.
- Consider reducing repeated serialization/hashing code across report modules.
- Add deeper end-to-end runtime coverage if the project starts accepting
  external traffic.

### Remove

- No functional product modules should be removed based on the current code.
- Any untracked local cache artifacts in the working tree should be cleaned
  before commits if the repository owner wants a pristine checkout.

## 14. Current product

AlphaLens currently is a deterministic quantitative research and internal
operations platform for BTC/USD daily data. It ingests Kraken public data,
validates it, computes a fixed feature pipeline, generates a five-day forward
log-return target, evaluates several baseline regressors, produces immutable
research reports, packages a selected Ridge model for inference, exposes a
read-only prediction API, simulates backtests and paper trading, and renders a
dashboard from persisted evidence.

It is not a broker-connected trading system, a multi-tenant SaaS product, or a
generic machine-learning platform.

## 15. Build status

### Completed

- backend research workflow
- market-data ingestion and validation
- feature engineering
- target generation
- walk-forward validation
- baseline regression experiments
- explainability, statistical validation, residual diagnostics, regime
  analysis, final model selection
- official holdout evaluation
- packaged Ridge inference artifact
- read-only prediction API
- backtesting, risk management, paper trading
- dashboard
- Docker and CI scaffolding

### Partially complete

- broader asset and timeframe support
- external trading connectivity
- user authentication / authorization
- operational observability outside process-local metrics

### Experimental

- no actively experimental product surface is obvious in the repository
  beyond the research workflow itself

### Deprecated

- none identified in the codebase

### Broken

- no code breakage is evident from inspection alone; runtime verification is
  separate from this audit

## 16. Development roadmap

This is not a product roadmap; it is the set of natural next engineering
steps implied by the current code.

1. Expand beyond BTC/USD daily evidence to additional assets or timeframes.
2. Remove hardcoded single-asset assumptions from the research and dashboard
   layers.
3. Add authenticated user access and role-aware dashboard behavior if the
   system will be exposed beyond trusted operators.
4. Extend operational monitoring beyond in-process metrics if production usage
   requires external observability.
5. Reduce the size of the largest persistence/research modules.
6. Add stronger browser-level end-to-end coverage for the dashboard and API
   integration flow.
7. Broaden the report/query layer if users need analytical access rather than
   only immutable read models.

## 17. Overall assessment

### Architecture score: 9/10

The architecture is unusually disciplined for a single repository: research
artifacts are immutable, provenance is explicit, the production API is
read-only, and the frontend is a thin consumer of persisted evidence. The
deduction is for the narrow BTC/USD specialization and the size of the central
schema module.

### Code quality: 8/10

The code is strongly typed, deterministic, and well covered by tests. The
remaining deduction comes from very large orchestration/persistence modules and
some repeated serialization/hashing patterns.

### Scalability: 6/10

The system is structurally capable, but the current implementation is narrow:
one asset, one timeframe, one approved target, and a single production model.
There is no distributed execution or multi-tenant runtime.

### Maintainability: 7/10

The code is organized by domain and has clear boundaries, but the schema and
research modules are large enough to become hard to navigate as the system
grows.

### ML pipeline: 9/10

The ML/research workflow is one of the strongest parts of the repository. It
includes deterministic features, targets, validation, baselines, explainable
artifacts, statistical validation, residual analysis, regime analysis, final
selection, holdout evaluation, and inference packaging.

### Production readiness: 8/10

The system has deployment artifacts, a production API, immutable evidence, and
CI. The deduction is for the lack of authentication, the narrow data domain,
and the absence of external monitoring and broker connectivity.

---

This audit intentionally describes the current implementation only. It does
not assign future features or alter the repository’s architecture.
