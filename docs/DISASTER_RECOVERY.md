# AlphaLens Disaster Recovery Notes

## Recovery priorities

1. Protect and restore PostgreSQL canonical data.
2. Verify migration and immutable-record integrity.
3. Restore the API and workers.
4. Rebuild Redis coordination state; never restore it as canonical data.
5. Restore the frontend.

## PostgreSQL

Operators SHALL configure encrypted backups and point-in-time recovery outside the application containers. Backups MUST include the `alembic_version` table. Restore drills SHOULD occur on an isolated database and verify: migration head equality, immutable table constraints/triggers, aggregate hashes, version histories, and representative as-of queries.

Before a destructive migration or application rollback, take and verify a fresh backup. Never edit immutable aggregate rows to repair an incident; restore or append a contract-authorized successor record.

## Redis

Redis contains cache entries, locks, task references, and worker heartbeats only. On loss, recreate the service, invalidate all caches, and re-enqueue tasks from durable PostgreSQL/audit state where the governing service contract permits. Redis recovery SHALL NOT synthesize canonical records.

## Application recovery

Redeploy the last verified immutable images and run Alembic to the image-compatible head. Keep readiness disabled until PostgreSQL, schema, Redis, and required production artifacts pass validation. Preserve logs, metrics, database backup identifiers, image digests, migration heads, and incident timestamps as the recovery audit record.

Recovery is complete only after deterministic replay checks demonstrate identical hashes for selected immutable inputs and the operator documents any unavailable or quarantined scope.
