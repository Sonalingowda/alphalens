# Gate 06 volatility experiment result — 2026-11-11

Status: **DEVELOPMENT COMPLETE; Gate 06 NOT VALIDATED**

The authorized three-candidate development experiment completed without
protected-data access, owner database access, network access, artifact
promotion, or deployment. No candidate satisfied all five mandatory criteria.

## Execution identity

- execution Git commit: `56427682c437a93c912e033dfe4b07196c76b2f7`;
- execution Git tree: `d21c8aa4082db001616b5ee69698ae2ac57d36dd`;
- dataset file SHA-256: `2825f80df1434ac52eef868cd3606b95b046d7e624d9e0ad84754be494e156b4`;
- custodied development-content SHA-256: `d24af87a174a6baef4042afe682760954d7851c18fc75865a18c24f55c5308da`;
- source-file SHA-256: `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`;
- source manifest SHA-256: `4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038`;
- feature implementation SHA-256: `25f630fe86f88c8ecef71d43d57d925313f0d5a3fb8b09979d3f8a3e861b1cf0`;
- fitting runner SHA-256: `4c0fc84f29f326454097ec0d72c0c5ed0752c0efe4578bf65b26568cf5d9cb24`;
- protocol SHA-256: `8decbda413ed41c7ca9cb81f648625a52bf9189d2b387beb856b2d931941b45f`;
- dependency lock SHA-256: `a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959`;
- execution manifest SHA-256: `b464fb827c7940404dca4b5d28fcd2c7b199a006dae865619f9f41c3593558bb`;
- result archive SHA-256: `646a0928c731d3567a1db69cf03a43c6090572664eb98d42cd9b526aa2b7fe55`;
- final checkpoint SHA-256: `eb38db3316e7f98b5e735c98c2b0a6ae0c0546a53fac52550c15fa8b1a525f5f`.

Private artifacts are retained under:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-volatility-execution-20261111-r2/`

## Frozen population and candidates

All candidates used the same 164 expanding chronological folds and 16,400
test observations. Fold IDs, timestamps, actual values, and ATR comparator
values were independently identical across candidates.

| Candidate | R² improvement | Correlation improvement | MAE reduction | Calibration | Regimes | Decision |
|---|---:|---:|---:|---|---|---|
| Ridge α=1.0 baseline | +0.113234 | +0.004712 | 8.1805% | PASS | PASS | Rejected |
| Ridge + Parkinson(20) α=1.0 | +0.113450 | +0.004847 | 8.2507% | PASS | PASS | Rejected |
| Ridge + Garman–Klass(20) α=1.0 | +0.112351 | +0.004218 | 8.1720% | PASS | PASS | Rejected |

All three candidates failed the mandatory correlation-improvement threshold
of `>0.05`. Each passed the R², MAE, calibration, and per-regime criteria.
No candidate is nominated or promoted.

## Scientific decision

This exact three-candidate budget is closed as negative development evidence.
The volatility features improved R² and MAE modestly but did not provide the
required correlation improvement. Gate 06 remains NOT VALIDATED; Gate 07
remains blocked on predictive certification, and no model artifact is active.
