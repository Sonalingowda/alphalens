# Gate 06 controlled development experiment — 2026-11-11

Status: **BLOCKED before candidate completion; no predictive result reported**

## Isolation evidence

The custodian extractor read the verified source and emitted a separate
development-only artifact containing 17,280 candles:

- development window: `2026-07-14T10:10:00Z` through `2026-09-12T10:05:00Z`;
- source hash: `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`;
- development dataset SHA-256:
  `2825f80df1434ac52eef868cd3606b95b046d7e624d9e0ad84754be494e156b4`;
- protected rows read by the runner: false.

The development artifact is retained privately at:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-development-20261111-v2/development-dataset.json`

The runner accepts only this development artifact, has no HTTP, PostgreSQL,
Redis, or protected-source access path, and uses the fixed 200-candle
pre-roll, five-candle label extension, and 250-observation purge.

## Executable identity

- custodian extractor SHA-256:
  `eb206429955bb6e460ac5f8bc2150888148e86182b01e253716439bc29a394ce`;
- offline runner SHA-256:
  `013366d7f0e99d59a2e2f0fd420ec6a678bf51959d08f1293e1eec597326e966`;
- protocol SHA-256:
  `ab736306b98877abf725d8700e509d78d41ec4cd9e86619f0390bb64712e1f9a`;
- dependency lock SHA-256:
  `a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959`.

## Execution outcome

The first attempt exposed and corrected a Decimal-conversion defect. A second
attempt was interrupted during feature construction because the production
prefix-invariance diagnostic is O(n²). A third attempt used the documented
research-only bypass of that redundant diagnostic, but the three fixed
chronological RandomForest candidates exceeded a bounded runtime; the run was
interrupted before publishing results. A parallel `n_jobs=-1` rerun was also
interrupted after more than four minutes without a result file.

No candidate metrics, acceptance decisions, nominations, predictions, or
residual archives are claimed. No protected rows, owner database, Redis data,
model artifact, or deployment target was accessed.

The interrupted executions are negative engineering evidence. Any retry must
use a new run identity after a separately reviewed runtime-bounded
implementation; candidate count, hyperparameters, seeds, and acceptance
criteria must remain unchanged.
