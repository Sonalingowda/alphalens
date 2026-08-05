# AlphaLens Runtime Assessment Policy v1.0

**Policy identifier:** `alphalens_runtime_assessment_ema_rsi`

**Policy version:** `1.0.0`

**Policy status:** Superseded by `ALPHALENS_RUNTIME_ASSESSMENT_POLICY_V1.0.1.md`

**Approval date:** 2026-08-04

**Approval authority:** AlphaLens project owner, POLICY-003

**Artifact type:** Immutable executable runtime assessment policy

**Scope:** `BTCUSDT` spot market, `5m` timeframe only

**Configuration hash algorithm:** SHA-256

**Configuration hash:**
`713e488f81043bd28e97467a7884ed69c3ac5b5bfeeec75c5ca18d4006ff024d`

This document is the complete policy artifact for the stated identifier and
version. It is immutable. Any change to scope, required inputs, lineage,
decision mapping, reason codes, identities, timestamps, missing-data handling,
or hashing requires a new policy version and explicit approval.

---

## 1. Purpose and boundary

This policy converts one valid persisted candidate and its valid persisted
runtime evidence into one canonical `Opportunity` assessment. It introduces no
new market predicate: it verifies and projects the already-approved detection
direction from `alphalens_runtime_detection_ema_rsi`.

It does not define qualification, scoring, ranking, dashboard projection,
notification, confidence, plan, or any trading instruction. A completed
assessment is not a qualification or a recommendation to execute a trade.

## 2. Required persisted inputs

The evaluator MUST resolve and verify, through the existing repositories,
exactly one immutable instance of each of the following objects:

1. An `OpportunityCandidate` produced by
   `alphalens_runtime_detection_ema_rsi` version `1.0.0` with hash
   `d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a`.
2. An `EvidencePackage` produced by
   `alphalens_runtime_evidence_ema_rsi` version `1.0.0` with hash
   `9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8`.
   It MUST have `candidate_id` equal to the candidate identifier and
   `assessment_id=null`, as required by the evidence policy.
3. A `MarketContext` whose identifier and integrity digest exactly match the
   candidate's context reference and the evidence package's context source
   reference.
4. A `FeatureSnapshot` whose identifier and integrity digest exactly match the
   candidate's feature reference and the evidence package's feature source
   reference.
5. A complete one-candle `MarketSnapshot` whose identifier and integrity digest
   exactly match the candidate's market reference and the evidence package's
   market source reference.

All inputs MUST have scope `BTCUSDT` / `5m`. Caller-supplied instances MUST be
byte-equivalent under canonical serialization to the corresponding repository
objects. Supplied objects are never trusted merely because their identifiers
match.

The evidence package MUST contain exactly one canonical record for each key:

```text
market_price_close
market_volume
ema_12
ema_26
rsi
atr_true_range
ema_alignment
rsi_state
market_structure
```

The records, taxonomy, source definitions, source references, observations,
availability, and limitations MUST satisfy
`ALPHALENS_RUNTIME_EVIDENCE_POLICY_V1`. In particular, `market_structure` MUST
remain the explicit unavailable structure record with limitation
`context.structure.unavailable`; it is not missing input for this policy.

## 3. Lineage, chronology, and freshness validation

The candidate's market, feature, and context references; the evidence
package's candidate, market, feature, and context provenance references; and
the repository-resolved objects MUST be mutually identical by identifier and
integrity digest. The evidence package MUST retain the exact candidate,
detection-policy, and evidence-policy lineage required by its governing
policy.

The candidate evidence cutoff is the assessment evidence cutoff. Every
required source, feature value, context observation, evidence record, and
policy reference MUST be available at or before that cutoff. The market candle,
required feature values, context data-quality observation, and every evidence
record MUST refer to the evaluated candle. No wall-clock timeout is defined.
Freshness is exclusively exact lineage plus causal availability at or before
the candidate evidence cutoff.

The assessment MUST verify that the context data-quality component is
`AVAILABLE` and contains exactly one Boolean
`data_quality.persisted_inputs_verified=true` observation for that candle.

## 4. Deterministic assessment output

On successful evaluation, the service MUST create and persist exactly one
immutable canonical `Opportunity` with these identities:

```text
assessment_id          = assessment.runtime_ema_rsi.{candidate_id}
decision_id            = decision.runtime_ema_rsi.{candidate_id}
opportunity_id         = opportunity.runtime_ema_rsi.{candidate_id}
opportunity_version_id = opportunity.runtime_ema_rsi.{candidate_id}.v1
```

The successful assessment status is `COMPLETED`. `COMPLETED` is represented by
the persisted `Opportunity` and the completed Assessment pipeline-stage record;
it is not a separate mutable domain artifact.

The `Opportunity` MUST contain:

- the candidate identifier and scope;
- the decision produced in Section 5;
- this policy's identifier, version, and configuration hash as its decision
  policy reference;
- exact integrity references to the persisted evidence package and market
  context;
- source provenance references, in order: candidate, evidence package, market
  snapshot, feature snapshot, market context;
- the ordered reason codes from Section 6;
- limitations exactly equal to the evidence package limitations;
- no qualification reference, score reference, confidence record, plan,
  supersession reference, or `valid_until` value; and
- audit `evidence_cutoff`, `created_at`, and `available_at` all equal to the
  candidate evidence cutoff.

The audit configuration hash is this policy hash. Its lineage hash is the
canonical SHA-256 of the ordered five source references above. Its result hash
is the canonical SHA-256 of the complete `Opportunity` content excluding that
result-hash field.

## 5. Deterministic decision mapping

This policy accepts only the two exact ordered candidate-reason tuples below.
The corresponding evidence policy-trace records MUST have the stated observed
values. Any other tuple or trace is invalid input, not a `WAIT` decision.

| Candidate reason codes, in order | `ema_alignment` | `rsi_state` | Decision |
| --- | --- | --- | --- |
| `detection.persisted_inputs_verified`, `detection.ema12_above_ema26`, `detection.rsi_ge_55` | `true` | `buy_threshold_met` | `BUY` |
| `detection.persisted_inputs_verified`, `detection.ema12_below_ema26`, `detection.rsi_le_45` | `false` | `sell_threshold_met` | `SELL` |

`WAIT` is not a valid successful output of this policy because the Assessment
stage is reached only with a candidate detected under one of those two approved
directional conditions. `WAIT` MUST NOT be used to represent missing,
unavailable, invalid, conflicting, or policy-blocked input.

## 6. Ordered reason-code mapping

| Decision | Ordered `Opportunity.reason_codes` |
| --- | --- |
| `BUY` | `assessment.persisted_inputs_verified`, `assessment.evidence_lineage_verified`, `assessment.buy_direction_confirmed` |
| `SELL` | `assessment.persisted_inputs_verified`, `assessment.evidence_lineage_verified`, `assessment.sell_direction_confirmed` |

No reason code may be added, removed, reordered, or derived from an unapproved
inference, score, forecast, confidence value, or external source.

## 7. Missing input, policy block, and fail-closed behavior

No partial `Opportunity` may be persisted. The service MUST perform all
validation and decision construction before its single repository persistence
operation. Repository failures MUST propagate; the service MUST not retry,
modify an existing artifact, regenerate evidence or features, fetch live data,
or substitute a neutral value.

| Condition | Assessment stage record | Terminal pipeline outcome | Persisted assessment artifact |
| --- | --- | --- | --- |
| Required repository object, evidence record, reference, digest, scope, timestamp, or availability is absent, invalid, conflicting, or future-unavailable | `BLOCKED` with `assessment.input_unavailable` | `UNAVAILABLE` | None |
| Candidate/evidence lineage or decision trace does not satisfy Sections 2–5 | `BLOCKED` with `assessment.contract_unavailable` | `UNAVAILABLE` | None |
| This policy identifier, version, configuration hash, or approval is absent, invalid, or unavailable | `BLOCKED` with `assessment.policy_unavailable` | `POLICY_BLOCKED` | None |
| Repository persistence fails | `BLOCKED` with `assessment.persistence_unavailable` | `UNAVAILABLE` | None |

For all terminal failure paths, downstream stages MUST NOT execute. The blocked
stage record and immutable pipeline audit are persisted only when the
pipeline-audit repository is available, as required by the runtime contract.
Their absence never authorizes a substitute assessment artifact.

## 8. Idempotency and immutability

For byte-identical persisted inputs, policy reference, code version, and
canonical configuration, replay MUST reconstruct byte-identical `Opportunity`
content with the identities in Section 4. Saving that content is idempotent.
A conflicting artifact with any of those immutable identities MUST fail closed;
it MUST NOT overwrite, update, or supersede the existing artifact.

The candidate, evidence package, market context, feature snapshot, and market
snapshot are immutable inputs. This policy never modifies them. In particular,
the evidence package remains `assessment_id=null`; no evidence artifact is
rewritten to attach the resulting assessment.

## 9. Canonical configuration payload

The configuration hash above is SHA-256 of this UTF-8 canonical JSON payload:

```json
{"candidate_policy":{"hash":"d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a","id":"alphalens_runtime_detection_ema_rsi","version":"1.0.0"},"decision_mapping":{"buy":{"candidate_reason_codes":["detection.persisted_inputs_verified","detection.ema12_above_ema26","detection.rsi_ge_55"],"evidence_trace":{"ema_alignment":true,"rsi_state":"buy_threshold_met"},"stance":"BUY"},"sell":{"candidate_reason_codes":["detection.persisted_inputs_verified","detection.ema12_below_ema26","detection.rsi_le_45"],"evidence_trace":{"ema_alignment":false,"rsi_state":"sell_threshold_met"},"stance":"SELL"}},"evidence_policy":{"hash":"9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8","id":"alphalens_runtime_evidence_ema_rsi","version":"1.0.0"},"freshness":"all_required_artifacts_available_at_or_before_candidate_evidence_cutoff","identities":{"assessment":"assessment.runtime_ema_rsi.{candidate_id}","decision":"decision.runtime_ema_rsi.{candidate_id}","opportunity":"opportunity.runtime_ema_rsi.{candidate_id}","opportunity_version":"opportunity.runtime_ema_rsi.{candidate_id}.v1"},"missing_input":"unavailable_no_opportunity","policy_id":"alphalens_runtime_assessment_ema_rsi","required_evidence_records":["market_price_close","market_volume","ema_12","ema_26","rsi","atr_true_range","ema_alignment","rsi_state","market_structure"],"scope":{"instrument":"BTCUSDT","timeframe":"5m"},"version":"1.0.0"}
```
