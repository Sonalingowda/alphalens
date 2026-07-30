# AlphaLens v2 Research Protocol

## Status and Authority

**Phase:** Phase 4 — Research Foundation  
**Artifact type:** Research governance and evaluation protocol  
**Implementation status:** No experiments authorized  
**Protocol version:** Unresolved

This document governs future AlphaLens v2 research into the
`BUY`/`SELL`/`WAIT` problem. It defines methodology and approval gates without
selecting a label policy, dataset, model, hyperparameter, threshold, metric
target, or production decision policy.

It is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_PHASE_1_BASELINE.md`;
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`;
- `ALPHALENS_V2_PHASE_3_BASELINE.md`;
- `ALPHALENS_V2_LABELING_SPECIFICATION.md`; and
- `ALPHALENS_V2_DATASET_SPECIFICATION.md`.

## Research Objective

The future research program will determine whether point-in-time Tier-A
intraday evidence contains reproducible information relevant to a separately
approved `BUY`/`SELL`/`WAIT` label policy.

The research must prioritize:

1. statistical defensibility;
2. chronological validity;
3. directional opportunity quality over signal frequency;
4. explicit and valid `WAIT` behavior;
5. stability across time and approved timeframes;
6. explainability;
7. auditability; and
8. exact reproducibility.

Research success does not itself authorize a production decision engine,
confidence, ranking, scanner, overlay, or trading conclusion.

## Approved Research Sequence

Future work must follow these gates in order.

### Gate 1 — Select and approve the label policy

Produce a versioned quantitative label policy resolving every relevant item
in `ALPHALENS_V2_LABELING_SPECIFICATION.md`.

No label outcome may be generated before approval.

### Gate 2 — Freeze the dataset protocol

Resolve dataset version, evidence scope, chronological boundaries, walk-forward
design, purge, embargo, final test, and preprocessing policy.

No model-ready dataset may be generated before approval.

### Gate 3 — Produce descriptive dataset audit

Generate only counts, time ranges, class counts, exclusions, feature
coverage, overlap diagnostics, and provenance verification.

If evidence is insufficient or invalid, stop. Do not repair data or weaken
the protocol to obtain a usable dataset.

### Gate 4 — Preregister baseline experiments

Before fitting:

- identify each baseline;
- declare its parameters;
- declare preprocessing;
- freeze eligible folds;
- select primary and secondary metrics;
- define aggregation;
- define uncertainty and multiplicity procedures;
- define success and stopping criteria;
- declare random seeds; and
- record the protected-test prohibition.

### Gate 5 — Execute development experiments

Fit and evaluate only through the approved chronological development folds.
Persist immutable per-fold predictions and experiment evidence.

### Gate 6 — Compare and review

Compare baselines using only development-period evidence. Report favorable,
unfavorable, null, and unstable results. Do not select a method using the
protected final test.

### Gate 7 — Optional confidence research

Confidence remains absent. A separate confidence specification and calibration
study may begin only after a decision policy exists and every gate in
`ALPHALENS_V2_CONFIDENCE_POLICY.md` is satisfied.

### Gate 8 — One-time protected evaluation

A final test evaluation requires separate explicit approval after the entire
research configuration and selection procedure are frozen. Its consumption
is recorded once and cannot trigger tuning for the same study.

## Baseline Experiment Plan

No baseline is selected or authorized for implementation by this document.
The future preregistration must choose the smallest defensible set needed to
test whether the approved features add information beyond trivial behavior.

### Candidate non-learned references

| Candidate | Purpose | Governance condition |
| --- | --- | --- |
| Always `WAIT` | Measures the trivial abstention policy and exposes why accuracy alone can mislead. | Valid only as a reference, never as an operational failure proxy. |
| Training-prior class | Predicts the most frequent class using training data only. | Class prior must be re-estimated independently per training fold. |
| Deterministic directional persistence rule | Uses a preregistered sign rule from approved point-in-time features. | Exact rule and tie-to-`WAIT` behavior require approval. |
| Deterministic directional reversal rule | Uses the inverse of a preregistered point-in-time sign rule. | Exact rule and tie-to-`WAIT` behavior require approval. |

### Candidate learned baselines

| Candidate family | Purpose | Governance condition |
| --- | --- | --- |
| Multinomial linear classifier | Tests a low-complexity linear relationship among the three classes. | Solver, regularization, class handling, scaling, and seed must be preregistered. |
| One-versus-rest linear classifiers | Tests separately defined directional class boundaries. | Joint mapping and conflict-to-`WAIT` rule must be preregistered. |
| Shallow decision tree | Tests limited nonlinear threshold interactions. | Depth, leaf size, class handling, and seed must be fixed without tuning. |

These are candidate research baselines, not approved model families. No tree
ensemble, boosting system, neural network, language model, or additional
predictive family is implied.

### Baseline execution requirements

Every approved baseline must:

- use the identical frozen dataset and folds;
- retain the approved ordered feature set without selection;
- fit preprocessing on training only;
- use fixed, recorded parameters;
- use fixed random seeds where applicable;
- emit exactly one research class per evaluated row;
- persist per-observation outputs and hashes;
- preserve `WAIT` semantics;
- avoid confidence or probability claims unless separately calibrated and
  approved; and
- leave the protected final test untouched.

## Evaluation Methodology

Evaluation must report per-fold and pooled development evidence. Pooled
metrics are calculated from the combined immutable out-of-fold predictions,
not by averaging incompatible fold summaries without disclosure.

### Required descriptive evidence

For every baseline and timeframe, report:

- evaluated and excluded observations;
- class count and prevalence;
- predicted class count;
- complete confusion matrix;
- per-fold date boundaries;
- per-fold metrics;
- pooled metrics;
- temporal metric dispersion;
- worst, best, and median fold;
- missing or invalid prediction count; and
- prediction and result hashes.

### Candidate classification metrics

The future preregistration must select metrics appropriate to the approved
label policy. Candidate measures include:

| Metric | Appropriate use | Required caution |
| --- | --- | --- |
| Per-class precision | Measures correctness among predicted `BUY`, `SELL`, or `WAIT` observations. | Directional precision must be reported separately; pooled precision can hide asymmetry. |
| Per-class recall | Measures coverage of each true class. | High `WAIT` recall does not establish directional opportunity quality. |
| Per-class F1 | Summarizes precision/recall trade-off for one class. | It obscures the separate quantities and must not replace them. |
| Macro-averaged F1 | Gives each class equal weight. | Can be unstable with small class counts. |
| Balanced accuracy | Averages class recalls. | Does not directly measure directional precision. |
| Overall accuracy | Describes total correct-class frequency. | Potentially misleading when `WAIT` dominates; never sufficient alone. |
| Matthews correlation coefficient | Summarizes multiclass association. | Requires interpretation alongside class-specific evidence. |
| Action rate | Fraction predicted `BUY` or `SELL`. | Frequency is not quality and is not a success metric alone. |
| Abstention rate | Fraction predicted `WAIT`. | Must not reward unconditional abstention without directional-quality reporting. |
| Directional precision | Correct directional outcomes among directional predictions. | Exact treatment of opposite-direction versus `WAIT` errors must be predeclared. |
| Directional recall | Captured directional opportunities among true directional labels. | Must be reported by `BUY` and `SELL`, not only combined. |

ROC-AUC and PR-AUC are not automatically applicable to a three-class
decision. They may be used only if the preregistered study defines a valid
one-versus-rest estimand and immutable continuous score. A raw score is not
confidence.

### Selective-decision evaluation

Because `WAIT` is first-class, evaluation must jointly disclose:

- directional precision;
- directional recall;
- action rate;
- abstention rate;
- `BUY`/`SELL` confusion;
- directional-to-`WAIT` and `WAIT`-to-direction errors; and
- performance over time.

No single metric may conceal the trade-off between opportunity quality and
frequency.

### Confidence and calibration

No calibration metric, probability quality metric, or confidence threshold is
approved here. If a future baseline emits numeric scores, those scores remain
internal research outputs and must not be named, stored, displayed, or
interpreted as confidence.

Calibration evaluation requires a separate approved confidence specification.

### Statistical comparison

Any comparison among approved baselines must:

- use paired predictions on identical folds and observations;
- report fold-level distributions;
- report uncertainty intervals selected before viewing results;
- predeclare the statistical test, assumptions, and effect size;
- correct for multiple comparisons under a predeclared method;
- report raw and adjusted results;
- distinguish statistical evidence from practical acceptance; and
- avoid declaring superiority when sample evidence is inadequate.

The test family, interval method, confidence level, correction method, and
minimum fold/sample requirements remain unresolved until the final metric and
split design are approved.

## Success Metrics and Acceptance Gates

### Methodological success

A research run is methodologically successful only if:

- every source, dataset, split, configuration, prediction, and result hash
  verifies;
- chronology and point-in-time checks pass;
- no protected-test evidence is accessed;
- all expected folds execute or exclusions are reported;
- repeated execution is deterministic;
- all metrics are computed exactly as preregistered;
- all adverse and null findings are retained; and
- a reviewer can reproduce the complete run.

A negative or inconclusive predictive result may still be a methodologically
successful experiment.

### Predictive success

Predictive success must be defined before experiments by:

1. one or more primary metrics;
2. required class-specific constraints;
3. comparison baselines;
4. minimum evidence and fold-stability requirements;
5. uncertainty and effect-size requirements;
6. multiplicity-adjusted acceptance rules; and
7. explicit failure conditions.

The exact primary metric, numeric threshold, minimum improvement, evidence
size, stability tolerance, and acceptance rule are unresolved. This protocol
does not invent them.

Product principles require directional opportunity quality to take precedence
over frequency, but they do not supply a numeric trade-off. A future
acceptance rule must therefore constrain both directional quality and action
rate rather than optimize either in isolation.

### Prohibited success claims

The following do not establish success by themselves:

- training-set fit;
- overall accuracy;
- high `WAIT` prevalence or recall;
- one favorable fold;
- an uncorrected p-value;
- a small metric difference without uncertainty;
- uncalibrated score magnitude;
- feature importance;
- a favorable chart example;
- backtest or trading profitability;
- protected-test iteration; or
- comparison against a weak reference chosen after results.

## Point-in-Time and Leakage Controls

Every experiment must verify:

1. feature pipeline `2.0.0` and its registry hash;
2. feature `available_at <= evidence_cutoff`;
3. label outcome begins after the prediction-origin boundary;
4. label intervals do not leak across partitions;
5. purged rows are unavailable for fitting;
6. embargo boundaries match preregistered dependencies;
7. preprocessing is fitted on training only;
8. any data-derived label threshold is fitted on training only;
9. validation is never used as training during the same selection step;
10. final-test data is isolated;
11. model selection does not access calibration or holdout outcomes;
12. repeated observations and overlapping labels are disclosed;
13. no future-active artifact replaces historical evidence; and
14. no prediction-time input contains an outcome-derived field.

Random chronological splitting is absolutely prohibited.

## Data-Snooping and Multiplicity Controls

Before execution, preregister:

- number of label policies under study;
- number of feature sets;
- number of baseline families;
- number of parameter configurations;
- primary comparisons;
- primary and secondary metrics;
- subgroup and timeframe analyses;
- statistical tests;
- multiplicity correction; and
- stopping rule.

Any unplanned analysis is exploratory and must be labeled as such. It cannot
support a confirmatory or production claim without a new protocol and fresh
protected evidence.

Failed, null, and superseded studies remain in the immutable registry.
Selective reporting is prohibited.

## Timeframe and Regime Reporting

Results must be reported separately for `5m`, `10m`, and `15m` unless pooling
has been explicitly approved.

No market-regime analysis is authorized by this protocol. A future regime
study must define each regime using only point-in-time evidence, preregister
its categories, and address reduced subgroup sample sizes and multiplicity.

Current Tier-A features do not include a complete approved regime taxonomy.

## Research Governance and Reproducibility

Every experiment record must contain:

- immutable experiment ID and version;
- research question and protocol reference;
- label-policy ID and version;
- dataset ID, version, and hash;
- feature pipeline, registry, and run identities;
- split configuration and boundary hash;
- purge and embargo configuration;
- model or baseline family;
- complete parameters;
- preprocessing definition;
- random seeds;
- code commit and dirty-state evidence;
- software and hardware-relevant versions;
- per-observation out-of-fold predictions;
- per-fold and pooled metrics;
- uncertainty, effect-size, and multiplicity results when applicable;
- runtime;
- configuration hash;
- prediction hash;
- result hash;
- creation timestamp;
- status and supersession lineage; and
- every limitation or protocol deviation.

### Determinism

Identical source artifacts, configuration, code, and seeds must reproduce:

- row identities and order;
- split boundaries;
- transformed training and validation inputs;
- predictions;
- metrics;
- configuration hash; and
- result hash.

Any nondeterministic dependency must be identified before approval. If exact
repeatability cannot be established, the limitation must be reviewed before
the experiment can support a claim.

### Audit and immutability

- Experiments are append-only.
- Existing parameters, predictions, and results are never modified.
- A correction creates a new linked record.
- Protected-test access is logged.
- Deviations are recorded, not silently repaired.
- Artifacts must remain resolvable from their recorded references.
- Fabricated, placeholder, or incomplete evidence must never be represented
  as an experiment.

## Research Review Checklist

Before execution:

- label policy approved;
- dataset protocol approved;
- class and exclusion audit reviewed;
- split boundaries frozen;
- protected test sealed;
- metrics and success gates preregistered;
- baselines and parameters fixed;
- statistical procedures fixed;
- seeds fixed;
- provenance complete; and
- explicit execution approval recorded.

After execution:

- hashes verified;
- repeatability verified;
- chronology and leakage checks passed;
- all folds and exclusions reported;
- null and adverse results retained;
- no protected-test access occurred;
- claims limited to measured evidence;
- confidence remained absent; and
- human review completed before any next phase.

## Decisions Frozen by This Protocol

The following are approved:

1. Research proceeds through explicit approval gates.
2. Label, dataset, experiment, and protected-test decisions are frozen before
   their evidence is examined.
3. Development uses purged, embargoed chronological walk-forward validation.
4. A separately sealed final test is mandatory.
5. All baselines use identical datasets, folds, and approved features.
6. Preprocessing is fitted inside training partitions only.
7. Evaluation reports class-specific quality and decision frequency.
8. Per-fold and pooled development evidence are both required.
9. Comparisons are paired and multiplicity-aware.
10. Experiments, predictions, metrics, and deviations are immutable and
    reproducible.
11. Confidence remains unavailable.
12. Research evidence does not automatically authorize a production model or
    decision policy.

## Unresolved Decisions Before Experiment Implementation

Explicit approval remains required for:

- selected label strategy and all parameters;
- protocol and dataset versions;
- timeframe-specific versus pooled study design;
- chronological split configuration;
- purge and embargo values;
- protected-test size;
- minimum sample and class-adequacy rules;
- approved baseline families;
- baseline parameters and preprocessing;
- class-imbalance handling;
- primary and secondary metrics;
- metric aggregation;
- uncertainty interval method and level;
- statistical tests and assumptions;
- effect sizes;
- multiplicity correction;
- predictive success thresholds;
- stopping rules;
- subgroup or regime analyses;
- model-selection procedure;
- one-time final-test authorization; and
- any later confidence-calibration research.

No labels, datasets, experiments, models, or protected-test evaluations may
be implemented under this document alone.
