# AlphaLens v2 Phase 3 — Intraday Feature Engineering Plan

## Status

**Planning baseline:** Proposed for human review  
**Implementation status:** Not started  
**Authorized scope:** Architecture and implementation sequencing only

This document freezes the proposed feature-engineering architecture before
feature code is written. It does not approve a feature catalog, feature
formula, lookback parameter, decision rule, target, model, ranking method, or
confidence value.

The current implementation sequence calls this work Phase 3. The migration
blueprint describes the same dependency milestone as “Phase 2 — Intraday
feature engineering” because its numbering begins after the earlier contract
freeze. This plan follows the current Phase 3 name while preserving the
blueprint dependency order.

## Governing References

This plan is subordinate to:

- `AGENTS.md`;
- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PHASE_1_BASELINE.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `IMPLEMENTATION_ORDER.md`;
- `ALPHALENS_V2_MIGRATION_PLAN.md`;
- `COMPONENT_AUDIT.md`;
- `TARGET_ARCHITECTURE.md`;
- `RISK_ASSESSMENT.md`; and
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`.

Phase 2 is the only implementation prerequisite. Its approved output is the
validated, persisted BTC/USD `5m`, `10m`, and `15m` candle foundation.

Phase 3 must not implement decisions, targets, labels, models, opportunity
ranking, calibration, scanner behavior, chart overlays, or frontend behavior.

## Current-State Evidence and Reuse Boundary

The existing daily feature pipeline already provides reusable patterns:

- `backend/app/features/contracts.py` defines typed feature values, Decimal
  quantization, source-candle safeguards, and a small computation protocol.
- `backend/app/features/pipeline.py` uses a deterministic ordered feature list,
  validates outputs, and proves prefix invariance.
- Individual computations are isolated in
  `backend/app/features/moving_averages.py`,
  `backend/app/features/momentum.py`,
  `backend/app/features/volatility.py`, and
  `backend/app/features/volume.py`.
- `backend/app/persistence/features.py` records immutable feature runs and
  values.
- `feature_pipeline_runs` and `engineered_features` retain pipeline version,
  source batch, source hash, timestamps, and computation provenance.

These patterns remain reusable. The daily pipeline version `1.1.0` and its
feature meanings remain immutable v1 evidence. They must not be silently
redefined or reused as the identity of the new intraday pipeline.

The following current assumptions cannot be carried into Phase 3 unchanged:

1. persistence is hard-coded to BTC/USD `1d`;
2. a feature value stores its candle-open timestamp but not its actual
   availability time;
3. a feature run references only one ingestion batch, while an incrementally
   accumulated intraday dataset may contain candles originating in several
   batches;
4. an engineered feature row belongs to only its original computation run,
   which does not fully represent later immutable snapshot runs that reuse
   existing values and add new timestamps; and
5. the current ordered tuple is executable configuration but does not expose
   enough metadata to audit warm-up, required inputs, output availability, and
   supported timeframes before computation.

Phase 3 will extend these boundaries without rewriting or invalidating the
daily feature evidence.

## Architecture

### Processing flow

```text
Validated canonical candles for one timeframe
                |
                v
Source snapshot construction and hashing
                |
                v
Ordered, versioned feature registry
                |
                v
Independent deterministic feature computations
                |
                v
Output, warm-up, continuity, and prefix-invariance validation
                |
                v
Immutable feature values and snapshot membership
                |
                v
Feature-run provenance and activation
```

Each run processes exactly one market and one timeframe. The initial scope is
three independent BTC/USD runs: `5m`, `10m`, and `15m`. No feature may combine
timeframes in this phase. Cross-timeframe joins would introduce a separate
availability/alignment policy and require later explicit approval.

### Pipeline components

The Phase 3 pipeline will have the following responsibilities:

1. **Source snapshot builder**
   - Reads only complete, validated canonical candles for one timeframe.
   - Orders them strictly by UTC candle timestamp.
   - Verifies interval continuity and Phase 2 validation invariants.
   - Records the exact candle identities and all contributing ingestion
     batches.
   - Produces a deterministic source-data hash.

2. **Feature registry**
   - Supplies the only approved ordered set of feature specifications.
   - Rejects duplicate feature identifiers or output names.
   - Provides warm-up and availability metadata before execution.
   - Produces a deterministic registry/configuration hash.

3. **Feature executor**
   - Calls each approved feature independently.
   - Supplies the same immutable candle snapshot to every computation.
   - Does not permit one feature to read another feature’s output unless a
     future specification explicitly defines a derived-feature dependency.
   - Collects values without repairing inputs or outputs.

4. **Validation gate**
   - Validates input chronology, continuity, completeness, and exact Decimal
     values.
   - Validates output identity, timestamp alignment, availability,
     finiteness, warm-up behavior, and uniqueness.
   - Proves deterministic repeatability and prefix invariance.
   - Prevents persistence when any required guarantee fails.

5. **Persistence boundary**
   - Creates an immutable feature-run snapshot.
   - Stores only valid non-null Decimal feature values.
   - Links the run to every source ingestion batch and every value included in
     the snapshot.
   - Activates a run only after the complete run is persisted and verified.

The architecture remains an in-process module within the existing Research
Layer and Feature Engineering Layer. It does not introduce services,
microservices, plugins, queues, or dynamic runtime discovery.

## Feature Registry

### Registry form

The registry will be a small, explicit, ordered, code-owned collection. It is
not a plugin system and is not editable through an API or database.

Each registered feature specification must declare:

| Field | Purpose |
| --- | --- |
| Stable feature identifier | Names the quantitative definition independently of display text. |
| Definition version | Distinguishes approved formula or seed-policy changes. |
| Output names | Declares every scalar series emitted by the definition. |
| Required candle fields | States whether open, high, low, close, and/or volume are consumed. |
| Supported timeframes | Prevents accidental execution outside approved `5m`, `10m`, and `15m` scope. |
| Minimum observations per output | Defines the exact warm-up boundary for every emitted series. |
| Lookback type | Identifies bounded rolling or recursively stateful history requirements. |
| Maximum required lookback | Supports validation and downstream embargo analysis. |
| Continuity requirement | Declares that consecutive source observations are mandatory. |
| Availability rule | Defines when an output becomes observable relative to its source candle. |
| Numeric/rounding policy | Fixes Decimal precision and rounding behavior. |
| Implementation reference | Resolves the isolated computation called by the pipeline. |

The pipeline registry itself has a separate semantic version. Any change to
registry membership, order, feature definition version, parameters, seed
policy, output names, availability semantics, or rounding policy requires a
new pipeline version and configuration hash.

### Feature catalog approval boundary

No intraday feature catalog is approved by this plan.

The existing daily SMA, EMA, RSI, MACD, Bollinger Band, and volume features
are implementation evidence, not automatic authorization to reuse their
formulas or parameters intraday. Before the feature-computation milestone, a
catalog must explicitly approve:

- each feature and its purpose;
- the exact formula;
- all parameters;
- required candle fields;
- seeding behavior;
- output names;
- exact per-output warm-up observations;
- supported timeframes; and
- definition version.

This unresolved catalog is not a blocker for the first milestone, which
creates only the contracts, registry validation, and persistence foundation.
It is a blocker for implementing quantitative feature formulas.

## Point-in-Time Guarantees

### Source boundary

For an output aligned to candle-open timestamp `t` and timeframe duration
`D`:

- the computation may use only the candle at `t` and candles strictly before
  `t`;
- it may not use any candle after `t`;
- because the candle at `t` is an interval observation, the output is
  available no earlier than `t + D`; and
- downstream consumers must compare against the explicit availability
  timestamp, not assume availability at candle open.

The persisted record will therefore distinguish:

- **feature timestamp:** the source candle’s canonical open timestamp; and
- **available-at timestamp:** the close boundary of that completed candle.

For Phase 3, `available_at = candle_timestamp + timeframe_duration`. No
same-candle-open availability is permitted.

### Structural enforcement

Every feature must satisfy all of the following:

1. outputs are aligned only to source candle timestamps;
2. outputs never precede their declared warm-up boundary;
3. outputs contain no duplicate `(timestamp, output_name)` identity;
4. outputs are strictly chronological within each output series;
5. output `available_at` is derived from the approved timeframe;
6. recomputing a source prefix produces exactly the same outputs for that
   prefix as the full-series computation;
7. appending future candles cannot change an earlier value;
8. identical ordered input, registry, pipeline version, and Decimal policy
   produce byte-equivalent canonical values and identical hashes; and
9. persistence occurs only after all guarantees pass.

Prefix invariance remains the primary executable leakage check. Focused tests
must also mutate future candles and prove that every prior output is
unchanged.

## Warm-Up Requirements

Warm-up is defined in observations, not elapsed wall-clock time. A feature
with a declared minimum of `N` observations cannot emit before its exact
approved observation boundary.

Rules:

- Every output series declares its own minimum observation count.
- Multi-output definitions may have different warm-ups for different outputs.
- Rolling features require a complete window of the approved size.
- Recursive features require their complete approved seed history and seed
  method before their first value.
- “Best effort,” shorter-window substitution, future backfill, and
  partial-window output are prohibited.
- Legitimate warm-up absence is represented by omission of a feature row, not
  a numeric placeholder and not a persisted null.
- The first timestamp at which a complete vector exists is determined by the
  maximum warm-up across all required registry outputs.
- The run records expected and observed first-valid timestamps for each
  output. A mismatch fails validation.

Exact warm-up counts will be frozen with the approved feature catalog. They
must be derived from definitions, not selected after observing results.

## Missing Data Policy

Phase 3 uses a strict fail-closed policy.

### Source candles

A run fails before computation if its selected source snapshot contains:

- a missing candle inside the selected interval;
- an out-of-order or duplicate timestamp;
- a timestamp not aligned to its timeframe;
- an incomplete candle;
- a null required OHLCV value;
- an invalid OHLC relationship;
- a non-positive price;
- a negative volume; or
- unverifiable validation/provenance evidence.

The pipeline does not interpolate, forward-fill, backward-fill, resample,
fabricate, or silently skip source candles. It also does not compute across a
gap or automatically restart a recursive feature after a gap. Segment-based
restarts require a separately approved policy and are outside this phase.

Zero volume remains valid because the Phase 2 candle contract permits it.

### Feature outputs

- Missing output before the declared warm-up boundary is expected.
- Missing output at or after its declared first-valid boundary is invalid.
- Null, NaN, infinite, or non-Decimal output is invalid.
- A failed individual definition fails the entire feature run; a partial run
  cannot become active.
- Invalid values and validation failures are retained in run audit evidence,
  but invalid feature rows are not persisted as valid observations.

## Feature Provenance

Every immutable feature run must record:

- run identifier;
- asset and quote currency;
- timeframe;
- pipeline version;
- ordered registry/configuration hash;
- code version when available from the repository state;
- source candle count and exact range;
- source-data hash over canonical ordered OHLCV input;
- every contributing ingestion batch;
- feature definition identifiers and versions;
- feature parameters and warm-up metadata;
- Decimal precision and rounding policy;
- per-output expected and observed first-valid timestamps;
- computed value count and persisted value count;
- point-in-time and repeatability validation status;
- computation timestamp;
- run status; and
- supersession/activation metadata.

### Required persistence adjustment

The current single `source_ingestion_batch_id` remains as historical v1
evidence but is insufficient for an accumulated intraday snapshot. Phase 3
will add immutable run-to-source-batch membership so a run can identify every
batch that contributed its candles.

The current feature-value `computation_run_id` identifies the run that first
created a canonical value. A second immutable run using the same pipeline
version may legitimately reuse historical values and add only new
timestamps. Phase 3 will therefore add explicit run-to-feature-value
membership so every snapshot can enumerate its complete value set without
overwriting or duplicating canonical values.

No existing daily feature rows, run records, versions, or provenance links
will be rewritten.

## Validation Strategy

### Contract tests

- Registry rejects duplicate identifiers and output names.
- Registry rejects unsupported timeframes and incomplete metadata.
- Warm-up metadata is internally consistent.
- Pipeline and registry hashes are stable under identical input.
- Registry order is explicit and deterministic.

### Feature-definition tests

Required after a catalog is approved:

- known-input formula examples;
- exact Decimal expected outputs;
- exact first-valid timestamp;
- insufficient-history omission;
- deterministic repeatability;
- future-candle mutation isolation;
- prefix invariance for every prefix;
- malformed-input rejection; and
- timeframe support enforcement.

### Pipeline tests

- Each timeframe is processed independently.
- Only complete, continuous, validated candles are accepted.
- All registry outputs are validated.
- No expected post-warm-up values are absent.
- `available_at` equals the candle close boundary.
- Full-vector availability begins at the declared maximum warm-up.
- Registry and source hashes are deterministic.
- A failed feature prevents run activation.

### Persistence tests

- Existing values are immutable.
- Repeating an identical run creates no conflicting feature values.
- An expanding snapshot links both reused and newly inserted values.
- Every run resolves all source batches and feature values.
- Exactly one active successful run exists per asset, quote currency,
  timeframe, and pipeline identity.
- Activation occurs only after complete transactional persistence.
- Failed runs remain auditable and never become active.
- Existing daily feature evidence remains unchanged.

### Live verification

After feature definitions are approved and implemented:

1. run the pipeline separately over the persisted BTC/USD `5m`, `10m`, and
   `15m` datasets;
2. report source counts, source ranges, hashes, and contributing batch IDs;
3. report values and coverage per output;
4. report expected and actual first-valid timestamps;
5. verify no post-warm-up omissions;
6. verify availability timestamps;
7. repeat each run and verify identical values and hashes;
8. verify no historical values were overwritten; and
9. verify daily v1 feature records are unchanged.

Live verification is descriptive. It must not evaluate predictive usefulness,
correlation, targets, model performance, or trading outcomes.

## Implementation Milestones

### Milestone 1 — Contracts, registry foundation, and provenance schema

**Objective**

Create the typed intraday pipeline contracts, non-dynamic registry structure,
source snapshot contract, availability semantics, and persistence migrations
needed for complete run provenance. Do not implement quantitative feature
formulas.

**Expected files**

- Modify `backend/app/features/contracts.py`.
- Add a small registry module under `backend/app/features/`.
- Modify `backend/app/persistence/models.py`.
- Add one Alembic migration.
- Add focused contract, registry, migration-model, and provenance tests.

**Dependencies**

- Approved Phase 2 candle contract and persistence.
- Human approval of this Phase 3 plan.

**Expected outcome**

The repository can represent and validate an empty or test-only intraday
registry, explicit feature availability, many-batch source provenance, and
complete feature-run snapshot membership without computing production
features.

**Validation criteria**

- Registry metadata and ordering are deterministic.
- Duplicate or incomplete specifications are rejected.
- Availability boundaries are correct for `5m`, `10m`, and `15m`.
- New provenance relationships are immutable and preserve existing rows.
- Migration upgrades successfully.
- Existing tests remain green.

**Complexity:** M

### Milestone 2 — Approved feature catalog and isolated computations

**Objective**

Implement only the explicitly approved intraday feature definitions and exact
parameters, one isolated definition at a time.

**Dependency**

- Milestone 1.
- Explicit approval of the feature catalog, formulas, parameters, seeds, and
  warm-ups.

**Expected outcome**

Every approved feature passes formula, warm-up, Decimal, determinism, and
prefix-invariance tests independently.

**Complexity:** L, subject to the approved catalog.

### Milestone 3 — Intraday pipeline execution and validation

**Objective**

Execute the ordered approved registry against one validated source snapshot
per timeframe and enforce all pipeline-level guarantees.

**Dependencies**

- Milestones 1 and 2.

**Expected outcome**

Deterministic validated feature results exist in memory for BTC/USD `5m`,
`10m`, and `15m`, with no persistence or downstream decision consumption yet.

**Complexity:** M

### Milestone 4 — Immutable persistence and activation

**Objective**

Persist complete feature snapshots, canonical values, source memberships, and
run memberships transactionally.

**Dependencies**

- Milestone 3.

**Expected outcome**

Each timeframe has an auditable active feature run. Prior runs remain
immutable and expanding runs reuse historical canonical values without losing
snapshot membership.

**Complexity:** L

### Milestone 5 — Live verification and Phase 3 closure

**Objective**

Run and repeat the approved pipeline over live persisted Phase 2 evidence,
verify provenance and point-in-time behavior, and produce the Phase 3
readiness record.

**Dependencies**

- Milestone 4.

**Expected outcome**

All three intraday feature datasets are deterministic, reproducible,
auditable, aligned to availability timestamps, and ready to serve as the
input boundary for the later Decision Engine phase.

**Complexity:** M

## Decisions Frozen by Approval of This Plan

Approval freezes:

- one independent feature run per market and timeframe;
- an explicit ordered code-owned registry, not a plugin system;
- separate pipeline and definition versioning;
- explicit candle-close feature availability;
- observation-count warm-ups;
- omission-only legitimate warm-up handling;
- fail-closed missing-data handling;
- no interpolation or automatic gap segmentation;
- Decimal deterministic computation;
- prefix invariance as a mandatory point-in-time proof;
- immutable canonical values plus complete snapshot membership;
- many-batch source provenance; and
- no cross-timeframe features in Phase 3.

## Unresolved Decisions and Blockers

The following remain intentionally unresolved:

1. the approved intraday feature catalog;
2. exact formulas and parameters;
3. per-output warm-up counts;
4. recursive feature seed policies;
5. the new intraday pipeline version identifier; and
6. whether a later phase will approve cross-timeframe evidence.

Items 1 through 5 must be resolved before Milestone 2. They do not block
Milestone 1.

No model family, label, target, decision threshold, confidence metric,
opportunity score, or economic interpretation is decided in Phase 3.

## Phase Boundary

Approval of this plan authorizes only Milestone 1 unless the human instruction
explicitly authorizes more.

Phase 4 work must not begin until all Phase 3 milestones are completed,
verified, reviewed, and approved.
