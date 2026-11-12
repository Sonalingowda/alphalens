# External backup verification — 2026-11-12

Result: **EXTERNAL BACKUP PARTIALLY VERIFIED**.

## Read-only identity checks

- USB volume: `/Volumes/ESD-USB`
- Filesystem: FAT32
- Removable USB media: confirmed
- DMG: `/Volumes/ESD-USB/AlphaLens-Backup-04E.dmg`
- Size: 100,016,640 bytes
- Modification time: `2026-11-11T16:40:52+0530`
- Current SHA-256:
  `b8f862ad2d41d0cfb24bc1739f68f716a0d72838a6c9ea53f407a815d364560c`

`hdiutil imageinfo` reports an encrypted `UDRW` image backed by
`CEncryptedEncoding`. It also reports no embedded checksum. The owner mounted
the image read-only; `hdiutil` reported `writeable: false` and
`image-encrypted: TRUE`, with `/dev/disk5s1` mounted at
`/Volumes/AlphaLens-Recovery`.

## Verification boundary

No password was requested, received, logged, passed as an argument, or stored.
The internal dump was
`alphalens-owner-checkpoint04e-pg16-20261111T110113Z-23f101b1.dump`; it was
370,807 bytes and its SHA-256 exactly matched the trusted Checkpoint 04E
record. The archive is PostgreSQL custom format, was created and dumped by
PostgreSQL 16.12, and records database
`alphalens_local_rebuild_20261105`. `pg_restore --list` succeeded. Archive
data inspection recorded Alembic `20261027_0043`, matching the pre-migration
Checkpoint 04E recovery point.

No separate recovery-manifest file was present in the mounted volume. No full
restore test was performed; archive readability is not being represented as a
restore certification.

The local copies remain unchanged and previously verified separately:

- Checkpoint 04E PostgreSQL dump:
  `fa37ff35447fae3acbe146e5fa20f8e63d3e2b6169cd112e9129ee38a91bd5e5`
- Baseline PostgreSQL dump:
  `4e7e44ec3ccd0f1d40d44325040bca245fcdff0af3f1f5b04c7389a8ff092d0b`

The read-only recovery volume was detached cleanly with `hdiutil detach`, and
the closed-DMG SHA-256 remained unchanged at
`b8f862ad2d41d0cfb24bc1739f68f716a0d72838a6c9ea53f407a815d364560c`.

The external backup is cryptographically verified at the dump and archive
level, with the separate-manifest and full-restore limitations recorded above.

No USB files, DMG bytes, databases, or Docker resources were modified by the
inspection. This sanitized report is the only repository change.
