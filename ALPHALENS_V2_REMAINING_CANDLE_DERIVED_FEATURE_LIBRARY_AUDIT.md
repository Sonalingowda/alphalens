# AlphaLens v2 Remaining Candle-Derived Feature Library Audit

**Task:** Phase 2 — Complete Remaining Candle-Derived Feature Library

**Audit date:** 2026-08-01

**Governing architecture:** `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

## 1. Executive Summary

The complete repository inventory found no remaining feature family that
satisfies all three implementation gates in this task:

1. use only approved OHLCV candle evidence;
2. have a complete, explicitly approved quantitative definition; and
3. require no prohibited data source or future architecture contract.

Accordingly, the authorized implementation set is empty. No feature code,
registry entry, pipeline version, persistence behavior, provenance contract,
hashing behavior, or test expectation was changed.

This is a governance result, not an assertion that no additional formula could
be calculated from OHLCV. Many catalog candidates are mechanically
calculable, but the governing catalog explicitly identifies itself as a
candidate inventory, states that no candidate is approved, and prohibits
implementation until a later approval selects exact outputs and resolves every
quantitative gate. Choosing familiar periods, lags, thresholds, estimators,
seeds, zero rules, or identities would invent quantitative definitions.

## 2. Authorities Reviewed

The audit reviewed the entire feature implementation, registry, pipeline,
shared contracts, persistence and validation infrastructure, together with:

- `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`;
- `ALPHALENS_V2_PHASE_2_FEATURE_CATALOG.md`;
- `ALPHALENS_V2_CORE_INTELLIGENCE_SPECIFICATION.md`;
- every repository file matching an AlphaLens v2 quantitative or family
  specification;
- every completed feature-family architecture audit; and
- the currently registered intraday feature definitions and outputs.

The authority hierarchy is unambiguous. The Feature Architecture Standard
requires approved feature-specific mathematics before implementation and
requires implementation to remain blocked when any quantitative decision is
missing. The Phase 2 Feature Catalog says:

- its status is “Frozen for research review; no candidate is approved”;
- it does not approve a feature, formula, parameter, seed, threshold, registry
  declaration, pipeline version, research claim, or source expansion; and
- no catalog candidate may enter the registry until an explicit approval names
  it and resolves every quantitative gate.

Catalog formulas and proposed priorities are therefore research inputs, not
implementation authority.

## 3. Already Complete Approved Families

Every standalone approved quantitative specification found in the repository
maps to an already implemented and frozen family:

| Approved family | Registered implementation status |
| --- | --- |
| Candle Geometry and True Range | Complete |
| ATR-01 | Complete |
| EMA-12, EMA-20, EMA-26, EMA-50, EMA-100, EMA-200 | Complete |
| RSI-01 | Complete |
| MACD-01 line, signal, and histogram | Complete |
| SMA-20, Rolling Standard Deviation-20, and Bollinger family | Complete |
| Positive/Negative DM, Positive/Negative DI, DX, ADX, and ADXR | Complete |

The related specifications explicitly exclude unapproved periods, variants,
slopes, deltas, thresholds, interpretations, and other family members. Those
exclusions cannot be overridden by similarly named catalog candidates.

## 4. Remaining Family Gate Review

### 4.1 OHLCV-capable but quantitatively blocked families

These families can potentially be derived from approved candle fields, but no
remaining candidate has a complete approved mathematical identity.

| Family | Remaining catalog candidates | Blocking quantitative decisions |
| --- | --- | --- |
| Return and price transforms | `RET-01`–`RET-05` | Candidate selection; lag sets; deterministic Decimal logarithm; representative-price formula; denominator and semantic ownership; identities and versions. Even rows showing a simple example formula remain explicitly unapproved by the catalog. |
| Price action | `PA-01`–`PA-05` | Output selection; close-location and wick formulas; equality, doji, reset, cap, categorical ontology, sign, and zero-range/zero-wick behavior. Several outputs may duplicate registered candle geometry. |
| Trend | `TRD-01`–`TRD-05` | Windows, normalization scales, slope endpoints, OLS estimator, signed/unsigned efficiency, zero-path handling, and return-sign convention. Registered SMA-20 is a level dependency, not approval for the catalog’s normalized SMA-distance feature. |
| EMA extensions | `EMA-02`–`EMA-04` and the distance portion of catalog `EMA-01` | Lags, normalization, fast/slow semantic ownership, ribbon member set, and dispersion formula. The approved EMA family authorizes only six price-level averages. |
| Momentum | `MOM-01`–`MOM-04` | Return dependency choice, windows, lags, slope definitions, normalization, persistence convention, and zero-range/zero-return behavior. |
| RSI extensions | `RSI-02`, `RSI-03`; `RSI-04` is separately context-blocked | Delta lag, neutral reference, normalization, and distinct registry meaning. Approved RSI-01 authorizes one level output only. |
| MACD extensions | `MACD-04` and normalized catalog variants | Histogram-delta lag and normalization. Approved MACD-01 already owns the exact 12/26 line, 9-period signal, and histogram meanings; duplicate normalized identities are not approved. |
| Volatility | `VOL-01`–`VOL-05` | Return definition, windows, centering, divisor, annualization, semivolatility empty-side rule, deterministic logarithm/constants, fast/slow periods, and nested dispersion method. |
| ATR extensions | `ATR-02`–`ATR-04` | Price denominator, units, inclusive versus prior ATR boundary, zero denominator, lag, and change normalization. Approved ATR-01 authorizes only the bounded arithmetic range mean. |
| Bollinger extensions | `BB-04` and catalog variants outside the approved family | Change lag/rate convention and any alternate normalization. Percent B, width, middle, upper, and lower are already complete under the approved statistical-volatility specification. |
| Volume and activity | `VOLM-01`–`VOLM-05` | Baseline windows/types, zero-volume and zero-baseline behavior, dispersion estimator, signed-volume proxy ontology, doji/tie rules, OBV seed and bounded change window, concordance formula, output identities, and provider-scope semantics. Existing legacy volume code is reference-only. |
| Range expansion | `RNG-01`–`RNG-04` | Window, baseline, prior versus inclusive boundary, zero rules, semantic deduplication with ATR shock, threshold, reset, cap, lag, and difference/rate convention. |
| Simple market-structure scalars | `STR-01`–`STR-03` | Window, zero-range behavior, strictly-prior boundary, normalization, comparison horizon, equality policy, Boolean versus categorical outputs, and ontology. |
| Prior-boundary support/resistance scalars | `SR-01`, `SR-04` | Window, normalization, boundary definition, candle-weighted reference dependency, and semantic ownership versus trend/mean-reversion distance. |
| Simple breakout evidence | `BRK-01`, `BRK-02` | Approved boundary dependency, equality, normalization, range/volume dependency definitions, and whether the composite is persisted or assembled later. |
| Mean reversion | `MR-01`–`MR-04` | Window, center, dispersion divisor, zero-dispersion behavior, scale dependency, short/long lags, combination formula, AR estimator, admissibility, logarithm, and failure policy. |
| Statistical | `STAT-01`–`STAT-06` | Approved return primitive, windows, lags, moment/bias conventions, divisors, zero-variance rules, bins, deterministic logarithm, inclusive/prior rank boundary, and tie handling. |
| Self-relative strength | `REL-01`–`REL-03` | Short/long lags, combination and zero rules, benchmark semantic owner, and approved volume baselines. |

No item in this table can be made implementation-ready merely by selecting a
common market convention. Each missing choice changes the quantitative
identity and requires explicit approval.

### 4.2 Explicitly excluded source or semantic families

| Family | Candidates | Blocker |
| --- | --- | --- |
| Candle-weighted price and VWAP | `CWP-01`–`CWP-03`, `VWAP-01` | The task explicitly excludes VWAP. The catalog also withholds proxy formula, window/session boundary, normalization, and naming approval. True VWAP requires trade memberships. |
| Liquidity | `LIQ-01`–`LIQ-06` | The task explicitly excludes liquidity. Direct spread, depth, imbalance, and execution-quality meanings require quote, order-book, or trade evidence; OHLCV proxies lack approved definitions and must not be represented as direct liquidity. |
| Cross-asset relative strength | `REL-04` | Requires synchronized external market evidence and an as-of/normalization contract. |

### 4.3 Future architecture or Market Context blocked families

| Family | Candidates | Blocker |
| --- | --- | --- |
| Confirmed structure and swing events | `STR-04`, `STR-05` | Require non-repainting pivot spans, tie and confirmation rules, event availability, lifecycle ownership, and an approved context/event contract. |
| Support/resistance lifecycles | `SR-02`, `SR-03` | Require tolerance, touch, merge, confirmation, invalidation, expiry, and versioned-zone ontology; complex zones belong to Market Context unless separately approved. |
| Breakout lifecycles | `BRK-03`, `BRK-04` | Require later-candle retest/failure confirmation, tolerance, expiry and immutable event semantics; backdating would violate future isolation. |
| RSI divergence | `RSI-04` | Requires approved confirmed swings and a divergence ontology and is explicitly identified as better suited to Market Context. |
| Session | `SES-01`–`SES-03` | Requires an approved session/timezone/DST/calendar ontology and timestamp/categorical contract evolution. |
| Time | `TIME-01`–`TIME-04` | Requires approved timestamp input metadata plus deterministic trigonometric or categorical encoding, calendar version, and boundary policy. Timestamp is not an OHLCV value under the current feature-input contract. |
| Multi-timeframe context | `MTF-01`–`MTF-05` | Requires an approved completed-as-of join, cross-timeframe availability, shared-source provenance, scaling, and registry/pipeline contract. |
| Market regime | `REG-01`–`REG-04` | Continuous entries duplicate upstream features; vectors and categorical states belong to Market Context and require an approved ontology, point-in-time reference distribution, and thresholds. The task explicitly prohibits Market Context. |

## 5. Dependency-Order Result

There is no valid dependency order to execute because the implementation-ready
set contains zero definitions. Potential upstream candidates such as returns,
volume baselines, prior boundaries, and timestamp encodings are themselves
unapproved. Consequently, none of their downstream volatility, momentum,
breakout, statistical, relative-strength, or regime candidates can become
eligible through existing dependencies.

The current registry and pipeline remain the canonical completed order. No
anonymous calculation, hidden dependency, duplicate semantic output, or
provisional registry identity was introduced.

## 6. Architecture Audit

| Requirement | Result | Evidence |
| --- | --- | --- |
| Dependency reuse | Pass | No unapproved calculation was added; all currently approved families continue to use their registered dependency graph. |
| Registry ordering | Pass | Registry is unchanged because no remaining definition passed governance. |
| Pipeline ordering | Pass | Pipeline version and execution order are unchanged. |
| Provenance completeness | Pass | No new value exists without a complete approved provenance contract. Existing provenance behavior is unchanged. |
| Deterministic hashes | Pass | Registry and pipeline canonical payloads are unchanged; repeatability remains covered by the existing suite. |
| Feature-family reuse | Pass | Related implemented outputs were not re-registered under catalog aliases. |
| Zero duplicated mathematics | Pass | No formula was added; catalog overlaps such as EMA spread/MACD, stochastic/range position, ATR shock/range expansion, and Bollinger/z-score remain unresolved rather than duplicated. |
| Scope boundary | Pass | No VWAP, liquidity, order-book, trade, execution-quality, Market Context, opportunity, explainability, or AI functionality was added. |

## 7. Validation

Because the governance review authorized no implementation, no new focused
family test was required. The existing focused feature regressions and full
backend suite remain the appropriate proof that the frozen implementation was
not changed.

Validation results:

- Ruff static analysis: passed;
- Python compilation of the backend application and tests: passed;
- existing focused feature, registry, and pipeline tests: 126 passed;
- complete backend suite: 348 passed; and
- `git diff --check`: passed.

## 8. Required Approval Sequence

To unblock any remaining candle-derived family, a future request must:

1. name the exact candidate identifiers and outputs;
2. create and explicitly approve a quantitative specification that resolves
   every formula, period, lag, seed, boundary, estimator, normalization, tie,
   zero, warm-up, domain, identity, version, dependency, and edge case;
3. resolve semantic overlap with already registered outputs;
4. approve any required timestamp, categorical, event, or cross-timeframe
   architecture extension; and
5. authorize that smallest dependency-ordered tranche for implementation.

Market Context, lifecycle-bearing structure, external data, VWAP, and
liquidity must remain separate approvals.

## 9. Final Decision

No remaining candle-derived feature family is currently implementation-ready.
The repository is compliant as-is, and the correct completion of this task is
to record the blockers without modifying production behavior. Phase 2 feature
implementation stops here pending new quantitative approvals. Work does not
continue to Market Context.
