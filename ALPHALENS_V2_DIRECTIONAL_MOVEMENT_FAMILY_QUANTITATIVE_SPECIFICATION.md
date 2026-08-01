# AlphaLens v2 Directional Movement Family Quantitative Specification

**Document type:** Feature-family quantitative specification

**Feature family:** Directional Movement

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

## 1. Purpose

This document defines only the approved mathematics and quantitative meaning
of the AlphaLens v2 Directional Movement family.

The family contains:

- Positive Directional Movement, \(+DM\);
- Negative Directional Movement, \(-DM\);
- Positive Directional Indicator, \(+DI\);
- Negative Directional Indicator, \(-DI\);
- Directional Index, \(DX\);
- Average Directional Index, \(ADX\); and
- Average Directional Movement Rating, \(ADXR\).

The family measures directional high/low movement and the strength of its
imbalance. It does not define trend direction from ADX or ADXR, predict future
movement, or produce a trading signal.

All engineering behavior is inherited from
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`. This document does not define
or modify numeric representation, source validation, availability,
missing-data handling, registry behavior, pipeline execution, persistence,
provenance, hashing, versioning architecture, or testing infrastructure.

## 2. Mathematical Inputs and Dependency

For one asset, quote currency, and timeframe, let the canonical chronological
candle sequence be indexed as:

\[
0,1,2,\ldots,t
\]

Let:

- \(H_t\) be the canonical High of candle \(t\);
- \(L_t\) be the canonical Low of candle \(t\); and
- \(TR_t\) be the exact contemporaneous registered True Range value.

The family requires canonical High and Low and registered True Range. It must
use the existing True Range definition rather than independently redefining
or recalculating gap-aware range.

The existing bounded arithmetic ATR is not a mathematical dependency of this
family. Directional Indicators require the Wilder-smoothed True Range state
defined in Section 6, which is quantitatively different from the approved
arithmetic ATR output.

## 3. Fixed Period

The Directional Movement period is exactly:

\[
N=14
\]

The period is fixed for every smoothed state, DI, DX, ADX, and ADXR operation
defined here. It is not configurable within this family. Changing the period
defines different mathematics.

## 4. One-Observation Directional Movement

For every position \(t\geq1\), define upward and downward high/low movement:

\[
U_t=H_t-H_{t-1}
\]

\[
D_t=L_{t-1}-L_t
\]

Positive Directional Movement is:

\[
+DM_t=
\begin{cases}
U_t, & \text{if }U_t>D_t\text{ and }U_t>0\\
0, & \text{otherwise}
\end{cases}
\]

Negative Directional Movement is:

\[
-DM_t=
\begin{cases}
D_t, & \text{if }D_t>U_t\text{ and }D_t>0\\
0, & \text{otherwise}
\end{cases}
\]

Both outputs are non-negative and use quote-price units.

No directional movement value exists at position 0 because there is no
preceding High or Low.

## 5. Directional Tie and Comparison Rules

The comparisons in Section 4 are strict.

If upward and downward movement are equal, including an equal positive
outside-bar movement:

\[
U_t=D_t
\]

then:

\[
+DM_t=0
\]

and:

\[
-DM_t=0
\]

If both \(U_t\) and \(D_t\) are non-positive, both directional movements are
zero. No equality is resolved in favor of either direction.

## 6. Wilder-Smoothed Directional and True Range States

Define three internal Wilder-smoothed sums:

- \(S^+_t\), the smoothed positive directional movement sum;
- \(S^-_t\), the smoothed negative directional movement sum; and
- \(S^{TR}_t\), the smoothed True Range sum.

### 6.1 Initialization

The first states are initialized at position 14 from the first exactly 14
eligible observations, positions 1 through 14:

\[
S^+_{14}=\sum_{i=1}^{14}\left(+DM_i\right)
\]

\[
S^-_{14}=\sum_{i=1}^{14}\left(-DM_i\right)
\]

\[
S^{TR}_{14}=\sum_{i=1}^{14}TR_i
\]

The seed therefore requires exactly 15 consecutive candles, positions 0
through 14. Initialization occurs once at the canonical sequence origin.

### 6.2 Recursive smoothing

For every position \(t\geq15\):

\[
S^+_t=S^+_{t-1}-\frac{S^+_{t-1}}{14}+\left(+DM_t\right)
\]

\[
S^-_t=S^-_{t-1}-\frac{S^-_{t-1}}{14}+\left(-DM_t\right)
\]

\[
S^{TR}_t=S^{TR}_{t-1}-\frac{S^{TR}_{t-1}}{14}+TR_t
\]

These are Wilder smoothed sums. They are equivalent to carrying a prior
weight of \(13/14\) and adding the complete current observation. They are not
simple rolling sums, rolling arithmetic means, EMA span smoothing, or the
existing arithmetic ATR.

The three smoothed states are internal mathematical state. They are not
additional quantitative outputs authorized by this specification.

## 7. Positive and Negative Directional Indicators

When \(S^{TR}_t>0\), Positive Directional Indicator is:

\[
+DI_t=100\times\frac{S^+_t}{S^{TR}_t}
\]

and Negative Directional Indicator is:

\[
-DI_t=100\times\frac{S^-_t}{S^{TR}_t}
\]

When:

\[
S^{TR}_t=0
\]

both indicators are defined exactly as zero:

\[
+DI_t=0
\]

\[
-DI_t=0
\]

The first valid \(+DI\) and \(-DI\) values occur at position 14 after exactly
15 consecutive candles.

Both outputs are dimensionless values scaled by 100. They measure the
relative magnitude of smoothed directional movement; they are not
probabilities or trading directions.

## 8. Directional Index

Let:

\[
Z_t=\left(+DI_t\right)+\left(-DI_t\right)
\]

When \(Z_t>0\), Directional Index is:

\[
DX_t=100\times
\frac{\left|\left(+DI_t\right)-\left(-DI_t\right)\right|}
{\left(+DI_t\right)+\left(-DI_t\right)}
\]

When:

\[
Z_t=0
\]

Directional Index is defined exactly as:

\[
DX_t=0
\]

The first valid \(DX\) occurs at position 14 after exactly 15 consecutive
candles.

DX is dimensionless and lies on the closed interval \([0,100]\). It measures
the magnitude of contemporaneous directional imbalance without identifying
which direction dominates.

## 9. Average Directional Index

ADX uses Wilder smoothing of the valid DX sequence with period 14.

### 9.1 Initialization

The first 14 valid DX values are:

\[
DX_{14},DX_{15},\ldots,DX_{27}
\]

The first ADX is their arithmetic mean:

\[
ADX_{27}=\frac{1}{14}\sum_{i=14}^{27}DX_i
\]

The first valid ADX occurs at position 27 after exactly 28 consecutive
candles.

### 9.2 Recursive smoothing

For every position \(t\geq28\):

\[
ADX_t=\frac{13\times ADX_{t-1}+DX_t}{14}
\]

ADX is initialized once and is never reset or reseeded.

ADX is dimensionless and lies on the closed interval \([0,100]\). It measures
smoothed directional-strength magnitude. ADX alone does not identify bullish
or bearish direction and does not define weak, strong, trending, or ranging
thresholds.

## 10. Average Directional Movement Rating

ADXR uses an exact 14-observation lag of the valid ADX sequence.

For every position \(t\geq41\):

\[
ADXR_t=\frac{ADX_t+ADX_{t-14}}{2}
\]

The first ADXR uses:

\[
ADX_{41}\text{ and }ADX_{27}
\]

and therefore first becomes valid at position 41 after exactly 42
consecutive candles.

ADXR is dimensionless and lies on the closed interval \([0,100]\). It is the
equal-weighted average of current ADX and ADX from exactly 14 observations
earlier. It is not a separate directional signal, forecast, or regime label.

## 11. First Valid Observations and Warm-Up Mathematics

The exact mathematical boundaries are:

| Output | First valid position | Required consecutive candles | Initialization basis |
| --- | ---: | ---: | --- |
| \(+DM\) | 1 | 2 | Current and preceding High |
| \(-DM\) | 1 | 2 | Current and preceding Low |
| \(+DI\) | 14 | 15 | First 14 \(+DM\) values and True Range values |
| \(-DI\) | 14 | 15 | First 14 \(-DM\) values and True Range values |
| \(DX\) | 14 | 15 | First valid contemporaneous DI pair |
| \(ADX\) | 27 | 28 | Arithmetic mean of first 14 DX values |
| \(ADXR\) | 41 | 42 | Current ADX and ADX lagged exactly 14 observations |

For a valid canonical sequence containing \(m\) candles, the number of
mathematically defined values is:

| Output | Defined-value count |
| --- | ---: |
| \(+DM\), \(-DM\) | \(\max(0,m-1)\) |
| \(+DI\), \(-DI\), \(DX\) | \(\max(0,m-14)\) |
| \(ADX\) | \(\max(0,m-27)\) |
| \(ADXR\) | \(\max(0,m-41)\) |

How undefined warm-up positions are represented is inherited exclusively
from the Feature Architecture Standard.

## 12. Edge Cases

### 12.1 Inside bar

If the current High does not exceed the preceding High and the current Low
does not fall below the preceding Low, both directional movements are zero.

### 12.2 Outside bar

If both upward and downward movement are positive, only the strictly larger
movement is retained. If they are equal, both are zero.

### 12.3 Unchanged High or Low

Zero movement on one side cannot win the strict positive comparison. The
corresponding directional movement is zero.

### 12.4 Price gap

Directional Movement remains defined only from consecutive High and Low
changes. Gap-aware magnitude enters the denominator through registered True
Range. No alternate gap adjustment is applied to \(+DM\) or \(-DM\).

### 12.5 Completely flat eligible history

If all eligible directional movements and True Range values are zero, both DI
values, DX, the eventual ADX, and the eventual ADXR are exactly zero at their
respective valid boundaries.

### 12.6 One-sided movement

If one smoothed directional state is positive and the other is zero while
smoothed True Range is positive, the corresponding DX is exactly 100.

### 12.7 Invalid negative state

Raw directional movement, smoothed directional movement, smoothed True Range,
DX, ADX, and ADXR cannot be negative under the approved mathematics. A
negative state is mathematically invalid and must not be clamped or
absolutized to conceal an error.

### 12.8 Invalid or unavailable evidence

This family defines no imputation, interpolation, skipping, fallback,
partial seed, reset, or reseed mathematics. Shared handling of invalid,
missing, discontinuous, or unavailable evidence is inherited from the
Feature Architecture Standard.

## 13. Output Meanings and Domains

| Output | Units/domain | Quantitative meaning |
| --- | --- | --- |
| \(+DM\) | Non-negative quote-price units | Retained strictly dominant upward High movement |
| \(-DM\) | Non-negative quote-price units | Retained strictly dominant downward Low movement |
| \(+DI\) | Dimensionless, scaled by 100 | Smoothed positive movement relative to smoothed True Range |
| \(-DI\) | Dimensionless, scaled by 100 | Smoothed negative movement relative to smoothed True Range |
| \(DX\) | Dimensionless \([0,100]\) | Absolute contemporaneous DI imbalance |
| \(ADX\) | Dimensionless \([0,100]\) | Wilder-smoothed directional-strength magnitude |
| \(ADXR\) | Dimensionless \([0,100]\) | Mean of current and 14-observation-lagged ADX |

None of these outputs is a probability, expected return, trend-state label,
market-context classification, confidence value, or buy/sell decision.

## 14. Deterministic Mathematical Behavior

For a fixed canonical High/Low sequence, fixed registered True Range sequence,
and fixed canonical origin, this family has exactly one valid mathematical
result sequence.

Every conforming implementation must preserve these invariants:

1. The period is exactly 14.
2. Directional movement compares only consecutive High and Low values.
3. Strictly larger positive movement wins; ties produce two zero movements.
4. The initial smoothed states sum exactly observations 1 through 14.
5. Every later directional and True Range state uses the approved Wilder
   recurrence.
6. DI zero-range handling is exactly zero for both outputs.
7. DX zero-denominator handling is exactly zero.
8. The ADX seed is the arithmetic mean of exactly \(DX_{14}\) through
   \(DX_{27}\).
9. Every later ADX uses the immediately preceding ADX and current DX.
10. ADXR uses the exact lag \(t-14\), not \(t-13\), \(t-15\), or a rolling
    ADX mean.
11. Initialization occurs once; no state is reset or silently reseeded.
12. No future High, Low, True Range, DI, DX, or ADX value changes an earlier
    result.
13. No feature-specific intermediate rounding changes the recursive path.

## 15. Architecture Inheritance

The complete Directional Movement family inherits
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md` without exception. This
specification intentionally does not define a family-specific alternative for
Decimal representation, warm-up representation, availability, missing-data
handling, registry behavior, pipeline execution, persistence, provenance,
hashing, versioning, deterministic validation, point-in-time validation,
prefix-invariance validation, future-isolation validation, or testing.

## 16. Non-Goals

This specification does not define or authorize:

- another Directional Movement period;
- use of arithmetic ATR as the DI denominator;
- alternate EMA, rolling, or library-default smoothing;
- ADX or ADXR trend thresholds;
- bullish, bearish, strong, weak, range, or regime classifications;
- crossover events;
- trading signals or strategy logic;
- parameter optimization;
- implementation code;
- registry or pipeline changes;
- database migrations; or
- another feature family.
