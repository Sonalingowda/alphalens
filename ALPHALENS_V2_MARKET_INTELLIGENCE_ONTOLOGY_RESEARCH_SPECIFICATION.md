# AlphaLens v2 Market Intelligence Ontology Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; not approved production policy

## 1. Scope

This specification defines a mathematical vocabulary for describing market
state from point-in-time AlphaLens evidence. It SHALL NOT define a decision,
candidate, score, confidence value, threshold, or production classification.
It inherits engineering representation from the frozen Market Context Contract
and Feature Architecture Standard.

## 2. Index Set and Symbols

Let (s\in\mathcal S) denote a canonical instrument, (\tau\in\mathcal T) a
timeframe, and (t) the close time of a completed candle. Let
(\mathcal I_{s,\tau,t}) be the information set whose members were available no
later than cutoff (t). Let (W=(w_1,\ldots,w_k)) be an ordered collection of
backward-looking observation windows, each ending at (t). Let (H) denote an
ordered set of approved higher or lower context timeframes.

The market-intelligence state is the typed product

\[
X_{s,\tau,t}^{W,H}=(T,M,V,S,C,L^*,Q,\Omega,\Gamma),
\]

where (T) is trend, (M) momentum, (V) volatility, (S) structure,
(C) session state, (L^*) a liquidity-assumption record, (Q) data quality,
(\Omega) observation-window metadata, and (\Gamma) temporal context.

## 3. State Components

### 3.1 Trend

Trend is an ordered collection of factual, registered observables, not a
directional recommendation:

\[
T=(P_t-E_{p,t},\;E_{p_i,t}-E_{p_j,t},\;\Delta_h E_{p,t},\;
D^+_{p,t},D^-_{p,t},A_{p,t}),
\]

where (P_t) is canonical close, (E_{p,t}) is registered EMA with period
(p), (\Delta_h) is a backward difference over an explicitly declared lag,
(D^+,D^-) are directional indicators, and (A) is ADX. Any categorical trend
mapping is a function (g_T(T;\theta_T)) whose parameters and predicates require
future calibration and approval. The ontology assigns no sign, strength, or
threshold interpretation.

### 3.2 Momentum

Momentum is the typed vector

\[
M=(R_{p,t},\;D^{MACD}_t,\;G^{MACD}_t,\;\Delta_h P_t,\;\Delta_h R_{p,t}),
\]

where (R) is registered RSI, (D^{MACD}) is the MACD line, and (G^{MACD})
is its histogram. A future map (g_M(M;\theta_M)) MAY describe directional or
recovery states only after its estimand, lags, domains, and parameters are
approved. Momentum observations SHALL NOT be interpreted as future movement.

### 3.3 Volatility

Volatility is represented by absolute, relative, and distributional
observables:

\[
V=(ATR_{p,t},\;ATR_{p,t}/P_t,\;\sigma_{p,t},\;BW_{p,t},\;%B_{p,t},
\Delta_h ATR_{p,t},\Delta_h BW_{p,t}).
\]

Ratios require a nonzero valid denominator. Expansion, compression, high, and
low are relational states (g_V(V;\theta_V)), not intrinsic labels; their
reference population and parameters remain calibration variables.

### 3.4 Market Structure

Let (H_t,L_t) be completed-candle high and low. A candidate extremum at index
(i) is defined by an approved causal confirmation operator
(\mathcal C_{\theta_S}(i,t)) satisfying (i\le t). A confirmed swing high or
low SHALL exist only when all observations required by that operator are in
(\mathcal I_{s,\tau,t}). A confirmation time later than (i) SHALL be retained;
the event SHALL NOT be backdated as available at (i).

For consecutive confirmed swing highs (h_{k-1},h_k) and lows
(\ell_{k-1},\ell_k), higher/lower relations are ordinary order relations on
their prices. Equality and minimum separation rules are unresolved parameters.
BOS and CHOCH require a separately approved state ontology specifying prior
state, break price, close-versus-intrabar semantics, tolerance, and confirmation.
Until then, these fields remain `UNAVAILABLE` rather than inferred.

### 3.5 Session State

Session state SHALL use UTC and MAY include continuous cyclic coordinates

\[
c_d(t)=\cos(2\pi u_t/D),\qquad s_d(t)=\sin(2\pi u_t/D),
\]

where (u_t) is elapsed UTC time within a declared cycle of duration (D).
Named sessions require an approved boundary set (B_C), holiday/calendar
source, venue applicability, and daylight-saving treatment. Equity-session
semantics SHALL NOT be presumed for continuous crypto markets.

### 3.6 Liquidity Assumptions

The current OHLCV data contract does not observe spread, depth, impact,
resiliency, or executable volume. Therefore (L^*) is an assumption/proxy
record, never a liquidity measurement. Candle volume and range-derived
quantities MAY be stored as contextual proxies with explicit limitations, but
no `LIQUID`, `ILLIQUID`, slippage, capacity, or execution-quality conclusion is
mathematically authorized without trade, quote, or order-book contracts.

### 3.7 Data Quality

Let (Q=(q_c,q_f,q_v,q_o,q_a,q_p)) represent completeness, freshness,
validation, ordering/continuity, availability, and provenance integrity. Each
coordinate has a declared domain and source validation artifact. (Q) is not a
weighted quality score. Failure of any policy-mandatory coordinate makes the
consuming mathematical operation undefined.

### 3.8 Observation Window and Temporal Context

(\Omega) records window length, start/end, included observation identities,
warm-up status, gaps, and source availability. (\Gamma) records primary and
context timeframes, their completed boundaries, shared sources, and relative
availability. A context timeframe contributes only through its most recent
completed observation available by (t). Forward filling and retrospective
alignment are prohibited unless a future approved definition explicitly
specifies a causal operation.

## 4. Relationships and Dependency Graph

The ontology dependency order is

\[
OHLCV\rightarrow Registered\ Features\rightarrow(T,M,V)
\rightarrow S,C,L^*,Q\rightarrow X.
\]

No component depends on a candidate, decision, score, rank, explanation, or
lifecycle state. Multi-timeframe observations are siblings joined at a common
cutoff, not recursive summaries of a future primary-timeframe state.

## 5. Assumptions

- `MI-A01`: completed-candle OHLCV and feature provenance are valid.
- `MI-A02`: all time coordinates use canonical UTC.
- `MI-A03`: registered indicators retain their frozen mathematical meanings.
- `MI-A04`: context mappings are population- and timeframe-specific unless
  transferability is empirically established.
- `MI-A05`: candle volume is not executable liquidity.
- `MI-A06`: structure confirmation may introduce delay and SHALL preserve it.

These assumptions are registered in the Quantitative Assumptions Register.

## 6. Validation and Future Calibration

Research SHALL validate domain definitions, unit compatibility, chronology,
window membership, missingness, causal confirmation, stability across folds,
and sensitivity to (W,H,\theta_T,\theta_M,\theta_V,\theta_S,B_C). Categorical
maps require preregistered estimands and walk-forward evaluation. No category
or parameter becomes production policy through this specification.
