# AlphaLens v2 EMA-01 Successor Quantitative Specification

**Document type:** Feature-specific quantitative specification

**Feature:** EMA-01

**Status:** Successor specification for approval

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

**Reconciliation reference:**
`ALPHALENS_V2_EMA_ARCHITECTURE_RECONCILIATION.md`

## 1. Purpose

This document defines only the approved mathematics and quantitative meaning
of EMA-01. It replaces the architecture-incompatible EMA quantitative
definition after approval.

EMA-01 is a 20-observation exponential moving average of canonical Close. It
provides one recursively smoothed price series in the same units as Close.

This document does not define an independent engineering architecture. All
numeric representation, source validation, warm-up representation,
availability, missing-data handling, registry behavior, pipeline behavior,
persistence, provenance, hashing, versioning, determinism, point-in-time
correctness, prefix invariance, future isolation, and testing requirements are
inherited from `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`.

If this document and the Feature Architecture Standard appear to conflict,
the Feature Architecture Standard governs and EMA-01 implementation remains
blocked until the documents are reconciled through approval.

## 2. Supersession

Upon explicit approval, this document supersedes every earlier EMA-01
quantitative requirement that conflicts with the Feature Architecture
Standard or EMA Architecture Reconciliation.

The superseded requirements include feature-specific use of binary
floating-point arithmetic, nullable feature values, continuation across a
missing Close, and consumption of a separately registered passthrough Close
feature.

This supersession does not change the previously approved EMA period,
smoothing constant, recurrence, initialization mathematics, or output
meaning.

## 3. Mathematical Input Series

For one registered asset, quote currency, and timeframe, let the canonical
Close sequence be:

\[
C_0, C_1, C_2, \ldots, C_t
\]

where each \(C_t\) is the Close of the canonical completed candle at sequence
position \(t\).

The sequence is ordered chronologically and begins at the canonical recursive
origin defined in Section 7. Close is a canonical OHLCV source field under the
Feature Architecture Standard. It is not a separately calculated EMA
dependency.

## 4. Period

The EMA-01 period is exactly:

\[
N = 20
\]

The period is measured in canonical Close observations for the registered
timeframe. It is not an elapsed-clock-time duration and is not configurable
within EMA-01.

Changing the period creates different feature mathematics and is not a
compatible change to EMA-01.

## 5. Smoothing Constant

The smoothing constant is exactly:

\[
\alpha = \frac{2}{N + 1} = \frac{2}{21}
\]

The complementary weight is:

\[
1 - \alpha = \frac{19}{21}
\]

No alternative smoothing constant, decay convention, span conversion, or
library default is permitted.

## 6. Initialization

EMA-01 is initialized with the arithmetic mean of the first exactly 20 Close
observations in the canonical sequence:

\[
E_{19} = \frac{1}{20}\sum_{i=0}^{19} C_i
\]

The seed membership is exactly:

\[
C_0, C_1, \ldots, C_{19}
\]

The seed is computed once for a canonical EMA-01 sequence. EMA-01 is not
reseeded at later observations.

No EMA-01 mathematical value exists for sequence positions \(0\) through
\(18\). The first mathematically valid EMA-01 value is \(E_{19}\), after
exactly 20 Close observations.

## 7. Canonical Recursive Origin

For each registered asset, quote currency, and timeframe, the EMA-01
recursive origin is the earliest canonical, complete, valid candle in the
versioned historical source lineage selected for the EMA-01 release.

The origin candle is sequence position \(0\). Its timestamp and immutable
source identity must be frozen in release evidence before EMA-01 activation.
Every full replay for that release must use the same origin and the same
ordered history through the requested endpoint.

A source snapshot that begins after the frozen origin does not contain enough
evidence to initialize EMA-01 independently. It cannot treat its first 20
observations as a new seed. Any checkpoint or incremental path is governed by
the equivalence requirements of the Feature Architecture Standard.

Adding or selecting earlier history changes the recursive origin and seed
membership. Such a change is not compatible with the released EMA-01
sequence and requires new versioned release identities under the Feature
Architecture Standard.

This origin policy introduces no additional numeric parameter and does not
alter the approved seed formula.

## 8. Recursive Update

For every sequence position \(t \geq 20\), EMA-01 is updated exactly as:

\[
E_t = \alpha C_t + (1 - \alpha)E_{t-1}
\]

Equivalently, using the approved period:

\[
E_t = \frac{2}{21}C_t + \frac{19}{21}E_{t-1}
\]

The current value uses only the current Close and the immediately preceding
EMA state. It does not use any later Close or later EMA value.

There is no feature-specific intermediate rounding rule. The recursive state
retains the working precision required by the Feature Architecture Standard.
Canonical repository quantization applies to each emitted output, but the
quantized persisted representation must not be substituted for the
higher-precision in-run predecessor unless an approved replay-equivalent path
proves identical results.

## 9. First Valid Observation and Mathematical Warm-Up

The mathematical warm-up length is exactly 20 Close observations.

The first valid output corresponds to:

- sequence position \(19\);
- the timestamp of \(C_{19}\); and
- the initialized arithmetic mean \(E_{19}\).

For a valid canonical sequence containing \(m\) Close observations, the
number of mathematically defined EMA-01 values is:

\[
\max(0, m - 19)
\]

How mathematically undefined warm-up positions are represented, validated,
and persisted is inherited exclusively from the Feature Architecture
Standard.

## 10. Output Meaning

EMA-01 has exactly one quantitative output: the 20-observation exponentially
weighted moving average of canonical Close, seeded by the arithmetic mean of
the first 20 canonical Close observations.

The output:

- is expressed in the same quote-price units as Close;
- is a price-level feature, not a return, ratio, percentage, direction,
  probability, score, or signal; and
- is mathematically positive when all admitted Close values satisfy the
  canonical positive-price source contract.

The canonical registry feature identifier, output identifier, definition
version, supported scope, and implementation reference are engineering
metadata. They must be frozen in the aligned registry and implementation
contracts before implementation and must conform to the Feature Architecture
Standard. They do not change the quantitative meaning defined here.

## 11. Architecture Inheritance

EMA-01 inherits the Feature Architecture Standard without exception.
Accordingly, this specification does not create EMA-specific alternatives for:

- Decimal representation, working precision, or output quantization;
- warm-up omission;
- candle-close availability;
- source continuity or invalid-source handling;
- canonical Close access;
- dependency validation;
- recursive execution safeguards;
- registry ordering or discovery;
- pipeline validation;
- immutable persistence;
- source and predecessor provenance;
- canonical hashing;
- semantic versioning;
- deterministic replay;
- point-in-time correctness;
- prefix invariance;
- future isolation; or
- required testing.

Where implementation needs an engineering decision in one of these areas, it
must resolve that decision from the Feature Architecture Standard and aligned
engineering contracts, not from convention, a third-party EMA library, legacy
code, or a new quantitative assumption.

## 12. Quantitative Invariants

Every conforming EMA-01 implementation must preserve these mathematical
invariants:

1. The period is exactly 20.
2. The smoothing constant is exactly \(2/21\).
3. The seed is the arithmetic mean of exactly the first 20 canonical Close
   observations from the frozen origin.
4. The first EMA value is associated with the twentieth Close.
5. No EMA value is mathematically defined before the twentieth Close.
6. Every later value uses exactly the current Close and immediately preceding
   EMA state under the approved recurrence.
7. The sequence is never silently reseeded.
8. The output remains a quote-price-level exponentially weighted average of
   Close.

Any change to one of these invariants defines different mathematics and
requires a separately approved quantitative specification and release
identity.

## 13. Non-Goals

EMA-01 does not define or include:

- a second EMA period;
- EMA crossovers or multi-EMA relationships;
- MACD;
- trend or momentum interpretation;
- buy, sell, ranking, opportunity, or trading signals;
- strategy logic;
- predictive claims;
- visualization;
- parameter optimization;
- alternate initialization methods;
- alternate smoothing formulas;
- missing-value imputation; or
- architecture changes.

No other feature family is approved or specified by this document.

## 14. Approval and Implementation Gate

This successor specification becomes authoritative only after explicit
approval under repository governance.

Before EMA-01 implementation begins:

- this document must be approved and frozen;
- the canonical recursive-origin evidence for each supported series must be
  frozen;
- aligned implementation and registry contracts must freeze the required
  engineering identities; and
- those contracts must reference and conform to the Feature Architecture
  Standard and this quantitative specification.

Approval of this document authorizes only the EMA-01 quantitative definition.
It does not itself authorize implementation or any other feature.
