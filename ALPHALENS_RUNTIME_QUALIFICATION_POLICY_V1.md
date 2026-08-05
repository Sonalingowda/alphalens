# AlphaLens Runtime Qualification Policy v1.0

**Policy identifier:** `alphalens_runtime_qualification_ema_rsi`

**Policy version:** `1.0.0`

**Policy status:** Approved and frozen

**Approval date:** 2026-08-04

**Approval authority:** AlphaLens project owner, POLICY-004

**Artifact type:** Immutable executable runtime qualification policy

**Scope:** `BTCUSDT` spot market, `5m` timeframe only

**Configuration hash algorithm:** SHA-256

**Configuration hash:**
`44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e`

This document is the complete policy artifact for the stated identifier and
version. It is immutable. Any change to scope, required inputs, gates,
decision mapping, reason codes, identities, timestamps, missing-data handling,
or hashing requires a new policy version and explicit approval.

---

## 1. Purpose and boundary

This policy determines whether one valid persisted `BUY` or `SELL` assessment
may enter the Scoring stage. It performs structural qualification only; it
introduces no score, confidence, rank, dashboard projection, notification, or
trading instruction. Qualification is not a ranking or a recommendation.

## 2. Required persisted inputs

The evaluator MUST resolve and verify, through the existing repositories,
exactly one immutable instance of each of the following objects:

1. An `Opportunity` produced by
   `alphalens_runtime_assessment_ema_rsi` version `1.0.1` with hash
   `4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d`.
2. An `EvidencePackage` produced by
   `alphalens_runtime_evidence_ema_rsi` version `1.0.0` with hash
   `9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8`.
3. A `MarketContext` with an identity and integrity digest exactly matching
   the `Opportunity.context_reference` and evidence-package context source
   reference.
4. A `FeatureSnapshot` and one complete-candle `MarketSnapshot` whose
   identities and integrity digests match the assessment provenance and the
   evidence-package source references.

All inputs MUST have scope `BTCUSDT` / `5m`. The evidence package MUST have
`candidate_id` equal to the assessment candidate identifier and
`assessment_id=null`. Caller-supplied instances MUST be byte-equivalent under
canonical serialization to their repository-resolved objects.

## 3. Required lineage, chronology, and freshness validation

The assessment's evidence-package and context references; the assessment audit
provenance references, in order; the evidence-package provenance; and the
repository-resolved objects MUST be mutually identical by identifier and
integrity digest. The assessment provenance source order is exactly:

```text
OpportunityCandidate
EvidencePackage
MarketSnapshot
FeatureSnapshot
MarketContext
```

The assessment evidence cutoff is the qualification evidence cutoff. Every
required artifact, policy reference, feature value, context observation, and
evidence item MUST be available at or before it. The market candle, required
feature values, data-quality observation, and evidence records MUST refer to
the evaluated candle. No wall-clock timeout, forward fill, interpolation, or
retrospective correction is allowed.

The context data-quality component MUST be `AVAILABLE` with exactly one
Boolean `data_quality.persisted_inputs_verified=true` observation for that
candle. The evidence package MUST contain its complete approved runtime record
set, including explicit unavailable `market_structure` with limitation
`context.structure.unavailable`.

## 4. Deterministic qualification output

On successful evaluation, the service MUST create and persist exactly one
immutable `QualificationRecord` with identity:

```text
qualification_id = qualification.runtime_ema_rsi.{assessment_id}
```

The successful qualification status is `COMPLETED`, represented by the
persisted `QualificationRecord` and completed Qualification pipeline-stage
record; it is not a separate mutable artifact.

The record MUST contain the exact assessment, evidence-package, and context
references; this policy reference; ordered gate results from Section 6; no
exclusions; limitations exactly equal to the assessment limitations; and audit
`evidence_cutoff`, `created_at`, and `available_at` all equal to the assessment
evidence cutoff.

The audit provenance source references are ordered as in Section 3. Its policy
reference is this policy. Its configuration hash is this policy hash, its
lineage hash is the canonical SHA-256 of those ordered sources, and its result
hash is the canonical SHA-256 of the complete record excluding that result-hash
field.

## 5. Deterministic qualification mapping

This policy defines one valid completed decision:

| Required assessment stance | Required gate results | Qualification outcome |
| --- | --- | --- |
| `BUY` or `SELL` | Every ordered gate in Section 6 is `PASS` | `QUALIFIED` |

`WAIT` is not a valid input under the governing Assessment Policy v1.0.1.
It MUST NOT be converted to `NOT_QUALIFIED`, `UNAVAILABLE`, or a neutral
substitute by this policy. No valid input in this narrowly scoped policy maps
to `NOT_QUALIFIED`; such a mapping requires a new approved policy version with
an explicit disqualifying gate.

## 6. Ordered gate and reason-code mapping

The `QualificationRecord.gate_results` MUST appear in this order:

| Gate identifier | Requirement class | Status | Ordered reason code | Evidence references |
| --- | --- | --- | --- | --- |
| `qualification.persisted_inputs` | `persisted_inputs` | `PASS` | `qualification.persisted_inputs_verified` | assessment, evidence package, context, feature snapshot, market snapshot |
| `qualification.assessment_policy` | `assessment_policy` | `PASS` | `qualification.assessment_policy_verified` | assessment |
| `qualification.evidence_lineage` | `evidence_lineage` | `PASS` | `qualification.evidence_lineage_verified` | evidence package, context, feature snapshot, market snapshot |
| `qualification.scope_chronology` | `scope_chronology` | `PASS` | `qualification.scope_chronology_verified` | assessment, evidence package, context, feature snapshot, market snapshot |

No gate, reason code, exclusion, limitation, or decision may be inferred from
an unapproved score, forecast, confidence value, external source, or evidence
count.

## 7. Missing input, policy block, and fail-closed behavior

No partial `QualificationRecord` may be persisted. The service MUST finish all
validation and construct every gate before its single repository persistence
operation. It MUST not retry, mutate an existing artifact, regenerate
features/evidence, fetch live data, or substitute a neutral result.

| Condition | Qualification stage record | Terminal pipeline outcome | Persisted qualification artifact |
| --- | --- | --- | --- |
| Required repository object, evidence record, reference, digest, scope, timestamp, or availability is absent, invalid, conflicting, or future-unavailable | `BLOCKED` with `qualification.input_unavailable` | `UNAVAILABLE` | None |
| Assessment/evidence lineage, required record set, gate order, or decision trace is invalid | `BLOCKED` with `qualification.contract_unavailable` | `UNAVAILABLE` | None |
| This policy identifier, version, configuration hash, or approval is absent, invalid, or unavailable | `BLOCKED` with `qualification.policy_unavailable` | `POLICY_BLOCKED` | None |
| Repository persistence fails | `BLOCKED` with `qualification.persistence_unavailable` | `UNAVAILABLE` | None |

For every terminal failure path, Scoring and all downstream stages MUST NOT
execute. The blocked stage record and immutable pipeline audit are persisted
only when the pipeline-audit repository is available; their absence never
authorizes a substitute qualification artifact.

## 8. Idempotency and immutability

For byte-identical persisted inputs, policy reference, code version, and
canonical configuration, replay MUST reconstruct byte-identical
`QualificationRecord` content with the identity in Section 4. Saving that
content is idempotent. A conflicting artifact with that immutable identity MUST
fail closed and MUST NOT overwrite, update, or supersede the existing record.

The opportunity, evidence package, market context, feature snapshot, and market
snapshot are immutable inputs. This policy never modifies them.

## 9. Canonical configuration payload

The configuration hash above is SHA-256 of this UTF-8 canonical JSON payload:

```json
{"assessment_policy":{"hash":"4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d","id":"alphalens_runtime_assessment_ema_rsi","version":"1.0.1"},"decision_mapping":{"qualified":{"required_stances":["BUY","SELL"],"result":"QUALIFIED"}},"freshness":"all_required_artifacts_available_at_or_before_assessment_evidence_cutoff","gates":["persisted_inputs_verified","assessment_policy_verified","evidence_lineage_verified","scope_and_chronology_verified"],"identities":{"qualification":"qualification.runtime_ema_rsi.{assessment_id}"},"missing_input":"unavailable_no_qualification_record","policy_id":"alphalens_runtime_qualification_ema_rsi","scope":{"instrument":"BTCUSDT","timeframe":"5m"},"version":"1.0.0"}
```
