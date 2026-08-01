# AlphaLens v2 Quantitative Experiment Framework

**Version:** Validation Framework v1.0.0

**Status:** Canonical Phase 5B validation specification

## 1. Scope

This framework defines generic, reproducible comparison of future AlphaLens
policy variants. It authorizes no policy family, parameter value, objective,
metric, or production promotion.

## 2. Definitions

An experiment is the immutable tuple

\[
E=(id,v,H,D,\Pi,S,M,A,C,R),
\]

where (H) is hypothesis/preregistration, (D) dataset snapshot, (\Pi) the
ordered policy variants, (S) split protocol, (M) metrics, (A) acceptance
rules, (C) code/configuration, and (R) results. An experiment run binds one
exact member of each versioned artifact.

## 3. Required Metadata and Provenance

Each experiment MUST record research question, estimand, hypotheses, population,
label policy, dataset/version/hash, variants and finite search space, baselines,
folds, preprocessing, missingness, metrics, uncertainty and multiplicity,
acceptance/stopping rules, seeds, code/environment identities, deviations,
predictions, exclusions, and result hashes.

Multiple datasets or policy variants require explicit compatibility and paired-
observation mappings. Variants SHALL receive identical eligible evidence and
folds unless the research question preregisters otherwise.

## 4. Execution and Comparison

The framework SHALL support descriptive audits, single-variant validation,
paired variant comparison, ablation, sensitivity, robustness, and nested
selection. Execution MUST canonicalize variant and observation order. Failed
runs and deviations remain immutable and SHALL NOT be silently rerun under the
same identity.

Statistical comparisons MUST operate on appropriate paired units and preserve
temporal dependence. A leaderboard alone is not evidence. Every selected
variant MUST retain comparisons with preregistered references and all adverse,
null, or unstable results.

## 5. Assumptions and Dependencies

Experiments assume frozen hypotheses and analysis choices, immutable datasets,
valid replay, and adequate provenance. They depend on the Dataset, Backtest,
Walk-Forward, Metrics, Statistical Validation, and Governance frameworks.
They do not assume any candidate is superior.

## 6. Validation Methodology

The system MUST validate artifact resolution, semantic versions, fold identity,
parameter domains, deterministic seeds, output completeness, prediction-to-row
alignment, metric reconstruction, comparison pairing, protected-test access,
and hashes. Exact replay MUST reproduce semantic outputs.

## 7. Acceptance Methodology

An experiment is methodologically accepted when preregistration is complete,
all infrastructure/lineage checks pass, every deviation is reviewed, and the
analysis exactly follows the frozen plan. A policy variant is empirically
acceptable only under separately preregistered statistical, stability,
practical, and protected-evaluation criteria. Methodological acceptance does
not imply policy acceptance.

## 8. Future Work

Future studies MUST instantiate hypotheses, variants, metrics, uncertainty,
multiplicity, sample adequacy, stopping, and promotion criteria. The framework
SHOULD support new policy types through typed adapters without changing
experiment identity or evidence standards.
