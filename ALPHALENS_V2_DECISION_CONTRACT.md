# AlphaLens v2 Decision Contract

## Status and Authority

This document is the Task 2 deliverable for Phase 1, “Scope freeze and
contract alignment,” in `IMPLEMENTATION_ORDER.md`.

It defines the canonical meaning and information content of an AlphaLens v2
decision. It is intentionally technology-agnostic. It does not prescribe a
model, heuristic, algorithm, service, transport, storage mechanism, or
presentation.

The contract is the shared domain interface for all future AlphaLens
subsystems, including research, decision production, opportunity scanning,
prediction delivery, chart annotation, and presentation. Every subsystem must
preserve these semantics and must not reinterpret the decision locally.

This document defines what a decision is. It does not define how a decision is
produced.

## Governing Contracts

This contract is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_MIGRATION_PLAN.md`;
- `COMPONENT_AUDIT.md`; and
- `TARGET_ARCHITECTURE.md`.

Where quantitative meaning is not yet approved, this contract requires an
explicit policy reference rather than inventing a definition.

## Canonical Definition

An AlphaLens decision is an immutable, point-in-time, explainable assessment
of one supported market and timeframe. It records exactly one of:

- `BUY`;
- `SELL`; or
- `WAIT`.

A decision describes the opportunity supported by evidence available at a
specific cutoff. It is not an order, execution instruction, portfolio action,
or guarantee of an outcome.

The decision remains a historical statement about what AlphaLens concluded
from the recorded evidence at that point in time. Later evidence cannot alter
it. A correction or replacement must be represented by a new decision that
explicitly refers to the decision it supersedes.

## Decision Semantics

### `BUY`

`BUY` means the approved decision policy identified a qualifying upward
opportunity for the specified instrument and timeframe using only evidence
available by the recorded evidence cutoff.

It does not mean:

- that an order was or should automatically be placed;
- that price will rise;
- that the opportunity is profitable after costs;
- that a confidence value exists; or
- that an entry, stop-loss, or take-profit is available unless those optional
  fields are present.

### `SELL`

`SELL` means the approved decision policy identified a qualifying downward
opportunity for the specified instrument and timeframe using only evidence
available by the recorded evidence cutoff.

It does not mean:

- close or exit an existing position;
- place a short-sale order;
- that price will fall;
- that the opportunity is profitable after costs;
- that a confidence value exists; or
- that an entry, stop-loss, or take-profit is available unless those optional
  fields are present.

`SELL` always describes directional opportunity. It must never be reused as a
portfolio-management or order-lifecycle command.

### `WAIT`

`WAIT` means a valid evaluation occurred but neither `BUY` nor `SELL` was
supported under the referenced decision policy at the evidence cutoff.

`WAIT` is:

- a complete decision;
- an intentional abstention;
- eligible for the same provenance and explanation standards as `BUY` and
  `SELL`; and
- distinct from missing data, a failed evaluation, an unavailable system, or
  the absence of a decision.

An operational failure must never be represented as `WAIT`. If a valid
evaluation cannot be completed under the referenced policy, no decision exists
for that evaluation attempt.

## Source-of-Truth Hierarchy

The following authority order applies to every decision:

1. `RESEARCH_CONSTITUTION.md` governs evidence integrity, chronology,
   reproducibility, and prohibited practices.
2. `ALPHALENS_V2_PRODUCT_CONTRACT.md` governs product scope and the exclusive
   `BUY` / `SELL` / `WAIT` vocabulary.
3. This document governs the canonical decision structure and semantics.
4. The referenced approved decision policy governs the quantitative conditions
   that distinguish `BUY`, `SELL`, and `WAIT`.
5. Referenced evidence artifacts are the source of truth for the observations
   used in the evaluation.
6. A separately approved confidence policy and its evidence are the only
   authority for an optional confidence value.

No consuming subsystem becomes the source of truth merely by transforming,
transmitting, storing, ranking, or displaying a decision.

## Canonical Decision Object

The canonical object contains the following top-level fields. Logical types
describe information content, not a programming language or serialization
format.

### Field summary

| Field | Logical type | Required |
| --- | --- | --- |
| `contract_version` | Version identifier | Yes |
| `decision_id` | Stable unique identifier | Yes |
| `instrument` | Instrument identity | Yes |
| `timeframe` | Market-observation interval | Yes |
| `decision` | `BUY` / `SELL` / `WAIT` | Yes |
| `evidence_cutoff` | Absolute timestamp | Yes |
| `available_at` | Absolute timestamp | Yes |
| `valid_until` | Absolute timestamp | No |
| `decision_policy` | Policy reference | Yes |
| `reasons` | Non-empty ordered collection of reason records | Yes |
| `evidence` | Non-empty ordered collection of evidence references | Yes |
| `confidence` | Calibrated confidence record | No |
| `opportunity_plan` | Decision-support price plan | No |
| `expected_hold_period` | Duration record | No |
| `annotations` | Ordered collection of annotation records | No |
| `limitations` | Ordered collection of limitation records | No |
| `supersedes_decision_id` | Decision identifier | No |

## Top-Level Field Definitions

### `contract_version`

| Attribute | Contract |
| --- | --- |
| Purpose | Identifies the semantic version of this decision contract. |
| Definition | The approved version under which every field and invariant in the decision must be interpreted. |
| Required/optional | Required. |
| Availability conditions | Available only after that contract version has been approved. It must be known before the decision is created. |
| Source of truth | The approved AlphaLens v2 Decision Contract version. |
| Future extensibility | New optional fields may be introduced by a compatible version. Changed meanings, required fields, or invariants require a new incompatible version. Existing decisions retain their original version. |

### `decision_id`

| Attribute | Contract |
| --- | --- |
| Purpose | Gives the decision a stable identity across all subsystems and audit records. |
| Definition | A globally unique, immutable identifier assigned to exactly one canonical decision. |
| Required/optional | Required. |
| Availability conditions | Created only when a complete decision satisfies all required fields and invariants. |
| Source of truth | The canonical immutable decision record. |
| Future extensibility | Identifier representation may evolve, but identity must remain stable, collision-resistant, and independent of any consumer. |

### `instrument`

| Attribute | Contract |
| --- | --- |
| Purpose | Identifies the market to which the decision applies. |
| Definition | A canonical base-asset and quote-asset pair. In the initial scope this is `BTC/USD`. |
| Required/optional | Required. |
| Availability conditions | Available only for an instrument approved by the active product scope. |
| Source of truth | The approved AlphaLens product and market-scope contracts. |
| Future extensibility | Additional instruments may be added without changing decision semantics. Provider- or venue-specific provenance belongs in evidence references unless a later market contract makes venue part of canonical identity. |

### `timeframe`

| Attribute | Contract |
| --- | --- |
| Purpose | States the observation interval for which the decision was evaluated. |
| Definition | The canonical duration of each market observation used to identify the decision context. Initial approved values are `5m`, `10m`, and `15m`. |
| Required/optional | Required. |
| Availability conditions | Available only for a timeframe approved by the active product scope and supported by the referenced decision policy. |
| Source of truth | The approved product scope and the referenced market evidence. |
| Future extensibility | New timeframes may be added as new values. Consumers must not infer that policies or results transfer between timeframes. |

### `decision`

| Attribute | Contract |
| --- | --- |
| Purpose | Communicates AlphaLens’s directional opportunity assessment. |
| Definition | Exactly one of `BUY`, `SELL`, or `WAIT`, with the meanings defined in this document. |
| Required/optional | Required. |
| Availability conditions | Available only after a valid evaluation under the referenced decision policy. |
| Source of truth | The immutable decision produced under the referenced approved policy and evidence set. |
| Future extensibility | No additional decision value may be added without explicit product-contract approval and a new incompatible contract version. Metadata must not create hidden decision states. |

### `evidence_cutoff`

| Attribute | Contract |
| --- | --- |
| Purpose | Establishes the point-in-time boundary that prevents future information from entering the decision. |
| Definition | The latest absolute time at which any evidence used by the decision was available. No referenced input may have an availability time after this cutoff. |
| Required/optional | Required. |
| Availability conditions | Available only when the availability time of every material input is known and auditable. |
| Source of truth | The availability metadata of the referenced evidence artifacts. |
| Future extensibility | Finer timestamp precision may be added without changing the rule. The semantic boundary must always remain explicit and timezone-unambiguous. |

### `available_at`

| Attribute | Contract |
| --- | --- |
| Purpose | States the earliest time at which the complete decision could have been consumed. |
| Definition | The first absolute time when the decision and all required fields existed. It must be equal to or later than `evidence_cutoff`. |
| Required/optional | Required. |
| Availability conditions | Known only after the complete decision has been produced. Replays must preserve the original value rather than substitute replay time. |
| Source of truth | The canonical audit evidence for the original decision’s availability. |
| Future extensibility | Additional lifecycle timestamps may be introduced, but they must not replace or reinterpret original availability. |

### `valid_until`

| Attribute | Contract |
| --- | --- |
| Purpose | Limits how long a decision may be represented as current when an approved policy defines such a limit. |
| Definition | The exclusive absolute time after which the decision must not be presented as currently valid. It must be later than `available_at`. |
| Required/optional | Optional. |
| Availability conditions | Present only when the referenced decision policy defines a deterministic validity period. Absence means no validity claim is made; it does not mean indefinite validity. |
| Source of truth | The referenced approved decision policy. |
| Future extensibility | Validity may later include explicit invalidation reasons, but historical decision content must remain immutable. |

### `decision_policy`

| Attribute | Contract |
| --- | --- |
| Purpose | Identifies the exact approved quantitative definition used to map evidence to the decision. |
| Definition | An immutable reference containing a stable policy identifier, policy version, and integrity digest. |
| Required/optional | Required. |
| Availability conditions | Available only for an approved, versioned policy whose complete definition can be retrieved and verified. |
| Source of truth | The approved decision-policy artifact. |
| Future extensibility | Any production method may be used behind a newly approved policy. A changed quantitative definition requires a new policy version and must not rewrite prior decisions. |

### `reasons`

| Attribute | Contract |
| --- | --- |
| Purpose | Makes every decision explainable, including `WAIT`. |
| Definition | A non-empty, deterministically ordered collection of structured reason records describing the evidence-supported basis for the decision. |
| Required/optional | Required. |
| Availability conditions | Present only when every reason can be traced to available evidence and the active reason taxonomy. |
| Source of truth | The decision evidence interpreted under the referenced decision policy and reason-taxonomy version. |
| Future extensibility | New reason codes and categories may be added through versioned taxonomies. Existing reason meanings must not change retroactively. |

### `evidence`

| Attribute | Contract |
| --- | --- |
| Purpose | Provides the complete audit path needed to verify and reproduce the decision. |
| Definition | A non-empty, deterministically ordered collection of immutable evidence references covering every material input and derived artifact used by the decision. |
| Required/optional | Required. |
| Availability conditions | Present only when each reference resolves to evidence with verifiable identity, version, integrity, and point-in-time availability. |
| Source of truth | The referenced immutable evidence artifacts. |
| Future extensibility | New evidence categories may be added without changing decision semantics. A consumer must tolerate unknown categories while preserving them. |

### `confidence`

| Attribute | Contract |
| --- | --- |
| Purpose | Communicates a statistically calibrated quantity with an explicit meaning and population scope. |
| Definition | A complete confidence record defined below. It is never a generic score, subjective certainty, ranking value, or uncalibrated model output. |
| Required/optional | Optional. |
| Availability conditions | Present only when an approved confidence policy has been satisfied and the calibration evidence is valid for this instrument, timeframe, decision meaning, and evidence regime. Otherwise the entire field must be absent. |
| Source of truth | The approved confidence policy and referenced immutable calibration evidence. |
| Future extensibility | Additional calibrated quantities may be supported through explicit meaning identifiers. Existing meanings and values must not be reinterpreted. |

### `opportunity_plan`

| Attribute | Contract |
| --- | --- |
| Purpose | Describes optional price-level context for understanding a `BUY` or `SELL` opportunity. |
| Definition | A complete decision-support plan containing an entry region, stop-loss level, one or more take-profit levels, and risk/reward values, as defined below. It is informational and never an executable order. |
| Required/optional | Optional. |
| Availability conditions | Permitted only for `BUY` or `SELL`, and only when every included value is deterministically defined by an approved policy using evidence available by `evidence_cutoff`. It must be absent for `WAIT`. |
| Source of truth | The referenced approved opportunity-plan policy and its evidence. |
| Future extensibility | Additional informational levels may be added through a versioned plan contract. Execution instructions, account data, quantities, and order state are permanently outside this field. |

### `expected_hold_period`

| Attribute | Contract |
| --- | --- |
| Purpose | Communicates the approved evaluation horizon associated with an opportunity. |
| Definition | A positive duration record describing the period over which the decision’s opportunity definition is evaluated. It is not a promise or an instruction to maintain a position. |
| Required/optional | Optional. |
| Availability conditions | Permitted only when the referenced decision policy defines an explicit horizon. It must be absent when no such horizon has been approved. |
| Source of truth | The referenced approved decision policy. |
| Future extensibility | Calendar-time and observation-count horizons may be represented through explicit bases. Consumers must not convert between bases without an approved rule. |

### `annotations`

| Attribute | Contract |
| --- | --- |
| Purpose | Associates evidence-backed market context with the decision. |
| Definition | A deterministically ordered collection of structured annotation records, such as trend, support, resistance, breakout, liquidity, volatility, or market-regime context. |
| Required/optional | Optional. |
| Availability conditions | Present only when each annotation conforms to an approved ontology and is supported by evidence available by `evidence_cutoff`. |
| Source of truth | The approved annotation ontology and referenced evidence artifacts. |
| Future extensibility | New annotation types may be added through ontology versioning without changing the core decision vocabulary. Unknown types must remain preservable. |

### `limitations`

| Attribute | Contract |
| --- | --- |
| Purpose | Discloses material qualifications that affect interpretation of the decision. |
| Definition | A deterministically ordered collection of structured limitation records. |
| Required/optional | Optional. |
| Availability conditions | Required in substance whenever a known material limitation applies; the field may be absent only when no reportable limitation was identified under the active policy. |
| Source of truth | The decision audit evidence and applicable research or data-quality records. |
| Future extensibility | New limitation categories may be added through a versioned taxonomy. Limitations must never be removed from an existing decision. |

### `supersedes_decision_id`

| Attribute | Contract |
| --- | --- |
| Purpose | Preserves audit history when a prior decision requires correction or explicit replacement. |
| Definition | The stable identifier of one earlier decision that this decision supersedes. Supersession does not mutate or erase the earlier record. |
| Required/optional | Optional. |
| Availability conditions | Present only when this decision is an approved correction or replacement of the identified prior decision. |
| Source of truth | The immutable decision lineage and the documented reason for supersession. |
| Future extensibility | More complex lineage may later use a separate lineage contract. The single reference must not be overloaded to imply aggregation. |

## Embedded Value Contracts

Embedded records are part of the canonical decision contract. Their fields
follow the same stability and audit requirements as top-level fields.

### Policy reference

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `policy_id` | Stable identity of the approved policy. | Required. | The policy has been approved. | Approved policy artifact. | Identifier representation may evolve without changing identity. |
| `policy_version` | Immutable version of the quantitative definition. | Required. | The exact version is retrievable. | Approved policy artifact. | Changed definitions require new versions. |
| `integrity_digest` | Verifiable digest of the complete policy content. | Required. | Canonical content exists for verification. | Approved policy artifact. | Digest algorithms may be versioned; existing digests remain valid. |

### Reason record

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `taxonomy_version` | Identifies the approved meaning of the reason code. | Required. | The taxonomy version is approved and retrievable. | Approved reason taxonomy. | New taxonomies must preserve old meanings. |
| `code` | Stable machine-independent reason identifier. | Required. | The code exists in the referenced taxonomy. | Approved reason taxonomy. | New codes may be added; existing codes cannot be redefined. |
| `summary` | Concise factual explanation of why the reason applies. | Required. | The statement is supported by referenced evidence. | Decision evidence under the approved policy. | Additional localized or detailed text may be added separately. |
| `evidence_references` | Ordered references supporting this reason. | Required and non-empty. | Every reference satisfies the evidence-reference contract. | Referenced evidence artifacts. | New evidence categories may be referenced. |

### Evidence reference

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `evidence_id` | Stable identity of an input or derived evidence artifact. | Required. | The artifact is immutable and retrievable for audit. | Referenced evidence artifact. | Identifier representation may evolve without changing identity. |
| `evidence_type` | Versioned category describing the artifact’s semantic role. | Required. | The category is defined by an approved evidence taxonomy. | Approved evidence taxonomy. | New categories may be added. |
| `evidence_version` | Exact immutable version of the artifact or evidence definition. | Required. | The version is known and retrievable. | Referenced evidence artifact. | Version schemes may evolve while old versions remain resolvable. |
| `integrity_digest` | Verifiable digest of canonical evidence content. | Required. | Canonical content exists for verification. | Referenced evidence artifact. | Digest algorithms may be versioned; integrity must not be weakened. |
| `available_at` | Earliest absolute time the evidence could have been used. | Required. | Point-in-time availability is known. | Evidence provenance record. | Precision may increase; original availability cannot move earlier retroactively. |

### Confidence record

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `value` | Reports the calibrated quantity using the scale explicitly defined by its approved meaning. | Required when `confidence` is present. | The approved calibration policy permits this exact quantity and defines its scale. | Immutable calibration evidence. | New scales require distinct meanings and must not reinterpret existing values. |
| `meaning` | Names the precise event or reliability statement represented by `value`. | Required when `confidence` is present. | The meaning is defined by the approved confidence policy. | Approved confidence policy. | New meanings may be added without reinterpreting existing ones. |
| `population_scope` | Identifies the instrument, timeframe, decision class, horizon, and other applicability boundaries of calibration. | Required when `confidence` is present. | Calibration evidence matches the current decision scope. | Immutable calibration evidence. | Scope dimensions may be extended conservatively. |
| `calibration_reference` | Identifies and verifies the approved calibration evidence. | Required when `confidence` is present. | The evidence is approved, immutable, and valid for the population scope. | Calibration artifact. | New calibration methods require new references. |

The confidence record is atomic: either every required member is present and
valid, or the top-level `confidence` field is absent.

### Opportunity-plan record

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `policy_reference` | Identifies the approved definition used for all plan values. | Required when the plan is present. | The policy is approved and evidence-compatible. | Approved opportunity-plan policy. | Changed calculations require new policy versions. |
| `reference_price` | Records the evidence-aligned market price from which the plan is expressed. | Required when the plan is present. | A valid price was available by `evidence_cutoff`. | Referenced market evidence. | Price-source metadata may be added through evidence references. |
| `entry_lower` | Lower bound of the informational entry region. | Required when the plan is present. | Deterministically available under the plan policy. | Approved plan policy and evidence. | An exact entry is represented by equal lower and upper bounds. |
| `entry_upper` | Upper bound of the informational entry region. | Required when the plan is present. | Deterministically available under the plan policy and not below `entry_lower`. | Approved plan policy and evidence. | Additional region semantics require a new plan version. |
| `stop_loss` | Informational price level at which the opportunity thesis is defined as invalidated. | Required when the plan is present. | Deterministically available under the plan policy. | Approved plan policy and evidence. | Multiple or dynamic stops require a new plan version. |
| `take_profit_levels` | Non-empty ordered collection of informational objective price levels. | Required when the plan is present. | Every level is deterministically available under the plan policy. | Approved plan policy and evidence. | Weighted or staged objectives require versioned extensions. |
| `risk_reward` | Ordered collection of dimensionless reward-to-risk ratios corresponding to take-profit levels. | Required when the plan is present. | Each value is deterministically derived from the same plan values and policy. | Approved plan policy and evidence. | Additional reward/risk definitions require explicit semantic identifiers. |

For `BUY`, the plan must place the stop-loss below the entry region and each
take-profit level above it. For `SELL`, the plan must place the stop-loss above
the entry region and each take-profit level below it. Every risk/reward value
must be positive and correspond one-to-one with the ordered take-profit
levels.

### Expected-hold-period record

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `value` | Positive magnitude of the approved evaluation horizon. | Required when the record is present. | The decision policy defines the magnitude. | Approved decision policy. | Fractional values may be supported only when their unit permits them. |
| `unit` | Unit in which the horizon is expressed. | Required when the record is present. | The unit is defined by the decision policy. | Approved decision policy. | New units may be added through versioning. |
| `basis` | Distinguishes elapsed calendar time from a count of market observations. | Required when the record is present. | The basis is explicit in the decision policy. | Approved decision policy. | New bases require explicit semantics and must not be inferred. |

### Annotation record

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `ontology_version` | Identifies the approved annotation vocabulary. | Required for each annotation. | The ontology is approved and retrievable. | Approved annotation ontology. | New ontologies preserve old meanings. |
| `type` | Stable annotation identifier such as trend or volatility context. | Required. | The type exists in the referenced ontology. | Approved annotation ontology. | New types may be added. |
| `summary` | Factual explanation of the annotated condition. | Required. | Supported by the annotation evidence. | Referenced evidence under the annotation definition. | Richer descriptions may be added separately. |
| `time_scope` | Absolute point or interval to which the annotation applies. | Required. | The time scope is deterministically known and does not use future evidence. | Referenced evidence. | More granular time scopes may be added. |
| `price_scope` | Optional exact price or price interval associated with the annotation. | Optional. | Present only when defined and supported by the annotation evidence. | Referenced evidence. | More complex geometry belongs in a versioned extension. |
| `evidence_references` | Ordered references supporting the annotation. | Required and non-empty. | Every reference satisfies the evidence-reference contract. | Referenced evidence artifacts. | New evidence categories may be referenced. |

### Limitation record

| Field | Purpose and definition | Required/optional | Availability conditions | Source of truth | Future extensibility |
| --- | --- | --- | --- | --- | --- |
| `taxonomy_version` | Identifies the approved limitation vocabulary. | Required for each limitation. | The taxonomy is approved and retrievable. | Approved limitation taxonomy. | New taxonomies preserve historical meanings. |
| `code` | Stable category of the material limitation. | Required. | The code exists in the referenced taxonomy. | Approved limitation taxonomy. | New codes may be added. |
| `summary` | Factual description of the limitation and affected interpretation. | Required. | The limitation is known from recorded evidence. | Research, validation, or data-quality evidence. | Additional details may be attached without weakening the original disclosure. |
| `evidence_references` | Ordered references supporting the limitation. | Required and non-empty. | Every reference satisfies the evidence-reference contract. | Referenced evidence artifacts. | New evidence categories may be referenced. |

## Cross-Field Invariants

Every canonical decision must satisfy all of the following:

1. Exactly one decision value is present.
2. The value is exactly `BUY`, `SELL`, or `WAIT`.
3. `WAIT` represents a completed evaluation and never an operational error.
4. `evidence_cutoff` is not later than `available_at`.
5. No evidence reference has an `available_at` later than
   `evidence_cutoff`.
6. Every reason and annotation refers only to evidence included in the
   top-level evidence collection.
7. Reasons and evidence are non-empty and deterministically ordered.
8. Optional collections, when present, are deterministically ordered.
9. `confidence`, when present, is complete, calibrated, in scope, and
   evidence-backed. Otherwise it is absent; placeholder, null, estimated, or
   uncalibrated confidence is prohibited.
10. `opportunity_plan` is absent for `WAIT`.
11. `opportunity_plan`, when present, is complete and directionally
    consistent with `BUY` or `SELL`.
12. `valid_until`, when present, is later than `available_at`.
13. `supersedes_decision_id` never equals `decision_id`.
14. No field implies that AlphaLens placed, routed, simulated, or managed a
    trade.
15. Reproducing the same approved policy over the same point-in-time evidence
    must reproduce the same semantic decision content.

## Availability and Absence Rules

The distinction between unavailable, absent, and `WAIT` is mandatory:

- **Unavailable decision:** a valid evaluation did not complete. No canonical
  decision object exists.
- **`WAIT` decision:** a valid evaluation completed and intentionally
  abstained under the referenced policy.
- **Absent optional field:** the decision is valid, but the field’s
  availability conditions were not met. The field carries no implied value.
- **Present optional field:** all of its required members, evidence, and
  policy conditions are satisfied.

Nulls, placeholders, zeros, empty strings, empty records, or inferred defaults
must not be used to disguise unavailable optional information.

## Immutability and Supersession

A canonical decision is immutable after it becomes available.

- New evidence does not rewrite an earlier decision.
- Policy changes do not rewrite decisions produced under earlier versions.
- Calibration changes do not add confidence retroactively to an existing
  decision.
- Presentation changes do not alter decision meaning.
- A correction creates a new decision with a new identifier and, when
  applicable, `supersedes_decision_id`.
- Superseded decisions remain auditable and retain their original provenance.

## Consumer Obligations

Every subsystem consuming this contract must:

- preserve the decision value and field meanings exactly;
- preserve contract, policy, taxonomy, evidence, and lineage references;
- preserve original ordering where the contract requires deterministic order;
- distinguish `WAIT` from unavailable evaluation;
- omit unavailable optional fields rather than fabricate values;
- prevent confidence from appearing without the complete confidence record;
- avoid converting `SELL` into an exit command;
- avoid converting decision-support price levels into executable orders; and
- retain enough information to trace displayed or analyzed content to the
  canonical decision.

Research may analyze decisions, scanners may rank them, delivery mechanisms
may convey them, overlays may annotate them, and presentation may render them.
None may change what the decision means.

## Explicit Non-Requirements

This contract does not select or assume:

- a prediction target;
- a label-generation formula;
- a model family;
- a training procedure;
- a heuristic or rules engine;
- a confidence-calibration method;
- a ranking method;
- a data provider;
- a persistence technology;
- a service topology;
- a transport or serialization format;
- an endpoint structure;
- a charting library; or
- a presentation framework.

These may change independently as long as they produce and consume decisions
that conform to this contract.

## Deferred Approvals

The following remain separate, prerequisite decisions before runtime
implementation:

- the quantitative decision-policy definition;
- the versioned reason taxonomy;
- confidence calibration methods and acceptance thresholds;
- the opportunity-plan policy;
- expected-hold-period definitions;
- the annotation ontology; and
- limitation taxonomy.

Illustrative examples in product documents do not constitute approval of
these quantitative definitions.

## Blueprint Traceability

This contract implements and is constrained by:

- `IMPLEMENTATION_ORDER.md`
  - “Critical path”
  - “Milestone details — 1. Scope freeze and contract alignment”
- `ALPHALENS_V2_MIGRATION_PLAN.md`
  - “Migration Strategy — Principle 2: replace the product contract”
  - “Phase 0 — Contract freeze and scope reset”
  - recommendations 1, 4, 7, and 10
- `COMPONENT_AUDIT.md`
  - “Target generation and walk-forward validation” (`MODIFY`)
  - “AI decision engine” (`ADD`)
  - “Confidence calibration / abstention service” (`ADD`)
- `TARGET_ARCHITECTURE.md`
  - “Decision Engine”
  - “System boundaries”
  - “Interfaces and contracts”
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`
  - “Product Purpose”
  - “Product Principles”
  - “Product Boundary”
- `RESEARCH_CONSTITUTION.md`
  - all chronology, leakage, evidence, explainability, audit, and
    reproducibility requirements

## Task 2 Acceptance Criteria

Task 2 is complete when:

- `BUY`, `SELL`, and `WAIT` have stable, non-execution semantics;
- `WAIT` is distinguishable from failure or missing output;
- every canonical field documents its purpose, definition, requirement,
  availability, source of truth, and extensibility;
- point-in-time evidence and decision availability are explicit;
- confidence cannot appear without separately approved calibration evidence;
- decisions remain immutable and corrections preserve lineage;
- every future subsystem can consume the same semantics without local
  reinterpretation; and
- no production method or implementation technology is prescribed.

Completion of Task 2 does not complete Phase 1 and does not authorize runtime
decision generation.
