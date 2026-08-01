# AlphaLens v2 Phase 2 Final Completion Report

**Report date:** 2026-08-01

**Decision:** Phase 2 is **NOT COMPLETE**

## 1. Dependency-Aware Audit Result

The audit reviewed the Core Intelligence Specification, Phase 2 Feature
Catalog, Feature Architecture Standard, all quantitative and family
specifications, Feature Registry, intraday pipeline, persistence/provenance
path, current implementations, architecture audits, and
`ALPHALENS_V2_FEATURE_LIBRARY_COMPLETION_REPORT.md`.

The active library contains 19 registered definitions and 30 fully implemented
outputs. Every standalone approved quantitative specification maps to an
existing implementation. No additional approved quantitative specification,
registry identity, ontology, or implementation contract exists for a
remaining catalog candidate.

The Phase 2 Feature Catalog is explicitly a non-authorizing candidate catalog:
it states that no catalog candidate is approved and prohibits implementation
until a later approval selects exact outputs and resolves every quantitative
gate. Familiar indicator conventions and illustrative catalog formulas cannot
be treated as approval.

The dependency-aware set of remaining features that is both required and
fully implementable under existing approvals is therefore empty.

## 2. Newly Implemented Feature Families

**None.**

No feature code, shared primitive, registry entry, pipeline version,
persistence behavior, provenance behavior, hashing behavior, migration, or
test expectation was changed. This satisfies the requirement not to invent
quantitative definitions or weaken governance.

## 3. Existing Completed Phase 2 Foundation

The following remain complete and frozen:

- Candle Geometry and True Range;
- ATR-01;
- EMA-12, EMA-20, EMA-26, EMA-50, EMA-100, and EMA-200;
- RSI-01;
- MACD line, signal, and histogram;
- SMA-20 and Rolling Population Standard Deviation-20;
- Bollinger middle, upper, lower, width, and percent-B; and
- positive/negative DM, positive/negative DI, DX, ADX, and ADXR.

## 4. Every Skipped Phase 2 Feature and Exact Blocker

Blocker classes in this report are exactly:

- **Missing quantitative specification** — mathematics or quantitative
  identity is not completely approved;
- **Missing ontology** — a non-repainting structural/session event vocabulary
  and lifecycle is not approved;
- **Missing trade-data contract** — required transaction evidence is absent;
  and
- **Intentional future work** — the item is deliberately deferred for
  deduplication, an external quote/book/cross-timeframe contract, or the future
  Market Context boundary.

### 4.1 Return and Price Transforms

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `RET-01` Lagged log-return family | Missing quantitative specification | Lag vector and deterministic Decimal logarithm algorithm/version are not approved. |
| `RET-02` Lagged arithmetic rate of change | Missing quantitative specification | Lag set, denominator/zero rule and semantic choice versus log return are not approved. |
| `RET-03` Prior-close displacement fraction | Missing quantitative specification | The catalog formula is illustrative; candidate selection, identity, version and fixtures are not approved. |
| `RET-04` Representative candle price | Missing quantitative specification | Typical price versus OHLC mean or another proxy is unresolved. |
| `RET-05` Open-to-prior-close gap fraction | Missing quantitative specification | Candidate selection, immutable identity/version and quantitative fixtures are not approved. |

### 4.2 Price Action

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `PA-01` Close location value | Missing quantitative specification | Normalization and zero-range behavior are unresolved. |
| `PA-02` Wick imbalance | Intentional future work | It is algebraically derived from registered wick fractions and deferred until a distinct semantic owner is justified. |
| `PA-03` Inside/outside bar state | Missing quantitative specification | Equality rules and categorical versus separate Decimal outputs are unresolved. |
| `PA-04` Directional candle streak | Missing quantitative specification | Doji/reset rule, cap, recursive seed and first-valid boundary are unresolved. |
| `PA-05` Body-to-range ratio | Intentional future work | It duplicates registered candle geometry and has no approved incremental hypothesis. |

### 4.3 Trend

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `TRD-01` SMA distance | Missing quantitative specification | Registered SMA-20 exists, but candidate period/semantic owner and normalization scale are unresolved. |
| `TRD-02` SMA slope | Missing quantitative specification | SMA dependency, lag, endpoint convention and normalization are unresolved. |
| `TRD-03` Rolling linear-regression slope | Missing quantitative specification | Window, deterministic OLS estimator, time scaling, normalization and optional fit output are unresolved. |
| `TRD-04` Trend efficiency ratio | Missing quantitative specification | Window, signed/unsigned choice and zero-path rule are unresolved. |
| `TRD-05` Directional persistence fraction | Missing quantitative specification | Return-sign dependency, window, zero-return treatment and output selection are unresolved. |

### 4.4 EMA Extensions

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `EMA-01` EMA baseline and distance | Missing quantitative specification | EMA levels are complete, but the catalog’s additional distance output lacks a selected dependency and normalization. |
| `EMA-02` EMA slope | Missing quantitative specification | EMA member, lag and difference/rate normalization are unresolved. |
| `EMA-03` Fast/slow EMA spread | Intentional future work | With approved 12/26 periods it duplicates the registered MACD line. |
| `EMA-04` EMA ribbon dispersion | Missing quantitative specification | EMA member set and dispersion/order formula are unresolved. |

### 4.5 Momentum

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `MOM-01` Return acceleration | Missing quantitative specification | Return representation, lag and normalization are unresolved. |
| `MOM-02` Stochastic close position | Missing quantitative specification | Window, zero-range rule and semantic owner versus `STR-01` are unresolved. |
| `MOM-03` Momentum persistence | Missing quantitative specification | Return dependency, window and zero-return behavior are unresolved. |
| `MOM-04` Price acceleration | Missing quantitative specification | Historical endpoints or slope components, windows, lags and normalization are unresolved. |

### 4.6 RSI Extensions

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `RSI-02` RSI delta | Missing quantitative specification | Lag and immutable output identity are unresolved. |
| `RSI-03` RSI distance from neutral | Intentional future work | It is algebraically redundant with RSI level and its neutral reference is unapproved. |
| `RSI-04` Price/RSI divergence event | Missing ontology | Confirmed swing identities, divergence rules and confirmation availability are absent. |

### 4.7 MACD Extension

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `MACD-04` MACD histogram delta | Missing quantitative specification | Lag and difference/rate convention are unresolved. |

### 4.8 Volatility

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `VOL-01` Rolling realized volatility | Missing quantitative specification | Return definition, window, centering, divisor and annualization are unresolved. |
| `VOL-02` Upside/downside semivolatility | Missing quantitative specification | Return dependency, window, threshold, divisors and empty-side behavior are unresolved. |
| `VOL-03` Parkinson range volatility | Missing quantitative specification | Window, deterministic logarithm and estimator constant are unresolved. |
| `VOL-04` Volatility term ratio | Missing quantitative specification | Base measure, fast/slow windows, ratio/difference choice and zero rule are unresolved. |
| `VOL-05` Volatility of volatility | Missing quantitative specification | Base series, second window and dispersion/change estimator are unresolved. |

### 4.9 ATR Extensions

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `ATR-02` Normalized ATR | Missing quantitative specification | Price denominator, units and zero behavior are unresolved. |
| `ATR-03` True Range shock ratio | Missing quantitative specification | Prior-only versus current-inclusive ATR reference and semantic owner versus `RNG-02` are unresolved. |
| `ATR-04` ATR slope/change | Missing quantitative specification | Lag and difference/rate normalization are unresolved. |

### 4.10 Bollinger Extensions

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `BB-03` Bollinger center distance | Intentional future work | It duplicates z-score/SMA-distance forms depending on scale; no separate semantic owner is approved. |
| `BB-04` Bollinger bandwidth change | Missing quantitative specification | Lag and difference/rate convention are unresolved. |

### 4.11 Volume and Activity

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `VOLM-01` Relative candle volume | Missing quantitative specification | Window, baseline type/inclusion and zero-baseline rule are unresolved. |
| `VOLM-02` Volume z-score | Missing quantitative specification | Window, dispersion divisor and zero-dispersion behavior are unresolved. |
| `VOLM-03` Signed volume pressure | Missing quantitative specification | Sign, doji, aggregation, normalization and proxy semantics are unresolved. |
| `VOLM-04` On-balance-volume change | Missing quantitative specification | Tie rule, canonical seed, bounded difference window and restart behavior are unresolved. |
| `VOLM-05` Price-volume concordance | Missing quantitative specification | Return/volume dependencies and product/standardization formula are unresolved. |

### 4.12 Candle-Weighted Price and VWAP

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `CWP-01` Rolling candle-volume-weighted price proxy | Missing quantitative specification | Representative price, window and zero-total-volume rule are unresolved. |
| `CWP-02` Candle-weighted price distance | Missing quantitative specification | Upstream proxy and normalization scale are unresolved. |
| `CWP-03` Candle-weighted price slope | Missing quantitative specification | Upstream proxy, lag and change normalization are unresolved. |
| `VWAP-01` True trade-level VWAP | Missing trade-data contract | Individual trade price, size, event-time, revision and window/session evidence do not exist. |

### 4.13 Liquidity

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `LIQ-01` Absolute-return-per-volume proxy | Missing quantitative specification | Return dependency, boundary, denomination and zero-volume rule are unresolved. |
| `LIQ-02` Range-per-volume proxy | Missing quantitative specification | Range choice, window, normalization and zero-volume rule are unresolved. |
| `LIQ-03` Zero-volume frequency | Missing quantitative specification | Window, count/fraction output and feature-versus-data-quality ownership are unresolved. |
| `LIQ-04` Quoted spread | Intentional future work | A future quote snapshot, sampling and staleness contract is required; OHLCV cannot substitute. |
| `LIQ-05` Book depth and imbalance | Intentional future work | A future sequenced order-book/recovery and depth-scope contract is required. |
| `LIQ-06` Trade-flow imbalance | Missing trade-data contract | Trade tape and deterministic aggressor-side classification are absent. |

### 4.14 Range Expansion

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `RNG-01` High-low range ratio | Missing quantitative specification | Prior window, baseline type and zero-baseline rule are unresolved. |
| `RNG-02` True Range expansion ratio | Intentional future work | It may be identical to `ATR-03`; one semantic owner must be selected. |
| `RNG-03` Compression duration | Missing quantitative specification | Base measure, threshold, cap and recursive reset rule are unresolved. |
| `RNG-04` Range expansion acceleration | Missing quantitative specification | Base feature, lag and difference/rate convention are unresolved. |

### 4.15 Market Structure

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `STR-01` Rolling price position | Intentional future work | It overlaps `MOM-02`; one semantic owner must be selected. |
| `STR-02` Prior channel width | Missing quantitative specification | Strictly-prior window and normalization scale are unresolved. |
| `STR-03` Higher-high/lower-low state | Missing ontology | Comparison horizon, equality rules and HH/HL/LH/LL output ontology are absent. |
| `STR-04` Confirmed swing points | Missing ontology | Left/right spans, tie rules, pivot/confirmation identity and lifecycle are absent. |
| `STR-05` Break-of-structure event | Missing ontology | Swing/zone dependency, close-versus-wick rule, equality, direction and event lifecycle are absent. |

### 4.16 Support and Resistance

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `SR-01` Prior upper/lower boundary distance | Missing quantitative specification | Prior window, normalization and equality/zero semantics are unresolved. |
| `SR-02` Boundary touch count | Missing ontology | Boundary source, tolerance, wick/close test and distinct-touch rules are absent. |
| `SR-03` Support/resistance zone lifecycle | Intentional future work | Creation, merge, confirmation, invalidation and expiry belong to future Market Context. |
| `SR-04` Distance to candle-weighted reference | Intentional future work | It duplicates `CWP-02` and other baseline distances; upstream `CWP-01` is unapproved. |

### 4.17 Breakout

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `BRK-01` Prior-range breakout displacement | Missing quantitative specification | `SR-01`, equality and normalization are unresolved. |
| `BRK-02` Breakout range/volume confirmation inputs | Missing quantitative specification | Boundary, range, volume dependencies and output/composite choice are unresolved. |
| `BRK-03` Breakout retest state | Intentional future work | Later-candle tolerance, confirmation, expiry and event lifecycle belong to future Market Context. |
| `BRK-04` Failed-breakout state | Intentional future work | Failure window/equality and immutable later-confirmation semantics belong to future Market Context. |

### 4.18 Mean Reversion

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `MR-01` Rolling price z-score | Intentional future work | It is algebraically redundant with approved Bollinger/SMA/dispersion evidence pending a semantic-owner decision. |
| `MR-02` Normalized EMA deviation | Missing quantitative specification | EMA dependency and ATR/volatility scale choice are unresolved. |
| `MR-03` Short-horizon reversal score | Missing quantitative specification | Short/long lags and combination formula are unresolved. |
| `MR-04` Rolling autoregressive half-life | Missing quantitative specification | Window, estimator, admissibility, deterministic logarithm and failure rules are unresolved. |

### 4.19 Session

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `SES-01` Named UTC participation session | Missing ontology | Session windows, timezone/DST/calendar version and overlap semantics are absent. |
| `SES-02` Session phase encoding | Missing ontology | It depends on the absent session ontology and an approved cyclic encoding. |
| `SES-03` Session overlap flags | Missing ontology | Approved session windows and overlap vocabulary are absent. |

### 4.20 Time

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `TIME-01` UTC time-of-day cyclic encoding | Intentional future work | Timestamp-input metadata and deterministic sine/cosine or lookup architecture are deferred. |
| `TIME-02` UTC day-of-week cyclic encoding | Intentional future work | Timestamp/categorical input support and exact encoding version are deferred. |
| `TIME-03` Weekend indicator | Intentional future work | Timestamp/categorical input support and canonical calendar version are deferred. |
| `TIME-04` Month/quarter boundary proximity | Intentional future work | Timestamp contract plus boundary window/encoding are deferred. |

### 4.21 Statistical

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `STAT-01` Rolling mean return | Missing quantitative specification | Return primitive and window are unresolved. |
| `STAT-02` Rolling return skewness | Missing quantitative specification | Return primitive, window, moment and bias convention are unresolved. |
| `STAT-03` Rolling return excess kurtosis | Missing quantitative specification | Window, fourth-moment, bias and excess conventions are unresolved. |
| `STAT-04` Lagged return autocorrelation | Missing quantitative specification | Return primitive, window, lag, mean/divisor and zero-variance rule are unresolved. |
| `STAT-05` Return entropy/concentration | Missing quantitative specification | Window, bins/symbolization and deterministic logarithm are unresolved. |
| `STAT-06` Rolling quantile position | Missing quantitative specification | Measure, reference boundary, window and tie convention are unresolved. |

### 4.22 Relative Strength

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `REL-01` Short/long self-relative return spread | Missing quantitative specification | Return definition, horizons, combination and zero rule are unresolved. |
| `REL-02` Price relative to trailing benchmark | Intentional future work | It duplicates SMA/EMA/CWP distance candidates; one semantic owner must be selected. |
| `REL-03` Relative activity strength | Missing quantitative specification | Fast/slow volume baselines and combination rule are unresolved. |
| `REL-04` Cross-asset relative strength | Intentional future work | External synchronized asset evidence, normalization and as-of provenance are deferred. |

### 4.23 Multi-Timeframe Context

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `MTF-01` Higher-timeframe trend as-of | Intentional future work | Completed-higher-timeframe as-of selection and shared-source provenance contract are deferred. |
| `MTF-02` Cross-timeframe volatility ratio | Intentional future work | Cross-timeframe join and compatible volatility scaling are deferred. |
| `MTF-03` Cross-timeframe momentum spread | Intentional future work | Cross-timeframe join and normalized momentum selection are deferred. |
| `MTF-04` Directional alignment vector | Intentional future work | Context vector semantics and cross-timeframe evidence belong to future Market Context. |
| `MTF-05` Alignment age/staleness descriptor | Intentional future work | Primary cutoff and selected higher-timeframe availability provenance are deferred. |

### 4.24 Market Regime

| Feature | Blocker class | Exact blocker |
| --- | --- | --- |
| `REG-01` Continuous trend-strength input | Intentional future work | It would duplicate registered ADX/trend evidence and should be selected as context metadata. |
| `REG-02` Continuous volatility-state input | Intentional future work | It would duplicate a future selected volatility-change feature. |
| `REG-03` Joint trend-volatility-activity vector | Intentional future work | It is a future Market Context component, not an independent scalar feature. |
| `REG-04` Categorical market regime | Intentional future work | Reference distributions, thresholds, ontology and update lifecycle belong to future Market Context. |

## 5. Validation and Architecture Audit

Because no implementation was authorized, focused tests mean the complete
existing feature/registry/pipeline regression set. Final validation results:

- Ruff: passed;
- Python compilation: passed;
- focused feature/registry/pipeline tests: 126 passed;
- full backend suite: 348 passed; and
- `git diff --check`: passed.

Architecture findings:

- **Registry integrity:** unchanged; all 19 definitions remain versioned and
  topologically valid.
- **Dependency reuse:** unchanged; no hidden calculation or new dependency was
  added.
- **Pipeline ordering:** unchanged at pipeline `2.7.0`.
- **Provenance completeness:** unchanged; no unsupported value was created.
- **Hash determinism:** registry and pipeline hash algorithms and payloads are
  unchanged.
- **No duplicated mathematics:** overlapping candidates remain deferred rather
  than being registered under duplicate identities.

## 6. Phase 2 Completion Decision

Phase 2 is **NOT COMPLETE**.

The exact remaining blocker totals across 99 skipped catalog candidates are:

| Blocker class | Feature count |
| --- | ---: |
| Missing quantitative specification | 60 |
| Missing ontology | 8 |
| Missing trade-data contract | 2 |
| Intentional future work | 29 |
| **Total skipped** | **99** |

The absence of an unblocked implementation does not convert blocked candidates
into completed or optional features. No completion commit is permitted under
this request because no implementation occurred and Phase 2 remains open.

## 7. Remaining Governance Work

Phase 2 requires, at minimum:

1. explicit selection and approval of a foundational return feature;
2. an approved provider-scoped candle-volume/activity specification;
3. approved normalized volatility/range-expansion mathematics;
4. approved strictly-prior boundary and breakout-displacement mathematics;
5. a non-repainting Market Structure ontology covering comparison horizons,
   pivot/confirmation identities, ties, HH/HL/LH/LL, BOS and lifecycle rules;
6. semantic-owner decisions for every algebraic duplicate;
7. a decision on whether timestamp and cross-timeframe architecture belongs in
   Phase 2 or intentional future work; and
8. separate future trade, quote and order-book contracts for VWAP and direct
   liquidity evidence.

## 8. Recommended Next Project Phase

The next phase should be **Phase 2 Quantitative Governance Closure**, not the
Market Context Engine.

The smallest recommended approval sequence is:

1. one return primitive;
2. relative candle volume;
3. one normalized volatility or range-expansion feature;
4. strictly-prior upper/lower boundary distance and breakout displacement; and
5. the Market Structure ontology as a separate governance artifact.

Only after those prerequisites are approved and implemented should AlphaLens
reassess Phase 2 completion and authorize Market Context. Trade-, quote-, and
order-book-dependent features may remain intentional future work if the first
context contract represents those domains explicitly as unavailable rather
than fabricating candle proxies.
