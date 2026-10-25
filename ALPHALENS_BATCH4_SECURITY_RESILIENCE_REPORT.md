# AlphaLens Batch 4 — Security, Resilience and Operational Readiness

Date: 2026-10-26 (IST)

Status: **Local security/resilience repair completed in isolation; service-integrated evidence and Gate 6/7 remain incomplete.**

## 1. Isolation and baseline

Disk was checked before creating the worktree: 16 GiB available on a 228 GiB filesystem.

Batch 4 worktree:

```text
path:       /private/tmp/alphalens-batch4-security-resilience-20261026
branch:     batch4-security-resilience-20261026
Batch 3 HEAD: 46faceb58cde1429702c6179102aa72760098433
Batch 3 tree: b54abab444449d6e6748863c3adcfac3b9007820
```

The Batch 3 isolated changes were first anchored in commit `46faceb…`; the Batch 4 source changes remain uncommitted in the new engineering worktree. The original dirty checkout, historical release refs, Docker/Colima resources, databases, datasets, collectors, and evidence were not modified.

## 2. Confirmed repair: collector raw-file integrity and symlink safety

Batch 3 recovery accepted any existing raw-response path without re-hashing its contents. It also resolved candidate paths before rejecting symlink targets, allowing a symlinked raw path to be read during recovery. These were confirmed local integrity/path-safety gaps.

Changes in `backend/scripts/section6_replacement_collector.py`:

- Reject symlinked storage paths before resolution.
- Require checkpoint and raw-response files to be regular, non-symlink files.
- Recompute each referenced raw-response SHA-256 during recovery.
- Reject a checkpoint when any referenced raw response is missing, symlinked, non-regular, or content-mismatched; recovery falls back to the newest complete prior checkpoint.

New tests in `backend/tests/test_section6_replacement_collector.py`:

- Tampered raw bytes cause recovery to select the prior valid checkpoint.
- Symlinked raw paths fail closed.

Current file hashes:

```text
backend/scripts/section6_replacement_collector.py
e2bb4f5dde378ba8aed00d138c0467ed0f682f004cd8f71eadee8d334d0365db

backend/tests/test_section6_replacement_collector.py
512cbf94ccdeaa384c9805519bd1449dd0492a3e3fa46f80bf4c5c9947ac1c97
```

The implementation remains filesystem-only, fixture-only, and separate from the lost historical collector. No network, scheduler, launchd, acquisition, training, or protected data path was added.

## 3. Clerk authentication audit

Verified locally by source inspection, SDK introspection, and existing fail-closed tests:

- Missing secret key or configured authorized user returns `503` and does not proceed.
- Missing, malformed, invalid, or expired authentication state is rejected with `401`.
- The Clerk SDK is called with `accepts_token=["session_token"]` and configured `authorized_parties`.
- The SDK’s `authenticate_request` path performs signed-token verification through its verifier; expiration and issuer validation are delegated to that verifier.
- The authenticated actor is derived from the verified `sub` claim, never from a client-supplied actor field.
- A valid but different user is rejected with `403`.
- Paper-tracking selection uses the verified actor identity and object references are resolved by the selection service.

Confirmed configuration limitation:

- `AuthenticateRequestOptions.audience` is not configured. The Clerk SDK option supports audience verification, but the correct audience is deployment-specific and no approved topology/value is recorded. No audience value was invented or added.
- The current authorization model is a single configured development user, not a general tenant-isolation policy. Multi-tenant isolation is therefore not established.
- With a secret key and no local JWT key, SDK verification may retrieve JWKS externally. No live Clerk verification was attempted in this batch.

Existing tests in `backend/tests/test_clerk_paper_tracking.py` cover missing credentials, invalid/expired/malformed states, unauthorized users, verified-sub identity, and rejection of client actor injection. These are mocked SDK-boundary tests, not live Clerk integration evidence.

## 4. Redis rate limiting and proxy identity

Verified implementation and tests:

- Redis uses one Lua script for `INCR`, first-use `EXPIRE`, and `TTL`, preserving atomic counter/window setup.
- Redis errors raise `RateLimitUnavailable`; the API fails closed with structured `503` behavior.
- Exceeded requests return structured `429` responses with `Retry-After` derived from Redis TTL; tests pass.
- Local limiter operations are lock-protected and bounded by `max_keys`.

Unresolved deployment-topology issue:

- The limiter key is `request.client.host`.
- `X-Forwarded-For` and similar headers are ignored, so behind a reverse proxy multiple users may share the proxy address.
- No forwarded-header trust policy was implemented because the deployment topology and trusted proxy set are not approved. This is a documented operational risk, not a locally reproducible correctness defect.

## 5. Background jobs, failure handling and readiness

Existing fixture/mocked tests and source review confirm:

- Warmup retries are bounded and back off after transient failures.
- Ingestion supervision uses bounded exponential restart delays and supports a restart limit.
- `CancelledError` propagates instead of causing restart loops.
- Shutdown sets the stop event, cancels supervisor tasks, and awaits cancellation.
- Lifecycle sweep and outcome-resolution failures are logged without terminating the service loop.
- Readiness is served while warmup is in progress and reports dependency failures as unavailable rather than ready.
- Redis/PostgreSQL readiness failures are fail-closed.

No live service, database, Redis, WebSocket, or launchd integration was run.

## 6. Configuration, secrets, logging and error responses

Verified local safeguards:

- Direct secret and secret-file forms cannot both be set.
- Empty secret files fail closed.
- Production rejects placeholder database/Redis passwords.
- CORS rejects wildcard origins and duplicate origins.
- Structured exception responses expose error codes/messages, not credentials or connection URLs.
- Request/correlation IDs are validated and emitted through response headers.
- Readiness and liveness are separate; readiness returns `503` when checks fail.
- Build provenance is surfaced as metadata and unreadable provenance fails configuration.

No evidence was found that passwords, bearer tokens, or secret URLs are intentionally logged. A production log review still requires deployment-specific log sink/configuration evidence.

## 7. Dependency checks

Executed without network access or lockfile changes:

```text
python -m pip check
No broken requirements found.

npm audit --offline --json
0 vulnerabilities reported across 803 installed dependency entries.

SHA-256 backend/uv.lock
a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959

SHA-256 frontend/package-lock.json
02119c5e622dadf029ee6cfd6ba1f0a8d2f09079abfedc2fe0b1c97944a03a24
```

`pip-audit` is installed in the existing virtual environment, but it requires a vulnerability advisory service/database and has no demonstrated offline advisory cache here. It was not run against the network. Therefore Python vulnerability status is **unverified**, not clean. No lockfile was altered to silence findings.

## 8. Test and quality results

Exact commands used:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/private/tmp/alphalens-batch4-security-resilience-20261026/backend \
  /private/tmp/alphalens-local-release-candidate-20261024/backend/.venv/bin/pytest \
  -q -rs -p no:cacheprovider --disable-warnings
918 passed, 23 skipped, 2 warnings, 497 subtests passed

ruff check app tests
PASS

ruff check scripts/section6_replacement_collector.py tests/test_section6_replacement_collector.py
PASS

ruff check scripts
FAIL: 82 existing diagnostic-script findings

Node 22.23.3:
npm run lint
PASS
npm run typecheck
PASS
npm test -- --run
7 files, 31 tests passed
```

The 23 backend skips remain the same PostgreSQL/transfer-fixture skips from Batch 1. The backend total increased from 916 to 918 because of the two new collector integrity tests. Frontend remains at 31 tests; its source tree is unchanged from the Node 22-tested checkout.

## 9. Change inventory

- Modified: `backend/scripts/section6_replacement_collector.py`.
- Modified: `backend/tests/test_section6_replacement_collector.py`.
- Added: this report.
- No frontend, API route, authentication, rate-limit, configuration, migration, Docker, database, AWS, collector-launch, dataset, or historical-evidence changes.
- No application/tests Ruff findings were introduced.

## 10. Remaining risks and blockers

1. Clerk audience and deployment issuer/topology policy are not explicitly frozen; live Clerk verification remains untested.
2. Multi-tenant isolation is not established; current paper tracking is restricted to one configured user.
3. Reverse-proxy client identity and trusted forwarded-header policy remain deployment-dependent.
4. Python vulnerability advisories are unverified because offline advisory data is unavailable.
5. PostgreSQL/Redis real-service behavior and production log sink behavior remain unverified locally.
6. Historical collector continuity remains unavailable; the replacement has a new provenance baseline.
7. Historical Gate 7 manifest `901cda5a…` remains unresolved; image build/digest/parity remain blocked.

## Proposed Batch 5 — approval required

1. Approve the Clerk deployment topology, issuer/audience values, and whether the authorization model is single-user or tenant-scoped.
2. Add a documented trusted-proxy policy only after topology approval, then test direct, proxied, multi-client, and spoofed-header cases.
3. Run Python dependency vulnerability scanning on an approved isolated host with an approved advisory service or preserved database snapshot.
4. Validate Redis/PostgreSQL failure and readiness behavior against disposable services without touching protected databases.
5. Review production log sink/redaction evidence and exact exception payloads.
6. Continue separate build-capacity and manifest reconciliation work; do not certify Gate 6 or Gate 7 from these offline results.

Final status: **Gate 6 NOT VALIDATED · Gate 7 BLOCKED · AWS deployment NOT AUTHORIZED.**
