# AlphaLens v2 Labeling Strategy Recommendation

## Status and Authority

**Phase:** Phase 4 — Labeling Strategy Recommendation  
**Artifact type:** Primary strategy recommendation  
**Implementation status:** Not implemented  
**Recommended candidate:** Candidate C — First-Touch Barrier Outcome

This document recommends one candidate for progression to a quantitative
label-policy specification. It does not approve numeric parameters, authorize
label generation, construct a dataset, approve an experiment, select a model,
or define a production decision policy.

This recommendation is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_PHASE_3_BASELINE.md`;
- `ALPHALENS_V2_LABELING_SPECIFICATION.md`;
- `ALPHALENS_V2_DATASET_SPECIFICATION.md`;
- `ALPHALENS_V2_RESEARCH_PROTOCOL.md`; and
- `ALPHALENS_V2_LABELING_STRATEGY_PROPOSAL.md`.

The stable output semantics remain:

- `BUY` is an identified upward opportunity;
- `SELL` is an identified downward opportunity; and
- `WAIT` is a valid completed evaluation that intentionally abstains.

None is an order, execution instruction, portfolio action, or guarantee.

## Recommended Strategy

The recommended primary strategy is:

> **Candidate C — First-Touch Barrier Outcome**

Starting strictly after the approved prediction-origin boundary, a future
path is observed until either:

1. an approved upper barrier is first touched;
2. an approved lower barrier is first touched; or
3. an approved time barrier expires.

The conceptual class mapping is:

| Resolved future event | Research class |
| --- | --- |
| Upper barrier first | `BUY` |
| Lower barrier first | `SELL` |
| Neither directional barrier before time expiry | `WAIT` |
| Outcome not resolvable under the approved policy | No label; exclude with an auditable reason |

This recommendation freezes only the strategy family and conceptual mapping.
It does not supply a barrier, horizon, reference price, touch field,
ambiguity rule, or timeframe-specific parameter.

## Why First-Touch Best Aligns With AlphaLens

### Opportunity occurrence rather than universal candle prediction

AlphaLens does not attempt to predict every candle and does not maximize
signal frequency. A first-touch label asks whether a predeclared directional
opportunity occurs within a bounded future interval. It does not require every
future observation to become directional.

When neither directional event occurs before expiry, the strategy produces a
natural `WAIT`. This directly supports the product requirement that no
qualifying opportunity is a valid and meaningful result.

### Direction and abstention have explicit event semantics

The strategy gives each class a distinct event meaning:

- `BUY` reflects an upward event occurring before the competing downward
  event;
- `SELL` reflects a downward event occurring first; and
- `WAIT` reflects expiration without either qualifying event.

This is stronger alignment with the Decision Contract than treating `WAIT`
only as a leftover numerical interval around zero. It also preserves the
mandatory distinction between `WAIT`, missing future evidence, ambiguity,
and failure.

### Path order is part of opportunity quality

A fixed endpoint can be positive even when price first moves substantially
downward, or negative after first moving substantially upward. A first-touch
strategy distinguishes these paths by the order in which the directional
conditions occur.

This does not prove predictive usefulness. It does make the retrospective
label more directly about directional opportunity order than endpoint return
alone.

### Compatible with the approved intraday evidence boundary

The existing Phase 2 data provides completed, validated BTC/USD OHLCV candles
for `5m`, `10m`, and `15m`. A first-touch study can be defined using those
candles without automatically requiring:

- a new predictive model;
- an additional Phase 3 feature;
- a transaction-cost artifact;
- broker or execution data;
- order-book data; or
- cross-timeframe feature joins.

OHLC data does create intrabar ambiguity, but that limitation can be governed
explicitly through exclusion or another preapproved conservative rule. It
must not be hidden.

### Transparent and reproducible

Once reference, barriers, horizon, touch semantics, and ambiguity rules are
approved, every class can be reconstructed from:

- immutable prediction-origin evidence;
- a bounded sequence of completed future candles;
- exact barrier definitions;
- the first resolved event; and
- a recorded label-availability timestamp.

The outcome and any exclusion can therefore be independently audited.

### Does not require confidence

The recommended strategy defines retrospective classes only. It does not
create a probability, certainty measure, ranking score, or confidence value.
Confidence remains unavailable under the frozen Confidence Policy.

## Recommended Conceptual Contract

Let:

- `t` be the prediction candle's canonical open timestamp;
- `D` be the timeframe duration;
- `a(t) = t + D` be the Phase 3 evidence availability;
- `P_reference(t)` be an approved price observable no earlier than the
  permitted post-cutoff reference boundary;
- `B_up(t)` be the approved upper barrier;
- `B_down(t)` be the approved lower barrier;
- `H` be the approved maximum outcome horizon; and
- `L(t)` be the post-cutoff outcome interval.

The later quantitative specification must ensure:

```text
feature evidence ends at or before a(t)
reference-price evidence satisfies the approved post-cutoff rule
barrier evaluation begins only after the prediction-origin boundary
label evidence is never available to the prediction
```

The selected policy must define a deterministic first resolved event over
`L(t)`.

No equation for `B_up`, `B_down`, `P_reference`, or `H` is approved here.

## Expected Strengths

The expected strengths are hypotheses to be verified, not measured results.

1. **First-class abstention**
   - `WAIT` corresponds to no directional barrier before expiry.
   - It is not merely the majority class, a null, or a model fallback.

2. **Path sensitivity**
   - Event order distinguishes paths with the same final price.
   - Opposite-direction movement occurring first is not hidden by the
     endpoint.

3. **Directional symmetry**
   - The same event framework can govern upward and downward opportunities.
   - Symmetric numeric barriers are not assumed; only structural symmetry is
     recommended.

4. **Bounded outcome**
   - A maximum horizon ensures every valid label has a finite terminal
     condition.
   - End-of-series incompleteness can be detected exactly.

5. **Explainability**
   - A reviewer can identify which barrier was touched, when it was touched,
     or why the label expired to `WAIT`.

6. **Determinism**
   - Fixed parameters and complete candles produce deterministic labels,
     subject to the approved ambiguity rule.

7. **No mandatory additional feature**
   - Fixed barriers can be researched from the current market evidence.
   - If scaled barriers are later proposed, their scale remains a separate
     approval.

## Expected Weaknesses

1. **Intrabar ordering is not always observable**
   - A candle may cross upper and lower barriers without revealing which was
     touched first.
   - Such observations cannot be assigned optimistically.

2. **Barrier sensitivity**
   - Class meanings and frequencies can change materially with barrier width.

3. **Horizon sensitivity**
   - Longer horizons may increase touch frequency and label overlap.
   - Shorter horizons may increase `WAIT`.

4. **Overlapping outcomes**
   - Adjacent prediction origins can share most of their future path.
   - Nominal label count will overstate independent evidence.

5. **Gap ambiguity**
   - A future candle may open beyond a barrier without revealing a continuous
     touch path or exact crossing price.

6. **Variable label availability**
   - Directional labels may resolve on different future observations, while
     `WAIT` resolves at expiry.

7. **Potential execution-language confusion**
   - Barriers must remain retrospective research conditions.
   - They must not be called orders, stops, take profits, or executable
     levels.

8. **Timeframe-specific behavior**
   - Identical numeric barriers across `5m`, `10m`, and `15m` may not have
     equivalent meaning.

## Research Risks

### Data snooping

Searching many barriers, horizons, scaling rules, and ambiguity treatments can
produce favorable class distributions or model results by chance. The first
implemented policy must use one preregistered configuration or a separately
approved, multiplicity-controlled design.

### Intrabar ambiguity bias

Excluding dual-touch observations may create a non-random subset. Assigning
them through a favorable convention would create stronger bias. The policy
must report exclusion frequency and temporal concentration without hiding the
limitation.

### Effective sample-size inflation

Overlapping horizons produce dependent labels. Research must not interpret
adjacent labeled rows as independent trials. Split, purge, uncertainty, and
sample-adequacy rules must account for overlap.

### Regime sensitivity

Fixed barriers may create different class semantics across changing
volatility states. Scaled barriers might reduce this issue but require a new
approved scale and add leakage and governance risks.

### Class sparsity

Wide barriers or short horizons may produce few `BUY` and `SELL` outcomes.
Narrow barriers may create frequent but noisy directional outcomes. Neither
class balance nor signal frequency may be optimized after seeing protected
results.

### Product-boundary drift

Barrier terminology can drift into trading or risk-management semantics.
This strategy labels directional opportunity events only. It does not define
entry, stop-loss, take-profit, position sizing, or execution.

### False confidence

Barrier distance, touch speed, class frequency, or model score must not be
presented as confidence. Confidence requires an independently approved
calibration specification and evidence.

## Why the Other Candidates Were Not Selected

The alternatives remain valid future research candidates. They were not
selected as the primary strategy for the following structural reasons.

### Candidate A — Fixed-Horizon Forward-Return Bands

Candidate A is simpler and less ambiguous, but it ignores the path before the
endpoint. A positive endpoint can conceal a downward event that occurred
first, and vice versa.

Its `WAIT` class is a return band rather than an explicit “no qualifying
directional event before expiry” outcome. It remains valuable as a later
reference or challenger, but it is not the primary recommendation for
opportunity-order semantics.

### Candidate B — Volatility-Scaled Forward-Return Bands

Candidate B retains Candidate A's endpoint path blindness and requires an
approved point-in-time volatility scale. No qualifying normalized scale is
part of the frozen Tier-A registry.

Selecting it now would either require a separately approved label-only scale
or reopen the frozen Phase 3 baseline. It therefore has more prerequisites
without resolving endpoint path blindness.

### Candidate D — Directional Opportunity With Adverse-Excursion Constraint

Candidate D represents path quality more richly, but requires multiple
favorable and adverse thresholds and rules for temporal ordering and dual
qualification.

That parameter burden increases multiplicity and can blur the boundary
between retrospective opportunity labeling and entry/stop risk logic. A
first-touch strategy captures path order with a smaller conceptual contract.

### Candidate E — Two-Stage Direction and Opportunity Qualification

Candidate E aligns strongly with selective decision-making, but it does not
itself define an opportunity or direction event. Two policies, possibly two
horizons, and a joint mapping must all be approved.

The staged design also introduces selection bias and sample-adequacy risks
before a single-stage label has established a defensible research baseline.
It remains a possible future strategy if evidence shows that opportunity
qualification and direction should be modeled separately.

### Candidate F — Friction-Aware Directional Outcome

Candidate F depends on another directional strategy and an approved
point-in-time friction artifact. AlphaLens v2 is not an execution platform,
and no authoritative v2 venue, order type, size, fee, spread, or slippage
policy exists.

Selecting it would introduce unsupported economic precision and risk
reintroducing deprecated v1 trading assumptions. Friction awareness may be
reconsidered only through a separate product and evidence decision.

## Remaining Implementation Decisions

The strategy family is recommended, but the quantitative policy remains
incomplete. All items below must be resolved before label implementation.

### Policy identity

- label-policy identifier;
- semantic version;
- effective scope;
- whether each timeframe has a distinct policy version; and
- canonical configuration and result hashing.

### Prediction-origin boundary

- exact relationship among prediction timestamp, evidence cutoff, and the
  first eligible future observation;
- whether the first evaluated path candle is the candle immediately following
  `t`;
- exclusion behavior when the required next observation is missing; and
- confirmation that no same-close reference is used.

### Reference price

- permitted source field;
- exact timestamp;
- whether it is a point value or deterministic region;
- behavior for a gap between evidence availability and the reference
  observation; and
- availability timestamp.

### Barrier basis

- absolute price, arithmetic-return, log-return, percentage, or approved
  point-in-time-scaled distance;
- fixed versus dynamically point-in-time-scaled barriers;
- scale definition if used;
- scale warm-up and zero policy;
- upper and lower barrier formulas; and
- whether directional barrier magnitudes are symmetric.

### Barrier parameters

- upper barrier magnitude;
- lower barrier magnitude;
- units;
- precision and rounding;
- equality convention;
- threshold effective date; and
- parameter treatment across `5m`, `10m`, and `15m`.

### Touch semantics

- high/low touch, close touch, or another approved field;
- inclusive versus strict comparison;
- exact first-touch timestamp;
- gap-through-barrier handling;
- same-candle upper/lower dual touch;
- simultaneous equality;
- malformed or missing future candle handling; and
- whether any ambiguity rule other than exclusion is defensible.

### Time barrier

- horizon magnitude;
- observation-count versus elapsed-time basis;
- inclusive/exclusive interval;
- expiry timestamp;
- treatment of early market-data gaps;
- per-timeframe versus common horizon; and
- label availability on expiry.

### `WAIT` and exclusion taxonomy

- exact `WAIT` condition;
- distinction between valid expiry, ambiguity, incomplete horizon, source
  gap, and validation failure;
- stable exclusion reason codes;
- whether a gap invalidates the complete origin or only the path after it;
- end-of-series behavior; and
- reporting requirements for exclusions.

### Chronology and dependence

- label outcome interval;
- overlapping-label policy;
- purge rule;
- embargo rule;
- minimum separation, if any, among evaluated origins;
- effective sample-size assessment; and
- protected validation/test boundaries.

### Research adequacy

- minimum total labels;
- minimum `BUY`, `SELL`, and `WAIT` observations;
- minimum observations per timeframe and chronological fold;
- maximum acceptable ambiguity or exclusion rate;
- temporal coverage requirements;
- allowed preregistered sensitivity analysis;
- multiplicity controls; and
- stopping criteria.

## Parameters Requiring Explicit Approval

No default is supplied for any of the following:

| Parameter group | Parameters |
| --- | --- |
| Scope | Instrument, approved timeframe policy, policy sharing versus per-timeframe versions |
| Origin | Evidence cutoff, first eligible future candle, reference timestamp |
| Reference | Price field, gap rule, precision |
| Upper event | Barrier basis, magnitude, units, inclusivity |
| Lower event | Barrier basis, magnitude, units, inclusivity |
| Scaling | Scale identity, formula, version, warm-up, zero/near-zero behavior |
| Horizon | Magnitude, unit, observation/calendar basis, interval boundaries |
| Touch | High/low/close field, first-touch timestamp, equality |
| Ambiguity | Dual-touch, gap-through, simultaneous-event, missing-candle rules |
| Availability | Directional-resolution availability and `WAIT` expiry availability |
| Exclusions | Reason taxonomy, incomplete horizon, end-of-series, data gaps |
| Dependence | Overlap, purge, embargo, origin spacing |
| Numeric policy | Decimal precision, quantization, rounding |
| Adequacy | Minimum class counts, fold counts, exclusion limits, coverage |
| Governance | Policy version, canonical serialization, hashes, supersession |

Selecting this strategy does not implicitly approve a conventional
“triple-barrier” parameter set or any value used by another project,
publication, library, or v1 AlphaLens component.

## Required Approval Sequence

Implementation may begin only after:

1. the strategy recommendation is human approved;
2. a quantitative first-touch label-policy specification resolves every
   required parameter;
3. an intrabar ambiguity and gap policy is approved;
4. the dataset and chronological split configuration is frozen;
5. class/sample adequacy rules are preregistered;
6. label identity, provenance, and hashing are approved;
7. protected evidence is identified and sealed; and
8. explicit human authorization for deterministic label generation is
   recorded.

If any parameter cannot be resolved from defensible evidence, implementation
must remain blocked rather than invent a default.

## Migration Path to a Future Strategy

The canonical Decision Contract is technology- and strategy-independent.
Changing a future label policy therefore does not require changing
`BUY`/`SELL`/`WAIT` meanings, but it does require new immutable research
evidence.

### 1. Preserve the original policy

- Keep the first-touch policy, labels, datasets, experiments, and decisions
  immutable.
- Do not relabel historical observations in place.
- Do not reinterpret existing results under a new strategy.

### 2. Register a challenger independently

- Assign a new label-policy identifier and semantic version.
- Freeze its definition, parameters, provenance, and hashing.
- Build a new dataset version from the same eligible point-in-time evidence
  where comparability is valid.
- Record observations that are not comparable because outcome intervals or
  exclusions differ.

### 3. Preregister comparison

- Define the research question before generating challenger results.
- Use identical development boundaries where label semantics permit.
- Define paired comparison units, metrics, uncertainty, multiplicity
  correction, and success criteria.
- Use fresh protected evidence if prior evidence was consumed during
  first-touch selection or evaluation.
- Do not select a challenger using the official final test already consumed
  for another policy.

### 4. Require defensible evidence

A future strategy may replace the recommended strategy only when a
preapproved study demonstrates improvement under the approved success rules,
including:

- directional class quality;
- `WAIT` validity;
- chronological stability;
- exclusion and ambiguity burden;
- sample adequacy;
- reproducibility;
- point-in-time correctness; and
- practical semantic alignment.

“Outperforms” must not mean only a favorable uncorrected metric.

### 5. Approve an additive transition

- Create a new dataset and research-policy version.
- Create a new decision-policy version if the production mapping changes.
- Keep confidence absent until separately recalibrated for the new policy.
- Update consumers through explicit policy references rather than changing
  class meaning.
- Preserve a deterministic rollback path to the prior approved artifacts.

### 6. Promote without rewriting history

If approved, the new strategy becomes active only for new research or
decisions under its effective version. Earlier first-touch artifacts remain
the source of truth for their original period and claims.

Rollback means restoring the prior approved policy reference for future use.
It never means deleting challenger evidence or rewriting historical labels.

## Recommendation Summary

### Recommended strategy

**Candidate C — First-Touch Barrier Outcome**

### Rationale

It provides the strongest direct alignment among the current candidates with:

- bounded intraday opportunity identification;
- directional event order;
- explicit `WAIT` through time expiry;
- path awareness;
- deterministic auditability; and
- the existing completed OHLCV evidence boundary.

It achieves that alignment without requiring a second-stage policy, an
unapproved volatility feature, a friction artifact, or a full
adverse-excursion parameter system.

### Remaining approvals required

The recommendation is not implementable until humans explicitly approve:

- prediction origin and reference price;
- upper and lower barrier definitions;
- time horizon;
- touch and equality semantics;
- dual-touch and gap ambiguity;
- `WAIT` and exclusion taxonomy;
- per-timeframe parameters;
- label availability;
- overlap, purge, and embargo;
- numeric policy;
- sample adequacy;
- policy versioning and hashing; and
- explicit authorization to generate labels.

Until those approvals are complete, no labels, datasets, experiments, models,
or production decisions are authorized.
