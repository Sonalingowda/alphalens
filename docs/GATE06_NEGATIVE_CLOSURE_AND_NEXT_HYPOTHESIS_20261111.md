# Gate 06 negative-result closure and next research design — 2026-11-11

## Closure

The three-candidate development budget is closed. The private result archive
and checkpoint are retained with the hashes recorded in
`GATE06_FINAL_DEVELOPMENT_RESULT_20261111.md`. No refit, retuning, protected
read, or candidate substitution is permitted under that lineage.

All candidates completed 164 folds and 16,400 observations. Every candidate
failed the mandatory correlation improvement criterion. RandomForest 400/depth
6 also failed the MAE criterion. The negative result is not a Gate 06
validation and no artifact is nominated.

## Evidence-based interpretation

The models consistently improved MAE and R² and passed calibration and both
30-day regime checks, while correlation improvement remained near zero or
negative. This supports a bounded hypothesis that the existing features carry
some conditional-magnitude information but insufficient incremental ranking
information relative to the ATR × 1.5 comparator. It does not prove that a
different feature family will pass.

## Proposed next hypothesis — point-in-time volatility representation

Hypothesis: a small, predeclared set of point-in-time range-volatility
features may improve ordering of five-candle absolute moves beyond the current
17-feature representation, without changing the target or comparator.

This is a new research lineage and requires separate approval before fitting.

### Frozen design

- Source: the same verified development artifact and cutoff ending
  `2026-09-12T10:05:00Z`; no protected rows.
- Target: unchanged `abs(log(close[t+5] / close[t]))`.
- Comparator: unchanged ATR × 1.5 converted using the observation close.
- Chronology: unchanged expanding folds, 200-candle pre-roll, five-candle
  label extension, and 250-observation purge.
- Metrics: unchanged five mandatory acceptance criteria.
- Candidate budget: exactly three predeclared candidates maximum.

Candidates:

1. Existing 17-feature Ridge α=1.0 baseline.
2. Baseline plus one 20-candle Parkinson range-volatility feature, computed
   from completed candles through `t` only.
3. Baseline plus one 20-candle Garman–Klass range-volatility feature, computed
   from completed OHLC candles through `t` only.

The formulas, feature names, ordering, decimal handling, missing-window
behavior, scaling, and training-fold feature selection must be frozen in the
run manifest before fitting. No additional volatility features, horizons,
models, transformations, or hyperparameter searches are allowed.

### Rejection conditions

Each candidate is rejected if any mandatory criterion fails, if any feature
uses data after `t`, if any required window is incomplete, if any nonfinite
value is silently substituted, or if source/protocol/code/dependency hashes do
not match the run manifest. A development pass would only nominate a
candidate; protected evaluation and artifact approval remain separate.

## Gate status

- Gate 06: NOT VALIDATED; negative development result closed.
- Gate 07: BLOCKED pending validated model artifact; model-unavailable behavior
  remains fail-closed.
- Gate 08: preparation remains partial; no production deployment or external
  staging evidence.
- Gate 09: preparation remains blocked pending mandatory gates and owner signoff.

No production data, owner database, Redis state, trading process, continuous
ingestion, protected test, or model artifact was changed.
