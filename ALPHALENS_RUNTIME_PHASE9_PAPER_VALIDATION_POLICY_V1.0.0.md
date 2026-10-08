# AlphaLens Runtime Phase 9 Paper Validation Policy v1.0.0

**Policy identifier:** `alphalens_runtime_phase9_paper_validation`
**Policy version:** `1.0.0`
**Status:** Proposed — pending explicit human approval
**Scope:** Real Binance spot BTCUSDT, 5m, EMA/RSI detection, Scoring V1.1,
ranking, OpportunityPlan V1.1, and the approved 10-minute OutcomeRecord horizon

This document is a proposed confirmatory research methodology. It does not
change runtime behavior, outcome semantics, thresholds, production data, or
the approved Phase 8 Outcome Evidence Policy. It assigns no canonical policy
hash until the unresolved human decisions below are approved and frozen.

## 1. Objective

Phase 9 would determine, under a preregistered chronological evaluation, what
evidence the frozen AlphaLens runtime produces for its declared BTCUSDT 5m
opportunity population and whether a separately approved evaluation estimand
meets its preregistered acceptance rule.

Phase 9 must not be framed as proof of profitability, live-trading readiness,
execution quality, causality, confidence, or generalization beyond the frozen
population and policy versions.

## 2. Evaluation population

The candidate population is every real production opportunity-version in the
declared BTCUSDT 5m scope produced by the frozen runtime policy chain during a
predeclared UTC observation window. No favorable outcome, score, rank, time
period, market regime, or subset may be selected after outcomes are inspected.

The population definition must state whether the estimand is:

1. all qualified opportunity-versions, including opportunities excluded from
   ranking; or
2. ranking-admitted qualified opportunity-versions only.

The current 76 OutcomeRecords alone cannot answer that population decision,
because records for qualified but non-admitted opportunities are not thereby
shown to exist. The exact observation-window boundaries and population choice
require human approval.

## 3. Evaluation unit

The default candidate unit is one unique opportunity-version. Lifecycle events,
candle observations, and OutcomeRecords are evidence attached to that unit,
not additional independent observations. Duplicate retries and repeated reads
must not increase the denominator.

Successor opportunity versions are separate units only when the approved
lifecycle policy treats them as new identities and the dependence treatment is
predeclared. The final unit and dependence rule require human approval.

## 4. Runtime outcome mapping

Runtime OutcomeRecords remain immutable and are not rewritten into the v2
research vocabulary without approval.

For descriptive outcome reporting, the following mapping is proposed:

| Runtime outcome | Research treatment |
| --- | --- |
| `TARGET_HIT` | favorable terminal barrier outcome |
| `STOP_HIT` | adverse terminal barrier outcome |
| `EXPIRED_BEFORE_ENTRY` | no-entry terminal outcome |
| `EXPIRED_AFTER_ENTRY` | post-entry horizon/censoring outcome |
| `DATA_INSUFFICIENT` | unavailable/censored observation, never success or failure |

This is a descriptive preservation map, not an approved BUY/SELL/WAIT label
policy. The Labeling Specification has not selected a research label strategy,
and explicitly requires approval of outcome semantics, horizon, thresholds,
friction, ambiguity, and incomplete-future handling before label generation.
Any predictive label mapping requires a separate human decision.

## 5. Inclusion and exclusion

Candidate deterministic inclusion rules:

- real Binance spot BTCUSDT;
- 5m timeframe;
- opportunity generated under the exact frozen detection, qualification,
  scoring, ranking, and plan references;
- unique opportunity-version identity;
- complete point-in-time provenance;
- completed 10-minute outcome window or an explicitly retained terminal
  unavailable/censored state;
- valid lifecycle and OutcomeRecord linkage;
- result and policy hashes verify.

Candidate exclusions:

- synthetic, replay, test-fixture, manually inserted, or unverifiable records;
- duplicate/conflicting identities;
- policy/hash/provenance mismatch;
- records outside the frozen population window;
- records whose outcome interval is incomplete when the approved policy requires
  a complete label.

Every exclusion must remain in an immutable exclusion ledger with its identity,
reason, affected interval, evidence, and hash. No exclusion may be introduced
after reviewing its outcome merely to improve results.

## 6. Temporal validation

The evaluation must use contiguous chronological development, validation, and
protected evaluation periods. The final protected period must be chronologically
last, sealed before any model, metric, threshold, or methodology selection, and
consumed once.

For each fold:

- training precedes validation;
- preprocessing and any fitted transformation use training data only;
- outcome intervals crossing a boundary are purged from the earlier partition;
- embargo follows the approved dependency and overlap rule;
- fold membership, exclusions, and boundaries are persisted and hashed; and
- no protected result may trigger tuning or methodology revision.

The repository requires chronological walk-forward evaluation, purge, embargo,
and protected-test isolation, but does not approve exact dates, fold count,
window widths, purge duration, embargo duration, or protected-period size.
Those values require human approval. The 10-minute outcome horizon must not be
silently substituted for an embargo duration; the framework requires the
dependency rule to be established first.

## 7. Leakage control

The evaluation must verify:

- every feature has `available_at <= evidence_cutoff`;
- signal/prediction evidence precedes the outcome interval;
- no future outcome, target, barrier touch, or resolution field enters runtime
  inputs or fitted preprocessing;
- revised market or feature data is not silently substituted;
- cross-timeframe completion cannot leak future information;
- overlapping outcome intervals are identified and handled under the approved
  dependence rule;
- source/survivor selection is not informed by outcomes; and
- protected outcomes are inaccessible during selection.

## 8. Frozen policy and artifact manifest

The Phase 9 manifest must bind exact identity, version, hash, and effective
scope for every dependency:

| Dependency | Current reference | Status for Phase 9 |
| --- | --- | --- |
| Detection | `alphalens_runtime_detection_ema_rsi` `1.0.0`, hash `d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a` | Existing runtime identity; manifest freeze required |
| Scoring | `alphalens_runtime_scoring_ema_rsi` `1.1.0`, hash `825ee3c060b4badc6d3348d1731dfd0683f46a4ad12f420a5e751e040cbca81b` | Existing runtime identity; manifest freeze required |
| Ranking | `alphalens_runtime_ranking_ema_rsi` `1.1.0`, hash `9a2e4c60da1f0b80dad6de944acd3092b06f9ef6c158a48b30b356827aecd294` | Existing runtime identity; manifest freeze required |
| Opportunity Plan | Checked-in artifact identifies `alphalens_opportunity_plan_v1` `1.0.0`; requested/current production scope is described as V1.1 | Version identity and canonical hash require human resolution |
| Outcome resolution | `alphalens_outcome_resolution` `1.0.0` | Existing persisted identity; an approved canonical policy artifact/hash requires human resolution |
| Phase 8 evidence policy | `alphalens_phase8_outcome_evidence` `1.0.0`, hash `3562a18bd9a9414e9a2d691833a414f4c8ce14fef5ba6956017989ec09a9b012` | Approved/frozen |
| Code identity | Exact source commit and environment | Human approval required for manifest value |
| Model/artifact | None for current EMA/RSI scoring path unless later used | Human decision required |

No policy with missing identity/hash may be silently replaced by a latest file,
runtime default, or mutable configuration.

## 9. Metrics

The repository does not select a primary Phase 9 metric. The primary metric is
therefore **HUMAN DECISION REQUIRED**.

Candidate secondary descriptive metrics, none approved as acceptance targets,
include:

- outcome availability rate;
- `DATA_INSUFFICIENT` rate;
- target-hit and stop-hit proportions;
- no-entry and post-entry expiry proportions;
- opportunity coverage and action rate;
- temporal fold composition and stability;
- rank/outcome association only after relevance and candidate-set semantics are
  approved; and
- directional precision/recall only if an approved BUY/SELL/WAIT research label
  exists.

P&L, Sharpe, drawdown, CAGR, hit rate after costs, and similar economic metrics
are not authorized unless a separate paper-execution and risk contract is
approved.

## 10. Denominators

Every metric must name its denominator before results are examined. Candidate
denominators are:

- all eligible population units for coverage and availability;
- all units with valid evaluable outcomes for terminal-outcome proportions;
- a separately approved at-risk subset for entry-conditioned outcomes; and
- the approved prediction class or decision subset for class-specific metrics.

The treatment of `DATA_INSUFFICIENT`, post-entry censoring, overlapping units,
and missing labels changes denominators and therefore requires human approval.
No denominator may be selected after inspecting results.

## 11. Uncertainty and statistical tests

The statistical framework requires a declared estimand, dependence unit,
uncertainty method, interval interpretation, hypotheses, test family, and
multiplicity procedure. It provides candidate block/bootstrap, paired
permutation, contingency-table, and dependence-robust methods but selects none.

The uncertainty method, confidence level or other interval level, test family,
null hypotheses, effect-size interpretation, and multiplicity correction are
HUMAN DECISION REQUIRED. Serial dependence, censoring, overlapping horizons,
and nonstationarity must be addressed explicitly.

## 12. Sample adequacy

No numeric sample-size requirement is introduced. The study must predeclare an
adequacy or precision rule, effective sample support, dependence assumptions,
fold support, and failure behavior. If adequacy or precision is insufficient,
the result is inconclusive or blocked; it must not be converted into a pass by
changing the rule after inspection.

The adequacy target and precision rule require human approval.

## 13. Paper execution model

The current runtime plan is informational and does not establish executable
fills. The following items therefore require explicit approval before any
paper-trading or economic evaluation:

| Item | Current evidence | Required status |
| --- | --- | --- |
| Signal timestamp | Runtime signal/evidence cutoff exists | Exact paper availability convention requires human approval |
| Entry rule | Plan contains an informational exact-price entry region | Whether paper entry is next-candle open, reference price, or another rule requires human approval |
| Entry price | Plan reference/entry price exists | Fill convention requires human approval |
| Exit rule | Target, invalidation, and 10-minute horizon exist for outcome resolution | Paper exit/fill semantics require human approval |
| Stop/invalidation | Runtime outcome records barrier resolution | Executability and intrabar rule require human approval |
| Target | Runtime outcome records target resolution | Executability and intrabar rule require human approval |
| Horizon | Approved runtime outcome horizon is 10 minutes | Paper treatment of expiry requires human approval |
| Position sizing | Not defined for current product | Human decision required |
| Initial capital | Not defined for current product | Human decision required |
| Fees | Not defined for current product | Human decision required |
| Spread | Not defined for current product | Human decision required |
| Slippage | Not defined for current product | Human decision required |
| Market impact | Not defined for current product | Human decision required |
| Concurrency | Not defined for current product | Human decision required |
| Overlapping opportunities | Must be retained for statistical analysis; portfolio treatment is undefined | Human decision required |

The legacy daily BTC/USD Kraken paper-trading configuration cannot be imported
into this BTCUSDT 5m study.

## 14. Risk accounting

Until an execution contract is approved, results must be represented as
opportunity-level barrier outcomes and censoring states, not realized trades,
returns, or P&L.

If paper accounting is later approved, it must separately define capital,
allocation, quantity, concurrent exposure, fees, spread, slippage, market
impact, gap handling, mark price, portfolio close, drawdown, and liquidation.
Geometric risk/reward in an OpportunityPlan must not be reported as expectancy
or realized risk-adjusted performance.

## 15. Protected holdout

The latest chronologically eligible period must be sealed as a protected
evaluation period after all methodology, policy, metric, denominator,
uncertainty, adequacy, and execution decisions are frozen. It may be consumed
once, with access logged and hashed. It must not be used for tuning, subset
selection, or revising the study.

The exact protected boundary and access protocol require human approval.

## 16. Reproducibility

The experiment manifest must retain:

- immutable dataset ID, version, membership, and dataset hash;
- exact UTC scope and partition hashes;
- all policy IDs, versions, and canonical hashes;
- code commit, environment, and dependency identity;
- model/artifact identity where applicable;
- preprocessing and configuration hashes;
- random seeds where randomness is mathematically used;
- every included and excluded unit;
- predictions, outcome mappings, metrics, uncertainty, and limitations; and
- final result and report hashes.

Identical inputs and manifest must reproduce identical ordered outputs, metrics,
exclusions, and hashes. No unrecorded randomness or mutable “latest” lookup is
permitted.

## 17. Failure and null results

Adverse, null, unstable, inconclusive, unavailable, and failed runs must remain
retained and visible. A negative or inconclusive result can be a successful
methodological execution, but it is not predictive or promotion success.

Missing outcomes, `DATA_INSUFFICIENT`, empty folds, zero denominators, and
failed assumptions must produce explicit statuses such as `UNDEFINED`,
`INCONCLUSIVE`, or `BLOCKED` under the approved study rules, never fabricated
zeros or favorable exclusions.

## 18. Acceptance and promotion boundary

Phase 9 methodological acceptance requires:

1. explicit human approval of this policy and its unresolved decisions;
2. a frozen dataset and population definition;
3. a frozen label/outcome mapping and censoring rule;
4. frozen chronological partitions, purge, embargo, and protected-test rules;
5. preregistered primary/secondary metrics, denominators, uncertainty,
   multiplicity, adequacy, and acceptance rules;
6. an approved paper-execution/risk contract if economic metrics are included;
7. deterministic replay, provenance, and leakage checks; and
8. retention of all adverse, null, and inconclusive evidence.

Phase 9 can establish only the approved research estimand for the frozen scope.
It cannot automatically establish live-trading readiness, execution feasibility,
profitability, causal efficacy, calibrated confidence, or transferability to
other symbols, venues, timeframes, or policy versions.

## 19. Explicit human decisions required

Before any performance result is examined, the human approver must decide and
record:

- population: all qualified versus ranking-admitted units;
- exact UTC observation window;
- evaluation unit and dependence treatment;
- research label mapping, if any;
- `DATA_INSUFFICIENT` denominator/censoring treatment;
- partition dates, fold design, purge, embargo, and protected boundary;
- exact OpportunityPlan and outcome policy hashes;
- code/environment identity;
- one primary metric;
- secondary metric set;
- denominators;
- uncertainty interval/test family and level;
- adequacy/precision rule;
- multiplicity procedure;
- paper entry/exit/fill assumptions;
- capital, sizing, fees, spread, slippage, market impact, concurrency, and
  overlap rules; and
- promotion and failure thresholds.

Until these decisions are approved, Phase 9 is not ready for paper validation
and no performance metric may be calculated.

## 20. Governance classification table

| ITEM | SOURCE | STATUS |
| --- | --- | --- |
| Point-in-time evidence and no future inputs | Labeling Specification §§70–100; Core Intelligence §0.4 | EXISTING REQUIREMENT |
| Chronological walk-forward validation | Walk-Forward Framework §§2–6 | EXISTING REQUIREMENT |
| Purge boundary-crossing outcome intervals | Labeling Specification §410; Walk-Forward Framework §3 | EXISTING REQUIREMENT |
| Protected final evaluation isolation | Walk-Forward Framework §4; Research Protocol Gate 8 | EXISTING REQUIREMENT |
| Immutable provenance and deterministic replay | Deterministic Backtest Framework §§2–4; Dataset Specification §§1–3 | EXISTING REQUIREMENT |
| Retention of exclusions and adverse/null results | Statistical Framework §§6–7; Research Protocol §§241–258 | EXISTING REQUIREMENT |
| Explicit estimand, population, unit, denominator, and censoring | Statistical Framework §3; Metrics Framework §§1–2 | EXISTING REQUIREMENT |
| No default statistical test or uncertainty method | Statistical Framework §§4 and 11 | EXISTING REQUIREMENT |
| No default numerical adequacy or acceptance gate | Statistical Framework §10; Metrics Framework §11 | EXISTING REQUIREMENT |
| No confidence/calibration claim without separate approval | Metrics Framework §6; Confidence Policy | EXISTING REQUIREMENT |
| Treat runtime records as opportunity-version evidence units | Lifecycle Contract; Phase 8 Outcome Evidence Policy | DERIVED |
| Preserve runtime outcome categories without relabeling | Phase 8 Outcome Evidence Policy; Labeling Specification | DERIVED |
| Candidate descriptive outcome mapping | Phase 8 Outcome Evidence Policy; Metrics Framework §4 | DERIVED |
| Evaluate every unit in the chosen frozen population | Metrics Framework §§1–2; Research Protocol §3 | DERIVED |
| Use the 10-minute horizon as the runtime outcome interval | Approved runtime OutcomeRecord behavior | DERIVED |
| Exact population: all qualified or ranking-admitted | Metrics Framework; Research Protocol | HUMAN DECISION REQUIRED |
| Exact observation window | Walk-Forward Framework; Dataset Specification | HUMAN DECISION REQUIRED |
| Research label mapping to BUY/SELL/WAIT or outcome estimand | Labeling Specification §§100–124 and 479–501 | HUMAN DECISION REQUIRED |
| DATA_INSUFFICIENT denominator/censoring rule | Metrics Framework §4; Statistical Framework §3 | HUMAN DECISION REQUIRED |
| Fold dates, count, purge, embargo, and protected boundary | Walk-Forward Framework §§2, 9–10 | HUMAN DECISION REQUIRED |
| Primary metric | Metrics Framework §11; Research Protocol §§176–198 | HUMAN DECISION REQUIRED |
| Secondary metric set and multiplicity | Metrics Framework §11; Statistical Framework §5 | HUMAN DECISION REQUIRED |
| Uncertainty method, level, and statistical test | Statistical Framework §§4 and 11 | HUMAN DECISION REQUIRED |
| Sample adequacy/precision rule | Statistical Framework §§9–11 | HUMAN DECISION REQUIRED |
| OpportunityPlan version/hash | Checked-in plan artifact is 1.0.0 while requested/current scope is V1.1 and no canonical hash is recorded | HUMAN DECISION REQUIRED |
| Outcome-resolution policy hash | Persisted identity exists; approved canonical hash artifact is unresolved | HUMAN DECISION REQUIRED |
| Paper fill, cost, and risk assumptions | Legacy Paper Trading §§35–64 is separate scope | HUMAN DECISION REQUIRED |
| Promotion threshold and readiness decision | Production Readiness §§3 and 11 | HUMAN DECISION REQUIRED |
