# AlphaLens Runtime Scoring Policy v1.1

**Policy identifier:** `alphalens_runtime_scoring_ema_rsi`
**Policy version:** `1.1.0`
**Status:** Approved production scoring policy
**Scope:** `BTCUSDT`, `5m`
**Canonical hash:** `825ee3c060b4badc6d3348d1731dfd0683f46a4ad12f420a5e751e040cbca81b`

This document is the authoritative executable-policy definition for the
continuous scoring implementation. The prior `ALPHALENS_RUNTIME_SCORING_POLICY_V1.md`
remains an immutable V1.0 audit artifact and is not an active production policy.

## Deterministic contract

The scorer uses only persisted inputs available at the qualification evidence
cutoff. Required evidence is `market_price_close`, `market_volume`, `ema_12`,
`ema_26`, `rsi`, `atr_true_range`, `ema_alignment`, `rsi_state`, and
`market_structure`. The persisted feature snapshot is required and supplies
`average_directional_index`, `macd_histogram`, and `bollinger_band_width` when
available.

For a BUY opportunity, `rsi_excess = max(0, rsi - 55)`; for a SELL,
`rsi_excess = max(0, 45 - rsi)`. Other stances produce quality `50`.

```text
ema_spread_bps = abs(ema_12 - ema_26) / ema_26 * 10000
signal_strength = rsi_excess * (1 + ema_spread_bps / 10000)
signal_score = clamp(signal_strength / 25, 0, 1)

atr_pct = atr_true_range / market_price_close, or 0 when price <= 0
volatility_score = clamp(atr_pct / 0.005, 0, 1)

adx_component = clamp(average_directional_index / 50, 0, 1)
macd_component = clamp(abs(macd_histogram) / atr_true_range, 0, 1)
bollinger_component = clamp(bollinger_band_width * 100, 0, 1)

trend_bonus = clamp(
    adx_component + macd_component + bollinger_component,
    0.5,
    1.5,
)

quality = 50 + 50 * clamp(
    signal_score * volatility_score * trend_bonus,
    0,
    1,
)
```

Missing optional feature values use the neutral component value `0.5`:
ADX unavailable → `adx_component = 0.5`; MACD unavailable or non-positive ATR
→ `macd_component = 0.5`; Bollinger width unavailable →
`bollinger_component = 0.5`. Their existing `.unavailable` limitation is
retained. Missing or unavailable required persisted inputs produces no
`ScoreResult` (`unavailable_no_score_result`). The optional dimension
limitations are retained as `scoring.risk_unavailable`,
`scoring.confidence_unavailable`, and `scoring.reward_unavailable`.

The final value is quantized with `Decimal.quantize(Decimal("1"))` using the
repository's deterministic `ROUND_HALF_EVEN` decimal convention. The valid
inclusive score domain is `[50, 100]`, represented as an integer-valued
`Decimal`. The persisted component is `opportunity_quality`, version `1.0.0`,
with weight `1`, contribution equal to the quantized quality, aggregation
definition `ordinal_quality_v1`, and unit `ordinal_priority`.

Ranking consumes this exact policy reference and admits values at or above the
unchanged minimum quality threshold `55`; it does not change the scoring
formula or manufacture membership.

## Dependencies and provenance

The policy requires the current assessment policy `1.0.1` hash
`4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59`, evidence
policy `1.0.0` hash
`9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8`, and
qualification policy `1.0.0` hash
`44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e`.
The score retains the opportunity, qualification, evidence, market context,
feature snapshot, code version, cutoff, and lineage references.

## Canonical hash input

The canonical hash is SHA-256 of the following compact, sorted-key UTF-8 JSON
object, using the repository's `canonical_sha256` convention. The `hash` field
is intentionally not part of the input; the value above is the digest of this
object exactly.

```json
{"aggregation":{"formula":"50 + 50 * clamp(signal_score * volatility_score * trend_bonus, 0, 1)","quantization":{"method":"Decimal.quantize(Decimal(\"1\"))","result_type":"integer-valued Decimal","rounding":"ROUND_HALF_EVEN"},"valid_domain":{"lower":"50","upper":"100"}},"components":{"signal_score":{"ema_spread_bps":"abs(ema_12 - ema_26) / ema_26 * 10000","formula":"clamp(signal_strength / 25, 0, 1)","rsi_excess":{"BUY":"max(0, rsi - 55)","SELL":"max(0, 45 - rsi)","other_stance":"0"},"signal_strength":"rsi_excess * (1 + ema_spread_bps / 10000)"},"trend_bonus":{"adx_component":"clamp(average_directional_index / 50, 0, 1); unavailable = 0.5","bollinger_component":"clamp(bollinger_band_width * 100, 0, 1); unavailable = 0.5","formula":"clamp(adx_component + macd_component + bollinger_component, 0.5, 1.5)","macd_component":"clamp(abs(macd_histogram) / atr_true_range, 0, 1); unavailable or non_positive_atr = 0.5"},"volatility_score":{"atr_pct":"atr_true_range / market_price_close","formula":"clamp(atr_pct / 0.005, 0, 1)","non_positive_price":"atr_pct = 0"}},"dependencies":{"assessment_policy":{"hash":"4a2c6c906097b31e2fe42f4d6fd52ef969a2d8c40513e594d4f3b8b23319a59","id":"alphalens_runtime_assessment_ema_rsi","version":"1.0.1"},"evidence_policy":{"hash":"9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8","id":"alphalens_runtime_evidence_ema_rsi","version":"1.0.0"},"qualification_policy":{"hash":"44ab0f80572ed66620ded65cdff3a85ba6cf83287e96e08ebd806301b968bd2e","id":"alphalens_runtime_qualification_ema_rsi","version":"1.0.0"}},"inputs":{"cutoff":"qualification.audit.evidence_cutoff","feature_snapshot_required":true,"no_future_data":true,"optional_features":["average_directional_index","macd_histogram","bollinger_band_width"],"required_evidence":["market_price_close","market_volume","ema_12","ema_26","rsi","atr_true_range","ema_alignment","rsi_state","market_structure"]},"missing_input_behavior":{"optional_dimensions":["scoring.risk_unavailable","scoring.confidence_unavailable","scoring.reward_unavailable"],"optional_feature":"use neutral component value 0.5 and retain *.unavailable limitation when present","required":"no ScoreResult; unavailable_no_score_result"},"policy_id":"alphalens_runtime_scoring_ema_rsi","ranking_relationship":{"accepted_score_domain":["50","100"],"admission_threshold":"55","ranking_must_reference_exact_policy":true},"scope":{"instrument":"BTCUSDT","timeframe":"5m"},"status":"approved_production","version":"1.1.0"}
```
