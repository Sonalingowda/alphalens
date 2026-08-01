# AlphaLens v2 Directional Movement Architecture Audit

**Audit scope:** Directional Movement feature family only

**Architecture authority:** `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`

**Quantitative authority:**
`ALPHALENS_V2_DIRECTIONAL_MOVEMENT_FAMILY_QUANTITATIVE_SPECIFICATION.md`

## 1. Audit Summary

The implementation conforms to the approved Directional Movement mathematics
and the permanent Feature Architecture Standard. It introduces exactly seven
quantitative outputs: positive and negative Directional Movement, positive and
negative Directional Indicator, DX, ADX, and ADXR.

The family is represented by five topologically ordered registered definitions:

1. `directional_movement` emits raw `positive_directional_movement` and
   `negative_directional_movement`;
2. `directional_indicators` consumes both registered movement outputs and
   registered `true_range` `1.0.0`;
3. `directional_index` consumes the registered DI pair;
4. `average_directional_index` consumes registered DX; and
5. `average_directional_movement_rating` consumes current and exactly
   14-observation-lagged registered ADX.

No unapproved indicator, interpretation threshold, regime, signal, or trading
logic was added.

## 2. Quantitative Compliance

The audited implementation fixes the period at 14 and implements the approved:

- strict dominant-movement comparison and zero-on-tie rule;
- one-time sums of observations 1 through 14 for smoothed movement and True
  Range initialization;
- Wilder smoothed-sum recurrence;
- exact zero results for zero smoothed True Range and zero DI sum;
- arithmetic ADX seed over the first 14 valid DX observations;
- Wilder ADX recurrence; and
- ADXR mean of current ADX and ADX lagged exactly 14 observations.

The first output boundaries are exactly two candles for raw DM, 15 for DI and
DX, 28 for ADX, and 42 for ADXR. Undefined warm-up values are omitted under the
repository-wide architecture policy.

## 3. Dependency Reuse and Duplication Review

The family consumes the registered `true_range` output and never recomputes
gap-aware True Range. DX consumes registered DI values, ADX consumes registered
DX, and ADXR consumes registered ADX. Downstream stages do not repeat upstream
calculations.

One shared `wilder_smoothed_sum` primitive was added to the existing feature
contracts module and is used for positive movement, negative movement, and True
Range smoothing. The three recurrences therefore share one implementation.

The existing `average_true_range` feature is deliberately not a mathematical
dependency. Its approved definition is a bounded 14-observation arithmetic
mean, while the Directional Movement specification explicitly requires an
internally maintained Wilder-smoothed True Range sum. Substituting arithmetic
ATR would change the approved DI mathematics. This is a quantitative
compatibility constraint, not duplicated ATR logic.

## 4. Decimal and Determinism Review

All source and derived values remain finite `Decimal` values. Calculations use
an isolated precision-50 Decimal context and shared half-even quantization to
18 fractional places only at registered output boundaries. The implementation
does not depend on ambient Decimal context.

The raw movement comparison, smoothing seeds, recursive transitions,
zero-denominator branches, dependency order, and output order contain no random
or provider-dependent behavior. Repeated execution produces identical values,
memberships, registry hash, and pipeline result hash.

## 5. Point-in-Time, Prefix, and Future-Isolation Review

Every raw movement uses only the current and immediately preceding completed
candle. Every derived dependency is contemporaneous or historical. ADXR uses
the exact historical ADX observation at `t-14`; no future evidence is read.

The shared pipeline recomputes every prefix and verifies exact equality with
the corresponding full-run prefix. Focused tests also mutate the final candle
and verify that every earlier family output remains unchanged. Point-in-time
availability remains the completed-candle close boundary inherited from the
architecture standard.

## 6. Registry and Pipeline Review

All definitions use immutable semantic version `1.0.0`, declare exact source
fields, output warm-up metadata, history classification, and version-pinned
dependency contracts. The production registry preserves dependency-before-
consumer ordering.

The intraday pipeline version advances from `2.6.0` to `2.7.0` because the
canonical registry, execution order, output set, dependency memberships, and
result hash payload have changed. Registry schema `1.1.0` remains sufficient;
no registry-schema revision is required.

The seven new outputs are appended in deterministic family order after the
existing statistical-volatility outputs. Pipeline validation enforces exact
warm-up coverage, unique output identities, quantized finite values, canonical
ordering, and valid recursive predecessor lineage.

## 7. Provenance and Persistence Review

Initial DI outputs retain all 14 registered movement observations and all 14
registered True Range observations used by the seed. Subsequent DI observations
retain the current movement, current True Range, and immediately preceding
same-output DI membership. Initial ADX retains the first 14 DX observations;
subsequent ADX retains current DX and preceding ADX. Every ADXR retains both
current and exactly lagged ADX.

The existing append-only persistence layer is output-agnostic and persists the
new immutable values, run memberships, ordered dependency memberships,
registry snapshot, and hashes without a schema change or migration. Focused
tests verify that every family membership resolves to an existing immutable
persisted value identity.

## 8. Hash Stability Review

No hashing algorithm, canonical serialization rule, field order rule, or hash
contract was modified. Registry and pipeline result hashes change only because
their already-defined canonical payloads now truthfully include the new
definitions, outputs, execution order, values, and dependency memberships.
Identical inputs reproduce identical hashes.

## 9. Test Coverage

Focused Directional Movement tests cover:

- metadata and topological dependency declarations;
- strict ties, inside bars, positive dominance, and negative dominance;
- exact one-sided DI, DX, ADX, and ADXR fixtures;
- flat-history and zero-denominator behavior;
- every warm-up boundary and first valid timestamp;
- missing dependencies and invalid or discontinuous source evidence;
- ambient Decimal-context isolation;
- immutable outputs;
- registry and pipeline ordering;
- exact dependency reuse and point-in-time provenance;
- deterministic replay and hash stability;
- prefix invariance and future isolation; and
- mapping of dependency evidence to immutable persistence rows.

Existing Tier A, ATR, EMA, RSI, MACD, statistical-volatility, registry,
pipeline, live-validation, and persistence regressions were retained and
updated only where the approved pipeline version or appended registry snapshot
changed.

## 10. Validation Results

- Ruff static analysis: passed.
- Python compilation of backend application and tests: passed.
- Focused Directional Movement suite: passed, 13 tests.
- Existing feature regression suite: passed, 113 tests.
- Full backend suite: passed, 348 tests.
- `git diff --check`: passed.

## 11. Final Audit Decision

The Directional Movement family is architecture-compliant and ready to freeze.
No implementation defect, duplicated indicator calculation, schema migration,
or remaining blocker was identified. Only the approved Directional Movement
family was implemented.
