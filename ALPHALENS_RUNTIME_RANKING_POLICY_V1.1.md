# AlphaLens Runtime Ranking Policy v1.1

**Policy identifier:** `alphalens_runtime_ranking_ema_rsi`
**Policy version:** `1.1.0`
**Status:** Approved production ranking policy
**Scope:** `BTCUSDT`, `5m`
**Canonical hash:** `9a2e4c60da1f0b80dad6de944acd3092b06f9ef6c158a48b30b356827aecd294`

This ranking revision records the dependency on the approved continuous
Scoring V1.1 policy. The ranking threshold remains exactly `55`; no admission
policy relaxation is made. The prior ranking V1.0 document remains available
as audit history.

Ranking accepts only persisted `ScoreResult` values whose exact scoring policy
reference is `alphalens_runtime_scoring_ema_rsi` version `1.1.0`, hash
`825ee3c060b4badc6d3348d1731dfd0683f46a4ad12f420a5e751e040cbca81b`, whose
`opportunity_quality` value is in the inclusive domain `[50, 100]`. Values
below `55` are excluded with `ranking.below_quality_threshold`; values at or
above `55` may enter membership. Ordering remains composite value descending,
qualification timestamp ascending, then score ID lexicographically. The
population is a rolling 15-minute window, and empty populations persist a
valid empty snapshot.

The canonical hash is SHA-256 of the compact sorted-key UTF-8 JSON payload
below, using the repository's `canonical_sha256` convention:

```json
{"admission":{"comparison":"greater_than_or_equal","minimum_quality_score":"55"},"composite_domain":{"lower":"50","upper":"100"},"conflict_behavior":"fail_closed_no_overwrite","dependencies":{"assessment_policy":{"hash":"4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59","id":"alphalens_runtime_assessment_ema_rsi","version":"1.0.1"},"detection_policy":{"hash":"d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a","id":"alphalens_runtime_detection_ema_rsi","version":"1.0.0"},"evidence_policy":{"hash":"9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8","id":"alphalens_runtime_evidence_ema_rsi","version":"1.0.0"},"qualification_policy":{"hash":"44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e","id":"alphalens_runtime_qualification_ema_rsi","version":"1.0.0"},"scoring_policy":{"hash":"825ee3c060b4badc6d3348d1731dfd0683f46a4ad12f420a5e751e040cbca81b","id":"alphalens_runtime_scoring_ema_rsi","version":"1.1.0"}},"empty_population_behavior":"valid_empty_snapshot_persist_ranking_snapshot","freshness":"all_members_available_at_or_before_ranking_cutoff","idempotency":"byte_identical_replay_no_op","identity_template":"ranking.runtime_ema_rsi.{instrument}.{timeframe}.{ranking_cutoff_epoch_ms}","missing_input":"unavailable_no_snapshot","ordering":{"primary":{"direction":"descending","key":"composite_value"},"secondary":{"direction":"ascending","key":"qualification_timestamp"},"tiebreaker":{"direction":"ascending","key":"score_id","method":"lexicographic"}},"policy_id":"alphalens_runtime_ranking_ema_rsi","population_window":{"instrument":"BTCUSDT","timeframe":"5m","type":"rolling","window_minutes":15},"rank_assignment":"dense_integer_from_1","required_inputs":["ScoreResult[]","QualificationRecord[]","Opportunity[]"],"scope":{"instrument":"BTCUSDT","timeframe":"5m"},"version":"1.1.0"}
```
