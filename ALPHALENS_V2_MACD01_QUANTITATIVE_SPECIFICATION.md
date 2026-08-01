# AlphaLens v2 MACD-01 Quantitative Specification

**Document type:** Feature-specific quantitative specification

**Feature:** MACD-01

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

## 1. Purpose

This document defines only the mathematics and quantitative meaning of
MACD-01.

MACD-01 measures the difference between a fast and a slow exponentially
smoothed canonical Close series, the exponentially smoothed baseline of that
difference, and the residual between the difference and its baseline. It
produces three related quantitative outputs and makes no trading, crossover,
trend, momentum, or predictive claim.

All engineering behavior is inherited from
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`. This document does not define
or modify numeric representation, registry behavior, pipeline execution,
availability representation, missing-data handling, persistence, provenance,
hashing, versioning, or testing architecture.

If this document appears to conflict with the Feature Architecture Standard,
the Feature Architecture Standard governs and implementation remains blocked
until the conflict is resolved through approval.

## 2. Mathematical Input and EMA Dependencies

For one asset, quote currency, and timeframe, let the canonical chronological
Close sequence be:

\[
C_0, C_1, C_2, \ldots, C_t
\]

MACD-01 requires two approved EMA output sequences derived from that exact
Close sequence and canonical origin:

- a fast EMA sequence with period 12, denoted \(F_t\); and
- a slow EMA sequence with period 26, denoted \(S_t\).

The fast and slow sequences are required derived-feature inputs. Their values
must come from separately approved EMA definitions with the exact periods and
mathematical identities specified here. MACD-01 does not authorize those EMA
definitions and does not permit either sequence to be replaced by EMA-01's
20-observation output.

The two dependency sequences must describe the same canonical Close lineage,
scope, timeframe, timestamp, and recursive origin. A mathematical MACD line
value exists only at positions where both required EMA values exist.

## 3. Fixed Periods

The MACD-01 periods are exactly:

\[
N_f = 12
\]

for the fast EMA,

\[
N_s = 26
\]

for the slow EMA, and

\[
N_{sig} = 9
\]

for the signal EMA.

The required ordering is:

\[
0 < N_f < N_s
\]

All three periods count consecutive observations in their respective input
sequences. They are fixed and are not configurable within MACD-01. Changing
any period defines different mathematics.

## 4. Fast and Slow EMA Mathematics

The fast EMA smoothing constant is:

\[
\alpha_f = \frac{2}{N_f + 1} = \frac{2}{13}
\]

The fast EMA is initialized by the arithmetic mean of the first exactly 12
canonical Close observations:

\[
F_{11} = \frac{1}{12}\sum_{i=0}^{11} C_i
\]

For every position \(t \geq 12\), its recurrence is:

\[
F_t = \alpha_f C_t + (1-\alpha_f)F_{t-1}
\]

The slow EMA smoothing constant is:

\[
\alpha_s = \frac{2}{N_s + 1} = \frac{2}{27}
\]

The slow EMA is initialized by the arithmetic mean of the first exactly 26
canonical Close observations:

\[
S_{25} = \frac{1}{26}\sum_{i=0}^{25} C_i
\]

For every position \(t \geq 26\), its recurrence is:

\[
S_t = \alpha_s C_t + (1-\alpha_s)S_{t-1}
\]

These equations state the quantitative identities that required EMA
dependencies must satisfy. A MACD-01 implementation must consume the approved
dependency outputs and must not independently recalculate these EMA
sequences.

## 5. MACD Line Definition

For every sequence position \(t \geq 25\), define the MACD line as:

\[
M_t = F_t - S_t
\]

No MACD line value exists before position 25 because the slow EMA is not yet
mathematically defined.

The MACD line is an unnormalized signed price difference. It is expressed in
the same quote-price units as canonical Close. Positive, zero, and negative
values are all valid.

## 6. Signal Initialization and Recurrence

The signal sequence is an EMA of the compact chronological MACD line
sequence. The signal period is exactly 9 and its smoothing constant is:

\[
\alpha_{sig} = \frac{2}{N_{sig}+1} = \frac{1}{5}
\]

The first nine MACD line values are:

\[
M_{25}, M_{26}, \ldots, M_{33}
\]

The signal is initialized with their arithmetic mean:

\[
Q_{33} = \frac{1}{9}\sum_{i=25}^{33} M_i
\]

For every sequence position \(t \geq 34\), the signal recurrence is:

\[
Q_t = \alpha_{sig}M_t + (1-\alpha_{sig})Q_{t-1}
\]

Equivalently:

\[
Q_t = \frac{1}{5}M_t + \frac{4}{5}Q_{t-1}
\]

The signal seed is formed from the first exactly nine mathematically valid
MACD line observations. The compact MACD line sequence retains its original
Close timestamps; it is not reindexed to the beginning of the Close series.

The signal is initialized exactly once. It is not seeded from fewer than nine
MACD line values, reset, or reseeded later.

## 7. Histogram Definition

For every position at which the signal is mathematically defined, the MACD
histogram is:

\[
H_t = M_t - Q_t
\]

The first histogram value is therefore \(H_{33}\). No histogram value exists
before position 33.

The histogram is a signed residual in the same quote-price units as canonical
Close. Positive, zero, and negative values are all valid.

## 8. Initialization and Warm-Up Mathematics

The exact mathematical boundaries are:

| Output | Required observations | First sequence position | First mathematical value |
| --- | ---: | ---: | --- |
| MACD line | 26 consecutive Close observations | 25 | \(M_{25}=F_{25}-S_{25}\) |
| Signal | 34 consecutive Close observations | 33 | Arithmetic mean of \(M_{25}\) through \(M_{33}\) |
| Histogram | 34 consecutive Close observations | 33 | \(H_{33}=M_{33}-Q_{33}\) |

For a valid canonical Close sequence containing \(m\) observations, the
number of mathematically defined MACD line values is:

\[
\max(0,m-25)
\]

The number of mathematically defined signal values is:

\[
\max(0,m-33)
\]

The number of mathematically defined histogram values is:

\[
\max(0,m-33)
\]

The representation and validation of mathematically undefined warm-up
positions are inherited exclusively from the Feature Architecture Standard.

## 9. Output Meaning

MACD-01 has exactly three quantitative outputs:

### 9.1 MACD line

The MACD line is the fast 12-observation EMA value minus the slow
26-observation EMA value at the same timestamp. It measures signed separation
between the two approved EMA baselines.

### 9.2 Signal

The signal is the 9-observation EMA of the compact chronological MACD line
sequence, initialized from the first nine MACD line values. It is a smoothed
baseline of the MACD line.

### 9.3 Histogram

The histogram is the contemporaneous MACD line minus the signal. It measures
the signed residual between the line and its smoothed baseline.

All three outputs use quote-price units. None is a return, ratio, percentage,
probability, categorical state, crossover event, direction label, or trading
signal.

## 10. Edge Cases

### 10.1 Equal fast and slow EMA values

If \(F_t=S_t\), then:

\[
M_t=0
\]

Zero is a valid MACD line value.

### 10.2 Equal MACD line and signal values

If \(M_t=Q_t\), then:

\[
H_t=0
\]

Zero is a valid histogram value.

### 10.3 Constant canonical Close sequence

For a constant valid Close sequence, the fast and slow EMA values are equal
after their respective initialization boundaries. Every mathematically valid
MACD line, signal, and histogram value is therefore exactly zero.

### 10.4 Negative values

A negative MACD line, signal, or histogram value is mathematically valid and
must not be clamped, absolutized, or treated as missing.

### 10.5 Insufficient history

No output is mathematically defined before its boundary in Section 8. The
signal and histogram do not use a partial nine-value seed.

### 10.6 Invalid or unavailable inputs

MACD-01 defines no imputation, skipping, interpolation, fallback, reset,
partial seed, or alternate-input mathematics. Handling of invalid, missing,
discontinuous, unavailable, or incompatible evidence is inherited from the
Feature Architecture Standard.

## 11. Deterministic Mathematical Behavior

For fixed canonical fast and slow EMA dependency sequences with fixed origins,
MACD-01 has exactly one valid mathematical output sequence.

Deterministic mathematical behavior requires:

1. the fast and slow periods are exactly 12 and 26;
2. the MACD line uses contemporaneous fast and slow EMA values;
3. the first MACD line value occurs at the slow EMA's first-valid position;
4. the signal seed contains exactly the first nine MACD line values;
5. the signal seed retains the original MACD line timestamps;
6. every later signal uses only the current MACD line and immediately
   preceding signal state;
7. every histogram uses the MACD line and signal at the same timestamp;
8. no future Close, EMA, MACD line, or signal value changes an earlier output;
9. no dependency EMA or signal sequence is silently reset or reseeded; and
10. no feature-specific intermediate rounding changes the recursive path.

There is no MACD-specific intermediate rounding rule. Shared mathematical
numeric behavior is inherited from the Feature Architecture Standard.

## 12. Quantitative Invariants

Every conforming MACD-01 implementation must preserve these mathematical
invariants:

1. The fast EMA period is exactly 12.
2. The slow EMA period is exactly 26.
3. The signal EMA period is exactly 9.
4. The fast and slow EMA dependencies use arithmetic-mean initialization and
   their approved EMA recurrences.
5. The MACD line equals fast EMA minus slow EMA.
6. The first MACD line is associated with the twenty-sixth Close.
7. The signal is initialized from the arithmetic mean of the first exactly
   nine MACD line values.
8. The first signal and histogram are associated with the thirty-fourth
   Close.
9. Every later signal uses the approved recursive equation.
10. The histogram equals contemporaneous MACD line minus signal.
11. All outputs remain signed price-unit quantities.
12. No sequence is silently reset, reseeded, normalized, or replaced by an
    alternative library convention.

Changing any invariant defines different mathematics and requires a
separately approved quantitative specification and release identity.

## 13. Architecture Inheritance

MACD-01 inherits the Feature Architecture Standard without exception. This
specification intentionally does not define a MACD-specific alternative for:

- Decimal representation or output quantization;
- warm-up representation;
- source continuity and missing-data handling;
- availability;
- registry identity or behavior;
- dependency resolution and validation;
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
Standard and later approved MACD-01 engineering contracts.

## 14. Non-Goals

This specification does not define or authorize:

- an EMA(12) or EMA(26) registry definition or implementation;
- recalculation of a registered EMA dependency inside MACD-01;
- a 20-observation EMA substitute for either required dependency;
- alternate MACD periods or MACD variants;
- normalized or percentage MACD;
- crossover events;
- trend or momentum classifications;
- signals, rankings, strategies, or trading decisions;
- parameter optimization;
- visualization;
- implementation code;
- registry changes;
- persistence or migrations;
- Bollinger Bands, VWAP, ADX, Supertrend, or another feature family.

## 15. Implementation Gate

The mathematics in this document requires separately approved and registered
EMA(12) and EMA(26) derived-feature outputs. Until both exact dependencies
exist in deterministic registry order and are available to MACD-01 through
the shared dependency graph, implementation must remain blocked under the
Feature Architecture Standard.

This document does not authorize creation of those missing EMA definitions.
