# Gate 06 development protocol — 2026-11-11

Status: **frozen for one bounded development cycle**
Lineage: `gate06-development-20261111-v1`

This protocol is development-only. It cannot certify Gate 06, access a
protected test, create or activate an inference artifact, or write to the
owner database.

## Source and provenance

The permitted source is the retained local Binance-shaped artifact:

`/Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json`

Its complete-file SHA-256 is
`f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`.
The source declares `BTCUSDT`, `5m`, and 25,920 candles. The run is
offline-only: no Binance request, owner database connection, Redis connection,
or protected-test mount is permitted.

The current source spans `2026-07-14T10:10:00Z` through
`2026-10-12T10:05:00Z`. The historical result artifact recovered from Git
records `2026-05-22T18:50:00Z` through `2026-08-20T18:45:00Z` and timestamp hash
`528bb245713f4ae7b60397d05c2875e41f96a68dd0cf0c8b3e68e6e82dba70b3`. Therefore
the current source cannot be treated as the exact original research input,
despite having the same documented file hash. This cycle uses a new lineage
and reports the discrepancy rather than overwriting either identity.

## Frozen protocol

- Target: `abs(log(close[t+5] / close[t]))`; horizon: five closed 5m candles.
- Features: the existing 17-feature intraday pipeline, with no feature
  definition or ordering changes.
- Chronology: expanding walk-forward folds; minimum train 500, test 100,
  step 100, purge 250 observations.
- Feature selection: training-fold data only, maximum 10 features, correlation
  ranking with the existing multicollinearity rule.
- Scaling and fitting: `StandardScaler` fit only on each training fold;
  Ridge with candidate-specific alpha; no random state is used.
- Comparator: ATR × 1.5 converted to log-return units using the observation's
  close price. No fallback price is permitted in this cycle.
- Calibration: five predicted-value quintiles, evaluated on development fold
  predictions only.
- Regimes: the existing 30-day chronological regime grouping.
- Protected test: unavailable and untouched.

## Bounded experiment budget

The baseline is Ridge alpha `1.0`. At most two predeclared candidates may be
run: Ridge alpha `0.1` and Ridge alpha `10.0`, using the identical folds,
features, comparator, and acceptance tests. Candidate selection is by the
frozen five-criterion result only; ties are resolved in favor of alpha `1.0`,
then lower alpha. No additional tuning, feature search, favorable-fold
selection, or threshold change is allowed.

All candidates must record source/file hashes, code and dependency identity,
fold membership, predictions, regime metrics, calibration, failures, and a
result hash outside Git. A candidate that passes development criteria is only
eligible for nomination; it remains unvalidated until separately authorized
protected evaluation.

## Frozen acceptance criteria

All five criteria are mandatory and must pass:

1. R² improvement over ATR × 1.5 is greater than `0.01`.
2. Correlation improvement over ATR × 1.5 is greater than `0.05`.
3. MAE reduction is greater than `5%`.
4. Predicted/actual calibration-bin means are monotonic.
5. MAE and R² improvements are positive in every required 30-day regime.

The historical `4/5` label is not a passing result. The legacy `>=4` decision
rule is excluded from this protocol.

## Reproducibility identity

The offline runner was recovered in disposable worktree commit `31aad1f` from
the historical Git object and changed only to reject network access, read the
explicit local source, and write output outside the repository. The active
research environment uses the repository's Python 3.11 virtual environment;
the exact package lock and runner tree must be retained with each result. No
production artifact or persisted research row is created by this protocol.
