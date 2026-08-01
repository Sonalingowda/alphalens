# AlphaLens v2 Walk-Forward Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B validation specification

## 1. Scope

This framework defines chronological development, calibration, validation, and
protected evaluation. It selects no window length, fold count, step, purge,
embargo, regime, holdout fraction, or acceptance value.

## 2. Definitions

For fold $k$, let $T_k$ be training observations and $V_k$ the later
validation observations with

\[
\max(time(T_k)) < \min(time(V_k)).
\]

Let $P_k$ be observations removed because their information or label intervals
overlap a boundary, and $E_k$ observations excluded by an approved embargo
dependency rule. $P_k$ and $E_k$ are exclusion sets, not assumed fixed-duration
intervals. An optional calibration set $C_k$ MUST be disjoint from training
used to fit the underlying model when required by the estimand.

A rolling design holds training width finite and advances its boundaries. An
expanding design holds the initial boundary and advances its end. The selected
design and all boundaries MUST be frozen before outcomes are examined.

## 3. Methodology

Each fold MUST fit preprocessing, normalization, parameters, and candidate
selection using authorized training data only. Validation observations SHALL
remain untouched until the fold specification is frozen. Label intervals that
cross a boundary MUST be purged. Embargo MUST follow a preregistered dependency
rule tied to label horizons and overlapping information, not a default duration.

Rolling evaluation SHALL emit per-fold immutable predictions and metrics plus
pooled out-of-fold results. Pooled metrics MUST use combined out-of-fold
observations when mathematically appropriate; averaging incompatible fold
summaries without disclosure is prohibited.

## 4. Holdout and Protected Test

The final holdout MUST be chronologically last, sealed before development, and
used once only after configuration selection, code, metrics, and acceptance
rules are frozen and independently approved. Protected results SHALL NOT cause
retuning within the same study. Failure on the protected test SHALL be retained
and reported.

## 5. Regime Separation

Regime analyses require a causal, versioned regime definition fitted or fixed
without validation/holdout outcomes. Regimes MAY stratify reporting but SHALL
NOT be used post hoc to discard unfavorable periods. Small or absent strata
remain explicit. A future market-context ontology is not automatically a valid
research stratifier.

## 6. Leakage Prevention

Random/shuffled folds are prohibited for temporal policy evaluation. Controls
MUST prevent target overlap, global preprocessing, future feature versions,
retrospective context, cross-timeframe completion leakage, survivor/source
selection informed by outcomes, and hyperparameter selection on outer folds.
Nested chronological validation is required when model or parameter selection
occurs.

## 7. Assumptions and Dependencies

The framework assumes chronological dependence and possible distribution drift.
It depends on label intervals, dataset availability, candidate search space,
metric definitions, and an approved protected-test protocol. It does not assume
fold independence or identical distributions.

## 8. Validation Methodology

Validation MUST verify boundary ordering, disjoint roles, purge/embargo
membership, training-only transformations, sealed holdout access, state reset,
fold reproducibility, prefix safety, and complete inclusion/exclusion accounting.
Temporal dispersion and worst/best/median folds SHALL be reported descriptively.

## 9. Acceptance Methodology

The split design is acceptable only when every leakage and reproducibility check
passes and preregistered sample/coverage adequacy rules are evaluated. Policy
acceptance MUST satisfy preregistered per-fold, pooled, stability, and protected
test criteria; no criterion is selected here.

## 10. Future Work

Phase 5B studies MUST approve expanding versus rolling design, all boundaries,
fold count, horizons, purge/embargo dependency, nested-selection procedure,
regime definitions, uncertainty method, and protected-test governance before
execution.
