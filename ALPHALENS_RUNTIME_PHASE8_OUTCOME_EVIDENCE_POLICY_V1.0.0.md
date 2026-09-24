# AlphaLens Phase 8 Outcome Evidence Policy v1.0.0

**Policy identifier:** `alphalens_phase8_outcome_evidence`
**Policy version:** `1.0.0`
**Status:** Pending explicit human approval
**Scope:** `BTCUSDT`, `5m`, real production OutcomeRecords only
**Canonical hash:** `3562a18bd9a9414e9a2d691833a414f4c8ce14fef5ba6956017989ec09a9b012`

This is a new Phase 8 governance artifact. Historical outcome, labeling,
lifecycle, scoring, ranking, and runtime policies remain unchanged.

## 1. Production provenance and integrity

An OutcomeRecord is accepted as Phase 8 evidence only when all of the
following are present and mutually consistent:

1. A unique real production opportunity and matching OpportunityPlan.
2. Matching lifecycle identity and version.
3. Signal timestamp and `valid_until`.
4. A persisted lifecycle resolution event.
5. A real Binance BTCUSDT 5m candle reference.
6. A deterministic outcome policy identifier, version, and hash.
7. An immutable result hash.
8. Resolution after the relevant observation window.
9. A reconstructible chain:
   `opportunity → plan → lifecycle → candle → outcome`.

Synthetic, replay, test-fixture, manually inserted, or unverifiable records
are not production evidence.

## 2. Approved lifecycle/outcome evidence scope

The following branches are included in this policy and each requires direct
real production evidence:

- `EXPIRED_BEFORE_ENTRY`;
- `EXPIRED_AFTER_ENTRY`;
- `TARGET_HIT`; and
- `DATA_INSUFFICIENT`.

Post-entry behavior is in scope. At least one real resolution with
`entry_reached = true` is required. Target resolution is in scope. At least
one naturally occurring real `TARGET_HIT` is required.

In the Phase 8 baseline audit, `STOP_HIT` was unobserved and is not a Phase 8
completion requirement. A zero count is neither a pass nor a fail. Any claim
about stop-hit or invalidation behavior requires explicit reporting and an
approved scope change or separate policy; later naturally observed records do
not retroactively change the baseline audit.

## 3. DATA_INSUFFICIENT treatment

`DATA_INSUFFICIENT` remains a separately reported outcome. It is not success or
failure evidence, must not be silently discarded, and must not be converted to
`TARGET_HIT`, `STOP_HIT`, or another terminal outcome. For any future
statistical analysis it must be handled under an explicitly approved
censoring/missingness rule.

## 4. Statistical boundary

This policy introduces no numeric sample-size gate. OutcomeRecord counts prove
operational evidence and branch execution only; they do not establish
statistical sufficiency.

Any future predictive or statistical claim requires a separately approved
specification containing, at minimum:

- estimand;
- denominator;
- censoring rule;
- dependence unit;
- uncertainty method;
- adequacy target; and
- acceptance rule.

## 5. Explicit limitations

Phase 8 OutcomeRecords do not, by themselves, establish:

- predictive performance;
- profitability;
- ranking quality;
- calibration;
- execution feasibility; or
- statistical sufficiency.

Unobserved branches and all evidence limitations must be reported explicitly.

## 6. Completion condition

Phase 8 Outcome Evidence may be declared complete only after:

1. This versioned policy has explicit human approval and is frozen.
2. Every record claimed as evidence passes the provenance and integrity rules.
3. Every branch included in the approved scope has direct real production
   evidence.
4. `DATA_INSUFFICIENT` remains separately reported.
5. Entry-before-resolution evidence is present.
6. Target-hit evidence is present.
7. Unobserved branches and limitations are recorded.

Until explicit human approval is recorded, this policy is pending approval and
Phase 8 is not complete.

## 7. Phase 8 audit baseline

Read-only audit result for the Phase 8 baseline set, defined as real production
BTCUSDT 5m OutcomeRecords with signal timestamps through
`2026-09-24T13:25:00.054Z`:

| Outcome | Count |
| --- | ---: |
| `EXPIRED_BEFORE_ENTRY` | 31 |
| `EXPIRED_AFTER_ENTRY` | 16 |
| `DATA_INSUFFICIENT` | 13 |
| `TARGET_HIT` | 1 |
| `STOP_HIT` | 0 |
| **Total unique OutcomeRecords** | **61** |

All 61 baseline records were reported as having real production Opportunity and
OpportunityPlan linkage, persisted lifecycle resolution, real Binance market
snapshot provenance, deterministic outcome policy/version, immutable result
hashes, and reconstructible provenance. The audit is evidence only; it does
not itself grant policy approval.

## 8. Canonical hash input

The canonical hash is SHA-256 of the following compact, sorted-key UTF-8 JSON
object, using the repository's
`app.opportunity_intelligence.domain.canonical_sha256` convention. The
`canonical_hash` field is excluded because it is not part of the input.

```json
{"completion":{"all_claimed_records_pass_integrity":true,"all_in_scope_branches_have_real_evidence":true,"data_insufficient_separately_reported":true,"explicit_limitations_recorded":true,"human_approval_required":true,"unobserved_branches_recorded":true},"data_insufficient":{"counts_as_success_or_failure":false,"separately_reported":true,"silently_discarded":false},"governance":{"hash_algorithm":"SHA-256","hash_convention":"app.opportunity_intelligence.domain.canonical_sha256","hash_excludes":["canonical_hash"],"serialization":"sorted-key compact UTF-8 JSON"},"lifecycle_path_scope":{"entry_before_resolution_required":true,"included_branches":["DATA_INSUFFICIENT","EXPIRED_AFTER_ENTRY","EXPIRED_BEFORE_ENTRY","TARGET_HIT"],"real_evidence_required_per_included_branch":true,"stop_hit_required":false,"target_hit_required":true,"unobserved_branches":["STOP_HIT"]},"limitations":["does_not_establish_execution_feasibility","does_not_establish_predictive_performance","does_not_establish_profitability","does_not_establish_ranking_quality","does_not_establish_statistical_sufficiency","does_not_establish_calibration"],"policy_id":"alphalens_phase8_outcome_evidence","production_provenance":{"candle_source":"Binance","immutable_result_hash":true,"matching_lifecycle_identity_version":true,"matching_opportunity_plan":true,"outcome_policy_version_hash":true,"persisted_lifecycle_resolution":true,"real_production_opportunity":true,"real_production_plan":true,"reconstructible_chain":["opportunity","plan","lifecycle","candle","outcome"],"resolution_after_relevant_observation_window":true,"scope":"BTCUSDT","signal_timestamp":true,"timeframe":"5m","valid_until":true},"statistical_claims":{"numeric_sample_size_gate":false,"required_specification":["estimand","denominator","censoring","dependence_unit","uncertainty_method","adequacy_target","acceptance_rule"],"separate_approval_required":true},"status":"pending_human_approval","version":"1.0.0"}
```

## 9. Governance basis

This policy applies the existing requirements in the Lifecycle Contract,
Production Readiness Validation Criteria, Statistical Validation Framework,
Performance Metrics Validation Framework, and Core Intelligence Specification.
Those documents establish provenance, immutability, censoring/missingness,
predeclared acceptance, and integrity boundaries; they do not define a numeric
Phase 8 OutcomeRecord sample-size requirement.
