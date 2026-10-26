# AlphaLens Public Product Readiness Backlog

Date: 2026-10-26  
Scope: Binance BTCUSDT, closed 5-minute candles only  
Baseline: `948913a7e2df47b785bef655deaa4843c7589bcf`  
Tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`

## Status summary

The repository contains a substantial product surface and a contract-tested
opportunity lifecycle, but it is not presently a verified public-use,
end-to-end BTCUSDT intelligence service.

- The frontend is implemented and has truthful unavailable, empty, timeout,
  and partial-detail states.
- Read-only opportunity and market APIs are implemented around persisted
  artifacts.
- Historical isolated replays verified genuine BTCUSDT Detection and
  pre-scoring lifecycle stages; this is not current live-service evidence.
- The new `btcusdt_5m_expected_move_ridge` contract is implemented as a
  fail-closed contract boundary only. No fitted or approved runtime artifact
  exists.
- The current scoring service remains bound to the separate approved daily
  Ridge contract and therefore cannot certify BTCUSDT/5m model scoring.
- Continuous Binance ingestion, durable production persistence, restart
  recovery, external notifications, deployment provenance, and public
  operational readiness remain unverified or blocked.

Gate 6 remains NOT VALIDATED. Gate 7 remains BLOCKED. No public launch is
authorized.

## Current verified user journey

The following is the implemented product path, subject to persisted backend
state and service availability:

1. The Next.js shell loads through `frontend/app/layout.tsx`, which wraps the
   application in `ClerkProvider`; `frontend/components/app-shell.tsx`
   exposes sign-in/user controls.
2. The dashboard at `frontend/app/page.tsx` requests health, live market data,
   and opportunities. The default product scope is BTCUSDT/5m.
3. `frontend/lib/api.ts` calls `/health`, `/markets/live`, and
   `/api/v1/opportunities` with bounded request timeouts and envelope/error
   handling.
4. `backend/app/opportunity_intelligence/api.py` reads persisted dashboard
   projections, applies scope/filter/cursor rules, and exposes opportunity
   detail and history endpoints.
5. `frontend/app/opportunities/[id]/page.tsx` renders persisted lifecycle,
   freshness, evidence cutoff, confidence availability, score reference,
   market snapshot, plan, and provenance fields. Missing detail is rendered
   as an unavailable state rather than fabricated data.
6. `frontend/components/opportunities/paper-track-control.tsx` forwards a
   Clerk bearer token for the paper-tracking selection path. This is manual
   paper tracking, not trading or an external order path.
7. `backend/app/runtime_notification/service.py` can create immutable
   notification intents from persisted ranking, opportunity, and lifecycle
   artifacts. The inspected service is an intent/persistence stage; it does
   not by itself prove browser push, email, messaging, worker delivery, or
   delivery confirmation.

This journey is implemented in code, but a complete live BTCUSDT journey is
not verified because the required runtime infrastructure, approved artifact,
and live operational execution evidence are absent.

## P0 — public-launch blockers

### P0.1 — No approved BTCUSDT/5m runtime model artifact

Status: BLOCKED by research and approval, not a code defect.

Evidence:

- `backend/app/inference/btcusdt_5m_contract.py` defines the approved
  contract namespace, five-feature schema, schema hash, target hash, and
  fail-closed provenance checks; it does not contain model state or a
  prediction implementation.
- `backend/app/runtime_scoring/service.py:91-107` remains bound to the
  separate daily Ridge feature list and artifact identity.
- `backend/app/startup.py` and the production health path require a verified
  artifact before reporting production readiness.
- Batch 6J and Batch 6P evidence record that no approved BTCUSDT/5m artifact
  exists.

Required repair: complete the owner-approved Batch 6O research protocol,
including independent validation and artifact approval. Do not display a
numeric BTCUSDT/5m model score or call it confidence before that point.

Acceptance tests:

- Artifact identity, contract version, schema hash, target hash, lineage,
  payload/state hashes, and explicit approval status all match.
- Missing, unapproved, or mismatched artifacts fail closed.
- A genuine candle-to-inference trace is retained with no future leakage.
- Direction remains supplied by Detection; magnitude is not presented as a
  win probability, signed return, or profit.

Dependency: Batch 6O research execution, independent review, Gate 6 approval,
then a separately authorized runtime integration.

### P0.2 — Continuous genuine BTCUSDT ingestion and durable runtime execution

Status: PARTIAL / UNVERIFIED for public operation.

Evidence:

- `backend/scripts/run_live_ingestion_pipeline.py` and
  `backend/app/live_market_data/` provide a live-ingestion path, but invoking
  it would use Binance network access and was not performed in this batch.
- `backend/scripts/trace_live_5m_pipeline.py` and the Batch 6G–6I reports
  establish bounded historical execution evidence, not 24/7 operation.
- The product APIs read persisted repositories, but no current public-run
  receipt proves continuous ingestion, restart recovery, or bounded lag.

Required repair: authorize a controlled BTCUSDT-only runtime trial with
closed-candle enforcement, immutable raw/canonical lineage, gap and duplicate
handling, restart recovery, bounded persistence, and read-only observability.

Acceptance tests:

- Only closed Binance BTCUSDT/5m candles are accepted.
- Every accepted candle has source receipt, UTC timestamp, availability
  cutoff, hash, and persistence identity.
- Restart resumes without duplicate lifecycle events or silent gaps.
- Stale, unavailable, malformed, or out-of-order input produces a truthful
  unavailable/error state.

Dependency: separate owner authorization for Binance access, isolated
PostgreSQL/Redis runtime, and operational review.

### P0.3 — Gate 7 image, artifact, migration, and recovery provenance

Status: BLOCKED / UNVERIFIED.

Evidence:

- `backend/Dockerfile:36` checks `/health/readiness`; `docker-compose.yml:69`
  uses the same readiness probe.
- `backend/app/startup.py` verifies database, Redis, schema, and artifact
  readiness, but this repository state has no newly certified exact-source
  image digest and no approved BTCUSDT/5m artifact.
- Existing Batch 6P readiness reports identify Docker/image and protected
  infrastructure verification as prerequisites, not completed evidence.

Required repair: perform the separately authorized exact-source build and
Gate 7 certification after capacity and artifact prerequisites are satisfied.

Acceptance tests:

- Immutable source commit/tree, image digest, manifest, and extracted source
  bytes agree.
- Disposable database migration head and Redis identity are verified.
- Readiness fails closed when schema, Redis, or artifact checks fail.
- Backup, restart, and recovery evidence is retained without touching
  protected resources.

Dependency: isolated build infrastructure, approved artifact, and Gate 7
execution authorization.

## P1 — high-priority engineering gaps

### P1.1 — Authentication and ownership policy for read APIs

Status: PARTIAL / POLICY REQUIRES CONFIRMATION.

Evidence:

- `frontend/lib/api-client.ts:37-54` attaches Clerk bearer tokens for the
  paper-tracking calls.
- `backend/app/opportunity_intelligence/api.py:57-220` exposes opportunity
  list/detail/history and market reads through repository-backed routes; the
  inspected route functions do not establish a user or organization scope.
- `frontend/lib/api.ts` calls read APIs without a Clerk token.
- `backend/app/settings.py:44-45` contains Clerk-related configuration, but
  the required product tenancy model is not established by these routes.

Required repair: explicitly decide whether public read access is intended or
whether all reads require authenticated user/organization scope. If scoped,
add object-level authorization and negative cross-user/cross-organization
tests. Do not infer multi-tenancy from the presence of Clerk.

Acceptance tests: missing, invalid, expired, wrong-tenant, and cross-object
requests fail closed; intended public read behavior is documented and
tested if it remains the decision.

Dependency: owner product/security decision and documented deployment
topology.

### P1.2 — Frontend/backend live-contract evidence

Status: IMPLEMENTED BUT UNVERIFIED against a real running service.

Evidence:

- `frontend/app/page.tsx` loads market/opportunity data and records partial
  detail failures.
- `frontend/components/opportunities/opportunity-feed.tsx` preserves
  persisted summaries and asks the user to retry missing detail; empty states
  explicitly avoid placeholder signals.
- `frontend/app/opportunities/[id]/page.tsx` renders plan and provenance data,
  but the current score/confidence fields can be unavailable.

Required repair: execute an authorized isolated browser-to-backend test with
one genuine persisted BTCUSDT candidate and one artifact-unavailable case.

Acceptance tests: authenticated session behavior, timeout recovery, partial
detail recovery, pagination/filtering/refresh, stale data, empty data, and
truthful artifact-unavailable health response are captured with request and
response evidence.

Dependency: isolated PostgreSQL/Redis and genuine persisted data; no mock
success may be reported as production evidence.

### P1.3 — Notification delivery is only an intent/persistence stage

Status: PARTIAL.

Evidence:

- `backend/app/runtime_notification/service.py` creates one immutable,
  deduplicated Notification intent per persisted ranking member and fails
  closed when required artifacts are missing or inconsistent.
- The service does not establish a browser-push, email, messaging, worker,
  retry, delivery receipt, expiry, or missed-event recovery path.
- `backend/scripts/run_live_ingestion_pipeline.py` wires the in-process
  service for pipeline tracing, which is not evidence of external delivery.

Required repair: define an in-app delivery/read API first, then separately
review external channels. Add eligibility, expiry, retry/backoff,
deduplication, delivery confirmation, outage recovery, and user authorization.

Acceptance tests: duplicate event suppression, expired event suppression,
restart replay behavior, channel failure/retry, and no external send in test
mode.

Dependency: approved artifact/ranking path, notification policy, persistent
queue/worker choice, and authenticated user model.

### P1.4 — Reverse-proxy client identity is unresolved

Status: CONFIRMED DESIGN GAP; not yet a demonstrated exploit.

Evidence: `backend/app/api/application.py:230-232` rate-limits
`request.client.host`. No trusted-proxy topology or forwarded-header policy
was established in the inspected configuration.

Required repair: document whether the service is directly exposed or behind a
known proxy. Then either retain proxy-level identity intentionally or add a
reviewed trusted-forwarded-header policy with spoofing protection.

Acceptance tests: direct clients, multiple clients through one proxy,
spoofed forwarded headers, Redis outage, local fallback policy, and
`Retry-After` behavior.

Dependency: deployment topology; do not implement header trust speculatively.

### P1.5 — Lifecycle outcome and economic evidence are incomplete

Status: PARTIAL / UNVERIFIED.

Evidence:

- `backend/app/outcome_resolution/service.py` and
  `backend/app/paper_execution/` provide lifecycle/paper-tracking components.
- The inspected public path does not prove fees, spread, slippage, latency,
  drawdown, losing-signal accounting, or complete outcome persistence under a
  real service.
- Frontend paper tracking is explicitly manual and must not be represented as
  execution or profitability evidence.

Required repair: run an authorized paper-observation protocol with explicit
market-cost assumptions and immutable outcome lineage.

Acceptance tests: wins, losses, expiry, invalidation, duplicate event,
restart recovery, fees/slippage/latency fields, and drawdown reporting.

Dependency: approved runtime artifact for model-dependent results, isolated
runtime services, and separate economic-evaluation authorization.

## P2 — important quality and launch-hardening work

### P2.1 — Unavailable confidence and score semantics need product-wide labels

Status: PARTIAL.

Evidence: `frontend/app/opportunities/[id]/page.tsx:120-141` correctly renders
“Unavailable” when confidence or expected-move output is absent, but the
public product must keep this distinction consistent across list, detail,
predictions, and notification views.

Acceptance tests: no artifact means no numeric model score; any displayed
quantity identifies whether it is a detector value, model magnitude, ordinal
quality score, or calibrated probability. Calibrated confidence remains
unavailable until independently demonstrated.

### P2.2 — Operational monitoring and user-facing recovery evidence

Status: IMPLEMENTED IN PART / UNVERIFIED.

Evidence: `backend/app/infrastructure/observability.py` supplies liveness,
readiness, and metrics surfaces; `backend/app/api/application.py` returns
structured rate-limit and artifact errors. No public-run evidence proves
alerting, log retention, missed-event monitoring, or operator runbooks.

Acceptance tests: readiness transitions for DB/Redis/artifact failure,
structured secret-redacted logs, stale-data alarms, ingestion lag, and
recovery after restart.

### P2.3 — Public documentation must describe the actual boundary

Status: REQUIRED.

Acceptance tests: documentation states BTCUSDT/5m scope, manual trading only,
no approved model until Gate 6, no automatic orders, data freshness, failure
states, and the difference between historical replay evidence and live
operation.

## Smallest next implementation batch before model approval

Implement one isolated, contract-neutral “public runtime truthfulness” batch:

1. Add explicit product-status metadata to health and opportunity responses:
   `market_scope=Binance BTCUSDT/5m`, `data_status`, `artifact_status`,
   `model_score_status`, and `notification_status`, without inventing values.
2. Add/verify read-only API contract tests for empty, stale, unavailable,
   partial-detail, pagination, filter, and artifact-unavailable responses.
3. Add frontend tests for the same states, including no numeric confidence or
   model score when the artifact is unavailable.
4. Document the authentication/ownership decision and test the selected
   policy; do not broaden to multi-tenant architecture without evidence.
5. Add notification-intent inspection/read semantics only if they use existing
   persisted contracts; do not add external delivery.
6. Add rate-limit topology documentation and tests without trusting forwarded
   headers until deployment topology is approved.

This batch can proceed without fitting, protected data, live acquisition,
Docker, AWS, scoring activation, notifications, or deployment. It must use
isolated test adapters only and must not present fixtures as live market
intelligence.

## Explicitly blocked until later authorization

- Binance acquisition or 24/7 ingestion.
- Fitting, tuning, protected-test evaluation, Gate 6 approval.
- BTCUSDT/5m artifact packaging, activation, or promotion.
- Live scoring/ranking and external notifications.
- Exact-source image certification and Gate 7.
- Public deployment, trading, or automatic order execution.

## Evidence and preservation

No source, database, dataset, Docker resource, cloud resource, historical
evidence, or original dirty checkout was modified for this backlog. The
accepted Batch 6P reports remain separate evidence and retain these hashes:

| Report | SHA-256 |
|---|---|
| `ALPHALENS_BATCH6P_OPERATIONAL_READINESS_REPORT.md` | `0d31e0cc46d22054ab2ad75f8665dae36610963ca2898c4b430b09d48005e5f5` |
| `ALPHALENS_BATCH6P_RESEARCH_EXECUTION_APPROVAL_MATRIX.md` | `328a5e5b9ad5c0a9cf5929bedf451c6b9cb12bce1a13a83978c81140c94a7b12` |
| `ALPHALENS_BATCH6P_ISOLATED_ENVIRONMENT_PLAN.md` | `9fe97441ce6147f1131441db225236d1639124a1d058413ac70eac01c5071482` |
| `ALPHALENS_BATCH6P_DATA_ACQUISITION_AND_LINEAGE_PLAN.md` | `f3ad5acaeae99aea1c099f2dc39afd5d86b5bab4297a2bc3d07bfde90b7d7104` |

Contract checks already recorded for this isolated baseline: six focused
BTCUSDT contract tests passed; full backend evidence is 924 passed, 23
skipped, 497 subtests, with Ruff passing. These are engineering checks, not
predictive validation or deployment evidence.

