# AlphaLens v2 Opportunity Scoring Framework

**Framework version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Boundary

This framework defines the architecture for a future deterministic opportunity
score. It approves no estimand, component, normalization, weight, range, or
threshold. A score SHALL order or describe opportunity quality only as defined
by an approved scoring policy. It SHALL NOT be confidence, probability,
expected return, risk/reward, or a decision.

## 2. Component Model

Each `ScoreComponent` MUST contain component identifier/version, semantic
meaning, source evidence, input domain, raw value, normalization reference,
normalized value when approved, weight reference when approved, contribution,
availability status, limitations, and component hash. Components SHALL be
stored individually; an opaque aggregate alone is prohibited.

A `ScoreResult` MUST contain score-policy identity/version/hash, opportunity and
qualification references, ordered components, aggregation definition,
aggregate value and unit, valid domain, precision metadata, missing-input
disposition, evidence cutoff, availability, configuration/result hashes, and
code identity.

## 3. Weight Interface

A weight set MUST be an immutable approved artifact specifying population
scope, ordered component-to-weight mappings, units, constraints, derivation
method, effective version, and integrity digest. Implementations SHALL reject
unknown, duplicate, negative, non-finite, out-of-scope, or structurally invalid
weights unless the approved policy explicitly permits their domain. No default
equal weights MAY be inferred.

## 4. Normalization Interface

A normalization artifact MUST identify its transform, input domain, output
domain, fitted or fixed parameters, population, point-in-time reference data,
freeze time, missing/out-of-range behavior, version, and digest. Runtime SHALL
NOT refit normalization from the current ranking population unless an approved
policy explicitly defines that point-in-time operation.

## 5. Precision

Quantitative scoring inputs, intermediates, and outputs MUST use finite exact
`Decimal` arithmetic. Computation SHALL use an isolated context of at least 50
significant digits. Canonical emitted values SHALL be quantized to
`0.000000000000000001` with `ROUND_HALF_EVEN`, unless a future repository-wide
successor standard explicitly changes this rule. Binary floating point SHALL
NOT enter canonical scoring, serialization, hashing, or persistence.

## 6. Missing Inputs

Every component SHALL declare `MANDATORY` or `OPTIONAL` in the scoring policy.
Missing mandatory input MUST make scoring unavailable. Optional absence SHALL
follow an approved policy rule such as omission or renormalization; no rule is
implied by this framework. Zero substitution, last-value carry-forward, and
silent reweighting are prohibited.

## 7. Aggregation and Extensibility

Aggregation SHALL be a versioned policy interface receiving the complete
ordered component set and producing a typed aggregate plus trace. New
components MAY be added only through a new scoring-policy version. Consumers
MUST preserve unknown components but SHALL NOT evaluate them without support.

## 8. Tie-Breaking Interface

The scoring policy MUST declare whether equal canonical scores are possible.
Tie resolution belongs to the Ranking Contract and MUST reference a complete,
approved, stable key. Score implementations SHALL NOT add hidden precision or
unrounded values to break ties.

## 9. Validation and Versioning

Validation MUST verify policy approval, component completeness, domains,
normalization scope, weight scope, exact arithmetic, chronology, evidence
integrity, deterministic ordering, aggregate reconstruction, and hashes.
Changed meaning, inputs, normalization, weights, aggregation, precision, or
missing-input behavior requires a new semantic policy version. Historical
results SHALL remain immutable.

## 10. Calibration Workflow

Before activation, quantitative research MUST preregister the opportunity-
quality estimand, population, components, normalization, weights, aggregation,
validation measures, chronological partitions, adequacy criteria, acceptance
criteria, and protected evaluation protocol. Approval MUST occur through an
immutable research artifact. Scoring calibration SHALL NOT authorize or be
presented as confidence calibration.
