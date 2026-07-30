# AlphaLens Dashboard

AlphaLens Dashboard v1.0.0 is a read-only operational interface for the Live
Prediction API. It displays verified prediction, paper-trading, portfolio,
risk, backtest, and system evidence. It contains no machine-learning,
prediction, trading, or risk-decision logic.

## Requirements

- Node.js 20.9 or newer
- A running AlphaLens Live Prediction API

## Configuration

Copy `.env.example` to `.env.local` and set:

```shell
ALPHALENS_API_BASE_URL=http://127.0.0.1:8000
```

This server-side variable identifies the API consumed by Next.js. It is the
only frontend environment variable.

## Local development

```shell
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. The API runs separately on port `8000`.

## Pages

- Dashboard
- Predictions
- Paper Trading
- Portfolio
- Trade History
- Risk Events
- Backtest Reports
- System Health
- Settings

Settings are inspection-only. Missing API or report evidence is shown as
unavailable and is never replaced with fabricated values.

## Verification

```shell
npm run typecheck
npm test
npm run build
```

Component tests cover shared dashboard states and signal presentation. API
integration tests verify the dashboard's versioned read-only API contract.
