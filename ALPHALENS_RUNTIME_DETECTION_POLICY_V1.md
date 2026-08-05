# AlphaLens Runtime Detection Policy v1.0

**Policy identifier:** `alphalens_runtime_detection_ema_rsi`

**Policy version:** `1.0.0`

**Policy status:** Approved and frozen

**Approval date:** 2026-08-04

**Approval authority:** AlphaLens project owner, POLICY-001

**Artifact type:** Immutable executable runtime detection policy

**Scope:** `BTCUSDT` spot market, `5m` timeframe only

**Configuration hash algorithm:** SHA-256

**Configuration hash:**
`d1ae27b11d710b5491394db3d144dbe6e71dfae254ae5b7bc2767d7417ddfb8a`

This document is the complete policy artifact for the stated identifier and
version. It is immutable. Any change to scope, inputs, predicates, thresholds,
reason codes, identity, freshness, missing-data handling, or hashing requires a
new policy version and a new explicit approval.

---

## 1. Purpose

This policy determines whether one persisted `BTCUSDT` 5-minute market state is
eligible to become an `OpportunityCandidate` for later assessment. It does not
produce an opportunity stance, assessment, score, rank, plan, notification, or
trading instruction.

The terms BUY and SELL below name directional detection conditions only. A
detected candidate has no stance.

## 2. Required persisted inputs

Evaluation MUST consume exactly these immutable repository-backed objects:

1. One complete `MarketSnapshot` with scope `BTCUSDT` / `5m` and exactly one
   completed candle.
2. One `FeatureSnapshot` with the identical scope whose
   `market_snapshot.artifact_id` and integrity digest reference that exact
   persisted `MarketSnapshot`.
3. One `MarketContext` produced by `RuntimeMarketContextService` with the
   identical scope and provenance references to that exact persisted market and
   feature snapshot.

The evaluator MUST retrieve and verify all three objects through their existing
repositories. Supplied in-memory objects that do not byte-equivalently match
their persisted identities MUST be rejected as unavailable.

## 3. Required context and feature fields

The required `MarketContext` fields are:

- `scope = BTCUSDT / 5m`;
- `context_timeframes = ("5m",)`;
- `data_quality.status = AVAILABLE`;
- exactly one data-quality observation with semantic identifier
  `data_quality.persisted_inputs_verified` and Boolean value `true`; and
- provenance references for the evaluated market and feature snapshots.

Trend, momentum, volatility, structure, and session context components are not
inputs to this policy. Their status MUST be `UNAVAILABLE`; an available value is
not silently consumed by this version.

The required `FeatureSnapshotValue` records are the following exact triples,
all for the evaluated market candle timestamp and available no later than the
evaluation cutoff:

| Feature identifier | Definition version | Output name |
| --- | --- | --- |
| `exponential_moving_average_12` | `1.0.0` | `exponential_moving_average_12` |
| `exponential_moving_average_26` | `1.0.0` | `exponential_moving_average_26` |
| `relative_strength_index` | `1.0.0` | `relative_strength_index` |

Each required record MUST be unique, finite, and canonical at the repository
contract's 18-decimal precision.

## 4. Freshness and chronology

The evaluation cutoff is the maximum `available_at` timestamp across the three
required immutable inputs. Every consumed reference and feature value MUST be
available at or before that cutoff.

The feature snapshot and context MUST refer to the exact persisted market
snapshot being evaluated. The market candle timestamp, every required feature
value timestamp, and the context data-quality observation time range MUST all
identify that candle. Any mismatch, future availability, incomplete candle,
scope mismatch, conflicting immutable identity, or missing provenance makes the
evaluation unavailable.

This policy defines no wall-clock timeout. Freshness is exclusively exact input
lineage plus causal availability at the evaluation cutoff.

## 5. Deterministic detection conditions

Let `EMA12`, `EMA26`, and `RSI` be the three required persisted feature values.
All comparisons are exact Decimal comparisons at their persisted canonical
precision.

A BUY-direction candidate condition is satisfied exactly when:

```text
EMA12 > EMA26
AND RSI >= 55.000000000000000000
```

A SELL-direction candidate condition is satisfied exactly when:

```text
EMA12 < EMA26
AND RSI <= 45.000000000000000000
```

The two conditions are mutually exclusive. Equality of `EMA12` and `EMA26`,
or an RSI value strictly between `45.000000000000000000` and
`55.000000000000000000`, does not qualify.

## 6. Candidate and no-candidate behavior

When exactly one directional condition is satisfied, the evaluator MUST create
one immutable candidate and one `DETECTED` attempt. The candidate MUST contain
the market, feature, and context references; all three references as ordered
evidence; the active policy reference; and the mapped reason codes in the order
below.

Candidate identity is exactly:

```text
candidate.runtime_detection_ema_rsi.{instrument}.{timeframe}.{market_candle_timestamp_epoch_ms}
```

where `{instrument}` is `BTCUSDT`, `{timeframe}` is `5m`, and
`{market_candle_timestamp_epoch_ms}` is the evaluated candle's UTC open
timestamp in epoch milliseconds. Replays with byte-identical content are
idempotent; conflicting content for that identity MUST fail closed.

When all required inputs are valid and neither directional condition is
satisfied, the evaluator MUST persist one `NOT_DETECTED` attempt with no
candidate and reason code `detection.conditions_not_met`. It MUST not raise an
error and MUST not create an `OpportunityCandidate`.

## 7. Reason-code mapping

| Result | Ordered reason codes |
| --- | --- |
| BUY-direction detected candidate | `detection.persisted_inputs_verified`, `detection.ema12_above_ema26`, `detection.rsi_ge_55` |
| SELL-direction detected candidate | `detection.persisted_inputs_verified`, `detection.ema12_below_ema26`, `detection.rsi_le_45` |
| Valid no-candidate result | `detection.conditions_not_met` |
| Required input absent, invalid, unverified, stale, or causally unavailable | `detection.input_unavailable` |
| Policy identity, version, or hash mismatch | `detection.policy_unavailable` |

## 8. Missing data and fail-closed behavior

No value may be inferred, substituted, carried forward, rounded differently,
or reconstructed outside the persisted snapshots. Missing, duplicate, invalid,
non-finite, incompatible, or future-unavailable required input yields one
`UNAVAILABLE` attempt with no candidate, using the applicable unavailable
reason code. Repository read or write failures MUST propagate as failures and
MUST NOT be reclassified as no-candidate results.

No candidate may be emitted if the active policy identifier, version, or
configuration hash differs from this document.

## 9. Canonical configuration payload

The configuration hash above is SHA-256 of this UTF-8 canonical JSON payload:

```json
{"candidate_identity":"candidate.runtime_detection_ema_rsi.{instrument}.{timeframe}.{market_candle_timestamp_epoch_ms}","conditions":{"buy":{"ema_12":"greater_than_ema_26","rsi":"greater_than_or_equal_to:55.000000000000000000"},"sell":{"ema_12":"less_than_ema_26","rsi":"less_than_or_equal_to:45.000000000000000000"}},"context":{"data_quality":"persisted_inputs_verified:true"},"feature_requirements":[["exponential_moving_average_12","1.0.0","exponential_moving_average_12"],["exponential_moving_average_26","1.0.0","exponential_moving_average_26"],["relative_strength_index","1.0.0","relative_strength_index"]],"freshness":"exact_input_lineage_and_available_at_lte_cutoff","missing_data":"unavailable","policy_id":"alphalens_runtime_detection_ema_rsi","scope":{"instrument":"BTCUSDT","timeframe":"5m"},"version":"1.0.0"}
```
