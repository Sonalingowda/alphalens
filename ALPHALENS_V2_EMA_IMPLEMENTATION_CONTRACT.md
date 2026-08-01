# AlphaLens v2 EMA-01 Implementation Contract

**Document type:** Deterministic engineering implementation contract

**Candidate scope:** `EMA-01` only

**Authority:** The separately approved EMA-01 quantitative specification

**Contract status:** Implementation contract; it does not approve, replace,
extend, or reinterpret the quantitative specification

**Implementation status:** No implementation is authorized by this document
alone

## 1. Purpose

This contract defines the engineering obligations that every EMA-01
implementation must satisfy. It governs dependency resolution, execution
order, validation, failure behavior, immutable persistence, provenance,
registry integration, performance, and testing.

The approved EMA-01 quantitative specification remains the sole authority for
all mathematical meaning. That authority includes the period, smoothing
coefficient, initialization method, seed membership, first-valid boundary,
warm-up, supported scopes, output set, units, numeric policy, and edge-case
semantics. An implementer must consume those declarations exactly and must not
derive missing values from convention, a library default, legacy daily code,
or another feature family.

This implementation contract is responsible for ensuring that the approved
mathematics is executed only against valid point-in-time evidence and that
every output is deterministic, immutable, reproducible, and traceable. It
does not redefine EMA, select parameters, claim predictive usefulness, or
authorize later EMA-family candidates.

If the approved quantitative specification cannot be resolved by immutable
identity and digest, EMA-01 is unavailable and implementation must stop. The
absence of that artifact must never be repaired by embedding a locally chosen
formula or parameter.

## 2. Inputs

### 2.1 Approved definition input

Every execution requires one immutable approved EMA-01 quantitative-definition
record containing or resolving:

- candidate identity `EMA-01`;
- stable feature identifier and feature name;
- semantic feature version;
- definition digest and approval reference;
- exact parameter-set identity;
- initialization and recursive-state contract;
- warm-up and first-valid boundary;
- supported symbol and timeframe scope;
- availability rule;
- Decimal precision, quantum, rounding, and intermediate-precision policy;
- output schema, units, and valid domain; and
- exact compatible dependency identifiers and versions.

The implementation must verify the definition digest before dependency lookup
or computation. A human-readable document name alone is not sufficient
identity.

### 2.2 Close feature dependency

EMA-01 requires the canonical registered Close feature declared by the
approved quantitative specification. The dependency input must provide:

- immutable Close feature-value identity;
- registered Close definition identifier;
- Close definition semantic version;
- Close output identifier;
- symbol;
- timeframe;
- event timestamp;
- exact availability timestamp;
- finite Decimal close value;
- originating feature-run identity;
- registry and pipeline identities;
- source snapshot and source-membership evidence;
- dependency result hash; and
- active, valid, non-suspended lifecycle state.

The registry must resolve Close by declared definition identity, compatible
version, and declared output identity. Lookup by column position, display
label, database ordering, or an unversioned string is prohibited.

Close is a registered feature dependency, not a hidden candle read. When a
registered Close feature exists for the approved scope, EMA-01 must consume
that value and must not access the candle's close field directly. If the
approved contract requires registered Close and no compatible Close feature
exists, EMA-01 remains unavailable; direct candle access is not an acceptable
fallback.

### 2.3 Previous EMA dependency

Every post-initialization output requires the immediately preceding eligible
EMA-01 value under the approved timeframe continuity rule. The previous EMA
input must provide:

- immutable EMA feature-value identity;
- the same EMA feature identifier and semantic version as the current
  execution;
- the same approved parameter-set identity;
- the same symbol and timeframe;
- the immediately preceding eligible timestamp;
- exact availability timestamp;
- finite, canonically quantized Decimal value;
- originating run, registry, pipeline, and result-hash evidence; and
- immutable provenance that is itself verifiable.

An EMA value from another version, parameter set, symbol, timeframe, branch,
or non-adjacent timestamp cannot be used as predecessor state.

### 2.4 Initialization input

The first valid EMA output requires the complete ordered initialization
evidence declared by the quantitative specification. Each initialization
member must be an immutable compatible Close feature value with its exact
identity, timestamp, availability, Decimal value, version, and provenance.

The initialization record must identify the complete seed membership and the
approved initialization-policy identity. Partial history, shortened history,
an implementation-library seed, or a previously computed value from a
different definition is prohibited.

### 2.5 Input immutability and provenance

All inputs must be immutable records or immutable in-memory projections of
verified records. Input objects, ordered membership collections, registry
snapshots, and configuration payloads must not be mutated during execution.

Every input must be available no later than the current output's evidence
cutoff. Later source revisions, later feature runs, and future timestamps may
not be substituted into historical execution.

## 3. Outputs

EMA-01 produces only the output or outputs explicitly declared by the
approved quantitative specification. This contract defines the required
engineering envelope for each EMA value record.

| Field | Contract |
| --- | --- |
| `feature_id` | Globally unique immutable value-record identity. It must never be reused for different content. |
| `feature_name` | Exact registered output name from the approved EMA-01 definition. Aliases and display-name substitutions are prohibited in canonical storage. |
| `feature_version` | Exact semantic definition version resolved from the approved registry entry. |
| `timestamp` | Canonical timezone-aware UTC event timestamp of the Close observation represented by this EMA value. It must be timeframe-aligned. |
| `available_at` | Earliest point-in-time availability determined by the approved definition and the maximum availability of all direct dependencies. |
| `symbol` | Exact approved market identity. It must match every direct and initialization dependency. |
| `timeframe` | Exact approved timeframe. It must match every direct and initialization dependency. |
| `ema_value` | Finite Decimal value computed under the approved quantitative definition and canonical precision policy. Binary floating-point storage is prohibited. |
| `dependency_references` | Ordered immutable references to the previous EMA and current Close, or to the complete initialization membership for the first valid output. |
| `provenance` | Complete provenance record defined in Section 8. |
| `metadata` | Definition, category, units, parameter-set, availability, numeric-policy, registry, pipeline, code, and lifecycle metadata required to interpret and reproduce the value. |
| `result_hash` | Canonical content hash covering semantic identity, value, ordered dependency memberships, availability, and required provenance identities. |
| `created_at` | Operational persistence time. It must remain distinct from `timestamp` and `available_at`. |
| `immutable` | Persisted invariant indicating that the record cannot be updated in place. |

The canonical output object and all nested dependency, provenance, and
metadata collections must be immutable. Presentation projections may rename
fields for display only if they retain an explicit reference to the canonical
record and cannot change its meaning.

## 4. Processing Pipeline

Execution must occur in the following fixed sequence. Each stage must finish
successfully before the next stage begins.

| Order | Stage | Required result |
| ---: | --- | --- |
| 1 | Resolve approved definition | Resolve the exact EMA-01 quantitative-definition identity, digest, parameter set, and approval evidence. |
| 2 | Resolve registry snapshot | Load the immutable registry snapshot selected by the approved pipeline and verify its hash and schema version. |
| 3 | Validate registry declaration | Confirm EMA-01 identity, semantic version, output schema, supported scope, execution position, and version-pinned dependencies. |
| 4 | Resolve Close evidence | Load the exact registered Close values required for initialization or the current update, preserving canonical ordering and availability. |
| 5 | Resolve EMA state | For initialization, load the complete approved seed membership. For a later value, load the immediately preceding compatible EMA value. |
| 6 | Validate dependencies | Apply every rule in Section 5, including identity, version, scope, chronology, availability, Decimal, hash, and immutability checks. |
| 7 | Evaluate availability | Confirm that all mandatory evidence is available by the output cutoff and that no future value or incomplete observation is present. |
| 8 | Execute approved calculation | Apply the quantitative specification exactly once using only the validated inputs. No hidden dependency or library initialization may participate. |
| 9 | Apply numeric policy | Enforce the approved working precision, intermediate handling, output quantum, rounding mode, finiteness, and output domain. |
| 10 | Build dependency memberships | Record the ordered previous-EMA/current-Close references, or the ordered initialization Close memberships for the first value. |
| 11 | Build provenance and hashes | Construct the complete provenance payload and canonical dependency, configuration, and result hashes. |
| 12 | Validate output | Verify schema, value, availability, ordering, prefix invariance obligations, and provenance completeness before persistence. |
| 13 | Persist transactionally | Insert or exactly reuse immutable values and memberships in one transaction. No partially active state may remain. |
| 14 | Verify persistence | Reload and compare exact value, memberships, hashes, registry snapshot, and run counts against the computed result. |
| 15 | Activate release | Register or promote the complete verified pipeline run only after all values and memberships pass validation. |

Registry declaration belongs to release preparation, before an active run is
accepted. A computation must never dynamically register an unknown feature or
modify the registry during value execution.

## 5. Validation Rules

### 5.1 Definition and registry validation

Before computation, validation must confirm:

- the approved EMA-01 definition exists and its digest matches the approval
  evidence;
- the registry contains exactly one matching feature identifier and version;
- every declared output is unique and schema-compatible;
- every dependency is registered earlier in canonical execution order;
- the Close dependency identifier, output, and version match the quantitative
  specification;
- the recursive EMA dependency refers to the same feature version and
  parameter-set identity;
- the requested symbol and timeframe are supported; and
- the active pipeline and registry identities are mutually compatible.

### 5.2 Close validation

Each Close dependency must:

- exist exactly once for the required symbol, timeframe, and timestamp;
- be an immutable registered feature value;
- match the required definition and output versions;
- contain a `Decimal`, never a float, string, null, NaN, or infinity;
- satisfy the approved value domain and canonical quantum;
- have a verified result hash and complete source provenance;
- be available by the current output cutoff; and
- be ordered strictly by canonical timestamp.

### 5.3 Previous EMA validation

For every recursive update, validation must confirm:

- exactly one predecessor exists;
- it is the immediately preceding eligible observation under the approved
  continuity rule;
- its identifier, version, parameter set, symbol, and timeframe match the
  current execution;
- its value is finite Decimal and canonically quantized;
- its record and provenance are immutable and hash-valid; and
- it was available before or at the current output availability boundary.

Using the latest database row without verifying exact predecessor identity is
prohibited.

### 5.4 Initialization validation

Before the first output, validation must confirm:

- the complete approved number of eligible Close observations exists;
- memberships are strictly chronological, unique, and consecutive where the
  quantitative specification requires continuity;
- no partial-window or alternate seed is present;
- all Close dependencies satisfy Section 5.2;
- the first-valid timestamp exactly matches the approved boundary; and
- no predecessor EMA is represented as the initialization source unless the
  quantitative specification explicitly declares one.

### 5.5 Duplicate and ordering validation

The implementation must reject:

- duplicate Close identities or timestamps;
- duplicate EMA output identities;
- multiple previous EMA candidates for one current value;
- repeated dependency ordinals;
- missing ordinals in an ordered membership set;
- non-increasing timestamps;
- timeframe-misaligned timestamps; and
- nondeterministic database or collection ordering.

An exact immutable replay under the same canonical identity may be reused only
after byte-equivalent semantic content and hashes are verified. A conflicting
duplicate is an integrity failure.

### 5.6 Precision and immutability validation

All numeric inputs, intermediate state exposed by the contract, and outputs
must obey the approved Decimal policy. Validation must reject binary floats,
non-finite values, excess or incompatible precision, an unauthorized rounding
mode, and output values outside the approved domain.

Any detected mutation of input content, membership ordering, registry
evidence, predecessor state, or persisted output invalidates the computation.

## 6. Error Handling

All failures must be deterministic and reason-coded. Operational failure must
not be converted into a numeric value, a shortened-window value, a zero, or a
successful empty result.

| Condition | Required state | Required behavior |
| --- | --- | --- |
| Approved definition missing or unverifiable | `UNAVAILABLE_DEFINITION` | Stop before dependency resolution. Produce no EMA value. |
| Close dependency missing | `NOT_YET_AVAILABLE` when legitimately pending; otherwise `UNAVAILABLE_DEPENDENCY` | Produce no value for the affected timestamp. Do not read the candle directly as fallback. |
| Previous EMA missing after initialization boundary | `UNAVAILABLE_RECURSIVE_STATE` | Stop the affected recursive chain. Do not reseed, reset, or skip over the gap. |
| Invalid Close type, value, domain, availability, or provenance | `INVALID_DEPENDENCY` | Reject the affected value and stop its dependent chain. |
| Invalid EMA predecessor | `INVALID_RECURSIVE_STATE` | Reject the current value and stop its dependent chain. |
| Dependency version mismatch | `INCOMPATIBLE_DEPENDENCY` | Stop computation before numeric evaluation. No implicit conversion is allowed. |
| Invalid precision or rounding policy | `INVALID_NUMERIC_POLICY` | Reject the computation and emit no value. |
| Duplicate timestamp with identical immutable content | `EXACT_REPLAY` | Reuse the existing canonical value only after all content, membership, and hash checks pass. |
| Duplicate timestamp with conflicting content | `CONFLICTING_VALUE` | Fail closed, retain conflict evidence, and do not overwrite either record. |
| Insufficient initialization history | `NOT_YET_AVAILABLE` | Omit the EMA output until the complete approved initialization boundary exists. This is not an error and must be counted separately. |
| Gap or non-adjacent predecessor | `DISCONTINUOUS_HISTORY` | Stop the affected chain. Do not fill, interpolate, segment, or silently restart. |
| Registry, pipeline, or result-hash mismatch | `INTEGRITY_FAILURE` | Reject or suspend the affected run and all dependent use. |
| Persistence failure | `PERSISTENCE_FAILURE` | Roll back the transaction and publish no new active value or run. |

Every error record must include a stable error code, contract version,
affected feature/scope/timestamp, stage, dependency references available at
failure time, retryability, safe diagnostic detail, and audit correlation
identity. Error records must not expose secrets.

## 7. Persistence Contract

EMA outputs must use the existing immutable feature-run, engineered-value,
source-membership, value-membership, dependency-membership, registry-snapshot,
hashing, activation, and supersession infrastructure.

Persistence must satisfy these rules:

1. Every EMA value is append-only and immutable after insertion.
2. Updates to the value, timestamp, availability, identity, version,
   dependencies, provenance, metadata, or hashes are prohibited.
3. A changed formula, parameter, initialization, dependency, availability,
   precision, output meaning, or feature version creates a distinct immutable
   value identity under a new approved definition/pipeline release.
4. An identical replay verifies and reuses existing canonical values; it does
   not create contradictory duplicates.
5. A conflicting replay fails closed and preserves auditable conflict
   evidence. It never overwrites the canonical record.
6. Each non-initial EMA value persists ordered references to exactly the
   previous EMA and current Close dependencies required by the quantitative
   specification.
7. Each initialization value persists the complete ordered seed membership
   and initialization-policy identity.
8. Run-level source and value memberships supplement, but do not replace,
   per-value dependency memberships.
9. The registry snapshot, configuration hash, dependency-membership hash,
   source hashes, and result hash are persisted with the run or value as
   required by the existing canonical hash contract.
10. All values, memberships, hashes, and run evidence are inserted and
    verified in one transaction before activation.
11. Failed persistence leaves no partially active run and does not deactivate
    the last verified compatible run.
12. Supersession changes lifecycle pointers or status only; it does not delete
    or mutate historical EMA evidence.

Canonical hashing must remain compatible with the repository's deterministic
JSON serialization, timestamp representation, Decimal string representation,
registry hashing, and pipeline result-hash conventions. Any required hash
schema evolution must be explicit, versioned, backward-compatible for
historical reads, and separately approved before implementation.

Reproduction must be possible from persisted definition, registry, pipeline,
code, parameter, dependency, source, ordering, precision, and hash evidence
without consulting mutable external state.

## 8. Provenance Contract

### 8.1 Required provenance fields for every output

Every EMA value must retain:

- `feature_id`;
- EMA candidate identity `EMA-01`;
- registered feature identifier and output name;
- EMA semantic feature version;
- approved quantitative-definition identity, digest, and approval reference;
- parameter-set identity and configuration hash;
- initialization-policy identity;
- symbol and timeframe;
- event timestamp, evidence cutoff, `available_at`, and persistence time;
- exact Decimal value, units, quantum, working precision, and rounding-policy
  identity;
- registry schema version, registry snapshot identity, and registry hash;
- pipeline version and pipeline configuration hash;
- implementation reference, code version, software/runtime identity, and
  deterministic seed identity when the approved definition declares one;
- source snapshot identity, source data hash, source provenance hash, and
  source batch memberships inherited through Close;
- ordered direct dependency memberships and their hash;
- output result hash;
- point-in-time, prefix-invariance, continuity, precision, and provenance
  validation results; and
- lifecycle status, predecessor/supersession references, limitations, and
  failure evidence where applicable.

### 8.2 Previous EMA linkage

Every post-initialization EMA value must reference the immediately preceding
EMA value by immutable value identity. The reference must also retain or
resolve its timestamp, availability, feature version, parameter-set identity,
run identity, registry/pipeline identity, and result hash.

The dependency ordinal for previous EMA must be stable and declared in the
EMA output schema. It must not depend on insertion order or query order.

### 8.3 Current Close linkage

Every EMA value must reference the exact current Close feature value by
immutable value identity. The reference must retain or resolve its Close
definition identifier, output name, semantic version, timestamp,
availability, Decimal value, source snapshot, source memberships, run
identity, and result hash.

The dependency ordinal for current Close must be stable and declared in the
EMA output schema.

### 8.4 Initialization linkage

The first valid EMA output must be explicitly marked as an initialization
output. Its provenance must include:

- initialization-record identity;
- approved initialization-policy identity and digest;
- complete ordered Close membership required by the quantitative
  specification;
- each Close value identity, version, timestamp, availability, value, run,
  and result hash;
- first and last initialization timestamps;
- initialization membership count;
- ordered initialization-membership hash; and
- validation result proving the first-valid boundary.

Later EMA values must retain a transitive path to this initialization record
through their previous-EMA chain. Implementations may add verified checkpoint
evidence for operational recovery only if it preserves the exact predecessor
and initialization chain and does not change numeric semantics.

### 8.5 Dependency-version provenance

Provenance must record the exact compatible version for every declared
dependency. Recording only an unversioned name is insufficient. A dependency
version change requires compatibility review and, whenever meaning or output
can change, a new EMA definition and pipeline release.

## 9. Registry Contract

EMA-01 must register through the existing explicit, code-owned,
content-addressed feature registry. Dynamic runtime registration is
prohibited.

The registry declaration must contain:

- catalog candidate identity `EMA-01` as governance metadata;
- exact stable lowercase-snake-case feature identifier from the approved
  quantitative specification;
- exact semantic definition version from the approved specification;
- non-empty description and primary category;
- exact supported symbols and timeframes;
- exact output schema, including output identifiers, descriptions, units,
  domains, types, first-valid boundaries, and minimum observations;
- recursive history classification and approved lookback/state requirements;
- continuity requirement;
- exact availability rule;
- implementation reference;
- Decimal quantum and numeric-policy identity;
- direct Close dependency declaration with exact compatible definition
  version and output name;
- recursive previous-EMA dependency contract for persisted value provenance;
- initialization membership contract and initialization-policy identity;
- approval reference and immutable quantitative-definition digest; and
- any limitations required by the approved specification.

Registry validation must require dependencies to be registered and compatible
before EMA-01 in canonical execution order. It must reject duplicate feature
identifiers, duplicate outputs, missing dependencies, forward dependencies,
cycles, version ambiguity, unsupported scope, invalid warm-up, incompatible
units or types, and nondeterministic ordering.

The feature identifier, semantic version, period-bearing parameter identity,
and output names must be taken verbatim from the approved quantitative
specification. This contract intentionally does not invent those absent
values. If the authoritative artifact is unavailable or does not declare
them, registry construction fails closed.

Adding EMA-01 changes registry membership and requires a new immutable
registry hash and pipeline version. Existing registry snapshots, hashes,
pipeline versions, values, and runs remain historical and retrievable.
Consumers must declare compatibility with the new registry and pipeline; no
implicit upgrade is permitted.

## 10. Performance Requirements

After initialization, one eligible EMA update must have `O(1)` computational
complexity relative to historical series length. It must require only the
current Close, immediately previous EMA, fixed definition metadata, and
bounded provenance-construction state needed for the current output.

Working numeric memory after initialization must remain `O(1)` with respect to
total archive length. Persistence and audit storage may grow linearly with the
number of immutable outputs and dependency memberships because historical
evidence cannot be discarded.

Initialization may consume only the finite history declared by the approved
quantitative specification. It must not load an entire archive when the
approved seed boundary is bounded.

Batch execution must be `O(n)` in the number of eligible observations.
Database access must avoid one unbounded historical scan per update and must
use exact indexed identities for current Close and previous EMA resolution.

Optimization must preserve byte-identical values, memberships, ordering,
availability, serialization, and hashes. Caching may change latency only; a
cache entry must be keyed by all semantic identities and verified before use.

Execution must remain deterministic across supported environments. Thread
scheduling, database row order, locale, wall-clock time, and process-level
Decimal context must not affect semantic output.

No performance target authorizes weakened validation, reduced provenance,
binary floating point, hidden checkpoints, alternate seeding, or mutable
state.

## 11. Testing Contract

Every implementation must include focused EMA-01 tests and the applicable
existing feature regression suite.

### 11.1 Dependency tests

Tests must prove:

- exact registered Close lookup by identifier, version, output, symbol,
  timeframe, and timestamp;
- rejection of missing, duplicate, unavailable, suspended, hash-invalid, or
  incompatible Close values;
- rejection of direct candle fallback when compatible registered Close exists
  or is required;
- exact previous-EMA resolution;
- rejection of wrong-version, wrong-parameter, wrong-symbol, wrong-timeframe,
  non-adjacent, or conflicting predecessor state; and
- rejection of registry order, schema, and dependency-contract mismatches.

### 11.2 Initialization tests

Tests must cover every approved initialization fixture and prove:

- no output before the complete warm-up boundary;
- exactly one first output at the approved first-valid timestamp;
- exact ordered Close seed membership;
- exact initialization-record and membership hash;
- rejection of partial, gapped, reordered, duplicated, or future seed input;
  and
- no use of a library-default or alternate initialization.

### 11.3 Recursive calculation tests

Tests must use the exact approved quantitative fixtures without redefining
them. They must prove:

- every later value uses exactly one current Close and the immediately
  previous EMA;
- timestamp mapping remains exact after initialization;
- a missing predecessor stops the chain rather than causing reseeding;
- current and predecessor dependency ordinals remain canonical; and
- full-series execution and valid incremental execution produce identical
  semantic output.

### 11.4 Precision tests

Tests must cover:

- Decimal-only inputs and outputs;
- approved working precision;
- approved intermediate handling;
- exact output quantum and rounding behavior, including boundary ties;
- rejection of floats, nulls, NaN, infinity, excess precision, and values
  outside the approved domain; and
- isolation from ambient process Decimal context.

### 11.5 Persistence and provenance tests

Tests must prove:

- immutable insert and exact replay reuse;
- conflicting duplicate rejection;
- transaction rollback on every injected persistence failure stage;
- activation only after complete value and membership verification;
- previous EMA and current Close foreign-key memberships for every recursive
  value;
- complete ordered initialization memberships for the first value;
- registry, pipeline, source, dependency, configuration, and result-hash
  integrity;
- supersession without mutation or deletion; and
- complete audit traversal from any EMA value to initialization and canonical
  Close source evidence.

### 11.6 Determinism and chronology tests

Tests must prove:

- repeated execution over identical evidence produces identical immutable
  objects and hashes;
- canonical ordering is independent of input container or database row order;
- every dependency is available by the output cutoff;
- incomplete or future Close evidence is excluded;
- modifying any future suffix leaves all earlier EMA values, memberships, and
  hashes unchanged;
- computing every valid prefix produces the same earlier outputs as the
  corresponding restriction of the full result;
- replay after process restart reproduces identical results from persisted
  state; and
- no random state, wall-clock time, locale, or concurrency schedule enters
  semantic output.

### 11.7 Regression requirements

The implementation must pass:

- focused EMA-01 tests;
- existing feature-contract tests;
- registry uniqueness, dependency, compatibility, ordering, and hash tests;
- pipeline warm-up, availability, deterministic replay, prefix-invariance,
  and result-hash tests;
- persistence immutability, idempotency, rollback, activation, and provenance
  tests;
- live or replay validation for every approved timeframe where authorized
  evidence exists;
- Python compilation and static analysis; and
- the complete backend regression suite.

Test success establishes contract compliance, not predictive usefulness.

## 12. Non-Goals

This contract does not authorize or define:

- EMA mathematics, parameters, coefficient, seed, warm-up, or output meaning;
- EMA-02 slope, EMA-03 fast/slow spread, EMA-04 ribbon dispersion, or any
  other EMA-family candidate;
- MACD or any MACD dependency, signal, histogram, or derivative;
- RSI or any other momentum feature;
- ATR modifications, ATR-derived features, or changes to existing ATR
  definitions, registry evidence, pipeline values, or provenance;
- moving-average parameter optimization or automated parameter selection;
- performance-driven semantic shortcuts;
- parallelization, distributed execution, queues, or service decomposition;
- visualizations, charts, dashboards, scanners, or frontend work;
- APIs, transport schemas, routes, or client integration;
- database migrations or persistence-schema design;
- model training, feature selection, benchmarking, or predictive claims;
- trading logic, opportunity qualification, ranking, confidence, or risk
  management;
- signal generation, including `BUY`, `SELL`, `WAIT`, entry, exit, stop, or
  objective semantics; or
- trade execution, simulation, order routing, position sizing, or portfolio
  action.

Any work in these areas requires a separate approved specification and
engineering change request. EMA-01 implementation must stop at producing and
persisting deterministic, versioned, point-in-time feature evidence.
