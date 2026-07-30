# AlphaLens v2 Dataset Specification

## Status and Authority

**Phase:** Phase 4 — Research Foundation  
**Artifact type:** Model-ready dataset methodology  
**Implementation status:** Not implemented  
**Dataset version:** Unresolved

This document defines how a future AlphaLens v2 research dataset must be
constructed from approved point-in-time evidence. It does not generate a
dataset, select a label policy, authorize model training, or approve an
experiment.

This specification is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PRODUCT_CONTRACT.md`;
- `ALPHALENS_V2_DECISION_CONTRACT.md`;
- `ALPHALENS_V2_CONFIDENCE_POLICY.md`;
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`;
- `ALPHALENS_V2_PHASE_3_BASELINE.md`; and
- `ALPHALENS_V2_LABELING_SPECIFICATION.md`.

## Dataset Purpose

The future dataset will provide an immutable, auditable join between:

1. one eligible BTC/USD prediction origin;
2. the complete approved Tier-A feature vector available at that origin;
3. one label generated under a separately approved label policy; and
4. the provenance required to reproduce both.

It is a research artifact, not a live prediction stream, trading record,
order record, or product decision.

## Approved Unit of Observation

The logical row identity is:

```text
(instrument, timeframe, prediction_timestamp, feature_pipeline_version,
 label_policy_version, dataset_version)
```

For the initial scope:

- `instrument = BTC/USD`;
- `timeframe` is exactly one of `5m`, `10m`, or `15m`;
- `prediction_timestamp` is the canonical candle-open timestamp `t`;
- feature evidence is available at `t + D`; and
- every row belongs to exactly one timeframe.

Timeframes are separate research populations unless a later protocol
explicitly approves pooling. Rows from different timeframes must not be
silently concatenated or treated as independent observations of the same
event.

## Logical Row Contract

Every included row must be traceable to the following logical fields:

| Field group | Required content |
| --- | --- |
| Identity | Instrument, timeframe, prediction timestamp, dataset version |
| Availability | Feature evidence cutoff, label interval, label availability |
| Features | Ordered complete vector from the approved registry |
| Label | Class and immutable label-policy reference |
| Candle provenance | Canonical candle identities and ingestion batches |
| Feature provenance | Feature run, pipeline `2.0.0`, registry hash, source-data hash, source-provenance hash, result hash |
| Label provenance | Label policy, source outcomes, configuration hash, result hash |
| Dataset provenance | Dataset ID, construction configuration, source references, code version, dataset hash |
| Partition status | Development, validation, protected test, purged, embargoed, or excluded |
| Exclusion evidence | Stable reason code and relevant timestamps when no row is included |

Feature ordering is the approved Phase 3 registry output order:

1. `candle_body_fraction`;
2. `candle_range_fraction`;
3. `upper_wick_fraction`;
4. `lower_wick_fraction`;
5. `true_range`.

Anonymous columns, reordered columns, hidden transformations, or
feature-name inference are prohibited.

## Approved Source Evidence

The feature source must be an immutable successful Phase 3 run satisfying:

- pipeline version `2.0.0`;
- registry schema version `1.0.0`;
- availability contract version `1.0.0`;
- registry hash
  `c89cdef54e4a59689259d18e0571ca5ab9dfebe713115c27dffd0818a6858aac`;
- complete source and value memberships;
- verified source, provenance, registry, and result hashes;
- point-in-time validation passed; and
- active status at dataset snapshot selection.

The dataset must capture the selected run IDs and hashes permanently.
Subsequent active-run promotion must not silently change an existing dataset.

Labels must come only from a separately approved, immutable policy satisfying
`ALPHALENS_V2_LABELING_SPECIFICATION.md`.

## Dataset Construction Methodology

Construction must follow this deterministic order.

### 1. Freeze construction configuration

Before reading outcomes, record:

- dataset specification version;
- instrument and timeframe scope;
- exact Phase 3 run identity for each timeframe;
- label-policy identity and version;
- date eligibility boundaries;
- required feature outputs and ordering;
- missing-data and exclusion rules;
- split design;
- purge and embargo policy;
- code version; and
- canonical serialization and hashing rules.

### 2. Resolve immutable source snapshots

Verify all selected candle, feature, and label evidence:

- exists;
- is immutable;
- has complete memberships;
- matches its recorded hashes;
- covers the same instrument and timeframe;
- uses canonical UTC timestamps; and
- retains point-in-time availability.

### 3. Establish eligible prediction origins

A candidate origin is eligible only when:

- the canonical candle is complete and validated;
- the complete approved feature vector exists;
- every feature has `available_at <= evidence_cutoff`;
- the feature run and registry match the frozen configuration;
- the label policy applies to the same instrument and timeframe;
- the complete future outcome required by the label exists;
- the label is available and unambiguous under the selected policy; and
- no data-quality or provenance failure applies.

### 4. Join by explicit identity

Join features and labels using instrument, timeframe, and prediction
timestamp plus their versioned provenance references. Positional joins,
nearest-time joins, forward-looking as-of joins, implicit timezone
conversion, and row-order assumptions are prohibited.

### 5. Validate complete vectors

Retain only rows containing every required feature output. Legitimate Phase 3
warm-up omission excludes the row until the complete vector exists.

No value may be:

- null;
- NaN or infinite;
- non-Decimal before an explicitly approved model-input conversion;
- duplicated;
- outside its supported timeframe; or
- available after the row's evidence cutoff.

### 6. Apply label and boundary eligibility

Exclude observations lacking a complete future outcome. Apply the selected
policy's ambiguity, overlap, and end-of-series rules. Then apply
chronological partition, purge, and embargo rules.

### 7. Canonicalize and hash

Sort deterministically by:

1. instrument;
2. timeframe;
3. prediction timestamp; and
4. approved feature order.

Produce immutable configuration, source-set, row-set, partition, and complete
dataset hashes.

### 8. Persist audit evidence

Persist the dataset artifact and exclusions without altering source candle,
feature, or label evidence. Promotion of a new dataset version supersedes but
does not delete earlier artifacts.

## Missing-Data and Exclusion Policy

The dataset is fail-closed.

### Required exclusions

A row must be excluded when:

- any required feature is absent after its warm-up boundary;
- a feature availability time exceeds the evidence cutoff;
- source chronology or continuity is invalid;
- the feature or label hash cannot be verified;
- the future label horizon is incomplete;
- the selected label policy cannot resolve an ambiguity;
- the row's label interval crosses a protected split boundary;
- the row is removed by the approved purge or embargo rule; or
- any required provenance link is missing.

Every exclusion must use a stable reason code and retain the affected
prediction timestamp and applicable evidence.

### Prohibited repairs

The construction process must not:

- interpolate features or labels;
- forward-fill or backward-fill;
- substitute zeros or sentinel values;
- shorten feature warm-up;
- shorten label horizon;
- infer an outcome from neighboring rows;
- convert a failed label evaluation into `WAIT`;
- silently discard exclusions from reporting; or
- use future observations to impute prediction-time evidence.

Any future imputation or transformation policy requires separate approval.
If approved, it must be fitted independently inside each training partition.

## Point-in-Time Guarantees

For every included row:

1. all source candles are complete;
2. every feature uses only candles at or before its prediction timestamp;
3. every feature availability time is at or before the evidence cutoff;
4. the evidence cutoff precedes the future label outcome;
5. label availability is recorded separately and is never a feature;
6. construction uses the source artifacts selected at dataset-freeze time;
7. later data revisions or active-run changes are not substituted;
8. any data-derived transformation is fitted only on the applicable training
   partition;
9. class thresholds learned from data, if later approved, are fitted only
   within training evidence; and
10. protected validation/test outcomes are unavailable to development logic.

The dataset must pass prefix-reconstruction checks: constructing an eligible
historical row from the evidence prefix available at its cutoff must reproduce
the same feature vector as the frozen full dataset.

## Leakage Prevention Rules

### Direct target leakage

The following are prohibited as inputs:

- label class;
- future return or future price used by the label;
- future high, low, close, excursion, or barrier event;
- label availability;
- time-to-label event;
- outcome-derived exclusion flags; and
- any transformation fitted using validation or protected-test outcomes.

### Temporal overlap leakage

Each label has an explicit outcome interval. For a validation or test boundary:

- a training row is purged if its label interval reaches into or beyond the
  later partition;
- rows inside the approved embargo gap are unavailable for fitting;
- the gap is derived from the selected label and preprocessing dependencies,
  not guessed after results are observed; and
- adjacent overlapping labels are not treated as independent without
  reporting their dependence.

### Feature leakage

The frozen Phase 3 pipeline prevents future-candle feature use, but dataset
construction must additionally prevent:

- recomputing features with a later pipeline or registry version;
- global normalization before splitting;
- feature selection using validation or test results;
- encoding future class frequency;
- fitting missing-value handling outside training; and
- using future-active run status as a historical input.

### Cross-timeframe leakage

No cross-timeframe join is approved. If later proposed, it must define:

- exact as-of availability;
- slower/faster candle boundary alignment;
- duplicate-event dependence;
- missing-boundary behavior; and
- a new feature and dataset version.

## Chronological Split Methodology

Random, shuffled, stratified-random, and ordinary k-fold splitting are
prohibited.

### Required partition structure

The future dataset must be divided chronologically into:

1. **Development period** — the only period available for candidate
   iteration, preprocessing design, and model development.
2. **Walk-forward validation periods** — chronological folds used to assess
   development stability. Each validation fold strictly follows its training
   window.
3. **Protected final test period** — the most recent predeclared segment,
   isolated from label-policy selection, preprocessing choices, model
   selection, and tuning.

### Walk-forward constraints

Every fold must satisfy:

- training timestamps strictly precede validation timestamps;
- training-label outcomes are fully available before the validation boundary;
- no train/validation overlap;
- explicit purge of crossing label intervals;
- explicit embargo according to the preregistered dependency policy;
- preprocessing fitted on training only;
- deterministic boundaries from immutable configuration; and
- identical folds for models compared in one study.

Expanding versus rolling training windows, minimum training observations,
validation window, step size, number of folds, purge length, embargo length,
and final-test size remain unresolved. They must be approved after the label
horizon and sample availability are known and before experiment results are
examined.

### Protected-test handling

- The protected test is sealed before development begins.
- Its labels and metrics must not be exposed during iteration.
- Candidate labeling strategies must not be selected using test outcomes.
- Only one explicitly approved final evaluation may consume it.
- Consumption must be immutable and recorded.
- A consumed test cannot become development evidence for the same research
  question.

## Dataset Validation Requirements

Before a dataset may support an experiment, verify:

- unique row identities;
- strict chronological ordering within each timeframe;
- exact temporal coverage and gaps;
- complete ordered feature vectors;
- expected Phase 3 warm-up exclusions;
- exact label-horizon exclusions;
- class counts by timeframe and chronological partition;
- exclusion counts by reason;
- feature and label availability;
- no crossing label intervals after purge;
- no protected-test leakage;
- complete source memberships;
- all configuration and result hashes;
- deterministic reconstruction; and
- byte-equivalent repeated generation from identical evidence.

Counts and distributions are descriptive audit evidence. They are not
predictive findings.

## Dataset Identity and Reproducibility

Every future dataset artifact must record:

- stable dataset ID and semantic version;
- construction timestamp;
- code commit;
- complete configuration;
- instrument and timeframe scope;
- Phase 3 run IDs and pipeline version;
- registry and Phase 3 result hashes;
- label-policy ID, version, configuration hash, and result hash;
- exact row identities;
- exact ordered feature schema;
- date range per timeframe;
- included and excluded counts;
- exclusion reasons;
- split configuration and boundaries;
- purge and embargo configuration;
- source, row-set, partition, and dataset hashes;
- software versions; and
- supersession lineage.

Identical evidence and configuration must reproduce identical semantic
content and hashes. Creation timestamps and generated identifiers must not be
included in deterministic result hashes.

## Decisions Frozen by This Specification

The following are approved:

1. One logical row represents one instrument, timeframe, and completed
   prediction origin.
2. Initial timeframes remain separate unless future pooling is approved.
3. The feature schema is the ordered complete Tier-A pipeline `2.0.0`
   output.
4. Dataset evidence is pinned to immutable feature and label artifacts.
5. Only complete feature vectors and valid labels are eligible.
6. Missing, ambiguous, invalid, warm-up, and incomplete-horizon observations
   are excluded with explicit reasons, never repaired.
7. Joins use explicit identities and versions.
8. Dataset ordering and hashes are deterministic.
9. Splits are chronological, walk-forward, purged, embargoed, and retain a
   protected final test.
10. All preprocessing is trained inside each training partition.
11. Dataset versions and historical artifacts are immutable.

## Unresolved Decisions Before Dataset Implementation

The following require explicit approval:

- selected label policy and version;
- dataset semantic version;
- exact eligible date range;
- separate versus pooled experiment design;
- expanding versus rolling walk-forward windows;
- training, validation, step, and final-test sizes;
- minimum training observations;
- purge and embargo values;
- overlapping-label dependence policy;
- any imputation or preprocessing;
- numeric conversion required by a future model library;
- class-imbalance handling;
- sample weighting;
- resampling policy;
- whether any later approved feature version joins Tier-A; and
- canonical persistence format for the dataset artifact.

Dataset construction must not begin until the label definition and all
boundary-dependent decisions are approved.
