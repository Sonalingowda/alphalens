# AlphaLens v2 Research Dashboard Validation Specification

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B read-model specification; no UI implementation

## 1. Scope

This specification defines a researcher-facing, read-only projection of
datasets, experiments, validation, calibration, comparisons, and promotion
readiness. It SHALL NOT execute experiments, change approvals, expose sealed
protected results, or convert metrics into production policy.

## 2. Definitions and Catalogue Schema

Each catalogue item MUST contain experiment identity/version/status, research
question, policy variants, dataset/label versions, scope, fold protocol,
preregistration and approval references, execution timestamps, validation and
calibration states, protected-test state, owner/reviewer roles, limitations,
predecessor/successor, and hashes.

Status values SHALL distinguish not started, unavailable, running, completed,
failed, invalidated, accepted, rejected, inconclusive, and not applicable where
the governing artifact defines them. Missing data SHALL NOT appear as zero or
passing.

## 3. Metric and Comparison Views

Metric summaries MUST show definition/version, population, counts/denominators,
per-fold and pooled values, uncertainty, raw/adjusted comparison results,
undefined metrics, exclusions, temporal dispersion, and data-quality context.
Primary metrics SHALL be visually distinguishable from secondary/exploratory
metrics without hiding adverse results.

Policy comparison MUST show paired observation coverage, dataset/fold equality,
effect estimates, uncertainty, multiplicity status, stability, deviations, and
selection outcome. Ranking by a dashboard metric SHALL NOT imply promotion.

## 4. Calibration and Promotion Views

Calibration view MUST display policy family, parameter-space identity, objective
and constraints, nested-fold status, candidates evaluated/failed, selected
artifact if any, sensitivity/robustness, and approval state. Parameter values
MUST remain traceable and SHALL NOT be shown as production-active without a
promotion reference.

Promotion readiness is a checklist of evidence gates, not a synthesized score.
It MUST show missing/failed gates, independent review, protected evaluation,
monitoring/rollback readiness, exact approved scope, and final authority.

## 5. Dataset and Data-Quality Views

Views MUST expose dataset identity/version/hash, source/feature/label versions,
symbol/market/timeframe and temporal coverage, row/partition counts, gaps,
missingness, exclusions, conflicts, quality checks, and lineage status. Protected
labels or metrics SHALL be redacted until authorized.

## 6. Filtering, Ordering, and Access Boundaries

Supported filters MAY include immutable identifiers, state, owner, scope,
dataset/policy version, date, metric, calibration status, and promotion status.
Default ordering MUST be deterministic and declared. Pagination MUST bind one
snapshot. Search SHALL NOT expose protected content.

Access controls MUST enforce research roles and protected-test seals. Exported
views require snapshot identity, applied filters, as-of time, redactions, and
result hash.

## 7. Assumptions and Dependencies

The dashboard assumes source repositories are authoritative and status/metric
vocabularies are versioned. It depends on dataset, experiment, metric,
calibration, statistical, promotion, and governance artifacts. It is not a
source of scientific truth.

## 8. Validation Methodology

Contract tests MUST verify schema, source equality, deterministic ordering,
pagination consistency, metric reconstruction, undefined/missing rendering,
redaction, protected access, hash stability, stale-state disclosure, and no
write side effects.

## 9. Acceptance Methodology

The dashboard specification is accepted when every displayed claim maps to an
immutable source and protected information cannot leak. Human-factors review
MUST confirm that score, rank, statistical significance, and promotion state are
not conflated. No numeric usability target is defined here.

## 10. Future Work

Future work MUST define access roles, retention, cache/freshness policy,
supported filters, export policy, accessibility, and human-factors study before
production deployment.
