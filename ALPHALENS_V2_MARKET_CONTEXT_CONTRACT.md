# AlphaLens v2 Market Context Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Authority

This contract defines the immutable schema for descriptive market context. It
inherits numeric, availability, persistence, provenance, hashing, and
determinism rules from the Feature Architecture Standard. Context SHALL NOT
emit a decision, candidate, score, rank, confidence, or opportunity plan.

## 2. Context Snapshot

| Field | Requirement |
| --- | --- |
| `contract_version`, `context_id` | MUST identify the contract and immutable snapshot. |
| `instrument`, `primary_timeframe` | MUST identify the approved scope. |
| `context_timeframes` | MUST be ordered and independently available. |
| `evidence_cutoff`, `available_at` | MUST preserve point-in-time boundaries. |
| `definition_set` | MUST identify every context definition and version. |
| `trend`, `momentum`, `volatility` | MUST use the component schema below. |
| `structure`, `session` | MUST use the component schema or be explicitly unavailable. |
| `data_quality` | MUST always be present. |
| `limitations`, `evidence_references` | MUST be ordered and complete. |
| `configuration_hash`, `result_hash` | MUST cover canonical content. |

## 3. Context Component Schema

Every component SHALL contain `category`, `definition_id`,
`definition_version`, `status`, `observations`, `evidence_references`,
`available_at`, and `limitations`. `status` SHALL be exactly `AVAILABLE`,
`UNAVAILABLE`, or `NOT_APPLICABLE`. An available observation SHALL contain a
registered semantic identifier, typed value, unit or enum vocabulary, time
scope, optional price scope, and source feature/context references.

## 4. Context Categories

- **Trend** SHALL describe approved direction and strength observations without
  recommending action.
- **Momentum** SHALL describe approved oscillator or change observations.
- **Volatility** SHALL describe approved range, dispersion, expansion, or
  compression observations.
- **Structure** SHALL describe only events defined by an approved non-repainting
  structure ontology. It SHALL otherwise be `UNAVAILABLE`.
- **Session** SHALL describe only an approved UTC-based market/session ontology.
  It SHALL NOT assume equity-session semantics for continuous markets.
- **Data quality** SHALL report source completeness, freshness, continuity,
  validation, conflicts, and affected scope.

Category values SHALL come from versioned definition registries. Indicator
values SHALL be referenced, not recalculated.

## 5. Multi-Timeframe and Availability Rules

A higher-timeframe component MUST be complete and available before use. Shared
source candles MUST be declared. Agreement SHALL be descriptive confluence,
not confidence. Missing or conflicting timeframes SHALL remain visible and
SHALL NOT be forward-filled or retrospectively joined.

## 6. Missing Information

Missing mandatory context SHALL make the snapshot unavailable under the
consuming policy. Missing optional context SHALL remain an explicit
`UNAVAILABLE` component with a reason code; it SHALL NOT receive a neutral,
zero, inferred, or copied value. Data-quality failure SHALL NOT be hidden by a
context summary.

## 7. Immutability and Validation

Snapshots SHALL be append-only. New observations create a successor reference
and SHALL NOT mutate historical context. Validation MUST enforce registered
definitions, type/domain conformance, availability ordering, evidence
resolution, scope compatibility, deterministic collection ordering, hash
verification, prefix invariance, and future isolation.

## 8. Quantitative Definitions

This contract defines schemas only. Every categorical state, threshold,
geometry, session boundary, or aggregation rule requires a separately approved
quantitative definition. Absence of such a definition SHALL make that component
unavailable.
