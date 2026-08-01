# AlphaLens v2 Immutable Research Dataset Executable Specification

**Specification version:** `1.0.0`

**Artifact class:** Canonical immutable labeled-dataset contract

**Dataset construction activation:** Disabled

STATUS: REQUIRES RESEARCH

## 1. Scope and Authority

This specification defines dataset identity, schema, deterministic construction,
partitions, validation, lineage, and governance for every future AlphaLens
experiment. It requires the Ground Truth Label Policy Specification and frozen
Dataset/Validation Frameworks. It defines no label thresholds, partition sizes,
model inputs beyond approved registered features, or acceptance values.

One dataset version is a closed immutable snapshot. Every experiment MUST bind
the exact dataset identifier, version, manifest digest, partition digest, and
label-policy digest. “Latest” resolution is prohibited.

## 2. Dataset Identity and Snapshot Model

A dataset snapshot is

\[
D=(id_D,v_D,S_D,F_D,L_D,R_D,X_D,P_D,M_D,H_D),
\]

where $S_D$ is scope, $F_D$ feature schema/reference set, $L_D$ label policy,
$R_D$ ordered row set, $X_D$ exclusion set, $P_D$ partitions, $M_D$ manifest/
lineage, and $H_D$ canonical digests.

Dataset identity MUST bind:

- stable dataset identifier and semantic version;
- construction specification/version and configuration digest;
- market, venue/source, symbol, currency, and timeframe scope;
- exact UTC eligibility boundaries and expected timestamp grids;
- candle/source snapshot identities and digests;
- feature registry, definitions, pipeline runs, and snapshot digests;
- label policy/version/approval/configuration and label-run digests;
- ordered feature schema and label vocabulary;
- included/excluded row identities;
- partition, purge, embargo, preprocessing, and protected-test configuration;
- construction code/environment identity; and
- predecessor/supersession lineage.

## 3. Versioning and Hashes

Semantic versioning rules are:

- **PATCH:** documentary or metadata correction proven unable to change row,
  value, partition, lineage, or digest semantics;
- **MINOR:** backward-compatible metadata addition that changes no existing
  semantic content;
- **MAJOR:** any change capable of altering scope, source membership, feature or
  label value/version, row eligibility, ordering, exclusion, partition,
  preprocessing, precision, or hash.

Canonical hashes MUST be domain-separated and include at least configuration,
source membership, feature schema, label membership, row content, exclusions,
partitions, lineage manifest, and whole-dataset result. Runtime timestamps,
storage locations, and generated surrogate identifiers SHALL NOT enter semantic
result hashes.

## 4. Market, Symbol, and Timeframe Scope

Each dataset configuration MUST declare exact instruments, markets/exchanges,
provider sources, quote currencies, price/volume conventions, and timeframes.
Pooling is prohibited unless an approved population contract defines
comparability and dependence. Each timeframe retains its own completion,
availability, warm-up, future horizon, gaps, partitions, and audit summaries.

Corporate-action policy MUST be explicit: `NOT_APPLICABLE` is valid only for a
scope where the approved instrument contract establishes no applicable action.
Equities, derivatives, rolls, redenominations, forks, or symbol migrations
require versioned adjustment/continuity policies before inclusion.

## 5. Canonical Row Schema

Each included row MUST contain:

| Group | Required fields |
| --- | --- |
| Identity | dataset ID/version, row ID, instrument, market/source, timeframe, prediction-origin timestamp |
| Availability | candle completion, feature evidence cutoff, feature availability, label event/expiry, label availability |
| Market reference | immutable origin candle and source snapshot references |
| Features | complete ordered typed feature values; identifiers, definition versions, output names, units, feature-record/run references |
| Label | exactly one of `BUY`, `SELL`, `WAIT`; label ID, policy/version/digest, reference, event/expiry, outcome interval, label-run reference |
| Dependence | overlap interval, concurrency/uniqueness metadata defined by policy |
| Partitions | development/validation/calibration/protected/walk-forward membership plus purge/embargo status |
| Provenance | source, feature, label, construction, code/configuration identities and digests |
| Integrity | row-content digest and membership digest |

Excluded observations MUST be stored in a separate immutable exclusion schema
with candidate row identity, terminal `INVALID` or `AMBIGUOUS`, stable reason,
affected interval, available evidence, partition-boundary effect, lineage, and
exclusion digest. Exclusions are never model labels.

## 6. Observation Ordering and Uniqueness

Canonical order MUST be an approved total key beginning with market/source,
instrument, timeframe, prediction-origin timestamp, then stable row identity.
The exact registry order for scopes and features MUST be embedded in the
configuration. Locale, filesystem, database, provider response, or insertion
order is prohibited.

Exactly one included or excluded terminal record may exist per evaluation-unit
identity within one dataset version. Byte-identical duplicates MAY collapse
idempotently. Conflicting duplicates fail construction.

## 7. Deterministic Construction Pipeline

### 7.1 Freeze configuration

Approve and hash scope, UTC boundaries, source snapshots, normalization,
expected grids, feature registry/runs, label policy/run, row eligibility,
ordering, partitions, purge/embargo, preprocessing, serialization, artifact
format, and validation/acceptance rules. Construction SHALL NOT start with any
unresolved field.

### 7.2 Historical ingestion

Resolve immutable historical source snapshots by exact identity/digest. Record
provider/exchange, retrieval, source event time, availability, completion,
original values, canonical values, and source conflicts. Ingestion SHALL NOT
rewrite source evidence.

### 7.3 Normalization and cleaning

Normalize timestamps to UTC, instrument symbols through an approved mapping,
units/precision under their data contracts, and records to canonical schemas.
“Cleaning” means validation and classification, not value alteration. Invalid
or conflicted records remain auditable and are excluded unless an approved
canonical-winner artifact resolves them.

### 7.4 Gap and duplicate processing

Generate the expected timestamp grid per scope. Record every missing, duplicate,
overlap, out-of-grid, or incomplete candle. Gap reports MUST contain interval,
expected/observed counts, source scope, downstream warm-up/outcome impact, and
digest. Interpolation and nearest-time substitution are prohibited.

### 7.5 Candidate origin generation

Enumerate eligible completed origins deterministically under the label policy's
ex ante sampling rule. Apply dataset start/end, source validity, and feature
warm-up requirements without viewing label classes.

### 7.6 Feature attachment

Attach the exact complete feature snapshot whose scope and origin match the row
and whose availability does not exceed the evidence cutoff. Positional joins,
later active runs, recomputation under new versions, partial vectors, and global
preprocessing are prohibited.

### 7.7 Label attachment

Attach the exact immutable label record with matching evaluation identity,
policy/version/digest, and source scope. Include only `BUY`, `SELL`, or `WAIT`.
Route `INVALID` and `AMBIGUOUS` to exclusions. Label availability and any
outcome-derived data SHALL NOT enter features.

### 7.8 Partition assignment

Apply the already frozen chronological partition manifest, then purge and
embargo from declared label/information dependencies. Assignment SHALL NOT use
class counts, metric results, or candidate performance.

### 7.9 Validation, hashing, and artifacts

Execute Section 11 validation. Canonicalize rows/exclusions/partitions, generate
domain hashes and full manifest, persist atomically, reload, rehash, and publish
only after exact verification. Partial artifacts SHALL remain failed audit runs,
not datasets.

## 8. Point-in-Time and Future-Isolation Guarantees

For every included row:

1. origin candles are complete and immutable;
2. all features use only source evidence within the row's evidence prefix;
3. every feature is available at or before the evidence cutoff;
4. the label outcome begins only under the approved strict-future rule;
5. label/outcome fields and outcome-derived exclusions are absent from inputs;
6. transformations are either fixed a priori or fitted only within authorized
   training data;
7. later source corrections, feature runs, labels, or approvals are not
   substituted; and
8. validation/protected outcomes do not influence development membership or
   configuration.

Prefix reconstruction using only the evidence prefix MUST reproduce the exact
feature vector and row identity. Adding later history MUST NOT alter any earlier
snapshot row, label, partition, or digest; a changed source produces a successor
dataset version.

## 9. Research Data Partitions

### 9.1 Partition roles

- **Development:** authorized for hypothesis/implementation development under
  the Research Protocol.
- **Validation:** later chronological evaluation unavailable to training or
  preprocessing fit for that fold.
- **Calibration:** separate data used only for an approved calibration estimand;
  it SHALL NOT be presumed required or merged with validation.
- **Protected test:** sealed, chronologically later confirmatory evidence used
  once only after independent authorization.

### 9.2 Walk-forward and nested validation

Each fold MUST define training and strictly later validation intervals. Expanding
or rolling training, fold count, widths, step, minimum support, and optional
nested calibration/selection MUST be approved before label or metric inspection.
Inner chronological folds select candidates; outer folds estimate the frozen
selection procedure. Random/shuffled ordinary cross-validation is prohibited.

### 9.3 Purge and embargo

Purge removes training origins whose outcome/information interval intersects or
reaches a later evaluation boundary. Embargo excludes origins according to a
preregistered dependency rule after an evaluation block before they can enter
subsequent training. Durations derive from approved label, feature,
preprocessing, and dependence semantics; no value is defined here.

### 9.4 Reproducibility and sealing

Partition manifests MUST contain exact UTC boundaries, row memberships,
exclusions, purge/embargo reasons, role, predecessor, configuration, and digest.
Protected label values, class summaries, and metrics remain inaccessible before
authorization. Partition changes require a new dataset major version and a new
protected-test governance decision.

## 10. Missing Data and Failure Handling

Missing mandatory candles, features, labels, provenance, or partition metadata
exclude the row. Missing optional values require an approved experiment-specific
policy fitted only within training when data-derived. Zero/sentinel substitution,
forward/backward filling, shortened warm-up/horizon, neighbor-label inference,
and conversion of failures to `WAIT` are prohibited.

Construction failure states include unresolved policy/configuration, source
unavailability, scope mismatch, noncanonical timestamp, gap/conflict/duplicate,
feature or label mismatch, future availability, incomplete lineage, partition
crossing, hash mismatch, nondeterministic reconstruction, partial persistence,
and protected-access violation. Each failure MUST produce an immutable run record.

## 11. Dataset Validation

### 11.1 Completeness and coverage

Verify configured scopes and expected grids; observed/gap intervals; warm-up and
tail exclusions; included/excluded counts; feature-vector completeness; label
terminal-state accounting; partition membership; and source/feature/label
coverage. Adequacy thresholds require separate preregistration.

### 11.2 Chronology and leakage

Verify strict within-scope ordering, unique origins, completed candles,
availability ordering, outcome separation, no future fields in inputs,
training-only transformations, label-interval purge, embargo, cross-timeframe
availability, and sealed protected evidence. Future perturbation MUST leave
earlier input rows unchanged.

### 11.3 Integrity and consistency

Verify all domain/configuration/result digests, schema and semantic versions,
source memberships, feature registry order, label-policy consistency,
duplicate/conflict resolution, Decimal/timestamp serialization, row/exclusion
reconciliation, and partition hashes.

### 11.4 Lineage and replay

Every row MUST resolve to source candles, feature computation, label evidence,
construction run, partition manifest, code/configuration, and approvals. Two
independent constructions from identical artifacts MUST produce byte-equivalent
semantic manifests and hashes. Snapshot and prefix replay MUST reconstruct
selected fixtures and complete row sets exactly.

## 12. Validation and Acceptance Workflow

Validation stages are configuration, source, normalization, feature, label,
row, partition, lineage, deterministic replay, artifact reload, and governance.
Every mandatory stage MUST pass. Unknown or partially executed checks are not
passes.

Dataset acceptance requires:

- approved executable label policy and exact label-run artifacts;
- approved complete construction/partition configuration;
- all structural, chronology, leakage, lineage, integrity, and replay checks;
- separately preregistered coverage/sample/ambiguity adequacy checks;
- protected-test seal verification; and
- explicit dataset approval with exact manifest digest.

Acceptance authorizes research use only. It does not authorize a model,
decision, score, confidence value, publication, or production policy.

## 13. Dataset Governance

Lifecycle states are `PROPOSED`, `CONFIGURATION_APPROVED`, `BUILDING`, `FAILED`,
`VALIDATED`, `APPROVED_FOR_RESEARCH`, `SUPERSEDED`, `WITHDRAWN`, and `ARCHIVED`.
Every transition is append-only and evidence-backed.

Dataset promotion is only the transition from `VALIDATED` to
`APPROVED_FOR_RESEARCH`. It requires independent validation review, exact
manifest/signature approval, scope declaration, protected-test seal, known-risk
record, and confirmation that every acceptance gate in Section 12 passes.
Promotion authorizes only the named research uses and SHALL NOT imply production
policy promotion.

Supersession MUST name the successor and reason. Rollback means withdraw active
research approval or restore an explicitly approved predecessor; it SHALL NOT
rewrite or delete data. Archives retain resolvable sources, manifests, rows or
canonical artifacts, exclusions, partitions, reports, approvals, code/
environment references, signatures, and hashes.

Audit events MUST record actor/role, timestamp, prior/resulting state, reason,
artifact digests, validation results, protected access, and predecessor/
successor. Dataset signatures MUST bind the exact manifest digest, signer role,
approval scope, and signature time using an approved signing mechanism. No
mechanism is selected here.

Reproducibility MUST be periodically verified before reuse. Broken lineage,
digest, environment, or protected-test governance SHALL suspend the dataset.

## 14. Artifact Set

One successful dataset version MUST publish:

1. frozen construction configuration;
2. scope/source snapshot manifest;
3. feature schema and run manifest;
4. label policy and label-run manifest;
5. included-row artifact;
6. exclusion artifact;
7. gap/conflict/quality report;
8. partition and purge/embargo manifests;
9. lineage graph;
10. validation and deterministic-replay report;
11. protected-test seal record;
12. approval/signature record; and
13. complete digest manifest.

## 15. Unresolved Research and Activation Status

No approved executable ground-truth parameter artifact exists. Dataset scope,
eligible historical boundaries, label run, partition design, purge/embargo,
preprocessing, adequacy criteria, artifact format, signature mechanism, and
approvals are unresolved. Therefore no labeled dataset may be generated under
this specification yet.

STATUS: REQUIRES RESEARCH
