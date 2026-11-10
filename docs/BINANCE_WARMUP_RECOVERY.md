# Binance warmup recovery protocol

This protocol is for a future owner-approved BTCUSDT 5m acquisition. It does
not authorize acquisition, worker startup, or migration of the owner database.

## Acceptance contract

The local worker validates the complete Binance Spot REST response before any
database write. The response must contain at least 200 finalized, UTC-aligned,
strictly ascending and contiguous BTCUSDT 5m candles with positive volume.
The bounded recovery target is 240 candles. The request is made to
`https://data-api.binance.vision/api/v3/klines` with `symbol=BTCUSDT`,
`interval=5m`, `limit=240`, and an exclusive end time at the latest completed
5-minute boundary. The provider response is not supplemented by another
provider.

Each acquisition receives a new caller-supplied lineage identity. The manifest
records the endpoint, exact parameters, UTC request range and retrieval time,
response hash, code/configuration identity, contiguous range, per-candle
source/result hashes, membership root, and deterministic batch hash. A unique
lineage can have only one accepted batch. A different response for an existing
lineage is rejected.

## Database and filesystem ordering

`binance_warmup_batches` and `binance_warmup_batch_members` are the new
Binance-specific manifest tables. One PostgreSQL transaction inserts the
manifest, immutable market snapshots, and membership records. The manifest is
`PENDING` until every snapshot and member hash verifies; only then is it marked
`ACCEPTED`. A transaction failure rolls back the manifest and all newly staged
members/snapshots.

The filesystem warmup marker is not authoritative. It is written with a
temporary file and atomic replacement only after the database transaction has
committed. At startup, an accepted database manifest repairs a missing marker;
an orphan marker or a hash/lineage mismatch fails closed. A database commit
followed by a marker-write failure is therefore recoverable on restart. A
crash before commit leaves no accepted batch.

The existing continuous WebSocket checkpoint remains a separate contract and
is not rewritten by this protocol.

After migration `20261110_0044` is installed, PostgreSQL market-snapshot reads
apply a membership guard: a snapshot linked to a warmup member is visible only
when its batch state is `ACCEPTED`. Pending, rejected, recovery-required, or
orphaned membership links therefore cannot enter feature-history reads. Before
the migration is installed, the guard detects the absent optional table and
leaves the pre-migration owner read path unchanged during staged rollout.

## Verification boundary

Migration `20261110_0044` was exercised only against a disposable PostgreSQL
database with upgrade and downgrade. The owner database remains at its prior
revision and receives no market-data rows from this change. The focused test
suite covers finalized-candle validation, short/open/misaligned/missing and
duplicate responses, manifest hash tampering, checkpoint reconciliation, and a
disposable-database failure injection after snapshot staging. Live Binance
acquisition remains a separate owner approval step.

Before approval, the owner should verify a fresh consistent backup and an
independent encrypted off-device copy. Then run the worker with a newly
generated source identity and `--warmup-limit 240`, review the accepted batch
manifest and counts, and confirm the dashboard reports genuine market data
only after the accepted contiguous range is present.

## Owner migration approval gate

The owner migration is a separate maintenance operation. Before running it,
confirm the database identity, current revision `20261027_0043`, a fresh
PostgreSQL 16 custom-format backup with a recorded SHA-256, and a tested
independent encrypted recovery copy. Stop all ingestion and predictive-worker
processes and keep the services loopback-only.

Apply only the single revision `20261110_0044`, then verify the Alembic
revision, both Binance warmup tables, the member foreign key, required unique
constraints and indexes, and unchanged audit and market-data counts. Verify
`/health/readiness` returns 200 after the migration. Do not start acquisition
as part of migration verification.

If migration fails before any approved acquisition, preserve the failure
evidence, restore the disposable rehearsal procedure, and use
`alembic downgrade 20261027_0043` only during an explicitly approved rollback
window. That downgrade drops the new warmup tables; it must not be used after
accepted warmup data exists without a separately reviewed recovery plan.
