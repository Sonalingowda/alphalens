# AlphaLens v2 Opportunity Detection Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Status and Authority

This contract defines the canonical boundary between validated market state and
opportunity assessment. It SHALL be subordinate to the Research Constitution,
Product Contract, Decision Contract, Confidence Policy, Feature Architecture
Standard, and Core Intelligence Specification. It defines no quantitative
threshold.

## 2. Canonical Definitions

An **opportunity candidate** is an immutable record that an approved detection
policy found a market state eligible for assessment. Detection SHALL NOT assert
quality, confidence, rank, profitability, or user action.

`BUY`, `SELL`, and `WAIT` SHALL retain their meanings from the Decision Contract:

- `BUY` is a qualifying upward opportunity assessment.
- `SELL` is a qualifying downward opportunity assessment and SHALL NOT mean exit.
- `WAIT` is a completed valid assessment that abstains.

Detection precedes assessment. A candidate SHALL NOT itself contain one of
these stances. Operational failure SHALL NOT produce `WAIT`.

## 3. Candidate Schema

| Field | Requirement |
| --- | --- |
| `contract_version` | MUST identify this contract version. |
| `candidate_id` | MUST be a stable identity derived under the active identity policy. |
| `instrument`, `timeframe` | MUST identify an approved scope. |
| `evidence_cutoff` | MUST bound every consumed input. |
| `detected_at` | MUST be no earlier than the latest input availability. |
| `detection_policy` | MUST contain approved identifier, version, and digest. |
| `market_snapshot_reference` | MUST resolve to immutable validated candle evidence. |
| `feature_snapshot_reference` | MUST resolve to a compatible immutable feature run. |
| `context_reference` | MAY be present only when required by the policy and valid. |
| `reason_codes` | MUST be non-empty, ordered taxonomy identifiers. |
| `evidence_references` | MUST be non-empty, ordered, immutable references. |
| `limitations` | MUST disclose every material known limitation. |
| `configuration_hash`, `result_hash` | MUST verify canonical configuration and result content. |

## 4. Detection Prerequisites

Before evaluation, the detector MUST verify approved scope, completed candles,
source integrity, feature compatibility, point-in-time availability, required
history, policy approval, policy hash, configuration hash, and deterministic
input ordering. Context SHALL be mandatory only when the active policy declares
it mandatory.

## 5. Required Evidence

Every candidate MUST reference the canonical market snapshot, every consumed
feature or context artifact, input availability, validation result, and active
policy. An evidence item unavailable at the cutoff SHALL NOT be consumed.

## 6. Evaluation and Rejection

Evaluation SHALL occur in this order:

1. validate policy and scope;
2. validate source snapshot and cutoff;
3. resolve declared dependencies in registry order;
4. validate availability and compatibility;
5. evaluate policy predicates in declared order;
6. assemble reasons and limitations;
7. validate and hash the candidate;
8. persist atomically.

The detector MUST reject evaluation on missing mandatory input, corrupt or
unverifiable evidence, incomplete candle, stale input under the active freshness
policy, undeclared dependency, version mismatch, chronology violation,
duplicate identity conflict, or policy ambiguity. A rejection SHALL create an
auditable attempt record, not a candidate or decision.

Optional missing input SHALL be handled only as declared by the detection
policy. An undeclared missing-input rule SHALL fail closed.

## 7. Detection States

An attempt SHALL transition only from `RECEIVED` to `VALIDATING`, then to
`DETECTED`, `NOT_DETECTED`, or `UNAVAILABLE`. `DETECTED` SHALL create one
candidate. `NOT_DETECTED` SHALL mean valid policy evaluation found no eligible
state. `UNAVAILABLE` SHALL mean evaluation could not complete. These states
SHALL NOT be rewritten.

## 8. Validation and Determinism

The same policy, configuration, code identity, and point-in-time evidence MUST
produce identical semantic content and hashes. Prefix extension SHALL NOT
change prior results. Duplicate attempts with identical identity and content
MAY resolve idempotently; conflicting content for the same identity MUST fail.

## 9. Quantitative Extension Point

Each production detector SHALL reference a separately approved quantitative
detection policy defining its eligible population, predicates, parameters,
missing-input rules, freshness needs, and reason-code mapping. No implementation
MAY infer these values from examples, indicators, model outputs, or protected
evaluation data.
