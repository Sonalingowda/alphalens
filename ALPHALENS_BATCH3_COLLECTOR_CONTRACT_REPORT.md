# AlphaLens Batch 3 — Collector Reliability and API Contract Integrity

Date: 2026-10-26 (IST)

Status: **Engineering changes isolated; Gate 6 and Gate 7 remain unvalidated/blocked.**

## Scope and preservation

Work was performed in the new branch/worktree:

```text
branch:  batch3-collector-contract-20261026
path:    /private/tmp/alphalens-batch3-collector-contract-20261026
base:    330670baf8c9f30ca974f8e2e0db1c93de107e06
size:    7.9M source-only checkout
disk:    16 GiB free before work
```

The original dirty checkout, historical Git refs, release reports, Docker resources, databases, collectors, datasets, and evidence were not modified. No network acquisition, launchd operation, model training, deployment, AWS operation, Docker/Colima operation, or protected-dataset access occurred.

## Workstream A — new source-manifest specification

The historical `901cda5a…` evidence was not changed or reclassified. A separate proposed manifest is defined for future review:

```text
name:       alphalens-gate7-330670-payload-v1
commit:     330670baf8c9f30ca974f8e2e0db1c93de107e06
selection:  backend/app/**
            backend/alembic/**
            backend/scripts/**
            backend/alembic.ini
            backend/pyproject.toml
            backend/uv.lock
            backend/Dockerfile
ordering:   bytewise ascending POSIX relative path
encoding:   UTF-8
record:     <sha256(file bytes)> + two ASCII spaces + <path> + LF
hash:       SHA-256 of the concatenated record stream
file_count: 312
hash:       562fd01fc755aed2dfbd1dac905b32047167b6102aa80dfa0987c0e7668f9a4d
status:     new evidence proposal; not historical Gate 7 certification
```

Reproducible verification command from the repository root:

```sh
commit=330670baf8c9f30ca974f8e2e0db1c93de107e06
git ls-tree -r --name-only "$commit" \
  | awk '$0 ~ /^backend\/(app|alembic|scripts)\// || $0 == "backend/alembic.ini" || $0 == "backend/pyproject.toml" || $0 == "backend/uv.lock" || $0 == "backend/Dockerfile"' \
  | LC_ALL=C sort \
  | while IFS= read -r path; do
      git cat-file blob "$commit:$path" | shasum -a 256 | awk -v path="$path" '{print $1 "  " path}'
    done \
  | shasum -a 256
```

Expected output begins with:

```text
562fd01fc755aed2dfbd1dac905b32047167b6102aa80dfa0987c0e7668f9a4d
```

This proposal does not explain or replace the historical 727-file `901cda5a…` record. The historical record remains unresolved because its additional file membership and original generator are unavailable.

## Workstream B — collector reliability implementation

New files in the isolated branch:

| File | SHA-256 | Purpose |
|---|---|---|
| `backend/scripts/section6_replacement_collector.py` | `b2c7526b2025fda9f3560d8a4fe4cf4668193b0e92d1fee3ebc0f4032fc9e2dc` | Separate replacement identity, validation, canonical hashing, durable raw/checkpoint store |
| `backend/tests/test_section6_replacement_collector.py` | `27970f503349f67c49a94a21e1d14284bfc5a1d0bd968f797827d8e7774001e1` | Engineering-fixture reliability tests |

Implemented behavior:

- Accepts only explicitly labeled engineering fixtures: `engineering-only-section6-replacement-v1`.
- Preserves BTCUSDT/5m, closed-candle-only semantics and development/protected boundaries.
- Rejects malformed scope, open candles, invalid OHLC, conflicting duplicates, gaps, reordering, and unsafe identifiers.
- Canonicalizes raw responses and stores them by SHA-256 under a caller-provided root.
- Writes raw response bytes before the associated checkpoint.
- Uses same-directory temporary files, flush/fsync, `os.replace`, and directory fsync for atomic writes.
- Stores sequence checkpoints and a latest pointer; recovery scans valid checkpoints when the latest pointer is corrupt or partially written.
- Verifies checkpoint hashes, replacement identity, and referenced raw-response presence during recovery.
- Does not perform network I/O, scheduling, launchd integration, acquisition, training, or protected-data access.

Historical collector-loss documentation was not modified. The replacement remains a new provenance baseline and is not presented as the original collector.

## Fixture-only test coverage

The 11 new tests cover:

1. Explicit engineering-fixture labeling.
2. Deterministic checkpoint round-trip.
3. Exact duplicate idempotency.
4. Conflicting duplicate rejection.
5. Gap/reordering rejection.
6. Open-candle and protected-boundary rejection.
7. Inclusive development-boundary behavior.
8. Checkpoint tamper detection.
9. Recovery after latest-checkpoint corruption.
10. Recovery after interrupted/partial checkpoint writes.
11. Raw-response provenance and path traversal protection.

These are engineering tests only. They are not predictive validation, historical observation recovery, or release certification.

## API contract inventory

The frontend/backend comparison found no confirmed integration defect requiring a change.

| Frontend client | Backend route | Contract result |
|---|---|---|
| `frontend/lib/api.ts:getMvpHealth` | `GET /health` | aligned: `1.0.0` envelope and `ready/degraded` payload |
| `frontend/lib/api.ts:getLiveMarket` | `GET /markets/live` | aligned: `instrument`, `timeframe`, optional `as_of` |
| `frontend/lib/api.ts:getOpportunities` / `api-client.ts:fetchOpportunities` | `GET /api/v1/opportunities` | aligned: filters, `as_of`, envelope, pagination cursor |
| `frontend/lib/api.ts:getOpportunityDetail` | `GET /api/v1/opportunities/{id}` | aligned: URL encoding and `as_of` |
| `frontend/lib/api-client.ts:confirmPaperTracking` | authenticated `GET /api/v1/paper-tracking/confirmation` | aligned: bearer token and query references |
| `frontend/lib/api-client.ts:selectPaperTracking` | authenticated `POST /api/v1/paper-tracking/selections` | aligned: bearer token, JSON body, response fields |
| `frontend/lib/api.ts:getDashboardBundle` | `GET /api/v1/dashboard`, `/health`, `/model`, `/metrics`, `/resources` | aligned with the prediction API response models |

Existing frontend integration tests exercise the opportunity, market, detail, health, timeout, partial-detail, pagination/filtering, and refresh behaviors. No speculative contract change was made.

## Ruff F811 review

The finding is in `backend/scripts/run_memory_pipeline.py:278`: `ScopedRepositoryQuery` is imported at line 15 and redundantly imported again inside the function. It has no identified functional impact; the script is a local diagnostic harness, and removing it would be cosmetic cleanup. It was intentionally deferred.

The scripts scope remains at 82 findings: E402=51, F401=11, F541=13, F811=1, F841=6. `ruff check app tests` passes, and the collector implementation plus its tests pass Ruff.

## Verification commands and results

```text
df -h /
16 GiB available before work

pytest -q -rs -p no:cacheprovider --disable-warnings
916 passed, 23 skipped, 2 warnings, 497 subtests passed

pytest ... tests/test_section6_replacement_collector.py
11 passed

ruff check app tests
PASS

ruff check scripts
FAIL: 82 pre-existing diagnostic-script findings

ruff check scripts/section6_replacement_collector.py tests/test_section6_replacement_collector.py
PASS

Node 22.23.3:
npm run lint
PASS
npm run typecheck
PASS
npm test -- --run
7 files, 31 tests passed
```

The frontend source tree was verified unchanged between `330670…` and the existing Node 22 dependency checkout used for these tests. The Batch 1 baseline was therefore preserved for frontend verification.

Backend changed from Batch 1 only by the 11 new collector tests, so the result increased from 905 to 916 passed with the same 23 skips. No skipped test was counted as passed.

## Change inventory

- Added replacement collector filesystem reliability implementation in the isolated branch.
- Added 11 fixture-only reliability tests in the isolated branch.
- Added this report in the isolated branch.
- Frontend source: unchanged.
- Backend application/API routes: unchanged.
- Historical reports, collector-loss records, source refs, datasets, Docker resources and evidence: unchanged.
- Original dirty checkout: unchanged.

## Unresolved risks and blockers

1. The historical collector implementation and continuity evidence remain unavailable.
2. The new filesystem store has no live transport, scheduler, launchd integration, or production deployment review.
3. The proposed 312-file source manifest requires explicit approval and is not a historical Gate 7 manifest.
4. The historical 727-file `901cda5a…` manifest remains unresolved.
5. PostgreSQL/transfer-fixture tests remain skipped under the approved no-service boundary.
6. Docker image build, immutable digest, extraction, and source-byte parity remain blocked.
7. Full scripts Ruff remains failing with the existing 82 findings.

## Proposed Batch 4 — approval required

1. Review and approve or reject the new manifest specification without changing historical evidence.
2. Review the filesystem store API for a separately authorized offline validation protocol.
3. If desired, approve narrowly scoped F841/F811 diagnostic-script cleanup with focused non-live tests.
4. Arrange isolated disposable PostgreSQL/transfer fixtures for the skipped backend tests.
5. Obtain separate build capacity before any exact-source image build, digest capture, or Gate 7 evidence generation.

Final status: **Gate 6 NOT VALIDATED · Gate 7 BLOCKED · AWS deployment NOT AUTHORIZED.**
