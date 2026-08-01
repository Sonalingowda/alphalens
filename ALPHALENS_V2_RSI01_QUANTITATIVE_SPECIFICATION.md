# AlphaLens v2 RSI-01 Quantitative Specification

**Document type:** Feature-specific quantitative specification

**Feature:** RSI-01

**Status:** Quantitative specification for approval

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

## 1. Purpose

This document defines only the mathematics and quantitative meaning of
RSI-01.

RSI-01 measures the bounded balance between recursively smoothed positive and
negative changes in canonical Close. It produces one dimensionless oscillator
value and makes no trading, threshold, trend, or predictive claim.

All engineering behavior is inherited from
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`. This document does not define
or modify numeric representation, registry behavior, pipeline execution,
availability representation, missing-data handling, persistence, provenance,
hashing, versioning, or testing architecture.

If this document appears to conflict with the Feature Architecture Standard,
the Feature Architecture Standard governs and implementation remains blocked
until the conflict is resolved through approval.

## 2. Mathematical Input

For one registered asset, quote currency, and timeframe, let the canonical
chronological Close sequence be:

\[
C_0, C_1, C_2, \ldots, C_t
\]

For each sequence position \(t \geq 1\), define the one-observation Close
change:

\[
\Delta_t = C_t - C_{t-1}
\]

Define the corresponding non-negative gain and loss magnitudes:

\[
G_t = \max(\Delta_t, 0)
\]

\[
L_t = \max(-\Delta_t, 0)
\]

Exactly one of \(G_t\) and \(L_t\) is positive for a nonzero change. Both are
zero when Close is unchanged.

Canonical Close is the sole mathematical input series. RSI-01 has no required
upstream derived-feature dependency.

## 3. Period

The RSI-01 period is exactly:

\[
N = 14
\]

The period counts consecutive Close-to-Close changes. A complete period
therefore requires exactly 15 consecutive Close observations.

The period is fixed for RSI-01 and is not configurable within this feature.
Changing the period defines different feature mathematics.

## 4. Initialization

The recursive sequence begins at the canonical origin of the versioned source
lineage governed by the Feature Architecture Standard.

The initial average gain is the arithmetic mean of the first exactly 14 gain
magnitudes:

\[
\overline{G}_{14}
= \frac{1}{14}\sum_{i=1}^{14}G_i
\]

The initial average loss is the arithmetic mean of the first exactly 14 loss
magnitudes:

\[
\overline{L}_{14}
= \frac{1}{14}\sum_{i=1}^{14}L_i
\]

The seed membership is exactly the 14 changes derived from:

\[
C_0, C_1, \ldots, C_{14}
\]

The initialization is performed once for a canonical RSI-01 sequence. The
averages are not initialized from fewer observations and are not reseeded at
a later timestamp.

## 5. Smoothing Method

After initialization, RSI-01 uses Wilder smoothing.

For every sequence position \(t > 14\), the smoothed average gain is:

\[
\overline{G}_t
= \frac{13\overline{G}_{t-1} + G_t}{14}
\]

The smoothed average loss is:

\[
\overline{L}_t
= \frac{13\overline{L}_{t-1} + L_t}{14}
\]

Equivalently, each prior smoothed average has weight \(13/14\), and the
current gain or loss magnitude has weight \(1/14\).

No simple rolling mean, exponential smoothing constant based on another
period convention, cutler-style RSI, full-series library seed, or alternative
gain/loss smoother is permitted.

There is no RSI-specific intermediate rounding rule. Mathematical recursive
state is carried without feature-specific intermediate quantization; shared
numeric behavior is inherited from the Feature Architecture Standard.

## 6. RSI Definition

When the smoothed average loss is positive, define relative strength as:

\[
RS_t = \frac{\overline{G}_t}{\overline{L}_t}
\]

The RSI-01 value is then:

\[
RSI_t = 100 - \frac{100}{1 + RS_t}
\]

This definition applies at initialization position \(t=14\) and at every
later mathematically eligible position, subject to the exact zero-state rules
in Section 8.

## 7. Warm-Up Mathematics

RSI-01 requires one initial Close plus 14 complete consecutive Close changes.

No RSI-01 mathematical value exists for sequence positions \(0\) through
\(13\). The first mathematically valid value is \(RSI_{14}\), associated with
\(C_{14}\), after exactly 15 Close observations.

For a valid canonical sequence containing \(m\) Close observations, the
number of mathematically defined RSI-01 values is:

\[
\max(0, m - 14)
\]

The representation and validation of mathematically undefined warm-up
positions are inherited exclusively from the Feature Architecture Standard.

## 8. Edge Cases

### 8.1 No smoothed loss and positive smoothed gain

If:

\[
\overline{L}_t = 0
\quad\text{and}\quad
\overline{G}_t > 0
\]

then:

\[
RSI_t = 100
\]

This rule avoids division by zero and represents an eligible sequence whose
smoothed movement contains gain but no loss.

### 8.2 No smoothed gain and positive smoothed loss

If:

\[
\overline{G}_t = 0
\quad\text{and}\quad
\overline{L}_t > 0
\]

then:

\[
RSI_t = 0
\]

This is also the direct limiting result of the standard RSI equation.

### 8.3 No smoothed gain and no smoothed loss

If:

\[
\overline{G}_t = 0
\quad\text{and}\quad
\overline{L}_t = 0
\]

then:

\[
RSI_t = 50
\]

This is the defined neutral value for a mathematically eligible sequence with
no smoothed movement. It is not a missing value and is not a trading
threshold.

### 8.4 Unchanged current Close

When \(C_t=C_{t-1}\), both current gain and current loss magnitudes are zero.
The prior smoothed averages continue through the approved Wilder recurrence.
The sequence is not reset or reseeded.

### 8.5 Invalid or unavailable mathematical input

RSI-01 defines no imputation, skip, interpolation, fallback, reset, or
partial-window mathematics. Engineering handling of invalid, missing,
discontinuous, or unavailable source evidence is inherited from the Feature
Architecture Standard.

## 9. Output Meaning

RSI-01 has exactly one quantitative output: the Relative Strength Index level
computed from the approved recursively smoothed gain and loss magnitudes.

The output is:

- dimensionless;
- bounded on the closed interval \([0,100]\);
- equal to 50 in the defined zero-gain/zero-loss state;
- a balance of smoothed positive and negative Close changes; and
- associated with the timestamp of the current Close observation.

The output is not:

- a percentage return;
- a probability;
- a direction label;
- an overbought or oversold classification;
- a threshold event;
- a divergence event;
- a trading signal; or
- a buy or sell decision.

## 10. Required Dependencies

RSI-01 requires:

- the canonical consecutive Close sequence; and
- its own immediately preceding smoothed gain and smoothed loss state after
  initialization.

It requires no registered derived feature. Close is a canonical OHLCV source
field under the Feature Architecture Standard, not a registered passthrough
feature.

The recursive averages are internal mathematical state. They are not
additional RSI-01 quantitative outputs and do not create a registry
self-dependency.

## 11. Deterministic Mathematical Behavior

For a fixed canonical Close sequence and fixed origin, RSI-01 has exactly one
valid mathematical result sequence.

Deterministic mathematical behavior requires:

1. changes are formed only from adjacent consecutive Close observations;
2. gain and loss magnitudes use the definitions in Section 2;
3. the seed contains exactly the first 14 changes;
4. initialization occurs exactly once;
5. every later state uses the immediately preceding smoothed state and the
   current gain or loss magnitude;
6. the zero-state rules in Section 8 are applied exactly;
7. no future Close changes an earlier RSI value;
8. no alternate seed, smoother, library default, reset, or reseed is used;
   and
9. no feature-specific intermediate rounding changes the recursive path.

All engineering mechanisms that enforce deterministic execution,
point-in-time correctness, prefix invariance, and future isolation are
inherited from the Feature Architecture Standard and are not redefined here.

## 12. Quantitative Invariants

Every conforming RSI-01 implementation must preserve these mathematical
invariants:

1. The period is exactly 14 Close changes.
2. Initialization requires exactly 15 consecutive Close observations.
3. Initial average gain and average loss are arithmetic means over the first
   exactly 14 gain and loss magnitudes.
4. Subsequent averages use Wilder smoothing.
5. The first output is associated with the fifteenth Close.
6. Output is bounded on \([0,100]\).
7. A positive gain state with zero loss maps to 100.
8. A positive loss state with zero gain maps to 0.
9. A zero-gain and zero-loss state maps to 50.
10. The recursive sequence is never silently reset or reseeded.
11. RSI-01 emits exactly one dimensionless level output.

Changing any invariant defines different mathematics and requires a
separately approved quantitative specification and release identity.

## 13. Architecture Inheritance

RSI-01 inherits the Feature Architecture Standard without exception. This
specification intentionally does not define an RSI-specific alternative for:

- Decimal representation or output quantization;
- warm-up representation;
- source continuity and missing-data handling;
- availability;
- registry identity or behavior;
- pipeline orchestration;
- persistence;
- provenance;
- hashing;
- versioning;
- deterministic validation;
- point-in-time validation;
- prefix-invariance validation;
- future-isolation validation; or
- implementation testing.

Those obligations must be resolved solely from the Feature Architecture
Standard and later approved RSI-01 engineering contracts.

## 14. Non-Goals

This specification does not define or authorize:

- RSI-02, RSI-03, or RSI-04;
- RSI deltas or slopes;
- distance from a neutral reference;
- overbought or oversold thresholds;
- price/RSI divergence;
- adaptive or optimized periods;
- Cutler RSI or another smoothing method;
- multiple RSI periods;
- signals, rankings, strategies, or trading decisions;
- visualization;
- implementation code;
- registry changes;
- persistence or migrations; or
- another feature family.

## 15. Approval Gate

This specification becomes authoritative only after explicit approval and
freeze.

Approval freezes only the RSI-01 mathematics and quantitative meaning in this
document. It does not authorize implementation, registry integration,
pipeline changes, persistence changes, or another feature.
