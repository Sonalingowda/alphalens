# Gate 06 volatility-feature experiment manifest identity — 2026-11-11

Status: **READY FOR DEVELOPMENT FITTING; fitting not performed**

Private manifest:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-volatility-20261111/manifest.json`

Manifest SHA-256:
`0da01ecb5cc42a3e01a5ed3787c81475002bad841f6ca9543bda07915e5fd898`

Bound identities:

- development dataset:
  `2825f80df1434ac52eef868cd3606b95b046d7e624d9e0ad84754be494e156b4`;
- source manifest:
  `4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038`;
- feature implementation:
  `25f630fe86f88c8ecef71d43d57d925313f0d5a3fb8b09979d3f8a3e861b1cf0`;
- manifest runner:
  `728c85379d84070d379d526ddd30c070869cbf943669a062000f34da687602bd`;
- protocol:
  `8decbda413ed41c7ca9cb81f648625a52bf9189d2b387beb856b2d931941b45f`;
- dependency lock:
  `a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959`.

The manifest freezes exactly three candidates: existing Ridge α=1.0,
Ridge α=1.0 plus Parkinson, and Ridge α=1.0 plus Garman–Klass. It records
the unchanged five acceptance criteria, cutoff, 20-candle feature window,
five-candle label extension, and 250-observation purge.
The fold schedule is minimum train 500, test 100, step 100, 164 expanding
chronological folds, and 16,400 observations per candidate; the total budget
is at most 492 candidate-fold fits.

No fitting, protected-data access, artifact creation, production-data access,
or deployment occurred.
