# AlphaLens v2 Performance Metrics Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B metric specification

## 1. Scope

This framework defines canonical metric families for policy research. It does
not select a primary metric, relevance definition, confidence quantity,
aggregation, target value, or acceptance threshold. Every metric MUST name its
estimand, population, unit, denominator, exclusions, and uncertainty method.

## 2. Definitions

An evaluation unit is the preregistered observation, opportunity episode,
candidate set, or lifecycle event on which a metric is computed. A metric is a
versioned function from an explicitly ordered evaluation sample to a typed value
or `UNDEFINED`, accompanied by counts and provenance. Metric values from
different units, labels, scopes, or versions are not comparable by default.

## 3. Classification Metrics

For class (c\in\{BUY,SELL,WAIT\}), define one-versus-rest counts
(TP_c,FP_c,FN_c,TN_c). Then

\[
Precision_c=\frac{TP_c}{TP_c+FP_c},\quad
Recall_c=\frac{TP_c}{TP_c+FN_c},
\]

\[
FPR_c=\frac{FP_c}{FP_c+TN_c},\quad
FNR_c=\frac{FN_c}{FN_c+TP_c}.
\]

A zero denominator yields `UNDEFINED`, not zero. Full confusion matrices and
class counts MUST accompany aggregates. Macro, micro, weighted, directional,
or pooled summaries require preregistration and SHALL NOT replace class results.

## 4. Opportunity Activity Metrics

- **Opportunity frequency:** count of detected, qualified, or published events
  divided by a declared exposure unit such as eligible observations or elapsed
  market time. Stage and denominator MUST be named.
- **Coverage:** evaluated eligible observations divided by all eligible
  observations, with unavailable and excluded causes reported separately.
- **Time-to-detection:** (a_D-a_O\), where (a_O) is availability of an
  approved opportunity-onset label and (a_D) candidate availability. Undefined
  onset or censoring MUST be explicit.
- **Opportunity longevity:** elapsed time from a declared lifecycle origin to a
  declared terminal/current boundary. Right censoring and competing terminal
  states MUST be retained; naïve means over incomplete episodes are prohibited.

## 5. Stability Metrics

Signal stability is a family, not one scalar. Candidate measures include
adjacent-output agreement, transition matrices, episode fragmentation,
candidate-set Jaccard overlap, rank correlation on common members, rank turnover,
and sensitivity to input/parameter perturbations. Each requires a declared
comparison interval and missing-member rule. Stability SHALL NOT reward a
trivial always-`WAIT` policy without opportunity-quality metrics.

## 6. Calibration Metrics

Calibration metrics are `NOT_APPLICABLE` unless a separately approved confidence
or probability estimand exists. Candidate measures include reliability curves,
calibration intercept/slope, proper scoring rules, and expected/maximum
calibration error. Bins, weighting, smoothing, and norm for any calibration
error MUST be preregistered; no bin count or mapping is defined here. Raw score
and rank SHALL NOT be evaluated or presented as confidence.

## 7. Ranking Metrics

Ranking quality requires an approved relevance/outcome variable and comparable
candidate set. Candidate families include pairwise concordance, Kendall or
Spearman association, mean average precision, discounted cumulative gain, and
top-set precision/recall. Relevance grades, discount, cut positions, ties,
missing outcomes, censoring, and candidate-set construction MUST be frozen.
Without these definitions ranking quality is unavailable.

## 8. Data Quality Impact

Data-quality impact compares metric distributions across preregistered quality
states or paired observations under controlled exclusions. It SHALL report
coverage and composition changes. Observational differences SHALL NOT be called
causal effects. Post hoc removal of poor periods to improve results is prohibited.

## 9. Assumptions and Dependencies

Metrics assume valid labels/outcomes, exact prediction alignment, declared
sampling units, and appropriate dependence handling. They depend on dataset,
split, lifecycle, ranking-relevance, and optional confidence specifications.
No metric alone establishes practical usefulness or production readiness.

## 10. Validation Methodology

Metric implementations MUST pass hand-computed fixtures, zero-denominator,
empty-set, tie, censoring, missingness, permutation, Decimal/rounding, fold
pooling, and exact replay tests. Counts MUST reconstruct every reported ratio.
Uncertainty methods MUST preserve the declared temporal/cluster structure.

## 11. Acceptance Methodology

Each experiment MUST preregister primary and secondary metrics, aggregation,
direction, practical interpretation, uncertainty, multiplicity, sample adequacy,
and acceptance rules before results. No value in this framework is a target.
Promotion requires all mandatory metrics, not selective favorable reporting.

## 12. Future Work

Future work MUST approve outcome semantics, primary metrics, denominators,
pooling, censoring, relevance, calibration estimand, uncertainty, and numerical
acceptance criteria for each policy study.
