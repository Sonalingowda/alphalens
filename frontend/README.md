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
NEXT_PUBLIC_ALPHALENS_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_<development-publishable-key>
```

`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` must belong to the same Clerk development
instance configured for the backend. It is intentionally browser-visible; do
not place a Clerk secret key (`sk_...`) in frontend files, browser-exposed
variables, or the frontend image.

The backend must be configured separately with `ALPHALENS_CLERK_SECRET_KEY`,
`ALPHALENS_CLERK_AUTHORIZED_PARTIES`, and
`ALPHALENS_CLERK_AUTHORIZED_USER_ID`. The authorized parties must contain the
exact browser origin used for the frontend, such as
`http://127.0.0.1:13000` and `http://localhost:13000`, and backend CORS must
allow that same origin. Never mix `pk_test_...` with `sk_live_...` or
`pk_live_...` with `sk_test_...`.

For the standalone production build, use the repository's supported launcher:

```shell
npm run build
HOSTNAME=localhost PORT=3000 npm start
```

This prepares the standalone static assets and invokes
`.next/standalone/server.js`; the Docker image performs the equivalent static
asset copy in its build stages and uses `node server.js` as the entrypoint.
Using `localhost` is intentional for local Clerk
development: the Clerk development-browser middleware may issue same-origin
requests through `localhost`, so binding only to the IPv4 literal
`127.0.0.1` can produce a self-request timeout. `localhost` still serves the
local loopback interface and must not be exposed through a public bind in
development. A raw `curl` request is not a Clerk browser-login test: Clerk
development middleware may require its browser session state before an
authenticated page can render.

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
