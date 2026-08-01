# AlphaLens v2 Opportunity Plan Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Boundary

An Opportunity Plan is optional, informational decision-support context for a
canonical `BUY` or `SELL` assessment. It SHALL NOT be an order, instruction,
guarantee, position-sizing recommendation, or portfolio rule. It MUST be absent
for `WAIT` and whenever any required quantitative policy or evidence is
unavailable.

This contract specializes, but SHALL NOT weaken, the atomic opportunity-plan
record in the Decision Contract.

## 2. Canonical Schema

| Field | Requirement |
| --- | --- |
| `contract_version`, `plan_id` | MUST identify the immutable plan. |
| `opportunity_id`, `assessment_id`, `decision_id` | MUST link canonical source objects. |
| `policy_reference` | MUST identify one approved plan definition/version/hash. |
| `instrument`, `timeframe`, `direction` | MUST match the decision. |
| `reference_price` | MUST identify value, source, event time, and availability. |
| `entry_zone` | MUST contain inclusive lower/upper Decimal bounds and semantics identifier. |
| `invalidation` | MUST contain one informational price level, condition identifier, and evidence. |
| `targets` | MUST be a non-empty ordered collection of target identifiers, prices, and evidence. |
| `risk` | MUST contain policy-defined price-distance quantity and unit. |
| `potential_rewards` | MUST correspond one-to-one with ordered targets. |
| `risk_reward` | MUST contain dimensionless ratios corresponding one-to-one with targets. |
| `assumptions`, `limitations` | MUST be ordered, evidence-backed disclosures. |
| `evidence_cutoff`, `available_at`, `valid_until` | MUST preserve availability and optional validity. |
| `evidence_references`, `configuration_hash`, `result_hash` | MUST make the plan reproducible. |

## 3. Structural Invariants

Entry lower MUST NOT exceed entry upper. For `BUY`, invalidation MUST be below
the entry zone and targets above it. For `SELL`, invalidation MUST be above the
entry zone and targets below it. Risk and every potential reward and ratio MUST
be positive. Target, reward, and ratio collections MUST have equal lengths and
stable ordering.

These invariants validate a policy result; they do not define how levels are
chosen.

## 4. Required Quantitative Inputs

The active policy MUST declare reference-price selection, entry-zone
construction, invalidation condition, target construction and ordering, risk
distance, reward distance, ratio convention, precision/rounding, validity,
missing-input behavior, and direction handling. Every consumed candle, feature,
context object, and parameter MUST be referenced in the plan evidence.

## 5. Atomicity and Missing Evidence

The plan is atomic. If any required level, ratio, assumption, policy reference,
or evidence item is invalid or unavailable, the entire plan field MUST be
absent. Partial plans, placeholder targets, inferred stops, zero risk, and
carried-forward plans are prohibited.

## 6. Immutability and Lifecycle

Plans SHALL be append-only. New evidence creates a new plan and opportunity
revision. Expiration or invalidation SHALL create lifecycle evidence and SHALL
NOT mutate the plan. A plan event SHALL NOT assert that the user entered,
exited, stopped, or realized a target.

## 7. Validation

Validation MUST enforce policy approval, scope/direction consistency,
structural invariants, exact Decimal arithmetic, point-in-time evidence,
availability, complete provenance, deterministic ordering, and hash stability.
