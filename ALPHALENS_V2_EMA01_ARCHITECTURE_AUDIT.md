# AlphaLens v2 EMA-01 Architecture Audit

**Audit status:** Passed

**Scope:** EMA-01 successor implementation only

**Audit date:** 2026-08-01

## 1. Audit Summary

The EMA-01 successor implementation conforms to the approved Feature
Architecture Standard, EMA Architecture Reconciliation, Successor
Quantitative Specification, Successor Implementation Contract, and Successor
Registry Specification.

EMA-01 is registered as `exponential_moving_average` version `1.0.0`, consumes
canonical Close directly from the immutable source snapshot, emits one
non-null Decimal output after the approved warm-up boundary, and is appended
to deterministic pipeline version `2.2.0` after the previously approved ATR
definition.

The implementation reuses the existing shared Decimal EMA primitive,
intraday candle validation, canonical output quantization, registry,
prefix-invariance validation, source snapshots, feature-value dependency
memberships, immutable persistence, provenance hashing, and live-validation
path. It does not introduce a registered Close feature, nullable output,
binary floating-point calculation, mutable EMA state, direct persistence
lookup, or feature-specific hash path.

Every post-initialization EMA value retains one ordered value-level reference
to the immediately preceding EMA output. This recursive lineage is validated
without adding a registry self-dependency, so the registry graph remains
acyclic. The existing `feature_value_dependencies` infrastructure can persist
the lineage; no EMA-specific migration or table is required.

No implementation of EMA-02, RSI, MACD, Bollinger Bands, VWAP, ADX, trend
interpretation, momentum interpretation, market context, signals, ranking, or
another feature family was added.

## 2. Governing Documents Reviewed

The audit reviewed the complete approved successor document set:

- `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`;
- `ALPHALENS_V2_EMA_ARCHITECTURE_RECONCILIATION.md`;
- `ALPHALENS_V2_EMA01_SUCCESSOR_QUANTITATIVE_SPECIFICATION.md`;
- `ALPHALENS_V2_EMA01_SUCCESSOR_IMPLEMENTATION_CONTRACT.md`; and
- `ALPHALENS_V2_EMA01_SUCCESSOR_REGISTRY_SPECIFICATION.md`.

The superseded EMA implementation and registry documents were treated only as
historical context and did not control implementation decisions.

## 3. Architecture Verification

| Review area | Evidence | Result |
| --- | --- | --- |
| No duplicated logic | EMA delegates its recurrence and seed calculation to the existing shared Decimal EMA primitive and uses shared validation and quantization. | Pass |
| Correct dependency reuse | Close is a declared canonical source field. EMA has no derived registry dependency and rejects unexpected dependency input. | Pass |
| Decimal arithmetic | Source values are validated Decimal values; recurrence uses an isolated 50-digit context; emitted outputs use canonical 18-place half-even quantization. | Pass |
| Warm-up | The feature emits no record before the registered first-valid boundary and emits exact coverage afterward. | Pass |
| Recursive origin | The production loader selects all canonical persisted candles in chronological order. Snapshot range start, source data hash, provenance hash, and run evidence freeze the origin used by a run. | Pass |
| Recursive state | Higher-precision state remains local to one deterministic replay. Persisted quantized output is not used as hidden mutable calculation state. | Pass |
| Prefix invariance | Shared pipeline validation recomputes every source prefix, including dependency memberships; focused suffix tests preserve all earlier EMA outputs. | Pass |
| Future isolation | EMA uses only current Close and preceding state. Mutation of a future suffix changes no earlier EMA output or lineage. | Pass |
| Deterministic ordering | Registry append order, timestamp/output sorting, and dependency ordinals are canonical. EMA predecessor ordinal is always zero. | Pass |
| Point-in-time correctness | Each output is available only at its source candle close. Every predecessor is from the immediately preceding timestamp and is available before its consumer. | Pass |
| Fail-closed validation | Invalid Decimal, missing Close, incomplete or invalid candle, timestamp gap, duplicate, unsupported dependency, bad provenance, and omitted predecessor paths reject computation. | Pass |
| Immutable outputs | Feature and predecessor records are frozen value objects. Existing immutable persistence reconciliation is reused. | Pass |
| Registry integration | Canonical identity, output, source input, recursive classification, continuity, availability, quantum, and implementation reference match the successor registry specification. | Pass |
| Provenance completeness | Current Close is reconstructable from timestamp and immutable source snapshot; initialization is reconstructable from the frozen source origin; every later value identifies its exact persisted predecessor output. | Pass |
| Hash stability | Canonical result hashing includes EMA values and recursive memberships. Replays are identical. Historical Tier-A registry hash remains unchanged. | Pass |
| Pipeline ordering | Execution order is candle geometry, True Range, ATR-01, then EMA-01. | Pass |
| Persistence compatibility | Existing non-null `Numeric(38,18)` feature storage and ordered dependency table represent EMA without schema changes. | Pass |
| Test completeness | Focused tests cover quantitative fixtures, seed, recursion, precision, warm-up, invalid input, immutability, registry, pipeline, persistence mapping, provenance, determinism, prefix invariance, and future isolation. | Pass |

## 4. Quantitative Verification

The implementation preserves the approved EMA-01 mathematics without adding
parameters or alternate behavior.

Audit fixtures verify:

- exact approved initialization;
- exact first-valid observation;
- exact recursive updates;
- omission throughout mathematical warm-up;
- absence of feature-specific intermediate rounding;
- canonical output-boundary quantization;
- isolation from ambient Decimal context; and
- continued use of higher-precision in-run state where early quantization
  would change a later emitted value.

The feature emits one price-level output in the same units as canonical Close.
It emits no auxiliary coefficient, seed, distance, slope, crossover, status,
or signal output.

## 5. Registry and Hash Audit

The successor production registry has:

- registry schema version `1.1.0`;
- canonical EMA identifier `exponential_moving_average`;
- canonical EMA output `exponential_moving_average`;
- EMA definition version `1.0.0`;
- no EMA derived dependencies;
- current configuration hash
  `b84b1fa534df0279628f54262409788a57d4e3229f808e7fa2f8702c243d1a07`;
  and
- pipeline version `2.2.0`.

The frozen Tier-A registry retains its historical configuration hash:
`c89cdef54e4a59689259d18e0571ca5ab9dfebe713115c27dffd0818a6858aac`.

Adding EMA produces a new registry hash and pipeline version as required. It
does not mutate a historical registry snapshot or change the canonical hash
algorithm.

## 6. Persistence and Provenance Audit

No EMA-specific persistence model or migration was created.

The implementation reuses:

- immutable engineered feature values;
- feature pipeline run records;
- run-to-source membership;
- run-to-value membership;
- ordered feature-value dependency membership;
- source data and provenance hashes;
- registry snapshots and hashes;
- result hashes; and
- activation and supersession safeguards.

The initialization output has no fabricated predecessor. Each subsequent EMA
output has exactly one dependency membership pointing to the previous EMA
output of the same identifier, version, and output name at the immediately
preceding timestamp. Pipeline validation resolves that reference to the exact
canonical value, verifies its availability, includes it in result hashing,
and persistence maps it to the exact immutable stored row.

Production source loading selects the complete persisted canonical history for
the supported BTC/USD timeframe. If earlier backfill changes the recursive
origin and produces different values under an existing release identity,
immutable stored-value verification fails closed. Such a change requires the
new versioned release process mandated by the governing documents.

## 7. Files Reviewed for Implementation

### EMA files created

- `backend/app/features/ema.py`
- `backend/tests/test_ema_features.py`
- `ALPHALENS_V2_EMA01_ARCHITECTURE_AUDIT.md`

### Existing files modified for EMA integration

- `backend/app/features/registry.py`
- `backend/app/features/intraday_pipeline.py`
- `backend/tests/test_feature_registry.py`
- `backend/tests/test_intraday_feature_pipeline.py`
- `backend/tests/test_intraday_feature_persistence.py`
- `backend/tests/test_intraday_feature_live_validation.py`
- `backend/tests/test_atr_features.py`

The EMA implementation did not require changes to production persistence
models, production persistence functions, live-validation logic, shared
quantitative formulas, or the existing Alembic migration graph.

## 8. Validation Results

| Validation | Result |
| --- | --- |
| Ruff lint, complete backend | Pass |
| Python compilation, application, tests, and migrations | Pass |
| Focused EMA-01 tests | 14 passed |
| Existing feature regression selection | 67 passed |
| Full backend suite | 291 passed |
| Alembic graph | Pass; single head `20260802_0034` |
| Git whitespace/error check | Pass |

The installed Ruff formatter reports pre-existing formatting differences in
unrelated repository files. Those files were not reformatted because the
EMA-01 change request prohibits unrelated modifications. All EMA-touched
Python files pass the formatter check, and the required repository-wide Ruff
lint check passes.

## 9. Architectural Inconsistencies and Defects

No unresolved EMA-01 architectural inconsistency was found after the
implementation audit.

One required shared integration defect was resolved during implementation:
the ATR-era pipeline accepted only declared upstream feature dependencies and
could not represent value-level lineage from a recursive definition to its
own immediately previous output. Pipeline provenance validation now permits
that narrowly defined recursive predecessor while continuing to reject
registry self-dependencies, absent predecessors, wrong versions, wrong
outputs, nonadjacent timestamps, fabricated initialization predecessors, and
missing dependency values.

No additional functionality was introduced by that correction.

## 10. Remaining Blockers

There is no remaining implementation, validation, migration, or audit blocker
for EMA-01.

Activation against live or historical database evidence remains subject to
the existing operational requirements for complete canonical source history,
successful ingestion validation, absence of unresolved source conflicts, and
transactional persistence. These are standard runtime preconditions, not an
EMA architecture defect.

Every later Phase 2 feature, including EMA-02, RSI, MACD, Bollinger Bands,
VWAP, and ADX, remains blocked until separately specified and explicitly
approved.

## 11. Final Audit Decision

EMA-01 is compliant, deterministic, point-in-time correct, prefix invariant,
future isolated, provenance complete, registry integrated, and compatible
with immutable persistence.

The implementation is approved by this audit for commit and release as
EMA-01 only. No additional indicator implementation is included or
authorized.
