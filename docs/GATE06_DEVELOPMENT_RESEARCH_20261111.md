# Gate 06 controlled development research — 2026-11-11

Status: **DEVELOPMENT COMPLETE / GATE 06 NOT VALIDATED**
Protocol: [`GATE06_DEVELOPMENT_PROTOCOL_20261111.md`](GATE06_DEVELOPMENT_PROTOCOL_20261111.md)

## Reproducibility restoration

The historical runner was recovered from Git object
`091cbe012c0b2a9a130b900c0c6baf9ed967d85d` into disposable worktree
`/tmp/alphalens-gate06-research.kUvh63`. It was adapted only to accept an
explicit local dataset, reject network access, and write result JSON outside
the repository. No owner PostgreSQL or Redis connection was configured.

The permitted source file was read-only and matched:

`f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`

It contained 25,920 contiguous `BTCUSDT`/`5m` candles. The current source
window is `2026-07-14T10:10:00Z` through `2026-10-12T10:05:00Z`. The historical
result records a different window, `2026-05-22T18:50:00Z` through
`2026-08-20T18:45:00Z`, and timestamp hash
`528bb245713f4ae7b60397d05c2875e41f96a68dd0cf0c8b3e68e6e82dba70b3`.
Consequently, the historical run is not numerically reproducible from the
currently retained source, even though the file hash documented by prior
reports is the same. This cycle is a new lineage and does not overwrite the
historical result.

## Frozen run

The run used the existing 17-feature pipeline, target
`abs(log(close[t+5] / close[t]))`, expanding chronological folds, minimum
training size 500, test size 100, step 100, purge 250, training-only feature
selection and scaling, Ridge alpha candidates, ATR×1.5 comparator, five
calibration quintiles, and 30-day regimes. No random state was required.

The baseline and two predeclared candidates were run exactly once each:

| Candidate | Ridge correlation | ATR correlation | Correlation improvement | MAE reduction | R² improvement | Calibration | Regimes |
|---|---:|---:|---:|---:|---:|---|---|
| alpha 1.0 | 0.3853225223 | 0.3766592628 | +0.0086632595 | 8.6058% | +0.1195706219 | PASS | 3/3 PASS |
| alpha 0.1 | 0.3853262838 | 0.3766592628 | +0.0086670210 | 8.6073% | +0.1195632525 | PASS | 3/3 PASS |
| alpha 10.0 | 0.3853234388 | 0.3766592628 | +0.0086641760 | 8.5940% | +0.1196176588 | PASS | 3/3 PASS |

Result hashes, retained outside Git:

- alpha 1.0: `/tmp/alphalens-gate06-research-result.json`,
  `a0c97b6c6ca31fa095c9ab9086af6baa26b7568548bf6990d02c7006a7ce7bbf`;
- alpha 0.1: `/tmp/alphalens-gate06-alpha-0.1.json`,
  `ac0c249249e7c504aa464007220d92118447a910b9f5ee17ab46ee395561a692`;
- alpha 10.0: `/tmp/alphalens-gate06-alpha-10.0.json`,
  `c56cd2cf0fcd4c5addc9f531c3f4ad9c54adc52268195ea4ceeaadc6e6cd02b5`.

## Acceptance decision

All three candidates fail criterion 2, correlation improvement `> 0.05`.
They pass the other recorded development checks, but all five criteria are
mandatory. No candidate is nominated, packaged, activated, or promoted. The
historical legacy `>=4/5` decision rule remains rejected.

The correlation arithmetic is internally consistent: for the baseline,
`0.3853225223348531 - 0.37665926279679174 = 0.00866325953806136`, which rounds
to the documented `+0.008663260`. There is no evidence that the historical
correlation improvement was miscomputed; the defect was the permissive
decision gate and the unresolved source-lineage mismatch.

## Scientific diagnosis

- Feature timestamps precede the five-candle target horizon; the target uses
  only future closes by construction.
- Feature selection and scaling are fit on each training fold only.
- Folds are chronological and purged by 250 observations.
- The retained source has no detected 5-minute gaps.
- All three regimes have positive MAE and R² improvement and monotonic
  calibration, but correlation remains weak relative to the frozen threshold.
- The alpha sweep changes the result only in the fourth decimal place and does
  not address the failed criterion.

The remaining likely causes are model-signal limitation and/or source-era
nonstationarity, not a demonstrated leakage or comparator arithmetic defect.
No further tuning is authorized by the frozen experiment budget.

## Gate status and safety

Gate 06 remains **NOT VALIDATED** because protected evaluation has not been
authorized or performed and development candidates do not satisfy all five
criteria. Gate 07 remains blocked on the absence of a validated artifact.
Gate 08 and Gate 09 preparation may continue independently, but deployment and
release certification remain unauthorized.

No protected data, owner database rows, Redis data, continuous ingestion,
trading process, predictive artifact, or production deployment was touched.
