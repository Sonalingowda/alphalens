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
`CEncryptedEncoding`. It also reports no embedded checksum. The image is not
currently attached and `/Volumes/AlphaLens-Recovery` is absent.

## Verification boundary

No password was requested, received, logged, passed as an argument, or stored.
A read-only attachment could not be completed in this unattended session
because the encrypted image requires owner-controlled authentication. The
internal recovery manifest and PostgreSQL dump were therefore not accessible
for this verification cycle. No `pg_restore --list` or restore operation was
performed against the external copy.

The local copies remain unchanged and previously verified separately:

- Checkpoint 04E PostgreSQL dump:
  `fa37ff35447fae3acbe146e5fa20f8e63d3e2b6169cd112e9129ee38a91bd5e5`
- Baseline PostgreSQL dump:
  `4e7e44ec3ccd0f1d40d44325040bca245fcdff0af3f1f5b04c7389a8ff092d0b`

Those local checksums do not independently prove the current encrypted DMG
contents. External recovery remains partially verified until the owner unlocks
the image through the normal macOS prompt and the internal dump checksum and
archive catalog are rechecked.

No USB files, DMG bytes, databases, Docker resources, or repository files were
modified by the inspection.
