# AlphaLens v2 Quantitative Calibration Validation Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B calibration specification; no calibrated output

## 1. Scope

This framework defines how future parameterized AlphaLens policies MAY be
calibrated. It selects no parameter, search range, objective, threshold, weight,
normalization, or policy variant. Calibration is model selection under a frozen
estimand, not production approval.

## 2. Definitions

For policy family (\Pi=\{\pi_\theta:\theta\in\Theta\}), calibration is a
preregistered procedure

\[
\mathcal C(D_{train},D_{cal},J,\Theta,\mathcal K)\rightarrow
(\hat\theta,Z_C),
\]

where (J) is the declared objective/constraint set, (\mathcal K) the nested
chronological protocol, and (Z_C) complete calibration evidence. This equation
defines an interface; no optimizer or objective is approved.

## 3. General Workflow

Calibration MUST freeze the estimand, population, finite or bounded candidate
space, transformations, missing rules, objective, constraints, comparison
method, nested folds, seeds, stopping rule, sensitivity plan, and acceptance
criteria before execution. Fitting occurs only on authorized inner-training/
calibration data. Outer validation and protected data SHALL NOT select
parameters.

All evaluated candidates, failures, and results MUST be retained. Selection
SHALL use the preregistered rule; manual preference after viewing results is a
new study, not a deviation.

## 4. Calibration Domains

- **Detection parameters:** calibrate declared predicates against an approved
  opportunity label while jointly reporting quality, coverage, and abstention.
- **Score normalization:** fit or select transforms on training populations;
  freeze parameters and out-of-range/missing behavior before outer evaluation.
- **Score components/weights:** compare preregistered component and constraint
  sets with dependence, ablation, and sensitivity analysis; equal weights are
  not a default.
- **Ranking components:** calibrate only after score comparability and relevance
  are defined; preserve candidate-set and tie semantics.
- **Notification thresholds:** require an approved publication event, user-impact
  estimand, operating constraints, rate-limit policy, and error-cost semantics;
  no threshold is implied.
- **Qualification:** calibrate mandatory/optional evidence, conflicts, and
  disqualifiers against an approved estimand without trading integrity gates.
- **Opportunity plans:** calibrate reference, entry, invalidation, target, path,
  horizon, censoring, and ambiguity rules only against approved scenario/outcome
  semantics; no execution claim is permitted.

## 5. Assumptions and Dependencies

Calibration assumes the candidate family and objective were chosen without
protected outcomes, inner folds represent the declared development population,
and search results may be unstable. It depends on approved labels, datasets,
walk-forward design, metrics, statistical validation, and policy-specific
mathematics. Confidence calibration remains a separate governed branch.

## 6. Validation Methodology

Required checks include nested-fold isolation, search-space completeness,
deterministic replay, parameter-domain validation, candidate accounting,
selection-rule reconstruction, sensitivity/perturbation, temporal and subgroup
stability, missingness, out-of-range behavior, and comparison with preregistered
references. Selection uncertainty and multiplicity MUST be reported.

## 7. Acceptance Methodology

A calibration run is methodologically accepted when all candidates and choices
match preregistration and reproduce exactly. A selected parameterization is
eligible for independent validation only when it meets predeclared adequacy,
stability, sensitivity, and practical criteria on development evidence. It is
not promoted until independent review and protected evaluation succeed under
the Promotion Framework.

## 8. Future Work

Future calibration studies MUST instantiate each domain's parameter space,
objective, constraints, nested folds, comparison method, uncertainty,
acceptance, and monitoring/recalibration triggers. This framework emits no
calibrated values.
