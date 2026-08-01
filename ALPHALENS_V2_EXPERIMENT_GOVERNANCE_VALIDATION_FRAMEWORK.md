# AlphaLens v2 Experiment Governance Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B experiment-governance specification

## 1. Scope

This framework governs experiment identity, approvals, execution evidence,
failure, supersession, rollback, and archival. It SHALL NOT determine scientific
acceptance or promote a policy by administrative status alone.

## 2. Definitions and States

An experiment has stable `experiment_id` and immutable semantic
`experiment_version`. Canonical states are `DRAFT`, `PREREGISTERED`, `APPROVED`,
`RUNNING`, `COMPLETED`, `FAILED`, `INVALIDATED`, and `ARCHIVED`.

Allowed transitions are forward and append-only. Material changes after
preregistration require a new version. `FAILED` and `INVALIDATED` records remain
visible. `ARCHIVED` removes an experiment from active work without deleting its
artifacts.

## 3. Versioning and Audit Trail

Identity MUST bind hypothesis, estimand, population, dataset, label policy,
variants, folds, metrics, statistics, calibration, acceptance, code, and
configuration. Any semantic change requires a new version.

Audit events MUST record actor/role, timestamp, prior/resulting state, reason,
artifact references, approvals, deviations, protected-data access, execution
environment, configuration/prediction/result hashes, and predecessor/successor.
Audit chronology SHALL be immutable and totally ordered per experiment version.

## 4. Approval Workflow

Preregistration approval MUST occur before outcome-bearing execution. Separate
approvals SHALL cover dataset/label, methodology/statistics, protected-test use,
and promotion where applicable. An approver MUST record the exact artifact
digest reviewed. Approval of one version or scope SHALL NOT transfer implicitly.

## 5. Failure and Deviation Handling

Infrastructure, data, validation, statistical, or governance failure MUST stop
the affected run and preserve partial evidence. Researchers SHALL classify the
failure without overwriting outputs. Rerun under unchanged inputs MAY use a new
run identity; changed methodology requires a new experiment version.

Unplanned analysis is exploratory and SHALL NOT inherit confirmatory status.
Protected-test exposure cannot be rolled back; affected research must be
invalidated or assigned a newly governed untouched test population.

## 6. Rollback and Supersession

Research rollback means withdrawing approval or active eligibility through a
new governance event. It SHALL NOT delete experiments or rewrite results.
Production rollback means disable/suspend the exact promoted policy and restore
an explicitly approved predecessor when compatible; it SHALL NOT silently
substitute a research version. Reasons and affected outputs MUST be audited.

## 7. Archival and Retention

Archive bundles MUST retain specifications, datasets or resolvable snapshots,
policies, environments, code references, logs, predictions, metrics,
statistical outputs, reviews, approvals, deviations, hashes, and readability
metadata. Retention and migration rules require operational approval and MUST
preserve hash/verifiability.

## 8. Assumptions and Dependencies

Governance assumes stable identity, authenticated reviewers, trustworthy clocks,
and durable artifact retention. It depends on experiment, dataset, statistical,
promotion, and runtime-governance frameworks. Administrative completeness is
not evidence of predictive validity.

## 9. Validation Methodology

Validation MUST test legal transitions, version immutability, approval scope,
artifact resolution, audit ordering, failure preservation, rerun identity,
protected-access logs, rollback compatibility, archive reconstruction, and hash
verification.

## 10. Acceptance Methodology

An experiment record is governance-compliant only when its state is supported
by all required prior events and exact artifact approvals. Missing, ambiguous,
or conflicting evidence fails closed. Scientific and promotion acceptance
remain governed by their own frameworks.

## 11. Future Work

Future work MUST define reviewer roles, signature authority, retention periods,
archive media, incident severity, emergency suspension, and operational service
levels without changing experiment semantics.
