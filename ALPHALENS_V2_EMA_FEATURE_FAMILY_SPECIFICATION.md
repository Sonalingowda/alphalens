# AlphaLens v2 EMA Feature Family Specification

**Document type:** Feature-family quantitative specification

**Feature family:** Exponential Moving Average

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

## 1. Purpose

This document defines only the approved mathematics and quantitative
identities of the AlphaLens v2 EMA feature family.

The family contains exactly six fixed-period exponentially weighted averages
of canonical Close: EMA-12, EMA-20, EMA-26, EMA-50, EMA-100, and EMA-200.
EMA-20 is the existing EMA-01 mathematical definition and retains its released
registry identity and behavior unchanged.

All engineering architecture is inherited from
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`. This document does not define
or modify numeric representation, source validation, warm-up representation,
availability, missing-data handling, registry implementation, pipeline
execution, persistence, provenance, hashing, versioning architecture, or
testing infrastructure.

## 2. Shared Mathematical Definition

For one asset, quote currency, and timeframe, let the canonical chronological
Close sequence be:

\[
C_0,C_1,C_2,\ldots,C_t
\]

For a family member with fixed period \(N\), the smoothing constant is:

\[
\alpha_N=\frac{2}{N+1}
\]

The member is initialized from the arithmetic mean of the first exactly
\(N\) canonical Close observations:

\[
E^{(N)}_{N-1}=\frac{1}{N}\sum_{i=0}^{N-1}C_i
\]

For every sequence position \(t\geq N\), the recursive update is:

\[
E^{(N)}_t=\alpha_N C_t+(1-\alpha_N)E^{(N)}_{t-1}
\]

No mathematical value exists before sequence position \(N-1\). The first
valid value is associated with the \(N\)-th canonical Close observation.

Every family member is initialized exactly once from the same canonical
source origin. No member may use a partial seed, alternate seed, library
default, reset, or later reseed.

## 3. Shared Dependency and Output Meaning

Each EMA family member has canonical Close as its sole mathematical input.
Close is a canonical OHLCV source field under the Feature Architecture
Standard.

No EMA family member has an upstream registered derived-feature dependency.
The immediately preceding value of the same member is recursive mathematical
state and value lineage, not a registry self-dependency.

Each output is a price-level exponentially weighted average expressed in the
same quote-price units as canonical Close. It is not a return, ratio,
percentage, slope, crossover, direction, probability, score, or trading
signal.

## 4. EMA-12

| Property | Quantitative definition |
| --- | --- |
| Catalog identifier | `EMA-12` |
| Period | `12` consecutive canonical Close observations |
| Dependency | Canonical Close only; no derived-feature dependency |
| Initialization | Arithmetic mean of exactly \(C_0\) through \(C_{11}\) |
| First valid position | \(t=11\), after exactly 12 Close observations |
| Smoothing constant | \(2/13\) |
| Recursive definition | \(E^{(12)}_t=(2/13)C_t+(11/13)E^{(12)}_{t-1}\) for \(t\geq12\) |
| Output meaning | 12-observation exponentially weighted canonical Close price baseline |
| Registry identity | Definition `exponential_moving_average_12`, version `1.0.0`; output `exponential_moving_average_12` |

## 5. EMA-20

| Property | Quantitative definition |
| --- | --- |
| Catalog identifier | `EMA-20`, retaining the existing EMA-01 definition |
| Period | `20` consecutive canonical Close observations |
| Dependency | Canonical Close only; no derived-feature dependency |
| Initialization | Arithmetic mean of exactly \(C_0\) through \(C_{19}\) |
| First valid position | \(t=19\), after exactly 20 Close observations |
| Smoothing constant | \(2/21\) |
| Recursive definition | \(E^{(20)}_t=(2/21)C_t+(19/21)E^{(20)}_{t-1}\) for \(t\geq20\) |
| Output meaning | 20-observation exponentially weighted canonical Close price baseline |
| Registry identity | Existing definition `exponential_moving_average`, version `1.0.0`; existing output `exponential_moving_average` |

EMA-20 preserves the complete mathematics and identity approved in
`ALPHALENS_V2_EMA01_SUCCESSOR_QUANTITATIVE_SPECIFICATION.md`. This family
specification does not rename, replace, or change it.

## 6. EMA-26

| Property | Quantitative definition |
| --- | --- |
| Catalog identifier | `EMA-26` |
| Period | `26` consecutive canonical Close observations |
| Dependency | Canonical Close only; no derived-feature dependency |
| Initialization | Arithmetic mean of exactly \(C_0\) through \(C_{25}\) |
| First valid position | \(t=25\), after exactly 26 Close observations |
| Smoothing constant | \(2/27\) |
| Recursive definition | \(E^{(26)}_t=(2/27)C_t+(25/27)E^{(26)}_{t-1}\) for \(t\geq26\) |
| Output meaning | 26-observation exponentially weighted canonical Close price baseline |
| Registry identity | Definition `exponential_moving_average_26`, version `1.0.0`; output `exponential_moving_average_26` |

## 7. EMA-50

| Property | Quantitative definition |
| --- | --- |
| Catalog identifier | `EMA-50` |
| Period | `50` consecutive canonical Close observations |
| Dependency | Canonical Close only; no derived-feature dependency |
| Initialization | Arithmetic mean of exactly \(C_0\) through \(C_{49}\) |
| First valid position | \(t=49\), after exactly 50 Close observations |
| Smoothing constant | \(2/51\) |
| Recursive definition | \(E^{(50)}_t=(2/51)C_t+(49/51)E^{(50)}_{t-1}\) for \(t\geq50\) |
| Output meaning | 50-observation exponentially weighted canonical Close price baseline |
| Registry identity | Definition `exponential_moving_average_50`, version `1.0.0`; output `exponential_moving_average_50` |

## 8. EMA-100

| Property | Quantitative definition |
| --- | --- |
| Catalog identifier | `EMA-100` |
| Period | `100` consecutive canonical Close observations |
| Dependency | Canonical Close only; no derived-feature dependency |
| Initialization | Arithmetic mean of exactly \(C_0\) through \(C_{99}\) |
| First valid position | \(t=99\), after exactly 100 Close observations |
| Smoothing constant | \(2/101\) |
| Recursive definition | \(E^{(100)}_t=(2/101)C_t+(99/101)E^{(100)}_{t-1}\) for \(t\geq100\) |
| Output meaning | 100-observation exponentially weighted canonical Close price baseline |
| Registry identity | Definition `exponential_moving_average_100`, version `1.0.0`; output `exponential_moving_average_100` |

## 9. EMA-200

| Property | Quantitative definition |
| --- | --- |
| Catalog identifier | `EMA-200` |
| Period | `200` consecutive canonical Close observations |
| Dependency | Canonical Close only; no derived-feature dependency |
| Initialization | Arithmetic mean of exactly \(C_0\) through \(C_{199}\) |
| First valid position | \(t=199\), after exactly 200 Close observations |
| Smoothing constant | \(2/201\) |
| Recursive definition | \(E^{(200)}_t=(2/201)C_t+(199/201)E^{(200)}_{t-1}\) for \(t\geq200\) |
| Output meaning | 200-observation exponentially weighted canonical Close price baseline |
| Registry identity | Definition `exponential_moving_average_200`, version `1.0.0`; output `exponential_moving_average_200` |

## 10. Deterministic Mathematical Behavior

For a fixed canonical Close sequence and fixed canonical origin, each family
member has exactly one valid mathematical result sequence.

Every member must preserve these deterministic mathematical invariants:

1. Its period is the exact fixed period assigned in this document.
2. Its seed contains exactly the first \(N\) canonical Close observations.
3. Its seed is their arithmetic mean.
4. Its first value is associated with sequence position \(N-1\).
5. Every later value uses exactly the current Close and immediately preceding
   same-member EMA state.
6. Its smoothing constant is exactly \(2/(N+1)\).
7. It is initialized once and is never silently reset or reseeded.
8. It uses no future Close or future EMA value.
9. It applies no feature-specific intermediate rounding.
10. It is independent of every other EMA family member; absence of a longer-
    period value does not prevent a shorter-period member from being
    mathematically defined.

Shared engineering mechanisms for Decimal arithmetic, deterministic
execution, point-in-time correctness, prefix invariance, and future isolation
are inherited from the Feature Architecture Standard and are not redefined
here.

## 11. Family Identity Invariants

The registry identity pairs in this document are quantitatively significant
and immutable after release. In particular:

- EMA-20 retains `exponential_moving_average` version `1.0.0`;
- no new family member aliases or replaces EMA-20;
- each added period has a distinct definition and output identity;
- a value from one period cannot satisfy a dependency on another period; and
- changing a period, seed, recurrence, output meaning, or identity defines a
  different feature.

## 12. Architecture Inheritance

The complete EMA family inherits
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md` without exception. This
document intentionally does not define an EMA-family alternative for:

- numeric representation or quantization;
- availability or warm-up representation;
- missing-data or source-validation policy;
- registry implementation or ordering mechanics;
- pipeline orchestration;
- persistence;
- provenance;
- hashing;
- engineering versioning;
- validation infrastructure; or
- testing requirements.

## 13. Non-Goals

This specification does not define or authorize:

- any EMA period other than 12, 20, 26, 50, 100, and 200;
- EMA slopes, distances, spreads, ribbons, or crossovers;
- MACD calculations;
- trend interpretation;
- trading signals or strategy logic;
- parameter optimization;
- visualization;
- implementation code;
- persistence changes;
- database migrations; or
- registry implementation changes.
