# AlphaLens v2 Statistical Volatility Feature Family Specification

**Document type:** Feature-family quantitative specification

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

## 1. Purpose

This document defines only the approved mathematics and quantitative
identities of the AlphaLens v2 Statistical Volatility Feature Family.

The family contains SMA-20, Rolling Standard Deviation-20, Bollinger Middle,
Bollinger Upper, Bollinger Lower, Bollinger Band Width, and Percent B.

All engineering behavior is inherited from
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`. This document does not define
or modify numeric representation, source validation, availability,
missing-data handling, registry implementation, pipeline execution,
persistence, provenance, hashing, versioning architecture, or testing
infrastructure.

## 2. Canonical Mathematical Input

For one asset, quote currency, and timeframe, let the canonical chronological
Close sequence be:

\[
C_0,C_1,C_2,\ldots,C_t
\]

The common period is exactly:

\[
N=20
\]

For each eligible position \(t\geq19\), the complete trailing window is:

\[
W_t=(C_{t-19},C_{t-18},\ldots,C_t)
\]

The window is current-inclusive and contains exactly 20 consecutive canonical
Close observations. No feature in this family uses a centered, expanding,
partial, future-inclusive, or observation-skipping window.

## 3. Dependency Graph

The mathematical dependency graph is:

\[
\text{canonical Close}\rightarrow\text{SMA-20}
\]

\[
(\text{canonical Close},\text{SMA-20})
\rightarrow\text{Rolling Standard Deviation-20}
\]

\[
(\text{canonical Close},\text{SMA-20},
\text{Rolling Standard Deviation-20})
\rightarrow\text{Bollinger outputs}
\]

SMA-20 has no registered derived-feature dependency. Rolling Standard
Deviation-20 requires the contemporaneous registered SMA-20 output. Every
Bollinger output requires the contemporaneous registered SMA-20 and Rolling
Standard Deviation-20 outputs.

No downstream member may privately recalculate an upstream registered mean or
dispersion value.

## 4. SMA-20

### 4.1 Mathematical definition

For every \(t\geq19\), SMA-20 is:

\[
A_t=\frac{1}{20}\sum_{i=t-19}^{t}C_i
\]

### 4.2 Initialization

The first value is:

\[
A_{19}=\frac{1}{20}\sum_{i=0}^{19}C_i
\]

No SMA-20 value exists at positions 0 through 18. Each later value uses the
complete trailing 20-Close window ending at its own timestamp.

### 4.3 Output meaning

SMA-20 is the equal-weighted arithmetic mean price of the latest exactly 20
canonical Close observations. It uses the same quote-price units as Close.
It is not a return, direction, trend state, probability, or signal.

### 4.4 Edge cases

For a constant Close window, SMA-20 equals that constant exactly. Positive
canonical Close inputs imply a positive SMA-20 value.

### 4.5 Registry identity

- definition identifier: `simple_moving_average_20`;
- definition version: `1.0.0`; and
- output identifier: `simple_moving_average_20`.

## 5. Rolling Standard Deviation-20

### 5.1 Mathematical definition

Rolling Standard Deviation-20 uses the population variance of the same
current-inclusive 20-Close window. For every \(t\geq19\):

\[
V_t=\frac{1}{20}\sum_{i=t-19}^{t}(C_i-A_t)^2
\]

and:

\[
D_t=\sqrt{V_t}
\]

The divisor is exactly 20. No sample correction, degrees-of-freedom
adjustment, annualization, return transformation, weighting, robust scale,
or alternative estimator is permitted.

The value \(A_t\) is the exact contemporaneous registered SMA-20 dependency
value. Its canonical released value is the center used by this definition.

### 5.2 Initialization

The first standard-deviation value is \(D_{19}\), using canonical Close values
\(C_0\) through \(C_{19}\) and registered SMA-20 value \(A_{19}\).

No standard-deviation value exists before position 19. No partial-window
estimate is defined.

### 5.3 Output meaning

Rolling Standard Deviation-20 is the non-negative population dispersion of
the latest exactly 20 Close prices around their registered SMA-20 center. It
uses the same quote-price units as Close.

### 5.4 Edge cases

If all 20 Close values are equal, variance and standard deviation are exactly
zero. A zero value is valid and is not missing. Population variance cannot be
negative; a negative intermediate result is mathematically invalid.

### 5.5 Registry identity

- definition identifier: `rolling_standard_deviation_20`;
- definition version: `1.0.0`; and
- output identifier: `rolling_standard_deviation_20`.

## 6. Bollinger Parameters and Shared Bands

The Bollinger period is exactly 20 and the standard-deviation multiplier is
exactly:

\[
K=2
\]

For every \(t\geq19\), let the band distance be:

\[
B_t=2D_t
\]

All Bollinger outputs use the contemporaneous registered values \(A_t\) and
\(D_t\). No Bollinger output recalculates the rolling mean or standard
deviation.

All Bollinger outputs first become mathematically valid at position 19 after
exactly 20 canonical Close observations.

The Bollinger outputs are registered together under:

- definition identifier: `bollinger_bands_20_2`; and
- definition version: `1.0.0`.

## 7. Bollinger Middle

### 7.1 Mathematical definition

\[
M_t=A_t
\]

### 7.2 Output meaning

Bollinger Middle is the contemporaneous registered SMA-20 price baseline. It
is expressed in quote-price units.

### 7.3 Edge cases

Bollinger Middle remains defined when dispersion is zero. It equals the
positive SMA-20 dependency exactly.

### 7.4 Registry identity

- definition identifier: `bollinger_bands_20_2` version `1.0.0`; and
- output identifier: `bollinger_middle`.

## 8. Bollinger Upper

### 8.1 Mathematical definition

\[
U_t=A_t+2D_t
\]

### 8.2 Output meaning

Bollinger Upper is the SMA-20 center plus two Rolling Standard Deviation-20
values. It is expressed in quote-price units.

### 8.3 Edge cases

When \(D_t=0\), Bollinger Upper equals Bollinger Middle.

### 8.4 Registry identity

- definition identifier: `bollinger_bands_20_2` version `1.0.0`; and
- output identifier: `bollinger_upper`.

## 9. Bollinger Lower

### 9.1 Mathematical definition

\[
L_t=A_t-2D_t
\]

### 9.2 Output meaning

Bollinger Lower is the SMA-20 center minus two Rolling Standard Deviation-20
values. It is expressed in quote-price units.

### 9.3 Edge cases

When \(D_t=0\), Bollinger Lower equals Bollinger Middle. A mathematically
negative lower band is valid and is not clamped to zero.

### 9.4 Registry identity

- definition identifier: `bollinger_bands_20_2` version `1.0.0`; and
- output identifier: `bollinger_lower`.

## 10. Bollinger Band Width

### 10.1 Mathematical definition

For every eligible timestamp:

\[
W_t=\frac{U_t-L_t}{M_t}
\]

Equivalently:

\[
W_t=\frac{4D_t}{A_t}
\]

The denominator is the positive contemporaneous registered SMA-20 value.
Band Width is not multiplied by 100.

### 10.2 Output meaning

Bollinger Band Width is the non-negative dimensionless envelope width relative
to the band center. It is not annualized and does not define a squeeze,
expansion category, threshold, or trading condition.

### 10.3 Edge cases

When \(D_t=0\), Band Width is exactly zero. A zero or negative center is
outside the admitted mathematical domain because canonical Close values are
positive.

### 10.4 Registry identity

- definition identifier: `bollinger_bands_20_2` version `1.0.0`; and
- output identifier: `bollinger_band_width`.

## 11. Percent B

### 11.1 Mathematical definition

When \(U_t>L_t\):

\[
P_t=\frac{C_t-L_t}{U_t-L_t}
\]

Percent B is a unitless ratio and is not multiplied by 100.

### 11.2 Zero-width definition

When:

\[
U_t=L_t
\]

Percent B is defined exactly as:

\[
P_t=0.5
\]

This is the neutral center position for a mathematically eligible constant
window and avoids division by zero.

### 11.3 Output meaning

Percent B locates the current canonical Close relative to the contemporaneous
lower and upper bands. A value of 0 corresponds to the lower band, 0.5 to the
middle, and 1 to the upper band.

Percent B is not clipped. Values below 0 or above 1 are mathematically valid
when the current Close lies outside the bands. It is not a probability,
classification, or trading signal.

### 11.4 Registry identity

- definition identifier: `bollinger_bands_20_2` version `1.0.0`; and
- output identifier: `bollinger_percent_b`.

## 12. Deterministic Mathematical Behavior

For a fixed canonical Close sequence and fixed dependency values, this family
has exactly one valid mathematical output sequence.

Every conforming implementation must preserve these invariants:

1. Every window contains exactly the latest 20 consecutive Close values and
   includes the current Close.
2. SMA-20 is the arithmetic mean with equal weight on all 20 values.
3. Rolling variance is population variance with divisor 20.
4. Standard deviation is the non-negative square root of population variance.
5. The registered SMA-20 dependency is the center used by standard deviation
   and every Bollinger output.
6. The registered Rolling Standard Deviation-20 dependency is the dispersion
   used by every Bollinger output.
7. The Bollinger multiplier is exactly 2.
8. Band Width uses the positive middle band as denominator and is not scaled
   by 100.
9. Percent B uses current Close and is not clipped or scaled by 100.
10. Zero-width Percent B is exactly 0.5.
11. No output exists before the twentieth Close.
12. No later Close can change an earlier window or output.
13. No feature-specific intermediate rounding is applied beyond the canonical
    released dependency values inherited from the architecture.

## 13. Architecture Inheritance

The entire family inherits
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md` without exception. This
specification intentionally does not define a family-specific alternative for
numeric representation, warm-up representation, availability, missing-data
handling, registry implementation, pipeline behavior, persistence,
provenance, hashing, engineering versioning, validation, or testing.

## 14. Non-Goals

This specification does not define or authorize:

- another SMA or dispersion period;
- sample standard deviation;
- exponentially weighted or robust dispersion;
- alternate Bollinger multipliers;
- clipped Percent B;
- squeeze, expansion, crossover, or threshold events;
- band slopes, deltas, or forecasts;
- trend, volatility-regime, or trading interpretations;
- parameter optimization;
- implementation code;
- database migrations; or
- another feature family.
