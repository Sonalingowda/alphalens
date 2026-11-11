# Gate 06 new source manifest identity — 2026-11-11

Status: **prepared; no fitting performed**

The immutable manifest is retained outside Git at:

`/Users/sonalingowda/alphalens-operational-20261105/research/gate06-source-manifest-20261111/manifest-4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038.json`

Manifest SHA-256:

`4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038`

Verified source identity:

- source file SHA-256: `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`;
- canonical candle dataset hash:
  `396f715032ef2e1a5d6f0325803eb0b4e7095b64c97c17fdf38ae9643f4531d4`;
- ingestion batch ID: `caf88988-248f-46e0-b2ef-348161fe38ee`;
- retrieval: `2026-10-12T10:06:11.418736Z`;
- UTC source window: `2026-07-14T10:10:00Z` through
  `2026-10-12T10:05:00Z`;
- count: 25,920 BTCUSDT/5m candles.

The original raw Binance response is unavailable. Its SHA-256 is recorded as
null in the manifest; endpoint metadata is not treated as raw-response proof.
The manifest also records the independently reproducible open-time sequence
hash and its exact hashing method.

The proposed development/protected boundary and the 200-candle pre-roll,
five-candle label extension, and 250-observation purge are defined in
[`GATE06_NEW_LINEAGE_PROTOCOL_20261111.md`](GATE06_NEW_LINEAGE_PROTOCOL_20261111.md).
Protected rows were not read.
