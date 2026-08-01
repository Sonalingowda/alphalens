# AlphaLens v2 Opportunity Qualification Specification

**Specification version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose

Qualification determines whether a valid `BUY` or `SELL` assessment MAY enter
a ranking snapshot. It SHALL be separate from detection, stance, score, rank,
confidence, and notification. This specification defines structural gates only;
quantitative gates require an approved qualification policy.

## 2. Qualification Record

A record MUST contain `qualification_id`, contract and policy versions,
assessment reference, context and evidence-package references, evidence cutoff,
evaluation time, ordered gate results, overall result, exclusions,
limitations, configuration hash, result hash, and code identity.

Each gate result MUST identify its gate, requirement class, status, evidence,
and reason code. Status SHALL be `PASS`, `FAIL`, or `UNAVAILABLE`.

## 3. Evidence Classes

Mandatory evidence SHALL include a valid canonical `BUY` or `SELL` decision,
verified market and feature snapshots, data-quality evidence, policy identity,
complete reasons, complete provenance, current lifecycle/freshness evidence,
and every item declared mandatory by the active policy.

Optional evidence MAY include context categories, opportunity plan, authorized
confidence, or other approved evidence. Its absence SHALL NOT be silently
penalized unless a quantitative policy explicitly makes it a scoring or
qualification input.

Disqualifying evidence SHALL include integrity failure, future leakage,
unsupported scope, stale or expired mandatory evidence, policy/version
mismatch, unresolved mandatory input, suspended dependency, invalid decision,
or a policy-defined disqualifier. Quantitative disqualifiers SHALL NOT exist
without policy approval.

## 4. Conflict and Incompleteness

Supporting and contradicting evidence MUST both be retained. Conflict SHALL be
resolved only by the approved policy; no majority vote or reason count MAY be
used implicitly. Missing mandatory evidence SHALL produce `UNAVAILABLE` and an
overall non-qualified result. Missing optional evidence SHALL be disclosed.
Unknown gate semantics, evidence conflict without a rule, or partial atomic
records SHALL fail closed.

## 5. Evaluation Order

Qualification MUST evaluate structural validity, scope compatibility,
chronology, integrity, lifecycle/freshness, mandatory evidence, policy-defined
disqualifiers, policy-defined positive gates, and final atomic validation in
that order. Every gate SHALL run or record why it was not evaluable.

## 6. Lifecycle

A qualification attempt SHALL progress from `PENDING` to `VALIDATING`, then
`QUALIFIED`, `NOT_QUALIFIED`, or `UNAVAILABLE`. Published records are immutable.
New evidence or policy versions create new records. A later qualified record
SHALL NOT erase a prior exclusion.

## 7. Determinism and Validation

Evaluation MUST preserve deterministic gate order, complete evidence lineage,
future isolation, prefix invariance, and reproducible hashes. Qualification
SHALL NOT manufacture a score, confidence value, decision, or explanation.

## 8. Policy Extension Point

A production qualification policy MUST define its population, mandatory and
optional evidence, each quantitative gate, conflict resolution, missing-input
behavior, freshness requirements, and applicability. Until approved, only
structural validation is defined and no assessment is publication-qualified.
