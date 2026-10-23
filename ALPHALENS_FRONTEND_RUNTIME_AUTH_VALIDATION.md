# AlphaLens Frontend Runtime and Clerk Validation

Status: PARTIAL. The candidate build and unauthenticated localhost rendering
are verified. Real interactive Clerk authentication and browser-only checks are
not certified because no browser executable or authenticated development
session is available in this environment.

## Candidate identity

- Worktree: `/private/tmp/alphalens-local-release-candidate-20261024`
- Branch before this report commit: `release/local-candidate-20261024`
- Base candidate commit: `d95e9967f828a01aee6c16c3797000b4dc07a426`
- Original dirty repository and its research evidence were not modified.
- The Section 6 collector and existing demo services were not touched.

## Confirmed runtime fix

`frontend/next.config.ts:7-12` enables `output: "standalone"`, while the
previous `frontend/package.json:11` used `next start`, which Next.js rejects for
standalone output. The candidate now uses `scripts/start-standalone.mjs`.
That launcher copies `.next/static` into the standalone runtime tree before
starting the server, matching the Dockerfile's runtime layout.

```text
node scripts/start-standalone.mjs
```

The Dockerfile already used the equivalent `node server.js` entrypoint
(`frontend/Dockerfile:23-29`). Local standalone startup was verified with:

```text
HOSTNAME=localhost PORT=13100 npm start
```

The root request returned HTTP 200. Binding the Clerk-enabled server only to
`127.0.0.1` reproduced a self-request timeout; binding to `localhost` returned
HTTP 200 and is now the documented local command. No middleware bypass was
added. `frontend/proxy.ts:1-11` remains the standard Clerk middleware matcher
with no custom proxy or self-request rewrite.

## Build and static verification

Executed under Node `v22.23.3` and npm `10.9.9`:

- `npm run build` — PASS; standalone output generated and all 12 routes built.
- `npm run typecheck` — PASS.
- `npm run lint` — PASS.
- `npm test -- --run` — PASS, 7 files and 31 tests.
- `npm audit --omit=dev --audit-level=high` — FAIL / release blocker: 14
  advisories (4 moderate, 8 high, 2 critical), including current Next.js and
  `proxy-addr` advisories. No forced upgrade or blanket suppression was made.
- Bundle scan found no `sk_test_` or `sk_live_` secret-key literals. Public
  Clerk publishable-key references are expected in the browser bundle.

## Real browser smoke evidence

Using disposable Chromium 134 outside the repository against the isolated
localhost services:

- Root page title: `AlphaLens`.
- Root heading: `Market surveillance`.
- Truthful `Unavailable` state present.
- Signed-out `Sign in` button present.
- Mobile `Open menu` opened the navigation successfully.
- `/markets/live` rendered `Live Market Status · AlphaLens` and its unavailable
  state.
- Sign-in button opened the Clerk development modal and displayed the email
  authentication UI.
- Browser console errors: none.
- Static JS, CSS, font, and image requests: no failed resource requests after
  the standalone launcher copied static assets.

## Local HTTP evidence

The isolated backend was run on `127.0.0.1:18100` with startup market-data
acquisition disabled and the isolated PostgreSQL/Redis services. The frontend
was run on `localhost:13100` and queried through `127.0.0.1:13100`.

- `/` — HTTP 200; dashboard HTML rendered.
- `/markets/live` — HTTP 200; unavailable/empty market state rendered.
- `/opportunities/unknown` — HTTP 200; route rendered without fabricated data.
- `/system-health` — HTTP 200; route rendered.
- Root HTML contained `Market surveillance`, `Opportunities`, and repeated
  `Unavailable`/`API unavailable` states. No market candle, prediction, or
  performance statistic was fabricated.
- Backend `/health/readiness` — HTTP 200.
- Backend `/health` — HTTP 503 `ARTIFACT_UNAVAILABLE`, preserved as a truthful
  fail-closed state.
- Backend `/markets/live` — empty/unavailable snapshot.
- Backend `/api/v1/opportunities` — HTTP 404 `entity.not_found` for the empty
  isolated database; no rows were added. The frontend treats this non-success
  response as an unavailable state rather than inventing an empty result.
- The isolated verification used the Compose-defined database/user and Redis
  credentials from `/private/tmp/alphalens-ops-20261024/compose.yml`; no
  existing demo database or volume was used.

## Clerk contract review

- `frontend/layout.tsx:29-38` uses `ClerkProvider` and does not expose a secret.
- `frontend/.env.example:3-4` requires
  `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.
- Backend `app/paper_execution/auth.py:31-72` verifies Clerk sessions through
  the SDK, authorized parties, and the configured authorized user; failures are
  401/403/503 as appropriate.
- The local operator configuration was inspected by variable name and prefix
  only. The frontend development key is `pk_test_`; the backend secret is
  `sk_test_`. A separate ignored backend environment also contains a
  `pk_live_`-prefixed frontend-named variable; it was not used or copied. The
  candidate documentation explicitly prohibits mixing test and live keys.
- Required development origins are documented as
  `http://127.0.0.1:13100` and `http://localhost:13100`; the backend CORS and
  Clerk authorized-party settings must use the exact origin selected for the
  browser session.

## Authentication status

The following remain UNVERIFIED, not passed:

- real browser sign-in and sign-out;
- session creation, refresh, and expiry;
- authenticated browser API calls and browser CORS;
- expired/malformed JWT rejection through a real browser/API path;
- issuer, audience, and signature verification with a real Clerk token;
- protected-route redirects;
- responsive browser navigation and end-to-end opportunity detail flow.

Raw `curl` requests without Clerk development-browser state returned Clerk
signed-out/dev-browser-missing headers. This is not evidence of a successful
login and was not treated as one. No credentials were printed or invented.

## Checklist classification

PASS: middleware comparison completed; standalone startup fixed; root and
related routes return stable HTTP 200 on the supported local binding; build,
typecheck, lint, and 31 frontend tests pass; unavailable states are truthful;
no secret-key literals are present in the browser bundle; no custom circular
proxy was found.

PARTIAL: frontend-to-backend unauthenticated rendering and truthful empty /
unavailable behavior are verified; API contracts are covered by mocked tests
and isolated HTTP checks, but browser-authenticated behavior is not.

BLOCKED: interactive Clerk authentication, authenticated browser CORS/API
requests, JWT negative cases with real tokens, genuine market-data display,
non-empty opportunity listing/detail, and browser responsive smoke tests.

FAIL / RELEASE BLOCKER: current production dependency audit reports 14
high-or-critical-inclusive advisories. The candidate was not force-upgraded
without compatibility review.

## Required next evidence

Use a real browser with an authorized Clerk development user and the matching
`pk_test_`/`sk_test_` instance. Capture sign-in, sign-out, session refresh,
expiry, protected API allow/deny, malformed/expired token rejection, browser
CORS, navigation, and unavailable-state screenshots or network evidence. Before
release, resolve or formally review the current frontend production audit
findings and rerun the complete frontend verification set.

This document does not certify Section 6, Gate 7, or production readiness.
