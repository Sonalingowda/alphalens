# Gate 06 new development lineage protocol — 2026-11-11

Status: **PREPARED; fitting not authorized or run**

This document defines one new development lineage. It does not certify Gate
06, open protected data, create a model artifact, or change the five frozen
acceptance criteria.

## Source identity and evidence boundary

The permitted source is the retained read-only BTCUSDT/5m artifact identified
by the companion content-addressed manifest. The complete file hash,
canonical candle hash, ingestion batch ID, retrieval time, source window, and
metadata are recorded there.

The source declares Binance REST endpoint metadata, but the original raw
provider response bytes are not retained. Therefore `raw_response_sha256` is
explicitly **unavailable**, not inferred. The source-availability cutoff is
the recorded retrieval timestamp; no network fetch or later source refresh is
permitted for this lineage.

## Chronological boundaries

The retained source window is `2026-07-14T10:10:00Z` through
`2026-10-12T10:05:00Z`.

This protocol proposes, for owner/custodian confirmation before fitting:

- development observations: `2026-07-14T10:10:00Z` through
  `2026-09-12T10:05:00Z`;
- sealed protected boundary: `2026-09-12T10:10:00Z` through
  `2026-10-12T10:05:00Z`.

The protected interval is a boundary declaration only. No protected rows,
labels, aggregates, or outcomes were read. Candidate selection, feature
selection, scaling, calibration, and stopping decisions use development data
only. A protected custodian must confirm the boundary before any fitting.

## Point-in-time construction

- Candle interval: 5 minutes; timestamps are UTC candle-open times.
- Feature pre-roll: exactly 200 completed candles (1,000 minutes).
- Label extension: exactly five completed candles (25 minutes) for
  `abs(log(close[t+5] / close[t]))`.
- Fold purge/embargo: exactly 250 observations (1,250 minutes) between the
  training tail and evaluation observations.
- Folds: expanding chronological train/development folds; no random split.
- Feature definitions, ordering, scaling, comparator, and acceptance code are
  frozen before fitting.
- Per-observation predictions and residuals are mandatory retained outputs.

## Bounded candidates and hypothesis

Scientific hypothesis: the frozen 17-feature point-in-time representation may
contain nonlinear interactions that Ridge cannot express, while preserving
the same target, chronology, comparator, and acceptance contract.

At most three candidates are predeclared:

1. Ridge, `alpha=1.0`, the frozen baseline, `random_state=None`.
2. RandomForestRegressor, `n_estimators=200`, `max_depth=4`,
   `min_samples_leaf=20`, `max_features=1.0`, `random_state=20261111`.
3. RandomForestRegressor, `n_estimators=400`, `max_depth=6`,
   `min_samples_leaf=20`, `max_features=1.0`, `random_state=20261111`.

Random forest is the only alternative model family. The target and feature
definitions are not changed. There is no further hyperparameter search,
feature search, candidate substitution, favorable-fold selection, or
protected-data selection.

## Frozen acceptance and rejection

Every candidate must satisfy all five existing criteria:

1. R² improvement over ATR × 1.5 is greater than `0.01`.
2. Correlation improvement over ATR × 1.5 is greater than `0.05`.
3. MAE reduction is greater than `5%`.
4. Calibration-bin means are monotonic.
5. MAE and R² improvements are positive in every required 30-day regime.

Any failed criterion rejects the candidate. Candidate selection is performed
only on the development result, using the complete five-criterion vector;
ties resolve to Ridge, then the lower candidate number. A development
nomination is not Gate 06 certification or artifact promotion.

## Reproducibility record required before fitting

The run manifest must bind the source manifest hash, repository tree hash,
feature implementation hash, dependency lock hash, runner hash, protocol
hash, exact fold membership, candidate configuration, random states, and
per-observation prediction/residual result hashes. Missing raw-response
evidence remains missing. Results are retained outside Git; only sanitized
lineage identity and status may be committed.

No fitting was performed under this preparation authorization.
