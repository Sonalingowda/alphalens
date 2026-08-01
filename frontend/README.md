# AlphaLens Dashboard

AlphaLens Dashboard v1.0.0 is a read-only market-surveillance interface for the
MVP API. It displays immutable live market snapshots and ranked opportunity
projections with their evidence-backed detail. It contains no indicator,
scoring, detection, confidence, ranking, or trading-decision logic.

## Requirements

- Node.js 22.13 or newer
- A running AlphaLens MVP API

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

- Market Surveillance Dashboard
- Opportunity Detail
- Live Market Status

Missing snapshots, opportunities, explanation text, or API evidence are shown
as unavailable and are never replaced with fabricated values. Charts render
only OHLC observations returned by the API.

## Verification

```shell
npm run typecheck
npm test
npm run build
```

Component tests cover opportunity cards, market status, and explicit unavailable
states. API integration tests verify all four versioned read-only MVP endpoints.
