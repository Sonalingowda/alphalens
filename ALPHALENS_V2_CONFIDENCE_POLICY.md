# AlphaLens v2 Confidence Policy

## Status and Authority

This document is the Task 3 deliverable for Phase 1, “Scope freeze and
contract alignment,” in `IMPLEMENTATION_ORDER.md`.

It defines the governance conditions under which an AlphaLens v2 decision may
contain confidence. It does not approve a calibration method, statistical
measure, numeric threshold, sample requirement, confidence scale, probability
cutoff, or display convention.

Confidence is unavailable by default. It becomes eligible for inclusion only
after all requirements in this policy have been satisfied by approved,
immutable, point-in-time research evidence for the exact decision scope.

This document governs confidence availability. It does not define how a
decision is produced and does not authorize confidence generation.

## Governing Contracts

This policy is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_MIGRATION_PLAN.md`;
- `COMPONENT_AUDIT.md`; and
- `TARGET_ARCHITECTURE.md`.

If calibration evidence conflicts with the Research Constitution, confidence
must remain unavailable regardless of apparent empirical performance.

## Policy Objective

The policy exists to prevent AlphaLens from presenting an unsupported number
as certainty.

A confidence value is permitted only when it has:

- one precise, approved statistical meaning;
- a declared scale and interpretation;
- a defined outcome against which it is calibrated;
- a defined population and applicability scope;
- point-in-time, chronologically valid calibration evidence;
- predeclared evaluation and acceptance rules;
- sufficient evidence under a predeclared adequacy rule;
- immutable provenance; and
- explicit human approval for use.

Failure to satisfy any requirement makes confidence unavailable. No fallback,
estimate, proxy, placeholder, or inferred value is permitted.

## Normative Meaning of Confidence

Confidence is a statistically calibrated quantity whose interpretation is
defined by an approved confidence specification.

Calibration means that the relationship between reported values and observed
outcomes has been evaluated under a predeclared, reproducible methodology for
a precisely defined population and event.

The word “confidence” does not, by itself, mean:

- probability;
- prediction certainty;
- expected return;
- opportunity quality;
- ranking score;
- decision strength;
- distance from a decision boundary;
- agreement among methods;
- historical accuracy;
- explanation quality; or
- likelihood of profit.

Confidence may carry one of those meanings only if that exact estimand,
outcome, scale, scope, and interpretation are explicitly defined and approved.
Until then, no confidence value exists.

## Default State: Unavailable

The canonical default is complete absence of the `confidence` field defined
in `ALPHALENS_V2_DECISION_CONTRACT.md`.

Unavailable confidence must not be represented by:

- zero;
- an empty value;
- a null placeholder;
- a default percentage;
- a neutral midpoint;
- a qualitative substitute such as “low,” “medium,” or “high”;
- an uncalibrated score;
- a ranking value;
- a raw predictive output; or
- explanatory language that implies a numerical certainty.

Absence means only that confidence is not authorized for that decision. It
does not alter the `BUY`, `SELL`, or `WAIT` decision and must not be
interpreted as low confidence.

## Confidence Availability Gate

Confidence may be attached to a new decision only when every gate below is
satisfied.

### Gate 1 — Approved meaning

The confidence specification must define:

- the exact quantity being reported;
- the event or reliability statement to which it refers;
- the scale and valid domain of the value;
- the interpretation of values on that scale;
- the associated decision class or classes;
- the evaluation horizon; and
- what the value explicitly does not claim.

The meaning must be approved before calibration results are examined for
acceptance.

### Gate 2 — Approved population scope

The confidence specification must predeclare the population for which
calibration is claimed. At minimum, applicability must address:

- instrument;
- timeframe;
- decision class;
- decision-policy version;
- outcome definition;
- evaluation horizon;
- evidence period;
- relevant market or data regime boundaries; and
- any exclusion rules.

Confidence calibrated for one scope must not be transferred to another scope
without separately approved evidence. Apparent similarity is not evidence of
transferability.

### Gate 3 — Approved calibration protocol

Before results are inspected, an immutable protocol must define:

- the calibration objective;
- the calibration method;
- the chronological data partitions;
- the evidence available for method development;
- the evidence reserved for evaluation;
- the treatment of overlapping outcomes;
- the treatment of class or outcome imbalance;
- the treatment of missing or censored outcomes;
- sample-adequacy requirements;
- the evaluation measures;
- uncertainty assessment;
- acceptance criteria;
- multiplicity or repeated-analysis controls where applicable;
- deterministic configuration and random-state requirements; and
- conditions that invalidate the study.

This policy intentionally supplies no values or methods for those items.
They require future research and explicit approval.

### Gate 4 — Chronological integrity

Calibration must preserve point-in-time correctness.

- Calibration inputs may use only information available by their recorded
  evidence cutoffs.
- Outcomes used to assess a decision must occur strictly after that
  decision’s availability.
- Development evidence must not gain access to protected evaluation outcomes.
- Preprocessing and calibration fitting must occur only within the
  chronologically eligible development evidence.
- Any purge or embargo required by the approved outcome horizon and feature
  dependencies must be predeclared and enforced.
- Overlapping outcomes must be handled by the approved protocol.
- Evaluation evidence must not influence the meaning, method, parameters,
  scope, acceptance criteria, or adequacy rule being evaluated.

Random or shuffled partitioning of time-dependent evidence is prohibited.

### Gate 5 — Research safeguards

The calibration study must actively prevent and document:

- look-ahead bias;
- target leakage;
- survivorship bias;
- data snooping;
- repeated evaluation against protected evidence;
- selection of methods or criteria after viewing results;
- silent exclusion of unfavorable or unavailable outcomes;
- use of revised evidence that was unavailable at the decision time; and
- aggregation that conceals material scope-specific failure.

If any safeguard cannot be established, the limitation must be recorded and
confidence remains unavailable for that study and scope. Approval cannot
convert an unestablished safeguard into statistical evidence.

### Gate 6 — Evidence adequacy

The study must satisfy an approved, predeclared evidence-adequacy rule for
every scope in which confidence will be used.

Adequacy may not be inferred from:

- the fact that a study completed;
- an apparently favorable result;
- the total dataset size without regard to the applicable subset;
- repeated observations that are not sufficiently independent for the
  approved analysis; or
- combining incompatible instruments, timeframes, decisions, horizons, or
  regimes.

This policy does not define a minimum sample size or any substitute threshold.
Those values remain unresolved pending research and approval.

### Gate 7 — Predeclared acceptance decision

The calibration protocol must state the complete acceptance rule before
protected evaluation evidence is examined.

The final evidence must be assessed against that unchanged rule. Acceptance
criteria must not be relaxed, replaced, selectively reported, or reinterpreted
after results are known.

This policy does not define the evaluation measures, acceptance thresholds,
or decision procedure.

### Gate 8 — Reproducibility and provenance

The complete calibration result must be reproducible from immutable evidence.
The retained record must identify:

- confidence-specification identity and version;
- calibration-protocol identity and version;
- decision-policy identity and version;
- dataset identity and integrity evidence;
- feature or evidence-definition versions where applicable;
- chronological development and evaluation boundaries;
- exclusions and their reasons;
- all configuration values;
- all random states, when applicable;
- software and code identity;
- generated results;
- limitations;
- approval status;
- creation and approval times; and
- integrity evidence for the complete artifact.

A missing or unverifiable provenance element makes confidence unavailable.

### Gate 9 — Scope match at decision time

For each new decision, the approved calibration evidence must match the
decision’s:

- instrument;
- timeframe;
- decision value;
- decision-policy version;
- confidence meaning;
- outcome definition;
- evaluation horizon;
- applicable population boundaries; and
- any validity or retirement conditions in force at `available_at`.

Partial matches are insufficient. A confidence value must be absent when the
applicable calibration scope cannot be established deterministically.

### Gate 10 — Explicit approval

Successful research does not automatically authorize confidence use.

The calibration artifact and its precise scope must receive explicit human
approval before any new canonical decision may include the corresponding
confidence record.

Approval applies only to the approved artifact, meaning, and population scope.
It does not authorize other interpretations, scopes, methods, or thresholds.

## Required Confidence Specification

Before calibration begins, the proposed confidence meaning must be captured in
a versioned specification containing every item below.

| Item | Required definition |
| --- | --- |
| Specification identity | Stable identity and version of the proposed confidence meaning. |
| Estimand | Exact statistical quantity the confidence value intends to represent. |
| Outcome event | Observable event or reliability condition against which calibration is assessed. |
| Value scale | Valid domain, units, and interpretation of the reported value. |
| Decision applicability | Whether the meaning applies to `BUY`, `SELL`, `WAIT`, or an explicitly approved subset. |
| Instrument scope | Exact supported instrument population. |
| Timeframe scope | Exact supported observation timeframe or timeframes. |
| Horizon | Exact future interval or observation count associated with the outcome. |
| Population boundaries | Inclusion, exclusion, regime, and data-availability conditions. |
| Point-in-time rule | Evidence cutoff and outcome-availability alignment. |
| Non-claims | Explicit statements the confidence value must not be interpreted to mean. |

None of these definitions may be selected after reviewing calibration
performance.

## Required Calibration Evidence

An approved calibration artifact must provide, without omission:

- the complete approved confidence specification;
- the complete predeclared calibration protocol;
- development and protected evaluation boundaries;
- the evaluated population and observation counts by relevant scope;
- exclusions and reasons;
- the predeclared evidence-adequacy assessment;
- the predeclared evaluation results;
- uncertainty evidence required by the protocol;
- scope-specific results required by the protocol;
- all known limitations and failed checks;
- an explicit pass or fail under the unchanged acceptance rule;
- deterministic repeatability evidence;
- the complete provenance chain;
- artifact integrity evidence; and
- human approval status and scope.

Unfavorable, inconclusive, or failed results must remain part of the audit
record. They must not be discarded and rerun under revised criteria without a
new protocol version and a new, properly isolated evaluation design.

## Decision-Class Applicability

Confidence availability is evaluated independently for `BUY`, `SELL`, and
`WAIT`.

Evidence supporting one decision class does not authorize confidence for
another. In particular:

- `BUY` confidence must not be reused for `SELL`;
- directional confidence must not be reused for `WAIT`;
- the frequency of `WAIT` does not establish calibration; and
- an approved meaning for `WAIT` must distinguish intentional abstention from
  operational unavailability.

Whether confidence should ever be provided for `WAIT` remains unresolved until
an explicit meaning and calibration specification are approved.

## Relationship to Opportunity Ranking

Confidence and opportunity ranking are distinct concepts.

- Ranking orders opportunities under a separately approved ranking policy.
- Confidence expresses only the calibrated meaning in its approved
  specification.
- Rank position does not imply confidence.
- Confidence does not determine rank unless a later approved ranking policy
  explicitly uses that calibrated quantity.
- Absence of confidence does not, by itself, make a decision invalid.

No ranking score may be relabeled or displayed as confidence.

## Relationship to Explainability

Confidence and explanation are distinct.

- Reasons explain why a decision was made.
- Evidence references make that explanation auditable.
- Confidence communicates a calibrated statistical quantity when authorized.

A detailed explanation does not establish calibration. Feature attribution,
reason strength, narrative quality, or annotation count must not be converted
into confidence without an independently approved statistical definition and
calibration study.

## Lifecycle and Continuing Validity

Approval is not permanent evidence that calibration will remain applicable.
Every approved confidence artifact must define lifecycle conditions before
use, including:

- when applicability begins;
- which decision-policy version it covers;
- conditions requiring review;
- conditions requiring suspension;
- conditions requiring retirement;
- the evidence needed for revalidation; and
- whether a predetermined expiration rule applies.

This policy does not choose review intervals, drift measures, suspension
thresholds, or expiration periods.

### Active

Confidence may be included in new decisions only while the exact calibration
artifact is approved and applicable to the decision scope.

### Suspended

Confidence must be absent from new decisions when a review condition occurs
and continuing validity has not been established. Suspension does not alter
historical decisions.

### Retired

Confidence must be absent from new decisions after the calibration artifact
is retired. A replacement requires a new approved artifact.

### Historical immutability

A confidence record validly attached when a decision became available remains
part of that immutable historical decision.

- Later suspension does not erase it.
- Later recalibration does not rewrite it.
- A newly approved method does not replace its meaning.
- Confidence must not be added retroactively to an existing decision that
  originally lacked it.

## Consumer Obligations

Every consumer of a canonical decision must:

- treat confidence as optional;
- preserve its exact meaning, value, population scope, and calibration
  reference;
- preserve absence without substitution;
- verify applicability before representing the value as current;
- avoid converting it to a percentage unless the approved meaning and scale
  explicitly authorize that representation;
- avoid rounding, bucketing, labeling, or color-coding that changes its
  interpretation unless separately approved;
- avoid comparing confidence values with different meanings or population
  scopes;
- avoid using confidence as an execution instruction;
- avoid implying profitability, certainty, or guarantee beyond the approved
  meaning; and
- retain the provenance necessary to audit the displayed or analyzed value.

Transformations for presentation or analysis must not create information that
is absent from the canonical confidence record.

## Prohibited Practices

AlphaLens must never:

- display uncalibrated output as confidence;
- fabricate confidence;
- substitute a raw score, rank, vote, margin, or explanation weight for
  confidence;
- choose a confidence meaning after seeing favorable results;
- choose evaluation measures or acceptance criteria after seeing results;
- reuse protected evidence for iterative development;
- use random chronological splits;
- fit calibration using evidence from the evaluation period;
- aggregate incompatible scopes to conceal poor calibration;
- transfer calibration across instruments, timeframes, decision classes,
  horizons, policies, or regimes without approved evidence;
- silently omit failed calibration studies;
- backfill confidence onto historical decisions;
- continue publishing confidence after its evidence is suspended, retired, or
  out of scope; or
- imply that confidence authorizes or executes a trade.

## Failure and Uncertainty Handling

When evidence is insufficient, inconclusive, unavailable, stale, unverifiable,
or outside the approved calibration scope:

1. the decision may still exist if it independently satisfies the Decision
   Contract;
2. the `confidence` field must be absent;
3. no replacement confidence value or qualitative proxy may be supplied; and
4. the limitation must remain auditable where it is material to
   interpretation.

A calibration failure is evidence about confidence availability, not a reason
to alter the underlying decision after the fact.

## Explicitly Unresolved Decisions

The following are intentionally unresolved and require future research plus
explicit human approval:

- the confidence estimand;
- whether confidence represents any probability;
- the outcome event;
- the value scale and units;
- the evaluation horizon;
- the calibration method;
- the evaluation measures;
- sample-adequacy rules;
- minimum evidence requirements;
- development and protected evaluation sizes;
- purge and embargo values;
- uncertainty methodology;
- acceptance criteria and thresholds;
- multiplicity controls;
- population and regime partitioning;
- treatment of overlapping outcomes;
- review and revalidation triggers;
- drift definitions and thresholds;
- suspension and retirement thresholds;
- expiration policy;
- applicability to `BUY`, `SELL`, and `WAIT`;
- rounding and display precision; and
- any qualitative presentation labels.

Nothing in this document supplies a default for those decisions.

## Blueprint Traceability

This policy implements and is constrained by:

- `IMPLEMENTATION_ORDER.md`
  - “Milestone details — 1. Scope freeze and contract alignment”
  - “Calibration and explainability gate”
- `ALPHALENS_V2_MIGRATION_PLAN.md`
  - “Migration Strategy — Principle 5: make confidence conditional”
  - “Phase 0 — Contract freeze and scope reset”
  - “Phase 4 — Calibration and explainability”
  - recommendation 7
- `COMPONENT_AUDIT.md`
  - “Research experiment and report stack” (`MODIFY`)
  - “Confidence calibration / abstention service” (`ADD`)
- `TARGET_ARCHITECTURE.md`
  - “Research Layer”
  - “Decision Engine”
  - “Opportunity Ranking Engine”
  - “Interfaces and contracts”
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`
  - “Product Principles”
  - “Product Boundary”
- `ALPHALENS_V2_DECISION_CONTRACT.md`
  - “Confidence record”
  - “Cross-Field Invariants”
  - “Availability and Absence Rules”
- `RESEARCH_CONSTITUTION.md`
  - all statistical defensibility, chronology, leakage, data-snooping,
    auditability, explainability, and reproducibility requirements

## Task 3 Acceptance Criteria

Task 3 is complete when:

- confidence is unavailable by default;
- confidence has no meaning without an approved specification;
- every availability gate is explicit;
- chronology, leakage, data snooping, and evidence adequacy are governed;
- confidence is scoped and cannot transfer without evidence;
- absent confidence cannot be replaced by a proxy;
- calibration evidence is immutable and reproducible;
- lifecycle suspension and retirement do not rewrite history;
- every unresolved quantitative choice remains explicitly unresolved; and
- no threshold, percentage, cutoff, evaluation measure, or calibration method
  has been invented.

Completion of Task 3 does not complete Phase 1 and does not authorize
confidence generation, runtime integration, or Task 4.
