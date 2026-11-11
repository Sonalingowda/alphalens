# Gate 06 source-lineage reconciliation — 2026-11-11

Decision: **UNRESOLVED; historical result and retained source remain separate
lineages**

## Retained source

The read-only artifact at
`/Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json`
has:

- complete-file SHA-256:
  `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`;
- Binance REST endpoint metadata and `BTCUSDT`/`5m` identity;
- 25,920 candles with canonical hash
  `396f715032ef2e1a5d6f0325803eb0b4e7095b64c97c17fdf38ae9643f4531d4`;
- ingestion batch ID `caf88988-248f-46e0-b2ef-348161fe38ee`;
- retrieval timestamp `2026-10-12T10:06:11.418736Z`; and
- candle window `2026-07-14T10:10:00Z` through `2026-10-12T10:05:00Z`.

## Historical result

The historical JSON is preserved as Git blob
`1630b1ec2c66a5857c84d4e950650d7b5766b82d`. Its provenance records:

- source `binance_rest_api`, 25,920 candles;
- window `2026-05-22T18:50:00Z` through `2026-08-20T18:45:00Z`;
- timestamp-list hash
  `528bb245713f4ae7b60397d05c2875e41f96a68dd0cf0c8b3e68e6e82dba70b3`; and
- no ingestion batch ID, raw response hash, canonical source hash, or
  source artifact ID.

The current source’s equivalent timestamp-list hash is
`135afeb27f12c7e195fae7a337c30986a8d7690a568e74ef0ed997d01d2f3532`, not the
historical value. The full-file hash cited by earlier reports therefore does
not establish that the historical result used the currently retained bytes.

## Finding

Available evidence supports two possibilities: the retained source artifact
was replaced after the historical run, or the historical result was associated
with the wrong source-file identity. The repository does not retain enough
immutable response/ingestion lineage to distinguish them. No source file,
historical result, UUID, or hash was changed to resolve this ambiguity.

The current development experiments are correctly treated as a new lineage.
The historical 4/5 result remains negative evidence, and no protected-test
data is inferred from either window.

## Required approval before new fitting

Approve a new development source boundary and manifest that records the raw
response hash, canonical candle hash, ingestion ID, retrieval time, exact
window, code/dependency identity, fold manifest, per-observation predictions,
and protected-test separation. Retain the complete manifest and result outside
Git; commit only its sanitized identity and status.
