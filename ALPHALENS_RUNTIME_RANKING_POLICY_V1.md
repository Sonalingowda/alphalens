# AlphaLens Runtime Ranking Policy v1.0

**Policy identifier:** `alphalens_runtime_ranking_ema_rsi`

**Policy version:** `1.0.0`

**Policy status:** Approved and frozen

**Approval date:** 2026-08-05

**Approval authority:** AlphaLens project owner, POLICY-006

**Artifact type:** Immutable executable runtime ranking policy

**Repository location:**
`/Users/sonalingowda/Downloads/alphalens/ALPHALENS_RUNTIME_RANKING_POLICY_V1.md`

**Scope:** `BTCUSDT` spot market, `5m` timeframe only

**Configuration hash algorithm:** SHA-256

**Configuration hash:**
`fa00f13d2344ed27e415d28955fb7e816a9d38718b4fdad7e76ab2976d42d238`

This document is the complete policy artifact for the stated identifier and
version. It is immutable. Any change to scope, required inputs, lineage
validation, freshness, ordering algorithm, tie-breaking rules, population
definition, idempotency, fail-closed behavior, or hashing requires a new
policy version and explicit approval.

---

## 1. Purpose and boundary

This policy converts one or more valid, persisted `ScoreResult` artifacts into
one deterministic, immutable `RankingSnapshot` for the Dashboard Projection
stage. It assigns a stable ordinal rank to every member of the ranking
population and exposes no artifact that was not produced by an approved
upstream pipeline stage.

This policy does not define detection predicates, evidence semantics,
assessment mathematics, qualification gates, scoring dimensions, dashboard
layout, detail projection, notification, confidence, plan, or any trading
instruction. A `RankingSnapshot` is not a recommendation to execute a trade.

---

## 2. Required persisted inputs

The evaluator MUST resolve through the existing repositories all of the
following immutable, repository-persisted objects:

1. Every `ScoreResult` in the ranking population as defined in Section 7,
   each governed by `alphalens_runtime_scoring_ema_rsi` version `1.0.0`,
   configuration hash
   `2e6b45f3d3f285b085677b647bfdb21bbf8359a4b184c84742025ec051f88328`.

2. For each `ScoreResult`, its referenced `QualificationRecord`, governed by
   `alphalens_runtime_qualification_ema_rsi` version `1.0.0`, configuration
   hash
   `44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e`.

3. For each `QualificationRecord`, its referenced `Opportunity`, governed by
   `alphalens_runtime_assessment_ema_rsi` version `1.0.1`, configuration hash
   `4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d`.

The governing detection-policy reference is
`alphalens_runtime_detection_ema_rsi` version `1.0.0`, configuration hash
`d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a`.
It is verified only through the persisted upstream lineage; it is not an
additional ranking input.

All inputs MUST have scope `BTCUSDT` / `5m`. Caller-supplied instances MUST
be byte-equivalent under canonical serialization to their repository-resolved
objects. Supplied in-memory objects that do not byte-equivalently match their
persisted identities MUST be rejected as unavailable.

No network response, reconstructed value, inferred artifact, or unpersisted
object may be used.

---

## 3. Required lineage validation

For every candidate member of the ranking population the service MUST verify,
through repository resolution, that:

1. The `ScoreResult.qualification_id` resolves to a `QualificationRecord`
   whose identifier and integrity digest match the score's qualification
   reference exactly.

2. The `QualificationRecord.assessment_id` resolves to an `Opportunity` whose
   identifier and integrity digest match the qualification's assessment
   reference exactly.

3. The `Opportunity` carries the governing detection-policy reference
   `alphalens_runtime_detection_ema_rsi` version `1.0.0` with hash
   `d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a`.

4. The ordered upstream source provenance preserved in the
   `QualificationRecord` is exactly:

   ```text
   OpportunityCandidate
   EvidencePackage
   MarketSnapshot
   FeatureSnapshot
   MarketContext
   ```

5. The `ScoreResult` component `opportunity_quality` is present, its
   `component_version` is `1.0.0`, its `raw_value` is exactly `100` or `50`,
   and its `contribution` equals its `raw_value`.

Any member that fails lineage validation is excluded from the population before
ordering. Its exclusion MUST be recorded in the `RankingSnapshot.exclusions`
collection with reason code `ranking.lineage_validation_failed`. A fully
excluded population (zero valid members remaining after all exclusions and
freshness filtering) produces an empty-member `RankingSnapshot` per the
approved behavior in Section 9; it does not produce an `UNAVAILABLE` outcome.

---

## 4. Freshness validation

The ranking cutoff is the maximum `available_at` timestamp across all
repository-resolved `ScoreResult` objects admitted to the population after
lineage validation. Every resolved `ScoreResult`, `QualificationRecord`, and
`Opportunity` MUST have been available at or before the ranking cutoff.

No artifact, policy reference, or evidence item whose availability exceeds the
ranking cutoff may be used to contribute to ordering. The service MUST NOT
fetch live data, regenerate artifacts, forward-fill, interpolate, substitute,
or use later corrections.

If a member's `ScoreResult.available_at` exceeds the ranking cutoff computed
from other population members, that member MUST be excluded with reason code
`ranking.freshness_violation` and the ranking cutoff MUST be recomputed from
the remaining admitted members. This process repeats until no admitted member
violates the cutoff. An empty result after exhaustive exclusion is handled per
Section 9.

---

## 5. Idempotency semantics

For byte-identical persisted inputs (the complete admitted population of
`ScoreResult` objects), validated lineage, policy reference, code version, and
canonical configuration, replay MUST reconstruct byte-identical
`RankingSnapshot` content including member order, all rank assignments,
exclusions, and hashes.

Saving that content is idempotent. A conflicting artifact with any of the
immutable identities in Section 10 MUST fail closed; it MUST NOT overwrite,
update, or supersede the existing snapshot.

The `ScoreResult`, `QualificationRecord`, and `Opportunity` objects are
immutable inputs. This policy never modifies them.

---

## 6. Fail-closed and POLICY_BLOCKED behavior

No partial, neutral, substitute, or inferred `RankingSnapshot` may be
persisted. The service MUST complete all validation and construct the whole
immutable snapshot before its single repository persistence operation.

| Condition | Ranking stage record | Terminal pipeline outcome | Persisted snapshot |
|---|---|---|---|
| A required repository object, integrity digest, scope, or policy reference for the triggering pipeline run's `ScoreResult` is absent, invalid, conflicting, or unavailable at cutoff | `BLOCKED` with `ranking.input_unavailable` | `UNAVAILABLE` | None |
| Lineage, contract, or ordering validation for the triggering run's `ScoreResult` fails in a way that leaves no population admissible | `BLOCKED` with `ranking.contract_unavailable` | `UNAVAILABLE` | None |
| This policy identifier, version, configuration hash, or approval is absent, invalid, or unavailable | `BLOCKED` with `ranking.policy_unavailable` | `POLICY_BLOCKED` | None |
| Repository persistence fails | `BLOCKED` with `ranking.persistence_unavailable` | `UNAVAILABLE` | None |

For every terminal failure path, Dashboard Projection and all downstream stages
MUST NOT execute. The blocked stage record and immutable pipeline audit are
persisted only when the pipeline-audit repository is available. Their absence
never authorizes a substitute snapshot.

A `ScoreResult` that fails lineage validation is excluded per Section 3, not
treated as a blocking input failure, except for the triggering pipeline run's
own `ScoreResult` (see Section 7 for population definition and the treatment
of the triggering member).

---

## 7. Ranking population definition

The ranking population for one pipeline run consists of all `ScoreResult`
objects that satisfy all four of the following conditions:

1. Persisted under `alphalens_runtime_scoring_ema_rsi` version `1.0.0` with
   configuration hash
   `2e6b45f3d3f285b085677b647bfdb21bbf8359a4b184c84742025ec051f88328`.

2. Have scope `BTCUSDT` / `5m`.

3. Have `available_at` within the rolling 15-minute window ending at and
   including the ranking cutoff. A `ScoreResult` is within the window when:

   ```text
   ranking_cutoff − 15 minutes < ScoreResult.available_at ≤ ranking_cutoff
   ```

   The window is open on the left (exclusive) and closed on the right
   (inclusive). `ScoreResult` objects with `available_at` outside this range
   MUST NOT be admitted to the population.

4. Pass lineage validation per Section 3.

**Approved decision (OQ-1, 2026-08-05):** The population is all non-expired
`ScoreResult` artifacts for the same instrument and timeframe within a rolling
15-minute window. The window bound is the ranking cutoff; maximum age is 15
minutes.

The triggering pipeline run's `ScoreResult` MUST be included in the candidate
set before lineage validation. If that `ScoreResult` itself fails lineage
validation, the pipeline run MUST fail closed with `ranking.input_unavailable`
rather than produce a snapshot that excludes its own triggering artifact.

---

## 8. Deterministic ordering algorithm

After population construction and lineage validation, the service MUST rank
admitted members by applying the following three-key sort exactly, in order,
with no additional key permitted in this version:

**Primary key — composite value, descending:**
Each member's rank-composite value is the `ScoreResult` component
`opportunity_quality` raw value. Valid values are `100`
(`QUALIFIED_COMPLETE`) and `50` (`QUALIFIED_LIMITED`). Higher composite
values receive lower (better) rank numbers. A member with composite value
`100` always outranks a member with composite value `50`.

**Secondary key — qualification timestamp, ascending:**
Among members with equal composite value, the member whose
`QualificationRecord.available_at` timestamp is earlier receives the lower
(better) rank number. Earlier qualification timestamps indicate earlier
confirmed opportunity status and rank first.

**Tertiary key — `score_id`, lexicographic ascending:**
Among members with equal composite value and equal
`QualificationRecord.available_at`, the member whose `ScoreResult.score_id`
sorts earlier in lexicographic ascending (byte-by-byte Unicode code-point)
order receives the lower (better) rank number. This key is deterministic and
derived entirely from persisted artifact identity; it introduces no market
judgment or external state.

Rank numbers are assigned as dense integers starting at `1`. No gaps are
introduced. All comparisons are exact. No rounding, floating-point conversion,
probabilistic weighting, normalization, or cross-population calibration is
applied.

**Approved decision (OQ-2, 2026-08-05):** The canonical tiebreaker is
lexicographic ascending order of `ScoreResult.score_id`.

---

## 9. Tie-breaking rules and empty-population behavior

The three-key sort in Section 8 is fully deterministic. Because
`ScoreResult.score_id` is a unique persisted identifier, no two distinct
members can be equal under all three keys simultaneously. No further
tiebreaker is required or permitted in this version.

**Empty population:** When the admitted population contains zero members after
all window filtering, lineage validation, and freshness exclusion, the service
MUST persist an empty-member `RankingSnapshot` (zero `members`, full
`exclusions` log, `member_count = 0`) and append a `COMPLETED` Ranking
pipeline-stage record. The pipeline run continues to Dashboard Projection. The
empty snapshot MUST NOT produce an `UNAVAILABLE` or `POLICY_BLOCKED` outcome.

**Approved decision (OQ-3, 2026-08-05):** An empty ranking population is a
valid successful outcome. The service MUST persist an empty `RankingSnapshot`
and MUST NOT return `UNAVAILABLE`.

---

## 10. RankingSnapshot artifact definition

On successful evaluation, the service MUST create and persist exactly one
immutable `RankingSnapshot` with identity:

```text
ranking_id = ranking.runtime_ema_rsi.{instrument}.{timeframe}.{ranking_cutoff_epoch_ms}
```

where `{instrument}` is `BTCUSDT`, `{timeframe}` is `5m`, and
`{ranking_cutoff_epoch_ms}` is the ranking cutoff in UTC epoch milliseconds.

The `RankingSnapshot` MUST contain:

- `ranking_id` as above;
- `scope`: `BTCUSDT` / `5m`;
- `ranking_cutoff`: the UTC epoch milliseconds timestamp computed per
  Section 4;
- `policy_reference`: this policy identifier, version, and configuration
  hash;
- `members`: an ordered list of `RankingMember` records, one per admitted
  member, in ascending rank order (rank `1` first), each containing:
  - `rank`: dense integer starting at `1`;
  - `score_id`: the `ScoreResult` identifier;
  - `qualification_id`: the `QualificationRecord` identifier;
  - `opportunity_id`: the `Opportunity` identifier;
  - `composite_value`: the `opportunity_quality` raw value (`100` or `50`);
  - `opportunity_quality`: `QUALIFIED_COMPLETE` or `QUALIFIED_LIMITED`;
  - `qualification_timestamp`: the `QualificationRecord.available_at` value
    used as the secondary sort key;
- `exclusions`: an ordered list of `RankingExclusion` records, one per
  excluded candidate, each containing:
  - `score_id`: the excluded `ScoreResult` identifier;
  - `reason_code`: one of `ranking.lineage_validation_failed` or
    `ranking.freshness_violation`;
  - `detail`: a human-readable non-normative description of the failure;
- `member_count`: the count of admitted ranked members;
- `exclusion_count`: the count of excluded candidates;
- `population_hash`: SHA-256 of the canonical UTF-8 JSON serialization of the
  ordered `score_id` list of all admitted members before ordering (sorted
  lexicographically ascending), to enable population audit;
- `ordering_hash`: SHA-256 of the canonical UTF-8 JSON serialization of the
  ordered list of `score_id` values after ranking (rank `1` first);
- `result_hash`: SHA-256 of the complete canonical `RankingSnapshot` content
  excluding the `result_hash` field itself;
- `audit.evidence_cutoff`: the ranking cutoff;
- `audit.created_at`: service creation timestamp;
- `audit.available_at`: equals `audit.evidence_cutoff`;
- `audit.policy_hash`: this policy configuration hash
  `fa00f13d2344ed27e415d28955fb7e816a9d38718b4fdad7e76ab2976d42d238`;
- `audit.lineage_hash`: SHA-256 of the canonical UTF-8 JSON serialization of
  the ordered `score_id` list of all admitted members (lexicographically
  ascending).

No confidence, risk, reward, forecast, trading instruction, or fabricated
domain object may appear in the `RankingSnapshot`. For an empty population,
`members` is an empty list, `member_count` is `0`, `population_hash` and
`ordering_hash` are SHA-256 of the canonical serialization of an empty JSON
array (`[]`).

---

## 11. Duplicate execution behavior

If a `RankingSnapshot` with the identical `ranking_id` (same instrument,
timeframe, and ranking-cutoff epoch milliseconds) already exists in the
repository, the service MUST verify that the newly computed snapshot content
is byte-identical under canonical serialization to the stored artifact. If
byte-identical, the write is a no-op (idempotent). If content differs, the
service MUST fail closed with `ranking.input_unavailable` and MUST NOT
overwrite, update, or supersede the existing snapshot.

---

## 12. Repository persistence requirements

The `RankingSnapshot` MUST be persisted through the existing immutable
ranking repository before the Ranking pipeline-stage record is appended as
`COMPLETED`. The stage record MUST NOT be appended before the repository write
succeeds. No in-memory, partial, or synthetic snapshot satisfies this
requirement.

The service MUST NOT bypass repositories, mutate upstream inputs, create
synthetic data, or perform a second write to amend the snapshot. A single
atomic write is the only permitted persistence operation per execution.

---

## 13. Canonical configuration payload

The configuration hash `fa00f13d2344ed27e415d28955fb7e816a9d38718b4fdad7e76ab2976d42d238`
is the SHA-256 of the following UTF-8 compact sorted-key JSON payload:

```json
{"composite_domain":{"lower":50,"upper":100},"conflict_behavior":"fail_closed_no_overwrite","dependencies":{"assessment_policy":{"hash":"4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d","id":"alphalens_runtime_assessment_ema_rsi","version":"1.0.1"},"detection_policy":{"hash":"d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a","id":"alphalens_runtime_detection_ema_rsi","version":"1.0.0"},"evidence_policy":{"hash":"9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8","id":"alphalens_runtime_evidence_ema_rsi","version":"1.0.0"},"qualification_policy":{"hash":"44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e","id":"alphalens_runtime_qualification_ema_rsi","version":"1.0.0"},"scoring_policy":{"hash":"2e6b45f3d3f285b085677b647bfdb21bbf8359a4b184c84742025ec051f88328","id":"alphalens_runtime_scoring_ema_rsi","version":"1.0.0"}},"empty_population_behavior":"valid_empty_snapshot_persist_ranking_snapshot","freshness":"all_members_available_at_or_before_ranking_cutoff","idempotency":"byte_identical_replay_no_op","identity_template":"ranking.runtime_ema_rsi.{instrument}.{timeframe}.{ranking_cutoff_epoch_ms}","missing_input":"unavailable_no_snapshot","ordering":{"primary":{"direction":"descending","key":"composite_value"},"secondary":{"direction":"ascending","key":"qualification_timestamp"},"tiebreaker":{"direction":"ascending","key":"score_id","method":"lexicographic"}},"policy_id":"alphalens_runtime_ranking_ema_rsi","population_window":{"instrument":"BTCUSDT","timeframe":"5m","type":"rolling","window_minutes":15},"quality_mapping":{"QUALIFIED_COMPLETE":100,"QUALIFIED_LIMITED":50},"rank_assignment":"dense_integer_from_1","required_inputs":["ScoreResult[]","QualificationRecord[]","Opportunity[]"],"scope":{"instrument":"BTCUSDT","timeframe":"5m"},"version":"1.0.0"}
```
