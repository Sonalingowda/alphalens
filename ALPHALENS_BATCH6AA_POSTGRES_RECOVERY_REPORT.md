# AlphaLens Batch 6AA — PostgreSQL Recovery Report

## Original state preservation

The original dirty checkout and retained Batch 6Z/6U evidence were not reset, overwritten or reinitialized. The owner directory `/private/tmp/alphalens-local-20261026/postgres` was inspected in place and preserved. It was non-empty but lacked root `PG_VERSION`, lacked `global/pg_filenode.map`, and `pg_ctl status` reported that it was not a database cluster. Logs repeatedly reported failure to open `global/pg_filenode.map`.

The retained Batch 6Z directory was a real cluster with `PG_VERSION`, but its recorded server was stale and startup encountered an existing shared-memory block. Ownership could not be established safely, so no shared-memory resource was removed and no WAL or data directory manipulation was attempted.

## Recovery path

A separately initialized recovery cluster was created at `/private/tmp/alphalens-batch6aa-local-recovery/postgres` on PostgreSQL port `55460`; Redis used port `56397`. The existing custom dump was retained and restored after PostgreSQL-version compatibility handling. The dump SHA-256 is `5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`, identical to the durable copy under the AlphaLens local-state-backups directory.

The dump contained owner thesis/event state but no candle rows. After recovery and genuine Binance warmup/live ingestion, canonical immutable persistence contained:

| Durable record | Count |
|---|---:|
| `MarketSnapshot` immutable aggregate rows | 1,295 |
| `opportunity_theses` | 28 |
| `opportunity_thesis_assessments` | 28 |
| `opportunity_thesis_events` | 84 |
| legacy `market_data_candles` rows | 0 |

The zero legacy candle count is not presented as a recovery failure: current live snapshot persistence uses `immutable_runtime_aggregates`, where the 1,283 genuine BTCUSDT/5m snapshots are present. The report explicitly does not claim the pre-Batch6Z backup contained historical candles.

## Safety result

Startup now refuses a non-empty directory that is not a recognizable cluster and only initializes an empty directory. Normal restart of the recovered cluster was verified through a fast PostgreSQL shutdown and restart with data retained. No existing database directory was deleted or automatically reinitialized.

Classification: **PASS for safe isolated recovery; PARTIAL for historical candle restoration**, because the retained backup itself contained no candle rows and the original invalid directory was not repairable from its contents.
