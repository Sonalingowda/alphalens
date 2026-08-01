# AlphaLens v2 MACD-01 Architecture Audit

**Audit status:** Passed

**Feature:** MACD-01

**Definition version:** `1.0.0`

**Pipeline version:** `2.5.0`

**Architecture authority:**
`ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

**Quantitative authority:**
`ALPHALENS_V2_MACD01_QUANTITATIVE_SPECIFICATION.md`

## 1. Audit Scope

This audit reviews only the MACD-01 implementation authorized for Phase 2.
It verifies quantitative conformance, EMA dependency reuse, registry and
pipeline integration, Decimal behavior, deterministic ordering, recursive
lineage, point-in-time correctness, prefix invariance, future isolation,
persistence compatibility, and hash stability.

No MACD variant, crossover, signal interpretation, Bollinger feature, VWAP,
ADX, Supertrend, strategy, or trading behavior was implemented.

## 2. Quantitative Conformance

MACD-01 implements the approved fixed periods:

- fast EMA period: 12;
- slow EMA period: 26; and
- signal EMA period: 9.

The line is the contemporaneous registered EMA-12 value minus the registered
EMA-26 value. Its first valid timestamp is the twenty-sixth canonical Close.

The signal uses the shared EMA calculation primitive on the compact MACD line
sequence. Its seed is the arithmetic mean of the first exactly nine MACD line
values, and subsequent values use the approved period-9 EMA recurrence. The
first signal is associated with the thirty-fourth canonical Close.

The histogram is the contemporaneous MACD line minus signal and begins at the
same thirty-fourth-observation boundary as the signal.

The focused suite verifies independently frozen nonlinear fixtures for all
three outputs, exact-zero constant-price behavior, and exact output counts and
timestamps at every warm-up boundary.

**Finding:** Conformant.

## 3. EMA Dependency Reuse

The MACD definition declares exact registry dependencies on:

- `exponential_moving_average_12` version `1.0.0`, output
  `exponential_moving_average_12`; and
- `exponential_moving_average_26` version `1.0.0`, output
  `exponential_moving_average_26`.

The implementation validates dependency identity, version, output name,
coverage, ordering, timestamp alignment, finite Decimal representation, and
canonical quantization before calculation.

MACD-01 does not read canonical Close to recalculate either fast or slow EMA.
It subtracts the exact registered dependency values supplied by the pipeline.

The signal calculation calls the existing shared
`exponential_moving_average` primitive with period 9 and the compact MACD line
series. No EMA formula was copied into the MACD implementation, and no
separate EMA-9 Close feature was introduced.

**Finding:** No duplicated EMA logic; dependency reuse is correct.

## 4. Registry Integration

The registry contains one new definition:

- identifier: `moving_average_convergence_divergence`;
- definition version: `1.0.0`;
- category: `momentum`;
- outputs, in order: `macd_line`, `macd_signal`, `macd_histogram`;
- minimum observations: 26, 34, and 34 respectively;
- history classification: recursive;
- continuity: required;
- availability: candle close; and
- exact EMA-12 and EMA-26 dependency contracts.

The definition occurs after both EMA dependencies in deterministic registry
order. Registry validation rejects missing, later, unversioned, or
output-incompatible dependencies.

The active registry schema remains `1.1.0`. The new deterministic registry
configuration hash is:

`43354e1f1d5de0659f8060d64663747a8cde5c72cec08765c8666254c9bc2919`

The frozen Tier-A registry hash remains unchanged:

`c89cdef54e4a59689259d18e0571ca5ab9dfebe713115c27dffd0818a6858aac`

**Finding:** Conformant.

## 5. Pipeline Integration and Ordering

Pipeline version `2.5.0` executes MACD-01 after EMA-12, EMA-26, the remaining
EMA family members, and RSI-01. Both declared EMA dependencies are therefore
resolved before MACD execution.

The shared pipeline continues to enforce:

- immutable source-snapshot integrity;
- exact implementation-to-registry metadata equality;
- dependency version and output compatibility;
- output coverage and per-output warm-up;
- canonical Decimal values;
- candle-close availability;
- prefix invariance;
- deterministic timestamp/output ordering;
- dependency membership validation;
- point-in-time validation; and
- canonical result hashing.

At a common timestamp, MACD outputs retain registered order: line, signal,
then histogram.

**Finding:** Conformant.

## 6. Decimal and Deterministic Execution

All inputs, intermediate line values, signal state, histogram values, and
outputs use Decimal arithmetic. Signal recursion and MACD arithmetic execute
inside an isolated 50-digit Decimal context. Canonical output quantization is
applied only at emitted-output boundaries through the shared quantizer.

Dependency validation uses the shared quantizer and is independent of ambient
Decimal precision. Focused tests execute MACD under a deliberately reduced
ambient Decimal context and obtain identical outputs.

Repeated execution of the same source snapshot produces identical values,
memberships, registry hash, and result hash.

**Finding:** Conformant.

## 7. Provenance Completeness

Every MACD line value records the exact same-timestamp EMA-12 and EMA-26
memberships. Definition-level recursive continuity records the preceding line
after initialization.

The initial signal records the ordered EMA-12 and EMA-26 memberships for all
nine MACD line seed timestamps. Each later signal records current EMA-12 and
EMA-26 plus the immediately preceding signal.

The initial histogram records the same complete nine-line seed evidence.
Each later histogram records current and preceding EMA pairs plus the
preceding histogram. Those memberships reconstruct the preceding signal as
the preceding line minus preceding histogram, then reconstruct the current
signal and histogram under the approved recurrence.

All dependency memberships preserve exact definition identifier, version,
output name, timestamp, availability, ordinal, and immutable value. No
dependency is newer than its consumer.

**Finding:** Every output is reconstructable from immutable registered
dependency evidence and approved mathematics.

## 8. Point-in-Time Correctness and Future Isolation

Every MACD output consumes only EMA evidence available at or before its own
candle-close availability. Signal initialization uses only the first nine
eligible historical line timestamps. Later signal and histogram calculations
use only current and preceding evidence.

Focused tests compare complete runs with strict prefixes and with a mutated
future suffix. All prior values and feature-level memberships remain exactly
unchanged. The changed final candle affects only eligible final outputs.

No future candle, future EMA value, future signal, target, label, outcome, or
execution-time information enters MACD computation.

**Finding:** Point-in-time correctness, prefix invariance, and future
isolation are preserved.

## 9. Persistence and Immutability

MACD-01 uses the existing generic intraday feature persistence path. No table,
column, migration, mutable recursive-state record, or MACD-specific storage
path was added.

The existing persistence model stores non-null `Numeric(38,18)` values,
pipeline and registry identities, source evidence, result hashes, and ordered
dependency memberships. Focused tests map every MACD membership to the exact
immutable persisted feature value it references.

Feature values and dependency declarations are frozen dataclasses. Mutation
attempts fail.

**Finding:** Conformant; no migration required.

## 10. Hash Stability

Adding MACD-01 intentionally creates new registry content and pipeline result
content. The new registry and result hashes are deterministic for identical
inputs.

Historical hash algorithms, canonical serialization, existing feature
definition versions, and frozen Tier-A registry evidence were not changed.
EMA dependency values and identities remain unchanged.

**Finding:** New content receives new hashes; historical hash semantics remain
stable.

## 11. Tests and Validation

Focused MACD-01 tests cover:

- metadata and exact dependency contracts;
- independently frozen nonlinear mathematical fixtures;
- line, signal, and histogram initialization;
- per-output warm-up omission;
- constant-price and signed-output behavior;
- registered EMA value consumption;
- single shared signal-EMA invocation;
- missing, mismatched, unordered, incomplete, non-finite, and incompatible
  dependencies;
- ambient Decimal isolation;
- immutable outputs and memberships;
- registry and pipeline order;
- exact reconstructable provenance;
- prefix invariance and future isolation;
- deterministic replay and hashing; and
- persistence membership mapping.

Release validation results:

- Ruff formatting check: passed;
- Ruff linting: passed;
- Python compilation: passed;
- focused MACD-01 tests: 12 passed;
- affected feature regression tests: 106 passed;
- full backend suite: 323 passed; and
- `git diff --check`: passed.

The full suite emits one pre-existing FastAPI/Starlette deprecation warning.
It does not affect MACD-01 behavior or validation.

## 12. Architecture Conclusion

MACD-01 complies with the Feature Architecture Standard and its approved
quantitative specification. It consumes registered EMA-12 and EMA-26 values,
reuses the shared EMA primitive only for the approved signal series, preserves
deterministic Decimal behavior and complete lineage, and integrates through
the existing registry, pipeline, validation, provenance, hashing, and
persistence infrastructure.

No architectural inconsistency or remaining MACD-01 implementation blocker
was identified. Only MACD-01 was implemented by this release.
