# AlphaLens v2 Evidence Taxonomy

**Taxonomy version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Authority

This taxonomy is the canonical ontology for evidence used by detection,
assessment, qualification, scoring, ranking, notification, and explanation. It
defines evidence representation, not indicator interpretation or thresholds.

## 2. Evidence Item Schema

Every evidence item MUST contain:

| Field | Requirement |
| --- | --- |
| `taxonomy_version`, `evidence_id`, `evidence_type` | MUST provide stable identity and meaning. |
| `category` | MUST use a category defined below. |
| `description_code` | MUST resolve to an approved factual description template. |
| `source_reference` | MUST identify the immutable source artifact. |
| `source_definition` | MUST identify source definition/version. |
| `polarity` | MUST be `SUPPORTING`, `CONTRADICTING`, or `CONTEXTUAL` relative to a declared proposition. |
| `proposition` | MUST identify the policy proposition being evaluated. |
| `severity` | MUST be `INFORMATIONAL`, `MATERIAL`, or `DISQUALIFYING` only when assigned by an approved policy. |
| `observed_value` | MUST preserve typed source value and unit without reinterpretation. |
| `evidence_cutoff`, `available_at` | MUST establish point-in-time usability. |
| `scope` | MUST identify instrument, timeframe, and applicable time/price scope. |
| `provenance` | MUST include lineage, code, configuration, run, and integrity references. |
| `limitations` | MUST disclose material constraints. |
| `integrity_digest` | MUST hash canonical stored content. |

Polarity and severity are relational policy outputs. The same observation MAY
have different polarity under different propositions, but each relationship
MUST be stored as a distinct evidence item or immutable policy-evaluation link.

## 3. Canonical Categories

| Identifier | Category | Canonical source |
| --- | --- | --- |
| `MARKET_PRICE` | Completed OHLC market evidence | Canonical candle snapshot |
| `MARKET_VOLUME` | Candle-level volume evidence | Canonical candle snapshot |
| `FEATURE_TREND` | Registered trend feature value | Feature run |
| `FEATURE_MOMENTUM` | Registered momentum feature value | Feature run |
| `FEATURE_VOLATILITY` | Registered volatility feature value | Feature run |
| `FEATURE_VOLUME` | Registered candle-volume feature value | Feature run |
| `CONTEXT_TREND` | Approved descriptive trend context | Context snapshot |
| `CONTEXT_MOMENTUM` | Approved descriptive momentum context | Context snapshot |
| `CONTEXT_VOLATILITY` | Approved descriptive volatility context | Context snapshot |
| `CONTEXT_STRUCTURE` | Approved non-repainting structure context | Context snapshot |
| `CONTEXT_SESSION` | Approved session context | Context snapshot |
| `DATA_QUALITY` | Completeness, freshness, validation, conflict evidence | Validation artifact |
| `POLICY_TRACE` | Deterministic predicate/gate outcome | Approved policy evaluation |
| `FORECAST` | Approved runtime artifact output | Inference artifact/run |
| `RISK_CONTEXT` | Opportunity-independent risk observation | Risk assessment artifact |
| `PLAN_VALUE` | Approved informational plan value | Plan policy evaluation |
| `CALIBRATION` | Approved confidence evidence | Calibration artifact |
| `LIFECYCLE` | Freshness, transition, or supersession evidence | Lifecycle event |
| `LIMITATION` | Known interpretive limitation | Governing artifact |

Trade, quote, order-book, liquidity, causal, or probability evidence SHALL NOT
use these identifiers unless a future data contract and taxonomy version
explicitly add them.

## 4. Storage and Ordering

Evidence SHALL be stored as immutable structured records with typed scalar or
structured values, ordered references, canonical timestamps, policy links, and
digests. Narrative text SHALL be a deterministic projection, never the source
of truth. Collections SHALL order by category registry order, proposition,
source availability, source identity, and evidence identity unless a consuming
approved policy declares a different complete key.

## 5. Validation and Evolution

An item MUST fail validation when its type is unknown, source is unresolved,
scope mismatches, availability exceeds the cutoff, polarity lacks a proposition,
severity lacks policy authority, or digest fails. Existing identifiers and
meanings SHALL be immutable. New categories require a new compatible taxonomy
version; changed meaning requires an incompatible version.
