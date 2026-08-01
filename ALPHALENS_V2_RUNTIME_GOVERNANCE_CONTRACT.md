# AlphaLens v2 Runtime Governance Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose

This contract defines fail-closed runtime health, suspension, recovery, and
audit behavior across market ingestion and Opportunity Intelligence. It SHALL
NOT define quantitative market policies or infrastructure-specific retry
values.

## 2. Governing Principle

Missing, corrupt, stale, incompatible, incomplete, or unverifiable mandatory
evidence MUST stop the affected scope before a new canonical downstream result
is published. Operational failure SHALL NOT become `WAIT`, low confidence, a
zero score, or a stale opportunity presented as current.

## 3. Runtime Health Record

Every evaluation cycle MUST create an immutable health record containing cycle
identity, scope, expected and observed boundaries, component checks, status,
reason codes, first/last observation times, evidence references, suspension
action, recovery prerequisites, configuration/code identity, and hashes.
Status SHALL be `HEALTHY`, `DEGRADED`, `SUSPENDED`, or `RECOVERING`.

## 4. Failure Matrix

| Condition | Required behavior |
| --- | --- |
| Missing data or gap | MUST stop dependent feature/context/assessment publication and record affected scope. |
| Corrupt data or hash mismatch | MUST quarantine the artifact, suspend dependants, and prohibit fallback. |
| Exchange/provider outage | MUST retain historical state, mark source unavailable, and suppress new-current claims. |
| Incomplete candle | MUST remain outside canonical evidence and all downstream computation. |
| Clock drift | MUST reject timestamps beyond approved tolerance and suspend time-sensitive publication. |
| Pipeline failure | MUST abort the atomic cycle; partial outputs SHALL NOT become active. |
| Validation failure | MUST persist failure evidence and prevent promotion. |
| Feature failure | MUST make dependent results unavailable; unrelated scopes MAY continue if isolated. |
| Context/policy failure | MUST stop affected detection, qualification, or publication. |
| Persistence/hash failure | MUST roll back publication and raise critical health state. |
| Notification failure | MUST preserve opportunity state and record delivery failure. |

Clock tolerance, freshness limits, retry counts, and backoff require approved
operational policy values. Their absence SHALL disable the affected automated
decision rather than invoke defaults.

## 5. Scanner Suspension

Suspension SHALL be scoped to the smallest safely isolated instrument,
timeframe, provider, dependency graph, or global boundary. A suspended scope
MUST publish health status and SHALL NOT publish new opportunities. Previously
published items MUST be marked non-current when their validity ends. Operators
MAY manually widen suspension; manual action MUST be authenticated and audited.

## 6. Recovery

Recovery MUST verify source continuity, corrections/conflicts, completed
candles, clock synchronization, registry/dependency compatibility, feature and
context recomputation, hashes, persistence health, and policy availability.
Missed intervals MUST be processed in chronological order. Recovery SHALL
replay idempotently from the last verified checkpoint and SHALL NOT overwrite
history. Publication MAY resume only after a complete validation cycle reaches
`HEALTHY`.

## 7. Concurrency and Idempotence

Each scope/cutoff cycle MUST have a stable identity. A single-writer lease or
equivalent approved mechanism MUST prevent conflicting promotion. Identical
retries MAY resolve idempotently; divergent results for one identity MUST
suspend the scope. Processing order and checkpoint advancement MUST be
deterministic.

## 8. Audit, Observability, and Security

Logs and metrics SHALL reference immutable identities without becoming source
of truth. Health transitions, quarantine, retries, manual actions, and recovery
MUST be retained. Secrets and raw credentials SHALL NOT enter evidence,
notifications, logs, hashes exposed to consumers, or API errors.

## 9. Operational Policy Gate

Production scheduling, lateness/freshness tolerances, drift bounds, retry and
backoff values, leases, recovery windows, escalation, and retention require a
versioned Runtime Operations Policy. This contract fixes behavior categories
and fail-closed semantics while leaving those environment-dependent values for
explicit approval.
