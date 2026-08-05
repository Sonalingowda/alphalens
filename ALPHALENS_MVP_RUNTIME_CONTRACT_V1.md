# AlphaLens MVP Runtime Contract v1.0

**Contract identifier:** `alphalens_mvp_runtime_contract`

**Contract version:** `1.0.0`

**Status:** Approved and frozen

**Approval date:** 2026-08-04

**Approval authority:** AlphaLens project owner, ARCH-001

This contract governs the legal terminal outcomes of the MVP
`OpportunityIntelligencePipeline`. It does not define detection predicates,
evidence semantics, assessment mathematics, scoring, ranking, or presentation
content. Those remain governed by their separately approved policies.

## 1. Pipeline status model

The pipeline has one immutable ordered stage record per attempted stage. A stage
may be `COMPLETED` or `BLOCKED`. A blocked stage carries a stable reason code.
Stages after a terminal stage MUST NOT execute.

The legal `PipelineRunResult.outcome` values are:

| Outcome | Meaning | Domain artifacts |
| --- | --- | --- |
| `COMPLETED` | Every required stage through detail projection completed | All stage outputs required by the result contract |
| `NO_CANDIDATE` | Detection evaluated valid persisted inputs and found no candidate | `DetectionAttempt(NOT_DETECTED)` only; no candidate or downstream artifacts |
| `UNAVAILABLE` | A required input, repository, policy, or contract gate prevented evaluation | No unavailable domain substitute; immutable blocked stage/run audit only |
| `POLICY_BLOCKED` | A required approved policy is absent, invalid, or unavailable | No policy-dependent downstream artifact; blocked stage/run audit only |
| `NOT_QUALIFIED` | Assessment produced an opportunity but qualification rejected it | Upstream artifacts plus qualification record; no scoring/ranking/dashboard/detail |

`PipelineRunResult` MUST retain the immutable run identifier, ordered stage
records, terminal outcome, trace hash, and every artifact legally produced
before termination. A terminal result MUST be reproducible from its persisted
inputs, policy references, code version, and configuration hashes.

An unavailable artifact is never represented by a fabricated domain object,
neutral value, empty success object, or `WAIT` decision. For `UNAVAILABLE` and
`POLICY_BLOCKED`, the blocked stage record and immutable pipeline audit are
persisted if a pipeline-audit repository is available; the stage's domain
artifact is not persisted. This is the sole legal unavailable behavior.

## 2. Stage contract

### 2.1 Market Context

**Required inputs:** Persisted compatible `MarketSnapshot` and
`FeatureSnapshot`, resolved through repositories and bounded by one evidence
cutoff.

**Required output:** Persisted `MarketContext` with verified lineage, scope,
availability, context definition hash, and audit metadata.

**Success:** Append a `COMPLETED` stage record and continue to Detection.

**Fail closed:** Persist no context substitute; record `UNAVAILABLE` and stop.

**Terminal:** Yes on `UNAVAILABLE`; otherwise no.

### 2.2 Detection

**Required inputs:** Persisted `MarketSnapshot`, `FeatureSnapshot`, and
`MarketContext`, plus the active approved detection policy.

**Required outputs:** Persisted `DetectionAttempt`; persist an
`OpportunityCandidate` only when the approved policy detects one.

**Success with candidate:** Append `COMPLETED` and continue to Evidence.

**Success without candidate:** Persist `DetectionAttempt(NOT_DETECTED)`, do not
persist a candidate, append a terminal `COMPLETED` Detection stage, and stop
with `PipelineOutcome.NO_CANDIDATE`.

**Fail closed:** Persist no candidate; append a blocked Detection stage and stop
with `UNAVAILABLE` or `POLICY_BLOCKED` as applicable.

**Terminal:** Yes for no-candidate, unavailable, and policy-blocked outcomes.

### 2.3 Evidence

**Required inputs:** Persisted `OpportunityCandidate`, `MarketContext`,
`FeatureSnapshot`, `MarketSnapshot`, and the approved evidence policy.

**Required output:** Persisted deterministic `EvidencePackage` with ordered
items, source lineage, timestamps, policy reference, and integrity hashes.

**Success:** Append `COMPLETED` and continue to Assessment.

**Fail closed:** Persist no partial or fabricated evidence package. Append a
blocked Evidence stage and stop with `UNAVAILABLE` or `POLICY_BLOCKED`.

**Terminal:** Yes for fail-closed outcomes; no for successful evidence.

### 2.4 Assessment

**Required inputs:** Persisted candidate, evidence package, market context, and
approved assessment policy.

**Required output:** Persisted canonical `Opportunity` assessment.

**Success:** Append `COMPLETED` and continue to Qualification.

**Fail closed:** Persist no opportunity substitute; append a blocked Assessment
stage and stop with `UNAVAILABLE` or `POLICY_BLOCKED`.

**Terminal:** Yes on failure; otherwise no.

### 2.5 Qualification

**Required inputs:** Persisted opportunity, evidence package, market context,
and approved qualification policy.

**Required output:** Persisted `QualificationRecord`.

**Success qualified:** Append `COMPLETED` and continue to Scoring.

**Success not qualified:** Persist the qualification record, append a terminal
`COMPLETED` stage, and stop with `PipelineOutcome.NOT_QUALIFIED`.

**Fail closed:** Persist no score or downstream projection; stop with
`UNAVAILABLE` or `POLICY_BLOCKED`.

**Terminal:** Yes for not-qualified and failure outcomes.

### 2.6 Scoring

**Required inputs:** Persisted opportunity, qualification, evidence, market
context, and approved scoring policy.

**Required output:** Persisted deterministic `ScoreResult`.

**Success:** Append `COMPLETED` and continue to Ranking.

**Fail closed:** Persist no score substitute; stop with `POLICY_BLOCKED` when
the scoring policy is unavailable, otherwise `UNAVAILABLE`.

**Terminal:** Yes on failure; otherwise no.

### 2.7 Ranking

**Required inputs:** Persisted qualified opportunity set, qualification records,
score results, common cutoff, and approved ranking policy.

**Required output:** Persisted `RankingSnapshot` with complete membership,
ordering, exclusions, and hashes.

**Success:** Append `COMPLETED` and continue to Dashboard Projection.

**Fail closed:** Persist no ranking substitute; stop with `POLICY_BLOCKED` or
`UNAVAILABLE`.

**Terminal:** Yes on failure; otherwise no.

### 2.8 Dashboard Projection

**Required inputs:** Persisted ranking snapshot, qualified opportunities,
lifecycle state where required, and approved dashboard contract.

**Required output:** Persisted `DashboardPage` projection.

**Success:** Append `COMPLETED` and continue to Detail Projection.

**Fail closed:** Persist no partial dashboard page; stop with `UNAVAILABLE` or
`POLICY_BLOCKED`.

**Terminal:** Yes on failure; otherwise no.

### 2.9 Detail Projection

**Required inputs:** Persisted opportunity, market snapshot, indicators,
context, evidence, explanation, lifecycle state, and approved detail contract.

**Required output:** Persisted `OpportunityDetail` projection.

**Success:** Append `COMPLETED`; terminate with `PipelineOutcome.COMPLETED`.

**Fail closed:** Persist no partial detail projection; stop with `UNAVAILABLE`
or `POLICY_BLOCKED`.

**Terminal:** Always: success terminates the run as `COMPLETED`, failure
terminates it as unavailable or policy-blocked.

## 3. Transition rules

The legal MVP transitions are:

```text
Market Context -> Detection
Detection(candidate) -> Evidence
Detection(no candidate) -> NO_CANDIDATE [terminal]
Evidence -> Assessment
Assessment -> Qualification
Qualification(qualified) -> Scoring
Qualification(not qualified) -> NOT_QUALIFIED [terminal]
Scoring -> Ranking
Ranking -> Dashboard Projection
Dashboard Projection -> Detail Projection
Detail Projection(success) -> COMPLETED [terminal]
Any stage(fail closed) -> UNAVAILABLE or POLICY_BLOCKED [terminal]
```

No transition may skip a required stage, execute a downstream stage after a
terminal result, or convert a blocked/unavailable state into a successful
artifact. Replays with identical inputs and policy references MUST preserve the
same transition sequence and trace hash.

## 4. Persistence rule summary

- Valid no-candidate detection persists its `DetectionAttempt` only.
- Successful stages persist their declared domain artifact before the next
  stage begins.
- A failed stage persists no domain artifact or partial artifact.
- Blocked stage/run audit is persisted when the pipeline-audit repository is
  available; absence of that repository does not authorize a substitute domain
  artifact.
- No SQL, mock, placeholder, neutral, fabricated, or future-derived data may
  satisfy any stage.
