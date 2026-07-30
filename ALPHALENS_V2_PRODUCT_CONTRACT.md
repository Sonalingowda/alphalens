# AlphaLens v2 Product Contract

## Status and Authority

This document is the Task 1 deliverable for Phase 1, “Scope freeze and
contract alignment,” as ordered by `IMPLEMENTATION_ORDER.md`.

`ALPHALENS_V2_MIGRATION_PLAN.md` names the same prerequisite gate “Phase 0 —
Contract freeze and scope reset.” For implementation sequencing, these names
refer to the same contract-alignment milestone. No intraday data, feature,
decision-engine, scanner, API, or frontend implementation is authorized by
this document.

This contract records only product decisions already approved in the
AlphaLens v2 product vision and migration blueprint. It does not define
quantitative labels, thresholds, calibration tests, model families, ranking
formulas, or chart-annotation semantics.

## Product Purpose

AlphaLens v2 identifies, ranks, and explains statistically favorable intraday
market opportunities. It is a quantitative research and decision-support
system whose primary user workspace is a market chart informed by a ranked
opportunity scanner.

The system exists to help a user answer:

1. What is the current decision: `BUY`, `SELL`, or `WAIT`?
2. What recorded evidence explains that decision?

Opportunity quality takes precedence over signal frequency. The system is not
required to emit an actionable opportunity for every candle. `WAIT` is a
first-class product outcome.

## Phase 1 Market Scope

The approved initial market scope is:

| Contract field | Approved value |
| --- | --- |
| Asset | Bitcoin |
| Base asset | `BTC` |
| Quote currency | `USD` |
| Market identifier | `BTC/USD` |
| Candle timeframes | `5m`, `10m`, `15m` |
| Decision vocabulary | `BUY`, `SELL`, `WAIT` |

Additional assets, quote currencies, and timeframes are outside the initial
scope. Their future addition must preserve the stable contracts identified in
`TARGET_ARCHITECTURE.md`; it must not be inferred from this document.

## Product Pillars

### AI Chart Overlay

The chart is the primary workspace. The target product presents the current
decision and its supporting context on the chart. Planned overlay fields and
annotation semantics remain governed by later contract tasks and phases; they
are not defined here.

### AI Opportunity Scanner

The scanner continuously presents ranked opportunities for supported markets
and timeframes. It prioritizes opportunity quality and may present no
actionable opportunity when evidence is insufficient.

### AI Decision Engine

The decision engine produces exactly one of `BUY`, `SELL`, or `WAIT` for an
evaluated opportunity. The quantitative meaning and label-generation rules
for those values require a separate approved decision contract before the
engine is implemented.

## Product Principles

- AlphaLens does not attempt to predict every candle.
- AlphaLens does not maximize the number of signals.
- `WAIT` is an explicit result, not a null, error, or missing prediction.
- Every recommendation must be explainable from recorded evidence.
- Confidence must be absent unless a separately approved calibration policy
  has been satisfied by statistically defensible evidence.
- Research and runtime results must remain deterministic, auditable,
  explainable, reproducible, and point-in-time correct.
- Future information, look-ahead bias, target leakage, random chronological
  splits, fabricated data, and fabricated results remain prohibited.

## Product Boundary

### Inside AlphaLens v2

- quantitative research and chronological validation for opportunity
  identification;
- intraday market-data ingestion, validation, provenance, and persistence;
- point-in-time feature engineering;
- deterministic decision and opportunity-ranking logic;
- confidence gating backed by approved calibration evidence;
- opportunity scanning and chart annotations;
- a read-only, versioned API;
- a chart-first frontend; and
- immutable research, decision, and audit evidence.

### Outside AlphaLens v2

AlphaLens v2 is not:

- a broker;
- an exchange;
- an order-routing or order-execution system;
- a live-trading system;
- a paper-trading application;
- a portfolio manager;
- a copy-trading platform; or
- a system that places or simulates trades as part of the product experience.

No v2 component may place orders or imply that AlphaLens executes a displayed
decision. Entry, stop-loss, take-profit, risk/reward, or expected-hold-time
fields are decision-support information only when later defined and approved.

## Preservation and Migration Rules

- Components classified `KEEP` in `COMPONENT_AUDIT.md` remain reusable.
- Components classified `MODIFY` may change only in their scheduled migration
  phase and according to their recorded modification scope.
- Components classified `REMOVE` remain untouched until the decommission
  milestone in `IMPLEMENTATION_ORDER.md`.
- Existing v1 research artifacts and provenance evidence remain immutable.
- The current v1 API and product path remain available until their v2
  replacements have passed the prerequisite phases and verification gates.
- PostgreSQL persistence, provenance hashing, configuration validation,
  observability, CI/container scaffolding, and reusable frontend primitives
  retain their approved roles.

## Deferred Contracts

This Task 1 product-boundary contract deliberately does not decide:

- intraday provider and backfill policy;
- intraday candle normalization and completeness rules;
- quantitative `BUY`, `SELL`, and `WAIT` label definitions;
- entry, stop-loss, take-profit, risk/reward, or hold-time calculations;
- calibration methods, metrics, thresholds, or acceptance criteria;
- opportunity-ranking formulas or tie-breaking;
- scanner and overlay API schemas;
- chart-annotation ontology; or
- the physical removal or archival treatment of v1 simulation components.

Those decisions must be completed in dependency order. None may be inferred
from illustrative language in the product vision.

## Blueprint Traceability

This contract implements and is constrained by:

- `IMPLEMENTATION_ORDER.md`
  - “Critical path”
  - “Recommended execution order,” milestone 1
  - “Milestone details — 1. Scope freeze and contract alignment”
- `ALPHALENS_V2_MIGRATION_PLAN.md`
  - “Migration Strategy”
  - “Phase 0 — Contract freeze and scope reset”
  - “Top 10 Highest-Impact Recommendations”
- `COMPONENT_AUDIT.md`
  - “Table 1 — Platform foundations that can be reused”
  - “Table 2 — v1 subsystems that require modification or removal”
  - “Table 3 — Missing AlphaLens v2 components that must be added”
- `TARGET_ARCHITECTURE.md`
  - “Architecture overview”
  - “System boundaries”
  - “Interfaces and contracts”
- `RESEARCH_CONSTITUTION.md`
  - all research quality, chronology, leakage, and reproducibility rules

## Task 1 Acceptance Criteria

Task 1 is complete when:

- the purpose of AlphaLens v2 is explicit;
- the initial asset and timeframe scope is explicit;
- `BUY`, `SELL`, and `WAIT` are the exclusive product decisions;
- `WAIT` is explicitly first-class;
- the non-execution product boundary is explicit;
- uncalibrated confidence is explicitly prohibited;
- reusable v1 foundations and immutable evidence are protected; and
- quantitative definitions reserved for later tasks remain undecided.

Completion of Task 1 does not complete Phase 1 and does not authorize
intraday data implementation.
