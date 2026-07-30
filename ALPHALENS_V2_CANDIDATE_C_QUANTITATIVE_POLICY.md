# AlphaLens v2 Candidate C Quantitative Policy Recommendation

## Status and Authority

**Phase:** Phase 5 — Candidate C Quantitative Policy Recommendation  
**Artifact type:** Quantitative research recommendation  
**Implementation status:** Not implemented  
**Approval status:** Recommended; pending explicit human approval  
**Recommended policy identifier:** `candidate_c_first_touch_atr`  
**Recommended policy version:** `1.0.0`

This document recommends a complete quantitative parameterization of the
approved Candidate C — First-Touch Barrier Outcome strategy. It is a design
review artifact only.

It does not:

- approve the recommendation;
- generate a label;
- construct a dataset;
- train or select a model;
- create confidence;
- define an executable trading plan;
- authorize an entry, stop-loss, or take-profit;
- modify any approved contract; or
- authorize implementation without a subsequent explicit human approval.

The recommendation remains subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`;
- `ALPHALENS_V2_PHASE_3_BASELINE.md`;
- `ALPHALENS_V2_LABELING_SPECIFICATION.md`;
- `ALPHALENS_V2_DATASET_SPECIFICATION.md`;
- `ALPHALENS_V2_RESEARCH_PROTOCOL.md`;
- `ALPHALENS_V2_LABELING_STRATEGY_PROPOSAL.md`; and
- `ALPHALENS_V2_LABELING_STRATEGY_RECOMMENDATION.md`.

If this recommendation conflicts with an approved contract, the approved
contract prevails.

## Executive Summary

The recommended policy is a conservative, volatility-scaled first-touch
label with:

- the open of the first contiguous candle after the prediction candle as the
  retrospective reference price;
- symmetric upper and lower barriers at `1.5 × ATR14`;
- `ATR14` defined as the arithmetic mean of the most recent 14 approved
  point-in-time `true_range` values;
- a fixed elapsed-time horizon of 60 minutes for `5m`, `10m`, and `15m`;
- `BUY` when the upper barrier is deterministically touched first;
- `SELL` when the lower barrier is deterministically touched first;
- `WAIT` only when neither barrier is touched by expiry;
- inclusive barrier equality;
- deterministic gap-at-open precedence;
- exclusion, rather than optimistic assignment, when one OHLC candle makes
  first-touch ordering unknowable;
- separate policies and datasets for each timeframe;
- exact Decimal computation quantized to 18 decimal places using
  round-half-even;
- full future-path provenance;
- purged, embargoed expanding walk-forward evaluation; and
- a final 20% chronological test period sealed until one approved evaluation.

This is a triple-barrier-style research label: two price barriers and one time
barrier determine the outcome. The names `BUY`, `SELL`, and `WAIT` describe
retrospective research classes. They do not represent orders or executable
levels.

The recommendation is designed for AlphaLens' objective of identifying
selective, high-quality intraday opportunities:

1. direction must resolve before an adverse competing event;
2. no qualifying event becomes an explicit `WAIT`;
3. the barrier scale adapts to information available at prediction time;
4. the one-hour horizon keeps the research question intraday;
5. unresolved OHLC paths are excluded rather than guessed; and
6. identical evidence always produces identical labels and hashes.

The numeric values are preregistration recommendations, not claims that the
values are optimal. They must not be tuned after class or model results are
observed under this version.

## Policy Decision Table

| Policy element | Recommendation |
| --- | --- |
| Strategy | Candidate C — First-Touch Barrier Outcome |
| Instrument | BTC/USD |
| Timeframes | `5m`, `10m`, `15m`, evaluated separately |
| Prediction origin | Completed candle with canonical open timestamp `t` |
| Evidence cutoff | `a(t) = t + D`, where `D` is timeframe duration |
| Reference price | Open of the immediately following contiguous candle |
| Volatility scale | Arithmetic mean of the latest 14 approved `true_range` values available at `a(t)` |
| Upper barrier | `reference_price + 1.5 × ATR14(t)` |
| Lower barrier | `reference_price - 1.5 × ATR14(t)` |
| Horizon | 60 elapsed minutes from the reference candle open |
| 5m path | 12 complete candles |
| 10m path | 6 complete candles |
| 15m path | 4 complete candles |
| Touch fields | Candle open first; then high and low |
| Equality | Inclusive |
| Dual touch | Exclude when order cannot be determined from OHLC |
| WAIT | Neither barrier touched during the complete 60-minute path |
| Precision | Decimal, quantum `0.000000000000000001` |
| Rounding | Round-half-even at defined canonicalization points |
| Overlap | Retain valid origins; record interval concurrency; do not assume independence |
| Split | Calendar-time expanding walk-forward, separate per timeframe |
| Protected test | Final 20% of eligible calendar span, minimum eight weeks |
| Confidence | Unavailable |

## Recommended Quantitative Policy

### 1. Reference price

#### Recommendation

For a prediction candle with canonical open timestamp `t` and duration `D`,
define the evidence cutoff:

\[
a(t)=t+D.
\]

The reference candle is the complete, valid candle whose canonical open
timestamp is exactly `a(t)`. Its open price is:

\[
P_0(t)=O_{a(t)}.
\]

The reference candle must be the immediately following expected candle. A
nearest-time or later substitute is prohibited.

#### Rationale

- The prediction candle is complete at `a(t)`.
- The next candle open is the earliest distinct market observation after the
  prediction-origin candle.
- This avoids using the prediction candle close as a same-close execution
  assumption.
- The open is a precisely recorded observation and does not require an
  invented fill model.

The reference price is only a retrospective coordinate for label evaluation.
It is not an entry recommendation or a claim that an order could execute at
that price.

#### Trade-offs and risks

- A zero-latency transition from candle close to next open remains an
  idealized evaluation boundary.
- Opening gaps affect the distance between the prediction close and reference
  price.
- A decision service may later have additional latency. That would require a
  new policy version rather than retrospective reinterpretation.

### 2. Volatility scale

#### Recommendation

Use an approved label-policy scale derived only from Phase 3 `true_range`
values.

For the prediction origin `t`, define:

\[
\operatorname{ATR}_{14}(t)
=
\frac{1}{14}
\sum_{j=0}^{13}
\operatorname{TR}(t-jD).
\]

Despite the conventional name `ATR`, this policy explicitly uses a 14-value
arithmetic mean, not Wilder recursive smoothing.

All 14 `true_range` values must:

- belong to the same instrument and timeframe;
- come from one verified Phase 3 pipeline `2.0.0` source snapshot;
- have `available_at <= a(t)`;
- be consecutive by observation;
- be finite and strictly nonnegative; and
- retain their immutable feature provenance.

The resulting `ATR14` must be strictly positive.

#### Rationale

- Raw fixed-price barriers change meaning as BTC price and volatility change.
- Scaling by recent point-in-time range makes the event definition relative
  to contemporaneous market movement.
- `true_range` is already an approved Tier-A feature, so this recommendation
  does not add a predictive feature or reopen the Phase 3 registry.
- An arithmetic mean is transparent, bounded to 14 observations, and
  prefix-invariant.

#### Trade-offs and risks

- Fourteen observations are a convention and not demonstrated as optimal.
- A short scale can react quickly but may be noisy.
- A long scale would be smoother but less responsive to regime changes.
- ATR is range-based and can be affected by isolated spikes.
- The label meaning remains dependent on the chosen scale.

The scale is part of label policy `1.0.0`. It must not be varied inside that
policy after results are observed.

### 3. Upper barrier

#### Recommendation

Define:

\[
B_U(t)
=
Q\left(P_0(t)+1.5\operatorname{ATR}_{14}(t)\right),
\]

where `Q` is the approved 18-decimal canonical quantization operation.

#### Rationale

A `1.5 × ATR14` barrier requires movement larger than one recent average
range without making the event so remote that directional classes are likely
to disappear. The multiplier is intentionally identical for all timeframes
under version `1.0.0` to limit research degrees of freedom.

#### Trade-offs and risks

- The multiplier has not been empirically validated for this dataset.
- Narrower barriers would increase event frequency and ambiguity.
- Wider barriers would increase `WAIT` and class sparsity.
- Symmetry may not reflect asymmetric upside and downside dynamics.

### 4. Lower barrier

#### Recommendation

Define:

\[
B_L(t)
=
Q\left(P_0(t)-1.5\operatorname{ATR}_{14}(t)\right).
\]

Require:

\[
0 < B_L(t) < P_0(t) < B_U(t).
\]

If this invariant fails, exclude the observation.

#### Rationale

A symmetric first policy creates a clear directional comparison and avoids
introducing two independently selected magnitudes. It is a defensible
baseline, not an assertion that the market is directionally symmetric.

#### Trade-offs and risks

- Downside and upside price behavior may differ.
- Symmetric barriers can create asymmetric class counts.
- A later asymmetric challenger would require a new policy version and fresh
  protected evidence.

### 5. Time barrier and prediction horizon

#### Recommendation

Use a fixed elapsed-time horizon:

\[
H=60\text{ minutes}.
\]

Starting at the reference time `a(t)`, the outcome interval is:

\[
L(t)=[a(t),a(t)+H).
\]

It contains:

- 12 complete `5m` candles;
- 6 complete `10m` candles; or
- 4 complete `15m` candles.

The final path candle must close exactly at `a(t)+H`.

#### Rationale

- Sixty minutes is unambiguously intraday.
- A shared elapsed horizon gives the three timeframes the same economic clock
  without pooling their observations.
- It prevents a nominal “12-bar” horizon from meaning one hour on `5m` and
  three hours on `15m`.
- It bounds label availability and enables exact purge rules.

#### Trade-offs and risks

- The timeframes contribute different numbers of path observations.
- Four `15m` candles provide coarser path resolution than twelve `5m`
  candles.
- A one-hour horizon may be too short or too long for some regimes.
- It must not be changed based on version `1.0.0` results.

### 6. First-touch rules

For each complete future candle in chronological order:

1. Evaluate its open against both barriers.
2. If the open deterministically crosses one barrier, resolve that event at
   the candle open.
3. Otherwise evaluate its high and low.
4. If only the upper barrier is touched, resolve `BUY`.
5. If only the lower barrier is touched, resolve `SELL`.
6. If neither is touched, continue.
7. If both are touched and their order cannot be established, exclude the
   origin.
8. Stop permanently at the first resolved directional event.

Later movement cannot revise an already resolved class.

#### Rationale

The procedure uses the only ordering available in OHLC data: candle open
precedes the candle's unknown intrabar high/low path. It refuses to invent an
order where the source cannot provide one.

### 7. Equality handling

Barrier comparisons are inclusive:

\[
\text{upper touch}\iff price\ge B_U(t)
\]

and

\[
\text{lower touch}\iff price\le B_L(t).
\]

Equality at the quantized barrier is a touch.

#### Rationale

Inclusive comparisons are deterministic, preserve exact observed boundary
events, and avoid an arbitrary epsilon.

### 8. Gap handling

#### Valid gap across contiguous candles

If a contiguous future candle opens:

- at or above the upper barrier, resolve `BUY` at that open;
- at or below the lower barrier, resolve `SELL` at that open; or
- between the barriers, continue with high/low evaluation.

The opening event has precedence over later intrabar extrema because the open
is the first recorded state for that candle.

#### Missing-candle gap

If an expected candle timestamp is absent, duplicated, incomplete, invalid,
or sourced from an unverifiable snapshot, exclude the origin. Do not jump to
the next available candle.

#### Rationale

This distinguishes an observed discontinuous price move from an unobserved
data interval. Observed gaps can resolve an event; missing evidence cannot.

### 9. Simultaneous dual-touch handling

If a future candle opens strictly between the barriers and its:

\[
H_c\ge B_U(t)
\quad\text{and}\quad
L_c\le B_L(t),
\]

the OHLC record cannot establish which barrier was touched first.

Exclude the origin with:

```text
AMBIGUOUS_DUAL_TOUCH
```

Do not assign `BUY`, `SELL`, or `WAIT`. Do not use candle direction, distance
from open, proximity, random ordering, or a favorable/conservative directional
guess.

If the candle open already resolves one barrier, that deterministic open event
precedes later high/low movement and is not a dual-touch ambiguity.

#### Rationale

Exclusion is the only defensible behavior without approved finer-grained
evidence. It prevents fabricated path ordering.

#### Risk

Dual-touch exclusions may be non-random and concentrated during volatile
periods. Their frequency and temporal distribution must be reported.

### 10. `WAIT` definition

Assign `WAIT` only when:

1. the complete 60-minute future path exists;
2. every path candle is valid, complete, and contiguous;
3. neither barrier is touched under the approved rules;
4. no ambiguity occurs;
5. all hashes and provenance verify; and
6. the time barrier expires.

`WAIT` means a completed evaluation found no qualifying directional event.

It must never represent:

- incomplete future data;
- warm-up failure;
- missing candles;
- invalid prices;
- zero volatility scale;
- dual-touch ambiguity;
- hash failure;
- policy mismatch; or
- operational failure.

### 11. Excluded observations

The policy recommends these stable exclusion codes:

| Code | Condition |
| --- | --- |
| `FEATURE_WARMUP_INCOMPLETE` | Fewer than 14 valid consecutive `true_range` values are available. |
| `FEATURE_VECTOR_INCOMPLETE` | The complete approved Tier-A vector is absent at the origin. |
| `FEATURE_AVAILABLE_AFTER_CUTOFF` | Any required feature violates point-in-time availability. |
| `REFERENCE_CANDLE_MISSING` | The immediately following reference candle is absent. |
| `REFERENCE_CANDLE_INVALID` | The reference candle is incomplete or invalid. |
| `OUTCOME_HORIZON_INCOMPLETE` | The full 60-minute path is unavailable. |
| `OUTCOME_CANDLE_MISSING` | An expected path timestamp is absent. |
| `OUTCOME_CANDLE_INVALID` | A path candle is incomplete or fails data validation. |
| `AMBIGUOUS_DUAL_TOUCH` | One candle touches both barriers without determinable order. |
| `VOLATILITY_SCALE_NON_POSITIVE` | `ATR14 <= 0`. |
| `BARRIER_INVARIANT_FAILED` | Quantized barriers do not satisfy `0 < lower < reference < upper`. |
| `SOURCE_HASH_MISMATCH` | Any source, registry, snapshot, provenance, or feature hash fails. |
| `POLICY_MISMATCH` | Scope, version, or policy configuration does not match. |
| `TIMESTAMP_NOT_CANONICAL` | Timestamp is non-UTC or off its timeframe boundary. |
| `SOURCE_CONTINUITY_FAILED` | Required historical or future evidence is not continuous. |

Each exclusion must retain its prediction timestamp, relevant evidence
timestamps, reason code, source references, and deterministic exclusion hash.

### 12. Label availability timing

For a directional touch in candle `c`:

\[
\operatorname{label\_available\_at}
=
\operatorname{close\_time}(c).
\]

Even when the candle open crosses a barrier, the research label becomes
available at candle close because this policy consumes validated completed
OHLC candles.

For `WAIT`:

\[
\operatorname{label\_available\_at}
=
a(t)+60\text{ minutes}.
\]

For a dual-touch exclusion, availability is the close of the ambiguous
candle. For a missing or incomplete path, the exclusion becomes final at the
scheduled horizon expiry `a(t)+60 minutes`. A run must not declare an
end-of-series origin incomplete before that time has passed. The observation
remains excluded and never becomes a class.

Label availability is outcome evidence and must never enter a feature vector.

### 13. Multi-timeframe behavior

Use the same conceptual formula for `5m`, `10m`, and `15m`, with:

- separate policy records;
- separate source feature runs;
- separate label runs;
- separate datasets;
- separate chronological splits;
- separate class and exclusion audits; and
- separate research results.

Recommended identities:

```text
candidate_c_first_touch_atr / 1.0.0 / BTC/USD / 5m
candidate_c_first_touch_atr / 1.0.0 / BTC/USD / 10m
candidate_c_first_touch_atr / 1.0.0 / BTC/USD / 15m
```

The shared version does not authorize pooling. Identical numeric policy
parameters do not imply identical statistical populations.

No cross-timeframe feature join or majority vote is permitted.

The derived `10m` evidence shares underlying `5m` candles with the `5m`
population. Cross-timeframe comparisons must record that dependence and must
not treat the three timeframe results as independent replications.

### 14. Decimal precision

Use Decimal arithmetic exclusively for:

- OHLC inputs;
- `true_range`;
- `ATR14`;
- barrier multipliers;
- reference and barrier prices; and
- all stored quantitative label metadata.

The canonical quantum is:

```text
0.000000000000000001
```

Binary floating point is prohibited during label generation, comparison,
serialization, and hashing.

### 15. Rounding policy

Apply round-half-even only at these canonicalization points:

1. quantize `ATR14` to 18 decimal places after dividing by 14;
2. quantize the upper and lower barriers to 18 decimal places; and
3. serialize every Decimal as a fixed-point string with exactly 18 fractional
   digits.

Do not round:

- source candle values before the existing canonical source conversion;
- intermediate true-range values already governed by Phase 3;
- observed OHLC prices before comparison; or
- timestamps.

All comparisons use the stored quantized barriers. This ensures calculation
and audit use the same boundary.

### 16. Chronological constraints

For every origin:

1. source candles are strictly chronological and unique;
2. prediction features have `available_at <= a(t)`;
3. `ATR14` uses only `true_range` values at or before `t`;
4. the reference candle opens at `a(t)`;
5. future path evaluation begins at `a(t)`;
6. no outcome field appears in model inputs;
7. label availability follows the event evidence;
8. a training label must be available strictly before the next evaluation
   partition begins;
9. partition boundaries are fixed before model results; and
10. random, shuffled, stratified-random, and ordinary k-fold splits are
    prohibited.

Prefix reconstruction must reproduce every feature, scale, barrier, class,
exclusion, and hash from only the evidence available to the applicable
artifact at that time.

### 17. Overlap policy

Generate one candidate origin for every otherwise eligible completed candle.
Retain overlapping valid labels, but record:

- outcome interval;
- label availability;
- number of concurrent label intervals at each timestamp;
- average uniqueness for each observation;
- maximum concurrency;
- concurrency distribution; and
- effective sample-size diagnostics.

Do not:

- call overlapping labels independent;
- downsample after inspecting results;
- weight observations without a separately approved preprocessing policy; or
- allow overlapping intervals to cross a partition boundary.

#### Rationale

Retaining all origins preserves opportunity coverage and avoids an arbitrary
event-sampling rule. Explicit concurrency evidence lets later statistical
work account for dependence.

#### Risk

Nominal row counts can materially overstate independent information.
Uncertainty procedures must use time blocks at least as long as the 60-minute
outcome interval and must be preregistered in the experiment protocol.

### 18. Purge and embargo policy

#### Purge

At every train/validation or development/test boundary `T_b`, remove from the
earlier partition every origin whose:

\[
\operatorname{label\_available\_at}\ge T_b
\]

or whose outcome interval intersects the later partition.

This produces a maximum pre-boundary purge of 60 elapsed minutes for valid
`WAIT` labels. Directional labels that resolved earlier may remain only when
their complete label evidence was available strictly before `T_b`.

#### Embargo

Use a 60-minute elapsed-time embargo after every validation or protected-test
block before observations can enter a later training partition.

Origins whose evidence cutoff falls in the embargo interval are not training
observations for that later fold.

#### Rationale

The purge removes direct label-interval overlap. The embargo matches the
maximum label horizon and reduces leakage from immediately adjacent,
serially dependent event paths.

#### Trade-off

This sacrifices observations. It is preferable to overstating independent
evidence.

### 19. Dataset split recommendation

Create independent calendar-time partitions for each timeframe.

Let the complete approved dataset span be `[T_0,T_1)`.

#### Protected test

Reserve the final 20% of elapsed calendar time:

\[
T_{\text{test}}
=
T_0+0.80(T_1-T_0).
\]

The protected interval is:

\[
[T_{\text{test}},T_1).
\]

It must span at least eight complete weeks. If it does not, the dataset is
inadequate.

#### Development walk-forward

Use the first 80% of elapsed time for development.

- Initial training interval: first 50% of the complete elapsed span.
- Five sequential validation intervals: each 6% of the complete elapsed span.
- Training expands for each fold.
- Purge and embargo are applied at every fold boundary.
- Boundaries are computed from UTC elapsed time, then snapped forward to the
  next canonical timeframe boundary.
- Boundaries do not depend on class counts or model results.

Conceptually:

| Segment | Complete-span share |
| --- | ---: |
| Initial training | 50% |
| Validation fold 1 | 6% |
| Validation fold 2 | 6% |
| Validation fold 3 | 6% |
| Validation fold 4 | 6% |
| Validation fold 5 | 6% |
| Protected final test | 20% |

This totals 100% of elapsed calendar time before exclusions.

#### Why expanding walk-forward

It preserves chronology, evaluates multiple later periods, and reflects the
growing evidence available to a future research system. Rolling-origin
evaluation is established practice for forecasting problems where future
observations must be evaluated using only earlier information.

#### Risks

- Later folds contain more training data.
- Nonstationarity can make older observations less representative.
- Fixed calendar shares do not guarantee equal class counts.
- A rolling-window challenger may be studied only under a new approved
  protocol.

### 20. Protected test-set policy

The protected test must be:

- identified and hashed before model development;
- inaccessible to label-policy tuning;
- inaccessible to feature selection, preprocessing selection, model
  selection, or calibration;
- excluded from descriptive class-balance review beyond source coverage and
  time-span verification;
- consumed exactly once under separate explicit approval;
- recorded as consumed immutably; and
- retired from further selection or tuning for the same research question.

The protected test's label values, class counts, exclusions, and metrics must
remain sealed. Source-data continuity and cryptographic existence may be
verified without exposing outcome summaries.

If the official test is consumed, a changed policy or model requires newly
accrued or separately sealed evidence. The test must not be recycled as
development data for a confirmatory claim.

### 21. Class balance monitoring

Class balance is descriptive evidence, not a parameter-tuning objective.

For development data only, report:

- `BUY`, `SELL`, and `WAIT` counts and prevalence;
- counts by timeframe;
- counts by month;
- counts by walk-forward fold;
- exclusion counts by reason;
- dual-touch exclusion prevalence;
- action rate (`BUY` plus `SELL`);
- directional asymmetry;
- longest interval without each class; and
- temporal drift in prevalence.

#### Review triggers

The dataset is not automatically approved for modeling if:

- any class is below 5% of valid development labels;
- one class exceeds 80%;
- any class has fewer than 1,000 development examples;
- any validation fold has fewer than 100 examples of any class;
- total exclusions exceed 5% of otherwise eligible origins;
- dual-touch exclusions exceed 2%; or
- missing/invalid source evidence exceeds 0.5%.

A trigger requires human review. It does not authorize changing barriers,
horizon, exclusions, or class semantics under version `1.0.0`.

No oversampling, undersampling, synthetic labels, class weighting, or
threshold tuning is approved by this policy.

### 22. Minimum dataset adequacy requirements

Each timeframe is adequate for initial model research only when all of these
hold:

1. at least 365 consecutive calendar days are covered;
2. source candle coverage is at least 99.5%;
3. the protected test spans at least eight complete weeks;
4. at least 80% of otherwise eligible origins receive valid labels;
5. at least 25,000 valid labels exist before the protected test;
6. each class has at least 1,000 valid development labels;
7. each of five validation folds has at least 100 examples of each class;
8. at least 2,000 non-overlapping 60-minute outcome blocks exist in
   development;
9. no unresolved hash, chronology, or provenance failure exists;
10. exclusion and class-balance review triggers are resolved explicitly; and
11. deterministic regeneration produces byte-equivalent semantic output.

These are governance floors, not power calculations and not guarantees of
predictive validity.

#### Current practical implication

A provider-limited 720-candle snapshot is insufficient:

- 720 `5m` candles cover about 2.5 days;
- 720 `10m` candles cover about 5 days; and
- 720 `15m` candles cover about 7.5 days.

Therefore this policy should not authorize model research until a longer
validated point-in-time history is available.

### 23. Policy versioning

Recommended identity:

```text
policy_identifier = candidate_c_first_touch_atr
policy_version = 1.0.0
```

Version rules:

- **PATCH:** documentation correction with no semantic or output change;
- **MINOR:** backward-compatible metadata addition that cannot change any
  label or exclusion;
- **MAJOR:** any change capable of changing eligibility, class, availability,
  interval, precision, or hash.

The following always require a new major version:

- reference-price change;
- ATR definition or lookback change;
- barrier multiplier change;
- symmetry change;
- horizon change;
- touch-field or equality change;
- gap or dual-touch change;
- `WAIT` or exclusion change;
- availability change;
- precision or rounding change;
- timeframe scope change; or
- source feature-pipeline change.

Historical policy records, labels, datasets, and experiments are immutable.
A new policy supersedes but never overwrites them.

### 24. Policy hashing

#### Configuration hash

Serialize the complete policy as canonical UTF-8 JSON:

- keys sorted lexicographically;
- no insignificant whitespace;
- Unicode represented consistently;
- enums serialized by stable identifier;
- Decimal values serialized as fixed-point strings with 18 fractional digits;
- timestamps serialized as UTC RFC 3339 with `Z`;
- durations serialized as integer microseconds;
- ordered collections retained in contract order;
- unordered collections sorted before serialization; and
- generated IDs, creation timestamps, database sequence values, and active
  status excluded.

Compute:

\[
\operatorname{configuration\_hash}
=
\operatorname{SHA256}(\operatorname{canonical\_policy\_bytes}).
\]

#### Label result hash

For each label or exclusion, hash canonical content containing:

- policy identifier and version;
- configuration hash;
- instrument and timeframe;
- prediction timestamp;
- evidence cutoff;
- reference timestamp and price;
- `ATR14`;
- upper and lower barriers;
- outcome interval;
- resolved event timestamp;
- label availability;
- class or exclusion reason;
- source feature-run ID and hashes;
- ordered source candle identities; and
- ordered source candle content hashes.

The run result hash is SHA-256 over the ordered canonical label/exclusion
records sorted by:

1. instrument;
2. timeframe duration;
3. prediction timestamp; and
4. stable class-or-exclusion identifier.

Identical semantic evidence must reproduce identical hashes regardless of
database IDs or execution time.

### 25. Provenance requirements

Every policy record must retain:

- policy identifier and version;
- strategy identifier;
- complete configuration;
- approval reference;
- code commit and dirty-state evidence;
- software versions;
- configuration hash;
- effective scope; and
- supersession lineage.

Every generation run must retain:

- run ID;
- policy ID and configuration hash;
- Phase 3 pipeline version `2.0.0`;
- registry schema and availability-contract versions;
- registry hash;
- exact feature-run IDs;
- source snapshot and provenance hashes;
- instrument and timeframe;
- source range;
- counts by class and exclusion;
- point-in-time validation evidence;
- source candle memberships;
- label-result memberships;
- run result hash;
- generation timestamp; and
- immutable status.

Every observation must retain:

- prediction timestamp;
- evidence cutoff;
- reference candle and price;
- volatility scale and its 14 source feature values;
- barriers;
- complete path-candle memberships;
- outcome interval;
- event type and event timestamp;
- label availability;
- class or exclusion;
- per-record result hash; and
- all source ingestion and feature provenance.

Any missing or unverifiable provenance element causes exclusion or run
failure. No partial successful run may be promoted as active.

## Mathematical Definitions

Let:

- `D ∈ {5m,10m,15m}`;
- `t` be the prediction candle open;
- `a=t+D` be its evidence cutoff;
- `P_0=O_a` be the next contiguous candle open;
- `TR_i` be approved Phase 3 true range;
- `Q` quantize to 18 decimal places using round-half-even;
- `k=1.5`; and
- `H=60m`.

Define:

\[
V_t
=
Q\left(\frac{1}{14}\sum_{j=0}^{13}TR_{t-jD}\right).
\]

\[
B_U=Q(P_0+kV_t)
\]

\[
B_L=Q(P_0-kV_t).
\]

Let the complete future path be:

\[
\mathcal{C}_t
=
\{c:\operatorname{open\_time}(c)\in[a,a+H)\}.
\]

For each candle `c` in ascending time:

\[
G_U(c)=\mathbb{1}[O_c\ge B_U]
\]

\[
G_L(c)=\mathbb{1}[O_c\le B_L]
\]

\[
T_U(c)=\mathbb{1}[H_c\ge B_U]
\]

\[
T_L(c)=\mathbb{1}[L_c\le B_L].
\]

Resolve in this order:

1. `G_U(c)=1` → `BUY`;
2. `G_L(c)=1` → `SELL`;
3. `T_U(c)=1` and `T_L(c)=0` → `BUY`;
4. `T_L(c)=1` and `T_U(c)=0` → `SELL`;
5. `T_U(c)=1` and `T_L(c)=1` → exclusion;
6. otherwise continue.

If no directional event resolves before `a+H`, assign `WAIT`.

The `G_U=G_L=1` state is impossible when the required barrier invariant
holds. If observed due to invalid data or arithmetic failure, exclude under
`BARRIER_INVARIANT_FAILED`.

## Expected Advantages

### Direct opportunity semantics

The label represents which directional condition occurs first, rather than
only where price ends. This aligns with selective opportunity identification.

### First-class abstention

`WAIT` has a positive, auditable definition: a complete future interval
expired without either qualifying event.

### Point-in-time volatility adaptation

ATR scaling reduces the inconsistency of fixed absolute-price barriers across
changing price and volatility states.

### Bounded availability

Every valid origin resolves no later than 60 minutes after the reference
time.

### Conservative ambiguity handling

Unobservable OHLC order is excluded rather than fabricated.

### Cross-timeframe clock consistency

The same elapsed horizon is used without pooling populations.

### Reproducibility

All formulas, ordering rules, precision, canonicalization, memberships, and
hashes are explicit.

## Expected Weaknesses

### Parameter dependence

`ATR14`, `1.5`, and 60 minutes materially determine class semantics.

### Intrabar information loss

OHLC cannot resolve every first-touch order.

### Exclusion bias

Ambiguous, missing, and invalid paths may be systematically associated with
high volatility.

### Overlapping outcomes

Adjacent origins share most of their future path, reducing effective sample
size.

### Reference idealization

The next candle open is an evaluation anchor, not guaranteed executable
evidence.

### Regime instability

ATR scaling may not fully normalize market states.

### Coarse 15-minute path

Only four candles are observed over the one-hour horizon, increasing
dual-touch uncertainty relative to `5m`.

## Failure Modes

The policy must fail closed when:

- an approved source run cannot be resolved;
- source hashes differ;
- timestamps are noncanonical;
- candles are missing, duplicated, incomplete, or invalid;
- feature availability exceeds the evidence cutoff;
- `ATR14` warm-up or continuity fails;
- `ATR14` is nonpositive;
- barrier ordering fails;
- the reference candle is not the immediate next candle;
- the outcome interval is incomplete;
- dual-touch order is unobservable;
- policy configuration differs from the approved hash;
- quantization is inconsistent;
- a run is partially persisted;
- repeated generation changes semantic hashes; or
- any protected-test evidence is accessed prematurely.

Failure must produce an auditable run failure or observation exclusion. It
must never produce `WAIT`.

## Statistical Risks

### Backtest and research overfitting

Trying multiple barriers, horizons, volatility estimators, ambiguity rules,
and class thresholds increases selection bias. The policy must be frozen
before class or model evidence is used. Bailey et al. show why repeated
strategy selection can make ordinary holdout evidence unreliable.

### Label-policy overfitting

The label itself can be optimized to create favorable-looking class balance
or predictive metrics. Version `1.0.0` permits one confirmatory
parameterization only.

### Scale-induced target dependence

The barrier scale is derived from `true_range`, which is also an approved
prediction-time feature. This is not look-ahead leakage because the scale is
available at the evidence cutoff, but it mechanically links label difficulty
to an input feature. Research reports must disclose this endogeneity and must
not describe the relationship as independent evidence of predictive skill.

### Serial dependence

Overlapping one-hour paths violate independent-observation assumptions.
Nominal counts must not be used as independent sample counts.

### Nonstationarity

BTC/USD behavior can shift over time. Fold and monthly class diagnostics are
mandatory.

### Class imbalance

Wide barriers may dominate with `WAIT`; narrow barriers may create noisy
directional classes. The response is review, not after-the-fact threshold
tuning.

### Ambiguity selection

Dual-touch exclusions can remove the most volatile observations and alter the
research population.

### Multiple-timeframe multiplicity

Three timeframe studies are three populations and comparisons. Favorable
results cannot be pooled selectively.

### Protected-test contamination

Inspecting test class counts or exclusions can influence policy changes even
without model training. Those outputs remain sealed.

### Method-to-product mismatch

Triple-barrier-style labels are not universally suitable. Recent BTC research
in fixed-resolution binary prediction markets reports that triple-barrier
labels can underperform when their event semantics do not match the evaluated
payoff. AlphaLens is not a binary prediction venue, but the result reinforces
the need to validate semantic alignment rather than assume the methodology is
superior.

## Implementation Constraints

If approved, implementation must:

- use the existing non-executable Phase 5 label infrastructure;
- introduce no default parameter outside this document;
- register the exact approved configuration and hash;
- consume only Phase 3 pipeline `2.0.0` evidence;
- preserve separate timeframe runs;
- use Decimal only;
- load no future candle into prediction features;
- calculate labels only retrospectively;
- retain complete source memberships;
- persist label and exclusion evidence transactionally;
- promote a run only after every validation and hash passes;
- roll back on any failure;
- leave existing v1 targets untouched;
- expose no API;
- create no confidence;
- construct no model-ready dataset until label validation receives separate
  approval; and
- prevent protected-test inspection.

No implementation may call the barrier levels entries, stops, take profits,
or trading instructions.

## Required Validation Tests

### Formula tests

- exact `ATR14` arithmetic mean;
- 14-value warm-up;
- Decimal quantization;
- symmetric barrier construction;
- positive and ordered barrier invariant;
- inclusive equality;
- no floating-point conversion.

### First-touch tests

- upper-only touch → `BUY`;
- lower-only touch → `SELL`;
- no touch through expiry → `WAIT`;
- first upper then later lower → `BUY`;
- first lower then later upper → `SELL`;
- gap-open upper resolution;
- gap-open lower resolution;
- high/low dual touch with open between → exclusion;
- touch on final eligible candle;
- equality on each barrier;
- no event after expiry affects the label.

### Chronology tests

- future path begins at the exact reference candle;
- every feature is available by the evidence cutoff;
- no label field appears in features;
- directional availability equals resolving candle close;
- `WAIT` availability equals horizon expiry;
- incomplete horizon is excluded;
- prefix reconstruction is invariant;
- non-UTC and misaligned timestamps fail.

### Data-quality tests

- missing reference candle;
- missing path candle;
- duplicate timestamp;
- incomplete candle;
- impossible OHLC;
- invalid volume;
- broken provenance;
- hash mismatch;
- zero `ATR14`;
- barrier invariant failure.

### Multi-timeframe tests

- exactly 12 `5m` path candles;
- exactly 6 `10m` path candles;
- exactly 4 `15m` path candles;
- same 60-minute expiry;
- separate policy and result identities;
- no cross-timeframe join.

### Dataset-boundary tests

- purge every label crossing a boundary;
- retain only labels available strictly before a boundary;
- enforce 60-minute embargo;
- prevent random or shuffled split generation;
- reproduce calendar-time fold boundaries;
- seal the last 20%;
- prevent protected-test summary access.

### Persistence and audit tests

- immutable policy identity;
- no duplicate policy version per scope;
- transactional run persistence;
- exact source memberships;
- exact label memberships;
- class-versus-exclusion exclusivity;
- deterministic configuration hash;
- deterministic observation hashes;
- deterministic run result hash;
- repeated-run semantic equality;
- zero partial active runs after injected failure;
- supersession without overwrite.

### Live validation requirements

After implementation approval, but before dataset approval:

- run independently for `5m`, `10m`, and `15m`;
- use live or newly retrieved Kraken evidence only through the approved
  ingestion layer;
- report exact source ranges;
- report class and exclusion counts from development-eligible evidence only;
- verify zero incomplete candles;
- regenerate twice from identical snapshots;
- confirm identical configuration, source, provenance, observation, and
  result hashes; and
- keep protected-test evidence uncomputed or cryptographically sealed.

Live validation is methodological verification, not evidence that the policy
is predictive.

## Research Basis

This recommendation draws on established event-labeling and chronological
validation principles:

- López de Prado describes the triple-barrier method as two price barriers
  plus a vertical time barrier in *Advances in Financial Machine Learning*;
  the method is the conceptual basis, not authority for AlphaLens-specific
  parameters.
- Rolling-origin evaluation preserves the forecasting direction by fitting
  on earlier observations and evaluating later observations.
- Financial research is especially vulnerable to backtest overfitting when
  many alternatives are tried and selected.
- Kraken documents continuous 24/7/365 crypto market-data availability,
  supporting elapsed-time rather than exchange-session horizons for BTC/USD.

Primary and publisher sources:

1. Marcos López de Prado, *Advances in Financial Machine Learning*, Wiley,
   2018:
   <https://www.wiley-vch.de/de/fachgebiete/finanzen-wirtschaft-recht/finanz-und-anlagewesen-13fi/spezialthemen-finanz-u-anlagewesen-13fiz/advances-in-financial-machine-learning-978-1-119-48208-6>
2. David H. Bailey, Jonathan Borwein, Marcos López de Prado, and Qiji Jim Zhu,
   “The Probability of Backtest Overfitting,” *Journal of Computational
   Finance*, 2015:
   <https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253>
3. Christoph Bergmeir, Rob J. Hyndman, and Bonsoo Koo, “A Note on the
   Validity of Cross-Validation for Evaluating Autoregressive Time Series
   Prediction,” *Computational Statistics & Data Analysis* 120, 2018:
   <https://robjhyndman.com/publications/cv-time-series/>
4. Rob J. Hyndman, “Cross-validation for time series,” 2016:
   <https://robjhyndman.com/hyndsight/tscv/>
5. Bryan T. Kelly and Dacheng Xiu, “Financial Machine Learning,” NBER Working
   Paper 31502, 2023:
   <https://www.nber.org/papers/w31502>
6. Kraken API Center:
   <https://docs.kraken.com/>
7. Nicolae Filip Stanciu, “Why Triple Barrier Labeling Fails in
   Fixed-Resolution Binary Prediction Markets: An Empirical Study on BTC/USD
   5-Minute Contracts,” 2026, used only as a caution about semantic mismatch:
   <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6519542>

## Final Recommendation

Approve Candidate C policy `candidate_c_first_touch_atr` version `1.0.0` for
implementation review with:

- next-contiguous-candle open reference;
- point-in-time arithmetic `ATR14`;
- symmetric `1.5 × ATR14` barriers;
- a 60-minute elapsed horizon;
- inclusive first-touch comparison;
- open-before-high/low gap precedence;
- dual-touch exclusion when OHLC order is unknowable;
- explicit `WAIT` only on clean time expiry;
- separate `5m`, `10m`, and `15m` populations;
- Decimal `38,18`-compatible values and round-half-even;
- retained overlapping origins with concurrency evidence;
- strict purge and 60-minute embargo;
- five expanding development folds;
- a final sealed 20% chronological test;
- the stated adequacy and class-monitoring gates;
- immutable semantic versions;
- canonical SHA-256 hashes; and
- complete candle, feature, policy, label, and dataset provenance.

The recommendation is suitable as AlphaLens' first confirmatory labeling
policy because it balances:

- opportunity selectivity;
- an explicit abstention class;
- responsiveness to prevailing range;
- intraday boundedness;
- path awareness;
- conservative ambiguity treatment; and
- exact auditability.

Approval would authorize a later, separately requested implementation
milestone. Until that approval is explicit, no label, dataset, experiment,
model, confidence value, decision, ranking, or scanner output may be
generated.
