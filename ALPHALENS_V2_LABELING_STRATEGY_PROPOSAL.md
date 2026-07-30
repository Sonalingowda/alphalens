# AlphaLens v2 Labeling Strategy Proposal

## Status and Authority

**Phase:** Phase 4 — Labeling Strategy Research  
**Artifact type:** Candidate strategy evaluation  
**Implementation status:** Not implemented  
**Selection status:** No strategy selected

This document evaluates the six candidate labeling strategies defined in
`ALPHALENS_V2_LABELING_SPECIFICATION.md`. It does not add a candidate, select
a winner, authorize a label policy, generate labels, construct a dataset, or
authorize model research.

This proposal is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_PHASE_3_BASELINE.md`;
- `ALPHALENS_V2_LABELING_SPECIFICATION.md`;
- `ALPHALENS_V2_DATASET_SPECIFICATION.md`; and
- `ALPHALENS_V2_RESEARCH_PROTOCOL.md`.

The approved output vocabulary remains exactly `BUY`, `SELL`, and `WAIT`.
`WAIT` is valid abstention, not missing data, ambiguity, or failure. No class
means that AlphaLens executes or recommends automatic execution of a trade.

## Evaluation Boundary

This is a design comparison based on the semantics and evidence available in
the repository. No outcome distribution, label count, class balance,
predictive relationship, or model performance has been measured.

The evaluation therefore distinguishes:

- **structural properties**, which follow from a candidate definition;
- **expected effects**, which are hypotheses requiring later evidence; and
- **unresolved choices**, which require human approval before implementation.

Terms such as “may,” “could,” and “expected” describe research hypotheses,
not measured findings.

## Common Point-in-Time Requirements

For every candidate:

- `t` is the canonical candle-open timestamp;
- `D` is the timeframe duration;
- approved Phase 3 features become available at `a(t) = t + D`;
- the evidence cutoff is no earlier than `a(t)`;
- the future outcome interval begins after the approved prediction-origin
  boundary;
- the label becomes available only when all required future evidence is
  complete; and
- the label is retrospective research evidence, never a prediction-time
  input.

No candidate may:

- use an incomplete candle;
- use the completed candle close as an assumed same-close execution price;
- use future volatility as a prediction-time scale;
- convert an unresolved outcome to `WAIT`;
- learn thresholds from validation or protected-test outcomes;
- cross a chronological split boundary without purging; or
- expose outcome-derived fields to a model.

## Evaluation Dimensions

Candidates are compared on:

1. alignment with upward, downward, and abstention semantics;
2. required future data;
3. point-in-time validity;
4. path awareness;
5. sensitivity to horizon and thresholds;
6. intrabar ambiguity;
7. expected class and sample effects;
8. leakage exposure;
9. computational complexity;
10. auditability;
11. dependence on unapproved features or external evidence; and
12. risk of encoding execution or trading assumptions into a non-execution
    product.

## Candidate A — Fixed-Horizon Forward-Return Bands

### Description

Candidate A compares an approved future price with an approved reference
price over a fixed horizon `H`. A predeclared return function produces a
future return:

\[
R_{t,H}
=
g\left(
P_{\operatorname{reference}}(t),
P_{\operatorname{outcome}}(t,H)
\right)
\]

An upward band maps to `BUY`, a downward band maps to `SELL`, and the
predeclared middle band maps to `WAIT`.

The strategy is endpoint-based. It does not use the intervening path except
to establish that the required observations exist.

### Required future information

- an approved first eligible reference price after the evidence cutoff;
- the approved outcome observation at horizon `H`;
- the required future price field, such as an approved open or close;
- complete candles through the horizon; and
- timestamps proving the outcome is strictly later than prediction evidence.

### Point-in-time validity

The strategy is point-in-time valid when:

- prediction features stop at the evidence cutoff;
- the reference-price convention does not assume unavailable same-close
  execution;
- `R(t,H)` is used only as a retrospective label;
- label availability is the availability time of the complete horizon
  outcome; and
- crossing label intervals are purged at every split.

### Advantages

- mathematically compact;
- straightforward to reconstruct and audit;
- deterministic under fixed price, horizon, threshold, and boundary rules;
- produces at most one class for each complete horizon;
- has limited intrabar ambiguity when the outcome uses one declared field;
- makes horizon and abstention-band sensitivity visible.

### Disadvantages

- ignores whether the path first moved strongly in the opposite direction;
- an endpoint may conceal large favorable or adverse excursions;
- neighboring labels overlap when `H > 1`;
- results may change materially with reference price, horizon, return type,
  and threshold;
- a fixed raw-return band may have different meaning across volatility
  regimes and timeframes.

### Potential leakage risks

- using candle `t` close as though it were actionable before `a(t)`;
- shifting the future target by the wrong number of observations;
- including `R(t,H)` or its components as features;
- selecting `H` or thresholds after inspecting class balance or model
  results;
- fitting thresholds globally before chronological splitting;
- retaining training rows whose horizon crosses into validation/test;
- using revised future prices not present in the frozen source evidence.

### Expected impact on `BUY`/`SELL`/`WAIT` quality

- Directional labels may be transparent because they depend on a signed
  endpoint move.
- A wider abstention band is expected to increase `WAIT` frequency and may
  concentrate directional labels on larger endpoint moves.
- A narrower band is expected to increase directional frequency but may
  classify small, noisy movements as opportunities.
- Because path quality is absent, directional labels may not distinguish
  smooth moves from paths with materially adverse interim behavior.

These effects have not been measured.

### Computational complexity

- Time: `O(n)` for fixed observation horizon and direct indexed access.
- Memory: `O(H)` for a streaming implementation or `O(n)` for a materialized
  series.
- Hashing and audit serialization remain `O(n)`.

### Research risks

- threshold tuning can become an unreported search over class balance;
- endpoint semantics may be too weak for “opportunity quality”;
- multiple horizon comparisons create multiplicity;
- highly overlapping labels reduce effective sample independence;
- apparent stability may be specific to one volatility regime.

## Candidate B — Volatility-Scaled Forward-Return Bands

### Description

Candidate B uses the Candidate A future return but evaluates it relative to a
point-in-time scale `V_t`:

\[
Z_{t,H} = \frac{R_{t,H}}{V_t}
\]

Predeclared positive and negative scaled bands map to `BUY` and `SELL`; the
middle region maps to `WAIT`.

The scale must be fully available by the evidence cutoff and must itself be
an approved, versioned feature or statistic.

### Required future information

- all Candidate A future outcome evidence;
- no future value for `V_t`; and
- only the future endpoint required for `R(t,H)`.

The additional volatility scale is prediction-time evidence, not future
information.

### Point-in-time validity

The strategy is point-in-time valid only when:

- `V_t.available_at <= evidence_cutoff`;
- `V_t` is computed without future candles;
- its warm-up is complete;
- the denominator and zero policy are predeclared;
- future return evidence is isolated as in Candidate A; and
- per-split threshold estimation, if approved at all, uses training only.

No qualifying volatility-normalized Tier-A feature exists in the frozen
Phase 3 registry. Candidate B is therefore not implementable under the
current feature baseline without a separately approved Phase 3 change or a
separately governed point-in-time label scale.

### Advantages

- directional thresholds can adapt to the volatility scale known at the
  prediction origin;
- may make label magnitude more comparable across changing market
  variability;
- makes scale assumptions explicit instead of embedding them in timeframe-
  specific raw thresholds;
- could reduce the tendency of high-volatility periods to dominate
  directional labels.

### Disadvantages

- label semantics depend on two quantitative definitions rather than one;
- the scale introduces warm-up and missing-value exclusions;
- near-zero or unstable `V_t` requires explicit fail-closed handling;
- a mis-specified scale can amplify noise;
- endpoint path blindness remains;
- the current registry cannot supply the required normalized scale.

### Potential leakage risks

- using realized volatility measured over the future outcome interval;
- calculating `V_t` from a centered or full-series window;
- normalizing with statistics fitted on validation/test data;
- choosing the scale or scaled bands after viewing outcomes;
- silently recomputing `V_t` under a later feature version;
- transferring thresholds across timeframes without evidence.

### Expected impact on `BUY`/`SELL`/`WAIT` quality

- Directional labels may be more selective relative to the local market
  scale than raw fixed bands.
- `WAIT` may represent moves small relative to contemporaneous variability
  rather than small in absolute return terms.
- A poor or unstable scale may reduce class consistency and create
  unexplained omissions.
- Whether scaling improves opportunity quality or merely changes prevalence
  is unresolved and requires evidence.

### Computational complexity

- Future-return computation: `O(n)`.
- Point-in-time scale computation: `O(n)` for a fixed rolling or recursive
  definition, subject to the separately approved formula.
- Memory: `O(H + W)` for horizon `H` and scale history `W`, or the state
  required by an approved recursive estimator.

### Research risks

- requires governance beyond the frozen Tier-A feature set;
- scale/threshold combinations expand the research search space;
- different volatility definitions can produce materially different labels;
- regime adaptation can be mistaken for empirical improvement before model
  evidence exists;
- future-volatility leakage is easy to introduce through careless
  normalization.

## Candidate C — First-Touch Barrier Outcome

### Description

Candidate C observes the post-cutoff price path until an approved maximum
horizon. An upper barrier, lower barrier, and time barrier are fixed by the
approved policy:

- upper barrier touched first → `BUY`;
- lower barrier touched first → `SELL`;
- neither price barrier touched before expiry → `WAIT`.

The strategy is path-dependent and event-timed.

### Required future information

- the first eligible future reference price;
- every complete future candle through the first barrier touch or time
  expiry;
- future highs and lows, or another explicitly approved touch field;
- exact timestamps of qualifying touches; and
- evidence sufficient to resolve which event occurred first.

### Point-in-time validity

The strategy is point-in-time valid when:

- barriers are determined entirely from predeclared rules and evidence
  available at the prediction origin;
- barrier levels do not incorporate future volatility or extrema;
- outcome scanning begins strictly after the prediction-origin boundary;
- the label becomes available only at first resolved touch or expiry;
- overlapping outcome intervals are recorded and purged; and
- unresolved intrabar ordering produces exclusion, not an invented class.

### Advantages

- includes the order in which directional outcomes occur;
- gives `WAIT` a direct time-expiry meaning;
- can distinguish paths that endpoint returns treat identically;
- aligns naturally with a research question about qualifying opportunities
  emerging within a bounded future interval;
- supports explicit time-to-event audit evidence.

### Disadvantages

- OHLC candles do not reveal intrabar ordering when both barriers are crossed
  in one candle;
- labels depend strongly on barrier size and time horizon;
- gaps can cross barriers without revealing an exact touch price;
- future intervals have variable label availability;
- adjacent observations often share much of the same future path;
- scaled barriers would add the unresolved Candidate B dependency.

### Potential leakage risks

- constructing barriers from future range or volatility;
- using the current candle's high/low after treating the prediction as
  available before close;
- resolving same-candle dual touches using a favorable assumption;
- leaking time-to-event or barrier identity into features;
- failing to purge variable-length outcome intervals;
- selecting barriers after observing touch frequencies;
- treating unresolved paths as `WAIT`.

### Expected impact on `BUY`/`SELL`/`WAIT` quality

- Directional labels may better reflect which opportunity appeared first.
- `WAIT` has a clear “no barrier before expiry” interpretation.
- Dual-touch and gap exclusions may reduce sample size.
- Narrow barriers may create frequent direction labels sensitive to candle
  noise.
- Wide barriers or short expiry may increase `WAIT`.
- The quality impact cannot be established without an approved ambiguity
  policy and descriptive label audit.

### Computational complexity

- Naive time: `O(nH)` for maximum horizon `H`.
- Optimized event scanning may reduce practical cost, but remains dependent
  on barrier semantics.
- Memory: `O(H)` per active streaming window; overlapping origins can require
  multiple active states.

### Research risks

- intrabar ambiguity can create systematic label bias;
- many barrier/horizon combinations create a large multiplicity burden;
- overlapping events reduce effective sample independence;
- an apparently intuitive barrier policy can encode unapproved trading-plan
  assumptions;
- insufficient candle granularity may make the research question
  unidentifiable for some observations.

## Candidate D — Directional Opportunity With Adverse-Excursion Constraint

### Description

Candidate D evaluates the maximum favorable and adverse movement after the
prediction origin over an approved horizon. A direction qualifies only when
its favorable-excursion requirement is met without violating its adverse-
excursion constraint.

- qualifying upward path → `BUY`;
- qualifying downward path → `SELL`;
- neither qualifies → `WAIT`;
- a path for which both qualify or temporal ordering is unresolved has no
  label unless an approved rule resolves it.

### Required future information

- approved post-cutoff reference price;
- complete future highs and lows through the horizon;
- maximum favorable and adverse excursion by direction;
- timestamps or ordering evidence if the policy depends on sequence; and
- complete evidence for dual-direction qualification handling.

### Point-in-time validity

The strategy is point-in-time valid when:

- reference price and thresholds are fixed before future outcomes;
- all excursion fields are used only in retrospective labels;
- no future excursion statistic enters prediction features;
- label availability occurs after the complete horizon unless the approved
  policy defines an earlier fully resolved terminal event;
- ambiguous order is excluded or resolved by a predeclared conservative rule;
- crossing outcome intervals are purged.

### Advantages

- directly represents both opportunity magnitude and adverse path;
- differentiates endpoint-equivalent paths;
- may make directional labels more selective than return bands;
- can expose why a future move did or did not qualify;
- provides richer audit evidence for path quality.

### Disadvantages

- requires several thresholds and boundary conventions;
- OHLC extrema do not provide exact path ordering;
- both directions can qualify within one horizon;
- `WAIT` meaning can become complex;
- multiple constraints can reduce sample size;
- can drift toward an entry/stop research construct outside the current
  non-execution product boundary.

### Potential leakage risks

- including future maximum favorable/adverse excursion as features;
- selecting thresholds from full-period excursion distributions;
- using future extrema to establish the reference scale;
- resolving dual qualification using later endpoint direction;
- failing to purge the full horizon;
- tuning constraints to retain desirable class proportions.

### Expected impact on `BUY`/`SELL`/`WAIT` quality

- Directional classes may exclude paths with large adverse movement.
- `WAIT` may capture both insufficient favorable movement and excessive
  adverse movement unless the policy preserves reason codes.
- Stricter constraints are expected to reduce directional frequency.
- Whether stricter path quality improves learnability or produces sparse,
  unstable classes is unresolved.
- Separate exclusion and `WAIT` reasons are essential to prevent semantic
  ambiguity.

### Computational complexity

- Naive time: `O(nH)` for horizon `H`.
- Rolling extrema can improve fixed-window calculations, but direction-
  specific ordering rules may retain additional complexity.
- Memory: `O(H)` or the state needed for approved rolling extrema.

### Research risks

- high parameter dimensionality and data snooping;
- hidden execution assumptions;
- reduced effective sample size;
- intrabar ordering bias;
- conflating opportunity absence with risk-rule failure;
- difficult comparison across timeframes without separately approved scaling.

## Candidate E — Two-Stage Direction and Opportunity Qualification

### Description

Candidate E decomposes labeling into:

1. whether an approved qualifying opportunity occurred; and
2. its approved direction if an opportunity occurred.

The joint mapping is:

- qualifying upward opportunity → `BUY`;
- qualifying downward opportunity → `SELL`;
- no qualifying opportunity → `WAIT`.

If the opportunity qualifies but direction cannot be resolved, no label
exists unless the approved policy defines a deterministic resolution.

### Required future information

The required information depends on the two selected sub-policies and may
include:

- fixed-horizon outcome prices;
- future high/low paths;
- barrier events;
- favorable/adverse excursion;
- opportunity completion time; and
- directional completion time.

Both stages require explicit outcome intervals and availability timestamps.

### Point-in-time validity

The strategy is point-in-time valid when:

- both sub-policies use only post-cutoff outcome evidence;
- their definitions and order are preregistered;
- no second-stage result leaks into prediction features or first-stage
  training;
- stage-specific thresholds are fit only on applicable training evidence if
  data-derived thresholds are ever approved;
- the joint label becomes available only when both required outcomes are
  resolved; and
- split purging covers the union of both outcome intervals.

### Advantages

- makes opportunity qualification explicit rather than defining `WAIT` only
  as a numerical middle band;
- separates selectivity from direction conceptually;
- can support diagnostics for opportunity detection and directional
  classification;
- aligns with the product principle that quality matters more than signal
  frequency;
- preserves a direct role for abstention.

### Disadvantages

- requires two complete, compatible policies;
- joint behavior can be harder to explain than a single rule;
- first-stage errors constrain the second-stage sample;
- staged class balance may become sparse;
- two horizons or event definitions complicate purge and availability;
- it does not specify what constitutes an opportunity.

### Potential leakage risks

- defining opportunity quality using outcomes later reused to select the
  directional rule;
- training or evaluating the second stage on a sample selected with protected
  outcomes;
- inconsistent fold-specific opportunity filtering;
- exposing stage-one future outcomes as stage-two prediction inputs;
- choosing the two-stage structure after comparing it with single-stage model
  results;
- inadequate purge for the longer stage interval.

### Expected impact on `BUY`/`SELL`/`WAIT` quality

- `WAIT` may have the clearest intentional-abstention role if opportunity
  qualification is defensible.
- Directional quality may benefit from restricting direction assessment to
  qualifying opportunities.
- Error propagation may reduce overall quality even if each stage appears
  reasonable separately.
- Stage-specific sample sizes may be inadequate.
- Joint, stage-one, and stage-two metrics would all be required to understand
  quality.

### Computational complexity

- At minimum, the sum of both selected sub-policy costs.
- Fixed-horizon sub-policies can remain `O(n)`.
- Path-based sub-policies can be `O(nH)` naively.
- Audit and storage complexity is higher because stage results and the joint
  mapping must all remain reproducible.

### Research risks

- hidden selection bias between stages;
- multiplicity across two policy definitions;
- insufficient directional observations after qualification;
- inconsistent `WAIT` meaning if opportunity and direction rules overlap;
- premature architectural commitment to a staged predictive system.

## Candidate F — Friction-Aware Directional Outcome

### Description

Candidate F wraps an approved directional candidate with an approved friction
allowance. A future directional outcome must exceed the applicable friction-
aware condition; otherwise the valid result is `WAIT`.

This candidate does not independently define direction. It depends on another
candidate and a separately governed friction specification.

### Required future information

- all future information required by the underlying candidate;
- no future market information for the friction value unless the friction
  policy explicitly defines point-in-time variation;
- immutable evidence supporting venue, fee, spread, slippage, and other
  approved friction components; and
- effective dates defining which friction artifact applies.

### Point-in-time validity

The strategy is point-in-time valid only when:

- the friction artifact is known and applicable at the prediction origin;
- it is not estimated from the future outcome interval;
- the underlying candidate is independently point-in-time valid;
- friction changes are versioned rather than backfilled;
- label availability follows the underlying future outcome; and
- no execution result is used to label a non-executed opportunity.

### Advantages

- can prevent negligible moves from automatically becoming directional
  labels;
- makes friction assumptions explicit and auditable;
- may align directional qualification with a minimum move beyond stated
  costs;
- discourages claims based on gross moves too small to distinguish from
  assumed friction.

### Disadvantages

- AlphaLens v2 is explicitly not a broker, execution system, paper-trading
  system, or portfolio manager;
- no approved v2 friction source or policy exists;
- venue, order type, size, spread, and slippage materially affect friction;
- a single value may imply false precision;
- the candidate inherits all weaknesses of its underlying strategy;
- using v1 backtesting assumptions would violate the migration boundary.

### Potential leakage risks

- estimating slippage from future executions or future spreads;
- selecting friction after viewing returns;
- using current best-case venue costs without point-in-time provenance;
- silently changing cost assumptions over history;
- applying a cost model outside its size, venue, or time scope;
- conflating a friction-adjusted research class with an executable trade.

### Expected impact on `BUY`/`SELL`/`WAIT` quality

- Directional frequency is expected to fall relative to the underlying gross
  strategy.
- `WAIT` is expected to include moves that do not exceed approved friction.
- Label quality may improve only if the friction model is relevant and
  defensible.
- A fabricated or stale friction assumption may reduce validity more than it
  improves semantics.
- No impact can be assessed until a valid evidence source and product
  rationale are approved.

### Computational complexity

- Underlying candidate cost plus `O(n)` friction lookup and comparison.
- Additional provenance resolution is required when friction varies over
  time or scope.
- Complexity is dominated by the underlying label strategy.

### Research risks

- conflict with the non-execution product boundary;
- fabricated economic precision;
- external evidence availability and licensing;
- historical point-in-time reconstruction difficulty;
- parameter staleness;
- accidental reuse of deprecated v1 trading assumptions.

## Objective Cross-Candidate Comparison

| Dimension | A: Fixed return | B: Scaled return | C: First touch | D: Excursion constraint | E: Two stage | F: Friction aware |
| --- | --- | --- | --- | --- | --- | --- |
| Core outcome form | Endpoint | Scaled endpoint | First event | Path extrema and constraints | Joint opportunity and direction | Underlying candidate plus friction |
| Path-aware | No | No | Yes | Yes | Depends on sub-policies | Depends on underlying policy |
| Native `WAIT` meaning | Return inside band | Scaled return inside band | No touch before expiry | No qualifying constrained path | No qualifying opportunity | Directional move below friction condition |
| Future fields | Approved outcome price | Outcome price | Future highs/lows or touch field | Future highs/lows | Depends on both stages | Underlying fields |
| Variable label availability | Usually no for fixed horizon | Usually no for fixed horizon | Yes | Usually horizon-end unless terminal rules exist | Depends on stages | Depends on underlying policy |
| Intrabar ambiguity | Low if one endpoint field is used | Low if one endpoint field is used | High with high/low touches | Medium to high | Depends on stages | Inherited |
| Parameter burden | Moderate | High | High | High | Very high | High plus external evidence |
| Additional feature dependency | None structurally | Approved point-in-time scale | None for fixed barriers | None for fixed thresholds | Depends on stages | Separate friction artifact |
| Current Phase 3 compatibility | Uses existing market evidence | Blocked unless scale is separately approved | Uses existing OHLCV, subject to ambiguity | Uses existing OHLCV, subject to ambiguity | Depends on selected sub-policies | Blocked by absent v2 friction policy |
| Naive computational cost | `O(n)` | `O(n)` plus scale | `O(nH)` | `O(nH)` | Sum of stages | Underlying cost plus `O(n)` |
| Overlap dependence | Horizon-dependent | Horizon-dependent | Event/horizon-dependent | Horizon-dependent | Union of stage intervals | Inherited |
| Execution-assumption risk | Reference-price choice | Reference and scale choices | Barrier interpretation | High if treated as stop logic | Depends on stages | Highest |
| Primary research concern | Endpoint path blindness | Scale governance and leakage | Intrabar ordering | Parameter multiplicity | Selection bias between stages | Evidence validity and product boundary |

## Quality Trade-Off Summary

No candidate dominates every dimension.

- Endpoint candidates minimize path and computational complexity but omit
  interim path quality.
- Scaled labels may improve comparability across volatility states but require
  additional approved point-in-time evidence.
- Path-dependent candidates express richer opportunity semantics but increase
  ambiguity, overlap, parameter burden, and effective-sample concerns.
- A staged candidate gives `WAIT` an explicit opportunity-qualification role
  but adds selection and joint-evaluation risk.
- A friction-aware candidate may filter economically negligible moves but is
  currently unsupported by an approved v2 friction evidence contract and has
  the greatest risk of crossing the non-execution product boundary.

The correct trade-off depends on human-approved meaning, available evidence,
and preregistered research priorities. It cannot be decided from structural
analysis alone.

## Recommendation Matrix

This matrix does not rank candidates or recommend a winner. It identifies the
minimum research action required before each could be considered for
implementation approval.

| Candidate | Current disposition | Required next research action | Blocking human decisions | Evidence needed before implementation |
| --- | --- | --- | --- | --- |
| A — Fixed-horizon return bands | Eligible for quantitative specification review; not approved | Freeze reference price, return type, horizon, bands, and boundary rules | Opportunity horizon and what constitutes a meaningful directional endpoint move | Predeclared sensitivity design, expected overlap, source-field availability, and class-adequacy plan |
| B — Volatility-scaled return bands | Conditionally researchable; not approved | Define and govern the point-in-time scale before label parameters | Whether Phase 3 may be extended or a label-only scale may exist; scale formula and zero policy | Approved scale provenance, warm-up, stability rationale, and leakage analysis |
| C — First-touch barrier | Conditionally researchable; not approved | Resolve OHLC intrabar ambiguity and barrier semantics | Touch fields, dual-touch policy, barriers, expiry, gaps, and scaling | Ambiguity-rate audit plan, granularity sufficiency assessment, overlap plan |
| D — Adverse-excursion constraint | Conditionally researchable; not approved | Separate opportunity semantics from execution/risk semantics | Excursion definitions, thresholds, ordering, dual qualification, and product-boundary interpretation | Path ambiguity assessment, threshold multiplicity plan, exclusion and `WAIT` taxonomy |
| E — Two-stage qualification | Conceptually researchable after sub-policies; not approved | Specify opportunity and direction policies independently before joint mapping | Stage definitions, horizons, mapping, conflict rules, and stage-wise evaluation | Stage sample-adequacy plan, selection-bias controls, union-interval purge design |
| F — Friction-aware outcome | Blocked pending separate evidence and product decision; not approved | Determine whether friction belongs in v2 research and whether defensible evidence exists | Product applicability, venue/scope, friction components, versioning, and evidence authority | Approved friction contract, point-in-time history, applicability validation, underlying label policy |

“Eligible” and “conditionally researchable” mean only that a candidate can
proceed to a more precise design review. They do not authorize label
generation or imply comparative preference.

## Human Approvals Required Before Implementation

The following questions require explicit human decisions.

### Research meaning

1. What observable future event constitutes a qualifying upward opportunity?
2. What observable future event constitutes a qualifying downward
   opportunity?
3. What exact event constitutes valid `WAIT` rather than exclusion?
4. Should opportunity quality depend only on an endpoint, or also on the
   intervening path?
5. Should opportunity qualification be a single policy or a two-stage policy?

### Time and price reference

6. What is the first eligible future observation after evidence becomes
   available?
7. What reference price is permitted without a same-close execution
   assumption?
8. What horizon applies, and is it measured in observations or elapsed time?
9. Is the horizon shared across `5m`, `10m`, and `15m`, or independently
   specified?
10. Which future price or path fields define outcomes?

### Quantitative class boundaries

11. Are class boundaries fixed, asymmetric, scaled, path-based, or staged?
12. What are the exact thresholds, units, and equality conventions?
13. If scaling is used, what approved point-in-time scale applies?
14. How are zero, near-zero, missing, or unstable scales handled?
15. Is friction relevant to this non-execution product, and if so, what
    immutable evidence is authoritative?

### Ambiguity and missing evidence

16. How are upper/lower barrier touches in the same candle handled?
17. How are gaps across barriers handled?
18. How are paths satisfying both directional conditions handled?
19. Which unresolved observations are excluded rather than labeled `WAIT`?
20. What stable exclusion and limitation taxonomy applies?

### Chronology and research design

21. How are overlapping label intervals treated?
22. What purge and embargo rules follow from the selected outcome interval?
23. What end-of-series policy applies?
24. What descriptive sensitivity analysis may occur without becoming
    threshold tuning?
25. What sample and class-adequacy requirements must be satisfied before
    dataset construction or model research?

### Governance

26. What is the approved label-policy identifier and semantic version?
27. Is one policy shared across timeframes, or is each timeframe governed by
    a distinct versioned policy?
28. Which candidate and parameter choices are confirmatory versus
    exploratory?
29. What evidence is protected from label-policy selection?
30. What explicit approval authorizes deterministic label generation after
    the quantitative policy is frozen?

## Conclusion

All six candidates remain unresolved.

No winner is selected, no preference ordering is established, and no
candidate is authorized for implementation. The next valid step is a human
decision on research meaning and evidence constraints, followed by a
versioned quantitative label-policy specification for the selected candidate.

Until that approval exists:

- no labels may be generated;
- no dataset may be constructed;
- no model or experiment may be implemented; and
- no candidate class distribution or predictive result may be represented as
  evidence.
