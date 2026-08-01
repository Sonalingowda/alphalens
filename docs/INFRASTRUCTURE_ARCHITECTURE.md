# AlphaLens Infrastructure Architecture

## Runtime topology

```text
Browser -> Frontend -> Backend API -> Repository interfaces -> PostgreSQL
                           |                     |
                           +-> Redis coordination+
                           +-> Prometheus metrics

Scheduler -> Redis task references -> Worker
```

PostgreSQL is the sole source of truth. Immutable aggregate records store canonical serialized domain payloads, hashes, version identity, scope, provenance-bearing content, and append-only history. Database triggers reject updates and deletes. Policy artifacts use a separate append-only binary table whose declared and computed hashes must agree.

Redis stores only expiring cache values, locks, worker task references, and health heartbeats. Loss of Redis may interrupt coordination but cannot lose canonical market or opportunity records. Workers receive opaque task references and fail closed when no approved handler is configured.

## Boundaries

- Domain models contain no infrastructure dependencies.
- PostgreSQL adapters implement frozen repository interfaces and do not leak SQLAlchemy types.
- API and application layers depend on abstractions, not the database schema.
- Alembic is the only schema mutation mechanism.
- Operational endpoints disclose status, not credentials or canonical payloads.
- Request and correlation IDs propagate through structured logs and HTTP response headers.

## Determinism and immutability

Canonical JSON and SHA-256 identity remain governed by the existing domain contracts. Repository reads use explicit deterministic ordering. Conflicting writes fail; exact replays are idempotent. Logical histories are append-only. PostgreSQL advisory locks serialize identity-sensitive writes and lifecycle streams.

## Failure behavior

Invalid configuration prevents process start. Readiness fails when PostgreSQL, Redis, or the Alembic head is unavailable. Repository hash mismatches and version conflicts raise canonical repository exceptions. No infrastructure fallback invents domain data or decisions.
