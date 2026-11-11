# Gate 06 volatility-feature preparation protocol — 2026-11-11

Status: **READY FOR DEVELOPMENT FITTING; no fitting performed**
Lineage: `gate06-development-20261111-volatility-v1`

This is a new development lineage. It uses only the isolated development
dataset ending `2026-09-12T10:05:00Z`; the protected period is not read.

## Feature definitions

For each completed candle `t`, let `H_i`, `L_i`, `O_i`, and `C_i` be the
positive high, low, open, and close values for the 20-candle window
`i = t-19, ..., t`. Values are interpreted as dimensionless log-return
inputs; no price-level scaling is applied.

Parkinson:

`parkinson_volatility_20[t] = sqrt(max(0, sum(log(H_i/L_i)^2) / (20*4*log(2))))`

Garman–Klass:

`garman_klass_volatility_20[t] = sqrt(max(0, sum(0.5*log(H_i/L_i)^2 - (2*log(2)-1)*log(C_i/O_i)^2) / 20))`

Both features use the square root of the nonnegative aggregated variance.
The current completed candle is included. Future candles are never read.
The first output requires exactly 20 candles; incomplete or missing windows,
nonpositive OHLC values, nonfinite values, duplicate timestamps, and
non-increasing timestamps fail closed. Results use IEEE-754 binary64
(`float`) arithmetic with deterministic operation order.

Feature names and ordering are fixed:

1. `parkinson_volatility_20`
2. `garman_klass_volatility_20`

The existing 17 production features are unchanged. These features are
research-only and are not added to production feature contracts.

## Frozen candidates

Exactly three candidates are authorized for a later development fit:

1. Existing 17-feature Ridge, `alpha=1.0`.
2. Existing 17 features plus Parkinson, Ridge `alpha=1.0`.
3. Existing 17 features plus Garman–Klass, Ridge `alpha=1.0`.

Target, ATR × 1.5 comparator, expanding chronological folds, 200-candle
feature pre-roll, five-candle label extension, 250-observation purge,
training-only scaling/selection, and all five acceptance criteria remain
unchanged. The fold schedule is fixed at minimum train 500 observations,
100 test observations, 100-observation step, 164 folds, and 16,400 test
observations per candidate. No additional features, models, horizons, or
hyperparameters are permitted.

The experiment budget is exactly three candidates and at most 492 candidate
fold fits (3 × 164). Candidate evaluation must stop after this budget; no
protected observations may be read for selection or diagnostics.

## Reproducibility and isolation

The run manifest must bind the development dataset SHA-256, source manifest
SHA-256, feature implementation hash, runner hash, this protocol hash,
dependency lock hash, candidate specifications, fold manifest, and budget.
The fold manifest is the exact schedule above, not a post-fit reconstruction.
Predictions, residuals, and checkpoints remain outside Git. No owner database,
Redis, network, protected data, model artifact, or production process may be
accessed.
