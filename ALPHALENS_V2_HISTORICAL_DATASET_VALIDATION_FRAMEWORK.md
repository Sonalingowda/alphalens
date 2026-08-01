# AlphaLens v2 Historical Dataset Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B validation specification

## 1. Scope

This framework defines immutable historical datasets used to evaluate future
AlphaLens policies. It SHALL NOT select a label policy, symbol, market,
timeframe, date range, split size, or acceptance threshold. It specializes the
frozen Dataset Specification without weakening it.

## 2. Definitions

A dataset row is identified by

\[
r=(s,m,\tau,t,v_F,v_L,v_D),
\]

where (s) is instrument, (m) market/venue scope, (\tau) timeframe, (t)
prediction origin, and (v_F,v_L,v_D) feature, label-policy, and dataset
versions. A dataset snapshot (D_v=(R,X,Y,P,B,H)) contains ordered row
identities, inputs, labels, provenance, partition assignments, and canonical
hashes. (Y) is absent until an approved label policy exists.

## 3. Dataset Requirements and Coverage

Every dataset specification MUST declare eligible instruments, venues, quote
currencies, timeframes, UTC boundaries, source providers, feature registry and
pipeline versions, label policy, sampling unit, warm-up, and exclusions.
Coverage SHALL be reported as observed intervals and counts, never described as
adequate without a preregistered adequacy rule.

Cross-market or cross-venue pooling MUST preserve source identity and requires
a declared population estimand. Cross-timeframe rows MUST preserve independent
completion and availability times. Unsupported scopes SHALL be excluded with
reason codes rather than coerced into another scope.

## 4. Data Quality and Missingness

Required quality dimensions are source integrity, schema validity, completion,
chronological ordering, duplicate/conflict status, continuity, availability,
feature/label compatibility, and hash verification. Missing values SHALL be
classified by cause and scope.

Missing mandatory features, labels, provenance, or availability MUST exclude
the row. Optional missingness requires an experiment-specific preregistered
rule. Zero substitution, backward/forward filling across unavailable evidence,
full-sample imputation, and silent row repair are prohibited. Exclusion counts
and missingness patterns SHALL remain part of the snapshot.

## 5. Versioning, Lineage, and Immutability

Dataset identity MUST bind construction specification, source snapshots,
feature/label versions, eligible population, ordering, exclusions, partitions,
preprocessing, code identity, and hashes. Any semantic or row-membership change
requires a new version. Snapshots SHALL be append-only; later corrections or
active-run changes SHALL NOT rewrite historical datasets.

Lineage MUST resolve each row to candles, features, labels, validation records,
construction configuration, and code. Canonical row order SHALL be scope,
prediction origin, and stable identity under the approved ordering contract.

## 6. Assumptions and Dependencies

The framework assumes immutable source artifacts, UTC chronology, registered
features, and collision-resistant canonical identities. It depends on an
approved label policy, split protocol, and evidence scope before a model-ready
snapshot can exist. It does not assume stationarity, balanced classes, complete
coverage, or transferability.

## 7. Validation Methodology

Validation MUST perform schema/domain checks, exact identity joins, source and
hash replay, availability joins, row-order verification, duplicate/conflict
audits, boundary-label overlap checks, split leakage checks, prefix
reconstruction, and deterministic rebuild. A rebuilt snapshot from identical
inputs MUST have identical semantic content and hashes.

Descriptive audits SHALL report coverage, gaps, exclusions, missingness,
class counts when labels exist, partition counts, provenance failures, and
time ranges without testing policy performance.

## 8. Acceptance Methodology

A dataset is methodologically acceptable only when every mandatory validation
passes and every preregistered coverage/adequacy condition is evaluated. Numeric
adequacy criteria MUST be approved before descriptive results are inspected.
Failure SHALL block experiments; researchers SHALL NOT relax membership or
quality rules to obtain acceptance.

## 9. Future Work

Future work MUST approve the label policy, dataset version, scope, date range,
split boundaries, purge/embargo, preprocessing, persistence format, adequacy
criteria, and protected-test seal. Dataset acceptance does not approve any
policy or predictive claim.
