# AlphaLens v2 Feature Library Completion Report

**Report date:** 2026-08-01

**Scope:** Phase 2 Feature Catalog, Feature Registry, Core Intelligence
Specification, and current implementation

## 1. Executive Summary

The AlphaLens v2 runtime Feature Library contains 19 registered definitions
and 30 deterministic outputs. All registered outputs are fully implemented,
tested, persisted immutably, provenance-linked, and executed by intraday
pipeline `2.7.0`.

The broader planned library is not complete. Most Phase 2 catalog entries are
candidate hypotheses rather than approved definitions. The catalog explicitly
states that no candidate is approved and requires a later quantitative freeze
before implementation. Later approvals completed seven catalog candidates and
also introduced 23 independently usable registered outputs that do not have an
exact one-to-one catalog-candidate equivalent.

The current library is strong enough for trend, momentum, range, and
statistical-volatility evidence, but it is not sufficient to begin a compliant
Market Context Engine. It lacks approved candle-volume context, prior-boundary
and non-repainting structure evidence, session/time semantics, a Market
Structure ontology, and the Market Context definition itself.

## 2. Counting Method and Completion Percentage

The completion denominator is a deduplicated set of planned feature records:

- 106 named Phase 2 catalog candidates; plus
- 23 registered outputs with no exact one-to-one equivalent among those
  catalog candidates.

Seven catalog candidates are fully implemented under later approved
quantitative specifications: `ATR-01`, `RSI-01`, `MACD-01`, `MACD-02`,
`MACD-03`, `BB-01`, and `BB-02`. The other 23 implemented records are listed
in Section 4.

Therefore:

\[
\text{completion}=\frac{30}{129}\times100=23.3\%\text{ (rounded to one decimal)}
\]

This metric intentionally does not count a partial dependency as completion
of a broader candidate. For example, registered SMA-20 does not complete
`TRD-01`, which additionally requires a normalized close-to-SMA distance.
Likewise, registered EMA levels do not complete the catalog version of
`EMA-01`, which also proposes a separately declared distance output.

## 3. Status and Effort Conventions

Every planned feature receives exactly one of the requested classifications:

- ✅ Fully Implemented
- 🟡 Blocked by Missing Quantitative Specification
- 🟡 Blocked by Missing Data Contract
- 🟡 Blocked by Missing Trade Data
- 🟡 Blocked by Missing Market Structure Ontology
- 🟡 Blocked by Future Market Context Dependency
- 🟡 Intentionally Deferred

Effort estimates describe implementation after the stated prerequisite is
approved; they exclude quantitative research, governance review, external
data acquisition, and Market Context design:

- **S:** 1–3 engineering days;
- **M:** 4–8 engineering days; and
- **L:** 2–4 engineering weeks or a cross-component architecture change.

Document abbreviations used below:

- **Catalog:** `ALPHALENS_V2_PHASE_2_FEATURE_CATALOG.md`, especially Sections
  1, 4.1, 5, and 9;
- **Standard:** `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`, especially
  its authority, quantitative-freeze, determinism, provenance, and
  conformance requirements;
- **Core:** `ALPHALENS_V2_CORE_INTELLIGENCE_SPECIFICATION.md`, especially
  Sections 3.2–3.3 and the Market Context boundaries;
- **Approved family specification:** the applicable ATR, EMA, RSI, MACD,
  Statistical Volatility, or Directional Movement quantitative specification.

## 4. Fully Implemented Registry Outputs Without Exact Catalog Equivalents

Each item in this table is classified ✅ Fully Implemented.

| Registered output | Governing authority | Notes |
| --- | --- | --- |
| `candle_body_fraction` | Tier-A Feature Specification | Frozen completed-candle body geometry. |
| `candle_range_fraction` | Tier-A Feature Specification | Frozen normalized high-low geometry. |
| `upper_wick_fraction` | Tier-A Feature Specification | Frozen upper-wick geometry. |
| `lower_wick_fraction` | Tier-A Feature Specification | Frozen lower-wick geometry. |
| `true_range` | Tier-A Feature Specification | Frozen gap-aware range primitive. |
| `exponential_moving_average_12` | EMA Feature Family Specification | Approved EMA-12 price level. |
| `exponential_moving_average` | EMA Feature Family Specification | Approved EMA-20 price level. |
| `exponential_moving_average_26` | EMA Feature Family Specification | Approved EMA-26 price level. |
| `exponential_moving_average_50` | EMA Feature Family Specification | Approved EMA-50 price level. |
| `exponential_moving_average_100` | EMA Feature Family Specification | Approved EMA-100 price level. |
| `exponential_moving_average_200` | EMA Feature Family Specification | Approved EMA-200 price level. |
| `simple_moving_average_20` | Statistical Volatility Family Specification | Approved current-inclusive SMA-20 level. |
| `rolling_standard_deviation_20` | Statistical Volatility Family Specification | Approved population standard deviation. |
| `bollinger_middle` | Statistical Volatility Family Specification | Registered reuse of SMA-20 as the band center. |
| `bollinger_upper` | Statistical Volatility Family Specification | Approved upper band. |
| `bollinger_lower` | Statistical Volatility Family Specification | Approved lower band. |
| `positive_directional_movement` | Directional Movement Family Specification | Approved strict dominant upward movement. |
| `negative_directional_movement` | Directional Movement Family Specification | Approved strict dominant downward movement. |
| `positive_directional_indicator` | Directional Movement Family Specification | Approved Wilder-smoothed +DI. |
| `negative_directional_indicator` | Directional Movement Family Specification | Approved Wilder-smoothed −DI. |
| `directional_index` | Directional Movement Family Specification | Approved DX. |
| `average_directional_index` | Directional Movement Family Specification | Approved ADX. |
| `average_directional_movement_rating` | Directional Movement Family Specification | Approved ADXR. |

The implemented catalog candidates appear in their original catalog-family
tables in Section 5.

## 5. Complete Phase 2 Catalog Classification

### 5.1 Return and Price Transforms

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `RET-01` Lagged log-return family | 🟡 Blocked by Missing Quantitative Specification | Lag set and deterministic Decimal logarithm are unresolved. | Catalog §§5.1, 9.3; Standard | Approved lag vector, log algorithm/version, identities and fixtures. | M | Momentum, realized volatility, statistics, relative strength, regime inputs. |
| `RET-02` Lagged arithmetic rate of change | 🟡 Blocked by Missing Quantitative Specification | Lag set, denominator policy, and semantic choice versus log return are unresolved. | Catalog §§5.1, 9.3 | Approved lags, denominator/zero rule, output identity. | S | Momentum, acceleration, self-relative returns. |
| `RET-03` Prior-close displacement fraction | 🟡 Blocked by Missing Quantitative Specification | Formula is illustrated but the catalog expressly withholds selection, identity, version, fixtures, and approval. | Catalog §§1, 5.1, 9 | Explicit candidate approval and immutable quantitative specification. | S | Return primitives, volatility, momentum. |
| `RET-04` Representative candle price | 🟡 Blocked by Missing Quantitative Specification | Typical price versus OHLC mean or another proxy is unresolved. | Catalog §5.1 | Approved proxy formula, units, name, edge cases. | S | Candle-weighted price proxy and related distances. |
| `RET-05` Open-to-prior-close gap fraction | 🟡 Blocked by Missing Quantitative Specification | Example formula exists, but candidate selection, identity, version, and fixtures are not approved. | Catalog §§1, 5.1, 9 | Explicit quantitative freeze and release identity. | S | Gap analysis, price action, range/volatility research. |

### 5.2 Price Action

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `PA-01` Close location value | 🟡 Blocked by Missing Quantitative Specification | Normalization and zero-range rule are unresolved. | Catalog §5.2 | Exact bounded formula, zero rule, output identity. | S | Breakout, pressure, structure evidence. |
| `PA-02` Wick imbalance | 🟡 Intentionally Deferred | Algebraically derived from registered wick fractions and intentionally redundant pending incremental-value approval. | Catalog §§5.2, 10.2 | Explicit semantic-owner decision and approved difference/ratio zero rule. | S | Price rejection and context inputs. |
| `PA-03` Inside/outside bar state | 🟡 Blocked by Missing Quantitative Specification | Equality convention and categorical versus separate Decimal outputs are unresolved. | Catalog §5.2; Standard | Approved ontology, equality rules, output schema. | S | Range expansion and structure. |
| `PA-04` Directional candle streak | 🟡 Blocked by Missing Quantitative Specification | Doji/reset convention, cap, seed, and first-valid rule are unresolved. | Catalog §5.2 | Complete recursive specification and restart policy. | M | Momentum persistence and trend context. |
| `PA-05` Body-to-range ratio | 🟡 Intentionally Deferred | Fully derived from registered candle geometry and marked highly redundant. | Catalog §§5.2, 10.2 | Evidence-based approval that a separate semantic output is justified. | S | Price action compression only. |

### 5.3 Trend

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `TRD-01` SMA distance | 🟡 Blocked by Missing Quantitative Specification | SMA-20 exists, but window choice for this candidate and normalization scale are unresolved. | Catalog §5.3; Core §3.2 | Approved window, scale, formula and semantic owner. | S | Mean reversion, relative strength, trend context. |
| `TRD-02` SMA slope | 🟡 Blocked by Missing Quantitative Specification | SMA period, slope lag, endpoint convention, and normalization are unresolved. | Catalog §5.3 | Exact dependencies, lag, difference/rate formula. | M | Trend strength, acceleration, context. |
| `TRD-03` Rolling linear-regression slope | 🟡 Blocked by Missing Quantitative Specification | Window, OLS estimator, time scaling, normalization, and optional fit output are unresolved. | Catalog §5.3; Standard numeric policy | Deterministic Decimal OLS specification and fixtures. | M | Trend and regime research. |
| `TRD-04` Trend efficiency ratio | 🟡 Blocked by Missing Quantitative Specification | Window, signed versus unsigned output, and zero-path rule are unresolved. | Catalog §5.3 | Exact period, domain and zero rule. | S | Trend-strength/context inputs. |
| `TRD-05` Directional persistence fraction | 🟡 Blocked by Missing Quantitative Specification | Window, return-sign dependency, zero-return treatment, and output selection are unresolved. | Catalog §5.3 | Approved sign primitive, window and output semantics. | S | Momentum and trend context. |

### 5.4 EMA Family

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `EMA-01` EMA baseline and distance | 🟡 Blocked by Missing Quantitative Specification | Six EMA levels exist, but the catalog candidate additionally requires a selected period and separately declared normalized distance. | Catalog §5.4; EMA Family Specification non-goals | Approval of the distance output, chosen EMA dependency and normalization. | S | Trend distance and mean reversion. |
| `EMA-02` EMA slope | 🟡 Blocked by Missing Quantitative Specification | Lag and normalization are unresolved. | Catalog §5.4 | Selected EMA, lag, difference/rate and scale. | S | Trend acceleration and context. |
| `EMA-03` Fast/slow EMA spread | 🟡 Intentionally Deferred | With 12/26 periods it duplicates the registered MACD line; catalog prohibits duplicate semantic ownership. | Catalog §§5.4, 10.2; MACD Specification | A distinct approved parameterization/hypothesis or formal retirement. | S | Trend context; otherwise MACD already supplies it. |
| `EMA-04` EMA ribbon dispersion | 🟡 Blocked by Missing Quantitative Specification | EMA member set and dispersion/order formula are unresolved. | Catalog §5.4 | Ordered member vector, statistic, normalization and domain. | M | Trend agreement/context. |

### 5.5 Momentum

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `MOM-01` Return acceleration | 🟡 Blocked by Missing Quantitative Specification | Return representation, lag and normalization are unresolved. | Catalog §5.5 | Approved return dependency and delta specification. | S | Momentum/exhaustion context. |
| `MOM-02` Stochastic close position | 🟡 Blocked by Missing Quantitative Specification | Window and zero-range rule are unresolved; semantic overlap with `STR-01` is undecided. | Catalog §§5.5, 10.2 | Period, formula, tie/zero rule and semantic owner. | S | Momentum and boundary context. |
| `MOM-03` Momentum persistence | 🟡 Blocked by Missing Quantitative Specification | Window, aligned-return definition and zero-return behavior are unresolved. | Catalog §5.5 | Return dependency and exact balance/fraction formula. | S | Momentum summary and trend maturity. |
| `MOM-04` Price acceleration | 🟡 Blocked by Missing Quantitative Specification | Endpoint or slope components, windows, lags and normalization are unresolved. | Catalog §5.5 | Complete causal slope-difference definition. | M | Exhaustion/reversal research. |

### 5.6 RSI Family

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `RSI-01` RSI level | ✅ Fully Implemented | Registered `relative_strength_index` `1.0.0`, period 14, approved Wilder seed/recurrence. | RSI-01 Quantitative Specification | None. | — | Momentum and future context. |
| `RSI-02` RSI delta | 🟡 Blocked by Missing Quantitative Specification | Lag is unresolved. | Catalog §5.6; RSI Specification non-goals | Exact lag, domain and identity. | S | Momentum acceleration. |
| `RSI-03` RSI distance from neutral | 🟡 Intentionally Deferred | Algebraically redundant with RSI level; neutral reference and normalization are unapproved. | Catalog §5.6; RSI Specification non-goals | Evidence for separate output plus approved reference. | S | Momentum interpretation only. |
| `RSI-04` Price/RSI divergence event | 🟡 Blocked by Missing Market Structure Ontology | Requires confirmed price/RSI swings and non-backdated divergence rules. | Catalog §5.6; Core §3.2 | Approved swing and divergence ontology with confirmation availability. | L | Reversal-candidate Market Context. |

### 5.7 MACD Family

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `MACD-01` MACD line | ✅ Fully Implemented | Registered line reuses approved EMA-12 and EMA-26. | MACD-01 Quantitative Specification | None. | — | Signal, histogram, trend/momentum context. |
| `MACD-02` MACD signal | ✅ Fully Implemented | Registered approved 9-observation signal recurrence. | MACD-01 Quantitative Specification | None. | — | Histogram and momentum context. |
| `MACD-03` MACD histogram | ✅ Fully Implemented | Registered line-minus-signal output. | MACD-01 Quantitative Specification | None. | — | Momentum acceleration/context. |
| `MACD-04` MACD histogram delta | 🟡 Blocked by Missing Quantitative Specification | Lag and difference/rate convention are unresolved. | Catalog §5.7; MACD Specification non-goals | Exact lag and output definition. | S | Momentum acceleration/exhaustion. |

### 5.8 Volatility

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `VOL-01` Rolling realized volatility | 🟡 Blocked by Missing Quantitative Specification | Return definition, window, centering, divisor and annualization are unresolved. | Catalog §5.8; Core §3.2 | Approved return primitive and estimator specification. | M | Volatility context, scaling, regime inputs. |
| `VOL-02` Upside/downside semivolatility | 🟡 Blocked by Missing Quantitative Specification | Return dependency, window, threshold, denominators and empty-side behavior are unresolved. | Catalog §5.8 | Complete two-output estimator definition. | M | Asymmetric volatility context. |
| `VOL-03` Parkinson range volatility | 🟡 Blocked by Missing Quantitative Specification | Window, deterministic logarithm and estimator constant are unresolved. | Catalog §5.8; Standard numeric policy | Approved Decimal log and estimator fixtures. | L | Range-volatility research. |
| `VOL-04` Volatility term ratio | 🟡 Blocked by Missing Quantitative Specification | Base measure, fast/slow windows, ratio versus difference and zero rule are unresolved. | Catalog §5.8 | Two approved base-volatility dependencies and combination rule. | S | Expansion/compression context. |
| `VOL-05` Volatility of volatility | 🟡 Blocked by Missing Quantitative Specification | Base series, second window and dispersion/change statistic are unresolved. | Catalog §5.8 | Approved dependency and nested estimator. | M | Volatility instability/context. |

### 5.9 ATR-Derived

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `ATR-01` Average True Range | ✅ Fully Implemented | Registered 14-observation arithmetic mean of `true_range` `1.0.0`. | Approved ATR Quantitative Specification | None. | — | Range scale and future normalized volatility. |
| `ATR-02` Normalized ATR | 🟡 Blocked by Missing Quantitative Specification | Positive price denominator, units and zero policy are unresolved. | Catalog §5.9; ATR Specification non-goals | Approved denominator/reference and output identity. | S | Cross-time scale comparison and context. |
| `ATR-03` True Range shock ratio | 🟡 Blocked by Missing Quantitative Specification | Prior-only versus current-inclusive ATR reference is unresolved. | Catalog §§5.9, 10.2 | Boundary rule, zero denominator and semantic owner versus `RNG-02`. | S | Expansion/shock context. |
| `ATR-04` ATR slope/change | 🟡 Blocked by Missing Quantitative Specification | Lag and difference/rate normalization are unresolved. | Catalog §5.9 | Exact lag and change formula. | S | Volatility expansion/context. |

### 5.10 Bollinger Family

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `BB-01` Bollinger percent-B | ✅ Fully Implemented | Registered `bollinger_percent_b` uses approved 20-period population bands, multiplier 2, unclipped output and zero-width rule. | Statistical Volatility Family Specification | None. | — | Extension and mean-reversion evidence. |
| `BB-02` Bollinger bandwidth | ✅ Fully Implemented | Registered `bollinger_band_width` uses approved center normalization. | Statistical Volatility Family Specification | None. | — | Compression/volatility context. |
| `BB-03` Bollinger center distance | 🟡 Intentionally Deferred | Algebraically duplicates z-score/SMA-distance forms depending on scale; semantic owner is deliberately unresolved. | Catalog §§5.10, 10.2 | Incremental hypothesis and one approved normalization owner. | S | Mean-reversion/trend extension. |
| `BB-04` Bollinger bandwidth change | 🟡 Blocked by Missing Quantitative Specification | Lag and difference/rate convention are unresolved. | Catalog §5.10 | Exact lag and change formula. | S | Compression/expansion context. |

### 5.11 Volume and Activity

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `VOLM-01` Relative candle volume | 🟡 Blocked by Missing Quantitative Specification | Window, baseline type, inclusion boundary and zero-baseline rule are unresolved. | Catalog §5.11; Core §3.2 | Approved provider-scoped baseline specification. | S | Volume summary, breakout context, `VOLM-05`, `REL-03`, `BRK-02`. |
| `VOLM-02` Volume z-score | 🟡 Blocked by Missing Quantitative Specification | Window, dispersion divisor and zero-dispersion rule are unresolved. | Catalog §5.11 | Approved mean/dispersion estimator and period. | M | Volume/activity context. |
| `VOLM-03` Signed volume pressure | 🟡 Blocked by Missing Quantitative Specification | Sign, doji, aggregation, normalization and proxy naming are unresolved. | Catalog §5.11 | Exact candle-direction proxy specification. | M | Volume pressure/context. |
| `VOLM-04` On-balance-volume change | 🟡 Blocked by Missing Quantitative Specification | Tie rule, canonical seed, bounded difference window and restart behavior are unresolved. | Catalog §5.11 | Approved OBV-change rather than path-level specification. | M | Trend-volume concordance. |
| `VOLM-05` Price-volume concordance | 🟡 Blocked by Missing Quantitative Specification | Return and relative-volume dependencies plus product/standardization formula are unresolved. | Catalog §5.11 | Approved upstream features and interaction formula. | S | Breakout/activity context. |

### 5.12 Candle-Weighted Price and VWAP

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `CWP-01` Rolling candle-volume-weighted price proxy | 🟡 Blocked by Missing Quantitative Specification | Representative candle price, window and zero-total-volume rule are unresolved. | Catalog §§5.1, 5.12 | Approved `RET-04`, period, boundary and explicit proxy identity. | M | `CWP-02`, `CWP-03`, `SR-04`. |
| `CWP-02` Candle-weighted price distance | 🟡 Blocked by Missing Quantitative Specification | Upstream proxy and scale normalization are unresolved. | Catalog §5.12 | Approved `CWP-01` and distance scale. | S | Mean-reversion/reference context. |
| `CWP-03` Candle-weighted price slope | 🟡 Blocked by Missing Quantitative Specification | Upstream proxy, lag and normalization are unresolved. | Catalog §5.12 | Approved `CWP-01`, lag and change formula. | S | Trend/reference context. |
| `VWAP-01` True trade-level VWAP | 🟡 Blocked by Missing Trade Data | No individual trade price/size/event-time memberships or session/window contract exist; candles cannot substitute. | Catalog §5.12; Core §3.2 | Approved immutable trade-data contract, late/revision policy and VWAP window/session. | L | True transactional price context. |

### 5.13 Liquidity

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `LIQ-01` Absolute-return-per-volume proxy | 🟡 Blocked by Missing Quantitative Specification | Return dependency, rolling boundary, denomination and zero-volume rule are unresolved. | Catalog §5.13 | Approved proxy formula and explicit non-liquidity semantics. | M | Optional fragility proxy; Market Context liquidity cannot treat it as direct evidence. |
| `LIQ-02` Range-per-volume proxy | 🟡 Blocked by Missing Quantitative Specification | Range choice, window, normalization and zero-volume rule are unresolved. | Catalog §5.13 | Approved proxy definition and semantic label. | M | Optional activity/fragility context. |
| `LIQ-03` Zero-volume frequency | 🟡 Blocked by Missing Quantitative Specification | Window and count/fraction semantics are unresolved; ownership as data quality versus feature is undecided. | Catalog §5.13 | Approved window, output and ownership decision. | S | Source-quality/activity context. |
| `LIQ-04` Quoted spread | 🟡 Blocked by Missing Data Contract | No point-in-time quote stream, sampling, staleness or crossed-market contract exists. | Catalog §5.13; Core §3.2 | Approved quote snapshot and provenance contract. | L | Direct liquidity summary and execution context. |
| `LIQ-05` Book depth and imbalance | 🟡 Blocked by Missing Data Contract | No sequenced order-book snapshot/recovery contract or depth scope exists. | Catalog §5.13; Core §3.2 | Approved book ingestion, reconstruction and level-aggregation contract. | L | Direct liquidity/market-depth context. |
| `LIQ-06` Trade-flow imbalance | 🟡 Blocked by Missing Trade Data | No trade tape or approved aggressor-side classification exists. | Catalog §5.13; Core §3.2 | Trade contract and deterministic aggressor classifier/version. | L | Order-flow/liquidity context. |

### 5.14 Range Expansion

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `RNG-01` High-low range ratio | 🟡 Blocked by Missing Quantitative Specification | Prior window, baseline type and zero-baseline rule are unresolved. | Catalog §5.14 | Exact prior-only period and ratio behavior. | S | Compression/expansion and breakout context. |
| `RNG-02` True Range expansion ratio | 🟡 Intentionally Deferred | Potentially identical to `ATR-03`; catalog requires one semantic owner. | Catalog §§5.14, 10.2 | Deduplication decision and approved prior reference. | S | Range shock context. |
| `RNG-03` Compression duration | 🟡 Blocked by Missing Quantitative Specification | Base measure, threshold, cap and recursive reset rule are unresolved. | Catalog §5.14 | Approved condition and recursive state specification. | M | Compression-state context. |
| `RNG-04` Range expansion acceleration | 🟡 Blocked by Missing Quantitative Specification | Base feature, lag and difference/rate convention are unresolved. | Catalog §5.14 | Approved dependency and delta formula. | S | Expansion acceleration/context. |

### 5.15 Market Structure

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `STR-01` Rolling price position | 🟡 Intentionally Deferred | Semantically equivalent to `MOM-02` under matching parameters; one owner must be selected. | Catalog §§5.15, 10.2 | Approved owner, period and zero-range rule. | S | Boundary/momentum context. |
| `STR-02` Prior channel width | 🟡 Blocked by Missing Quantitative Specification | Strictly-prior window and normalization scale are unresolved. | Catalog §5.15 | Exact period, denominator and zero rule. | S | Structure, support/resistance and breakout. |
| `STR-03` Higher-high/lower-low state | 🟡 Blocked by Missing Market Structure Ontology | Comparison horizon, equality rule and HH/HL/LH/LL output ontology are unresolved. | Catalog §5.15; Core §3.2 | Non-repainting comparison ontology and output schema. | M | Trend state, BOS/CHOCH and structure summary. |
| `STR-04` Confirmed swing points | 🟡 Blocked by Missing Market Structure Ontology | Left/right spans, tie rule, confirmation time and event representation are unresolved. | Catalog §5.15; Core §3.2 | Approved non-repainting swing ontology and lifecycle contract. | L | Support/resistance, BOS, CHOCH, divergence, breakout lifecycle. |
| `STR-05` Break-of-structure event | 🟡 Blocked by Missing Market Structure Ontology | Swing/zone dependency, close-versus-wick, equality, direction and event lifecycle are unresolved. | Catalog §5.15; Core §3.2 | Approved swing/zone and BOS ontology. | L | Structure summary and Market Context. |

### 5.16 Support and Resistance

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `SR-01` Prior upper/lower boundary distance | 🟡 Blocked by Missing Quantitative Specification | Prior window, normalization and equality/zero semantics are unresolved. | Catalog §5.16 | Approved period, boundary outputs and distance scale. | S | `BRK-01`, channel/structure context. |
| `SR-02` Boundary touch count | 🟡 Blocked by Missing Market Structure Ontology | Boundary source, tolerance, wick/close test and distinct-touch rules are unresolved. | Catalog §5.16; Core §3.2 | Approved boundary/touch ontology and tolerance. | M | Zone strength and Market Context. |
| `SR-03` Support/resistance zone lifecycle | 🟡 Blocked by Future Market Context Dependency | Versioned creation, merge, confirmation, invalidation and expiry belong to Market Context. | Catalog §5.16; Core §§3.2, Market Context | Approved zone ontology and Market Context lifecycle persistence. | L | Structure and support/resistance summaries. |
| `SR-04` Distance to candle-weighted reference | 🟡 Intentionally Deferred | Duplicates `CWP-02` and other baseline distances; `CWP-01` is itself unapproved. | Catalog §§5.12, 5.16, 10.2 | Semantic-owner decision and approved upstream proxy. | S | Reference-distance context. |

### 5.17 Breakout

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `BRK-01` Prior-range breakout displacement | 🟡 Blocked by Missing Quantitative Specification | `SR-01`, equality and normalization are unresolved. | Catalog §5.17 | Approved prior-boundary dependency and displacement formula. | S | Breakout evidence and `BRK-02`–`BRK-04`. |
| `BRK-02` Breakout range/volume confirmation inputs | 🟡 Blocked by Missing Quantitative Specification | Boundary displacement, range expansion, relative volume and composite/output choice are unresolved. | Catalog §5.17 | Approved `BRK-01`, range and volume dependencies plus output contract. | M | Breakout context summary. |
| `BRK-03` Breakout retest state | 🟡 Blocked by Future Market Context Dependency | Retest tolerance, confirmation, expiry and predecessor-event lifecycle require later candles and context ownership. | Catalog §5.17; Core Market Context | Approved breakout event and context lifecycle contract. | L | Retest/structure context. |
| `BRK-04` Failed-breakout state | 🟡 Blocked by Future Market Context Dependency | Failure window/equality and immutable later-confirmation event semantics are unresolved and cannot be backdated. | Catalog §5.17; Core Market Context | Approved breakout lifecycle and failure ontology. | L | Reversal-candidate context. |

### 5.18 Mean Reversion

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `MR-01` Rolling price z-score | 🟡 Intentionally Deferred | With approved SMA-20 and population deviation it is algebraically redundant with Bollinger position/center distance; no separate owner is approved. | Catalog §§5.18, 10.2 | Incremental hypothesis and approved center/scale owner. | M | Mean-reversion context. |
| `MR-02` Normalized EMA deviation | 🟡 Blocked by Missing Quantitative Specification | EMA dependency and ATR/volatility scale choice are unresolved. | Catalog §5.18 | Selected EMA and approved normalized scale dependency. | S | Mean-reversion/trend extension. |
| `MR-03` Short-horizon reversal score | 🟡 Blocked by Missing Quantitative Specification | Short/long lags and product/difference/direction formula are unresolved. | Catalog §5.18 | Approved return dependencies and combination formula. | S | Reversal-candidate context. |
| `MR-04` Rolling autoregressive half-life | 🟡 Blocked by Missing Quantitative Specification | Window, estimator, admissibility, deterministic log and failure rules are unresolved. | Catalog §5.18; Standard numeric policy | Complete reproducible AR/half-life specification. | L | Mean-reversion research; not a prerequisite for core context. |

### 5.19 Session

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `SES-01` Named UTC participation session | 🟡 Blocked by Missing Data Contract | Current feature metadata has no timestamp/categorical input contract; session ontology, timezone/DST/calendar and overlap rules are absent. | Catalog §5.19; Core §3.2 | Approved session ontology and additive timestamp/categorical contract. | M | Session summary and context. |
| `SES-02` Session phase encoding | 🟡 Blocked by Missing Data Contract | Depends on absent `SES-01` ontology and deterministic cyclic encoding contract. | Catalog §5.19; Core §3.2 | Session ontology plus encoding/version specification. | M | Intraday seasonality/context. |
| `SES-03` Session overlap flags | 🟡 Blocked by Missing Data Contract | Depends on absent session windows and categorical overlap semantics. | Catalog §5.19; Core §3.2 | Approved session ontology and overlap outputs. | S | Session/context descriptors. |

### 5.20 Time

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `TIME-01` UTC time-of-day cyclic encoding | 🟡 Blocked by Missing Data Contract | Registry metadata supports candle fields, not timestamp inputs; deterministic sine/cosine or lookup policy is absent. | Catalog §5.20; Catalog §2.3 | Approved timestamp-input contract and numeric encoding. | M | Session/seasonality context. |
| `TIME-02` UTC day-of-week cyclic encoding | 🟡 Blocked by Missing Data Contract | Timestamp input/categorical contract and exact encoding version are absent. | Catalog §5.20; Catalog §2.3 | Approved timestamp contract and seven-day encoding. | M | Weekly seasonality/context. |
| `TIME-03` Weekend indicator | 🟡 Blocked by Missing Data Contract | Timestamp/categorical input metadata and canonical calendar version are absent. | Catalog §5.20; Catalog §2.3 | Approved timestamp input and Boolean Decimal/categorical output contract. | S | Session/activity context. |
| `TIME-04` Month/quarter boundary proximity | 🟡 Blocked by Missing Data Contract | Timestamp contract and proximity window/encoding are unresolved. | Catalog §5.20; Catalog §2.3 | Approved calendar input, boundary window and output semantics. | S | Calendar context. |

### 5.21 Statistical

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `STAT-01` Rolling mean return | 🟡 Blocked by Missing Quantitative Specification | Return primitive and window are unresolved. | Catalog §5.21 | Approved returns, period and mean boundary. | S | Drift/trend context. |
| `STAT-02` Rolling return skewness | 🟡 Blocked by Missing Quantitative Specification | Return primitive, window, centered-moment and bias convention are unresolved. | Catalog §5.21 | Deterministic third-moment estimator and minimum sample. | M | Distribution/asymmetry context. |
| `STAT-03` Rolling return excess kurtosis | 🟡 Blocked by Missing Quantitative Specification | Window, fourth-moment, bias and excess conventions are unresolved. | Catalog §5.21 | Deterministic fourth-moment estimator and minimum sample. | M | Tail/distribution context. |
| `STAT-04` Lagged return autocorrelation | 🟡 Blocked by Missing Quantitative Specification | Return primitive, window, lag, mean/divisor and zero-variance rule are unresolved. | Catalog §5.21 | Complete point-in-time correlation estimator. | M | Momentum/reversal research. |
| `STAT-05` Return entropy/concentration | 🟡 Blocked by Missing Quantitative Specification | Window, bins/symbolization and deterministic logarithm are unresolved. | Catalog §5.21; Standard numeric policy | Frozen bins, log algorithm and estimator. | L | Distribution/regime research. |
| `STAT-06` Rolling quantile position | 🟡 Blocked by Missing Quantitative Specification | Measure, prior versus inclusive reference, window and tie convention are unresolved. | Catalog §5.21 | Approved rank definition and reference boundary. | M | Robust extension/context. |

### 5.22 Relative Strength

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `REL-01` Short/long self-relative return spread | 🟡 Blocked by Missing Quantitative Specification | Return definition, horizons, difference/ratio and zero rule are unresolved. | Catalog §5.22 | Approved fast/slow returns and combination. | S | Trend/momentum maturity. |
| `REL-02` Price relative to trailing benchmark | 🟡 Intentionally Deferred | Duplicates `TRD-01`, EMA distance or `CWP-02`; semantic owner is unresolved. | Catalog §§5.22, 10.2 | One approved benchmark-distance owner. | S | Trend/mean-reversion context. |
| `REL-03` Relative activity strength | 🟡 Blocked by Missing Quantitative Specification | Fast/slow relative-volume dependencies do not exist and combination is unresolved. | Catalog §5.22 | Approved volume baselines and ratio/difference rule. | S | Volume/activity context. |
| `REL-04` Cross-asset relative strength | 🟡 Blocked by Missing Data Contract | No synchronized external asset evidence, quote normalization or as-of policy exists. | Catalog §5.22; Core source boundary | Approved multi-asset source, normalization and synchronized provenance contract. | L | Cross-asset context; not needed for single-asset engine. |

### 5.23 Multi-Timeframe Context

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `MTF-01` Higher-timeframe trend as-of | 🟡 Blocked by Missing Data Contract | No cross-timeframe as-of selection, availability or shared-source provenance contract exists. | Catalog §5.23; Core §3.2 | Approved completed-higher-timeframe join contract. | L | Multi-timeframe Market Context. |
| `MTF-02` Cross-timeframe volatility ratio | 🟡 Blocked by Missing Data Contract | Cross-timeframe join and compatible volatility scaling are absent. | Catalog §5.23; Core §3.2 | As-of contract plus approved normalized volatility per timeframe. | L | Multi-timeframe volatility context. |
| `MTF-03` Cross-timeframe momentum spread | 🟡 Blocked by Missing Data Contract | As-of join and compatible normalized momentum definitions are absent. | Catalog §5.23; Core §3.2 | As-of contract and selected momentum outputs. | L | Multi-timeframe momentum context. |
| `MTF-04` Directional alignment vector | 🟡 Blocked by Future Market Context Dependency | Ordered vector/categorical agreement belongs to context and requires cross-timeframe evidence and ontology. | Catalog §5.23; Core Market Context | MTF contract and approved context vector semantics. | L | Context alignment summary. |
| `MTF-05` Alignment age/staleness descriptor | 🟡 Blocked by Missing Data Contract | No explicit primary cutoff/selected higher-timeframe value contract exists. | Catalog §5.23; Core §3.2 | As-of selection and availability-age provenance contract. | M | Context evidence quality. |

### 5.24 Market Regime

| Feature | Classification | Exact blocker / current state | Governing document | Missing prerequisite | Effort | Downstream dependencies |
| --- | --- | --- | --- | --- | ---: | --- |
| `REG-01` Continuous trend-strength input | 🟡 Intentionally Deferred | It would duplicate an upstream trend/ADX value; catalog says the dependency should normally be context metadata, not a new feature. | Catalog §§5.24, 10.2 | Select an existing registered input during context design. | S | Market Context trend summary. |
| `REG-02` Continuous volatility-state input | 🟡 Intentionally Deferred | It would duplicate a selected volatility-change dependency; none is yet approved. | Catalog §§5.24, 10.2 | Approve one upstream volatility-state feature and reference it in context. | S | Market Context volatility summary. |
| `REG-03` Joint trend-volatility-activity vector | 🟡 Blocked by Future Market Context Dependency | Combining registered dimensions creates a context component, not new information or a scalar feature. | Catalog §5.24; Core Market Context | Approved context input vector and complete activity feature. | M | Market Context classification. |
| `REG-04` Categorical market regime | 🟡 Blocked by Future Market Context Dependency | Point-in-time reference distribution, thresholds, ontology and update policy are absent; state belongs to Market Context. | Catalog §5.24; Core Market Context | Approved context/regime ontology and reference-snapshot policy. | L | Market Context state classification. |

## 6. Core Intelligence Feature-Ecosystem Reconciliation

The Core Intelligence Specification defines architectural families rather than
additional approved formulas. Each Core family maps as follows and therefore
has exactly one status:

| Core planned family | Classification | Reconciliation |
| --- | --- | --- |
| Candle geometry | ✅ Fully Implemented | Four registered Tier-A outputs. |
| True range | ✅ Fully Implemented | Registered Tier-A `true_range`. |
| Trend | 🟡 Blocked by Missing Quantitative Specification | EMA/SMA/ADX components exist, but planned slope, persistence, efficiency and distance features remain unapproved. |
| Momentum | 🟡 Blocked by Missing Quantitative Specification | RSI and MACD exist; planned returns, acceleration and persistence remain unapproved. |
| Volatility | 🟡 Blocked by Missing Quantitative Specification | ATR, standard deviation and Bollinger width exist; realized and relative volatility remain unapproved. |
| Volume | 🟡 Blocked by Missing Quantitative Specification | Candle volume exists as source evidence, but no registered provider-scoped activity feature is approved. |
| ATR | ✅ Fully Implemented | Approved arithmetic ATR-01. |
| VWAP | 🟡 Blocked by Missing Trade Data | True transaction-weighted evidence is unavailable. |
| Session | 🟡 Blocked by Missing Data Contract | Session ontology and timestamp input contract are absent. |
| Liquidity | 🟡 Blocked by Missing Data Contract | Quote/book evidence is unavailable; trade-flow evidence separately requires trades. |
| Market structure | 🟡 Blocked by Missing Market Structure Ontology | Non-repainting pivot/transition semantics are absent. |
| Support/resistance | 🟡 Blocked by Future Market Context Dependency | Versioned zone lifecycles belong to context after ontology approval. |
| Swing structure | 🟡 Blocked by Missing Market Structure Ontology | Pivot/confirmation identity is absent. |
| Higher-timeframe alignment | 🟡 Blocked by Missing Data Contract | Cross-timeframe as-of and shared-source provenance contract are absent. |
| Context features | 🟡 Blocked by Future Market Context Dependency | Context ontology and approved definition set do not yet exist. |

## 7. Remaining Feature Families

The remaining work falls into six dependency-ordered groups:

1. **Foundational candle transforms:** returns, gaps, selected price action,
   and provider-scoped volume/activity.
2. **Derived continuous evidence:** trend distance/slope/efficiency, realized
   and relative volatility, ATR extensions, range expansion, and selected
   statistical features.
3. **Non-repainting scalar boundaries:** prior channel width, prior boundary
   distance, and breakout displacement.
4. **Market Structure ontology:** confirmed swings, HH/HL/LH/LL semantics,
   BOS and related event availability.
5. **Architecture-gated evidence:** timestamp/session inputs and completed
   cross-timeframe as-of alignment.
6. **External-data evidence:** true VWAP, quoted spread, book depth and trade
   flow. These are not prerequisites for a candle-only first context version
   if their absence is represented honestly.

## 8. Remaining Technical Debt

Current production code has no identified correctness debt from this audit.
The remaining technical debt is architectural backlog rather than a defect:

- registry metadata cannot declare timestamp, categorical, event-object or
  cross-timeframe inputs;
- recursive provenance records predecessor outputs but does not expose every
  internal unpersisted smoothing state as a first-class value;
- the catalog and Core Specification predate later approved implementations,
  so their “current state” prose is stale even though their governance gates
  remain useful;
- catalog candidates mix single outputs, output families and lifecycle
  objects, making raw completion counts sensitive to granularity;
- semantic overlap remains unresolved among EMA spread/MACD, stochastic/range
  position, ATR shock/range expansion, z-score/Bollinger position, and several
  baseline-distance candidates; and
- no automated manifest currently links each catalog candidate to its
  approval, supersession, implementation or blocker artifact.

## 9. Remaining Governance Work

Before further feature implementation, governance must:

1. approve a small foundational tranche rather than the entire catalog;
2. freeze exact output identities, periods, lags, estimators, normalization,
   seeds, warm-up, tie/zero behavior and deterministic fixtures;
3. choose one semantic owner for every algebraic overlap;
4. approve a provider-scoped candle-volume specification;
5. approve strictly-prior boundary features suitable for non-repainting
   structure inputs;
6. create the Market Structure ontology with pivot and confirmation time,
   equality/tie rules, BOS/CHOCH semantics and lifecycle ownership;
7. decide whether timestamp/session and multi-timeframe contracts are required
   for the first Market Context release; and
8. define how unavailable liquidity is represented without fabricating OHLCV
   proxies as spread, depth or order flow.

## 10. Sufficiency for the Market Context Engine

**Decision: the current Feature Library is not yet sufficient to begin the
Market Context Engine implementation.**

It is sufficient for three major context dimensions:

- trend/trend-strength through EMA and Directional Movement;
- momentum through RSI and MACD; and
- volatility through True Range, ATR, standard deviation and Bollinger
  outputs.

It is insufficient for the complete object required by Core Intelligence:

- no approved volume/activity summary exists;
- no approved non-repainting Market Structure or swing ontology exists;
- support/resistance and breakout lifecycles are undefined;
- liquidity inputs are unavailable and their explicit unavailable-state
  behavior is not frozen;
- no context score or confidence mathematics is approved; and
- the context definition set, classification ontology and lifecycle contract
  are not approved.

Beginning implementation now would force the engine either to omit required
domains silently or invent classification thresholds and structural semantics.

## 11. Final Recommendation

### A. Continue Feature Library

Continue the Feature Library, but only through the smallest prerequisite
tranche needed for Market Context:

1. approve and implement one return primitive;
2. approve and implement relative candle volume plus, if justified, one
   complementary activity feature;
3. approve and implement one normalized volatility/expansion measure;
4. approve and implement strictly-prior upper/lower boundaries and breakout
   displacement; and
5. separately freeze the Market Structure ontology before implementing swings,
   HH/HL/LH/LL, BOS, CHOCH or zones.

This recommendation is preferable to beginning Market Context because it
closes the missing evidence dimensions without inventing the engine’s future
ontology. Trade, quote and order-book features may remain blocked; the first
context contract can explicitly represent liquidity as unavailable rather
than substituting misleading candle proxies.

After that narrow tranche and the Market Structure ontology are approved,
AlphaLens should reassess readiness and then begin the Market Context Engine.
