# AlphaLens v2 Feature Catalog Proposal

## Status

**Status:** Candidate catalog for human review  
**Implementation status:** No feature calculations implemented  
**Scope:** BTC/USD `5m`, `10m`, and `15m` single-timeframe OHLCV evidence

Every entry below is a candidate, not an approved feature. Inclusion in this
proposal does not authorize implementation.

All lookbacks, smoothing periods, comparison windows, band multipliers,
thresholds, and recursive seed policies are intentionally unresolved. They
must be approved before a candidate becomes part of the versioned feature
registry.

## Notation

- `t` is the canonical candle-open timestamp.
- `D` is the approved timeframe duration.
- `W`, `W_fast`, `W_slow`, and `L` are unresolved positive
  observation-count parameters.
- A window ending at `t` contains only the completed candle at `t` and
  preceding candles.
- Every candidate is available no earlier than `t + D`, after candle `t` is
  complete.
- Warm-up is measured in consecutive observations, not wall-clock time.

## Candidate 1 — Lagged Log Return

| Attribute | Proposal |
| --- | --- |
| Name | Lagged Log Return |
| Purpose | Represent the magnitude and direction of price change over an approved prior observation lag. |
| Category | Price change |
| Inputs | Completed close at `t` and completed close at `t-L`. |
| Point-in-time availability | `t + D`; both closes are known by that boundary. |
| Warm-up requirement | `L + 1` consecutive candles. `L` is unresolved. |
| Dependencies | Validated close prices; deterministic logarithm and Decimal quantization policy. |
| Expected predictive hypothesis | Recent signed price change may contain information about short-horizon continuation or reversal conditional on other evidence. This is a hypothesis, not an established relationship. |
| Research rationale | Returns provide a scale-independent representation of price change and are a standard primitive for momentum, volatility, and regime research. |
| Computational complexity | `O(n)` time and `O(L)` bounded history for streaming evaluation. |
| Deterministic or derived | Deterministic; directly derived from two point-in-time close observations. |

## Candidate 2 — Candle Geometry

| Attribute | Proposal |
| --- | --- |
| Name | Candle Geometry |
| Purpose | Describe the completed candle’s body, total range, upper wick, and lower wick in scale-independent form. |
| Category | Price action |
| Inputs | Open, high, low, and close at `t`. |
| Point-in-time availability | `t + D`, when the full candle is complete. |
| Warm-up requirement | One completed candle. |
| Dependencies | Valid OHLC relationships; an approved zero-range handling rule before implementation. |
| Expected predictive hypothesis | The relative shape of a completed candle may distinguish directional conviction, rejection, and indecision states. |
| Research rationale | Candle geometry preserves within-interval price-location information that close-only features omit, without requiring future observations. |
| Computational complexity | `O(n)` time and `O(1)` state. |
| Deterministic or derived | Deterministic; multiple scalar outputs derived directly from the current completed OHLC candle. |

## Candidate 3 — Close Location Value

| Attribute | Proposal |
| --- | --- |
| Name | Close Location Value |
| Purpose | Express where the close lies within the completed candle’s high-low range. |
| Category | Price action |
| Inputs | High, low, and close at `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | One completed candle. |
| Dependencies | Valid high-low range; an approved zero-range handling rule. |
| Expected predictive hypothesis | Closes near an interval extreme may contain different continuation or reversal information from closes near the interval midpoint. |
| Research rationale | This is a normalized, price-scale-independent summary of intrabar closing pressure. |
| Computational complexity | `O(n)` time and `O(1)` state. |
| Deterministic or derived | Deterministic; directly derived from the current completed candle. |

## Candidate 4 — Rolling Price Position

| Attribute | Proposal |
| --- | --- |
| Name | Rolling Price Position |
| Purpose | Locate the current close within the trailing high-low envelope. |
| Category | Market structure |
| Inputs | Current close and trailing highs and lows through `t`. |
| Point-in-time availability | `t + D`; the window ends at `t` and contains no later candle. |
| Warm-up requirement | `W` consecutive candles. `W` is unresolved. |
| Dependencies | Approved lookback `W`; approved handling when the trailing range is zero. |
| Expected predictive hypothesis | Price near a trailing boundary may carry different opportunity information from price near the center of its recent range. |
| Research rationale | A normalized rolling position can describe consolidation, boundary pressure, and range location without assigning a BUY or SELL meaning. |
| Computational complexity | `O(n)` time with rolling extrema structures; `O(W)` state. |
| Deterministic or derived | Deterministic; derived from the current close and trailing OHLC evidence. |

## Candidate 5 — Simple Moving-Average Distance

| Attribute | Proposal |
| --- | --- |
| Name | Simple Moving-Average Distance |
| Purpose | Measure the current close’s normalized displacement from its trailing arithmetic mean. |
| Category | Trend |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | `W` consecutive candles. `W` is unresolved. |
| Dependencies | Approved lookback `W` and normalization definition. |
| Expected predictive hypothesis | The sign and magnitude of price displacement from a trailing mean may encode trend persistence or mean-reversion conditions. |
| Research rationale | Normalized distance is more comparable across price levels than the raw moving-average value. |
| Computational complexity | `O(n)` time with a rolling sum and `O(W)` state. |
| Deterministic or derived | Deterministic; derived from current price and a trailing close aggregate. |

## Candidate 6 — Simple Moving-Average Slope

| Attribute | Proposal |
| --- | --- |
| Name | Simple Moving-Average Slope |
| Purpose | Describe the direction and rate of change of a trailing arithmetic price mean. |
| Category | Trend |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | The approved moving-average window plus an approved slope-comparison lag; both are unresolved. |
| Dependencies | Approved average window, slope lag, and scale normalization. |
| Expected predictive hypothesis | The direction and magnitude of a smoothed price slope may differentiate trending from non-trending conditions. |
| Research rationale | Slope adds change information that a moving-average level or distance alone does not contain. |
| Computational complexity | `O(n)` time and bounded state determined by the approved windows. |
| Deterministic or derived | Deterministic composite; derived from trailing close aggregates without consuming another persisted feature. |

## Candidate 7 — Exponential Moving-Average Distance

| Attribute | Proposal |
| --- | --- |
| Name | Exponential Moving-Average Distance |
| Purpose | Measure current price displacement from a recursively weighted trailing mean. |
| Category | Trend |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | The complete approved seed period. The smoothing period and seed policy are unresolved. |
| Dependencies | Approved smoothing period, multiplier definition, seed method, and normalization. |
| Expected predictive hypothesis | A recency-weighted price baseline may respond to intraday trend changes differently from an equal-weighted mean. |
| Research rationale | This candidate tests whether more recent closes should receive greater influence while retaining deterministic state. |
| Computational complexity | `O(n)` time and `O(1)` recursive state after warm-up. |
| Deterministic or derived | Deterministic recursive derivation from closes under a fixed seed policy. |

## Candidate 8 — Fast/Slow Trend Spread

| Attribute | Proposal |
| --- | --- |
| Name | Fast/Slow Trend Spread |
| Purpose | Represent the normalized separation between two approved trailing price baselines. |
| Category | Trend |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | At least the complete slow-window or slow-seed requirement. `W_fast`, `W_slow`, baseline type, and seed policy are unresolved. |
| Dependencies | Approved fast and slow definitions with `W_fast < W_slow`; approved normalization. |
| Expected predictive hypothesis | Separation between faster and slower price baselines may describe trend direction and maturity. |
| Research rationale | Relative baseline separation is a continuous trend-state input and does not itself impose a regime threshold. |
| Computational complexity | `O(n)` time and bounded or constant state depending on the approved baseline type. |
| Deterministic or derived | Deterministic composite derived from the same point-in-time close prefix. |

## Candidate 9 — Moving-Average Convergence/Divergence Family

| Attribute | Proposal |
| --- | --- |
| Name | Moving-Average Convergence/Divergence Family |
| Purpose | Describe the difference between fast and slow recursive price baselines, its smoothed signal, and their divergence. |
| Category | Trend and momentum |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | Separate exact warm-ups for line and signal-derived outputs. All fast, slow, signal, and seed parameters are unresolved. |
| Dependencies | Approved recursive-baseline definitions, periods, seed rules, and output set. |
| Expected predictive hypothesis | Changes in fast/slow convergence and divergence may contain information about trend acceleration or deceleration. |
| Research rationale | The family provides related continuous trend and momentum summaries while requiring explicit per-output availability. |
| Computational complexity | `O(n)` time and `O(1)` recursive state after complete seeding. |
| Deterministic or derived | Deterministic recursive composite; all outputs derive from the same close prefix. |

## Candidate 10 — Relative Strength Index

| Attribute | Proposal |
| --- | --- |
| Name | Relative Strength Index |
| Purpose | Summarize the balance of recent positive and negative close changes on a bounded scale. |
| Category | Momentum |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | The approved change window plus its required initial candle. Period and recursive smoothing seed are unresolved. |
| Dependencies | Approved period, gain/loss smoothing rule, seed policy, and zero-loss behavior. |
| Expected predictive hypothesis | The balance of recent gains and losses may differentiate persistent momentum from locally extended movement. |
| Research rationale | A bounded momentum measure may complement unbounded return and trend-distance candidates. No overbought/oversold threshold is proposed. |
| Computational complexity | `O(n)` time and `O(1)` recursive state after warm-up. |
| Deterministic or derived | Deterministic recursive derivation from close changes. |

## Candidate 11 — Rate of Change

| Attribute | Proposal |
| --- | --- |
| Name | Rate of Change |
| Purpose | Express percentage price change over an approved trailing observation lag. |
| Category | Momentum |
| Inputs | Close at `t` and close at `t-L`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | `L + 1` consecutive candles. `L` is unresolved. |
| Dependencies | Approved lag `L` and Decimal ratio policy. |
| Expected predictive hypothesis | Price change over a defined lag may capture momentum at a scale distinct from candle-level geometry. |
| Research rationale | Rate of change is directly interpretable and provides an arithmetic alternative to log return; empirical redundancy must be assessed later rather than assumed. |
| Computational complexity | `O(n)` time and `O(L)` bounded history. |
| Deterministic or derived | Deterministic; derived from two completed closes. |

## Candidate 12 — True Range

| Attribute | Proposal |
| --- | --- |
| Name | True Range |
| Purpose | Measure completed-candle price range while accounting for displacement from the preceding close. |
| Category | Volatility |
| Inputs | High and low at `t`, plus close at `t-1`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | Two consecutive candles. |
| Dependencies | Valid current OHLC and preceding close. |
| Expected predictive hypothesis | Abrupt range expansion or inter-candle displacement may identify changing uncertainty and opportunity conditions. |
| Research rationale | True range retains information that high-low range alone omits and is a primitive for normalized volatility measures. |
| Computational complexity | `O(n)` time and `O(1)` state. |
| Deterministic or derived | Deterministic; directly derived from current OHLC and prior close. |

## Candidate 13 — Average True Range

| Attribute | Proposal |
| --- | --- |
| Name | Average True Range |
| Purpose | Estimate the recent scale of price movement from trailing true ranges. |
| Category | Volatility |
| Inputs | Current and historical high, low, and close observations through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | Complete approved true-range averaging and seed history. Window and smoothing policy are unresolved. |
| Dependencies | True-range definition; approved average type, window, and seed rule. |
| Expected predictive hypothesis | Recent range scale may distinguish environments in which price movement and forecast error distributions differ. |
| Research rationale | A range-based volatility measure can support scale normalization and descriptive volatility context without using future returns. |
| Computational complexity | `O(n)` time with `O(W)` rolling or `O(1)` recursive state, depending on the approved definition. |
| Deterministic or derived | Deterministic composite derived from point-in-time true-range evidence. |

## Candidate 14 — Rolling Realized Volatility

| Attribute | Proposal |
| --- | --- |
| Name | Rolling Realized Volatility |
| Purpose | Summarize dispersion of trailing close-to-close returns. |
| Category | Volatility |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | The approved return window plus the initial close required to form it. Window and estimator convention are unresolved. |
| Dependencies | Approved return definition, lookback, centering convention, degrees-of-freedom convention, and optional annualization policy. |
| Expected predictive hypothesis | Recent return dispersion may identify heteroscedastic conditions in which opportunity quality and uncertainty differ. |
| Research rationale | Financial return variance is time-varying; a trailing estimator offers a point-in-time continuous volatility input. |
| Computational complexity | `O(n)` time with rolling moments and `O(W)` state. |
| Deterministic or derived | Deterministic statistical derivation from trailing returns. |

## Candidate 15 — Bollinger Band Geometry

| Attribute | Proposal |
| --- | --- |
| Name | Bollinger Band Geometry |
| Purpose | Represent current price location relative to a trailing mean and dispersion envelope, together with relative envelope width. |
| Category | Volatility and price position |
| Inputs | Consecutive closes through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | `W` consecutive closes. Window, dispersion convention, and band multiplier are unresolved. |
| Dependencies | Approved center, dispersion estimator, multiplier, normalization, and zero-width handling. |
| Expected predictive hypothesis | Relative band position and width may distinguish compressed, expanded, extended, and mean-adjacent conditions. |
| Research rationale | Joint location and dispersion geometry can describe price state without imposing breakout or reversal thresholds. |
| Computational complexity | `O(n)` time with rolling moments and `O(W)` state. |
| Deterministic or derived | Deterministic composite derived from the trailing close distribution. |

## Candidate 16 — Volatility Term Ratio

| Attribute | Proposal |
| --- | --- |
| Name | Volatility Term Ratio |
| Purpose | Compare shorter-window and longer-window trailing volatility estimates. |
| Category | Volatility regime |
| Inputs | Consecutive closes or true ranges through `t`, according to the approved volatility basis. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | Complete slow-window history. `W_fast`, `W_slow`, and volatility basis are unresolved. |
| Dependencies | Two approved volatility definitions with `W_fast < W_slow`; approved zero-denominator handling. |
| Expected predictive hypothesis | Relative short-term volatility expansion or contraction may carry more regime information than a single absolute estimate. |
| Research rationale | A continuous ratio avoids predeclaring high/low regime thresholds while describing changes in volatility scale. |
| Computational complexity | `O(n)` time and bounded state determined by the approved estimators. |
| Deterministic or derived | Deterministic composite derived from two point-in-time volatility estimates. |

## Candidate 17 — Relative Volume

| Attribute | Proposal |
| --- | --- |
| Name | Relative Volume |
| Purpose | Compare the current completed candle’s volume with an approved trailing volume baseline. |
| Category | Volume |
| Inputs | Volume through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | `W` consecutive candles. Baseline window and average type are unresolved. |
| Dependencies | Approved baseline definition and zero-baseline handling. |
| Expected predictive hypothesis | Unusually high or low activity relative to recent observations may distinguish the evidentiary strength of price movement. |
| Research rationale | Raw volume is nonstationary in scale; relative volume provides local context without requiring trade-level data. |
| Computational complexity | `O(n)` time and bounded state determined by the approved baseline. |
| Deterministic or derived | Deterministic; derived from current volume and trailing volume observations. |

## Candidate 18 — Signed Volume Pressure

| Attribute | Proposal |
| --- | --- |
| Name | Signed Volume Pressure |
| Purpose | Summarize recent volume associated with positive, negative, and unchanged candle direction. |
| Category | Volume and directional pressure |
| Inputs | Open, close, and volume through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | `W` consecutive candles. Window, sign convention, and unchanged-candle treatment are unresolved. |
| Dependencies | Approved candle-direction convention, aggregation, and normalization. |
| Expected predictive hypothesis | The balance of volume accompanying positive and negative completed candles may provide context for directional persistence or exhaustion. |
| Research rationale | This is an OHLCV-only activity proxy; it must not be represented as true buyer/seller order flow. |
| Computational complexity | `O(n)` time with a rolling aggregate and `O(W)` state. |
| Deterministic or derived | Deterministic proxy derived from candle direction and volume; not direct trade-flow evidence. |

## Candidate 19 — Rolling Candle-Weighted Price

| Attribute | Proposal |
| --- | --- |
| Name | Rolling Candle-Weighted Price |
| Purpose | Estimate a trailing volume-weighted price reference from candle-level price and volume observations. |
| Category | Price and volume |
| Inputs | Approved representative candle price and volume through `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | `W` consecutive candles. Window and representative-price definition are unresolved. |
| Dependencies | Approved candle-price proxy, rolling window, and zero-total-volume handling. |
| Expected predictive hypothesis | Distance from a recent volume-weighted price reference may contain information distinct from distance from an equal-weighted mean. |
| Research rationale | The candidate incorporates observed candle volume but must be identified as a candle-level approximation, not exchange trade-level VWAP. |
| Computational complexity | `O(n)` time with rolling weighted sums and `O(W)` state. |
| Deterministic or derived | Deterministic OHLCV-derived approximation. |

## Candidate 20 — Price-Impact Proxy

| Attribute | Proposal |
| --- | --- |
| Name | Price-Impact Proxy |
| Purpose | Relate absolute price change to observed candle volume as a coarse OHLCV-only liquidity proxy. |
| Category | Liquidity proxy |
| Inputs | Consecutive closes and volume at `t`. |
| Point-in-time availability | `t + D`. |
| Warm-up requirement | At least two consecutive candles; any rolling normalization window is unresolved. |
| Dependencies | Approved return definition, volume denomination treatment, zero-volume handling, and optional normalization. |
| Expected predictive hypothesis | Larger price movement per unit of observed volume may identify conditions with different liquidity and error behavior. |
| Research rationale | The available Phase 2 dataset contains no order book or trade tape. This candidate is explicitly a proxy and cannot establish actual market depth or executable liquidity. |
| Computational complexity | `O(n)` time and `O(1)` state before any approved rolling normalization. |
| Deterministic or derived | Deterministic proxy derived from OHLCV; not direct liquidity evidence. |

## Candidate 21 — Prior Range Boundary Distance

| Attribute | Proposal |
| --- | --- |
| Name | Prior Range Boundary Distance |
| Purpose | Measure normalized distance from the current close to trailing support-like and resistance-like price boundaries. |
| Category | Market structure |
| Inputs | Current close and highs/lows strictly before `t` over an approved trailing window. |
| Point-in-time availability | `t + D`; reference boundaries exclude candle `t` and all future candles. |
| Warm-up requirement | `W` prior candles plus the current completed candle. `W` is unresolved. |
| Dependencies | Approved boundary definition, lookback, normalization, and tie handling. |
| Expected predictive hypothesis | Proximity to an established trailing boundary may distinguish range interaction from movement in unconstrained price space. |
| Research rationale | Excluding the current candle from boundary construction prevents the tested observation from defining its own prior reference level. |
| Computational complexity | `O(n)` time with rolling extrema structures and `O(W)` state. |
| Deterministic or derived | Deterministic; derived from current close and strictly prior OHLC evidence. |

## Candidate 22 — Breakout Displacement

| Attribute | Proposal |
| --- | --- |
| Name | Breakout Displacement |
| Purpose | Quantify how far the completed close lies beyond, at, or within a strictly prior trailing range boundary. |
| Category | Market structure and breakout context |
| Inputs | Current close and trailing highs/lows strictly before `t`. |
| Point-in-time availability | `t + D`; breakout status is not known until the current candle closes. |
| Warm-up requirement | `W` prior candles plus the current completed candle. `W` is unresolved. |
| Dependencies | Approved boundary window, displacement normalization, and equality convention. |
| Expected predictive hypothesis | The magnitude of a completed boundary displacement may distinguish failed tests, marginal breaks, and stronger range exits. |
| Research rationale | A continuous displacement avoids selecting a breakout threshold before research while preserving chart-annotation relevance. |
| Computational complexity | `O(n)` time with rolling extrema structures and `O(W)` state. |
| Deterministic or derived | Deterministic; derived from current close and strictly prior range evidence. |

## Candidate 23 — Time-of-Day Encoding

| Attribute | Proposal |
| --- | --- |
| Name | Time-of-Day Encoding |
| Purpose | Represent the candle’s UTC position within the 24-hour crypto trading day without an artificial discontinuity at midnight. |
| Category | Calendar context |
| Inputs | Canonical UTC candle timestamp. |
| Point-in-time availability | Known at candle open but, under the approved Phase 3 uniform feature contract, emitted no earlier than `t + D`. |
| Warm-up requirement | One completed candle. |
| Dependencies | Approved UTC basis and cyclical encoding convention. No exchange session assumption is permitted. |
| Expected predictive hypothesis | Intraday activity and volatility patterns may differ by time of day even in a continuously traded market. |
| Research rationale | A cyclical representation can test recurring UTC-time structure without imposing named geographic sessions. |
| Computational complexity | `O(n)` time and `O(1)` state. |
| Deterministic or derived | Deterministic calendar derivation from the canonical timestamp. |

## Candidate 24 — Day-of-Week Encoding

| Attribute | Proposal |
| --- | --- |
| Name | Day-of-Week Encoding |
| Purpose | Represent the candle’s UTC weekday cyclically. |
| Category | Calendar context |
| Inputs | Canonical UTC candle timestamp. |
| Point-in-time availability | Known at candle open but emitted no earlier than `t + D` under the uniform Phase 3 availability rule. |
| Warm-up requirement | One completed candle. |
| Dependencies | Approved UTC basis and cyclical encoding convention. |
| Expected predictive hypothesis | Market participation or volatility may vary across UTC weekdays, including weekends. |
| Research rationale | BTC/USD trades continuously across the week; an explicit cyclic encoding permits later evidence-based assessment of weekly structure. |
| Computational complexity | `O(n)` time and `O(1)` state. |
| Deterministic or derived | Deterministic calendar derivation from the canonical timestamp. |

## Parameters Requiring Approval

No value is proposed here for:

- return or comparison lags;
- rolling, fast, slow, or signal windows;
- smoothing multipliers;
- recursive seed methods;
- dispersion estimators or degrees-of-freedom conventions;
- volatility annualization;
- band multipliers;
- normalization denominators;
- zero-range, zero-volume, or zero-denominator behavior;
- support/resistance boundary definitions;
- breakout equality treatment;
- price proxies used by candle-weighted calculations;
- cyclical encoding conventions; or
- which candidates and outputs belong to the first approved registry.

These decisions must be fixed before implementation and versioned as part of
the approved feature definitions.

## Catalog Boundary

No candidate in this proposal:

- consumes another timeframe;
- uses an incomplete candle;
- uses future market data;
- defines a target or label;
- emits BUY, SELL, or WAIT;
- supplies calibrated confidence;
- claims causality;
- uses order-book, funding, trade-tape, on-chain, news, or external sentiment
  data that does not exist in the approved Phase 2 dataset; or
- authorizes feature selection based on observed model performance.

Approval of this proposal must explicitly identify the accepted candidates
and resolve their required quantitative parameters before any production
feature calculation is implemented.
