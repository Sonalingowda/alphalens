# AlphaLens v2 Production Readiness Validation Criteria

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B readiness specification; all capabilities disabled by default

## 1. Scope

This specification defines evidence categories required before individual
Opportunity Intelligence capabilities MAY be enabled. It provides no production
threshold or current approval. Readiness is capability- and version-specific;
one approved output SHALL NOT authorize another.

## 2. Definitions

A capability is one externally observable output class at an exact policy and
scope version. A readiness gate is an evidence-backed requirement with status
`PASS`, `FAIL`, `INCONCLUSIVE`, `UNAVAILABLE`, or `NOT_APPLICABLE` under a
governing rule. Production readiness is the conjunction of all mandatory gate
passes; it is not a score or probability.

## 3. Common Readiness Gates

Every capability requires approved mathematics/policy, dataset/label scope,
preregistered experiments, deterministic replay, walk-forward and protected
evaluation, statistical and practical acceptance, robustness/sensitivity,
independent review, complete provenance, explainability, data-quality/runtime
gates, monitoring, rollback, version compatibility, and human approval.

Each numerical acceptance criterion MUST have been frozen before confirmatory
results. A missing, failed, inconclusive, expired, or scope-mismatched gate
means `NOT_READY`. Readiness SHALL NOT be averaged across gates.

## 4. Opportunity Publication

Publication additionally requires approved market-context definitions used by
the policy, detection predicates, `BUY`/`SELL`/`WAIT` decision policy,
qualification/conflict rules, identity/continuation, freshness/lifecycle,
canonical explanations, limitations/disclosures, and runtime suspension/recovery.
Publication SHALL remain disabled if valid evaluation cannot distinguish `WAIT`
from `UNAVAILABLE`.

## 5. Notifications

Notifications require a publication-ready opportunity plus approved event
types, user-impact estimand, material-change/deduplication, freshness/expiration,
thresholds where used, rate limits, retry/backoff, channels, delivery audit,
disclosures, and suppression/rollback policies. Notification validation MUST
measure opportunity quality and delivery effects separately. No notification
threshold is defined here.

## 6. Scores

Score publication requires an approved quality estimand, component set,
normalization, weights, aggregation, scale/unit, missing behavior, sensitivity,
scope, and monitoring. The displayed value MUST reconstruct from components.
It SHALL be labelled opportunity score and SHALL NOT imply confidence,
probability, expected return, or risk/reward.

## 7. Rankings

Ranking publication requires score readiness plus approved cross-market and
cross-timeframe comparability, candidate-set definition, duplicate identity,
freshness use, score direction, complete tie key, rank stability analysis, and
snapshot accounting. Incomparable scopes MUST remain separately ranked.

## 8. Opportunity Plans

Plans require a publication-ready `BUY` or `SELL` opportunity and approved
reference-price, entry, invalidation, target, risk, reward, ratio, path,
censoring, validity, missingness, and precision rules. Validation MUST address
intrabar ambiguity and non-executability. Partial plans and plans for `WAIT` are
prohibited. Plans SHALL remain informational.

## 9. Assumptions and Dependencies

Readiness assumes evidence remains representative enough for the approved scope
only as supported by monitoring; it does not assume permanent validity. It
depends on all Phase 5B frameworks, policy promotion, runtime governance,
security/operations, and exact production artifact versions.

## 10. Validation Methodology

Readiness review MUST reconstruct every gate, rerun canonical experiments,
verify protected-test and independent-review evidence, audit production wiring,
exercise failure/suspension/rollback, verify disclosure and provenance, and
confirm no unapproved optional field is exposed.

## 11. Acceptance Methodology

Readiness is accepted only by explicit signed approval of the exact capability,
policy, scope, dependencies, and effective version after every mandatory gate
passes. Conditional readiness remains disabled until conditions are evidenced.
Drift, incident, dependency change, or policy supersession MAY suspend readiness
without rewriting the prior approval.

## 12. Future Work

Future policy studies MUST supply numeric acceptance artifacts and monitoring
triggers. Operational work MUST implement durable experiment storage, protected
access, policy registry approval gates, monitoring, incident response, and
capability-specific rollout/rollback before activation.
