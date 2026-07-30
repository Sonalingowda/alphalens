# AlphaLens Executive Summary

AlphaLens is a deterministic quantitative research and internal operations
platform for BTC/USD daily market data. It ingests public Kraken data,
validates and persists it, computes a fixed feature set, generates a forward
log-return target, evaluates baseline models, produces immutable research
reports, packages a selected Ridge model for read-only inference, and renders
an operator dashboard from persisted evidence.

## Repository snapshot

### What it currently is

- A full-stack Python + Next.js application.
- Research-heavy, production-shaped, and strongly provenance-driven.
- Specialised to one asset class/data source path: BTC/USD daily candles from
  Kraken.
- Built around immutable artifacts rather than mutable model or trading state.

### Current architecture

- `backend/app/main.py` handles research and data-engineering workflows.
- `backend/app/prediction_api.py` + `backend/app/api/application.py` expose
  the read-only production inference API.
- `frontend/` renders a dashboard from API-provided evidence.
- PostgreSQL is the canonical persistence layer.

### Maturity

The repository is well beyond a scaffold:

- deterministic ingestion and validation exist;
- features and labels are versioned and persisted;
- walk-forward validation and holdout isolation are implemented;
- multiple research reports are materialized as immutable artifacts;
- the production API only serves packaged inference; and
- the dashboard is wired to persisted evidence.

The main limitations are scope, not architecture quality: the codebase is
narrowly focused on BTC/USD daily data, has no authentication, and does not
connect to a broker.

## Folder overview

### Root

Contains governance docs, deployment docs, environment templates, Docker
composition, and GitHub Actions.

### `backend/`

Python backend, Alembic migrations, research pipeline, live API, and tests.

### `frontend/`

Next.js dashboard, reusable UI components, API client helpers, and tests.

### `.github/workflows/`

Locked-install CI for backend and frontend plus Docker build validation.

## Existing features

- Kraken live quote and OHLC ingestion
- historical backfill and candle validation
- deterministic feature engineering
- forward-log-return target generation
- expanding walk-forward validation
- baseline regression experiments
- explainability, statistical validation, residual diagnostics
- market regime analysis
- final model selection
- official holdout evaluation
- packaged Ridge inference artifact
- read-only Live Prediction API
- deterministic backtesting engine
- modular risk management
- deterministic paper trading
- immutable dashboard projections
- Docker deployment and CI

## ML pipeline summary

The research pipeline is unusually complete for a repository of this size:

- features are point-in-time safe;
- the approved target is a five-step forward log return;
- walk-forward validation uses purge/holdout controls;
- baselines include Linear, Ridge, Random Forest, and XGBoost;
- explainability includes permutation importance and TreeSHAP;
- statistical validation uses paired tests and bootstrap confidence intervals;
- residual diagnostics and market regime analysis are persisted as reports;
- a final deterministic model-selection report exists; and
- the selected Ridge model is packaged into an immutable inference artifact.

## Current strengths

- Strong reproducibility and provenance.
- Clear separation between research and read-only inference.
- Immutable report and artifact generation.
- Broad backend coverage and good test organization.
- Production-style deployment artifacts.
- Read-only dashboard that reflects persisted evidence instead of recomputing
  it.

## Current weaknesses

- The system is still narrowly centered on BTC/USD daily data.
- There is no authentication or authorization layer.
- There is no broker connectivity or live order execution.
- Some backend modules are large and harder to navigate than ideal.
- Operational observability is local-process oriented rather than platform
  oriented.

## Keep / Modify / Remove

### Keep

- Deterministic research/evidence flow.
- Immutable provenance and SHA-256 verification.
- Read-only production inference.
- PostgreSQL-backed persistence and Alembic migrations.
- Dashboard architecture and charting approach.

### Modify

- Reduce the size of the largest backend persistence/research modules.
- Add stronger end-to-end runtime coverage if the deployment surface grows.
- Remove some hardcoded BTC/USD assumptions if future expansion requires it.

### Remove

- No functional product feature should be removed from the current codebase.
- Clean up any local cache artifacts if a pristine working tree is desired.

## Immediate next engineering priorities

These are the natural next steps implied by the current repository:

1. Broaden the data model beyond BTC/USD daily evidence.
2. Reduce hardcoded single-asset assumptions across the backend and frontend.
3. Add authentication and authorization if the system is exposed to users
   outside a trusted operator group.
4. Improve external observability and monitoring.
5. Break up the largest persistence/research modules.
6. Add stronger browser-level end-to-end tests.

## Build status

- Completed: research pipeline, inference, dashboard, backtesting, risk,
  paper trading, deployment scaffolding.
- Partially complete: broader market support, auth, broker connectivity,
  external monitoring.
- Experimental: the research workflow itself, by design.
- Deprecated: none identified.
- Broken: no obvious code breakage is evident from inspection alone.

## License

No license file exists in the repository at the time of this audit.
