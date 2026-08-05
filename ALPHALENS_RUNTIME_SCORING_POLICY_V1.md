# AlphaLens Runtime Scoring Policy v1.0

**Policy identifier:** `alphalens_runtime_scoring_ema_rsi`

**Policy version:** `1.0.0`

**Policy status:** Approved and frozen

**Approval date:** 2026-08-04

**Approval authority:** AlphaLens project owner, POLICY-005

**Artifact type:** Immutable executable runtime scoring policy

**Repository location:**
`/Users/sonalingowda/Downloads/alphalens/ALPHALENS_RUNTIME_SCORING_POLICY_V1.md`

**Scope:** `BTCUSDT` spot market, `5m` timeframe only

**Configuration hash algorithm:** SHA-256

**Configuration hash:**
`2e6b45f3d3f285b085677b647bfdb21bbf8359a4b184c84742025ec051f88328`

This document is the complete policy artifact for the stated identifier and
version. It is immutable. Any change to scope, inputs, validation, quality
mapping, ordering, reason codes, identities, timestamps, missing-data
handling, or hashing requires a new policy version and explicit approval.

---

## 1. Purpose and boundary

This policy produces a deterministic, qualitative, ordinal opportunity score
for Ranking only. It prioritizes valid qualified opportunities within one
ranking population. It does not estimate future return, probability, expected
profit, execution quality, confidence, reward, or risk, and it creates no
trading instruction.

The only scoring dimension is Opportunity Quality. Its values are ordinal
labels with the fixed composite values in Section 6. They have no statistical,
probabilistic, monetary, or cross-population interpretation.

## 2. Permitted persisted inputs

The evaluator MUST resolve through the existing repositories exactly one
immutable, repository-persisted instance of each of the following:

1. A valid qualified `QualificationRecord` governed by
   `alphalens_runtime_qualification_ema_rsi` version `1.0.0`, configuration
   hash `44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e`.
2. Its referenced persisted `Opportunity`, governed by
   `alphalens_runtime_assessment_ema_rsi` version `1.0.1`, configuration hash
   `4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d`.
3. Its referenced persisted runtime evidence (`EvidencePackage`), governed by
   `alphalens_runtime_evidence_ema_rsi` version `1.0.0`, configuration hash
   `9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8`.
4. Persisted lineage verification, persisted evidence-completeness verification,
   and persisted repository-integrity verification for those artifacts.

The governing detection-policy reference is
`alphalens_runtime_detection_ema_rsi` version `1.0.0`, configuration hash
`d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a`.
It is verified only through the persisted upstream lineage; it is not an
additional scoring input.

No input other than the persisted artifacts and verifications above is
permitted. In particular, this policy MUST NOT derive, require, infer, or use
spread, liquidity, realized volatility, market regime, session, structure,
momentum, or trend.

## 3. Lineage, integrity, and freshness validation

The scoring evidence cutoff is the `QualificationRecord` evidence cutoff. The
qualification reference, opportunity reference, evidence-package reference,
and their repository-resolved objects MUST match by identifier and integrity
digest. The qualification record MUST be the completed, qualified result of
the approved Qualification Policy.

Lineage verification MUST preserve the ordered upstream source provenance
required by that policy:

```text
OpportunityCandidate
EvidencePackage
MarketSnapshot
FeatureSnapshot
MarketContext
```

Every required artifact, policy reference, evidence item, validation result,
and repository-resolved source MUST have been available at or before the
scoring evidence cutoff. The evaluator MUST not fetch live data, regenerate
artifacts, forward-fill, interpolate, substitute, or use later corrections.

Evidence completeness means the complete required record set defined by the
approved Evidence Policy is present and valid. A deliberately persisted
unavailable optional item, together with its persisted limitation, does not
make that required record set incomplete.

## 4. Opportunity Quality classification

An opportunity is eligible for scoring only when the required inputs and all
validations in Section 3 succeed. Classification is then deterministic:

| Quality class | Required condition |
| --- | --- |
| `QUALIFIED_COMPLETE` | A qualification exists, evidence is complete, lineage is verified, and no optional information is recorded as unavailable. |
| `QUALIFIED_LIMITED` | The opportunity is otherwise valid and qualified, but optional information is recorded as unavailable. |

For this policy, optional information is only information explicitly persisted
as unavailable or limited in the resolved Opportunity or runtime evidence and
that is not required to establish qualified status or evidence completeness.
It is never inferred from an absent artifact. This definition uses no
market-state data. `QUALIFIED_LIMITED` is a valid score, not a failure state.

## 5. Unavailable dimensions and ordered reason codes

Confidence, risk, and reward are not evaluated in this MVP. They MUST NOT
appear as `ScoreResult` components and MUST NOT have numeric values.

The scoring decision trace MUST retain these reason codes in this order after
the successful quality classification reason code:

1. `scoring.risk_unavailable`
2. `scoring.confidence_unavailable`
3. `scoring.reward_unavailable`

The complete ordered successful decision trace is:

1. `scoring.persisted_inputs_verified`
2. `scoring.qualification_verified`
3. `scoring.evidence_completeness_verified`
4. `scoring.lineage_integrity_verified`
5. exactly one of `scoring.quality_qualified_complete` or
   `scoring.quality_qualified_limited`
6. `scoring.risk_unavailable`
7. `scoring.confidence_unavailable`
8. `scoring.reward_unavailable`
9. exactly one of `scoring.composite_qualified_complete` or
   `scoring.composite_qualified_limited`

The runtime contract has no requirement for unavailable dimensions to be
represented as components. These reason codes belong to the persisted scoring
stage and audit decision trace; they are not score components.

## 6. Composite, ordering, and normalization

The composite is the ordinal Opportunity Quality mapping below:

| Opportunity Quality | Composite value |
| --- | ---: |
| `QUALIFIED_COMPLETE` | 100 |
| `QUALIFIED_LIMITED` | 50 |

Higher composite values rank first. Equal composite values are ordered by
qualification timestamp ascending. No normalization, calibration, weighting,
probability conversion, or cross-population comparison exists in version 1.

## 7. Immutable ScoreResult output

On successful evaluation, the service MUST create and persist exactly one
immutable `ScoreResult` with identity:

```text
score_id = score.runtime_ema_rsi.{qualification_id}
```

The result MUST contain exactly one available component:

| Field | Required value |
| --- | --- |
| `component_id` | `opportunity_quality` |
| `component_version` | `1.0.0` |
| `meaning` | `ordinal_opportunity_priority` |
| `raw_value`, `normalized_value`, `contribution` | 100 for `QUALIFIED_COMPLETE`; 50 for `QUALIFIED_LIMITED` |
| `weight` | 1 |
| `source_evidence` | Repository-integrity references for the qualification, opportunity, and runtime evidence |
| `normalization_reference`, `weight_reference` | `null` |
| `limitations` | Persisted optional-information limitations, if any |

The aggregate definition is `ordinal_quality_v1`, aggregate unit is
`ordinal_priority`, valid domain is inclusive `[50, 100]`, and missing-input
disposition is `unavailable_no_score_result`. The audit must use this policy
reference and preserve the validated cutoff and ordered provenance.

## 8. Fail-closed and POLICY_BLOCKED behavior

No partial, neutral, substitute, or inferred `ScoreResult` may be persisted.
The evaluator MUST complete validation and construct the whole immutable result
before its one repository persistence operation.

| Condition | Scoring stage record | Terminal pipeline outcome | Persisted score |
| --- | --- | --- | --- |
| A required repository object, integrity digest, scope, timestamp, qualification, evidence record, or validation is absent, invalid, conflicting, or unavailable at cutoff | `BLOCKED` with `scoring.input_unavailable` | `UNAVAILABLE` | None |
| Required lineage, evidence completeness, repository integrity, ordering, or contract validation fails | `BLOCKED` with `scoring.contract_unavailable` | `UNAVAILABLE` | None |
| This policy identifier, version, configuration hash, or approval is absent, invalid, or unavailable | `BLOCKED` with `scoring.policy_unavailable` | `POLICY_BLOCKED` | None |
| Score repository persistence fails | `BLOCKED` with `scoring.persistence_unavailable` | `UNAVAILABLE` | None |

An explicit optional-information unavailability is classified as
`QUALIFIED_LIMITED` only after all required validations succeed. It must never
be used to substitute for a missing required artifact or verification.

## 9. Idempotency, immutability, and repository persistence

For byte-identical persisted inputs, validated lineage, policy reference, code
version, and canonical configuration, replay MUST reconstruct byte-identical
`ScoreResult` content with the identity in Section 7. Saving that content is
idempotent. A conflicting artifact with that immutable identity MUST fail
closed and MUST NOT overwrite, update, or supersede the existing record.

The service MUST resolve and persist artifacts through the existing immutable
repositories. It MUST NOT bypass repositories, mutate upstream inputs, create
synthetic data, or perform a second write to amend the score.

## 10. Canonical configuration payload

The configuration hash above is SHA-256 of this UTF-8 canonical JSON payload:

```json
{"aggregation":{"definition":"ordinal_quality_v1","domain":{"lower":"50","upper":"100"},"mapping":{"QUALIFIED_COMPLETE":"100","QUALIFIED_LIMITED":"50"},"normalization":"none","tie_breaker":"qualification_timestamp_ascending"},"confidence":{"component":"omitted","reason_code":"scoring.confidence_unavailable"},"dependencies":{"assessment_policy":{"hash":"4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59d","id":"alphalens_runtime_assessment_ema_rsi","version":"1.0.1"},"detection_policy":{"hash":"d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a","id":"alphalens_runtime_detection_ema_rsi","version":"1.0.0"},"evidence_policy":{"hash":"9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8","id":"alphalens_runtime_evidence_ema_rsi","version":"1.0.0"},"qualification_policy":{"hash":"44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e","id":"alphalens_runtime_qualification_ema_rsi","version":"1.0.0"}},"inputs":["QualificationRecord","Opportunity","RuntimeEvidence","persisted_lineage_verification","persisted_evidence_completeness","persisted_repository_integrity"],"policy_id":"alphalens_runtime_scoring_ema_rsi","quality":{"classes":["QUALIFIED_COMPLETE","QUALIFIED_LIMITED"],"complete":"qualified_complete_evidence_and_lineage_with_no_optional_information_unavailable","limited":"otherwise_valid_qualified_opportunity_with_optional_information_unavailable"},"reward":{"component":"omitted","reason_code":"scoring.reward_unavailable"},"risk":{"component":"omitted","reason_code":"scoring.risk_unavailable"},"scope":{"instrument":"BTCUSDT","timeframe":"5m"},"version":"1.0.0"}
```
