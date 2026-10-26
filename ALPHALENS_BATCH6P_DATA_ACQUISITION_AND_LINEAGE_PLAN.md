# AlphaLens Batch 6P — Data Acquisition and Lineage Plan

Date: 2026-10-26  
Status: **PROPOSED / NO ACQUISITION EXECUTED**

## Source and access boundary

Future development-only acquisition may use the Binance Spot klines endpoint
already referenced by `backend/scripts/run_live_ingestion_pipeline.py`:

```text
https://api.binance.com/api/v3/klines
symbol=BTCUSDT
interval=5m
```

No request was made. The plan permits only closed BTCUSDT/5m market-data reads;
no account, order, withdrawal, trading, or private-data permission is needed
or authorized. If the future environment requires credentials, they must be
unique, short-lived, read-only market-data credentials stored outside source
and logs. No credentials are generated here.

## Source availability cutoff

At actual authorized acquisition time, record one UTC
`source_availability_cutoff` before examining returned data. A candle is
eligible only when its close timestamp is at or before that cutoff and the
response was available under the recorded acquisition receipt. The cutoff,
collector commit, request timestamps, endpoint parameters, page sequence, and
raw response hashes are immutable manifest fields.

The proposed chronology remains:

- development source collection: `2026-10-13T00:00:00Z` through
  `2027-01-10T23:55:00Z`;
- last development-fitting eligible timestamp:
  `2027-01-10T03:05:00Z`;
- 250-row embargo: `2027-01-10T03:10:00Z` through `23:55:00Z`;
- protected test: `2027-01-11T00:00:00Z` through `2027-02-09T23:55:00Z`;
- protected target-label completion: through `2027-02-10T00:20:00Z`.

These are approved protocol definitions, not evidence that data exists.

## Pagination and candle verification

The future collector must:

1. request bounded pages using `symbol=BTCUSDT`, `interval=5m`, and an explicit
   start/end or continuation boundary;
2. retain exact raw response bytes and a canonical parsed representation;
3. verify UTC open timestamps are strictly increasing at 300-second cadence;
4. verify Binance candle close semantics, closed status/source cutoff, OHLCV
   validity, and five-minute alignment;
5. detect duplicates, gaps, overlapping pages, unexpected counts, malformed
   metadata, and boundary truncation;
6. stop on any mismatch rather than filling, interpolating, retrying across an
   unexplained gap, or silently dropping a row;
7. record requested count, actual count, first/last open timestamps, page count,
   collection timestamps, raw SHA-256, canonical SHA-256, and a unique
   ingestion identity.

No existing raw file is copied or altered by this plan.

## Storage proposals

The following paths are proposals only and were not created:

```text
/private/tmp/alphalens-batch6o-evidence-<run-id>/raw/pages/
/private/tmp/alphalens-batch6o-evidence-<run-id>/canonical/candles.json
/private/tmp/alphalens-batch6o-evidence-<run-id>/manifests/source.json
/private/tmp/alphalens-batch6o-evidence-<run-id>/lineage/
/private/tmp/alphalens-batch6o-evidence-<run-id>/logs/
```

Raw responses, canonical candles, manifests and logs must be append-only or
content-addressed. The original repository evidence directory, historical
dataset, protected-test storage, and production volumes are not destinations.

## Pre-roll, fitting rows and labels

- Collect at least 200 prior closed candles before the first eligible model
  observation; this is full-pipeline pre-roll and is not a fitting row.
- The five-feature lower bound is 28 candles, but it does not replace the 200
  candle full-pipeline requirement.
- For prediction candle `t`, feature availability is `t + 5m` and the target
  uses `close[t+5]`; the target label completes at `t + 30m` when that future
  candle closes.
- The final development-fitting row must have a complete target label within
  the authorized development/source boundary.
- The 250 embargo observations are explicit non-fitting/non-selection rows.
- Protected pre-roll/context rows are sealed with the protected evaluation
  bundle and are not exposed to development.

## Lineage records

The future source manifest must link:

1. raw response pages and source availability receipt;
2. canonical candle artifact and hashes;
3. ingestion batch ID and source boundaries;
4. feature run ID, pipeline/registry/schema hashes, ordered five features,
   Decimal rules, pre-roll, dependency cutoffs, and result hash;
5. target run ID, target hash/formula/horizon, label-completion checks, and
   source/feature parents;
6. chronological split manifest, 250-row embargo membership, protected seal
   reference, and no-overlap proof;
7. validation run, code/lockfile/environment identity, configuration/random
   state, fold results, reviewer receipt, and final result hash.

No historical UUIDs or 4/5 results may be backfilled as new lineage. A failed
or incomplete run is retained with its exact failure predicate and hashes.

## Acquisition stop conditions

Stop before feature/target materialization on source hash or endpoint mismatch,
missing source metadata, unavailable or late closed candles, duplicates, gaps,
unexpected symbol/timeframe, incomplete pages, cutoff violation, protected
period access, credential ambiguity, or unavailable custodian/reviewer.

Stop before fitting on missing 200-candle pre-roll, target label lateness,
future-data leakage, broken feature/target linkage, split overlap, missing
embargo membership, nondeterministic hashes, or any protected-data access.

## Status

No network request, dataset creation, source write, feature generation, target
generation, model prediction, validation, or infrastructure operation occurred.
The smallest next executable batch is development-environment preparation and
development-only acquisition, each requiring separate explicit approval.
