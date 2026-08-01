# AlphaLens v2 EMA-01 Successor Implementation Contract

**Document type:** Feature-specific implementation contract

**Feature:** EMA-01

**Status:** Successor contract for approval

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

**Architecture reconciliation:**
`ALPHALENS_V2_EMA_ARCHITECTURE_RECONCILIATION.md`

**Quantitative authority:**
`ALPHALENS_V2_EMA01_SUCCESSOR_QUANTITATIVE_SPECIFICATION.md`

## 1. Purpose

This contract defines the engineering obligations of every EMA-01
implementation. It describes how an implementation must participate in the
existing AlphaLens feature registry, feature pipeline, validation,
persistence, provenance, hashing, and test infrastructure.

This contract does not define EMA mathematics. The Successor Quantitative
Specification is the sole authority for EMA-01 period, smoothing,
initialization, recurrence, seed membership, first valid observation,
recursive origin, and output meaning.

This contract does not define a separate feature architecture. Every
cross-feature engineering rule is inherited from the Feature Architecture
Standard. The implementation must reuse the repository's existing contracts
and infrastructure and must not create an EMA-specific parallel path.

## 2. Authority and Supersession

Upon explicit approval, this document supersedes the previous EMA-01
Implementation Contract wherever that contract conflicts with any governing
document listed above.

The order of authority is:

1. Feature Architecture Standard;
2. EMA Architecture Reconciliation;
3. EMA-01 Successor Quantitative Specification;
4. this Successor Implementation Contract; and
5. implementation and tests.

If the documents cannot be satisfied simultaneously, implementation must
stop. Code, tests, library conventions, legacy behavior, and operational
convenience cannot resolve a specification conflict.

Approval of this contract does not approve an implementation, registry
release, pipeline release, migration, or another feature.

## 3. Scope

The implementation scope is one EMA-01 definition with the single
quantitative output authorized by the Successor Quantitative Specification.

The implementation is responsible for:

- resolving and validating its approved definition and release identity;
- consuming canonical Close from the immutable source snapshot;
- executing the approved mathematics exactly;
- emitting only mathematically defined values;
- preserving recursive predecessor lineage;
- conforming to shared Decimal and quantization infrastructure;
- integrating with the registry and deterministic pipeline;
- producing immutable persistable results and complete provenance;
- failing closed on invalid or incomplete evidence; and
- passing all required focused and regression validation.

No other EMA variant, distance, slope, crossover, signal, or feature family is
within scope.

## 4. Implementation Preconditions

EMA-01 implementation must not begin until all of the following are frozen
and mutually consistent:

- approved Feature Architecture Standard;
- approved EMA Architecture Reconciliation;
- approved EMA-01 Successor Quantitative Specification;
- this approved contract;
- a successor EMA-01 registry contract;
- exact canonical feature identifier;
- exact output identifier;
- semantic definition version;
- supported asset, quote-currency, and timeframe scope;
- implementation reference;
- quantitative-specification identity and digest;
- implementation-contract identity and digest; and
- canonical recursive-origin evidence for every supported series.

An implementer must not infer unresolved identity or scope from filenames,
display names, legacy daily features, third-party libraries, or catalog
shorthand.

## 5. Input Contract

### 5.1 Canonical source input

EMA-01 consumes canonical Close as a typed OHLCV source field from the
pipeline-provided immutable source snapshot.

The implementation must:

- declare Close as its required source input;
- use the validated Close value associated with each canonical candle;
- preserve source ordering and timeframe membership;
- treat input objects as immutable; and
- reject any attempt to supply a binary float, null, non-finite value,
  unvalidated candle, or out-of-snapshot observation.

The implementation must not query candle persistence directly, access mutable
live candle state, or bypass the snapshot supplied by the feature pipeline.

### 5.2 No registered Close feature

Close is not a registered derived-feature dependency. EMA-01 must not require,
create, register, load, or persist a passthrough Close feature.

The absence of a registered Close definition is not an error. The required
Close evidence is resolved through declared source-field metadata and the
validated source snapshot.

### 5.3 Derived dependencies

EMA-01 has no upstream derived-feature dependency under the approved
quantitative definition. The implementation must reject undeclared derived
dependency input.

The immediately preceding EMA-01 value is recursive value lineage, not a
registry self-dependency. It must be handled and recorded according to
Sections 8 and 10 without introducing a dependency cycle.

## 6. Output Contract

EMA-01 must emit exactly the one quantitative output defined by the Successor
Quantitative Specification. It must not emit auxiliary seed, coefficient,
distance, slope, signal, quality, status, or debugging outputs.

Each internal feature output must conform to the repository feature-value
contract and include:

- canonical candle timestamp;
- exact registered output identity;
- finite canonically quantized Decimal value; and
- ordered recursive predecessor membership when a predecessor exists.

The pipeline, not the EMA implementation, is responsible for adding the
canonical feature identifier, definition version, `available_at`, scope,
pipeline version, registry identity, run evidence, and result hashes to the
pipeline and persistence envelopes.

No output may contain null, NaN, infinity, a binary float, an unquantized
value, or a timestamp outside the source snapshot.

## 7. Execution Obligations

The implementation must execute through the established feature-definition
interface. Its execution responsibilities are limited to the following
ordered obligations:

1. Accept the immutable candle sequence, registered timeframe, and resolved
   dependency-input collection supplied by the pipeline.
2. Validate that the invocation matches the approved input and dependency
   contract.
3. Delegate shared candle, timestamp, continuity, Decimal, and scope
   validation to existing repository safeguards.
4. Confirm that the supplied sequence contains the frozen recursive origin or
   an explicitly approved replay-equivalent checkpoint.
5. Apply the Successor Quantitative Specification without changing or
   supplementing its mathematics.
6. Retain approved working precision for recursive state and use the shared
   canonical output-quantization boundary.
7. Emit no values before the quantitative first-valid boundary.
8. Associate each emitted value with the correct source candle timestamp.
9. Attach exact predecessor lineage to every post-initialization recursive
   value.
10. Return immutable outputs in strict chronological order.

The implementation must be stateless between independent invocations. It may
hold local in-run recursive state, but must not rely on mutable global state,
ambient Decimal context, previous process execution, wall-clock time, or an
unversioned database checkpoint.

Existing shared primitives must be reused when their verified behavior
matches the governing documents. Approved shared validation, quantization,
ordering, and dependency structures must not be duplicated in an EMA-specific
form.

## 8. Validation Obligations

### 8.1 Validation before computation

Before performing EMA mathematics, the invocation must be rejected if:

- implementation metadata differs from the registered metadata;
- the timeframe or scope is unsupported;
- Close is not declared or is unavailable in the source snapshot;
- an undeclared derived dependency is supplied;
- timestamps are missing, duplicated, unordered, discontinuous, misaligned,
  non-UTC, or timezone-naive;
- a candle is incomplete or violates canonical OHLCV validity;
- a required value is null, non-Decimal, or non-finite;
- the snapshot fails integrity or provenance verification;
- the snapshot does not satisfy the frozen recursive-origin contract; or
- an invocation attempts to infer a new seed from a later snapshot boundary.

### 8.2 Validation during and after computation

The implementation and pipeline must jointly reject results when:

- output appears before the approved first-valid observation;
- an eligible output is missing after warm-up;
- an unexpected output or timestamp is present;
- output identity differs from registered metadata;
- a value is null, non-Decimal, non-finite, out of the approved mathematical
  domain, or not canonically quantized;
- output ordering is not strictly chronological;
- a post-initialization value lacks its immediately preceding EMA lineage;
- predecessor identity, version, output, timestamp, value, or availability is
  inconsistent;
- a predecessor is later than or nonadjacent to its consumer;
- repeated execution differs;
- a prefix result differs from its full-run counterpart;
- future evidence influences an earlier output; or
- output or provenance cannot be reproduced from the frozen evidence.

Validation must be fail closed. It must produce no substitute feature value,
must not reseed, and must not continue a broken recursive chain.

### 8.3 Warm-up validation

The implementation must derive the output boundary exclusively from the
Successor Quantitative Specification and declare matching registry metadata.
Before that boundary, output is omitted. At and after that boundary, exact
coverage is mandatory for every eligible source timestamp.

Warm-up omission must not be confused with a missing input, failed
dependency, broken recursive chain, or invalid source snapshot.

## 9. Deterministic Execution Obligations

For identical approved definition, registry snapshot, pipeline version,
source snapshot, scope, and recursive origin, EMA-01 must produce identical
outputs and evidence on every execution.

Determinism includes:

- identical output presence and count;
- identical canonical Decimal values;
- identical timestamp and availability association;
- identical predecessor membership;
- identical ordering;
- identical canonical hash inputs; and
- identical validation outcome.

The implementation must isolate its Decimal context and must not depend on
machine floating-point behavior, locale, system timezone, database return
order, unordered collection traversal, concurrency timing, process history,
or current time.

The implementation must use each source observation and its preceding history
only. Appending a future suffix must not alter previously emitted values or
their feature-level lineage.

## 10. Provenance Obligations

### 10.1 Source provenance

EMA-01 must preserve the standard source provenance supplied by the pipeline,
including the immutable source snapshot, source range, ingestion evidence,
source data hash, source provenance hash, scope, timeframe, and candle
timestamps.

The current Close for each EMA value is identified through the consumer
timestamp and the corresponding candle in the immutable hashed snapshot. The
implementation must not manufacture a Close feature value or duplicate the
raw Close in a private provenance structure.

The initialization output must be reconstructable from the frozen origin,
the approved seed membership in the source snapshot, the quantitative
specification identity, and canonical source evidence.

### 10.2 Recursive predecessor provenance

Every EMA value after initialization must contain one ordered predecessor
membership identifying the immediately preceding EMA-01 output by:

- feature definition identifier;
- definition version;
- output name;
- predecessor candle timestamp; and
- the exact immutable predecessor value resolved by the pipeline.

The initialization output has no prior EMA predecessor and must not contain a
fabricated predecessor membership.

Predecessor membership is value-level recursive lineage. It must not be
declared as a registry self-dependency and must not create a registry cycle.

### 10.3 Persistence provenance

The pipeline and persistence layers must retain source membership, registry
snapshot, registry hash, pipeline version, availability-contract version,
result hash, run-value membership, predecessor membership, and point-in-time
validation evidence.

If existing shared contracts cannot represent required predecessor lineage
without ambiguity, implementation remains blocked until a narrowly scoped,
repository-wide provenance extension is approved. The implementation must not
drop, flatten, or approximate the lineage.

## 11. Pipeline Integration Obligations

EMA-01 must integrate into the existing deterministic intraday feature
pipeline. The implementation must not introduce a separate EMA runner,
direct-persistence path, live-only calculation path, or alternate hash path.

Pipeline integration must:

- resolve EMA-01 from the active immutable registry;
- verify exact implementation-to-registry metadata equality;
- pass the immutable validated source snapshot and registered timeframe;
- reject unexpected derived dependency input;
- execute EMA-01 at its deterministic registry position;
- validate output coverage against registered warm-up metadata;
- validate canonical Decimal output;
- validate timestamp and candle-close availability;
- verify recursive predecessor membership;
- execute isolated-prefix validation;
- verify future isolation;
- place EMA output in canonical timestamp and registry-output order;
- incorporate EMA values and lineage into canonical result hashing; and
- mark a run point-in-time valid only after every check succeeds.

Batch execution is linear in source observations with constant arithmetic work
per recursive update after initialization. Performance optimization must not
change output, lineage, ordering, or hashes.

## 12. Registry Obligations

EMA-01 must be registered through the existing immutable Feature Registry.
The aligned successor registry contract must provide the exact engineering
identities withheld from the quantitative specification.

The registry entry must:

- use one canonical lowercase-snake-case feature identifier;
- use one semantic definition version;
- declare Close as the required canonical candle field;
- declare no derived-feature dependencies;
- declare exactly the one approved output;
- set output minimum observations to the quantitative first-valid boundary;
- classify EMA-01 as recursive;
- require continuous input;
- use candle-close availability;
- declare no bounded maximum lookback for the recursive history;
- declare the canonical repository Decimal quantum;
- declare supported scopes and timeframes explicitly;
- identify the exact implementation entry point;
- reference the governing architecture, reconciliation, quantitative
  specification, and this contract; and
- include the approved recursive-origin policy and release evidence required
  by the active registry schema or release process.

Registry validation must reject duplicate identity, duplicate output,
undeclared dependency, unsupported scope, incompatible metadata, unresolved
document reference, or implementation mismatch.

Adding EMA-01 creates new registry content and therefore requires a new
registry snapshot and configuration hash. It must not mutate an earlier
registry snapshot.

## 13. Persistence Obligations

EMA-01 must use the existing engineered-feature and feature-run persistence
path. No EMA-specific table, mutable state record, nullable feature-value
column, float column, or passthrough Close persistence is permitted.

Persistence must:

- accept only a complete point-in-time-validated pipeline result;
- store canonically quantized non-null Decimal values;
- retain the canonical value identity and run membership;
- retain source and registry evidence;
- persist ordered predecessor memberships;
- verify every membership before activation;
- remain idempotent for identical canonical content;
- prevent in-place mutation of an existing feature value; and
- preserve superseded runs and their evidence.

Persisted EMA values are immutable research evidence. They must not become an
unversioned mutable recursive-state cache. Any later checkpoint mechanism
must remain subordinate to full-replay equivalence and must not change the
authoritative stored results.

No database migration is authorized by this contract. If implementation
proves that an architecture-required relationship cannot be represented by
the existing persistence model, work must stop for a separate reviewed
architecture and migration request.

## 14. Error-Handling Obligations

EMA-01 uses deterministic fail-closed error handling inherited from the
Feature Architecture Standard.

On invalid source evidence, metadata mismatch, unsupported scope, unexpected
dependency, insufficient origin evidence, broken continuity, missing
predecessor, numeric violation, provenance failure, nondeterminism,
point-in-time failure, prefix failure, future-isolation failure, or persistence
conflict, the affected computation or run must stop.

The implementation must not:

- emit a null or sentinel value;
- skip the offending observation;
- fall back to direct persistence access;
- substitute another Close source;
- forward-fill or interpolate;
- reseed or reset the recursive sequence;
- reuse a stale predecessor;
- downgrade an error to warm-up; or
- activate a partial run.

Equivalent invalid inputs must produce equivalent validation outcomes.
Diagnostic text may add context but must not change semantic behavior or
canonical result evidence.

## 15. Testing Obligations

EMA-01 requires focused tests sufficient to prove conformance with the three
governing documents and this contract.

### 15.1 Quantitative conformance

Tests must cover:

- independently derived approved-value fixtures;
- exact initialization and seed membership;
- exact recursive calculation;
- first-valid observation;
- output meaning and units;
- minimum, shorter-than-minimum, and longer histories;
- no unintended intermediate quantization; and
- canonical emitted-value quantization.

Expected quantitative values must come from the approved specification, not
from the implementation under test or a third-party library default.

### 15.2 Input and validation behavior

Tests must cover:

- canonical Close source declaration and use;
- rejection of a registered-Close or other undeclared dependency input;
- missing, null, non-Decimal, non-finite, and invalid source values;
- incomplete candles;
- duplicate, unordered, discontinuous, misaligned, or non-UTC timestamps;
- unsupported scope or timeframe;
- source-snapshot integrity failure;
- missing or incompatible recursive-origin evidence;
- no reseeding from a later snapshot boundary;
- missing or incorrect predecessor lineage; and
- fail-closed behavior without partial output.

### 15.3 Determinism and temporal integrity

Tests must cover:

- repeated-execution equality;
- isolation from ambient Decimal context;
- deterministic output and membership ordering;
- every valid source prefix;
- future-suffix append and mutation isolation;
- candle-close availability;
- dependency availability for predecessor lineage;
- full replay from the frozen origin; and
- checkpoint equivalence if any incremental path exists.

### 15.4 Architecture integration

Tests must cover:

- registry metadata and implementation equality;
- exact output coverage and warm-up omission;
- recursive history classification;
- absence of a registered Close dependency;
- deterministic registry and result hash changes;
- pipeline integration;
- live-validation integration;
- immutable non-null Decimal persistence;
- idempotent persistence replay;
- run activation and supersession without historical mutation;
- source provenance reconstruction;
- predecessor-membership persistence and reconstruction;
- existing ATR and True Range regression protection; and
- the full existing feature and backend regression suites.

Required repository validation includes linting, Python compilation, focused
EMA-01 tests, existing feature regression tests, persistence tests, live
validation tests, and the full backend suite.

## 16. Non-Goals

This contract does not authorize or define:

- EMA mathematics or alternative EMA formulas;
- a second EMA output or period;
- EMA distance, slope, crossover, or multi-EMA relationships;
- MACD, RSI, ATR changes, Bollinger Bands, VWAP, ADX, or another feature;
- trend interpretation, ranking, signals, strategies, or trading decisions;
- a registered passthrough Close feature;
- API endpoints or user-interface behavior;
- visualization;
- database migrations;
- mutable recursive state;
- feature-specific hashing or persistence;
- concurrency or checkpoint optimization; or
- changes to existing released feature values.

## 17. Approval and Completion Gate

This contract becomes authoritative only after explicit approval and freeze.

EMA-01 implementation remains blocked until the preconditions in Section 4
and the successor registry contract are approved. After authorization, the
implementation is complete only when:

- code matches the approved quantitative specification exactly;
- registry and implementation metadata match exactly;
- every architecture, validation, provenance, deterministic-execution,
  pipeline, registry, persistence, and testing obligation in this contract is
  satisfied;
- all required validation passes without waiver;
- architecture review confirms EMA-01-only scope; and
- the resulting registry and pipeline release identities are frozen without
  changing historical evidence.

Completion of EMA-01 does not authorize EMA-02 or any other feature family.
