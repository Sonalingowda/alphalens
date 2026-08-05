# AlphaLens Runtime Evidence Policy v1.0

**Policy identifier:** `alphalens_runtime_evidence_ema_rsi`  
**Policy version:** `1.0.0`  
**Status:** Approved and frozen  
**Approval date:** 2026-08-04  
**Approval authority:** AlphaLens project owner, POLICY-002  
**Scope:** `BTCUSDT` spot, `5m` timeframe  
**Taxonomy version:** `1.0.0`  
**Policy hash:** `9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8`

This immutable policy defines deterministic factual evidence assembly only. It
does not define confidence, scoring, qualification, ranking, AI reasoning, or
trading behavior. Any semantic or source change requires a new version and
explicit approval.

## 1. Required candidate input

The input MUST be an immutable `OpportunityCandidate` produced under
`alphalens_runtime_detection_ema_rsi` version `1.0.0` with policy hash
`d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a`.

It MUST have scope `BTCUSDT` / `5m`, a valid identity, ordered reason codes,
market/feature/context references, evidence cutoff, availability, provenance,
and integrity digests. References MUST be resolved through repositories and
byte-equivalently verified; caller-supplied copies are never trusted.

## 2. Required persisted inputs

The service MUST resolve exactly one complete persisted `MarketSnapshot` with
one 5-minute candle, the compatible referenced `FeatureSnapshot`, and the
referenced `MarketContext` produced by `RuntimeMarketContextService`.

The market and feature snapshots MUST match candidate references by identity and
digest. The context MUST match its reference and carry the market and feature
references in provenance. No network response, reconstructed candle, inferred
value, or unpersisted object may be used.

The context MUST have scope `BTCUSDT` / `5m`, `context_timeframes=("5m",)`,
and an `AVAILABLE` data-quality component containing the Boolean observation
`data_quality.persisted_inputs_verified=true` for the evaluated candle.
Trend, momentum, volatility, structure, and session components remain explicit
`UNAVAILABLE`; their absence is never converted into a neutral value.

The feature snapshot MUST contain exactly one value for each triple below at
the evaluated candle timestamp:

| Feature identifier | Definition version | Output name |
| --- | --- | --- |
| `exponential_moving_average_12` | `1.0.0` | `exponential_moving_average_12` |
| `exponential_moving_average_26` | `1.0.0` | `exponential_moving_average_26` |
| `relative_strength_index` | `1.0.0` | `relative_strength_index` |
| `average_true_range` | `1.0.0` | `true_range` |

Values MUST be finite, canonical at 18-decimal precision, causally available,
and backed by immutable feature-record references.

## 3. Identity, lineage, and timestamps

Package identity MUST be:

```text
evidence.runtime.ema_rsi.{candidate_id}
```

Item identity MUST be:

```text
evidence.runtime.ema_rsi.{candidate_id}.{record_key}
```

`record_key` is defined in Section 5. Identical source artifacts, candidate,
policy, and code version MUST replay byte-identically; conflicting immutable
identity MUST fail closed.

Package provenance MUST include, in order, candidate, market snapshot, feature
snapshot, market context, and this policy references. Each item source
reference MUST identify the artifact supplying its observed value.

The evidence cutoff is the candidate cutoff. Every source, feature, context
observation, and policy reference MUST be available no later than that cutoff.
Every item uses the candle timestamp for `time_start` and `time_end`.
`available_at` is persisted source availability and MUST not precede the time
scope or exceed the cutoff. No wall-clock timeout, forward fill, interpolation,
or retrospective correction is allowed.

## 4. Required package and item fields

The package MUST use `EvidencePackage` with `assessment_id=null`, non-empty
ordered items, immutable audit metadata, and package limitation
`confidence.unavailable`.

Every `EvidenceItem` MUST populate taxonomy version, identity, evidence type,
category, description code, exact source reference and definition, polarity,
proposition, informational severity, typed observed value, unit where relevant,
scope, time range, availability, limitations, and canonical integrity digest.

## 5. Deterministic evidence records

The service MUST create one record for each key below. Values are copied from
persisted sources unless explicitly marked unavailable.

| Record key | Category | Source definition | Observed value | Polarity |
| --- | --- | --- | --- | --- |
| `market_price_close` | `MARKET_PRICE` | `market_snapshot.candle.close` | persisted close Decimal | `CONTEXTUAL` |
| `market_volume` | `MARKET_VOLUME` | `market_snapshot.candle.volume` | persisted volume Decimal | `CONTEXTUAL` |
| `ema_12` | `FEATURE_TREND` | `exponential_moving_average_12:1.0.0:exponential_moving_average_12` | persisted EMA-12 Decimal | `CONTEXTUAL` |
| `ema_26` | `FEATURE_TREND` | `exponential_moving_average_26:1.0.0:exponential_moving_average_26` | persisted EMA-26 Decimal | `CONTEXTUAL` |
| `rsi` | `FEATURE_MOMENTUM` | `relative_strength_index:1.0.0:relative_strength_index` | persisted RSI Decimal | `CONTEXTUAL` |
| `atr_true_range` | `FEATURE_VOLATILITY` | `average_true_range:1.0.0:true_range` | persisted true-range Decimal | `CONTEXTUAL` |
| `ema_alignment` | `POLICY_TRACE` | detection policy v1.0.0 | Boolean approved EMA-direction trace | `CONTEXTUAL` |
| `rsi_state` | `POLICY_TRACE` | detection policy v1.0.0 | `buy_threshold_met`, `sell_threshold_met`, or `threshold_not_met` | `CONTEXTUAL` |
| `market_structure` | `CONTEXT_STRUCTURE` | `market_context.structure` | `unavailable` | `CONTEXTUAL` |

The structure item MUST carry limitation `context.structure.unavailable` and
does not represent fabricated structure. Policy-trace items are deterministic
projections of candidate reason codes and persisted values; they add no new
predicate, threshold, score, or recommendation.

No forecast, confidence, score, qualification, ranking, plan, or AI-reasoning
evidence may be emitted. Confidence is always `UNAVAILABLE`, represented by
the package limitation above.

## 6. Missing-input and fail-closed behavior

Missing or duplicate candidate references, source artifacts, feature values,
context observations, policy metadata, provenance, or canonical digests MUST
produce no `EvidencePackage`; the service MUST return an explicit unavailable
or contract failure and never substitute a neutral value. The unavailable
structure item is the sole allowed absence because this policy explicitly
defines it.

Repository failures MUST propagate. Scope, timestamp, definition-version,
taxonomy-version, candidate-policy-hash, evidence-policy-hash, or canonical
serialization failures MUST fail closed. No partial package or item set may be
persisted.

## 7. Policy metadata and versioning

The evidence policy reference is:

```text
policy_id      = alphalens_runtime_evidence_ema_rsi
policy_version = 1.0.0
policy_hash    = 9159b3d43cbfeafdbe11f0a9e748119f5ddbac762e2bb89c62fd937dacd913c8
```

Any change affecting identity, source meaning, fields, categories, polarity,
severity, limitations, freshness, missingness, or hash requires a new major
version and approval. Historical evidence packages remain immutable.

The policy hash is SHA-256 of this compact, sorted-key JSON configuration:

```json
{"candidate_policy":{"hash":"d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a","id":"alphalens_runtime_detection_ema_rsi","version":"1.0.0"},"freshness":"all_sources_available_at_or_before_evidence_cutoff","missing_input":"unavailable_no_package","policy_id":"alphalens_runtime_evidence_ema_rsi","required_features":[["exponential_moving_average_12","1.0.0","exponential_moving_average_12"],["exponential_moving_average_26","1.0.0","exponential_moving_average_26"],["relative_strength_index","1.0.0","relative_strength_index"],["average_true_range","1.0.0","true_range"]],"required_records":["market_price_close","market_volume","ema_12","ema_26","rsi","atr_true_range","ema_alignment","rsi_state","market_structure_unavailable","confidence_unavailable"],"scope":{"instrument":"BTCUSDT","timeframe":"5m"},"taxonomy_version":"1.0.0","version":"1.0.0"}
```
