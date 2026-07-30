# AlphaLens v2 Phase 1 Alignment Record

## Status and Scope

This document is the Task 4 deliverable for Phase 1, “Scope freeze and
contract alignment,” in `IMPLEMENTATION_ORDER.md`.

It records the cross-document review of the approved:

- AlphaLens v2 Product Contract;
- AlphaLens v2 Decision Contract;
- AlphaLens v2 Confidence Policy; and
- six-document migration blueprint.

No runtime code, data pipeline, feature pipeline, decision engine, ranking
engine, API, scanner, overlay, or frontend work is part of this record.

**Alignment outcome:** Phase 1 contract deliverables are complete, the five
documented blueprint conflicts have been resolved through the minimum approved
corrections, and the reviewed documents are mutually consistent. Phase 1 exit
criteria are satisfied and the phase is ready for formal human approval.
Phase 2 remains unauthorized until that approval occurs.

## Reviewed Evidence

This alignment record applies to the exact document contents identified below.

| Document | SHA-256 |
| --- | --- |
| `ALPHALENS_V2_PRODUCT_CONTRACT.md` | `89525bd09cafbb4fff3d8db26a2ddfc39f495f92d2264795c7a0d8030024a196` |
| `ALPHALENS_V2_DECISION_CONTRACT.md` | `3b75a9f409cf43cdf0bfe5825bb20d26d8a214554345af65ead15bd5224818d6` |
| `ALPHALENS_V2_CONFIDENCE_POLICY.md` | `ee5e39a7c6c90fb6c268110c1b0a80db143548c48e559056ba29a2f226e8502d` |
| `ALPHALENS_V2_MIGRATION_PLAN.md` | `8ac1e60159ddc1776f334c7eba9e8a2606ade863f452400e1237e81d1c297b2c` |
| `COMPONENT_AUDIT.md` | `96c20897da37bfef99d311dd045d920d298163ce86c8430f95e5c3ea31a58914` |
| `IMPLEMENTATION_ORDER.md` | `7c0aff728bce715fdc224046fb1cfdeb2deb48845a393cc030c405ef2b0676a1` |
| `TARGET_ARCHITECTURE.md` | `101583eaf50de0ec3962428b6250ecbbeae0f4413c82222403f584fff962f60a` |
| `RISK_ASSESSMENT.md` | `3fd744e8c209af812230385d22969305c5322a16a527bb5595de104a69234401` |
| `ASSUMPTIONS_AND_UNKNOWNS.md` | `fc75db2cc37ee618dd1523d47b2aae9af8e25de76d359a4b249dede84ef0cd3f` |

The permanent governance in `AGENTS.md` and
`RESEARCH_CONSTITUTION.md` was also applied.

## Phase Naming Alignment

`IMPLEMENTATION_ORDER.md` identifies its first milestone as “Scope freeze and
contract alignment.” `ALPHALENS_V2_MIGRATION_PLAN.md` calls the same
prerequisite “Phase 0 — Contract freeze and scope reset” and calls intraday
data work “Phase 1 — Intraday data pipeline.”

For the task sequence approved by the human owner:

| Current task terminology | Migration-plan terminology |
| --- | --- |
| Phase 1 — Scope freeze and contract alignment | Phase 0 — Contract freeze and scope reset |
| Phase 2 — Intraday data foundation | Phase 1 — Intraday data pipeline |

This is a nomenclature mismatch, not a dependency mismatch. The governing
order remains:

`contract alignment -> intraday data -> intraday features -> decision engine`

The mapping is already stated in the Product Contract. No prior document was
modified for this naming issue.

## Contract Alignment Results

| Topic | Product Contract | Decision Contract | Confidence Policy | Blueprint | Result |
| --- | --- | --- | --- | --- | --- |
| Product purpose | Intraday opportunity identification, ranking, and explanation | Decision is an opportunity assessment | Confidence describes only an approved calibrated meaning | Migration and target architecture center the scanner and chart | Aligned |
| Initial market scope | `BTC/USD`, `5m`, `10m`, `15m` | Instrument and timeframe are required and scope-bound | Calibration cannot transfer across instrument or timeframe | Migration plan and component audit specify the same initial scope | Aligned |
| Decision vocabulary | Exactly `BUY`, `SELL`, `WAIT` | Stable semantics for all three values | Evaluates applicability independently by decision class | Blueprint uses the same vocabulary | Aligned |
| `WAIT` semantics | First-class product outcome | Valid abstention, distinct from failure | Confidence for `WAIT` requires independent approved evidence | Target architecture requires abstention | Aligned |
| Point-in-time correctness | Mandatory | Evidence cutoff and availability are explicit | Calibration requires chronology, purge/embargo where applicable, and protected evaluation evidence | Research Constitution and risk plan require leakage-safe chronology | Aligned |
| Confidence default | Must be absent unless statistically calibrated | Optional atomic field | Unavailable by default with non-waivable evidence gates | Target architecture now makes calibration metadata and evidence optional | Aligned |
| Explainability | Every recommendation must be explainable | Non-empty reasons and evidence are required | Explanation cannot substitute for calibration | Target architecture includes reasoning and annotations | Aligned |
| Non-execution boundary | Explicitly excludes execution, paper trading, and portfolio management | Decision is not an order; `SELL` is not an exit command | Confidence never authorizes execution | Target architecture now outputs optional decision-support context | Aligned |
| Immutability and provenance | Existing evidence is protected | Decisions are immutable and corrections use supersession | Calibration artifacts and historical confidence are immutable | Blueprint preserves provenance and SHA-256 discipline | Aligned |
| Technology independence | Product contracts describe domain behavior | Decision meaning is independent of production method and transport | Policy does not choose a calibration method or implementation | Decision architecture now evaluates approved point-in-time evidence without requiring a production method | Aligned |
| Deferred removals | `REMOVE` components remain until their scheduled milestone | No removal behavior introduced | No removal behavior introduced | Decommission follows the complete v2 path | Aligned |

## Conflict Resolution Record

The Product Contract, Decision Contract, and Confidence Policy remain
unchanged. The five documented blueprint conflicts were resolved only in the
sections and rows identified below.

### INC-01 — Resolved

**Document changed:** `TARGET_ARCHITECTURE.md`

**Exact section:** “Layer-by-layer design — 4. Decision Engine — Outputs”

**Reason:** Preserve the approved non-execution boundary and prevent `SELL`
from being interpreted as a position exit.

**Conflict resolved:** Decision output described as entry/exit intent.

- Before: `Entry/exit intent.`
- After: `Optional decision-support opportunity context.`

No other Decision Engine output was changed for INC-01.

### INC-02 — Resolved

**Documents changed:** `TARGET_ARCHITECTURE.md` and `COMPONENT_AUDIT.md`

**Exact sections changed:**

- `TARGET_ARCHITECTURE.md` — “Layer-by-layer design — 4. Decision Engine —
  Responsibility” and “Inputs”
- `COMPONENT_AUDIT.md` — “Table 3 — Missing AlphaLens v2 components that must
  be added,” `AI decision engine` row, `Purpose` and `Dependencies`

**Reason:** Keep the canonical decision architecture independent of a model,
heuristic, or other production method, as required by the approved Decision
Contract.

**Conflict resolved:** Model-specific Decision Engine wording and mandatory
model-artifact/inference dependency.

Target Architecture responsibility:

- Before:
  `Convert features and model outputs into a first-class trading decision:
  BUY, SELL, or WAIT.`
- After:
  `Evaluate approved point-in-time evidence under a versioned decision policy
  to produce BUY, SELL, or WAIT.`

Target Architecture inputs:

- Before: `Feature vectors.` and `Inference outputs or model scores.`
- After:
  `Point-in-time feature vectors and other approved evidence.`
- Before: `Decision-policy configuration.`
- After: `Approved decision-policy configuration.`

Component Audit purpose:

- Before: `Produce BUY / SELL / WAIT outputs from model evidence.`
- After:
  `Produce BUY / SELL / WAIT outputs from approved point-in-time evidence
  under a versioned decision policy.`

Component Audit dependencies:

- Before:
  `Feature engineering, calibration, ranking, model artifact/inference.`
- After:
  `Feature evidence, approved decision policy, research/evaluation evidence.`

These changes do not prohibit a future approved model. They remove a mandatory
production-method assumption from the stable architecture.

### INC-03 — Resolved

**Document changed:** `COMPONENT_AUDIT.md`

**Exact section:** “Table 3 — Missing AlphaLens v2 components that must be
added,” `AI decision engine` row, `Dependencies`

**Reason:** Restore the approved dependency direction in which ranking consumes
decisions.

**Conflict resolved:** Decision Engine incorrectly depended on its downstream
Opportunity Ranking Engine.

- Before dependencies included: `ranking`
- After dependencies:
  `Feature evidence, approved decision policy, research/evaluation evidence.`

Ranking is no longer a Decision Engine dependency.

### INC-04 — Resolved

**Documents changed:** `TARGET_ARCHITECTURE.md` and `COMPONENT_AUDIT.md`

**Exact sections changed:**

- `TARGET_ARCHITECTURE.md` — “Layer-by-layer design — 4. Decision Engine —
  Dependencies”
- `TARGET_ARCHITECTURE.md` — “Layer-by-layer design — 5. Opportunity Ranking
  Engine — Inputs” and “Dependencies”
- `COMPONENT_AUDIT.md` — “Table 3 — Missing AlphaLens v2 components that must
  be added,” `AI decision engine` and `Opportunity ranking engine` rows,
  `Dependencies`

**Reason:** Preserve the approved milestone order and the Confidence Policy’s
unavailable-by-default semantics. Core decisions and ranking must not require
confidence.

**Conflict resolved:** Confidence/calibration dependencies pointed backward
from Decision Engine and Opportunity Ranking to the later Calibration
milestone.

Decision Engine dependency:

- Removed: `Confidence gating.`

Opportunity Ranking input:

- Before: `Calibration metadata.`
- After: `Optional approved calibration metadata.`

Opportunity Ranking dependencies:

- Before: `Calibration/evaluation evidence.`
- After:
  `Approved ranking policy and research/evaluation evidence.` and
  `Optional approved calibration evidence when explicitly used by the ranking
  policy.`

Component Audit Decision Engine dependencies:

- Before included: `calibration`
- After:
  `Feature evidence, approved decision policy, research/evaluation evidence.`

Component Audit Opportunity Ranking dependencies:

- Before:
  `Decision engine, calibration, research metrics, evidence store.`
- After:
  `Decision engine, approved ranking policy, research/evaluation evidence,
  evidence store; optional approved calibration evidence.`

### INC-05 — Resolved

**Document changed:** `TARGET_ARCHITECTURE.md`

**Exact section:** “Layer-by-layer design — 5. Opportunity Ranking Engine —
Responsibility” and “Outputs”

**Reason:** Prevent absent confidence from being interpreted as low confidence
or replaced by an uncalibrated placeholder.

**Conflict resolved:** Ranking wording implied confidence was mandatory.

Ranking responsibility:

- Before: `Filter low-quality or low-confidence setups.`
- After:
  `Filter low-quality setups under the approved ranking policy; apply
  confidence criteria only when calibrated confidence is available and
  explicitly authorized.`

Ranking output:

- Before: `Priority and confidence metadata.`
- After: `Priority metadata and optional calibrated confidence metadata.`

## Post-Correction Consistency Verification

The corrected blueprint now establishes:

- point-in-time evidence and an approved decision policy as the stable
  Decision Engine inputs;
- no required model, inference artifact, or production method;
- no entry/exit or order-lifecycle semantics;
- Decision Engine before Opportunity Ranking with no circular dependency;
- decisions and ranking that remain valid without confidence;
- confidence metadata only when approved calibration evidence is available;
  and
- ranking confidence criteria only when an approved ranking policy explicitly
  authorizes them.

No new layer, subsystem, dependency, product behavior, or scope was introduced.
The corrections narrow existing language to the approved contracts.

The following obsolete phrases no longer appear in the corrected blueprint
sections:

- `Entry/exit intent`
- `model outputs`
- `from model evidence`
- Decision Engine dependency on `ranking`
- Decision Engine dependency on `Confidence gating`
- mandatory `Calibration metadata`
- `low-quality or low-confidence setups`
- mandatory `Priority and confidence metadata`

### Non-blocking baseline-audit note

`ASSUMPTIONS_AND_UNKNOWNS.md` remains an unchanged snapshot of what was missing
when the migration blueprint was produced. Its earlier unknowns for product
scope, decision semantics, timeframes, and confidence governance are resolved
by the approved Phase 1 contracts and this record. It is not a current blocker.

## Unresolved Decisions

Unresolved items are classified by the earliest milestone that needs them.
Their unresolved status does not authorize guessing.

### Phase 1 formal status

No technical or contract blocker remains for Phase 1 exit. Formal human
approval of the corrected blueprint and this regenerated alignment record is
still required before the phase is complete.

### Required before Phase 2 — Intraday Data Foundation

- approved BTC/USD intraday provider;
- whether each timeframe is provider-native or derived, especially `10m`;
- exact candle-boundary and completed-candle semantics;
- UTC normalization rules;
- historical availability and backfill policy;
- pagination and rate-limit policy;
- gap, duplicate, incomplete-candle, and provider-revision treatment;
- intraday persistence and provenance contract; and
- rollout and rollback controls preserving the daily v1 path.

These are already identified as blockers for the intraday data milestone in
`IMPLEMENTATION_ORDER.md` and `RISK_ASSESSMENT.md`.

### Required before Intraday Feature Engineering

- approved intraday feature definitions;
- point-in-time lookback and warm-up rules;
- timeframe-specific feature policy;
- feature pipeline versioning; and
- prefix-invariance and leakage verification criteria.

### Required before Decision Engine implementation

- quantitative decision-policy definition;
- research target and outcome definitions;
- evaluation horizon;
- decision eligibility and abstention conditions;
- approved reason taxonomy;
- opportunity-plan policy;
- expected-hold-period policy; and
- limitation taxonomy.

The qualitative decision semantics are approved. The quantitative mapping from
evidence to `BUY`, `SELL`, or `WAIT` remains deliberately unresolved.

### Required before Opportunity Ranking

- ranking objective;
- quality measures;
- eligibility and filtering policy;
- deterministic tie-breaking;
- missing-confidence handling consistent with the Confidence Policy; and
- ranking provenance and reproducibility requirements.

### Required before Calibration and Explainability

Every item listed under “Explicitly Unresolved Decisions” in
`ALPHALENS_V2_CONFIDENCE_POLICY.md`, including:

- confidence estimand and outcome;
- scale and horizon;
- calibration method;
- evaluation measures;
- evidence-adequacy rules;
- acceptance criteria;
- uncertainty methodology;
- lifecycle and revalidation rules; and
- decision-class applicability.

### Required before Scanner, Overlay, and Presentation work

- scanner item and freshness contract;
- overlay decision-support contract;
- chart-annotation ontology;
- reason and limitation presentation rules;
- treatment of absent confidence; and
- versioned read-only delivery contract.

### Required before v1 decommissioning

- archive-versus-removal decision for backtesting, simulated risk, and paper
  trading;
- retention policy for immutable v1 research evidence; and
- verified operation of the complete v2 path.

## Dependency Verification

### Phase 1 task chain

| Task | Dependency | Verification | Status |
| --- | --- | --- | --- |
| Task 1 — Product Contract | Approved v2 vision and migration blueprint | Product boundary, initial scope, and preservation rules recorded; human approved | Complete |
| Task 2 — Decision Contract | Task 1 | Canonical technology-independent decision semantics recorded; human approved | Complete |
| Task 3 — Confidence Policy | Tasks 1 and 2; Research Constitution | Statistically governed unavailable-by-default policy recorded; human approved | Complete |
| Task 4 — Alignment Record | Tasks 1 through 3 and six blueprint documents | Five conflicts corrected; hashes, consistency, dependencies, unknowns, and exit status regenerated | Complete pending human approval |

### Milestone-order verification

- Intraday data work depends on completion of the contract-alignment milestone.
- Intraday feature work depends on verified intraday data.
- Decision Engine work depends on verified intraday features.
- Opportunity Ranking depends on canonical decisions.
- Calibration and explainability follow the decision and ranking foundations.
- Scanner delivery follows decision, ranking, and calibration contracts.
- Chart overlay work follows a stable scanner and annotation contract.
- v1 simulation components remain untouched until the v2 path exists.

No dependency was skipped during Tasks 1 through 4.

### Preservation verification

- `KEEP` infrastructure was not modified or removed.
- `MODIFY` components were not changed before their scheduled phase.
- `REMOVE` components were not deleted, renamed, or altered.
- Existing v1 research evidence was not changed.
- No runtime or research implementation was introduced.
- No Phase 2 work began.

## Phase 1 Exit Readiness

| Exit criterion | Evidence | Status |
| --- | --- | --- |
| Product boundary is explicit | Approved Product Contract | Pass |
| Initial asset and timeframes are explicit | `BTC/USD`, `5m`, `10m`, `15m` | Pass |
| Canonical decision object is defined | Approved Decision Contract | Pass |
| `BUY`, `SELL`, and `WAIT` semantics are stable | Approved Decision Contract | Pass |
| `WAIT` is distinct from failure | Approved Decision Contract | Pass |
| Confidence policy is canonical | Approved Confidence Policy | Pass |
| Evidence required before confidence is explicit | Ten non-numeric availability gates and required calibration evidence | Pass |
| No unsupported threshold or metric was invented | Confidence Policy unresolved-decision register | Pass |
| Architecture dependency direction matches implementation order | INC-03 and INC-04 corrections | Pass |
| Architecture wording preserves non-execution semantics | INC-01 correction | Pass |
| Decision architecture is production-method independent | INC-02 corrections | Pass |
| Blueprint treats confidence as optional | INC-04 and INC-05 corrections | Pass |
| No new inconsistency or scope expansion introduced | Post-correction consistency verification | Pass |
| Alignment record formally approved | Human review pending | Pending |

## Readiness Determination

All Phase 1 technical exit criteria are satisfied.

- All five documented blueprint conflicts are resolved.
- No new inconsistency was found after correction.
- The Product Contract, Decision Contract, and Confidence Policy remain
  unchanged and mutually consistent.
- Dependency order matches `IMPLEMENTATION_ORDER.md`.
- No Phase 2 implementation has begun.

Phase 1 is **ready for formal human approval**, but it is not formally complete
until that approval is given. This record does not authorize Phase 2.
