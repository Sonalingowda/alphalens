# AlphaLens v2 Project Constitution

**Status:** Governing engineering constitution  
**Applies to:** All future AlphaLens v2 research, architecture, contracts,
implementation, testing, documentation, review, migration, and operations  
**Nature:** Implementation-independent  
**Effective date:** 2026-07-31

---

## Constitutional Authority

This document is the common governing reference for AlphaLens v2. Every future
implementation prompt, milestone, change request, and review inherits it.

It ties together the repository's existing governance, audit, migration,
research, architecture, risk, contract, baseline, and roadmap artifacts. It
does not duplicate or replace their specialized content.

The following remain authoritative within their scopes:

- repository instructions in `AGENTS.md`;
- quantitative research law in `RESEARCH_CONSTITUTION.md`;
- approved product, decision, and confidence contracts;
- approved phase baselines and their hash manifests;
- the technical audit and implementation inventory;
- the migration blueprint, component audit, implementation order, and risk
  assessment;
- the research protocol and approved research specifications;
- the strategic architecture review and architecture evolution;
- the approved roadmap and explicit human phase approvals.

### Interpretation and precedence

1. Explicit human instructions define the authorized task and scope.
2. Repository instructions govern how work is performed.
3. This constitution governs the common product and engineering principles
   inherited by all work.
4. Specialized frozen contracts, research rules, approved baselines, and
   phase-specific specifications govern their respective domains.
5. The approved implementation order and current phase authorization govern
   sequencing.

A more specific rule does not cancel a stricter general rule. Where multiple
documents apply, all compatible requirements apply.

If an instruction or artifact appears to conflict with this constitution, the
Research Constitution, a frozen contract, approved architecture, or an
immutable baseline:

- stop the affected work;
- identify the exact documents and provisions in conflict;
- record the impact;
- do not infer a resolution;
- request explicit human direction.

Schedule pressure, convenience, implementation progress, or apparent model
performance never authorizes a constitutional exception.

---

# 1. Product Vision

AlphaLens v2 is an **AI Market Intelligence Platform**.

Its purpose is to continuously analyze approved markets, identify statistically
attractive market opportunities, assess and rank them, explain the evidence and
limitations supporting them, and present timely decision support to a human.

AlphaLens is:

- an opportunity-discovery system;
- a quantitative research platform;
- an evidence and market-context platform;
- a decision-support product;
- a read-only source of market intelligence from the standpoint of market
  execution.

AlphaLens is not:

- an autonomous trading bot;
- an execution engine;
- a broker or exchange;
- an order router;
- a portfolio manager;
- a position-sizing service;
- a capital-allocation system;
- an authority that decides whether a user must trade.

The product is successful only when its claims are:

- statistically defensible;
- point-in-time valid;
- reproducible;
- auditable;
- explainable;
- appropriately limited;
- useful without implying certainty or execution.

The approved product scope, market scope, terminology, and system boundaries
are defined by the frozen Product Contract and associated baselines. This
constitution does not expand them.

---

# 2. Human Decision Boundary

The human is always the final decision maker.

AlphaLens may:

- collect and validate approved evidence;
- compute approved features and market context;
- identify and assess opportunities;
- produce an approved `BUY`, `SELL`, or `WAIT` assessment;
- rank qualified opportunities under an approved policy;
- report informational entry, invalidation, objective, duration, or
  risk/reward context when separately authorized;
- explain supporting and conflicting evidence;
- provide confidence only when the frozen Confidence Policy is satisfied;
- notify a user that an opportunity was identified, updated, or expired.

AlphaLens must never:

- place, route, modify, or cancel an order;
- connect an assessment directly to execution;
- select a user's position size;
- allocate or rebalance capital;
- manage an open position;
- infer a user's portfolio or risk tolerance;
- convert confidence, score, or rank into leverage;
- represent a user acknowledgement as a trade;
- override, automate, or impersonate the user's decision.

`BUY`, `SELL`, and `WAIT` are system assessment semantics governed by the
approved Decision Contract. They are not commands:

- `BUY` identifies a qualifying upward opportunity;
- `SELL` identifies a qualifying downward opportunity and is not an exit
  instruction;
- `WAIT` means a valid evaluation found no qualifying directional opportunity;
- operational failure, stale evidence, or unavailable evaluation is not
  `WAIT`.

No user-facing or internal workflow may create an implicit execution bridge
after an AlphaLens assessment.

---

# 3. Core Product and Engineering Principles

## 3.1 Evidence before confidence

No confidence value, probability interpretation, reliability claim, or
qualitative substitute may exist without the complete evidence required by the
approved Confidence Policy.

A raw model output, score, vote, margin, rank, explanation, similarity result,
or agreement across timeframes is not confidence.

When confidence is not authorized, it is absent. It is never zero-filled,
estimated, guessed, or replaced with suggestive wording.

## 3.2 Explain before recommending

Every published opportunity assessment must be supported by retrievable,
point-in-time evidence and an approved explanation form.

Explanations must:

- distinguish factual market context from model behavior;
- identify the policy or artifact responsible for the assessment;
- disclose material conflicting evidence and limitations;
- avoid causal language unless causal evidence exists;
- never manufacture a narrative after observing a result.

Explanation does not repair weak evidence and does not establish confidence.

## 3.3 Quality over quantity

AlphaLens does not maximize the number of signals, predictions, alerts, or
opportunities.

- `WAIT` is a valid and necessary result.
- A valid empty scanner is preferable to low-quality output.
- A missing optional field is preferable to a fabricated value.
- Opportunity frequency is not evidence of quality.
- Product pressure must not weaken research or publication gates.

## 3.4 Never fabricate certainty

AlphaLens must never fabricate:

- market data;
- features;
- labels;
- targets;
- predictions;
- probabilities;
- confidence;
- benchmark results;
- historical performance;
- backtests;
- evaluation metrics;
- explanations;
- provenance;
- functionality presented as real.

Uncertainty, ambiguity, missing evidence, and inconclusive research must be
reported honestly.

## 3.5 Fail closed

When a mandatory condition cannot be verified, the affected output is
unavailable.

Fail-closed behavior applies to:

- source integrity;
- chronology;
- feature availability;
- schema and contract compatibility;
- provenance and hashes;
- artifact identity;
- policy scope;
- calibration scope;
- opportunity freshness;
- required explanation evidence;
- persistence transactions;
- configuration and startup validation.

Failure must remain distinguishable from `WAIT`, exclusion, expiration,
supersession, and an empty valid result.

## 3.6 Point-in-time correctness

Every value used at time `t` must have been available no later than the
applicable evidence cutoff.

The system must:

- use completed observations according to approved contracts;
- enforce explicit availability timestamps;
- omit unavailable warm-up values;
- prevent future information from entering features, labels, models,
  calibration, ranking, explanation, or monitoring;
- preserve as-of semantics for multi-timeframe data;
- prevent retrospective data revisions from replacing the evidence underlying
  a historical claim.

No same-close, intrabar, fill, or execution assumption may be inferred unless
it has been explicitly approved.

## 3.7 Deterministic behavior

Identical approved inputs, code, configuration, dependency versions, and seeds
must produce identical semantic outputs.

Determinism requires:

- canonical ordering;
- canonical serialization;
- explicit decimal and rounding policies;
- recorded seeds where randomness is authorized;
- deterministic tie-breaking;
- stable configuration and result hashes;
- repeatability verification proportional to the risk of the component.

Timestamps or identifiers that are inherently generated at runtime must not
alter the hash of otherwise identical semantic evidence unless the governing
contract explicitly includes them.

## 3.8 Reproducibility

Every research claim and material runtime result must be reproducible from
recorded evidence corresponding to a specific point in time.

The reproducibility record must include every applicable item:

- code version and dirty-state evidence;
- configuration;
- dataset and source versions;
- source memberships;
- feature, target, label, policy, and pipeline versions;
- experiment parameters;
- random seeds;
- validation and split identities;
- software versions;
- artifact identities;
- provenance links;
- canonical hashes.

## 3.9 Provenance and immutability

Every derived result must retain a complete chain to its source evidence.

- Historical evidence is never silently overwritten.
- New versions supersede rather than rewrite prior meaning.
- Active status is a pointer to an immutable version, not permission to mutate
  history.
- Failed, excluded, superseded, retired, and historical records remain
  auditable where required by their contracts.
- Hash failures invalidate use of the affected evidence.

## 3.10 Transparency

Every externally visible claim must disclose enough information to understand:

- what was evaluated;
- when it was evaluated;
- which evidence was available;
- which policy or artifact produced it;
- its scope and limitations;
- whether optional confidence is available;
- whether the result is fresh, stale, expired, or superseded.

Internal complexity must not be hidden behind an unexplained “AI score.”

## 3.11 Separation of meanings

The following concepts must remain distinct:

- observation and feature;
- feature and context;
- label and runtime assessment;
- forecast and opportunity;
- opportunity assessment and human decision;
- score and confidence;
- rank and confidence;
- evidence and explanation;
- `SELL` and exit;
- `WAIT` and failure;
- opportunity plan and executable order;
- market/opportunity risk and user portfolio risk;
- research evaluation and production monitoring.

## 3.12 Security and privacy by default

The platform must:

- validate all external input;
- use environment-based configuration;
- commit no secrets or real credentials;
- use least privilege;
- expose no mutation or training surface through a read-only inference
  boundary;
- apply explicit request and resource limits;
- fail startup on invalid production configuration;
- log safely without leaking sensitive values.

Security controls may become stricter without weakening reproducibility or
historical evidence.

---

# 4. Architecture Principles

## 4.1 Architecture governs implementation

Implementation follows approved architecture. Implementation work must not
redesign architecture opportunistically.

If implementation exposes a genuine architectural problem:

- stop the affected implementation;
- document the evidence;
- explain the current and required behavior;
- assess downstream impact;
- propose no silent workaround;
- obtain explicit approval before changing the architecture or contracts.

## 4.2 Reuse before replacement

Existing infrastructure must be inspected and reused whenever it satisfies the
approved semantics.

In particular, preserve and extend the existing patterns for:

- provider abstraction;
- market-data validation;
- exact decimal handling;
- immutable ingestion batches;
- feature registration;
- availability and warm-up;
- prefix invariance;
- chronological validation;
- purge, embargo, and holdout isolation;
- experiment records;
- artifact packaging;
- SHA-256 verification;
- provenance;
- transactional persistence;
- deterministic replay;
- structured validation and errors;
- deployment checks and CI.

New functionality must not duplicate a capability merely because the existing
capability has a legacy name or lives in another module.

## 4.3 Extend the platform incrementally

New work should extend clear domain boundaries rather than replace the platform
wholesale.

- Prefer extending an existing module when its responsibility remains
  coherent.
- Create a new module when the responsibility is materially distinct and the
  boundary can be stated precisely.
- Keep the repository intentionally small and maintainable.
- Avoid premature microservices.
- Avoid unnecessary abstraction and plugin systems.
- Avoid premature optimization.
- Avoid infrastructure whose need has not been demonstrated.

## 4.4 Legacy v1 treatment

Legacy v1 components may be:

- retained as immutable historical research evidence;
- reused as engineering patterns;
- adapted when their semantics match the v2 contract;
- isolated when they conflict with the v2 product boundary;
- removed only at the explicitly approved migration phase and without deleting
  required historical evidence.

Legacy functionality must never be represented as a completed v2 capability
when its target, timeframe, decision vocabulary, evidence, or product semantics
differ.

## 4.5 Stable contracts, versioned evolution

Contracts define meaning independently of implementation technology.

A contract change requires:

- the exact contract and section affected;
- evidence of the architectural or semantic issue;
- change rationale;
- impact assessment;
- compatibility analysis;
- migration strategy;
- rollback strategy;
- treatment of historical records;
- explicit human approval;
- a new version whenever meaning changes.

No implementation may reinterpret an existing field without a contract change.

## 4.6 Research and runtime separation

Research may create and evaluate candidates. Runtime may use only explicitly
approved immutable artifacts and policies.

- Research code may fit models only within approved experiments.
- Inference code must never call `fit()`.
- Protected evidence must remain inaccessible to iterative development.
- Runtime output must identify the approved artifact and policy used.
- Research results do not become production behavior automatically.
- Promotion requires an explicit, auditable gate.

## 4.7 Presentation is not a source of truth

The frontend renders authoritative backend evidence.

It must not:

- calculate predictions;
- generate decisions;
- infer confidence;
- rank opportunities;
- repair missing values;
- reinterpret stale evidence;
- create business logic that differs from the governing backend contract.

## 4.8 Logical layers do not require separate services

Approved architectural layers describe responsibilities and interfaces. They
do not mandate one process, deployment, database, or microservice per layer.

Physical extraction requires measured justification such as:

- independent scale;
- failure isolation;
- data rate;
- latency;
- security boundary;
- operational ownership.

---

# 5. Engineering Rules

## 5.1 Never

Future work must never:

- duplicate existing functionality without documented evidence that extension
  is unsuitable;
- bypass source, schema, chronology, availability, or provenance validation;
- remove or weaken deterministic behavior;
- delete or rewrite historical evidence without explicit authorization;
- hide uncertainty, exclusions, ambiguity, gaps, or failures;
- fabricate default values for unavailable evidence;
- convert a null, error, or stale result into `WAIT`;
- introduce random or shuffled validation for time-dependent market data;
- fit preprocessing on validation, test, holdout, or future evidence;
- access a protected holdout outside its approved one-time procedure;
- change quantitative definitions after viewing favorable results;
- tune against the protected test;
- treat rank, score, attribution, or model agreement as confidence;
- expose raw model outputs as approved opportunities without the required
  policy;
- couple AlphaLens output to order execution or capital management;
- hardcode secrets;
- weaken APIs silently;
- make incompatible schema changes without migration;
- begin a later roadmap phase before its prerequisites and approval.

## 5.2 Always

Future work must always:

- inspect the repository and working tree before modification;
- read applicable instructions, contracts, baselines, and phase specifications;
- identify existing components before creating new ones;
- document assumptions;
- preserve unrelated human work;
- use professional, domain-accurate naming;
- use strong typing;
- keep modules cohesive and readable;
- keep quantitative units and timestamp semantics explicit;
- validate external and persisted data;
- preserve chronological ordering;
- preserve auditability and reproducibility;
- record provenance and version identities;
- use immutable or append-only evidence where required;
- add failure-path tests;
- verify migrations and rollbacks;
- update relevant documentation in the same approved change;
- stop at the approved phase boundary;
- report unresolved decisions without guessing.

## 5.3 Backward compatibility

Backward compatibility is required where an approved consumer, stored
historical artifact, or public contract depends on existing behavior.

Compatibility may be intentionally broken only with:

- explicit approval;
- a versioned replacement;
- consumer impact analysis;
- migration and rollback procedures;
- preserved historical interpretation;
- an announced deprecation or cutover path when applicable.

Backward compatibility never requires preserving a security vulnerability,
fabricated claim, or constitutionally invalid behavior. Such cases require an
explicit reviewed resolution.

## 5.4 Performance

Correctness precedes optimization.

Performance work must:

- respond to measured behavior;
- use a reproducible benchmark or operational metric;
- preserve semantic equivalence;
- preserve determinism and provenance;
- document the before/after evidence;
- avoid weakening validation for speed.

No universal latency, throughput, or resource target is created by this
constitution. Applicable budgets must come from an approved requirement.

---

# 6. Repository Rules

## 6.1 Repository inspection

Before changing anything:

1. inspect `git status`;
2. identify repository-level instructions;
3. inspect relevant source, tests, migrations, contracts, and documentation;
4. identify existing implementation under alternate names;
5. distinguish user changes from task changes;
6. state the intended scope.

Pre-existing changes belong to the user unless proven otherwise. They must not
be overwritten, reformatted, staged, committed, or deleted as incidental work.

## 6.2 Adding modules

A new module is permitted only when:

- the current phase authorizes the responsibility;
- no existing module provides the required behavior;
- the responsibility has a clear name and boundary;
- its inputs, outputs, dependencies, failure semantics, and source of truth are
  understood;
- it does not create a speculative registry, factory, abstraction, or service;
- it has tests and documentation proportional to its risk.

Prefer a small set of cohesive modules over one oversized file or many
single-purpose wrappers with no semantic boundary.

## 6.3 Contracts

Contracts must:

- define what a domain object means, not how a technology implements it;
- identify required and optional fields;
- define availability and absence;
- define source of truth;
- define cross-field invariants;
- distinguish failure from valid negative outcomes;
- support deterministic ordering and versioning;
- preserve future extensibility without speculative fields.

Frozen contracts are not edited as part of routine implementation.

## 6.4 Database migrations

Every schema change must:

- be implemented through the approved migration tool;
- have one clear purpose;
- follow the existing revision chain;
- preserve existing data and immutable evidence;
- use exact types and constraints consistent with domain contracts;
- include indexes and uniqueness constraints justified by access and integrity;
- include a tested upgrade path;
- include a safe downgrade or documented non-destructive rollback strategy;
- avoid destructive data rewriting unless explicitly authorized;
- update persistence models and tests atomically with the migration.

Application startup must not silently ignore a migration failure.

## 6.5 Configuration

- Configuration uses environment variables or approved configuration
  artifacts.
- Only values actually used by the system are declared.
- Secrets are never committed.
- Local defaults must be clearly safe for local development.
- Production configuration must validate required values and reject insecure
  placeholders.
- Quantitative parameters are versioned research or policy configuration, not
  informal environment defaults.

## 6.6 Testing

Every material behavior requires tests appropriate to its layer.

Applicable test categories include:

- formula and unit tests;
- metadata and contract validation;
- chronology and point-in-time tests;
- prefix-invariance tests;
- warm-up and missing-data tests;
- deterministic repeatability;
- hash and provenance verification;
- idempotency and immutability;
- transaction rollback;
- database integration and migration tests;
- API schema and structured-error tests;
- frontend component and API integration tests;
- startup and configuration validation;
- security and request-limit tests;
- live-provider validation when the approved phase requires it.

A passing happy-path test is insufficient when failure could fabricate,
misstate, overwrite, leak, or expose evidence.

## 6.7 Documentation

Documentation must be updated when an approved change affects:

- public or internal contracts;
- configuration;
- startup or deployment;
- database schema;
- APIs;
- research methodology;
- artifact identity;
- operational procedures;
- user-visible meaning.

Documentation must describe implemented reality. It must not claim unimplemented
features, unverified performance, or future approvals.

New documents must not duplicate an existing source of truth. They must state
their authority, scope, status, dependencies, and relationship to frozen
artifacts.

## 6.8 Review requirements

Every implementation review must verify:

- authorized scope and roadmap phase;
- applicable contracts and baselines;
- reuse of existing functionality;
- point-in-time integrity;
- deterministic behavior;
- provenance completeness;
- failure semantics;
- historical immutability;
- migration safety;
- API and consumer compatibility;
- test adequacy;
- documentation accuracy;
- absence of secrets and temporary artifacts;
- explicit unresolved decisions.

Quantitative review and software review are both required when a change affects
research meaning.

## 6.9 Git safety

- Never delete, rename, or rewrite existing files unless explicitly authorized.
- Stage only intentional task changes.
- Exclude secrets, local databases, dumps, caches, logs, virtual environments,
  generated temporary files, and developer-specific state.
- Do not alter historical evidence to obtain a clean diff.
- Use professional, scoped commits.
- Verify the working tree after any requested commit.
- Tag or release only under explicit authorization.

---

# 7. Development Workflow

Every roadmap phase follows this sequence:

```text
Research
    ↓
Architecture
    ↓
Contracts
    ↓
Implementation
    ↓
Testing and Validation
    ↓
Documentation and Evidence
    ↓
Human Review and Approval
```

No stage is skipped.

## 7.1 Research

Before implementation, establish:

- the problem being solved;
- source evidence;
- approved scope;
- hypotheses and non-claims;
- unresolved quantitative decisions;
- adequacy requirements;
- leakage and data-snooping risks;
- evaluation and stopping rules where applicable.

If research is not required for a purely mechanical change, the change must
still identify the approved evidence or requirement that authorizes it.

## 7.2 Architecture

Confirm:

- the governing target layer;
- responsibility and boundary;
- existing components to reuse;
- inputs and outputs;
- dependencies and prerequisites;
- failure behavior;
- persistence and lifecycle implications;
- compatibility and migration impact.

Architecture is frozen before implementation.

## 7.3 Contracts

Freeze the semantic interface:

- object identity;
- fields and types;
- availability;
- invariants;
- provenance;
- version;
- failure and absence;
- extensibility boundary.

No code should force an unresolved contract decision.

## 7.4 Implementation

Implementation must:

- remain within the authorized milestone;
- follow the approved architecture and contracts exactly;
- make the smallest coherent change;
- extend rather than duplicate;
- preserve existing evidence and behavior outside scope;
- stop if a prerequisite is missing.

## 7.5 Testing and validation

Testing proves software behavior. Validation proves that the behavior satisfies
the approved quantitative and data contracts.

Both are required where applicable.

Live validation:

- uses real evidence;
- records exact source and time;
- never fabricates a success response;
- reports provider limitations and data-quality findings honestly;
- does not substitute for historical research adequacy.

## 7.6 Documentation and evidence

Before review:

- update required technical documentation;
- record files and migrations changed;
- record tests and commands run;
- record real validation evidence;
- record configuration and result hashes;
- record assumptions, exclusions, and remaining blockers;
- confirm prohibited scope was not implemented.

## 7.7 Human review and approval

Completion of a phase does not authorize the next phase.

After an approved phase or milestone:

- provide a complete factual summary;
- stop;
- wait for explicit approval;
- do not infer approval from silence, prior authority, or a successful test
  result.

---

# 8. Quality Gates

A feature or milestone is not complete until every applicable gate passes.

## Gate 1 — Scope

- The work is explicitly authorized.
- All prerequisites are complete.
- No later-phase functionality is included.
- Out-of-scope changes are absent.

## Gate 2 — Architectural alignment

- The approved architecture is followed.
- Existing KEEP infrastructure is preserved.
- No duplicate or speculative architecture is introduced.
- Domain boundaries and dependencies are explicit.

## Gate 3 — Contract compliance

- Inputs and outputs match approved contracts.
- Required and optional semantics are enforced.
- Absence and failure states are distinct.
- Contract and schema versions are recorded.
- Compatibility is verified.

## Gate 4 — Research integrity

- Point-in-time correctness is demonstrated.
- Chronology is preserved.
- Leakage controls pass.
- Random time-series splitting is absent.
- Data snooping and multiplicity are addressed where applicable.
- Protected evidence remains protected.
- Claims do not exceed measured evidence.

## Gate 5 — Determinism and reproducibility

- Repeated execution produces identical semantic results.
- Seeds and software versions are recorded where applicable.
- Canonical hashes verify.
- Source and result provenance is complete.
- Replay succeeds when required.

## Gate 6 — Data and persistence integrity

- Source data is validated.
- Missing or invalid evidence fails closed.
- Writes are transactional.
- Idempotency is verified where required.
- Immutable records are not overwritten.
- Supersession preserves history.
- Migration and rollback behavior are tested.

## Gate 7 — Software quality

- Code is typed, modular, readable, and professionally named.
- No unnecessary abstraction or optimization is present.
- Static checks, compilation, linting, and type checking pass as applicable.
- Unit and integration tests pass.
- Failure paths are covered.
- No known build or startup blocker remains.

## Gate 8 — Security and operations

- No secrets or credentials are committed.
- Configuration validation passes.
- Input and request limits are enforced.
- Logs avoid sensitive data.
- Health checks represent real dependencies.
- Production defaults are safe.
- Observability is sufficient for the approved capability.

## Gate 9 — Performance

- Approved performance budgets are met, if defined.
- Measurements are reproducible.
- Optimization does not change meaning or bypass validation.
- Resource behavior is acceptable for the approved deployment scope.

## Gate 10 — Documentation

- Documentation matches the implementation.
- Commands and configuration are factual.
- Migrations and operational procedures are recorded.
- Limitations and unresolved decisions are explicit.
- No future capability is represented as complete.

## Gate 11 — Review evidence

- Changed files are enumerated.
- Test and validation results are reported.
- Hashes and provenance are reported where applicable.
- Risks and rollback are documented.
- The working tree contains only intentional task changes.
- Required human review is complete.

---

# 9. Definition of Done

A roadmap item, phase, milestone, or feature is **Done** only when every
applicable statement below is true.

## Authorization and scope

- [ ] The work had explicit human authorization.
- [ ] All implementation-order prerequisites were complete.
- [ ] The implemented scope matches the approved milestone exactly.
- [ ] No prohibited or later-phase behavior was added.

## Research and semantics

- [ ] The governing research question or requirement is approved.
- [ ] Quantitative parameters and definitions were not invented.
- [ ] Applicable hypotheses, metrics, and non-claims are recorded.
- [ ] Point-in-time and leakage analysis is complete.
- [ ] The implementation does not imply unsupported predictive, causal, or
      economic value.

## Architecture and contracts

- [ ] Applicable governance, architecture, contracts, baselines, and risks were
      reviewed.
- [ ] Existing functionality was reused where semantically appropriate.
- [ ] The implementation follows approved boundaries.
- [ ] Contracts define meaning independently of technology.
- [ ] All fields, availability rules, invariants, and failure states comply.
- [ ] Any approved contract change has rationale, impact, migration, rollback,
      historical treatment, versioning, and approval.

## Implementation

- [ ] Code is modular, typed, readable, and narrowly scoped.
- [ ] Configuration is externalized appropriately.
- [ ] No secrets or unsafe defaults were introduced.
- [ ] No historical evidence was deleted or rewritten.
- [ ] No unnecessary dependency, abstraction, service, or optimization was
      added.
- [ ] APIs remain compatible or have an approved migration.

## Data, determinism, and provenance

- [ ] Source evidence is valid and its limitations are recorded.
- [ ] Availability timestamps and chronology are enforced.
- [ ] Warm-up, gaps, missing data, and ambiguity fail closed.
- [ ] Decimal, rounding, ordering, and seed policies are explicit.
- [ ] Identical inputs reproduce identical semantic outputs.
- [ ] Configuration, source, provenance, and result hashes verify.
- [ ] The full lineage to source evidence is retrievable.

## Persistence and migrations

- [ ] Schema changes use the approved migration system.
- [ ] Upgrade behavior is tested.
- [ ] Rollback or downgrade behavior is safe and documented.
- [ ] Transactions roll back completely on failure.
- [ ] Idempotency is verified where applicable.
- [ ] Active promotion occurs only after successful verification.
- [ ] Superseded records remain auditable.

## Testing and validation

- [ ] Formula and unit tests pass.
- [ ] Integration tests pass.
- [ ] Failure-path tests pass.
- [ ] Deterministic repeatability is verified.
- [ ] Provenance and hash verification tests pass.
- [ ] Prefix invariance and chronology tests pass where applicable.
- [ ] API, frontend, migration, configuration, and security tests pass where
      applicable.
- [ ] Required live validation was completed with factual results.
- [ ] No protected evidence was accessed improperly.

## Operations and documentation

- [ ] Startup and health behavior is verified.
- [ ] Observability represents real state.
- [ ] Performance meets any approved budget.
- [ ] Documentation reflects implemented reality.
- [ ] Changed files, migrations, dependencies, and tests are reported.
- [ ] Assumptions, exclusions, limitations, and remaining blockers are
      reported.

## Review and closure

- [ ] No accidental, sensitive, generated, or unrelated files are included.
- [ ] Software and quantitative review requirements are satisfied.
- [ ] The final summary is evidence-based and makes no unsupported claims.
- [ ] Human approval has been recorded when the phase requires it.
- [ ] Work stopped at the approved boundary.

If an applicable item is false, the work is not Done.

---

# 10. Governance and Change Control

## 10.1 Constitutional changes

This constitution may change only through an explicitly approved governance
change containing:

- the exact section affected;
- reason for change;
- evidence that the current rule is insufficient or conflicting;
- impact on existing contracts, code, data, research, artifacts, APIs,
  deployment, and future phases;
- compatibility and migration plan;
- rollback plan;
- treatment of historical evidence;
- explicit human approval;
- a new constitution version or recorded revision identity.

No implementation task implicitly amends this constitution.

## 10.2 Exceptions

There are no silent exceptions.

An approved exception must be:

- explicit;
- narrowly scoped;
- time- or milestone-bounded where appropriate;
- documented with risk and compensating controls;
- prohibited from rewriting historical evidence;
- reviewed before it becomes a general rule.

## 10.3 Quantitative change control

Any change to a feature formula, label, target, split, embargo, purge,
evaluation metric, threshold, calibration definition, model configuration,
ranking meaning, or statistical interpretation requires the process mandated
by the Research Constitution and applicable frozen specification.

Better apparent results are not sufficient justification.

## 10.4 Auditability

Governance decisions must be traceable to:

- the approving human instruction;
- affected documents and versions;
- rationale;
- impact;
- implementation evidence;
- validation evidence;
- migration and rollback status.

---

# 11. Roadmap Reference

This constitution does not redefine, reorder, expand, or approve the AlphaLens
v2 roadmap.

Roadmap scope and execution order remain governed by:

- the approved migration blueprint;
- `IMPLEMENTATION_ORDER.md`;
- the component audit and risk assessment;
- approved phase baselines;
- the current implementation inventory;
- explicit human instructions.

Future implementation documents must:

1. cite this constitution;
2. identify the authorized roadmap item and milestone;
3. cite the applicable architecture, contract, research, baseline, and risk
   sections;
4. list prerequisites;
5. define the stop condition;
6. inherit every applicable quality gate and Definition of Done item.

Documentation of a roadmap item is not implementation. Partial legacy
functionality is not v2 completion. Completion of one phase does not authorize
the next.

---

# 12. Constitutional Commitment

AlphaLens v2 will be built as a disciplined market-intelligence system, not as
a collection of indicators, an opaque AI score, or an automated trading
machine.

Every future contribution must preserve:

- human authority;
- research integrity;
- evidence-first behavior;
- honest uncertainty;
- deterministic computation;
- point-in-time correctness;
- immutable provenance;
- reproducibility;
- explainability;
- secure and maintainable engineering;
- explicit approval boundaries.

When correctness and speed conflict, correctness wins.

When evidence and presentation conflict, evidence wins.

When uncertainty and certainty conflict, uncertainty is disclosed.

When output frequency and opportunity quality conflict, quality wins.

When automation and human authority conflict, human authority wins.

