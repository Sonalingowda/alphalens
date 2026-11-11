# Gate 08 local staging rehearsal — 2026-11-11

Status: **PARTIAL / BLOCKED**. Disposable database and host-level application
checks passed, but Docker could not complete the backend or frontend image
builds because the Docker engine storage reached `ENOSPC`. No stale application
image was substituted, and this is not external staging or Gate 09
certification.

## Identity and isolation

- Repository: `434949f4078c764965060820172041afdeeda3d6`
- Branch: `gate9d2/owner-infrastructure-20261105`
- Effective disposable Compose configuration SHA-256:
  `b0a43d2681b0866507fca6c7cd62c701ce67f5fe9ecf7921fed2bfe53d689d8a`
- Disposable ports were `127.0.0.1:55481`, `56381`, `18081` and `30081`.
- The worker was excluded by a disabled profile and restart policies were
  explicitly `no`.
- Owner services, legacy services, persistent backups and the protected
  checkout were not modified.

## Database and recovery

PostgreSQL `16.8-alpine3.21` and Redis `7.4.2-alpine` ran in a unique
disposable project. Empty-database migration reached `20261110_0044` with 72
tables, 438 constraints and 196 indexes. A PostgreSQL 16 custom-format backup
was restore-tested successfully; its SHA-256 is
`c565873d16aa8fad3516810d912865ab12950acabde5005487b4875bee3c5b4a`.
Disposable downgrade to `20261027_0043` and re-upgrade to `20261110_0044` both
succeeded. No owner database was touched.

## Smoke and quality results

- Backend readiness: `200`.
- Model health: `503 ARTIFACT_UNAVAILABLE`.
- Development-only diagnostic route in staging: `404`.
- CORS: approved preflight `200`; disallowed origin `400` without
  `Access-Control-Allow-Origin`.
- Rate-limit sample: 120 successful readiness responses and 5 `429` responses.
- Missing Clerk configuration failed closed; no authenticated API PASS is
  claimed.
- Frontend under Node `20.20.0`: 39 tests passed; typecheck, lint and
  production build passed. Docker frontend build remained blocked by ENOSPC.
- Backend CI-equivalent result available from the verified baseline: 970 passed,
  27 skipped. No source code was changed by this rehearsal before this record.

## Storage finding

Host storage showed approximately 8.5 GiB free while Docker reported 40 images
using 38.81 GB and 30 volumes using 2.208 GB. The failure occurred inside the
Docker engine while installing locked dependencies. The only failed build
container removed was the task-created `dazzling_pike`; no broad prune or
unknown-resource deletion was performed. Application image digests are
therefore unavailable.

Complete private evidence, artifact hashes and cleanup records are stored under
`/Users/sonalingowda/alphalens-operational-20261105/staging-20261111/`.
The sanitized manifest is `evidence-manifest.json`; its file hash is recorded
outside this document after capture as
`c39614f67ba085d803e2174cf464267c7a0e426be563e2f713a0ba7eb4585408`.
Gate 06 and Gate 07 remain blocked, and
Gate 09 remains uncertified.

## Required next step

Provision or safely reclaim verified Docker engine storage without touching
owner or unknown resources, then rerun the exact source-identified backend and
frontend image builds and the full container staging smoke. External staging,
production deployment and release certification still require separate
approval.
