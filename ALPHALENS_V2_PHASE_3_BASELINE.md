# AlphaLens v2 Phase 3 Approved Baseline

## Status

**Phase:** Phase 3 — Feature Engineering  
**Status:** Complete and human approved  
**Baseline date:** 2026-07-30  
**Pipeline version:** `2.0.0`

This document freezes the complete approved Phase 3 feature-engineering
contract, implementation boundary, and verification evidence for AlphaLens
v2. It is the normative baseline for all later consumers of intraday feature
data.

Historical Phase 3 contracts, feature meanings, pipeline runs, feature
values, hashes, and provenance records are immutable. A later implementation
must consume this baseline as recorded or follow the change-control process
defined in this document.

## Phase 3 Scope

Phase 3 establishes deterministic feature engineering for:

| Scope field | Approved value |
| --- | --- |
| Instrument | `BTC/USD` |
| Timeframes | `5m`, `10m`, `15m` |
| Source evidence | Complete, validated, canonical Phase 2 OHLCV candles |
| Native source intervals | Kraken `5m` and `15m` |
| Derived source interval | Deterministic `10m` candles derived from validated `5m` evidence |
| Feature tier | Tier-A only |
| Feature definitions | `candle_geometry`, `true_range` |
| Numeric representation | Exact `Decimal` |
| Feature availability | Completed-candle close boundary |
| Persistence | Immutable canonical values plus complete run memberships |

Phase 3 includes:

1. typed feature metadata and availability contracts;
2. an explicit, ordered, code-owned feature registry;
3. isolated Tier-A feature definitions;
4. deterministic source-snapshot construction;
5. point-in-time-safe pipeline execution;
6. warm-up, coverage, ordering, availability, and prefix-invariance
   validation;
7. transactional feature-run and feature-value persistence;
8. many-batch source and value-membership provenance;
9. immutable run activation and supersession; and
10. live Kraken validation for all three approved timeframes.

Phase 3 does not define or implement labels, targets, models, feature
selection, research experiments, `BUY`/`SELL`/`WAIT`, confidence, opportunity
ranking, scanner behavior, chart overlays, backtesting, or trading behavior.

## Approved Architecture

The approved processing path is:

```text
Validated canonical candles for one BTC/USD timeframe
                         |
                         v
Deterministic immutable source snapshot
  - ordered complete candles
  - source-data hash
  - source-provenance hash
  - contributing ingestion batches
                         |
                         v
Ordered versioned Feature Registry
  - registry schema
  - availability contract
  - definition metadata
  - registry hash
                         |
                         v
Isolated Tier-A feature computations
  - candle_geometry
  - true_range
                         |
                         v
Pipeline validation gate
  - chronology and continuity
  - warm-up and complete coverage
  - availability
  - deterministic ordering
  - prefix invariance
  - Decimal precision
                         |
                         v
Transactional persistence
  - immutable canonical values
  - source memberships
  - value memberships
  - run hashes and registry snapshot
                         |
                         v
Verified active feature run per timeframe
```

Each execution processes exactly one market and one timeframe. Cross-timeframe
feature computation is not part of this baseline. The registry is a static,
explicit collection owned by the codebase; it is not a plugin system,
database-configurable registry, API-managed registry, or dynamic discovery
mechanism.

### Approved implementation boundaries

| Responsibility | Approved implementation |
| --- | --- |
| Feature contracts and safeguards | `backend/app/features/contracts.py` |
| Registry metadata and hashing | `backend/app/features/registry.py` |
| Tier-A definitions | `backend/app/features/tier_a.py` |
| Snapshot and pipeline orchestration | `backend/app/features/intraday_pipeline.py` |
| Live validation orchestration | `backend/app/features/live_validation.py` |
| Transactional persistence | `backend/app/persistence/intraday_features.py` |
| Persistence models | `backend/app/persistence/models.py` |

## Approved Version and Registry Identity

| Identity | Approved value |
| --- | --- |
| Intraday feature pipeline version | `2.0.0` |
| Registry schema version | `1.0.0` |
| Feature availability contract version | `1.0.0` |
| Tier-A feature-definition version | `1.0.0` |
| Registry hash | `c89cdef54e4a59689259d18e0571ca5ab9dfebe713115c27dffd0818a6858aac` |
| Decimal quantum | `0.000000000000000001` |
| Decimal arithmetic precision | 50 digits |
| Rounding mode | `ROUND_HALF_EVEN` |

The registry ordering is immutable for pipeline `2.0.0`:

1. `candle_geometry`;
2. `true_range`.

The output ordering is immutable:

1. `candle_body_fraction`;
2. `candle_range_fraction`;
3. `upper_wick_fraction`;
4. `lower_wick_fraction`;
5. `true_range`.

The registry hash is calculated from the canonical, deterministically ordered
registry payload, including schema and availability versions, definition
metadata, inputs, timeframes, outputs, warm-ups, history properties,
continuity, availability, implementation references, dependencies, and
Decimal policy.

## Tier-A Feature Definitions

### `candle_geometry`

| Attribute | Approved definition |
| --- | --- |
| Definition version | `1.0.0` |
| Category | Price action |
| Inputs | Completed open, high, low, and close at observation `t` |
| Supported timeframes | `5m`, `10m`, `15m` |
| Warm-up | One consecutive completed candle |
| Availability | `t + D`, where `D` is the timeframe duration |
| History type | Bounded |
| Maximum lookback | One observation |
| Registered dependencies | None |

For open \(O_t\), high \(H_t\), low \(L_t\), and close \(C_t\):

\[
\operatorname{candle\_body\_fraction}_t
=
\frac{C_t-O_t}{O_t}
\]

\[
\operatorname{candle\_range\_fraction}_t
=
\frac{H_t-L_t}{O_t}
\]

\[
\operatorname{upper\_wick\_fraction}_t
=
\frac{H_t-\max(O_t,C_t)}{O_t}
\]

\[
\operatorname{lower\_wick\_fraction}_t
=
\frac{\min(O_t,C_t)-L_t}{O_t}
\]

All four outputs are emitted together for each eligible candle. Partial
output sets are invalid. Zero-range candles remain defined because
normalization uses the strictly positive open price. Values are not clipped.

Required invariants include:

- total range, upper wick, and lower wick are non-negative;
- absolute signed body does not exceed total range; and
- before final quantization, total range equals absolute body plus upper and
  lower wick.

### `true_range`

| Attribute | Approved definition |
| --- | --- |
| Definition version | `1.0.0` |
| Category | Volatility |
| Inputs | Completed high and low at `t`; completed close at `t-1` |
| Supported timeframes | `5m`, `10m`, `15m` |
| Warm-up | Two consecutive completed candles |
| Availability | `t + D`, where `D` is the timeframe duration |
| History type | Bounded |
| Maximum lookback | Two observations |
| Registered dependencies | None |

The preceding close must come from exactly one timeframe observation before
the current candle:

\[
\operatorname{timestamp}(C_{t-1})=t-D
\]

The approved output is:

\[
\operatorname{true\_range}_t
=
\max\left(
H_t-L_t,
\left|H_t-C_{t-1}\right|,
\left|L_t-C_{t-1}\right|
\right)
\]

The first candle has no True Range row. From the second consecutive candle
onward, one value is required for every candle. The output remains in
BTC/USD quote-price units and is not normalized or annualized.

Required invariants include:

\[
\operatorname{true\_range}_t \ge 0
\]

and:

\[
\operatorname{true\_range}_t \ge H_t-L_t
\]

## Feature Availability Contract

For a canonical candle-open timestamp `t` and timeframe duration `D`:

```text
available_at = t + D
```

| Timeframe | Availability offset |
| --- | --- |
| `5m` | 5 minutes |
| `10m` | 10 minutes |
| `15m` | 15 minutes |

No Phase 3 feature is available at candle open. An output may use the
completed candle at `t` and earlier completed observations, but never a candle
after `t`. Downstream systems must use `available_at`; the feature timestamp
alone does not establish availability.

Warm-up is measured in consecutive observations, not elapsed time.
Legitimate warm-up absence is represented by omission. Nulls, zeros,
shortened windows, later backfill, or placeholders must not represent
insufficient history.

## Pipeline Execution Guarantees

Pipeline `2.0.0` guarantees:

1. **Complete sources only.** Incomplete candles are rejected before snapshot
   construction.
2. **Canonical scope.** Only BTC/USD `5m`, `10m`, and `15m` snapshots are
   accepted.
3. **Strict chronology.** Candle timestamps are strictly increasing,
   gap-free, and exactly one timeframe duration apart.
4. **UTC alignment.** Every timestamp is timezone-aware, canonical UTC, and
   aligned to its timeframe.
5. **Validated OHLCV.** Prices are finite and positive, volume is finite and
   non-negative, and OHLC relationships are valid.
6. **Immutable snapshots.** Source data and ingestion provenance are
   canonicalized and independently hashed.
7. **Registry-only execution.** Every executed definition and output must
   match the approved ordered registry.
8. **Dependency order.** A declared dependency must already have executed;
   the current Tier-A definitions declare no inter-feature dependencies.
9. **Exact warm-up.** Every declared output appears at every eligible
   timestamp and never before its approved observation boundary.
10. **Exact Decimal output.** Values are finite `Decimal` instances quantized
    to 18 decimal places with `ROUND_HALF_EVEN`.
11. **Deterministic ordering.** Values are ordered by candle timestamp and
    approved output order.
12. **Duplicate prevention.** A pipeline result cannot contain duplicate
    `(candle_timestamp, output_name)` identities.
13. **Availability enforcement.** Every value has the exact approved
    candle-close `available_at`.
14. **Prefix invariance.** Recomputing every source prefix produces exactly
    the same corresponding values as the full computation.
15. **Future isolation.** Appending or changing later candles cannot alter an
    earlier valid output.
16. **Deterministic results.** Identical source evidence, provenance,
    registry, versions, and numeric policy produce identical values and
    result hashes.
17. **Fail-closed behavior.** Any source, metadata, calculation, coverage,
    availability, precision, or integrity failure prevents persistence.

The pipeline does not interpolate, forward-fill, backward-fill, resample,
repair, fabricate, silently skip, or automatically segment invalid source
data.

## Persistence Guarantees

Phase 3 persistence guarantees:

1. Each feature run is written inside one database transaction.
2. The supplied pipeline result is deterministically recomputed and compared
   before persistence.
3. Persisted source candles and ingestion batches are verified against the
   immutable source snapshot.
4. Canonical feature values retain the existing uniqueness identity:
   instrument, quote currency, timeframe, candle timestamp, feature name, and
   pipeline version.
5. Existing values are never updated or overwritten.
6. An exact existing value may be reused by a later immutable run.
7. A conflicting existing value, availability timestamp, or source
   provenance fails closed.
8. Repeated execution inserts only genuinely new canonical feature
   identities.
9. Every run records all source-batch memberships.
10. Every run records membership for its complete feature-value snapshot,
    including reused values.
11. Persisted value count must equal computed value count before activation.
12. Source and value membership counts must be complete before activation.
13. Active-run promotion is the final database mutation in the transaction
    and becomes visible only when the transaction commits.
14. Promotion supersedes prior active runs without deleting them.
15. Any failure rolls back the complete transaction.
16. Historical daily v1 feature evidence remains unchanged.

Exactly one successful active pipeline `2.0.0` run is permitted for each
approved market/timeframe identity. Superseded runs remain immutable and
auditable.

## Provenance Guarantees

Every active Phase 3 feature dataset is traceable through:

- feature-run identifier;
- asset, quote currency, and timeframe;
- pipeline version;
- registry schema version;
- availability contract version;
- complete canonical registry snapshot;
- registry hash;
- source candle count and exact range;
- source-data hash over ordered OHLCV values;
- source-provenance hash over candle values, completeness, and ingestion
  batch identity;
- every contributing ingestion batch;
- per-batch source count, range, and subset hash;
- feature identifiers and definition versions;
- output names, candle timestamps, and availability timestamps;
- exact Decimal feature values;
- original computation-run identity for each canonical value;
- complete run-to-value membership;
- computed and persisted value counts;
- point-in-time validation status;
- result hash;
- computation time;
- active status; and
- supersession time for prior runs.

The source-data hash distinguishes market values from provenance. Identical
OHLCV values with different ingestion evidence retain the same data semantics
but different provenance evidence.

The result hash commits to:

- pipeline version;
- source-data hash;
- source-provenance hash;
- registry hash;
- registry schema version;
- availability contract version;
- execution order; and
- every ordered feature identity, definition version, timestamp,
  `available_at`, and exact value.

## Live Validation Baseline

Live validation used the approved keyless Kraken public OHLC endpoint and the
existing Phase 2 ingestion path. Kraken-native `5m` and `15m` candles were
fetched directly. `10m` candles were deterministically derived from validated
`5m` evidence.

One open provider candle was observed and excluded for each timeframe. No
incomplete candle entered a feature snapshot, feature computation, or
canonical persistence record.

### Live dataset and idempotency evidence

| Timeframe | Source candles | Expected feature values | First-run inserted | Second-run inserted | Second-run reused | Source batches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `5m` | 746 | 3,729 | 130 | 0 | 3,729 | 2 |
| `10m` | 372 | 1,859 | 1,859 | 0 | 1,859 | 2 |
| `15m` | 729 | 3,644 | 3,644 | 0 | 3,644 | 2 |

The expected complete Tier-A value count for `N` source candles is:

```text
(4 × N candle-geometry values) + (N − 1 true-range values)
= 5 × N − 1
```

The first `5m` live run reused the previously validated Milestone 4 history
and inserted the 130 genuinely new values required by the expanded canonical
snapshot. The second run for every timeframe inserted zero values and reused
the complete canonical value set.

### Live integrity evidence

| Timeframe | Source-data hash | Source-provenance hash | Result hash |
| --- | --- | --- | --- |
| `5m` | `824b04e6f36ff2590b271e71a9b0656228fad829cb67d927bc2917e7e37f4c9d` | `e165ce23d2cea2c4791b82ff4ee532e47fdeec19dbc8ae3accd42a305604d9c5` | `5c087588c56977ae4143dcb145d3b8884cd24116aebc770733198b5fbfc3b363` |
| `10m` | `e6c0f9e6e843b75156d7f6e2898bc6b8d68e315ea4006b1de7b020e470c9b8d5` | `098abea17ad4791d48e04902e7a45531851317fc96809f839f0f1e88a3cb1752` | `60cf4c68bcee4cfbbef7e44d10eb00dd1c4dfe874743da30bcde68dcc330abaa` |
| `15m` | `3a62f5d6fc777b3a3bf44e47fbd896e59d1973ca72d31d807a6fdb9ce159a1b0` | `619e672da5bb5387d2074df394d964d03520f39a2e0a8066ae66e01d1b653eb2` | `309700a7a4586c858fef3f2887d55e9a6981b5bd5a83917956ed9965d4fc1ca9` |

Both executions for each timeframe produced identical source, provenance,
registry, and result hashes.

### Approved active runs at baseline creation

| Timeframe | Active run ID | Canonical values | Value memberships | Incomplete source candles |
| --- | --- | ---: | ---: | ---: |
| `5m` | `5303427d-fe36-43a4-9a48-643f8db00986` | 3,729 | 3,729 | 0 |
| `10m` | `e793ff7e-cc0b-48b3-84ae-72daf2c82e01` | 1,859 | 1,859 | 0 |
| `15m` | `1567b028-f0cd-45eb-8eb6-58ecfdd043b9` | 3,644 | 3,644 | 0 |

Direct PostgreSQL verification found exactly one active pipeline `2.0.0` run
per timeframe. Computed, persisted, canonical, and membership counts matched
for each active run.

## Test Baseline

At Phase 3 approval:

- Python compilation passed;
- Ruff checks passed;
- Alembic revision `20260730_0026` was current;
- all **170 backend automated tests passed**; and
- Git whitespace validation passed.

Phase 3 coverage includes:

- metadata and registry validation;
- duplicate definition and output rejection;
- feature formula examples and Decimal precision;
- supported-timeframe enforcement;
- warm-up omission and exact first-valid observations;
- malformed and incomplete source rejection;
- deterministic feature outputs;
- prefix invariance and future-candle mutation isolation;
- snapshot data and provenance hash semantics;
- availability timestamp enforcement;
- pipeline ordering, coverage, and duplicate prevention;
- deterministic pipeline result hashes;
- transactional persistence;
- rollback before activation;
- immutable value-conflict rejection;
- source and value memberships;
- active-run promotion and supersession;
- repeated-run idempotency;
- live 5m, 10m, and 15m orchestration; and
- incomplete live-candle exclusion.

The principal Phase 3 test files are:

- `backend/tests/test_feature_registry.py`;
- `backend/tests/test_tier_a_features.py`;
- `backend/tests/test_intraday_feature_pipeline.py`;
- `backend/tests/test_intraday_feature_persistence.py`; and
- `backend/tests/test_intraday_feature_live_validation.py`.

## Database Migration Baseline

| Revision | Purpose | SHA-256 |
| --- | --- | --- |
| `20260730_0024` | Adds intraday derivation provenance and canonical UTC alignment constraints used by Phase 2/3 source evidence. | `561b10cafbf7b16eb58f6b61400097b54aa99701bfffb0a07967679f0625bf0a` |
| `20260730_0025` | Adds registry metadata, explicit feature availability, run-to-source membership, and run-to-value membership. | `0e3b21ac90da642396045dc6342b79e3a7c6a5953c553457f0c780694ca062fa` |
| `20260730_0026` | Adds immutable source-provenance and pipeline-result hashes to feature runs. | `b9e6a508c2046ed7776420b26ef0d344fc04496fe4759fe70c6fd833d0f288b4` |

Revision `20260730_0026` is the approved database head for the Phase 3
baseline.

## Active Invariants

The following invariants are mandatory for every use of this baseline:

1. The approved market is BTC/USD.
2. The approved timeframes are independently computed `5m`, `10m`, and
   `15m`.
3. Only complete, validated, canonical, continuous candles enter the feature
   pipeline.
4. `10m` market evidence retains deterministic derivation provenance from
   validated `5m` candles.
5. Feature pipeline identity is `2.0.0`.
6. Registry schema identity is `1.0.0`.
7. Availability contract identity is `1.0.0`.
8. The registry hash is
   `c89cdef54e4a59689259d18e0571ca5ab9dfebe713115c27dffd0818a6858aac`.
9. The registry contains only `candle_geometry` followed by `true_range`.
10. Both feature definitions use version `1.0.0`.
11. Every feature value is available only at its completed candle’s close
    boundary.
12. Warm-up absence is omission only.
13. Every value uses the approved exact Decimal and rounding policy.
14. Prefix invariance and deterministic repeatability are required.
15. Invalid source or output evidence fails closed.
16. Canonical feature values are immutable and never overwritten.
17. Every run identifies all source batches and all feature values in its
    snapshot.
18. Run activation requires complete transactional persistence and
    verification.
19. Superseded runs and historical values remain auditable.
20. Pipeline and provenance hashes must verify before downstream use.
21. No Phase 3 feature implies predictive utility, causality, confidence, a
    decision, or a trading outcome.
22. No downstream phase may silently reinterpret a Phase 3 timestamp as
    feature availability.

## Explicitly Unresolved Research Decisions

The following remain unresolved and are not authorized by Phase 3:

1. inclusion of any Feature Catalog candidate beyond Candle Geometry and
   True Range;
2. any Tier-B or Tier-C feature set;
3. normalized, averaged, rolling, annualized, or thresholded True Range
   variants;
4. lookback windows, smoothing parameters, multipliers, thresholds, or
   normalization policies for future features;
5. seed policy for any future recursive feature;
6. cross-timeframe feature definitions, joins, alignment, or availability
   policy;
7. feature selection or claims of predictive usefulness;
8. research-experiment use of the Tier-A feature set;
9. target or label definitions;
10. model families, training, tuning, or inference;
11. `BUY`, `SELL`, or `WAIT` decision policy;
12. opportunity scoring or ranking;
13. confidence metrics, calibration method, thresholds, or presentation;
14. scanner and chart-overlay consumption semantics; and
15. economic, trading, or causal interpretation of any feature.

These decisions require their own research specification and explicit human
approval. Their unresolved status does not weaken the approved deterministic
data, feature, persistence, or provenance guarantees in this baseline.

The pipeline version, Tier-A membership, formulas, outputs, warm-ups,
availability, and numeric policy are resolved for this baseline and are not
unresolved decisions.

## Governing Artifact Hash Manifest

The hashes below are SHA-256 digests over the exact repository file bytes at
baseline creation.

### Permanent research and agent governance

| Artifact | SHA-256 |
| --- | --- |
| `AGENTS.md` | `49017eb9621b0132764582561b41bb1b5732223545ccf89a198fa773fd43faf0` |
| `RESEARCH_CONSTITUTION.md` | `4ac07a0f90823460dd000abeead335d4270ba72e55517351d712c64563ae911e` |

### AlphaLens v2 architecture baseline

| Artifact | SHA-256 |
| --- | --- |
| `ALPHALENS_V2_MIGRATION_PLAN.md` | `8ac1e60159ddc1776f334c7eba9e8a2606ade863f452400e1237e81d1c297b2c` |
| `COMPONENT_AUDIT.md` | `96c20897da37bfef99d311dd045d920d298163ce86c8430f95e5c3ea31a58914` |
| `IMPLEMENTATION_ORDER.md` | `7c0aff728bce715fdc224046fb1cfdeb2deb48845a393cc030c405ef2b0676a1` |
| `TARGET_ARCHITECTURE.md` | `101583eaf50de0ec3962428b6250ecbbeae0f4413c82222403f584fff962f60a` |
| `RISK_ASSESSMENT.md` | `3fd744e8c209af812230385d22969305c5322a16a527bb5595de104a69234401` |
| `ASSUMPTIONS_AND_UNKNOWNS.md` | `fc75db2cc37ee618dd1523d47b2aae9af8e25de76d359a4b249dede84ef0cd3f` |

### Approved Phase 1 contracts inherited by Phase 3

| Artifact | SHA-256 |
| --- | --- |
| `ALPHALENS_V2_PRODUCT_CONTRACT.md` | `89525bd09cafbb4fff3d8db26a2ddfc39f495f92d2264795c7a0d8030024a196` |
| `ALPHALENS_V2_DECISION_CONTRACT.md` | `3b75a9f409cf43cdf0bfe5825bb20d26d8a214554345af65ead15bd5224818d6` |
| `ALPHALENS_V2_CONFIDENCE_POLICY.md` | `ee5e39a7c6c90fb6c268110c1b0a80db143548c48e559056ba29a2f226e8502d` |
| `ALPHALENS_V2_PHASE_1_ALIGNMENT_RECORD.md` | `cc9a490e490aef27cbf0506d1de2868925d7d0b1f6dee043000ba89910b51e7e` |
| `ALPHALENS_V2_PHASE_1_BASELINE.md` | `1b74d98c07b19a558b0b42d53741573bccc17ef34fbff802d9cafcce71367c65` |

### Direct Phase 2 and Phase 3 contracts

| Artifact | SHA-256 |
| --- | --- |
| `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md` | `712bd76b45aa70c899fe8212c2840daa8582a32227c4fb1594e205c79a8f91e1` |
| `ALPHALENS_V2_PHASE_3_FEATURE_ENGINEERING_PLAN.md` | `b2a78c4780e17af52714f13015aaf0bea173e49d477f9cc403895c8413aeb61b` |
| `ALPHALENS_V2_FEATURE_CATALOG_PROPOSAL.md` | `b845ba40062ee34ee39ac9529b373e3df29a97fd603d49ca5b578e559794cefb` |
| `ALPHALENS_V2_TIER_A_FEATURE_SPECIFICATION.md` | `2b88c7e679b8e4f7a892e3bf7dee060aaae6004242212bdda3ef18bd97fbfa42` |

The candidate status text retained inside the planning, catalog, and Tier-A
specification documents records their pre-implementation state. The explicit
human approvals and this completion baseline supersede those status labels
without rewriting historical governance documents.

## Change Control

Phase 3 contracts and infrastructure must not be modified merely for
convenience, stylistic preference, implementation simplification, observed
model performance, or downstream consumer requirements.

Every proposed modification must include, before implementation:

1. **Change rationale**
   - the documented architectural, quantitative, data-quality, or
     reproducibility issue;
   - why the approved Phase 3 baseline cannot remain unchanged; and
   - the exact contract, implementation symbol, schema object, or invariant
     affected.
2. **Impact assessment**
   - effect on feature meanings, timestamps, availability, warm-up, Decimal
     values, hashes, provenance, and active datasets;
   - effect on downstream research, decision, scanner, API, overlay, and
     frontend consumers;
   - backward-compatibility consequences; and
   - whether historical results remain reproducible without reinterpretation.
3. **Migration strategy**
   - new definition, registry, availability, and pipeline versions where
     applicable;
   - additive schema/data migration steps;
   - preservation of historical rows and run evidence;
   - consumer transition and validation procedure;
   - deterministic replay or recomputation boundaries; and
   - rollback strategy that does not delete or rewrite prior evidence.
4. **Explicit human approval**
   - approval must identify the proposed semantic change and its scope;
   - approval must precede implementation; and
   - implementation completion requires regenerated artifact hashes and an
     updated alignment or baseline record.

Any change to registry membership or order, feature identifiers, output
names, formulas, definition versions, parameters, warm-ups, supported
timeframes, dependencies, availability, Decimal policy, hash construction,
persistence identity, provenance, activation rules, or validation guarantees
requires change control.

Silent edits, in-place semantic redefinition, retroactive hash changes,
overwriting historical values, and implementation-led contract changes are
prohibited.

## Phase Boundary

Phase 3 is complete.

This baseline does not authorize labels, targets, research experiments,
models, decisions, confidence, ranking, scanner behavior, overlays, or any
other later phase. Further work requires an explicit human instruction under
the approved implementation order and this baseline’s change-control rules.
