# AlphaLens v2 EMA Architecture Reconciliation

**Document type:** Architecture conflict analysis and recommendation

**Scope:** EMA-01 specification-to-repository reconciliation only

**Status:** Recommendation for human approval; no production change is
authorized or implemented

**EMA source reviewed:** The final EMA-01 quantitative specification supplied
in the engineering request, together with the existing EMA-01 Implementation
Contract and EMA-01 Registry Specification

## 1. Executive Summary

EMA-01 should be reconciled primarily by revising its quantitative,
implementation, and registry documents to conform to the existing AlphaLens
feature architecture. The repository should not be redesigned around
`float64`, nullable feature values, feature-level missing-value continuation,
or mutable recursive state.

The existing architecture deliberately standardizes quantitative feature
values as finite `Decimal`, applies one canonical 18-decimal quantum with
`ROUND_HALF_EVEN`, represents legitimate warm-up as output omission, rejects
missing or discontinuous source evidence before feature computation, persists
non-null immutable values, and protects deterministic hashes. These are
cross-feature research-integrity guarantees, not incidental EMA
implementation details. Weakening them for one recursive indicator would
create two incompatible numeric and evidence systems and would affect every
registry, pipeline, persistence, validation, hashing, and consumer boundary.

The EMA documents also over-constrain the architecture by requiring a
registered Close feature that does not exist. The existing registry contract
already supports declared candle-field inputs, and Close is canonical source
evidence rather than a derived calculation. The recommended long-term design
is for EMA-01 to declare `CLOSE` as a required source field, not to create a
new passthrough Close feature merely to satisfy an accidental document
dependency. This follows the Phase 2 catalog's treatment of EMA as consuming
closes and avoids redundant values and provenance.

One targeted architecture decision remains justified. Recursive EMA must
retain exact lineage to its previous EMA value and current canonical Close.
The current value-dependency membership supports feature-to-feature lineage,
while source provenance is principally run-level and timestamp/batch based.
Before implementation, the architecture should either prove that the existing
source snapshot, candle timestamp, source batch, and result hashes uniquely
and durably encode current-Close membership, or add a small typed per-value
source-observation membership. This would be additive provenance evolution,
not a numeric or pipeline redesign.

EMA implementation must remain blocked until revised approved documents also
resolve canonical feature/output identifiers, semantic version, and recursive
initialization-origin policy. The supplied period and EMA equations are not
challenged by this reconciliation and no alternative quantitative parameter
is recommended.

## 2. Architecture Conflicts

### 2.1 Conflict summary

| ID | Conflict | EMA specification or contract position | Repository position | Primary authority | Recommended direction | Estimated impact |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Numeric representation | EMA output and input arithmetic use `float64`. | Feature values and persisted quantitative values use exact `Decimal`; core architecture requires exact arithmetic. | Core Intelligence Specification and existing feature contracts | Revise EMA specification to the existing Decimal policy. | Documentation: medium. Code after approval: low. Redesign alternative: very high. |
| C2 | Rounding and precision | No rounding. | Canonical output quantum is 18 decimal places with `ROUND_HALF_EVEN`; persistence is `Numeric(38,18)`. | Feature contract, persistence model, frozen feature baseline | Revise EMA specification to distinguish 50-digit working precision from one canonical output quantization. | Documentation: medium. Code: low. Redesign alternative: very high. |
| C3 | Warm-up representation | Values before warm-up are null. | Legitimate warm-up is represented by omitted output records; persisted feature values are non-null. | Core feature availability rules, pipeline coverage validation, persistence model | Revise EMA specification to omit pre-warm-up outputs. | Documentation: low. Code: low. Nullable redesign: high. |
| C4 | Missing Close behavior | Emit null for a missing Close, then resume from prior EMA on the next valid observation. | Missing or gapped mandatory source evidence invalidates the continuous run before feature computation. | Core fail-closed/continuity invariants and source snapshot validation | Revise EMA specification to fail the affected run or chain; prohibit silent resume across a gap. | Documentation: medium. Code: low. Sparse recursive redesign: very high. |
| C5 | Invalid candle behavior | Ignore invalid candles according to pipeline validation. | Invalid candles are rejected or quarantined; incomplete candles may be excluded before snapshot construction; valid feature snapshots are consecutive. | Market-data validation and intraday pipeline | Clarify the EMA specification: EMA never receives invalid candles and cannot skip them. | Documentation: low. Code: none. |
| C6 | Close dependency | EMA must consume a registered feature named Close and cannot read candle Close directly. | No registered Close feature exists; feature metadata already declares required candle fields. | Existing registry/contracts and catalog architecture | Revise EMA documents to declare canonical candle `CLOSE` as source input unless a separately approved Close primitive is justified. | Documentation: medium. Code: low. Adding Close instead: medium-to-high and broader scope. |
| C7 | Output schema | EMA specifies a two-field object with feature label and nullable float value. | Pipeline values require definition identity, version, output name, timestamp, availability, finite Decimal value, ordering, provenance, and hash coverage. | Feature/pipeline contracts and EMA implementation contract | Revise EMA quantitative output section to bind one quantitative output to the canonical pipeline envelope. | Documentation: medium. Code: low. |
| C8 | Identifier/version completeness | `EMA-01` is provided as Feature Name, but stable registry identifier, output identifier, and semantic version are not concretely frozen. | Registry requires lowercase-snake-case identifiers, semantic versions, unique outputs, and implementation-metadata equality. | Registry contract and metadata validation | Freeze exact identifiers and version in a revised EMA specification; do not infer them in implementation. | Documentation: medium. Code: blocked until resolved. |
| C9 | Recursive initialization origin | Initialization uses the first period of Close values without defining the canonical series origin or snapshot-start policy. | Recursive features must declare seed, first-valid observation, and reproducible history; backfilling earlier data can otherwise change all later EMA values. | Core specification and catalog recursive-start risk | Add a canonical initialization-origin and snapshot compatibility policy without changing period or formula. | Documentation/research governance: high. Code: medium. |
| C10 | Recursive state | EMA persistence says to persist state; implementation contract describes loading previous EMA. | Current pipeline computes deterministic series from an immutable source snapshot and persists immutable outputs, not mutable algorithm state. | Pipeline and persistence architecture | Treat prior EMA as deterministic value lineage, not mutable state; compute within the pipeline's immutable snapshot model. | Documentation: medium. Code: medium. Mutable-state alternative: high. |
| C11 | Per-value provenance | EMA needs exact previous-EMA and current-Close provenance. | Feature dependency memberships can reference prior feature values; current raw-candle membership is primarily represented through timestamp, source batch, snapshot, and run evidence. | EMA implementation contract and current persistence infrastructure | Prove current evidence is sufficient or add typed per-value source membership. | Architecture decision: medium. Possible migration/code impact: medium. |
| C12 | Hashing language | EMA says hashing behavior must not change. | Adding a registry member necessarily creates a new registry hash, pipeline version, and result hashes, while the hash algorithm and historical hashes remain unchanged. | Registry/pipeline immutability rules | Clarify that algorithms and historical identities remain unchanged, but new content receives new hashes. | Documentation: low. Code: low. |
| C13 | Dependency-contract contradiction | EMA implementation/registry documents require version-pinned Close, while the quantitative specification gives no Close feature version. | Version-pinned dependencies must resolve exactly and appear earlier in registry order. | EMA contracts and registry schema | Remove the artificial feature dependency or separately specify and approve it completely. | Documentation: medium. Adding dependency: medium-to-high. |
| C14 | Incremental complexity versus validation | EMA contract targets constant-time updates using previous EMA; pipeline validates prefix invariance from isolated snapshot prefixes. | The pipeline must reproduce a complete deterministic series and verify every prefix; persisted predecessor lookup is not currently the formula interface. | Pipeline architecture and EMA contract | Specify linear batch execution with constant work per eligible observation, using deterministic in-run predecessor state. | Documentation: low. Code: medium. |

### 2.2 Numeric contract conflict

The supplied EMA specification's `float64` and no-rounding rules cannot be
represented faithfully by `FeatureValue`, `PipelineFeatureValue`, registry
Decimal metadata, deterministic Decimal serialization, or
`EngineeredFeatureRecord.feature_value`. Converting the float result to
Decimal for persistence would introduce an unstated conversion and rounding
rule. Persisting a parallel float column would create a second canonical
numeric policy and change consumer, hashing, validation, and database
contracts.

The authoritative architecture requires exact arithmetic unless a separately
approved method explicitly authorizes floating point and its serialization
policy. The EMA specification does not define platform-level float evaluation,
serialization, non-associativity controls, or cross-runtime replay evidence.
It therefore cannot override the broader deterministic numeric architecture
merely by naming `float64`.

### 2.3 Null and missing-data conflict

The repository distinguishes three states:

- insufficient leading warm-up, represented by no output;
- invalid or discontinuous mandatory evidence, which fails closed; and
- a valid emitted feature value, which is finite and non-null.

The EMA specification collapses the first two states into null output records
and permits recursive continuation after a missing Close. That would require
nullable in-memory values, nullable persistence, a sparse timestamp contract,
new coverage validation, new hash serialization for null, new resumption
semantics, and consumer changes. It would also change the elapsed-time meaning
of a period based on consecutive observations.

### 2.4 Close dependency conflict

The requirement for registered Close originated in the EMA implementation
and registry documents even though no Close definition, version, output
identity, registry entry, implementation, or persistence evidence exists.
The Phase 2 catalog describes EMA inputs as closes, not as an approved derived
Close feature. Existing feature metadata intentionally supports candle fields
for primitive calculations.

Reading the exact Close of the canonical current candle is not duplicate
feature logic. It is source consumption. This differs from ATR, where the
registered `true_range` dependency prevents recomputing an approved derived
formula. A passthrough Close feature would duplicate an already canonical
market value and would add values, memberships, hashes, ordering, registry
scope, pipeline coverage, persistence volume, and an additional release gate
without adding quantitative meaning.

### 2.5 Recursive-origin conflict

The phrase "first period Close values" is not reproducible until "first" has
a canonical meaning. It could mean the first values in a transient request,
the first values in the current database, the first values in an immutable
source snapshot, or the first values after an approved start boundary.

This matters more for EMA than for a bounded rolling feature. If earlier
history is later backfilled, a recursive seed at a newly earlier point can
change every subsequent EMA. That would violate immutable value reuse and
prefix expectations even though no future suffix was used. A canonical
initialization-origin policy is therefore a quantitative/governance
prerequisite, not an implementation convenience.

## 3. Root Cause Analysis

### 3.1 Document sequencing

The EMA implementation contract and registry specification were produced
before an exact EMA quantitative artifact was present in the repository. They
correctly refused to invent period, seed, version, and precision, but they
introduced a registered Close dependency as an architectural assumption.
The later supplied quantitative specification then selected float and null
semantics that conflict with the repository contracts those documents were
intended to preserve.

The result is not an EMA formula dispute. It is a contract-ordering failure:
quantitative meaning, architecture compatibility, implementation contract,
and registry release were not frozen in dependency order.

### 3.2 Conflation of mathematical absence with stored null

"No EMA exists before warm-up" and "persist a null EMA value" were treated as
equivalent. They are not equivalent in AlphaLens. Omission is an explicit
availability state; null would be a persisted quantitative output with no
value. The existing pipeline was designed to validate expected omissions from
per-output minimum observations.

### 3.3 Generic indicator conventions imported into a governed system

`float64`, null propagation, and resume-after-missing behavior are common in
dataframe and technical-analysis libraries. AlphaLens instead prioritizes
exact evidence, deterministic serialization, explicit continuity, and
fail-closed research inputs. The supplied rules appear to reflect a generic
indicator runtime rather than the approved feature-platform invariants.

### 3.4 Dependency abstraction applied too broadly

ATR established a valid pattern for consuming registered derived evidence:
ATR depends on the nontrivial, versioned True Range calculation. That pattern
was extended to Close without distinguishing a derived feature from a raw
canonical source field. The abstraction would create duplication rather than
reuse.

### 3.5 Recursive history not treated as part of identity

The supplied EMA specification defines a seed formula but not the identity of
the history to which it is applied. For recursive features, source origin,
continuity, seed membership, and restart behavior are part of reproducibility.
They must be frozen alongside period and formula.

### 3.6 Ambiguous use of "unchanged hashing"

Preserving hashing behavior was interpreted as preserving hash values. A
registry hash is content-addressed; adding EMA must change the current
registry hash. What must remain unchanged is the approved canonicalization and
hash algorithm for a given schema, plus every historical registry/pipeline
identity.

## 4. Recommended Resolution for Each Conflict

### 4.1 C1 and C2 — Decimal, precision, and rounding

**Conflict:** The EMA specification requires `float64` and no rounding, while
the repository requires Decimal working arithmetic and canonical output
quantization.

**Authoritative source:** The Core Intelligence Specification's exact
arithmetic invariant, `FEATURE_VALUE_QUANTUM`, `quantize_feature_value`,
registry Decimal metadata, existing Tier-A/ATR definitions, and
`Numeric(38,18)` persistence.

**Recommendation:** Revise the EMA quantitative specification to use the
existing feature numeric policy: Decimal working precision 50, canonical
quantum `0.000000000000000001`, and `ROUND_HALF_EVEN` at the output boundary.
The revised document must state how the already approved smoothing constant
is represented in Decimal and when intermediate results are or are not
quantized. This reconciliation does not select a different period, smoothing
constant, seed, or equation.

**Why:** One exact numeric policy preserves byte-repeatable results,
cross-feature compatibility, canonical serialization, and current persistence
without a second execution system. Recursive float error would otherwise
propagate indefinitely and be difficult to reproduce across runtimes.

**Repository impact:** Documentation changes to the EMA quantitative and
implementation contracts. After approval, a focused EMA definition and tests
can reuse current numeric helpers. No core numeric or database redesign is
recommended. Estimated implementation impact is low after the document gate;
the rejected float architecture has very high cross-repository impact.

### 4.2 C3 — Warm-up representation

**Conflict:** The EMA specification requires nulls before the twentieth Close;
the pipeline expects omission until `minimum_observations` is satisfied.

**Authoritative source:** Core warm-up rules, `FeatureOutputMetadata`, pipeline
coverage validation, non-null `FeatureValue`, and non-null engineered-feature
persistence.

**Recommendation:** Revise the EMA specification so no EMA output record is
emitted before the approved first-valid observation. Preserve the approved
twenty-Close boundary exactly; change only its engineering representation from
null records to omission.

**Why:** Omission distinguishes legitimate unavailability from an invalid
numeric output, requires no nullable schema, and already has deterministic
coverage validation.

**Repository impact:** Documentation and EMA-specific tests only. No
persistence migration is required. Estimated impact is low.

### 4.3 C4 and C5 — Missing, invalid, and discontinuous evidence

**Conflict:** EMA would emit null for missing Close, then resume from earlier
state, and would ignore invalid candles. The current pipeline requires a
continuous valid snapshot and fails closed on missing or invalid mandatory
evidence.

**Authoritative source:** Core point-in-time, continuity, completed-observation,
and fail-closed invariants; candle/source snapshot validation; catalog rule
that a gap fails the run rather than resetting or segmenting a window.

**Recommendation:** Revise EMA missing-data behavior. A missing or gapped Close
within the required recursive chain makes the affected EMA run unavailable;
the implementation must not emit a null, skip the timestamp, resume across the
gap, fill, interpolate, or silently reseed. Incomplete candles remain excluded
before snapshot construction. Invalid canonical candidates remain rejected or
quarantined and never reach EMA.

**Why:** Resuming after a gap changes the observation spacing and recursive
meaning. It also produces output whose predecessor is not the immediately
preceding eligible timeframe observation, conflicting with continuity and
provenance.

**Repository impact:** EMA documents and negative tests. Existing pipeline
validation can be reused unchanged. Estimated impact is low-to-medium. The
rejected sparse/null continuation design would have very high impact across
contracts, coverage, persistence, hashing, and consumers.

### 4.4 C6 and C13 — Close as source input, not feature dependency

**Conflict:** EMA documents require a registered Close feature that does not
exist or have a version, while current contracts support raw candle-field
inputs.

**Authoritative source:** Existing `CandleField.CLOSE` metadata, validated
source snapshots, Phase 2 catalog EMA input description, and the distinction
between source evidence and derived registered dependencies.

**Recommendation:** Revise the EMA quantitative, implementation, and registry
documents to declare canonical candle Close as a required source field. Remove
the mandatory registered-Close dependency and its unresolved version. EMA
must read Close only from the validated immutable source snapshot supplied by
the pipeline, never from an unvalidated candle or independent query.

**Why:** This follows existing interfaces, introduces no duplicate
calculation, avoids a meaningless passthrough feature, and retains direct
source provenance. True Range remains the correct comparison: it is a derived
feature worth versioning and reusing; Close is already canonical evidence.

**Repository impact:** Medium documentation impact because two EMA contracts
currently assert registered Close. Low implementation impact after approval.
No new Close feature, registry output, pipeline values, or persistence rows
are recommended. If governance insists on registered Close, that must become a
separate approved primitive-feature task with medium-to-high repository and
test impact before EMA can proceed.

### 4.5 C7 and C8 — Output envelope and canonical identity

**Conflict:** The supplied output is a minimal nullable float object and uses
`EMA-01` without concretely freezing registry-safe definition/output
identifiers or a semantic version.

**Authoritative source:** `FeatureDefinitionMetadata`, `FeatureOutputMetadata`,
`FeatureValue`, `PipelineFeatureValue`, registry uniqueness/version rules, and
the existing EMA implementation/registry output envelope.

**Recommendation:** Issue a revised EMA quantitative specification that names
the exact stable lowercase-snake-case definition identifier, exact output
identifier, semantic definition version, units, and domain. It must define one
finite Decimal quantitative output after warm-up and bind it to the existing
pipeline envelope: definition/version, output name, candle timestamp,
`available_at`, value, dependencies, provenance, ordering, and result hash.

**Why:** Implementers cannot choose identifiers or versions without changing
registry identity and historical evidence. The pipeline envelope is required
for point-in-time correctness and reproducibility; it is not an additional EMA
quantitative output.

**Repository impact:** Medium documentation/governance impact and low code
impact once resolved. Implementation remains blocked until these identities
are approved. This reconciliation intentionally does not invent them.

### 4.6 C9 — Canonical recursive initialization origin

**Conflict:** The approved seed rule names the first twenty Closes but does not
define the immutable series origin that makes those observations "first."

**Authoritative source:** Core recursive-feature contract, catalog
recursive-start sensitivity warning, immutable source snapshots, and
historical evidence rules.

**Recommendation:** Amend the EMA quantitative specification with a canonical
initialization-origin and restart policy. It must bind every EMA series to an
immutable source-snapshot identity or another approved canonical origin,
retain the exact ordered twenty-Close seed membership, define compatibility
when earlier history is later added, and prohibit implicit reseeding. No date
or additional numeric parameter is recommended here.

If the canonical origin changes, outputs must belong to a new approved
definition/pipeline evidence identity rather than conflict with existing
immutable values.

**Why:** Without origin identity, identical timestamps and formula parameters
can yield different recursive paths depending on how much earlier data was
loaded. That defeats reproducibility even though future isolation is intact.

**Repository impact:** High specification/governance importance. Medium EMA
implementation and provenance impact. Core architecture need not change if
the revised policy binds execution to immutable snapshots and versions.

### 4.7 C10 and C14 — Recursive execution and state

**Conflict:** EMA documents imply loading persisted previous EMA state for
each update, while the current feature interface computes an isolated series
from a validated immutable candle snapshot and pipeline prefix checks.

**Authoritative source:** `IntradayFeatureDefinition.compute`, source snapshot
integrity, registry-ordered execution, pipeline prefix-invariance validation,
and immutable run persistence.

**Recommendation:** Revise the implementation contract to define linear batch
execution with constant numeric work per eligible observation. The previous
EMA used during a run is deterministic in-run predecessor state. Persisted EMA
values are immutable evidence and may support exact replay verification, but
they must not become a mutable cache that changes computation semantics.

Incremental operation may later reuse a verified predecessor only when the
same definition, parameter set, source origin, symbol, timeframe, continuity,
registry, pipeline, and predecessor hash all match. Otherwise the run must
recompute from its approved seed.

**Why:** This fits the current interface, makes prefix invariance directly
testable, and avoids database state becoming an undeclared numeric input.

**Repository impact:** Medium revision to the EMA implementation contract and
medium EMA-specific implementation/testing. No general pipeline interface
change is recommended.

### 4.8 C11 — Exact source and predecessor provenance

**Conflict:** EMA requires per-value previous-EMA and current-Close lineage;
current feature dependencies link engineered values, while raw source evidence
is retained through snapshot, timestamp, batch, and run memberships rather
than a general typed per-value source link.

**Authoritative source:** Core provenance invariant, EMA implementation
contract, `FeatureValueDependencyRecord`, `EngineeredFeatureRecord` source
batch/timestamp fields, and source snapshot hashes.

**Recommendation:** Perform a focused provenance sufficiency review before
implementation. The review should prove whether the combination of output
timestamp, symbol/timeframe, source ingestion batch, immutable source snapshot
membership, source data/provenance hashes, and pipeline run uniquely retains
the exact current candle used by each EMA value.

If that proof is incomplete, add one versioned, typed per-value source
observation membership capable of referencing the current canonical candle.
Continue to use feature-value dependency membership for the previous EMA
lineage. Do not create a Close feature solely as a provenance workaround.

**Why:** Provenance should model the true dependency type. A source candle is
not an engineered feature, and pretending otherwise introduces semantic debt.

**Repository impact:** Review-only if existing evidence proves sufficient.
Otherwise medium impact: additive persistence model and migration, canonical
hash coverage, persistence verification, live validation, and focused tests.
Historical rows remain unchanged and readable.

### 4.9 C12 — Hash preservation

**Conflict:** "Do not modify hashing behavior" could be read as requiring the
current registry/result hash values to remain unchanged after adding EMA.

**Authoritative source:** Content-addressed registry and pipeline architecture,
immutable pipeline `2.0.0`/`2.1.0` history, and canonical result hashing.

**Recommendation:** Clarify the EMA documents: existing hash algorithms,
canonical serialization rules, historical registry hashes, historical
pipeline versions, and historical result hashes remain unchanged. A new EMA
registry member must create a new registry hash and new pipeline version, and
new outputs must produce new result hashes under the approved hash schema.

**Why:** A content hash that does not change when content changes would be
incorrect. Historical identity preservation and new-release identity are
compatible requirements.

**Repository impact:** Low documentation and implementation impact. No hash
algorithm redesign is recommended.

## 5. Required Future Changes

### 5.1 Required document changes

No existing document should be edited during this reconciliation task. Before
EMA implementation, governance should issue approved successor revisions for:

1. **EMA-01 Quantitative Specification** — replace float/null/resume semantics
   with the repository Decimal, output-omission, and continuity policies;
   freeze exact identifiers/version/domain; and add canonical initialization
   origin and restart behavior without changing approved period or equations.
2. **EMA-01 Implementation Contract** — replace registered Close with validated
   canonical source Close, align recursive execution with immutable snapshot
   computation, and distinguish in-run predecessor state from persisted audit
   evidence.
3. **EMA-01 Registry Specification** — remove the unresolved registered-Close
   dependency, declare `CLOSE` as a source field, freeze exact definition and
   output identities from the revised quantitative specification, and clarify
   hash/version release behavior.

Each successor must identify what it supersedes and retain the original
artifact for audit. The earlier documents must not be silently rewritten.

### 5.2 Required architecture decision

Approve one of these provenance outcomes before coding:

- **Preferred if proven sufficient:** formally document that current
  timestamp/batch/snapshot/run memberships uniquely retain exact current-candle
  dependency per EMA output; or
- **Additive evolution if necessary:** define a typed per-value source-candle
  membership and its canonical ordering/hash coverage.

This decision concerns evidence representation only. It must not alter EMA
mathematics.

### 5.3 Expected later implementation changes

After approvals, the anticipated in-scope implementation may include:

- one EMA-01 feature definition using existing Decimal and source validation;
- registry metadata for recursive history, approved source fields, output,
  warm-up, availability, and version;
- integration into a new immutable registry and pipeline release;
- deterministic in-run recursive computation from the approved seed;
- previous-EMA provenance membership and exact current-candle provenance;
- immutable value persistence using existing non-null Decimal storage;
- live-validation count/provenance extensions; and
- focused EMA formula, initialization, continuity, prefix, future-isolation,
  ordering, hashing, persistence, and regression tests.

If typed source membership is approved, an additive persistence migration and
corresponding model/verification tests will also be required. No nullable or
float feature-value migration is recommended.

### 5.4 Changes explicitly not required

The recommended reconciliation does not require:

- changing EMA period or equations;
- adding a registered Close feature;
- changing existing ATR or True Range definitions;
- making `FeatureValue` nullable;
- adding float feature-value storage;
- weakening candle or continuity validation;
- changing historical registry/pipeline hashes;
- redesigning APIs; or
- implementing EMA-02 or any other feature family.

## 6. Recommended Implementation Sequence

1. **Approve this reconciliation direction.** Confirm that AlphaLens numeric,
   warm-up, and continuity architecture remains authoritative for EMA-01.
2. **Issue a successor EMA quantitative specification.** Preserve the approved
   period and equations, while resolving Decimal representation, output
   quantization, omission, fail-closed gaps, identifiers/version, and canonical
   seed origin.
3. **Issue successor implementation and registry contracts.** Align them with
   source Close, immutable snapshot execution, exact output identity, and new
   release hashing semantics.
4. **Complete the provenance sufficiency review.** Approve existing evidence
   as sufficient or freeze the additive typed source-membership contract.
5. **Freeze exact validation fixtures.** Cover seed membership, first-valid
   observation, recursive values, Decimal boundaries, gaps, invalid input,
   prefix invariance, future isolation, snapshot-origin compatibility, and
   provenance.
6. **Authorize EMA-01 implementation only.** Do not combine it with a Close
   primitive, EMA-02, MACD, or other feature family.
7. **Implement through existing modules.** Reuse feature contracts, registry,
   pipeline validation, source snapshots, dependency memberships, persistence,
   activation, supersession, live validation, and hashing.
8. **Assign new immutable release identities.** Preserve historical registry
   and pipeline versions while adding EMA to a new registry hash and pipeline
   version.
9. **Validate proportionally.** Run static checks, compilation, focused EMA
   tests, existing feature regressions, persistence/migration validation where
   applicable, and the full backend suite.
10. **Perform architecture audit and freeze.** Verify EMA-only scope,
    provenance completeness, no quantitative drift, no historical mutation,
    and no predictive claim before activation.

No dependent EMA-family or Phase 2 feature should begin until EMA-01 is
reviewed and frozen under the reconciled contracts.

## 7. Risks

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| Silent quantitative drift during reconciliation | Decimal EMA may differ from the supplied float path, especially recursively. | Treat the successor numeric policy as an explicit human-approved quantitative revision with exact fixtures; never call it a formatting-only change. |
| Recursive origin remains ambiguous | Earlier backfill or a different snapshot start changes all later values. | Freeze canonical origin, seed membership, snapshot identity, and restart/version behavior before coding. |
| Registered Close is retained without full design | EMA remains blocked or a redundant feature is added informally. | Remove the dependency in successor documents or authorize Close as a separate primitive task before EMA. |
| Source provenance is assumed rather than proved | Auditors cannot reconstruct the exact Close used per value. | Complete the provenance sufficiency review and add typed source membership if necessary. |
| Nullable/float exceptions enter generic contracts | Other features inherit inconsistent types and missing states; hashes and consumers fragment. | Keep generic Decimal/non-null contracts unchanged and revise EMA-specific documents. |
| Gap continuation is preserved | EMA spans unequal elapsed intervals and predecessor lineage is not adjacent. | Retain fail-closed continuity and test missing timestamps explicitly. |
| Hash preservation is misunderstood | New registry content could be forced under an old identity or historical hashes could be mutated. | Freeze new registry/pipeline identities while preserving algorithms and historical snapshots. |
| Legacy daily EMA is reused directly | Daily pipeline identity, seed assumptions, and source semantics leak into v2 intraday EMA. | Use legacy code only as non-authoritative algorithmic reference after the successor spec is approved. |
| Implementation contract and registry spec diverge again | Code cannot satisfy both documents and hidden assumptions reappear. | Review successor documents together against one canonical compatibility matrix before authorization. |
| Scope expansion into EMA-02/MACD | The smallest approved tranche becomes entangled with unapproved dependencies and outputs. | Register and implement EMA-01 only; treat every later feature as a separate approval. |
| Operational optimization changes recursion | Checkpoints, caching, or incremental state produce different results from full replay. | Require byte-identical full replay, prefix, restart, and checkpoint-equivalence tests before optimization. |

## 8. Final Recommendation

Revise the EMA specifications to match the repository architecture. Do not
evolve AlphaLens into a mixed Decimal/float, non-null/nullable, continuous/
sparse feature platform for EMA-01.

The long-term target should be:

- the already approved EMA period, smoothing constant, recursive equation,
  and arithmetic seed retained without alternative parameter selection;
- those mathematics expressed under AlphaLens's existing Decimal precision
  and canonical output quantization through a newly approved successor
  quantitative specification;
- leading warm-up represented by output omission;
- missing or gapped mandatory Close evidence handled fail closed;
- canonical validated candle Close used as a declared source field rather than
  an artificial registered Close passthrough feature;
- exact definition/output identifiers, semantic version, units, domain, and
  canonical recursive origin frozen before implementation;
- deterministic linear snapshot computation with constant work per eligible
  observation and no mutable hidden state;
- immutable previous-EMA and exact current-candle provenance;
- additive typed source membership only if current provenance cannot prove the
  exact raw dependency; and
- a new registry hash and pipeline version that leave all historical feature
  evidence unchanged.

This recommendation preserves the strongest repository guarantees, minimizes
implementation and migration scope, avoids duplicating Close, and gives EMA-01
a reproducible recursive identity. EMA-01 should remain blocked until the
successor documents and provenance decision are explicitly approved. No
production code, registry, pipeline, persistence, migration, or existing
specification change is justified before those gates pass.
