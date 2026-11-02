# AlphaLens Database Failure Repair — 2026-11-03

## Scope

This repair addresses the failed six-hour acceptance in
`/private/tmp/alphalens-six-hour-acceptance-20261103/reports`. The failed
observation evidence was preserved unchanged.

## Root cause

The worker reached `ThesisIntelligenceService.attach_assessment()` while the
configured PostgreSQL database did not have the persistent-thesis migration
available to that worker connection. The missing relation was
`public.opportunity_thesis_assessments`.

The repository already contains the reviewed implementation in migration
`20261027_0042_create_persistent_theses.py`, followed by head migration
`20261027_0043_add_thesis_detection_family.py`. The documented acceptance
command launched `local_market_worker.py` directly and did not run an Alembic
schema preflight. The failure was therefore an unapplied-schema-readiness
failure, not a missing migration implementation or a Thesis Intelligence
bypass.

The acceptance and API configuration both target `alphalens_local_8bcdc1fc`
on `127.0.0.1:55461`, with `public` included in the search path. No connection
or search-path mismatch was found.

## Preservation and schema verification

- Failed evidence retained under
  `/private/tmp/alphalens-six-hour-acceptance-20261103/reports`.
- Existing failed-observation backup verified with `pg_restore --list`:
  `/private/tmp/alphalens-continuity-recovery-baseline-20261102.dump`.
- Fresh preflight backup created without overwriting existing backups:
  `/private/tmp/alphalens-six-hour-acceptance-20261103/database-preflight-20261103.dump`.
- Fresh backup SHA-256:
  `1adbb5d09a6102d9da3ab50c2d0d891602fdff88a6f174248ca865e80dfa1cfc`.
- Before smoke: Alembic `20261027_0043`, thesis tables present, 6 theses, 6
  assessments, 17 lifecycle events.
- `alembic upgrade head` was run twice against the configured database; both
  executions were idempotent at `20261027_0043 (head)`. No migration was
  applied because the database was already current at repair time.

## Code repair

`backend/scripts/run_market_acceptance.py` now verifies the backup and runs
`python -m alembic upgrade head` from the backend directory before starting a
worker. A migration failure aborts the acceptance before any market-data
worker starts. Relative Python paths are resolved before changing directory.

`backend/tests/test_market_acceptance_runner.py` covers both successful
preflight invocation and fail-closed behavior for an error containing the
missing thesis-assessment relation.

## Bounded smoke evidence

- Duration: 300.139 seconds requested/observed.
- Genuine Binance finalized candles: 1.
- Pipeline runs: 1.
- Processing errors: 0.
- Processor result: `PROCESSED`.
- Reconnects: 0.
- Checkpoint: sequence 1, status `READY`, no missing interval, committed
  candle `2026-11-02T08:35:00Z`.
- Final worker state: `STOPPED` after clean bounded shutdown.
- Smoke report: `/private/tmp/alphalens-db-repair-smoke-20261103/reports-1793608676`.

Post-smoke, the database still had 6 theses and 6 assessments. The assessment
fingerprint was unchanged. One append-only lifecycle event was added by the
real candle observation; no historical assessment or original thesis geometry
was rewritten.

## Validation

- Backend suite: **960 passed, 30 skipped**.
- New migration-preflight tests: **2 passed**.
- Thesis Intelligence and worker ownership tests: passed.
- No six-hour observation was started.
- No protected checkout, model, threshold, or protected-test data was changed.

