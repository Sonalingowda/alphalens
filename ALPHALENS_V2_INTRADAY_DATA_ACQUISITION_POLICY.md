# AlphaLens v2 Intraday Data Acquisition Policy

**Policy identifier:** `alphalens_v2_intraday_data_acquisition`

**Policy version:** `1.0.0`

**Roadmap gate:** `P1-01 — Freeze historical acquisition and correction policy`

**Scope:** BTC/USD `5m`, derived `10m`, and `15m` historical market evidence

**Implementation status:** Policy only; no implementation is authorized by
this document

**Approval status:** Approved and frozen on 2026-07-31

Future changes require an explicitly requested policy amendment with rationale,
impact assessment, migration strategy, and approval.

---

## 1. Purpose and Authority

This policy defines the historical acquisition and correction rules required
by P1-01 of `ALPHALENS_V2_IMPLEMENTATION_PLAN.md`.

It is subordinate to:

- `RESEARCH_CONSTITUTION.md`;
- `ALPHALENS_V2_PROJECT_CONSTITUTION.md`;
- `ALPHALENS_V2_INTRADAY_DATA_CONTRACT.md`;
- `ALPHALENS_V2_PHASE_3_BASELINE.md`;
- `ALPHALENS_V2_CANDIDATE_C_QUANTITATIVE_POLICY.md`;
- `ALPHALENS_V2_CORE_INTELLIGENCE_SPECIFICATION.md`; and
- explicit human approval.

This policy resolves the allowed acquisition strategy and the semantic
behavior of accumulation, retries, corrections, conflicts, retention,
canonicalization, checkpoints, provider pagination, failure, resumability,
provenance, validation, and adequacy.

It does not:

- implement acquisition;
- add a provider;
- create a migration or schema;
- define an API;
- authorize a scheduler;
- create historical coverage snapshots;
- generate features, labels, datasets, decisions, confidence, or ranks; or
- authorize P1-02 or any later task.

Where the governing repository does not supply a quantitative value, this
policy marks that value **REQUIRES EXPLICIT APPROVAL**. Such a marker is a
closed implementation gate, not permission to choose a default.

---

## 2. Policy Decisions at a Glance

| Policy area | Decision |
| --- | --- |
| Instrument | BTC/USD only |
| Native source | Kraken Spot REST public OHLC endpoint only |
| Native timeframes | `5m` and `15m` |
| Derived timeframe | `10m`, derived only from validated complete `5m` pairs |
| Historical strategy | Initial recent-window capture followed by prospective local accumulation |
| Retrospective depth | Limited to evidence actually returned by Kraken; no claim of pagination beyond the latest 720 entries |
| Additional providers | Not approved |
| Synthetic/interpolated history | Prohibited |
| Canonical writes | Insert-only |
| Existing canonical values | Never overwritten |
| Exact replay | Reuse existing canonical observation; retain attempt audit |
| Conflicting replay | Quarantine conflict evidence; leave canonical value unchanged |
| Automatic correction | Prohibited |
| Checkpoint boundary | After completed validation and transactional persistence of an acquisition unit |
| Retry behavior | Retry only approved transient classes; numeric limits/backoff require approval |
| Raw HTTP response retention | Not required by the current contract; normalized source-equivalent and audit evidence are required |
| Canonical/audit retention | No automatic deletion; evidence referenced by any artifact must remain retrievable |
| Research adequacy | Governed by the approved Candidate C requirements; acquisition alone cannot waive them |

---

## 3. Supported Provider and Source Scope

### 3.1 Approved provider

The only approved native intraday provider is:

| Field | Approved value |
| --- | --- |
| Provider | Kraken |
| Market | Kraken Spot |
| Transport | Public REST |
| Endpoint family | Public OHLC |
| Credential requirement | None for the approved endpoint |
| Instrument | BTC/USD |
| Native intervals | `5m`, `15m` |

The existing `MarketDataProvider` abstraction and
`KrakenMarketDataProvider` implementation are the required reuse boundary.

### 3.2 Derived source

The `10m` series is not a separate provider series. It is a deterministic
derivation from exactly two complete, adjacent, validated, UTC-aligned `5m`
Kraken candles.

The approved derivation remains the Phase 2 contract:

```text
open   = first 5m open
high   = max(first 5m high, second 5m high)
low    = min(first 5m low, second 5m low)
close  = second 5m close
volume = first 5m volume + second 5m volume
```

No `10m` candle exists when either source member is missing, incomplete,
invalid, duplicated, misaligned, or unverifiable.

### 3.3 Additional providers

No secondary historical provider, exchange, aggregator, paid data service,
file import, or manually supplied dataset is approved by this policy.

Adding one requires:

1. a separate provider and data-quality review;
2. an approved source contract;
3. exact venue/instrument normalization;
4. overlap and conflict research;
5. source-priority and canonical-series rules;
6. provenance and availability rules;
7. a migration and rollback strategy; and
8. explicit human approval.

Data from another provider must not be merged into the current Kraken
canonical series merely because its timestamps and symbol appear compatible.

---

## 4. Approved Historical Acquisition Strategy

### 4.1 Strategy

The approved strategy for the current source is:

1. capture the latest provider-available completed `5m` and `15m` Kraken
   windows;
2. exclude every incomplete candle;
3. validate and persist valid native observations insert-only;
4. derive valid `10m` observations from persisted/verified `5m` source
   evidence;
5. repeat acquisition prospectively;
6. insert only genuinely new completed timestamps;
7. retain overlaps as acquisition audit evidence without duplicating
   canonical candles; and
8. allow the local canonical history to grow over elapsed calendar time.

This is **prospective accumulation**, not retrospective pagination.

### 4.2 Provider history limit

The Kraken OHLC endpoint exposes at most the latest 720 entries for the
requested interval regardless of an older `since` value. Repeated calls cannot
retrieve older history that has already fallen outside that window.

The theoretical native window spans implied by the approved limit are:

- `5m`: `720 × 5 minutes = 3,600 minutes = 60 hours`;
- `15m`: `720 × 15 minutes = 10,800 minutes = 180 hours`.

These values are arithmetic consequences of the approved provider limit, not
service-level commitments. The response can also include an open candle, and
actual completed coverage can be smaller because of provider behavior,
retrieval timing, gaps, exclusions, or validation failure.

### 4.3 Accumulation cadence

To prevent an unrecoverable gap under the current provider, the elapsed time
between successful `5m` acquisitions must remain strictly shorter than the
actual provider-available `5m` window.

The following remain **REQUIRES EXPLICIT APPROVAL**:

- nominal acquisition interval;
- maximum permitted interval between attempts;
- operational safety margin below 60 hours;
- missed-run alert boundary;
- clock-drift tolerance;
- scheduler start/stop behavior; and
- recovery cadence after an outage.

No implementation may choose conventional values or copy cadence from the
legacy paper-trading scheduler. P1-01 does not authorize scheduling.

### 4.4 Attainable coverage

Under a Kraken-only prospective strategy:

- existing provider-returned history is the starting point;
- earlier unavailable history cannot be recovered from Kraken OHLC;
- the local archive grows only as new completed observations occur; and
- the 365-consecutive-day Candidate C requirement can be met only after the
  local archive actually contains and validates that elapsed coverage.

The system must report inadequate coverage until the approved adequacy rules
are satisfied. Time pressure does not authorize an alternative provider,
fabrication, interpolation, or weakening of adequacy.

### 4.5 Prohibited acquisition behavior

The acquisition process must never:

- describe overlapping Kraken calls as pages of older history;
- fabricate candles before the provider-available start;
- interpolate missing intervals;
- forward-fill OHLCV;
- construct synthetic volume;
- accept an incomplete candle;
- silently replace an existing canonical candle;
- mix venues/providers in one canonical series;
- treat a retry as independent evidence;
- present a scheduled attempt as a successful acquisition; or
- represent accumulated history as research-adequate before the approved gate
  passes.

---

## 4A. Initial Historical Bootstrap Policy

### 4A.1 Separation of acquisition modes

This policy distinguishes two acquisition modes with separate identities,
provenance, approval, and lifecycle:

- **Initial historical bootstrap:** an optional, one-time import of historical
  evidence intended to establish coverage that predates AlphaLens' prospective
  Kraken accumulation.
- **Ongoing production acquisition:** the existing Kraken-only process that
  retrieves new completed native `5m` and `15m` candles, derives `10m`
  evidence, and grows the canonical live history prospectively.

The initial bootstrap is not live production acquisition. It must not change
the approved status of Kraken Spot REST as the live production source.

### 4A.2 Approval boundary

A one-time historical bootstrap may be performed only after a separate,
explicit human approval covering the exact bootstrap source, scope, evidence,
import contract, validation, conflict treatment, and rollback plan.

Bootstrap provider selection is:

**REQUIRES EXPLICIT HUMAN APPROVAL.**

This section does not approve a bootstrap source, provider, dataset, import,
credential, paid service, implementation, migration, API, or execution.

### 4A.3 Bootstrap source requirements

Any future bootstrap source must satisfy all requirements below before it may
be approved:

1. **Identical instrument definition.** The source must unambiguously
   represent the same BTC/USD spot-market concept required by the approved
   research scope. Venue, base asset, quote asset, market type, price basis,
   volume denomination, and symbol normalization must be documented.
2. **UTC timestamps.** Every observation must use timezone-aware UTC
   timestamps with documented interval-open semantics and exact `5m` or `15m`
   alignment. Any source-time conversion must be deterministic and auditable.
3. **Documented provenance.** The source identity, dataset identity/version,
   retrieval or delivery method, acquisition time, requested scope, available
   range, provider metadata, and applicable source terms must be recorded.
4. **Deterministic import.** Identical approved source evidence,
   configuration, code, and versions must produce identical normalized
   observations, exclusions, memberships, ordering, and hashes.
5. **Immutable evidence.** Original bootstrap evidence or an approved
   source-equivalent representation must remain immutable and retrievable.
   Corrections must create new evidence rather than rewrite prior imports.
6. **Validation.** Bootstrap observations must pass the same applicable
   completeness, chronology, uniqueness, UTC alignment, missing-field, OHLC,
   volume, Decimal, and incomplete-candle rules as Kraken evidence. Validation
   may not interpolate, fabricate, forward-fill, or silently repair values.
7. **Conflict policy.** Overlap with Kraken or another bootstrap observation
   must be compared exactly. Identical overlap may be recorded as agreement;
   differing values must be quarantined and resolved under an explicitly
   approved source-priority/correction policy. No value may be silently
   selected.
8. **Candidate C compatibility.** Coverage, continuity, observation
   availability, Decimal precision, timeframe derivation, label horizon,
   purge/embargo, protected-test, and provenance evidence must support the
   approved Candidate C quantitative policy without weakening it.
9. **Complete audit trail.** Every import attempt must retain source
   memberships, normalized values, exclusions, validation issues, conflicts,
   configuration, code/software identity, timestamps, approval reference, and
   deterministic configuration, provenance, and result hashes.

Meeting these requirements makes a source eligible for human review. It does
not automatically approve the source or establish research adequacy.

### 4A.4 Evidence isolation and canonicalization

Bootstrap evidence must never silently merge into Kraken evidence.

The bootstrap and Kraken live accumulation must permanently retain distinct:

- source and provider identities;
- acquisition-mode identifiers;
- source batches and memberships;
- retrieval/import and availability timestamps;
- validation reports;
- configuration and provenance hashes;
- correction and conflict histories; and
- limitations.

A future approved canonical historical snapshot may reference both evidence
families only under an explicitly approved compatibility and source-priority
policy. That snapshot must preserve source membership for every observation
and must expose all overlaps, exclusions, and resolved or unresolved
conflicts. Shared timestamps do not establish source equivalence.

Derived `10m` evidence must retain the source family and exact two-candle
membership of its underlying `5m` evidence. A derived candle must not combine
one bootstrap `5m` member with one Kraken live `5m` member unless a separate
boundary-compatibility rule is explicitly approved.

### 4A.5 Bootstrap completion and production handoff

Bootstrap completion must be recorded as a finite, immutable import event with
an approved terminal range, validation result, adequacy report, provenance
hash, result hash, and human approval reference.

After the approved bootstrap completes:

- all future live acquisition continues under the existing Kraken-only
  production policy;
- the bootstrap source is not used as an ongoing live source;
- Kraken observations continue to accumulate prospectively and insert-only;
- overlapping Kraken evidence is evaluated under the approved conflict policy;
  and
- bootstrap evidence remains distinguishable and auditable for the lifetime
  of every dependent artifact.

Any proposal to reuse a bootstrap source after the one-time import is a new
provider-scope decision and requires separate explicit human approval.

### 4A.6 Implementation boundary

This bootstrap policy defines only an approval path. It does not authorize:

- selecting or contacting a bootstrap provider;
- acquiring, downloading, or importing data;
- introducing credentials or paid services;
- changing canonical persistence;
- adding schemas or migrations;
- implementing conflict resolution;
- generating historical snapshots;
- creating labels, datasets, features, or experiments; or
- beginning any implementation task.

Implementation may begin only after the bootstrap source and its complete
source-specific contract receive explicit human approval.

---

## 5. Accumulation Policy

### 5.1 Unit of accumulation

Each acquisition attempt is an immutable audit event. For each native
timeframe it must distinguish:

- requested range;
- provider-returned range;
- completed accepted observations;
- incomplete exclusions;
- malformed or invalid exclusions;
- overlap with existing canonical data;
- identical reuse;
- conflicting reuse;
- genuinely new observations;
- validation result;
- persistence result; and
- terminal attempt status.

The native `5m` and `15m` attempts remain independently auditable. The
derived `10m` attempt must reference the exact successful `5m` source attempt
and source candle memberships.

### 5.2 Insert-only accumulation

Canonical accumulation is insert-only under the uniqueness identity:

```text
instrument + quote currency + timeframe + candle timestamp
```

For a valid incoming observation:

- a new timestamp is eligible for canonical insertion;
- an exact replay is reuse, not insertion;
- a conflicting replay is not an update; it enters conflict handling; and
- a failed batch contributes no new canonical candles.

### 5.3 Ordering

Observations are evaluated and persisted in strict ascending canonical
timestamp order. Provider response order is not trusted without validation.

Canonical ordering must be deterministic for:

- validation;
- persistence input;
- memberships;
- hashes;
- coverage computation; and
- replay comparison.

### 5.4 Accumulation across timeframes

The approved order of dependency is:

```text
native 5m acquisition and persistence
  -> derived 10m generation and persistence

native 15m acquisition and persistence
  -> independent 15m canonical history
```

A valid `15m` result does not repair a failed `5m` or `10m` result. A valid
`5m` result does not imply the independent native `15m` source is valid.

---

## 6. Retry Policy

### 6.1 Retryable classes

An acquisition attempt may be retried only for a failure that is plausibly
transient and does not indicate invalid semantic content:

- network connection failure;
- connection reset;
- request timeout;
- provider rate limiting;
- provider service unavailability;
- provider gateway failure; or
- another explicitly classified transient server response.

Every retry must retain:

- the originating acquisition identity;
- attempt ordinal;
- failure class;
- status code when available;
- safe error summary;
- attempt start/end;
- requested scope;
- provider identity;
- retry decision; and
- next eligible attempt time when one exists.

### 6.2 Non-retryable within the same attempt sequence

The same provider response must not be retried as though transport caused:

- malformed JSON;
- malformed provider schema;
- invalid provider error structure;
- invalid timestamp or Decimal content;
- chronology failure;
- duplicate source timestamp;
- impossible OHLC;
- negative volume;
- source hash mismatch;
- canonical conflict; or
- unsupported instrument/timeframe.

A later scheduled acquisition may obtain new provider evidence, but it is a
new acquisition event. It must not erase the failed event.

### 6.3 Retry limits and timing

The following values remain **REQUIRES EXPLICIT APPROVAL**:

- maximum attempts per acquisition;
- initial delay;
- backoff function;
- maximum delay;
- use and definition of jitter;
- provider rate-limit cooldown;
- total retry time budget; and
- circuit-breaker activation and recovery boundaries.

Until those values are approved:

- retry orchestration must not be implemented;
- a failed provider request terminates the current attempt;
- the previous canonical state remains unchanged; and
- a later manually or separately approved acquisition may try again.

Random retry jitter must not be introduced without an approved source of
randomness and recorded configuration. Operational retry timing must never
change canonical market semantics or result hashes.

### 6.4 Retry success

A later successful response proceeds through complete normalization,
validation, conflict detection, and persistence. Success of a retry does not
delete or convert earlier failed attempt evidence.

---

## 7. Correction Policy

### 7.1 Default correction rule

Automatic correction of an existing canonical candle is prohibited.

Once a validated canonical observation is stored, a later provider response
must not update its:

- timestamp;
- open;
- high;
- low;
- close;
- volume;
- timeframe;
- instrument;
- quote currency;
- provider provenance; or
- source batch identity.

### 7.2 Exact replay

An incoming observation is an exact replay only when every canonical identity
and value matches exactly after the approved source normalization:

- instrument;
- quote currency;
- timeframe;
- UTC timestamp;
- open;
- high;
- low;
- close; and
- volume.

Exact Decimal equality is required. Approximate floating-point tolerance is
prohibited.

An exact replay:

- creates no new canonical candle;
- does not alter the existing candle;
- is counted as reused overlap;
- remains represented in the new attempt's audit evidence; and
- may contribute evidence that acquisition continuity was checked.

### 7.3 Provider revision

When the same canonical identity arrives with any different OHLCV value, it
is a provider revision conflict.

The current approved disposition is:

1. preserve the original canonical candle unchanged;
2. do not promote the incoming value;
3. retain the complete incoming normalized value as conflict evidence;
4. record the existing and incoming source identities and exact values;
5. record retrieval/availability times;
6. record a deterministic conflict hash;
7. mark the affected attempt and coverage range as conflicted;
8. block the conflicted observation from new downstream snapshots; and
9. require explicit human resolution before the range can be represented as
   conflict-free.

### 7.4 Human correction boundary

No correction-selection rule is approved. Human review may not directly edit
the canonical row.

Resolving a provider revision requires a separate approved correction
decision that defines:

- which evidence is authoritative;
- why it is authoritative;
- the affected scope;
- treatment of dependent derived candles, features, labels, datasets, and
  research artifacts;
- whether a new canonical version or snapshot is created;
- migration and rollback;
- audit retention; and
- explicit approval identity.

Until such a decision exists, the original canonical observation remains
stored, the conflict remains visible, and affected new research eligibility
fails closed.

### 7.5 No retroactive rewriting

Even after a future correction decision:

- original source evidence must remain retrievable;
- historical artifacts retain the point-in-time evidence they actually used;
- old hashes are not recomputed to conceal the correction;
- the correction receives a new identity and availability time; and
- later snapshots may supersede but never rewrite older snapshots.

---

## 8. Conflict Handling

### 8.1 Conflict categories

| Category | Meaning | Disposition |
| --- | --- | --- |
| Exact replay | Same identity and exact OHLCV | Reuse; no insert |
| Intra-response duplicate, same value | Provider returned duplicate rows | Validation issue; deduplication is not silently assumed |
| Intra-response duplicate, different value | Ambiguous provider response | Fail the affected native batch |
| Existing-canonical value conflict | Later response differs | Quarantine; preserve canonical |
| Provider identity conflict | Same apparent market/time but different source | Reject from current canonical series |
| Derivation membership conflict | A 10m candle's 5m members differ or are unverifiable | Do not create/promote the 10m candle |
| Hash/membership conflict | Stored evidence does not verify | Suspend affected use; do not recalculate silently |

### 8.2 Batch scope

A source conflict must not be reduced to a database `DO NOTHING` result
without classification.

Whether one conflicted observation invalidates the entire acquisition batch
or only the conflicted observation remains **REQUIRES EXPLICIT APPROVAL**.
Until approved, the fail-closed policy is:

- no new canonical observations from the affected native batch are promoted;
- the batch and conflict evidence remain auditable; and
- independent timeframes may proceed only in independent transactions whose
  own evidence passes.

### 8.3 Conflict resolution service level

No time-to-resolution target is approved. The conflict remains unresolved and
the affected range remains ineligible for a conflict-free snapshot until an
approved decision is recorded.

---

## 9. Retention Policy

### 9.1 Evidence that must be retained

The following evidence must have no automatic deletion:

- canonical candles;
- ingestion batches, including failed batches;
- normalized source-equivalent observations used for canonical insertion;
- incomplete/malformed/invalid exclusion summaries required for audit;
- progress and provider-limit evidence;
- exact replay/reuse counts;
- conflict evidence;
- derivation policies and source memberships;
- validation reports and issue records;
- checkpoint records;
- configuration, code, software, and policy identities;
- provenance and result hashes; and
- every source object referenced by a feature, label, dataset, experiment,
  context, decision, ranking, explanation, or other immutable artifact.

Evidence referenced by an immutable artifact must remain retrievable for at
least as long as that artifact or any claim based on it is retained.

### 9.2 Raw provider payloads

The current approved provider contract does not require retention of complete
raw HTTP bodies.

The required source-equivalent evidence is:

- exact normalized candle values;
- provider and endpoint identity;
- requested parameters and range;
- provider cursor/limit metadata;
- retrieval time;
- validation/exclusion evidence; and
- integrity hashes sufficient to reproduce the canonicalization decision.

If later research, regulation, provider terms, or correction analysis requires
raw response retention, its storage format, sensitive-data review, compression,
duration, and integrity policy require explicit approval.

### 9.3 Retention duration

No fixed number of days or years is approved.

The following remain **REQUIRES EXPLICIT APPROVAL**:

- minimum retention for unreferenced failed attempts;
- minimum retention for raw responses if later enabled;
- archival tier timing;
- deletion eligibility;
- legal/regulatory holds;
- storage capacity thresholds; and
- secure destruction procedure.

Until approved, no automatic purge, compaction that loses evidence, or
destructive archival is permitted.

---

## 10. Canonical Source Rules

### 10.1 Canonical observation eligibility

A native candle is eligible only when:

- provider is the approved Kraken Spot REST source;
- instrument is BTC/USD;
- timeframe is native `5m` or `15m`;
- timestamp is timezone-aware UTC and exactly interval-aligned;
- the full interval ended at or before the retrieval cutoff;
- all required fields exist;
- OHLC and volume use exact Decimal values;
- prices are finite and strictly positive;
- volume is finite and nonnegative;
- OHLC relationships are valid;
- chronology is strict;
- timestamp is unique in the provider response;
- validation passes; and
- no unresolved canonical conflict applies.

### 10.2 Canonical 10m eligibility

A derived `10m` candle is eligible only when:

- both exact source `5m` members are canonical and verified;
- timestamps are `t` and `t + 5m`;
- both are complete and valid;
- the 10m bucket is UTC-aligned;
- the approved derivation version is recorded;
- source batch and candle memberships are complete; and
- the derived series passes the same applicable validation rules.

### 10.3 Canonical precision

Market values preserve the repository's exact Decimal representation.

No acquisition policy may:

- convert source values through binary floating point;
- round an incoming value to force equality with an existing value;
- apply an approximate conflict tolerance; or
- change the Phase 3 feature Decimal rules.

### 10.4 Source priority

Kraken is the only source, so no cross-provider priority rule exists. If a
future provider is approved, source priority and series identity must be
defined before any mixed-source ingestion.

---

## 11. Checkpoint Strategy

### 11.1 Purpose

A checkpoint records verified acquisition progress so an interrupted
operation can resume without treating unverified work as complete.

### 11.2 Checkpoint boundary

A checkpoint may advance only after:

1. the provider response for the acquisition unit is received;
2. source normalization completes;
3. incomplete observations are excluded and counted;
4. validation completes;
5. conflicts are classified;
6. the database transaction commits;
7. persisted memberships/counts verify; and
8. checkpoint content and hashes are durably recorded.

A provider cursor alone is not a committed checkpoint.

### 11.3 Checkpoint content

Each checkpoint must identify:

- checkpoint and acquisition identities;
- policy version and hash;
- provider and endpoint identity;
- instrument/timeframe;
- requested range and provider-returned range;
- provider cursor/limit evidence;
- latest successfully committed canonical interval;
- ingestion batch identity;
- accepted/excluded/reused/inserted/conflicted counts;
- validation status;
- derivation source identity where applicable;
- configuration/code/software identity;
- predecessor checkpoint;
- created/available times; and
- canonical checkpoint hash.

### 11.4 Checkpoint frequency

For current Kraken intraday acquisition, one provider response per native
timeframe is the natural acquisition unit because the endpoint does not expose
older pages beyond its latest-720 limit.

If a future approved provider exposes genuine pagination, the checkpoint unit
must be one completely validated and transactionally persisted page or
approved bounded chunk.

Any smaller/larger chunk size, batch-size limit, or time-based checkpoint
frequency **REQUIRES EXPLICIT APPROVAL**.

### 11.5 Checkpoint failure

If checkpoint persistence fails after candle persistence, the acquisition must
not be represented as checkpoint-complete. Recovery must reconcile immutable
database evidence before attempting another provider request.

The exact reconciliation implementation belongs to later tasks.

---

## 12. Pagination Policy

### 12.1 Kraken intraday behavior

Kraken intraday acquisition is single-window retrieval, not historical
pagination.

The provider `last` cursor is retained as source metadata, but repeatedly
advancing or changing `since` must not be represented as access to candles
older than the endpoint's latest 720 entries.

### 12.2 Termination

A Kraken native intraday acquisition terminates after:

- one successful provider response for the requested native timeframe; or
- a terminal provider/retry failure.

The response is then normalized, validated, and persisted or failed.

### 12.3 Provider limit reporting

Every attempt must report:

- provider row count;
- completed accepted count;
- incomplete excluded count;
- overlap/reuse count;
- conflict count;
- provider page limit;
- whether the limit was reached;
- provider-available start/end; and
- terminal reason.

### 12.4 Pagination exhaustion

When the oldest requested time precedes the oldest provider-returned entry,
the result is:

```text
PROVIDER_HISTORY_EXHAUSTED
```

This is a truthful coverage limitation, not a retriable pagination failure.
The acquisition may still persist valid returned candles, but adequacy remains
failed for the missing earlier range.

### 12.5 Future provider pagination

No generic multi-provider pagination is approved. A future provider must
define cursor semantics, stable ordering, overlap behavior, rate limits,
termination, checkpointing, and source revisions in its approved contract.

---

## 13. Failure Handling

### 13.1 Failure taxonomy

| Failure | Required outcome |
| --- | --- |
| Provider unreachable/timeout | Record failed attempt; no canonical change |
| Approved transient HTTP failure | Apply approved retries; without numeric approval, terminate |
| Provider history exhausted | Persist honest returned coverage; mark inadequacy |
| Malformed response/schema | Fail batch; preserve diagnostics |
| Incomplete candle | Exclude/count; do not persist as complete |
| Validation failure | Persist failed batch audit; no canonical inserts |
| Source gap | Report exact interval; no interpolation |
| Exact replay | Reuse; no duplicate |
| Value conflict | Quarantine; no canonical update |
| Derived member missing | Omit derived candle; report gap/failure |
| Database transaction failure | Roll back; do not advance checkpoint |
| Checkpoint failure | Do not report completion; reconcile before resume |
| Hash/membership mismatch | Suspend affected evidence; fail closed |
| Inadequate coverage | Block research-adequate status |
| Unsupported scope | Reject before provider request |

### 13.2 Failure isolation

- A failed `5m` batch prevents dependent `10m` generation.
- A failed `15m` batch does not rewrite or invalidate an independently valid
  previous `5m`/`10m` canonical state.
- No new active coverage state may be promoted from a partially failed
  transaction.
- Previous verified canonical evidence may remain available only for its
  actual range and freshness; it must not be described as current if stale.

### 13.3 Failure visibility

Every terminal result must distinguish:

- successful with new inserts;
- successful with reuse only;
- successful but provider-limited/inadequate;
- successful with incomplete exclusions;
- validation failed;
- conflict failed;
- provider failed;
- persistence failed;
- checkpoint/reconciliation required; and
- unsupported request.

An empty insert count is not, by itself, failure: an exact overlapping replay
can validly insert zero rows.

---

## 14. Resumability

### 14.1 Resume source of truth

Resume decisions are based on verified persisted checkpoints and canonical
memberships, not in-memory progress, logs, wall-clock assumptions, or the last
provider cursor alone.

### 14.2 Resume procedure

Before resuming:

1. load the latest compatible checkpoint;
2. verify its policy/configuration/code identities;
3. verify ingestion batch and canonical memberships;
4. verify hashes;
5. compare checkpoint range with canonical coverage;
6. identify an incomplete or conflicted acquisition;
7. reconcile persisted evidence without modifying history; and
8. begin a new acquisition event for any provider request.

### 14.3 Resume incompatibility

Resume must fail closed when:

- policy version changed incompatibly;
- provider/source scope differs;
- checkpoint hash fails;
- referenced batch or candles are missing;
- stored counts/memberships differ;
- canonical conflicts remain unresolved; or
- requested timeframe is unsupported.

No automatic checkpoint repair is approved.

### 14.4 Idempotency

Resuming or rerunning the same source window must:

- insert no duplicate canonical candle;
- classify identical overlap as reuse;
- reproduce validation semantics;
- retain the new attempt audit;
- preserve previous checkpoint evidence; and
- produce deterministic semantic hashes for identical content/configuration.

Runtime-generated attempt IDs and timestamps remain audit metadata and must
not change content hashes unless the governing hash contract explicitly
includes them.

---

## 15. Provenance Requirements

### 15.1 Native acquisition provenance

Every native attempt must record:

- provider and market identity;
- endpoint contract/version;
- instrument and timeframe;
- requested `since`/range parameters;
- provider cursor and row limit;
- retrieval start/end and cutoff;
- available range;
- exact normalized observations or their immutable memberships;
- completed/incomplete status;
- validation policy/report;
- overlap/reuse/conflict evidence;
- retry attempt evidence;
- checkpoint identity;
- configuration/code/software identity;
- policy identity/version;
- ingestion batch identity;
- canonical insert memberships;
- failure/terminal state; and
- configuration, source/provenance, and result hashes.

### 15.2 Derived 10m provenance

Every `10m` observation must additionally retain:

- derivation policy identity/version;
- source timeframe;
- exact two source candle identities;
- exact source ingestion batch identities;
- source data/provenance hashes;
- derivation availability time; and
- derived result hash.

### 15.3 Hash requirements

Hashes must use:

- SHA-256;
- canonical serialization;
- deterministic field ordering;
- UTC timestamp encoding;
- exact fixed-point Decimal encoding;
- stable ordered memberships; and
- a versioned hash schema.

The exact hash payload/schema for the future coverage snapshot belongs to
P1-02 and is not defined or implemented here.

### 15.4 Audit traversal

It must be possible to traverse:

```text
canonical candle
  -> ingestion batch
  -> provider request/response-equivalent evidence
  -> validation and exclusions
  -> retry/checkpoint evidence
  -> policy/configuration/code identity
```

For derived 10m evidence, traversal must continue to both source 5m candles.

---

## 16. Validation Requirements

### 16.1 Native candles

Before canonical insertion, validate:

- supported provider, instrument, and timeframe;
- timezone-aware timestamps;
- exact UTC timeframe alignment;
- strict chronological ordering;
- unique timestamps;
- expected continuity within provider-returned/requested coverage;
- complete required fields;
- exact finite Decimal values;
- strictly positive OHLC;
- nonnegative volume;
- valid OHLC relationships;
- completed interval at retrieval cutoff;
- provider-available bounds;
- canonical overlap and conflict status; and
- provenance completeness.

### 16.2 Derived 10m candles

Additionally validate:

- both consecutive 5m members exist;
- source memberships and hashes verify;
- bucket timestamp is 10m aligned;
- derivation formula is exact;
- no incomplete source member is used;
- derived chronology/uniqueness/continuity;
- derived OHLC/volume invariants; and
- availability is no earlier than both source members and successful
  derivation.

### 16.3 Batch validation

A validation report applies only to its exact:

- provider response;
- timeframe;
- requested/available range;
- policy and validator versions;
- source memberships; and
- retrieval cutoff.

A prior passing batch does not make a later batch valid.

### 16.4 No repair

Validation reports issues. It must never:

- interpolate;
- forward-fill;
- reorder without recording provider-order failure;
- round values to pass;
- drop a conflict silently;
- substitute another timeframe/provider;
- mark a partial candle complete; or
- waive adequacy.

---

## 17. Adequacy Requirements

### 17.1 Acquisition-level adequacy

For each timeframe, acquisition must report:

- first and last completed canonical timestamps;
- elapsed calendar coverage;
- expected candle count;
- valid canonical count;
- exact missing intervals;
- coverage percentage;
- unresolved conflicts;
- provider-limited start;
- latest completed interval and retrieval lag;
- validation/hash/provenance status; and
- whether data-level adequacy conditions pass.

### 17.2 Candidate C minimum adequacy

The approved Candidate C policy requires each timeframe to satisfy all of the
following before initial model research:

1. at least 365 consecutive calendar days;
2. source candle coverage of at least 99.5%;
3. a protected test spanning at least eight complete weeks;
4. valid labels for at least 80% of otherwise eligible origins;
5. at least 25,000 valid labels before the protected test;
6. at least 1,000 valid development labels in each class;
7. five validation folds, each with at least 100 examples of each class;
8. at least 2,000 non-overlapping 60-minute development outcome blocks; and
9. no unresolved hash, chronology, or provenance failure.

The acquisition layer can directly establish source coverage, continuity,
conflicts, and source integrity. Label, class, fold, outcome-block, and
protected-test conditions are evaluated only in their authorized later phases.

### 17.3 Adequacy outcome

The only acquisition adequacy outcomes are:

- `ADEQUATE_FOR_DOWNSTREAM_ADEQUACY_EVALUATION`;
- `INADEQUATE_COVERAGE`;
- `INADEQUATE_CONTINUITY`;
- `UNRESOLVED_CONFLICT`;
- `INTEGRITY_FAILURE`; or
- `SOURCE_UNAVAILABLE`.

The first outcome does not declare the model dataset adequate. It means only
that acquisition-level evidence is eligible for later label/dataset
evaluation.

### 17.4 No adequacy override

No administrative flag, retry, schedule, provider-limit exception, or product
need may override the Candidate C adequacy policy. A change requires a new
approved quantitative policy version.

---

## 18. Testable Policy Scenarios

P1-01 requires policy examples even though it requires no implementation
tests.

### Scenario A — Exact overlapping replay

**Given:** a canonical 5m candle and a later Kraken response containing the
same timestamp and exact OHLCV.

**Then:**

- no new canonical row is inserted;
- no existing value changes;
- reuse is counted;
- the attempt is retained; and
- no conflict is created.

### Scenario B — Provider revision

**Given:** a canonical 15m candle and a later response with the same identity
but a different close.

**Then:**

- the original remains canonical;
- the incoming value is retained as conflict evidence;
- the batch fails closed under the current batch-scope default;
- affected new snapshots are blocked; and
- explicit correction approval is required.

### Scenario C — Gap inside provider window

**Given:** two completed returned 5m candles separated by ten minutes.

**Then:**

- the missing timestamp is reported;
- no candle is interpolated;
- an affected 10m pair is not derived;
- the validation outcome follows the existing gap rules; and
- later retrieval may supply real evidence only while provider-available.

### Scenario D — Pagination exhaustion

**Given:** a request begins before the oldest candle in Kraken's latest-720
window.

**Then:**

- one provider window is processed;
- no loop claims to retrieve older history;
- provider history exhaustion is recorded;
- returned valid candles may be accumulated; and
- requested earlier coverage remains inadequate.

### Scenario E — Unavailable coverage

**Given:** the local archive contains less than 365 consecutive days.

**Then:**

- the observed range and coverage are reported;
- research adequacy is false;
- no labels/dataset/model work is authorized on the claim of adequate data;
- no synthetic source is used; and
- prospective accumulation continues only under approved operations.

### Scenario F — Transient provider timeout

**Given:** Kraken times out.

**Then, before numeric retry approval:**

- the current attempt terminates as provider failed;
- no checkpoint advances;
- no canonical state changes; and
- a later acquisition is a new audit event.

### Scenario G — Incomplete provider candle

**Given:** the response contains a candle whose interval has not ended at the
retrieval cutoff.

**Then:**

- it is excluded and counted;
- it is not validated as completed;
- it is not persisted canonically;
- it is not used for 10m derivation; and
- a later completed observation may be acquired normally.

### Scenario H — Persistence succeeds but checkpoint fails

**Given:** canonical insertion commits but checkpoint recording does not.

**Then:**

- the acquisition is not reported checkpoint-complete;
- the next run reconciles persisted evidence before requesting new data;
- replay remains idempotent; and
- no checkpoint is reconstructed from assumptions.

---

## 19. Assumptions

Verified assumptions inherited from approved documents:

1. Kraken Spot REST remains available as a keyless public source for the
   approved endpoint.
2. Kraken provides native `5m` and `15m` intervals.
3. Kraken does not provide native `10m` OHLC in the approved contract.
4. The endpoint's practical history is capped at its latest 720 entries.
5. BTC/USD trades continuously, so coverage uses elapsed UTC time rather than
   exchange sessions.
6. Canonical candle timestamps are inclusive interval-open times.
7. Existing persistence is insert-only and exact Decimal.
8. Existing validation and Phase 3 provenance remain reusable.

Operational assumptions that must be verified by implementation:

- provider behavior continues to match the approved contract;
- the deployment can run often enough to avoid falling outside the 5m window;
- persistent storage remains available and durable;
- UTC system time is sufficiently reliable for retrieval cutoff calculation;
- provider terms permit the approved acquisition and retention behavior; and
- accumulated storage capacity is sufficient.

No operational assumption may be treated as a guarantee.

---

## 20. Limitations

1. Kraken-only prospective accumulation cannot recover intraday history that
   left the latest-720 window before AlphaLens stored it.
2. Satisfying the 365-day requirement therefore takes actual elapsed
   accumulation time unless a new provider/source is separately approved.
3. Exact scheduler cadence, retry limits/backoff, freshness tolerance, and
   service-level objectives remain unapproved.
4. Raw HTTP payload retention is not required; normalized source-equivalent
   evidence limits future forensic review to the retained normalized/audit
   fields.
5. No automatic provider-revision correction is allowed.
6. No policy yet selects between conflicting source values.
7. Exact fixed retention periods and archive tiers remain unapproved.
8. This policy does not implement the immutable historical coverage snapshot;
   that is P1-02.
9. This policy does not prove the data are adequate, predictive, or suitable
   for a model.
10. This policy does not authorize additional instruments, timeframes,
    providers, trade data, quote data, or order-book data.

---

## 21. Quantitative and Operational Values Requiring Explicit Approval

Implementation must stop rather than infer any item below:

| Unresolved value | Why approval is required |
| --- | --- |
| Nominal acquisition cadence | Not defined by an approved document |
| Maximum time between attempts | Requires operational risk decision |
| Safety margin below provider window | Requires reliability decision |
| Missed-run/freshness alert threshold | No approved freshness tolerance exists |
| Maximum retry attempts | Not approved |
| Retry backoff function and delays | Not approved |
| Jitter policy | Not approved and may affect reproducibility evidence |
| Rate-limit cooldown | Not approved |
| Retry/circuit-breaker time budget | Not approved |
| Batch conflict scope narrower than fail-closed whole batch | Requires correction-risk decision |
| Conflict resolution service level | Not approved |
| Fixed retention durations | Not approved |
| Archive tier/compaction thresholds | Not approved |
| Raw response retention duration if later enabled | Not approved |
| Checkpoint chunk size for any future paginated source | Source-specific approval required |
| Operational performance targets | Core specification requires later measurement/approval |

These unresolved values do not authorize placeholder defaults.

---

## 22. Change Control

Any future policy change must include:

- exact section changed;
- rationale;
- evidence;
- impact on acquisition and downstream artifacts;
- compatibility analysis;
- migration strategy;
- rollback strategy;
- treatment of historical evidence;
- new policy version when semantics can change; and
- explicit human approval.

Changes that can alter source eligibility, canonical values, conflict
disposition, retry semantics, retention, availability, adequacy, or hashes are
semantic changes. They must not be applied retroactively to misrepresent prior
evidence.

---

## 23. P1-01 Exit Criteria

P1-01 can be recorded complete only when:

- this policy is explicitly approved;
- Kraken-only prospective accumulation is accepted with its time-to-adequacy
  limitation;
- the prohibition on automatic correction is accepted;
- the fail-closed conflict policy is accepted;
- the normalized source-equivalent retention boundary is accepted;
- every unresolved quantitative value is either explicitly approved in a
  policy amendment or remains a named blocker to the implementation task that
  needs it; and
- no P1-02 implementation has begun.

Approval of this policy authorizes planning for P1-02 only after a separate
task instruction. It does not itself authorize code, migrations, APIs,
acquisition, scheduling, or later-phase work.
