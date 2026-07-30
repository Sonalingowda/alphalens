# AlphaLens v2 Tier-A Feature Specification

## Status

**Specification status:** Proposed for human approval  
**Feature implementation status:** Not started  
**Definition version:** `1.0.0`

This document freezes the proposed first production feature set for AlphaLens
v2 Phase 3. It specifies feature meanings only. It does not implement feature
calculations, register executable features, or authorize later Phase 3
milestones.

## Governing Contracts

This specification is subordinate to:

- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_PHASE_1_BASELINE.md`;
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`;
- `ALPHALENS_V2_PHASE_3_FEATURE_ENGINEERING_PLAN.md`; and
- `ALPHALENS_V2_FEATURE_CATALOG_PROPOSAL.md`.

No governing document is modified by this specification.

## Tier-A Scope

The proposed Tier-A registry contains exactly two feature definitions in this
deterministic order:

1. `candle_geometry`;
2. `true_range`.

They correspond exclusively to:

- Candidate 2 — Candle Geometry; and
- Candidate 12 — True Range

from `ALPHALENS_V2_FEATURE_CATALOG_PROPOSAL.md`.

No other catalog candidate is approved as Tier-A by this specification.

## Shared Quantitative Policy

### Time and availability

For a canonical candle-open timestamp `t` and timeframe duration `D`, every
Tier-A output is available at:

\[
\operatorname{available\_at}(t) = t + D
\]

The supported durations are:

| Timeframe | Duration |
| --- | --- |
| `5m` | 5 minutes |
| `10m` | 10 minutes |
| `15m` | 15 minutes |

All timestamps must be canonical UTC timestamps aligned to their timeframe.
An output must not exist before its `available_at` timestamp.

### Numeric policy

- Every market-data input must be a finite `Decimal`.
- Intermediate arithmetic uses Decimal context precision of 50 digits.
- Final scalar outputs are quantized to:

  ```text
  0.000000000000000001
  ```

- Rounding mode is `ROUND_HALF_EVEN`.
- Binary floating-point arithmetic is prohibited.
- NaN, positive infinity, and negative infinity are prohibited.

### Input policy

Only validated, complete, strictly chronological, gap-free Phase 2 candles
may be used.

If a required input is missing, malformed, incomplete, duplicated,
misaligned, non-chronological, non-finite, or violates the approved OHLC
relationships, computation fails closed. The pipeline must not interpolate,
forward-fill, backward-fill, substitute, fabricate, or repair the value.

Legitimate warm-up absence is represented by omission of the feature output.
It is not represented by null, zero, or another placeholder.

## Feature 1 — Candle Geometry

### Identity

| Attribute | Definition |
| --- | --- |
| Identifier | `candle_geometry` |
| Definition version | `1.0.0` |
| Category | Price action |
| Candidate source | Candidate 2 — Candle Geometry |
| Required inputs | Completed `open`, `high`, `low`, and `close` at `t` |
| Supported timeframes | `5m`, `10m`, `15m` |
| Warm-up | One consecutive completed candle |
| Availability | `t + D` |
| Registered-feature dependencies | None |
| History type | Bounded |
| Maximum lookback | One observation |
| Continuity required | Yes |

### Mathematical definition

For a completed candle at timestamp `t`, let:

- \(O_t\) be open;
- \(H_t\) be high;
- \(L_t\) be low; and
- \(C_t\) be close.

Phase 2 validation guarantees:

\[
O_t > 0
\]

and:

\[
L_t \leq O_t \leq H_t
\]

\[
L_t \leq C_t \leq H_t
\]

The four outputs are:

#### Signed body fraction

\[
\operatorname{candle\_body\_fraction}_t
=
\frac{C_t - O_t}{O_t}
\]

#### Total range fraction

\[
\operatorname{candle\_range\_fraction}_t
=
\frac{H_t - L_t}{O_t}
\]

#### Upper-wick fraction

\[
\operatorname{upper\_wick\_fraction}_t
=
\frac{H_t - \max(O_t, C_t)}{O_t}
\]

#### Lower-wick fraction

\[
\operatorname{lower\_wick\_fraction}_t
=
\frac{\min(O_t, C_t) - L_t}{O_t}
\]

Normalization by the strictly positive open price makes these outputs
dimensionless and avoids undefined division for a zero-range candle.

### Outputs

| Output name | Definition | Earliest observation |
| --- | --- | --- |
| `candle_body_fraction` | Signed close-to-open change divided by open | First candle |
| `candle_range_fraction` | High-low range divided by open | First candle |
| `upper_wick_fraction` | Upper wick divided by open | First candle |
| `lower_wick_fraction` | Lower wick divided by open | First candle |

All four outputs must be emitted together for an eligible timestamp. A
partial Candle Geometry output set is invalid.

### Decimal and rounding policy

Each division is evaluated with Decimal precision 50. Each final output is
independently quantized to 18 decimal places using `ROUND_HALF_EVEN`.

The unquantized values remain the mathematical definition. Quantization is
the canonical persistence representation.

### Missing-data behavior

- Before the first completed candle: no output exists.
- At and after the first completed candle: all four outputs are required.
- If any OHLC input is unavailable or invalid, no output is valid for that
  timestamp and the feature run fails closed.
- The feature must not emit a partial subset of its outputs.

### Edge-case handling

| Condition | Required behavior |
| --- | --- |
| Flat candle, \(O_t = H_t = L_t = C_t\) | Emit zero for all four outputs. |
| Doji, \(O_t = C_t\) | Emit zero signed body; wick and range outputs remain defined normally. |
| Close above open | Signed body fraction is positive. |
| Close below open | Signed body fraction is negative. |
| Open is zero or negative | Reject input; do not emit values. |
| Invalid OHLC ordering | Reject input; do not emit values. |
| Missing or non-finite input | Reject input; do not emit values. |
| Incomplete candle | Reject input; do not emit values. |

No clipping is permitted.

### Provenance requirements

Every persisted output must retain:

- feature identifier `candle_geometry`;
- definition version `1.0.0`;
- exact output name;
- source candle identity;
- source ingestion-batch membership;
- source-data hash;
- feature registry hash and snapshot;
- feature pipeline version;
- candle timestamp;
- `available_at`;
- Decimal quantum and rounding policy;
- computation-run identity; and
- point-in-time validation status.

### Validation rules

The definition must pass:

1. exact known-input examples for all four outputs;
2. exact flat-candle and doji cases;
3. positive and negative body cases;
4. rejection of missing, incomplete, non-finite, non-positive-open, and
   invalid-OHLC inputs;
5. output-name and definition-version registry checks;
6. one-observation warm-up verification;
7. exact `available_at = t + D` verification for every supported timeframe;
8. deterministic repeatability;
9. prefix invariance for every source prefix;
10. future-candle mutation isolation;
11. duplicate output prevention; and
12. pre-quantization invariants:

\[
\operatorname{candle\_range\_fraction}_t
=
\left|\operatorname{candle\_body\_fraction}_t\right|
+
\operatorname{upper\_wick\_fraction}_t
+
\operatorname{lower\_wick\_fraction}_t
\]

The three unsigned outputs must be non-negative. The absolute signed body
fraction must not exceed the total range fraction.

### Research hypothesis

The relative geometry of a completed candle may distinguish directional
movement, rejection, and local indecision using only information available
when that candle closes.

This is an untested research hypothesis. The feature does not imply a
decision, causal relationship, confidence value, or trading outcome.

## Feature 2 — True Range

### Identity

| Attribute | Definition |
| --- | --- |
| Identifier | `true_range` |
| Definition version | `1.0.0` |
| Category | Volatility |
| Candidate source | Candidate 12 — True Range |
| Required inputs | Completed `high` and `low` at `t`; completed `close` at `t-1` |
| Supported timeframes | `5m`, `10m`, `15m` |
| Warm-up | Two consecutive completed candles |
| Availability | `t + D` |
| Registered-feature dependencies | None |
| History type | Bounded |
| Maximum lookback | Two observations |
| Continuity required | Yes |

### Mathematical definition

For a completed candle at timestamp `t`, let:

- \(H_t\) be the current high;
- \(L_t\) be the current low; and
- \(C_{t-1}\) be the immediately preceding completed candle’s close.

The preceding candle must be exactly one approved timeframe duration before
the current candle:

\[
\operatorname{timestamp}(C_{t-1}) = t - D
\]

True Range is:

\[
\operatorname{true\_range}_t
=
\max
\left(
H_t - L_t,
\left|H_t - C_{t-1}\right|,
\left|L_t - C_{t-1}\right|
\right)
\]

### Outputs

| Output name | Definition | Earliest observation |
| --- | --- | --- |
| `true_range` | Maximum of current range and current-extreme displacement from the preceding close | Second consecutive candle |

The output remains in the BTC/USD quote-price unit. No normalization or
annualization is part of definition `1.0.0`.

### Decimal and rounding policy

All subtraction, absolute-value, and maximum operations use Decimal values.
The final result is quantized to 18 decimal places using `ROUND_HALF_EVEN`
under Decimal precision 50.

### Missing-data behavior

- At the first candle in a continuous series: omit `true_range` as legitimate
  warm-up absence.
- From the second consecutive candle onward: exactly one output is required
  per candle.
- If the preceding candle is absent or not exactly `D` before the current
  candle, the input series is discontinuous and the feature run fails closed.
- Missing inputs must never be replaced with the current open, current close,
  zero, or another substitute.

### Edge-case handling

| Condition | Required behavior |
| --- | --- |
| Current high equals current low | True Range may still be positive because of displacement from the preceding close. |
| Current candle and preceding close are all at the same price | Emit zero. |
| Preceding close lies inside the current high-low range | True Range equals current high minus current low. |
| Preceding close lies above the current high | True Range equals preceding close minus current low. |
| Preceding close lies below the current low | True Range equals current high minus preceding close. |
| Missing immediately preceding candle | Reject the run as discontinuous. |
| Non-positive price or invalid OHLC ordering | Reject input; do not emit a value. |
| Missing or non-finite input | Reject input; do not emit a value. |
| Incomplete current or preceding candle | Reject input; do not emit a value. |

No clipping, normalization, or replacement is permitted.

### Provenance requirements

Every persisted output must retain:

- feature identifier `true_range`;
- definition version `1.0.0`;
- output name `true_range`;
- identities of the current and immediately preceding source candles;
- all contributing ingestion-batch memberships;
- source-data hash;
- feature registry hash and snapshot;
- feature pipeline version;
- current candle timestamp;
- `available_at`;
- Decimal quantum and rounding policy;
- computation-run identity; and
- point-in-time validation status.

### Validation rules

The definition must pass:

1. exact known-input examples for each branch of the maximum;
2. exact zero-range and gap-displacement cases;
3. omission at the first candle;
4. exact first-valid timestamp at the second consecutive candle;
5. rejection of a missing or non-consecutive preceding candle;
6. rejection of missing, incomplete, non-finite, non-positive-price, and
   invalid-OHLC inputs;
7. output-name and definition-version registry checks;
8. exact `available_at = t + D` verification for every supported timeframe;
9. deterministic repeatability;
10. prefix invariance for every source prefix;
11. future-candle mutation isolation;
12. duplicate output prevention; and
13. the invariants:

\[
\operatorname{true\_range}_t \geq 0
\]

\[
\operatorname{true\_range}_t \geq H_t - L_t
\]

### Research hypothesis

The completed candle’s total range, including displacement from the preceding
close, may describe changes in short-horizon market variability that are not
fully represented by the current high-low range alone.

This is an untested research hypothesis. True Range does not imply future
volatility, a decision, calibrated confidence, or a trading outcome.

## Registry Snapshot Requirements

When approved and later registered, the Tier-A registry must preserve this
exact deterministic ordering:

1. `candle_geometry`;
2. `true_range`.

The registry must expose exactly these output names in definition order:

1. `candle_body_fraction`;
2. `candle_range_fraction`;
3. `upper_wick_fraction`;
4. `lower_wick_fraction`;
5. `true_range`.

Changing membership, order, identifiers, output names, mathematical
definitions, warm-ups, supported timeframes, availability, precision, or
edge-case behavior requires:

- a new feature-definition version where applicable;
- a new registry hash;
- a new feature pipeline version;
- a documented change rationale and impact assessment; and
- explicit human approval.

Historical definitions and outputs must remain immutable.

## Explicitly Unresolved Decisions

The following remain unresolved and are not authorized by this specification:

1. the intraday feature pipeline version identifier;
2. inclusion of any other candidate from the Feature Catalog Proposal;
3. normalized or averaged True Range variants;
4. rolling windows, smoothing methods, thresholds, or multipliers;
5. cross-timeframe features;
6. feature selection or predictive-utility claims;
7. targets, labels, models, decision rules, ranking, and calibration; and
8. use of these features in research experiments.

None of these unresolved decisions blocks isolated implementation of the two
Tier-A definitions after this specification receives explicit approval.

## Approval Boundary

Approval of this specification authorizes only later implementation and
testing of the two definitions exactly as written.

It does not authorize Phase 3 Milestone 3, persistence execution, live feature
runs, research experiments, model development, decisions, ranking,
confidence, scanner behavior, or chart overlays.
