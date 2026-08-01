# AlphaLens v2 Opportunity Lifecycle Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose

This contract defines immutable opportunity identity, revisions, current-state
resolution, freshness, continuation, and terminal states. Lifecycle SHALL NOT
change decision semantics or infer user activity.

## 2. Identity

`opportunity_id` SHALL identify one continuing thesis under an approved
continuation policy. `opportunity_version_id` SHALL identify one immutable
revision. `assessment_id` and `decision_id` SHALL remain their source identities.
An identity record MUST also preserve instrument, timeframe, direction,
originating detection policy, initial candidate, initial evidence cutoff, and
identity-policy version/hash.

Two records SHALL NOT be merged solely because instrument, timeframe, or
direction match. Direction reversal SHALL create a different opportunity unless
an approved identity policy explicitly defines otherwise; it SHALL never imply
closing a user position.

## 3. States

Canonical states are `DETECTED`, `QUALIFIED`, `RANKED`, `PUBLISHED`, `UPDATED`,
`SUPERSEDED`, `INVALIDATED`, `EXPIRED`, and `ARCHIVED`.

- `DETECTED` requires a valid candidate.
- `QUALIFIED` requires a valid qualification record.
- `RANKED` requires membership in a valid ranking snapshot.
- `PUBLISHED` requires an immutable current delivery projection.
- `UPDATED` requires a successor revision under the continuation policy.
- `SUPERSEDED` means a named successor replaces current presentation.
- `INVALIDATED` requires a post-publication condition from an approved policy.
- `EXPIRED` requires the approved validity boundary to be reached.
- `ARCHIVED` removes the item from current views while retaining all evidence.

## 4. Allowed Transitions

Allowed forward transitions SHALL be:

- `DETECTED` to `QUALIFIED`, `EXPIRED`, or `ARCHIVED`;
- `QUALIFIED` to `RANKED`, `INVALIDATED`, `EXPIRED`, or `ARCHIVED`;
- `RANKED` to `PUBLISHED`, `SUPERSEDED`, `INVALIDATED`, or `EXPIRED`;
- `PUBLISHED` to `UPDATED`, `SUPERSEDED`, `INVALIDATED`, or `EXPIRED`;
- `UPDATED` to `RANKED`, `PUBLISHED`, `SUPERSEDED`, `INVALIDATED`, or `EXPIRED`;
- any terminal current state to `ARCHIVED`.

`SUPERSEDED`, `INVALIDATED`, `EXPIRED`, and `ARCHIVED` SHALL NOT return to an
earlier state. A renewed thesis SHALL receive a new opportunity identity unless
the approved continuation policy authorizes a successor revision.

## 5. Lifecycle Event Schema

Every event MUST contain event identity/version, opportunity identities, prior
and resulting state, assessment and policy references, evidence cutoff,
occurred-at and available-at timestamps, reason code, evidence references,
predecessor/successor references, configuration hash, result hash, and code
identity. Events SHALL be append-only and totally ordered per opportunity by
approved sequence plus stable event identity.

## 6. Freshness

Freshness SHALL preserve source event, retrieval, availability, feature/context,
assessment, ranking, publication, verification, and validity timestamps.
`current` means all mandatory artifacts remain valid under an approved
freshness policy at the resolution cutoff. Absence of a freshness policy SHALL
make current-state publication unavailable; no default tolerance MAY be used.

## 7. Continuation, Update, and Supersession

Continuation MUST require scope compatibility, direction compatibility, policy
compatibility, nonterminal predecessor state, and policy-defined time/evidence
conditions. Updates MUST create a new version referencing the predecessor.
Supersession MUST name the successor and reason. Rank-only change SHALL create
a ranking/lifecycle event, not a rewritten assessment.

## 8. Validation

The lifecycle service MUST reject illegal transitions, missing predecessors,
cycles, ambiguous current heads, timestamp regression, cutoff violations,
identity collisions, stale-policy mismatch, or broken hashes. Recovery MUST
replay events deterministically. Historical state SHALL remain reproducible and
prefix invariant.

## 9. Quantitative Extension Points

Freshness durations, validity, continuation windows, invalidation conditions,
and renewal rules require approved versioned policies. This contract approves
no durations, price conditions, or thresholds.
