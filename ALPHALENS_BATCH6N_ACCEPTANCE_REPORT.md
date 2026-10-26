# AlphaLens Batch 6N Acceptance Report

Date: 2026-10-26  
Status: **ACCEPTED WITH TARGETED DEFECT REPAIRED**  
Scope: contract-only BTCUSDT/5m engineering

## Baseline and preservation

- Isolated worktree: `/private/tmp/alphalens-batch6n-phase1-five-feature-20261026`
- Baseline commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- Baseline tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- Original checkout remains at dirty HEAD `ac298508fc55c8c53756caf68d78ef3d48aff3e3`.
- Original checkout, evidence, services, databases, artifacts and historical resources were not modified.
- Phase 0 freeze hash verified: `e975faee3c45726dfe92425aeb117042b46c4b7760824d905550721854ab3367`.

## Contract identity verification

The implementation contains exactly five features in the approved order:

```text
average_true_range
candle_range_fraction
bollinger_band_width
rolling_standard_deviation_20
average_directional_index
```

Recomputed values match the expected contract hashes:

```text
schema: 03ba127a57ec783dc2cb5b6e5af15a79d38a1b51914f4b0df9a6b38e2ec5cbe0
target: 14b0c2c7ca829ee014c629d95d68c251b5005b24718ad8977993152d5a510405
```

The target remains `abs(log(close[t+5] / close[t]))`, dimensionless and non-negative, with direction supplied only by Detection.

## Targeted acceptance results

| Check | Result | Evidence |
|---|---|---|
| Exact five-feature order | PASS | `backend/app/inference/btcusdt_5m_contract.py:51-57` |
| Decimal quantum and rounding | PASS | Contract validation and focused tests |
| Canonical decimal-string serialization | PASS | Exact ordered list, explicit quantum scale, sorted-key compact UTF-8 JSON |
| Float64 conversion | PASS | Conversion occurs only after Decimal validation; overflow/non-finite rejection tested |
| UTC, 5m, closed-candle cutoff | PASS | `validate_closed_candle_cutoff` |
| Schema/target determinism | PASS | Recomputed hashes match expected values |
| Missing/extra/reordered features | PASS | Focused negative tests |
| Wrong schema/target/version | PASS | Artifact provenance negative tests |
| Wrong exchange/symbol/timeframe/candle state | PASS after repair | Artifact scope is required and checked at `btcusdt_5m_contract.py:309-341` |
| Missing/unapproved/mismatched artifact | PASS | Explicit approval, payload/state hashes and lineage fields required |
| Prediction/scoring/ranking/notification activation | PASS | Module exposes validation/vector preparation only; no prediction API or activation wiring |
| Daily BTC/USD/1d Ridge compatibility | PASS | Existing inference, registry, scoring and Detection files unchanged; full suite passes |
| Original checkout preservation | PASS | Original HEAD/status remain unchanged |

## Defect found and repaired

Initial acceptance identified a real D6 omission: artifact provenance validation checked model family, contract version, schema and target hashes but did not require artifact-level `exchange`, `symbol`, `timeframe`, or `candle_state`. An artifact for another market could therefore have passed the contract gate if its other fields matched.

Repair:

- Added these fields to the required artifact envelope.
- Require exact values `binance`, `BTCUSDT`, `5m`, and `closed`.
- Added a wrong-symbol rejection test.

No strategy, model, API, migration, scoring, ranking, or research behavior was changed.

## Test evidence

```text
Full backend suite: 924 passed, 23 skipped, 497 subtests, 2 warnings
Ruff: all checks passed
```

Warnings were existing Starlette/httpx deprecation and asyncpg test-cleanup warnings. Skipped tests were not counted as passes.

Changed source/test hashes after the repair:

```text
backend/app/inference/btcusdt_5m_contract.py
5edb40ea868b9d4f5d62cab5d2948754964f9ef43e6db70709878713fad16471

backend/tests/test_btcusdt_5m_contract.py
d6a7735a5d5b589bc70b2dcdd16b615c605e0e93421e46cf008fc06cbc261ae6
```

## Acceptance decision

**Batch 6N contract-only engineering: ACCEPTED.**

This acceptance does not approve or create a model artifact and does not imply predictive validity. Batch 6O remains separately controlled and requires the prospective protocol draft and explicit execution approvals. Batch 6P remains blocked until an independently approved compatible artifact exists.

Final status: **ENGINEERING ACCEPTED; RESEARCH NOT EXECUTED; GATE 6 NOT VALIDATED; GATE 7 BLOCKED; DEPLOYMENT NOT AUTHORIZED.**
