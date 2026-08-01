# AlphaLens v2 Quantitative Evidence Ontology Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; not approved production policy

## 1. Scope

This document supplies mathematical meaning for the frozen Evidence Taxonomy
without changing its identifiers or storage contract. An evidence item is a
typed observation-policy-proposition relation, not a claim of causality,
predictive ability, confidence, or economic value.

## 2. Evidence Algebra and Symbols

An item is

\[
e=(i,c,x,u,\rho,\sigma,\phi,[t_0,t_1],a,z,\ell),
\]

where (i) is identity, (c) category, (x) typed value, (u) unit,
(\rho\in\{+,-,0\}) polarity relative to proposition (\phi), (\sigma) an
approved severity label, ([t_0,t_1]) observation interval, (a) availability,
(z) source/provenance, and (\ell) limitations. Evidence packages are finite
ordered multisets; two records with the same numeric value but different source,
scope, time, or proposition are not interchangeable.

Dependence relation (e_i\prec e_j) means (e_j) is derived from or evaluated
using (e_i). The transitive graph SHALL be acyclic. Contradiction is a
proposition-relative relation (e_i\bowtie_\phi e_j), not merely opposite
numeric signs. Redundancy and dependence SHALL be retained for calibration;
correlated evidence SHALL NOT be counted as independent by default.

## 3. Canonical Evidence Classes

| Identifier | Mathematical meaning and source | Dependencies and limitations | Possible contradiction |
| --- | --- | --- | --- |
| `MARKET_PRICE` | Completed (O,H,L,C) observation from a canonical candle. | Venue/source, aggregation, completion, and availability; no executable-price claim. | Another valid source conflict or proposition-relative adverse price relation. |
| `MARKET_VOLUME` | Completed candle volume (V_t). | Aggregation and venue coverage; not trade direction, depth, or liquidity. | Source conflict or proposition-relative volume condition. |
| `FEATURE_TREND` | Registered EMA or directional-movement value. | Candle inputs, warm-up, definition version; indicator is descriptive. | Another trend observation under an approved proposition rule. |
| `FEATURE_MOMENTUM` | Registered RSI or MACD-family value. | Feature dependencies and warm-up; no forecast semantics. | Opposed momentum relation defined by policy. |
| `FEATURE_VOLATILITY` | Registered ATR, rolling dispersion, or Bollinger value. | Window, scale, price denominator; volatility has no direction. | Conflicting scale/window observation, not an automatic directional contradiction. |
| `FEATURE_VOLUME` | Registered candle-volume-derived feature. | OHLCV only; cannot establish spread, depth, or impact. | Opposed volume condition or source conflict. |
| `CONTEXT_TREND` | Output (g_T(T;\theta_T)) of an approved context definition. | Depends on trend evidence and policy; category boundaries need calibration. | Incompatible context state at same scope/cutoff. |
| `CONTEXT_MOMENTUM` | Output (g_M(M;\theta_M)). | Depends on momentum evidence and policy. | Incompatible momentum context under the same definition. |
| `CONTEXT_VOLATILITY` | Output (g_V(V;\theta_V)). | Population/reference dependence. | Incompatible volatility context under the same definition. |
| `CONTEXT_STRUCTURE` | Causally confirmed structure state/event. | Requires approved non-repainting ontology and confirmation time. | Opposing valid structure event not superseded by chronology. |
| `CONTEXT_SESSION` | UTC/calendar state under approved boundary set. | Venue/calendar applicability; no universal session effect. | Boundary or calendar conflict. |
| `DATA_QUALITY` | Typed validity, completeness, freshness, continuity, or conflict result. | Depends on validation artifacts; not a scalar quality score. | A later correction may supersede, never rewrite, prior evidence. |
| `POLICY_TRACE` | Predicate or gate result (p_j\in\{1,0,\bot\}). | Requires approved policy/version and all referenced inputs. | Another trace under the same policy/input identity with different result is an integrity conflict. |
| `FORECAST` | Output of a separately approved inference artifact. | No forecast is approved by this research library; probability/confidence semantics absent. | Competing artifact output only under a declared comparison. |
| `RISK_CONTEXT` | Opportunity-independent risk observation. | Requires separate risk definition; SHALL NOT imply position sizing. | Opposed or invalidating risk evidence under policy. |
| `PLAN_VALUE` | Approved entry, invalidation, target, risk, or reward quantity. | Depends on complete plan policy; absent rather than partial. | Plan-level structural inconsistency or newer superseding plan. |
| `CALIBRATION` | Immutable evidence supporting an authorized calibrated quantity. | Requires estimand, population, sample, method, validation, and approval. | Calibration drift, scope mismatch, or failed adequacy test. |
| `LIFECYCLE` | State-transition, freshness, continuation, or supersession fact. | Depends on prior event and approved transition policy. | Competing current head or illegal transition. |
| `LIMITATION` | Typed boundary on interpretation or use. | Must identify affected evidence/proposition. | It qualifies other evidence; it is not erased by support. |

Every class preserves source identity, definition/version, scope, event time,
availability, cutoff compatibility, configuration/code identity, and integrity
digest. These fields constitute canonical provenance.

## 4. Interactions

For a proposition (\phi), let (E_\phi^+,E_\phi^-,E_\phi^0) be polarity
partitions. A future policy may define a vector functional

\[
F_\phi(E)=(f_1(E),\ldots,f_m(E)),
\]

provided each (f_j) is traceable, unit-valid, deterministic, and explicit
about dependence and missingness. No scalarization, weight, severity ordering,
or cancellation rule is approved here. Disqualifying severity is valid only
when an approved policy assigns it.

Evidence from different timeframes SHALL retain timeframe identity. Evidence
available after the cutoff is outside the admissible set. Missing evidence is
not neutral evidence; it is an availability state.

## 5. Assumptions

- `EV-A01`: source definitions and hashes uniquely identify semantic content.
- `EV-A02`: polarity is always relative to a declared proposition.
- `EV-A03`: dependence among indicators is material and must be measured.
- `EV-A04`: evidence count is not evidence strength.
- `EV-A05`: observed association is not causation.

## 6. Validation and Future Calibration

Validation SHALL check taxonomy identity, type/unit/domain, source resolution,
acyclic lineage, scope, chronology, proposition, policy authority, limitations,
and digest. Phase 5B SHALL study redundancy, conditional dependence, stability,
missingness, contradiction frequency, source conflicts, and population drift.
No evidence importance or polarity rule becomes operational without separate
approval.
