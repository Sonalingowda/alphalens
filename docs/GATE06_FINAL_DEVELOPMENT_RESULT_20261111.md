# Gate 06 final development result — 2026-11-11

Status: **DEVELOPMENT COMPLETE; Gate 06 NOT VALIDATED**

## Execution identity

- source manifest: `4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038`;
- development dataset: `2825f80df1434ac52eef868cd3606b95b046d7e624d9e0ad84754be494e156b4`;
- runner SHA-256: `8400fbb9440a61da1f9e7a0c32f7d1581b07ac3d6d29c8f82581b58eca76594f`;
- protocol SHA-256: `ab736306b98877abf725d8700e509d78d41ec4cd9e86619f0390bb64712e1f9a`;
- dependency lock SHA-256: `a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959`;
- folds per candidate: 164;
- observations per candidate: 16,400;
- development regimes: 2, both complete.

Private result archive:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-development-20261111-v2/final-results.json`

Result SHA-256:
`4a89aff510cbddbbfd387a23f2333ba7cf16616365f525bb0208d007155e361d`

Private atomic checkpoint:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-development-20261111-v2/final-results.checkpoint.json`

Checkpoint SHA-256:
`b0a33cf8fec479a0f338649bbeaec0c9aafe19af3f79d3d25bb142033d9d9b21`

## Candidate results

| Candidate | R² improvement | Correlation improvement | MAE reduction | Calibration | Regimes | Decision |
|---|---:|---:|---:|---|---|---|
| Ridge α=1.0 | +0.113234 | +0.004712 | 8.1805% | PASS | PASS | Rejected |
| Random Forest 200/depth 4 | +0.105864 | +0.001222 | 5.4706% | PASS | PASS | Rejected |
| Random Forest 400/depth 6 | +0.097929 | -0.004354 | 4.5860% | PASS | PASS | Rejected |

All three fail the mandatory correlation improvement threshold `>0.05`.
The 400-tree candidate also fails the mandatory MAE reduction threshold
`>5%`. No candidate was nominated or promoted.

## Correctness and recovery

- The fifth acceptance criterion now requires positive MAE and R² improvement
  in every complete 30-day regime.
- Missing or empty regimes reject rather than pass.
- Nonfinite source features, targets, predictions, and metric inputs fail
  closed.
- Fold IDs and UTC timestamps are retained for every prediction, residual, and
  baseline value.
- Checkpoints are identity-bound and atomically replaced after each completed
  fold; completed folds are resumable without restarting.
- The prefix-invariance bypass matched the reference implementation on a
  deterministic 320-candle prefix and 8,833 feature values.

No protected observations, owner database, Redis data, model artifact,
ingestion worker, trading process, or deployment target was accessed.
