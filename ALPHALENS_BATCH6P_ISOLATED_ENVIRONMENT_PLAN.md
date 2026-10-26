# AlphaLens Batch 6P — Isolated Environment Plan

Date: 2026-10-26  
Status: **PROPOSED / NOT AUTHORIZED TO EXECUTE**

## Proposed naming and boundaries

Use a unique run identifier and keep all writes outside the original checkout:

```text
worktree: /private/tmp/alphalens-batch6o-research-<run-id>
evidence: /private/tmp/alphalens-batch6o-evidence-<run-id>/
raw:      /private/tmp/alphalens-batch6o-evidence-<run-id>/raw/
canonical:/private/tmp/alphalens-batch6o-evidence-<run-id>/canonical/
lineage:  /private/tmp/alphalens-batch6o-evidence-<run-id>/lineage/
logs:     /private/tmp/alphalens-batch6o-evidence-<run-id>/logs/
```

No directory above was created by Batch 6P.

## Proposed disposable services

Pure offline feature/target computation may use files only. If the existing
application persistence interfaces are required for an authorized run, use a
new disposable PostgreSQL database such as `alphalens_batch6o_dev_<run-id>` on
a new local-only port, not the protected/default endpoint or the existing
Batch 6E disposable database. Redis is not required by the research protocol;
if an application harness requires it, use a separately named local-only
instance and port. No service is started or initialized here.

Denied mounts and destinations:

- original repository checkout and its dirty worktree;
- protected PostgreSQL/Redis data directories and ports;
- Docker/Colima volumes;
- preserved research evidence and backups;
- protected-test custodian storage;
- production credentials and deployment configuration.

## Reproducibility capture

The future run must capture source commit/tree, `backend/uv.lock` hash,
`backend/pyproject.toml` hash, Python/interpreter version, NumPy/scikit-learn
versions, contract schema/target hashes, registry hash, configuration hash,
all random-state values, commands, exit codes, and evidence hashes. The
approved source baseline is commit
`948913a7e2df47b785bef655deaa4843c7589bcf` / tree
`d5c58d5b7c001c7b84889a80831a0d8c9b054b73`.

## Proposed, unauthorized setup sequence

The following is a reviewable sequence only. Every line is **NOT AUTHORIZED TO
EXECUTE** in Batch 6P:

```text
# NOT AUTHORIZED
git worktree add --detach /private/tmp/alphalens-batch6o-research-<run-id> 948913a7e2df47b785bef655deaa4843c7589bcf
# NOT AUTHORIZED: create evidence directories listed above
# NOT AUTHORIZED: create a disposable local PostgreSQL database/schema
# NOT AUTHORIZED: run Alembic against that disposable target
# NOT AUTHORIZED: install or synchronize dependencies with uv --locked
# NOT AUTHORIZED: run source acquisition, feature generation, target generation, or fitting
# NOT AUTHORIZED: start or connect to protected/default services
```

## Cleanup and retention

No automatic cleanup is permitted. After an authorized run, failed and
successful evidence, raw pages, manifests, logs, lineage, configuration and
review receipts must be retained under an immutable run ID. Disposable service
shutdown and deletion require a separate owner-approved cleanup decision after
backup/hash verification; protected resources are never cleanup targets.

## Environment status

- Verified: Python 3.11.14 and `uv 0.12.1` are available; no installation was
  performed.
- Verified: approximately 17 GiB host free space at audit time.
- Proposed: isolated worktree, evidence root, database, optional Redis, and
  credentials.
- Not authorized: provisioning, initialization, dependency installation,
  service startup, database migration, acquisition, fitting, or evaluation.
