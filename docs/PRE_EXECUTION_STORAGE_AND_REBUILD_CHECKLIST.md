# AlphaLens pre-execution storage and backend rebuild checklist

This checklist is preparation only. It does not authorize cleanup, Colima
shutdown or resize, live database migration, deployment, or model activation.

## Host archival gate

- [ ] Confirm the owner-selected external volume through `diskutil info`.
- [ ] Confirm the exact volume name, removable status, mount path and filesystem.
- [ ] Confirm at least 20 GiB free, plus the recording bytes and a 1 GiB margin.
- [ ] Run `scripts/archive_screen_recordings.sh --volume-name <exact-name>`.
- [ ] Preserve the archival receipt, original recordings and SHA-256 comparisons.
- [ ] Confirm no original file was deleted or overwritten.

## Colima capacity gate

- [ ] Confirm `docker context show` is the intended Colima profile.
- [ ] Record `colima list`, guest filesystem capacity, Docker root usage and inode usage.
- [ ] Confirm owner containers, volumes, backups and forensic VMs are excluded from cleanup.
- [ ] Obtain explicit approval before stopping or resizing Colima.
- [ ] Before a resize, preserve the verified PostgreSQL backup and record the rollback limitation: disk expansion is not a data rollback mechanism.
- [ ] After an approved resize, verify the guest partition/filesystem, Docker root free space and all protected containers.

## Backend image gate

- [ ] Verify repository branch, HEAD, clean worktree and remote SHA.
- [ ] Preserve `backend/uv.lock` and the pinned Dockerfile base-image digests.
- [ ] Confirm Docker VM free space is sufficient for dependency download, extraction, virtual-environment layer and final image.
- [ ] Build only with a distinct rehearsal tag and explicit Git/build metadata.
- [ ] Record image ID, digest, provenance file and migration files through `20261110_0044`.
- [ ] Do not replace the live image.

## Disposable database gate

- [ ] Use only `alphalens-rehearsal-postgres-20261112` or a newly identified disposable database.
- [ ] Verify revision `20261110_0044` and preserved aggregate counts.
- [ ] Exercise API tests only against disposable services.
- [ ] Confirm live demo revision remains `20261003_0040`.

## API and frontend gate

- [ ] Verify `/api/v1/opportunities`, history, detail, thesis and assessment routes from the same source/image identity.
- [ ] Verify the current source fallback behavior with focused backend tests.
- [ ] Verify frontend API base URL and error/empty-state behavior with focused frontend tests.
- [ ] Confirm API 404/5xx responses are not silently represented as empty market data.
- [ ] Confirm `ARTIFACT_UNAVAILABLE` remains fail-closed.
- [ ] Confirm no fabricated opportunities, model artifacts or market values are introduced.

## Final acceptance evidence

- [ ] Backend image provenance matches the source commit.
- [ ] Migration rehearsal passes without modifying live or owner databases.
- [ ] Opportunity and thesis persistence tests pass.
- [ ] Economic analysis and market-data provenance tests pass.
- [ ] Audit persistence is available and immutable.
- [ ] Restart/recovery behavior is verified in disposable resources.
- [ ] Paper-trading readiness remains separate from predictive-model validation.
- [ ] Gate 06 remains NOT VALIDATED until protected evaluation is independently authorized and passed.
