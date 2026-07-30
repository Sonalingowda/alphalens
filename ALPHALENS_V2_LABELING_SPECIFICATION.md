# AlphaLens v2 Labeling Specification

## Status and Authority

**Phase:** Phase 4 — Research Foundation  
**Artifact type:** Research problem and candidate-label specification  
**Implementation status:** Not implemented  
**Label strategy status:** Unresolved; no candidate is selected

This document defines the AlphaLens v2 research problem and the admissible
design space for future labels. It does not authorize label generation,
dataset construction, model development, decision production, confidence, or
runtime use.

This specification is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_PHASE_1_BASELINE.md`;
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`; and
- `ALPHALENS_V2_PHASE_3_BASELINE.md`.

If a candidate definition conflicts with a frozen contract, the frozen
contract prevails and the candidate is ineligible.

## Approved Research Problem

For each eligible, completed BTC/USD observation on one approved timeframe,
the research question is:

> Using only evidence available at the observation's recorded evidence
> cutoff, can a future approved method identify whether the point-in-time
> market state supports a qualifying upward opportunity, a qualifying
> downward opportunity, or intentional abstention?

The exclusive research outcome vocabulary is:

- `BUY`;
- `SELL`; and
- `WAIT`.

These are research classes aligned with the canonical Decision Contract.
They are not orders, execution instructions, portfolio actions, guarantees,
or claims of profitability.

### Class semantics

| Class | Research meaning |
| --- | --- |
| `BUY` | The selected and approved label policy identifies a qualifying upward opportunity after the evidence cutoff. |
| `SELL` | The selected and approved label policy identifies a qualifying downward opportunity after the evidence cutoff. It never means close or exit a position. |
| `WAIT` | A valid label evaluation completes, but the approved policy identifies neither a qualifying upward nor a qualifying downward opportunity. |

`WAIT` is a first-class outcome. It is not:

- a missing label;
- an unavailable future outcome;
- insufficient source evidence;
- a failed calculation;
- an ambiguous result that the selected label policy cannot resolve;
- a data-quality failure; or
- a replacement for an operational error.

If a valid label cannot be determined under the selected policy, no label
exists for that candidate observation. Such an observation must be excluded
with a recorded reason rather than labeled `WAIT`.

## Approved Observation Semantics

Let:

- `t` be the canonical candle-open timestamp;
- `D` be the timeframe duration;
- `a(t) = t + D` be the Phase 3 feature-availability timestamp;
- `E_t` be the complete feature evidence available by `a(t)`; and
- `L(t)` be the future outcome interval used by a candidate label policy.

The candidate prediction origin is the completed observation at `t`. Feature
evidence may include candle `t`, because it becomes available only at
`a(t)`. No feature or decision is assumed available at candle open.

A future label may be calculated retrospectively for research only after all
outcomes required by `L(t)` are complete. The label's availability is
therefore later than the prediction evidence cutoff.

The separation is mandatory:

```text
feature / prediction evidence cutoff = a(t)
label outcome begins strictly after the approved prediction-origin boundary
label availability = time when the complete future outcome is observable
```

No candidate may assume same-close execution or treat the close used to
complete evidence as a price that was actionable before the decision became
available.

## Requirements for Any Selected Label Policy

Before implementation, one candidate policy must be explicitly approved and
versioned. Its specification must resolve:

1. the exact prediction origin;
2. the first eligible future observation;
3. horizon magnitude and basis;
4. outcome interval inclusivity;
5. reference-price definition;
6. upward, downward, and abstention conditions;
7. threshold values and units;
8. transaction-cost or friction assumptions, if any;
9. path-dependence rules;
10. ties and exact-boundary handling;
11. same-candle barrier ambiguity;
12. missing-future-observation handling;
13. label availability timestamp;
14. overlapping-outcome treatment;
15. end-of-series exclusions;
16. version and canonical hashing;
17. applicability by timeframe; and
18. the empirical or product rationale for the selected policy.

These values must be selected before label outcomes are inspected for model
development. They must not be chosen to improve observed model performance
or class balance.

## Candidate Labeling Strategies

The following are candidates only. Their inclusion here does not approve
their implementation or quantitative parameters.

### Candidate A — Fixed-Horizon Forward-Return Bands

#### Definition

For an approved future horizon `H`, reference-price convention
`P_reference(t)`, and future price `P_outcome(t,H)`, define a forward return:

\[
R_{t,H}
=
g\left(P_{\operatorname{reference}}(t),
P_{\operatorname{outcome}}(t,H)\right)
\]

where `g` is a predeclared arithmetic-return or log-return definition.

With approved upward and downward thresholds:

- `BUY` when the forward return meets the upward condition;
- `SELL` when it meets the downward condition; and
- `WAIT` when it lies inside the approved abstention region.

#### Strengths

- simple and auditable;
- one label per complete future horizon;
- class conditions are directly inspectable;
- supports controlled comparison across timeframes when independently
  specified.

#### Weaknesses

- ignores the path taken before the horizon;
- can label a final favorable return despite severe adverse movement;
- class balance may be highly sensitive to horizon and thresholds;
- overlapping horizons create dependent labels;
- reference-price choice materially changes meaning.

#### Required unresolved decisions

- `H` and whether it is measured in observations or elapsed time;
- arithmetic versus log return;
- future price field;
- first eligible reference price after evidence availability;
- threshold values and symmetry;
- friction treatment; and
- exact-boundary rules.

### Candidate B — Volatility-Scaled Forward-Return Bands

#### Definition

Compute a fixed-horizon future return as in Candidate A and divide or compare
it against an approved point-in-time scale `V_t` known by the evidence
cutoff:

\[
Z_{t,H} = \frac{R_{t,H}}{V_t}
\]

`BUY`, `SELL`, and `WAIT` are determined by predeclared scaled thresholds.

`V_t` must be an approved point-in-time feature or statistic. A future
volatility estimate is prohibited.

#### Strengths

- adapts label magnitude to the contemporaneous market scale;
- may reduce regime-driven variation in raw-return thresholds;
- makes explicit the distinction between move magnitude and prevailing
  variability.

#### Weaknesses

- label meaning depends on the approved scale definition;
- a near-zero or unstable denominator requires a fail-closed policy;
- no volatility-normalized Tier-A feature is currently approved;
- still ignores the path within the horizon;
- threshold and scale choices can become data-snooping channels.

#### Required unresolved decisions

- all Candidate A decisions;
- the approved point-in-time scale;
- its lookback, version, warm-up, and zero handling; and
- scaled threshold values.

This candidate cannot be implemented using an unapproved new feature.

### Candidate C — First-Touch Barrier Outcome

#### Definition

Starting strictly after the prediction evidence cutoff, observe a future path
until an approved maximum horizon. Define an upper barrier, lower barrier,
and time barrier using only predeclared rules.

- `BUY` when the upper barrier is first touched;
- `SELL` when the lower barrier is first touched;
- `WAIT` when neither price barrier is touched before the time barrier.

#### Strengths

- incorporates path and time-to-event information;
- distinguishes favorable from adverse first movement;
- naturally represents no qualifying move as `WAIT`;
- can align with opportunity-oriented rather than candle-oriented research.

#### Weaknesses

- OHLC candles may not reveal which barrier was touched first when both are
  crossed within one candle;
- results are sensitive to barrier width and maximum horizon;
- overlapping path intervals create dependence;
- fixed barriers behave differently across volatility regimes;
- it may require finer-grained data to resolve intrabar ordering.

#### Required unresolved decisions

- first eligible future candle;
- reference price;
- upper, lower, and time barriers;
- fixed versus point-in-time-scaled barriers;
- whether barriers are symmetric;
- high/low versus close touch rules;
- gap handling;
- same-candle dual-touch ambiguity;
- ties and exact-boundary rules; and
- label availability at first touch or time expiry.

An unresolved dual-touch observation must be excluded, not silently assigned
to a class.

### Candidate D — Directional Opportunity With Adverse-Excursion Constraint

#### Definition

Evaluate future favorable and adverse excursion over an approved horizon
relative to an approved post-cutoff reference price.

- `BUY` requires an approved upward excursion condition while remaining
  within an approved adverse-excursion condition;
- `SELL` requires the corresponding downward condition;
- `WAIT` applies when neither directional opportunity condition is met.

#### Strengths

- distinguishes endpoint return from path quality;
- can represent an opportunity that achieves a meaningful move without an
  excessive adverse path;
- exposes the relationship among horizon, favorable move, and adverse move.

#### Weaknesses

- multiple thresholds increase multiplicity and overfitting risk;
- OHLC data limits intrabar path reconstruction;
- it can become an implicit trading-plan label if entry and risk semantics
  are not carefully separated;
- class meaning is sensitive to reference price and excursion definitions.

#### Required unresolved decisions

- future horizon;
- reference-price convention;
- favorable and adverse excursion fields;
- directional and adverse thresholds;
- dual-direction qualification handling;
- intrabar ambiguity; and
- whether outcome timing is part of the label.

This candidate remains descriptive research. It does not authorize entry,
stop-loss, take-profit, or execution logic.

### Candidate E — Two-Stage Direction and Opportunity Qualification

#### Definition

Define two independently specified retrospective questions:

1. Did a qualifying opportunity occur?
2. If so, was its approved direction upward or downward?

Map the joint result to:

- qualifying upward opportunity → `BUY`;
- qualifying downward opportunity → `SELL`;
- no qualifying opportunity → `WAIT`.

An observation for which direction is unresolved under the approved policy
has no label.

#### Strengths

- makes abstention explicit instead of treating it as residual noise;
- separates opportunity quality from direction;
- supports future research into selective decision systems;
- can make class-generation assumptions more transparent.

#### Weaknesses

- requires two complete quantitative definitions;
- errors and selection bias can propagate between stages;
- the qualifying-opportunity definition can conceal subjective thresholds;
- evaluating a staged method requires both joint and component diagnostics.

#### Required unresolved decisions

- opportunity event;
- direction event;
- horizons for both events;
- whether the events share the same path;
- ordering when both directions qualify;
- threshold and tie rules; and
- evaluation of the joint mapping.

### Candidate F — Friction-Aware Directional Outcome

#### Definition

Apply an approved, immutable friction allowance to an otherwise approved
forward-return or path-based candidate. A directional class requires the
future move to exceed the applicable friction-aware condition; otherwise the
label is `WAIT`.

#### Strengths

- prevents economically negligible moves from automatically becoming
  directional research labels;
- makes any cost assumption explicit and versioned;
- may better align label semantics with the product's emphasis on opportunity
  quality.

#### Weaknesses

- AlphaLens is not an execution system and currently has no approved v2
  transaction-cost model;
- costs differ by venue, order type, size, and time;
- invented costs would create fabricated precision;
- a cost assumption can become stale and scope-specific.

#### Required unresolved decisions

- the underlying directional candidate;
- whether friction is appropriate for the non-execution product;
- venue and market scope;
- components and units of friction;
- effective dates and versioning; and
- whether a valid evidence source exists.

This candidate must remain unavailable unless a separate friction
specification is approved. No v1 backtesting cost assumption transfers
automatically to v2 research.

## Candidate Comparison Dimensions

Before selecting a label strategy, the design review must compare candidates
without training a predictive model. The comparison must address:

| Dimension | Required assessment |
| --- | --- |
| Semantic alignment | Whether labels represent the approved upward, downward, and abstention meanings. |
| Point-in-time integrity | Whether prediction evidence ends before all outcome evidence. |
| Actionability assumptions | Whether the reference-price rule assumes unavailable execution. |
| Path sensitivity | Whether intermediate adverse or favorable movement matters. |
| Intrabar ambiguity | Whether available OHLC granularity can determine the outcome. |
| Horizon overlap | Degree and treatment of dependent adjacent labels. |
| Regime sensitivity | Dependence of class meaning on volatility or price scale. |
| Sample efficiency | Number of valid labels after warm-up, horizon, gaps, and ambiguity exclusions. |
| Stability | Sensitivity of class counts to reasonable predeclared parameter variations. |
| Explainability | Whether a reviewer can reconstruct every class from source evidence. |
| Product fit | Whether `WAIT` represents intentional non-opportunity rather than a residual artifact. |

Descriptive class counts, exclusions, and temporal coverage may be examined
only after a candidate and its parameters have been preregistered for that
comparison. They must not be used iteratively to tune thresholds without a
new versioned protocol and fresh protected evidence.

## Label Point-in-Time and Leakage Rules

Every future implementation must enforce:

1. prediction features have `available_at <= evidence_cutoff`;
2. the label outcome begins after the approved prediction-origin boundary;
3. label values are never included in features;
4. future outcome fields are never retained as model inputs;
5. label availability is explicit;
6. a training observation is usable only when its complete label was
   available before the relevant validation boundary;
7. observations whose label intervals cross a split boundary are purged from
   the earlier partition;
8. overlapping labels are identified and handled under a predeclared policy;
9. thresholds estimated from data are fitted only within the applicable
   training partition;
10. protected validation or test outcomes never influence label-policy
    selection;
11. revised market or feature evidence is not substituted silently; and
12. end-of-series observations without a complete future horizon are
    excluded with an auditable reason.

Labels are retrospective research evidence. Their later availability does
not make them permissible at prediction time.

## Label Identity and Audit Requirements

Every future label artifact must record:

- stable label-policy identifier and semantic version;
- exact candidate strategy;
- complete quantitative definition and parameters;
- instrument and timeframe;
- prediction timestamp;
- evidence cutoff;
- label-outcome interval start and end;
- label availability timestamp;
- class value;
- source candle identities and ingestion provenance;
- source feature-run identity and pipeline version;
- dataset and source hashes;
- exclusion or ambiguity reason when no label exists;
- code version;
- configuration hash;
- result hash;
- generation timestamp; and
- supersession lineage.

Label records are immutable. A changed definition or parameter creates a new
policy version and new records; it never rewrites historical labels.

## Decisions Frozen by This Specification

The following research decisions are approved:

1. The research output domain is exactly `BUY`, `SELL`, or `WAIT`.
2. `BUY` and `SELL` represent upward and downward opportunities,
   respectively, not execution actions.
3. `WAIT` is an intentional, valid abstention outcome.
4. Failure, missing evidence, ambiguity unresolved by policy, and incomplete
   future outcomes are not `WAIT`.
5. Prediction evidence is bounded by explicit Phase 3 availability.
6. Label outcomes occur strictly after the prediction-origin boundary.
7. Same-close execution assumptions are prohibited.
8. Labels require immutable versions, complete provenance, explicit
   availability, and deterministic reproduction.
9. Split-boundary label overlap must be purged.
10. No candidate labeling strategy is selected by this document.

## Unresolved Decisions Before Label Implementation

Explicit approval is still required for:

- the selected candidate strategy;
- horizon and horizon basis;
- prediction reference price;
- outcome price or path fields;
- return definition;
- thresholds and units;
- fixed versus point-in-time-scaled conditions;
- friction assumptions;
- tie and exact-boundary conventions;
- dual-touch and other intrabar ambiguity;
- overlapping-label treatment;
- incomplete-future-data policy beyond exclusion;
- per-timeframe versus shared label policies;
- label-policy version;
- class-distribution adequacy rules; and
- any relationship between research labels and a later production decision
  policy.

No label generation may begin until these decisions are frozen in an
explicitly approved quantitative label-policy artifact.
