# AlphaLens v2 Statistical Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B statistical specification

## 1. Scope

This framework governs statistical evidence for future policies. It specifies
candidate methodologies and selection rules, not a significance level,
confidence level, interval method, test, effect threshold, or conclusion.

## 2. Definitions

An estimand is the precisely declared population quantity a study seeks to
describe or compare. An estimate is its sample-derived value. A statistical
validation result is the immutable tuple of estimate, uncertainty, hypothesis
test when applicable, diagnostics, sample support, multiplicity status, and
limitations. It is not a production decision.

## 3. Estimands and Hypotheses

Every analysis MUST define population, sampling unit, outcome, comparison,
estimand (\Delta), null/alternative hypotheses, directionality, dependence,
and missing/censoring rules. Hypotheses and primary analyses SHALL be registered
before outcomes are examined. Exploratory analyses MUST be labelled and cannot
support promotion without confirmation.

## 4. Significance Tests and Intervals

Test selection MUST match the estimand and paired temporal design. Candidate
methods MAY include paired permutation/randomization tests, contingency-table
tests for paired classifications, block/bootstrap procedures, or regression
with dependence-robust inference. None is the default. Assumptions, block or
cluster unit, statistic, tail, resampling plan, and finite-sample limitations
MUST be frozen.

Intervals (CI_{1-\alpha}(\Delta)) require preregistered (\alpha), method, and
coverage interpretation. P-values SHALL accompany effect estimates, intervals,
sample counts, and diagnostics; they SHALL NOT be called probability that a
policy is true or useful.

## 5. Cross-Validation and Multiplicity

Evaluation SHALL use purged, embargoed chronological walk-forward folds.
Hyperparameter or model selection requires nested chronological validation.
Fold observations are not presumed independent.

The complete family of variants, metrics, subgroups, horizons, and tests MUST be
declared. A preregistered multiplicity procedure SHALL control the selected
error criterion. Raw and adjusted results and all tested hypotheses MUST be
reported. Selective deletion or relabeling after results is prohibited.

## 6. Robustness and Sensitivity

Required candidate checks include alternative authorized windows/folds,
parameter perturbation, ablation, leave-period/source-out analysis, missingness,
class imbalance, timestamp boundary changes, reasonable outcome variants,
and implementation replay. Robustness is evidence about sensitivity, not a
license to search until a favorable result appears.

## 7. Outliers, Regimes, and Bias

Outliers MUST be defined without protected outcomes and retained in an audit.
Removal, clipping, robust transforms, or separate reporting requires a
preregistered rule fitted on training only. Results with and without authorized
treatment SHOULD be compared when relevant.

Regime comparisons require causal definitions and sufficient reported support;
post hoc favorable regime selection is exploratory. Bias audits MUST examine
temporal leakage, survivorship, venue/source selection, missingness, class and
scope imbalance, multiple testing, researcher degrees of freedom, protected-
test access, and presentation/publication bias.

## 8. Assumptions and Dependencies

This framework assumes observations may be serially dependent, heteroskedastic,
nonstationary, censored, and imbalanced. It depends on frozen datasets, labels,
folds, metrics, hypotheses, and experiment ledgers. Statistical evidence does
not establish causality, execution feasibility, or profitability.

## 9. Validation Methodology

Statistical implementations MUST pass simulated-null, known-effect,
degenerate-sample, missingness, dependence, reproducibility, and hand-computed
fixtures. Analysis MUST report assumption diagnostics, effective sample support,
fold dispersion, effect estimates, intervals, raw/adjusted tests, and deviations.

## 10. Acceptance Methodology

Acceptance requires methodological validity plus preregistered statistical,
practical, stability, and adequacy criteria. Statistical significance alone is
insufficient. Failure of assumptions, power/precision adequacy, multiplicity,
or stability SHALL block confirmatory claims. No numerical gate is defined here.

## 11. Future Work

Each study MUST approve the test family, interval, (\alpha), multiplicity,
effect-size interpretation, sample adequacy, dependence unit, robustness suite,
and protected-test rule before execution.
