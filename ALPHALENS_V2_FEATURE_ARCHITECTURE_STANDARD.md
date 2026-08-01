# AlphaLens v2 Feature Architecture Standard

**Document status:** Governing engineering standard

**Applies to:** All current and future AlphaLens v2 quantitative features

**Normative language:** The terms **MUST**, **MUST NOT**, **REQUIRED**,
**SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe
mandatory requirements, recommendations, and permitted behavior.

## Purpose

This document is the single governing engineering architecture standard for
all AlphaLens v2 quantitative features. It defines the shared rules for
numeric representation, availability, validation, dependencies, execution,
persistence, provenance, hashing, versioning, and reproducibility.

Every new or revised quantitative feature, including EMA, RSI, MACD,
Bollinger Bands, VWAP, ADX, and later feature families, SHALL conform to this
standard.

Future feature quantitative specifications SHALL define only feature
mathematics and feature-specific quantitative semantics. They SHALL NOT
redefine, replace, weaken, or duplicate the engineering architecture in this
document.

A feature quantitative specification may define only the matters necessary
to give the feature an unambiguous quantitative meaning, including:

- formula and mathematical operations;
- period, lookback, window membership, and seed parameters;
- initialization mathematics;
- first mathematically valid observation;
- output names, quantitative meaning, units, and valid mathematical domain;
- feature-specific intermediate rounding only when it is an intentional part
  of the approved mathematics; and
- feature-specific behavior that cannot be derived from this standard and
  does not contradict it.

A quantitative specification SHALL reference this document for all shared
engineering behavior. Copying architectural rules into a feature
specification does not give that specification authority to alter them.

## Scope and authority

This standard governs feature contracts, feature implementations, registry
entries, pipeline execution, live validation, persistence, provenance,
hashing, and tests.

The order of authority is:

1. this Feature Architecture Standard and other frozen core repository
   invariants;
2. approved feature-specific quantitative specifications;
3. approved feature implementation and registry contracts;
4. feature implementations and tests.

Lower-authority artifacts MUST conform to higher-authority artifacts. If an
approved quantitative specification conflicts with this standard,
implementation SHALL remain blocked until a successor quantitative
specification is explicitly reviewed and approved. An implementation SHALL
NOT silently reinterpret either document.

Changes to this standard require an explicit architecture change request,
impact analysis, approval, and versioned repository release. A feature task
does not authorize an exception to this standard.

## 1. Numeric Policy

### 1.1 Canonical representation

All quantitative source fields, dependency values, intermediate values, and
feature outputs MUST use finite `Decimal` representation within the feature
system. Binary floating-point values MUST NOT enter feature computation,
feature provenance, canonical serialization, hashing, or persistence.

Quantitative outputs MUST be representable by the canonical repository
feature-value quantum of 18 decimal places. An emitted feature value MUST be
quantized to `0.000000000000000001` using `ROUND_HALF_EVEN`.

Non-finite values, including NaN and positive or negative infinity, are
invalid and MUST cause fail-closed validation.

### 1.2 Working precision

Operations involving division, roots, smoothing, recursion, or other
precision-sensitive arithmetic MUST execute in an isolated Decimal context
with working precision of at least 50 significant digits. Ambient process
Decimal context MUST NOT affect semantic output.

Unless approved feature mathematics explicitly requires intermediate
quantization, implementations MUST retain working precision internally and
apply canonical quantization only at the emitted-output boundary.

### 1.3 Feature-specific numeric rules

A quantitative specification MAY define mathematically significant
intermediate rounding or domain constraints. Any such rule is part of the
feature's quantitative identity and MUST be explicit, deterministic, and
versioned.

A feature specification MUST NOT select `float32`, `float64`, an alternative
storage scale, an alternative repository-wide rounding mode, or a nullable
numeric representation.

## 2. Warm-Up Policy

Warm-up is the interval during which the approved mathematics does not yet
have sufficient historical observations to produce an output.

Each registered output MUST declare a positive `minimum_observations` value
consistent with its approved quantitative specification. Multi-output
features MAY have different warm-up boundaries for different outputs.

Before an output reaches its first valid observation:

- the feature MUST emit no value for that output and timestamp;
- the pipeline MUST represent the state as output omission;
- persistence MUST contain no feature-value record; and
- the feature MUST NOT emit or persist null, zero, NaN, a sentinel, a partial
  estimate, or a backfilled placeholder.

Once the warm-up boundary is reached, output coverage MUST exactly match the
registered contract for every eligible timestamp. Warm-up behavior is not a
missing-data policy and MUST NOT conceal invalid or discontinuous evidence.

## 3. Availability Policy

Every feature output MUST have an explicit, registered availability rule.
Unless a separately approved platform architecture version introduces
another rule, v2 candle-derived features use candle-close availability.

For a candle-derived value:

- `candle_timestamp` identifies the start of the canonical candle interval;
- `available_at` is the close of that interval under the registered
  timeframe; and
- the value MUST NOT be observable or consumed before `available_at`.

Timestamps MUST be timezone-aware, canonical UTC, and aligned to the declared
timeframe. Dependency availability MUST be no later than consumer
availability.

Availability semantics form part of registry metadata, provenance, hashing,
point-in-time validation, and version compatibility. They MUST NOT be inferred
from wall-clock execution time.

## 4. Missing-Data Policy

Feature execution is fail closed.

A required source field or declared dependency that is missing, null,
non-finite, invalid, unavailable, duplicated, unordered, version-incompatible,
or outside the immutable source snapshot MUST prevent computation of the
affected output or run as required by the pipeline contract.

The following behavior is prohibited unless a future architecture revision
explicitly authorizes it:

- forward-fill, backward-fill, or interpolation;
- substitution of zero or another sentinel;
- silent observation skipping;
- continuation of a recursive chain across a source gap;
- implicit reseeding after a missing predecessor;
- reading an undeclared fallback input; and
- emitting a null quantitative value.

Incomplete live candles MUST be excluded before source-snapshot creation.
Invalid completed candles MUST be rejected or quarantined by source
validation. Features MUST NOT contain private rules that silently ignore
invalid candles already admitted to a snapshot.

A deliberately sparse source or irregular-time feature requires a separate,
approved architecture extension. It MUST NOT be introduced through an
indicator-specific missing-data rule.

## 5. Canonical OHLCV Source Policy

Open, High, Low, Close, and Volume are canonical source fields, not calculated
features. Feature definitions MUST declare every OHLCV field they read through
typed required-input metadata.

Features MUST consume OHLCV only from the pipeline's validated, immutable
source snapshot. They MUST NOT query candles independently, read mutable live
state, bypass source validation, or use an undeclared field.

Canonical OHLCV fields MUST NOT be registered or persisted as passthrough
features merely to satisfy a dependency abstraction. A transformed price or
volume series, such as an adjusted, normalized, consolidated, or derived
series, has different semantics and MAY be registered as a derived feature
under its own approved specification and version.

The source snapshot MUST contain complete, valid, finite Decimal OHLCV values,
strictly increasing consecutive timestamps, canonical UTC alignment, declared
asset and quote scope, timeframe, and ingestion provenance.

## 6. Dependency Policy

The feature dependency graph contains dependencies between derived registered
features. Direct OHLCV fields are required source inputs and are not registry
dependencies.

Every derived dependency MUST declare:

- canonical feature identifier;
- exact semantic definition version;
- exact output names consumed; and
- compatibility with the consumer's scope and availability.

Dependencies MUST exist in the active registry, appear before their consumers
in deterministic topological order, and be acyclic. Undeclared, forward,
ambiguous, optional-fallback, and version-floating dependencies are
prohibited.

At execution time, dependency identity, version, output, timestamp,
availability, value representation, ordering, and coverage MUST be validated
before consumer computation. A mismatch MUST fail closed.

Ordered dependency membership MUST be preserved when order contributes to
reconstruction. A recursive predecessor from the same feature definition is
value lineage, not a registry self-dependency.

## 7. Recursive Feature Policy

A recursive feature is any feature whose current mathematical state depends
on one or more prior outputs or recursively accumulated values.

Before implementation, its quantitative specification MUST freeze:

- the recursive equation;
- coefficient or smoothing mathematics;
- initialization and seed mathematics;
- seed membership;
- first valid observation;
- the canonical initialization-origin policy; and
- any mathematically significant intermediate quantization.

The origin policy MUST make independent replay unambiguous. Earlier backfill,
origin replacement, or seed-policy change MUST NOT silently alter released
historical values. Such a change requires new versioned identities and a new
validated run.

The authoritative execution model is deterministic replay from an immutable
source snapshot. An implementation MAY hold predecessor state in memory
during one run, but MUST NOT depend on hidden mutable database state.
Persisted prior outputs are immutable evidence, not an unversioned mutable
calculation cache.

Recursive predecessor lineage MUST be reconstructable. A missing predecessor
after initialization invalidates the affected chain. Automatic resume,
reseed, or reset is prohibited.

Checkpointed or incremental execution MAY be introduced only after tests
prove exact equivalence to full replay, including identical values,
provenance, ordering, availability, and hashes.

## 8. Registry Policy

The Feature Registry is the canonical discovery, identity, dependency, and
execution-order mechanism for quantitative features.

Each registered definition MUST include:

- immutable canonical identifier;
- description and category;
- semantic definition version;
- required OHLCV source fields;
- supported assets, quote currencies, and timeframes as applicable;
- one or more uniquely identified outputs;
- each output's description and minimum observations;
- bounded or recursive history classification;
- maximum lookback for bounded features;
- continuity requirement;
- availability rule;
- implementation reference;
- exact dependency contracts;
- Decimal quantum; and
- any other metadata required by the active registry schema.

Identifiers and output names MUST follow repository naming rules and MUST be
unique within the active registry. Registered implementation metadata MUST
equal implementation metadata exactly.

Registry definitions MUST be deterministically ordered. Registration MUST
reject duplicates, invalid metadata, absent or later dependencies, dependency
cycles, incompatible versions, undeclared outputs, and unsupported scopes.

A released registry snapshot is immutable. Consumers MUST discover features
through canonical registry identity and MUST NOT infer definitions from class
names, file locations, display labels, or database rows.

## 9. Pipeline Policy

The feature pipeline MUST:

1. accept only an immutable, integrity-verified source snapshot;
2. validate scope, timeframe, timestamps, continuity, completeness, OHLCV,
   and source hashes;
3. resolve definitions from the active registry;
4. execute features in deterministic registry order;
5. validate all declared dependencies before computation;
6. validate implementation metadata against registry metadata;
7. validate exact output identity, coverage, warm-up, Decimal precision, and
   availability;
8. verify prefix invariance and future isolation;
9. build canonically ordered dependency memberships;
10. attach source, registry, pipeline, and point-in-time evidence;
11. compute canonical result hashes; and
12. reject the run if any required invariant fails.

Outputs MUST be sorted by canonical timestamp and registry output order.
Dependency memberships MUST be sorted by consumer identity and dependency
ordinal. Execution order MUST NOT depend on unordered collection iteration,
database return order, concurrency timing, locale, or process state.

Feature-specific implementations MUST NOT bypass shared pipeline validation
or reproduce registry, source, hashing, provenance, or persistence logic.

## 10. Persistence Policy

Persisted quantitative feature values MUST be immutable, finite, non-null
Decimal values compatible with `Numeric(38,18)`.

Persistence MUST be append-oriented and idempotent under the canonical value
identity. It MUST preserve:

- asset, quote currency, and timeframe;
- candle timestamp and availability;
- output identity and release identity;
- canonical value;
- pipeline run and version;
- source ingestion evidence;
- registry snapshot and hash;
- source and result hashes;
- derived dependency memberships; and
- point-in-time validation status.

Existing feature values MUST NOT be updated in place to reflect changed
mathematics, inputs, origin, precision, or implementation. A new approved
version and run MUST create new evidence.

Run activation and supersession MAY change which complete run is selected as
active, but MUST NOT rewrite or delete superseded values, memberships,
snapshots, hashes, or audit history.

Warm-up and invalid states MUST be represented by absence of persisted output,
not nullable feature rows. Mutable recursive state MUST NOT be stored as the
authoritative feature result.

## 11. Provenance Policy

Every persisted or externally consumed feature value MUST be reconstructable
from immutable evidence.

Required provenance includes, as applicable:

- feature identifier, definition version, and output name;
- asset, quote currency, and timeframe;
- candle timestamp and `available_at`;
- pipeline version and computation run;
- registry schema version, registry snapshot, and registry hash;
- source range, source ingestion batch membership, source data hash, and
  source provenance hash;
- ordered derived-feature dependency memberships;
- recursive predecessor lineage;
- availability-contract version;
- point-in-time validation result; and
- canonical result hash.

Direct same-timestamp OHLCV provenance is established by the output timestamp,
source ingestion reference, and immutable hashed source snapshot. Windowed
raw-source membership MUST be reconstructable from the approved mathematics,
canonical origin or lookback, and ordered source snapshot.

Derived dependency memberships MUST identify exact dependency definition,
version, output, timestamp, availability, and value. A dependency MUST NOT be
newer than its consumer's availability.

If a future feature cannot be exactly reconstructed using the existing
provenance model, its implementation SHALL remain blocked until an additive,
repository-wide provenance extension is approved. It MUST NOT invent private
or unpersisted lineage.

## 12. Hashing Policy

Hashing provides content identity and tamper evidence. Canonical hashing MUST
be deterministic and independent of runtime environment.

Hash inputs MUST use canonical:

- field names and ordering;
- UTF-8 serialization;
- Decimal string representation;
- UTC timestamp representation;
- registry ordering;
- output ordering;
- dependency ordering; and
- source-observation ordering.

Hash algorithms and canonical serialization rules MUST NOT change inside an
existing schema or pipeline version. Historical hashes MUST never be
rewritten or recomputed under new rules.

Adding or changing a definition, output, dependency, registry field,
execution semantic, source snapshot, or result MUST produce the appropriate
new registry, configuration, source, pipeline, or result identity. A new hash
for new content is required behavior and is not a violation of historical
hash preservation.

## 13. Versioning Policy

Released definitions, registry snapshots, pipeline contracts, availability
contracts, and hash schemas are immutable.

A feature definition version MUST change when any result-affecting semantic
changes, including:

- mathematics or parameters;
- seed or initialization;
- recursive origin;
- warm-up or first-valid observation;
- output identity, meaning, units, or domain;
- dependency identity, version, or membership;
- availability semantics;
- precision or mathematically significant rounding; or
- missing-data or continuity semantics.

Breaking semantic changes require a new major feature version. Compatible
additions or corrections MAY use minor or patch versions only when the
repository's semantic-version policy proves that existing output meaning and
reproduction remain unchanged.

Registry content changes require a new registry hash. Registry serialization
or validation-schema changes require a new registry schema version. Pipeline
result-semantic changes require a new pipeline version. Availability changes
require a new availability-contract version.

Historical versions MUST remain discoverable through persisted registry
snapshots and run evidence. Deprecation or retirement MUST prevent new
selection as appropriate without deleting historical evidence.

## 14. Testing Requirements

No feature may be registered, activated, or used by downstream research until
its required tests pass.

Every feature test suite MUST cover, where applicable:

- approved mathematical fixtures and independently calculated expected
  values;
- initialization and exact seed membership;
- first-valid observation and complete warm-up omission;
- minimum and boundary-length histories;
- source-field validation and declared-input enforcement;
- missing, incomplete, invalid, duplicate, unordered, and discontinuous
  observations;
- dependency identity, version, output, availability, ordering, and coverage;
- recursive predecessor failure and origin stability;
- Decimal-only input and output;
- canonical quantization and rounding boundaries;
- non-finite and out-of-domain results;
- deterministic repeated execution;
- isolation from ambient Decimal and process state;
- deterministic ordering;
- point-in-time availability;
- prefix invariance;
- future isolation;
- registry integration and canonical registry hashing;
- pipeline integration and result hashing;
- immutable persistence and idempotent replay;
- provenance and exact dependency reconstruction;
- full replay and checkpoint equivalence if incremental execution exists;
- existing feature regression protection; and
- fail-closed behavior for every violated invariant.

Validation before release MUST include repository linting, Python compilation,
focused feature tests, existing feature regressions, persistence tests when
applicable, and the full backend suite.

Tests MUST NOT weaken expected values merely to match an implementation.
Disagreement between approved mathematics and implementation blocks release.

## 15. Determinism Requirements

For identical approved definitions, registry snapshot, pipeline version,
source snapshot, scope, and configuration, repeated execution MUST produce
identical:

- output identities and values;
- timestamps and availability;
- output and dependency ordering;
- provenance memberships;
- registry, source, and result hashes; and
- validation outcomes.

Semantic results MUST NOT depend on machine architecture, operating system,
locale, timezone setting, unordered iteration, database query order, thread
schedule, process lifetime, wall-clock computation time, ambient Decimal
context, or mutable global state.

Any randomized operation is prohibited in deterministic feature computation.
If a later feature architecture permits randomness, its complete algorithm
and seed evidence require a separate approved standard revision.

## 16. Point-in-Time Requirements

A feature value may use only evidence whose availability is no later than the
feature value's `available_at`.

Feature computation MUST NOT use:

- a future candle or partial future candle;
- a later revision unavailable at the evaluation time;
- a dependency with later availability;
- a future aggregate, label, target, split, decision, or outcome; or
- execution-time knowledge that was absent from the immutable source
  snapshot.

Source timestamps, candle-close availability, dependency availability, and
run evidence MUST be validated and persisted. Point-in-time validation MUST
fail closed and MUST be included in activation eligibility.

## 17. Prefix Invariance Requirements

For any valid source sequence and any prefix of that sequence, computing the
feature on the prefix MUST produce exactly the same outputs for prefix
timestamps as computing it on the complete sequence.

Equality includes:

- output presence or omission;
- canonical Decimal value;
- identity and version;
- timestamp and availability;
- dependency membership and ordering; and
- deterministic hash inputs attributable to those values.

The pipeline MUST validate prefix invariance for new features using isolated
prefix computations or an equivalently strong approved proof. A failure blocks
persistence and activation.

Recursive origin, seed membership, missing-data handling, and checkpoint
behavior MUST be designed so that later suffix observations cannot change
earlier outputs.

## 18. Future Isolation Requirements

Feature computation MUST be causally isolated from all observations and
events after the output's availability boundary.

Appending, changing, or removing a future suffix MUST NOT alter any earlier
feature value, output availability, warm-up decision, dependency membership,
or feature-level provenance.

Future isolation applies to direct source fields, derived dependencies,
recursive state, source revisions, caching, parallel execution, persistence
lookup, and live-validation paths.

Research labels, targets, forward returns, model outcomes, trading decisions,
and later market context MUST never enter feature computation. Features are
descriptive point-in-time measurements, not retrospective or predictive
annotations.

Prefix invariance demonstrates stability under suffix extension; future
isolation additionally requires that the implementation has no hidden path to
future evidence. Both requirements MUST be tested and reviewed independently.

## Conformance and implementation gate

A future feature is architecture-conformant only when:

- its quantitative specification contains feature mathematics rather than a
  competing engineering architecture;
- its contracts and registry metadata conform to every applicable section of
  this standard;
- its implementation reuses repository infrastructure without duplicating
  cross-cutting logic;
- all deterministic, point-in-time, prefix-invariance, future-isolation,
  persistence, and provenance validations pass; and
- its release identities and hashes are new wherever content or semantics are
  new.

Any conflict, ambiguity, missing quantitative decision, provenance gap, or
requested architecture exception blocks implementation until resolved through
the appropriate approval process. Conformance for one feature does not
authorize implementation of another feature family.
