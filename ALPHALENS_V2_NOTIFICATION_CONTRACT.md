# AlphaLens v2 Notification Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Boundary

The Notification Engine SHALL deliver informational projections of canonical
opportunity lifecycle events. It SHALL NOT create opportunities, decisions,
scores, confidence, plans, or execution commands. Delivery acknowledgement
SHALL NOT represent user action or a trade.

## 2. Publication Eligibility

A notification MAY be created only for an event type authorized by an approved
notification policy, referencing a valid current opportunity revision and
verified lifecycle event. Content MUST be a projection of existing canonical
records. `SELL` SHALL mean a downward opportunity, never exit. Exit commands,
stop execution warnings, and take-profit execution reminders are prohibited;
plan or invalidation updates MAY be described neutrally when those source
records are approved and present.

## 3. Event and Payload Schema

Canonical event types SHALL be versioned. The architecture supports
`OPPORTUNITY_PUBLISHED`, `OPPORTUNITY_UPDATED`, `RANK_CHANGED`,
`PLAN_UPDATED`, `CONFIDENCE_STATUS_CHANGED`, `OPPORTUNITY_INVALIDATED`,
`OPPORTUNITY_EXPIRED`, `OPPORTUNITY_SUPERSEDED`, and `SYSTEM_SUSPENDED` only
when an approved policy enables them.

Every payload MUST contain notification/contract identity, event type,
opportunity and lifecycle references, instrument/timeframe, canonical stance,
score/rank only when approved, confidence only when authorized, evidence
summary references, optional complete plan, limitations, evidence cutoff,
created-at, expires-at when defined, deep-link reference, policy/code identity,
and result hash. It MUST state that AlphaLens provides information and the user
makes the decision.

## 4. Freshness, Expiration, and Suppression

Creation MUST revalidate currentness under the notification policy. Expired,
invalidated, superseded, suspended, or unverifiable opportunities MUST NOT
produce a new-opportunity notification. Expiration SHALL prevent undelivered
content from being presented as current. Suppression decisions and reasons MUST
be immutable and auditable.

## 5. Deduplication and Rate Limiting

Deduplication MUST use a versioned key over policy, user destination, event
type, opportunity revision, and canonical payload hash. Identical events SHALL
be idempotent. Material-change definitions, cooldowns, batch windows, and rate
limits require approved policy values; no defaults MAY be invented. Rate
limiting SHALL delay or suppress delivery without changing source opportunity
state.

## 6. Retry and Delivery Guarantees

Persistence of a valid notification intent and delivery attempt history MUST
be at-least-once and append-only. External delivery MAY be retried under an
approved bounded retry/backoff policy. Provider idempotency keys SHOULD be used
where available. The system SHALL NOT claim exactly-once external delivery.
Permanent failure SHALL be recorded and SHALL NOT invalidate the opportunity.

## 7. Delivery States

Allowed delivery states SHALL be `PENDING`, `SUPPRESSED`, `IN_FLIGHT`,
`DELIVERED`, `RETRYABLE_FAILURE`, `PERMANENT_FAILURE`, and `EXPIRED`.
Transitions MUST be forward-only and policy-governed. Delivery timestamps,
provider references, attempt sequence, and sanitized failure categories MUST be
retained.

## 8. Validation and Security

Validation MUST verify source hashes, payload projection, freshness,
authorization, destination scope, deduplication identity, prohibited wording,
and absence of secrets. Delivery channels, thresholds, schedules, retry
parameters, and rate limits require a separately approved notification policy.
