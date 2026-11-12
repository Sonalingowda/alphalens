# Gates 01–07 preservation reconciliation — 2026-11-12

Status: **PRESERVATION PARTIALLY VERIFIED — RESTRICTED WORK ONLY**.

## Repository

- Branch: `gate9d2/owner-infrastructure-20261105`
- Commit: `f0f73ed5c2e246f7e19890c32c2a21baf446ddf7`
- Local and remote branch SHAs match.
- Worktree was clean before this documentation change.

## Gate 04G storage reconciliation

The accepted bounded batch is present in the recovered owner database:

- Database: `alphalens_local_rebuild_20261105`
- PostgreSQL: 16.12 on `127.0.0.1:55461`
- Alembic: `20261110_0044`
- Batch: `559d9dff-2965-5a37-8a4d-095a3e631eba`
- State: `ACCEPTED`, `BTCUSDT`, `5m`, 240 members
- Source response SHA-256:
  `f2fdebc9d8b89052d4f08fcece4b2c946f99f27eaca72f44eef105c515209d72`
- Membership SHA-256:
  `223645b2391d2952c53bdee41ae18d20d40cf93fd4493f20ff4c7e92eac72a01`
- Batch SHA-256:
  `eaa0107ba999d5bc130633f52329ab2503592821cbaa08c7b0994a6c0524210e`

The canonical market-snapshot table for this path is
`immutable_runtime_aggregates`, filtered to entity type
`app.opportunity_intelligence.domain.market.MarketSnapshot`. It contains 240
rows, and all 240 warmup members link to distinct existing immutable
snapshots. The linked rows are all BTCUSDT/5m, immutable, hash-shaped
correctly, and cover contiguous five-minute timestamps with no interval
breaks.

`market_data_candles` is a separate legacy/provider candle table and contains
zero rows. The warmup repository writes immutable `MarketSnapshot` aggregates
and the accepted batch/member manifest in one transaction; it does not write
`market_data_candles`. The `/markets/live` path reads through
`MarketSnapshotPostgreSQLRepository`, which applies the accepted-batch guard.
Therefore the zero `market_data_candles` count is expected for this bounded
warmup and is not evidence of missing warmup snapshots.

## Gates 01–05

Committed implementation, migration, test, API, warmup, recovery and bounded
Binance evidence remain present through the checkpoint history. Gate 04G is
supported by the accepted database batch, 240 immutable members, private
runtime evidence and `docs/CHECKPOINT_04G.md`. Continuous ingestion was not
started.

## Gate 06

Protocols, source manifests, development data, result archives and hashes are
present locally and in sanitized Git documentation. The three-candidate
volatility experiment remains negative under the frozen criteria. No protected
observations were accessed, and no model artifact was activated or promoted.
Gate 06 remains **NOT VALIDATED**.

## Gate 07

Authentication, authorization, provenance, stale-data, audit, assessment-only
and model-unavailable fail-closed implementation/tests remain present. Gate 07
engineering remains PASS, but certification remains **BLOCKED** pending a
validated predictive artifact and protected evaluation.

## Recovery backup

Local PostgreSQL custom-format backups are present and readable by
`pg_restore`:

- `owner-baseline-20261105.dump` —
  `4e7e44ec3ccd0f1d40d44325040bca245fcdff0af3f1f5b04c7389a8ff092d0b`
- `owner-checkpoint04e-pg16-b39e0bd0c9e5.dump` —
  `fa37ff35447fae3acbe146e5fa20f8e63d3e2b6169cd112e9129ee38a91bd5e5`
- `owner-checkpoint04f-pre-migration-pg16-20261111T172252-28052.dump` —
  `8638978ff3b8df851b7c55a15b69e3f90a8d699add179e414476374a87e0506c`

The external encrypted DMG exists at
`/Volumes/ESD-USB/AlphaLens-Backup-04E.dmg`. Current SHA-256 is
`b8f862ad2d41d0cfb24bc1739f68f716a0d72838a6c9ea53f407a815d364560c`.
Metadata reports an encrypted UDRW image, but `hdiutil verify` reports that it
has no embedded checksum. The recovery volume is not mounted, so the internal
dump could not be rechecked during this audit. Earlier image hashes were not
found in the local operational files; the external backup therefore remains
independently **UNVERIFIED** until a controlled owner-assisted read-only mount
and internal dump checksum check is completed.

## Runtime separation and restrictions

- Recovered owner PostgreSQL: host process, `127.0.0.1:55461`, operational
  data directory, revision `20261110_0044`.
- Legacy Docker PostgreSQL: existing container, `127.0.0.1:15432`, separate
  Docker volume, revision `20261003_0040`; not the recovered owner database.
- Recovered owner Redis: host process, `127.0.0.1:56397`.
- Legacy Docker Redis: existing container, `127.0.0.1:16379`, separate Docker
  volume.

No databases, volumes, Docker resources or protected checkout files were
modified. No cleanup, build, acquisition, model fitting, protected
evaluation, trading or deployment was performed.

## Decision

The Gate 04G storage discrepancy is cleared. The remaining preservation
limitation is independent external-backup verification; Docker recovery must
remain restricted until that evidence is reconciled or explicitly accepted by
the owner.
