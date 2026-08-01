# AlphaLens v2 Opportunity Plan Mathematics Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; no plan policy is approved

## 1. Scope

This specification defines mathematical interfaces for an optional,
informational Opportunity Plan attached to a valid `BUY` or `SELL` assessment.
It is not an order, execution instruction, position-sizing rule, prediction, or
guarantee. A plan is absent for `WAIT` or when any required quantity is
undefined.

## 2. Symbols

Let direction (d=+1) for `BUY` and (d=-1) for `SELL`. Let (p_0) be a
policy-selected reference price, (Z_E=[e_L,e_U]) an inclusive entry region,
(i) an invalidation level, and (T=(t_1,\ldots,t_m)) an ordered nonempty
target set. All values are exact Decimal prices with point-in-time sources.

An approved policy must choose a representative entry reference
(e=\psi_E(Z_E,p_0;\Theta_P)) when scalar distance is required. No choice of
lower bound, upper bound, midpoint, close, or other reference is implied.

## 3. Structural Geometry

The entry region requires (e_L\le e_U). Directional validity requires

\[
d(e_L-i)>0\ \text{and}\ d(e_U-i)>0,
\]

and every target requires

\[
d(t_j-e_L)>0\ \text{and}\ d(t_j-e_U)>0.
\]

These conditions validate relative geometry only. They do not choose any
level, buffer, window, or target count.

## 4. Movement, Risk, Reward, and Ratio

Directional scenario movement to target (j) is

\[
M_j=d(t_j-e).
\]

It is a geometric displacement, not an expected value. “Expected movement” is
mathematically authorized only if a future study defines a random variable
(Y\), horizon (h), conditioning information (\mathcal I_t), estimator, and
validated conditional estimand such as (\mathbb E[Y_{t,h}\mid\mathcal I_t]).
Until then, the canonical term SHALL be *scenario movement*.

Given policy-selected (e), price-distance risk and potential reward are

\[
R=d(e-i)>0,\qquad G_j=d(t_j-e)>0,
\]

with dimensionless ratio

\[
\operatorname{RR}_j=G_j/R.
\]

These quantities exclude transaction costs, slippage, fill probability,
partial execution, financing, gap risk, and position size. They SHALL be
labelled geometric potential risk/reward unless future data contracts and
research authorize broader semantics.

## 5. Construction Interfaces

A future plan policy is the tuple

\[
\pi_P=(\psi_0,\psi_E,\psi_I,\psi_T,\psi_h,\Theta_P),
\]

where the functions choose the reference, entry region, invalidation, targets,
validity horizon, and parameters from immutable evidence. Each function must be
causal, deterministic, scope-bound, and versioned. No ATR multiple, support/
resistance rule, percentile, fixed percentage, or round-number rule is selected.

## 6. Assumptions and Limitations

- `PL-A01`: the chosen reference-price semantics match the distance equations.
- `PL-A02`: directional geometry is meaningful for the declared instrument and
  price convention.
- `PL-A03`: candle prices do not establish executable fills.
- `PL-A04`: path-dependent outcomes cannot be inferred from terminal levels.
- `PL-A05`: risk/reward geometry does not estimate probability or expectancy.

The research design SHALL account for intrabar ordering ambiguity whenever both
invalidation and target lie within the same aggregate candle. Such observations
require an approved conservative, exclusion, or higher-resolution rule.

## 7. Dependencies

Plan research depends on a valid stance, immutable market/evidence snapshots,
volatility and structure definitions where used, instrument price conventions,
and a future label/outcome horizon. It SHALL NOT depend on assumed user entry,
portfolio state, or trade execution.

## 8. Validation and Future Calibration

Phase 5B SHALL preregister candidate construction functions, horizon, event
ordering, cost scope, censoring, missingness, target count/order, and evaluation
estimands. Required diagnostics include coverage, invalid geometry, sensitivity,
path ambiguity, regime/timeframe stability, and walk-forward outcome analysis.
All references SHALL include the frozen Opportunity Plan Contract, Decision
Contract, Research Protocol, and any separately approved label specification.
External methods MAY be adopted only through a preregistered research review;
this specification endorses none.
