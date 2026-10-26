# AlphaLens Batch 6N Phase 1 — Five-Feature Contract Implementation Report

Date: 2026-10-26  
Status: **ENGINEERING COMPLETE — CONTRACT-ONLY; RESEARCH NOT AUTHORIZED; DEPLOYMENT NOT AUTHORIZED**

## Scope and isolation

Implementation was performed only in this detached worktree:

```text
/private/tmp/alphalens-batch6n-phase1-five-feature-20261026
```

Baseline verification:

- commit: `948913a7e2df47b785bef655deaa4843c7589bcf`
- tree: `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`
- initial worktree: clean
- final state: uncommitted changes limited to the two implementation/test files and this report
- host free space at start: approximately 17 GiB

The original checkout remained at its existing dirty HEAD
`ac298508fc55c8c53756caf68d78ef3d48aff3e3`; its changes and untracked files
were not touched. No protected database, service, dataset, artifact, Docker,
cloud, exchange, notification, scoring, ranking, or deployment operation was
performed.

The governing Phase 0 record was independently verified at SHA-256:

```text
e975faee3c45726dfe92425aeb117042b46c4b7760824d905550721854ab3367
```

## Changed-file inventory

| File | Purpose |
|---|---|
| `backend/app/inference/btcusdt_5m_contract.py` | Contract constants, five-feature wire, schema/target envelopes and hashes, cutoff validation, float64 boundary, artifact provenance gate |
| `backend/tests/test_btcusdt_5m_contract.py` | Focused contract and negative tests |

No existing production source file, migration, historical artifact, or daily
Ridge implementation was edited.

## Implemented contract

```text
model_family: btcusdt_5m_expected_move_ridge
contract_version: 1.0.0
exchange: binance
symbol: BTCUSDT
timeframe: 5m
candle_state: closed
timezone: UTC
```

Exact ordered feature vector:

```text
average_true_range
candle_range_fraction
bollinger_band_width
rolling_standard_deviation_20
average_directional_index
```

The module binds the registered pipeline identity (`2.7.0`), registry schema
(`1.1.0`), dynamic registry hash, availability contract, Decimal quantum,
rounding rule, wire encoding, and float64 conversion type into a versioned
schema envelope. It does not reuse the historical ten-feature schema or the
existing BTC/USD/1d schema hash.

Target identity:

```text
target_name: absolute_forward_log_move
target_version: expected_move_absolute_log_move.v1.0.0
formula: abs(log(close[t+5] / close[t]))
horizon_candles: 5
horizon_minutes: 25
units: dimensionless_log_magnitude
non_negative: true
direction_semantics: not_represented; supplied only by Detection
```

Contract-only hashes in this source state:

```text
schema_hash: 03ba127a57ec783dc2cb5b6e5af15a79d38a1b51914f4b0df9a6b38e2ec5cbe0
target_hash: 14b0c2c7ca829ee014c629d95d68c251b5005b24718ad8977993152d5a510405
```

These are contract hashes, not artifact hashes and not evidence of a fitted or
approved model.

## Serialization and validation behavior

- Feature values must be finite `Decimal` instances already quantized to
  `0.000000000000000001` using `ROUND_HALF_EVEN`.
- Wire values are canonical decimal strings with the quantum's explicit scale.
- Wire items are a list in the exact approved order; missing, extra, duplicate,
  reordered, non-string, non-canonical, or non-quantized values are rejected.
- Canonical JSON uses sorted object keys, compact separators, JSON escaping,
  UTF-8 bytes, and SHA-256. List order remains semantically significant.
- Conversion to finite `float64` occurs only after the complete ordered Decimal
  vector passes validation. Overflow, NaN, infinity, invalid types, and
  unsupported coercion fail closed.
- Candle timestamps must be timezone-aware canonical UTC and aligned to 5m.
  Feature availability must equal registered candle-close availability and
  must not occur after the prediction cutoff. Incomplete candles are rejected.
- Selected-vector minimum is 28 observations; full registered pipeline pre-roll
  is 200 observations because of EMA-200. The historical 250-observation purge
  is not used as runtime warmup.

## Artifact boundary

`validate_artifact_provenance()` requires matching model family, contract
version, schema hash, target hash, explicit `approval_status == "approved"`,
payload/state hashes, and synchronized candle/feature/target/validation lineage
fields. Missing, malformed, unapproved, or mismatched artifacts are rejected.

`Btcusdt5mInferenceBoundary` only validates provenance and prepares a validated
float64 feature vector. It deliberately exposes no prediction or fitting API.
No artifact ID, approval receipt, validated lineage, model state, prediction,
score, rank, notification, or production activation was created.

## Test matrix

Focused contract command:

```text
PYTHONPATH=. ALPHALENS_ENVIRONMENT=development \
  backend/.venv/bin/pytest -q tests/test_btcusdt_5m_contract.py
```

Result: **6 passed**, exit code 0.

Focused feature/inference/regression command covered the contract, model
inference, MACD, directional movement, statistical volatility, ATR, and
Detection tests.

Result: **68 passed, 89 subtests**, exit code 0.

Complete backend suite:

```text
PYTHONPATH=. ALPHALENS_ENVIRONMENT=development \
  backend/.venv/bin/pytest -q
```

Result: **924 passed, 23 skipped, 497 subtests, 2 warnings**, exit code 0.
No test was marked passed because of a skip. Warnings were existing
Starlette/httpx deprecation and asyncpg test-cleanup warnings.

Ruff:

```text
backend/.venv/bin/ruff check app tests
```

Result: **passed**, exit code 0.

No project type checker is declared in `backend/pyproject.toml`; no additional
type-check command was available or run.

## Backward compatibility

- Existing inference artifact loading, prediction service, lineage, daily
  dataset, runtime scoring, Detection, and feature registry files were not
  edited.
- Existing model-inference, feature, and Detection tests pass in the complete
  suite.
- No migration or database write was required.
- No scoring/ranking policy, confidence interpretation, strategy threshold, or
  API response was changed.

## Remaining blockers and authorization boundaries

- No model fitting, training, research validation, or protected-test evaluation
  was performed.
- No compatible numeric model state or approved artifact exists.
- No artifact was packaged, activated, or promoted.
- No scoring, ranking, notification, trading, deployment, Gate 6, or Gate 7
  work was performed.

The contract hashes are ready for a future artifact lineage record, but they do
not authorize artifact creation. Batch 6O requires separate research execution
authorization and the frozen five-criterion protocol. Batch 6P requires an
independently approved compatible artifact.

Final status: **ENGINEERING COMPLETE (CONTRACT-ONLY); RESEARCH NOT
AUTHORIZED; ARTIFACT PROMOTION NOT AUTHORIZED; SCORING/RANKING NOT ACTIVATED;
DEPLOYMENT NOT AUTHORIZED; GATE 6 NOT VALIDATED; GATE 7 BLOCKED.**
