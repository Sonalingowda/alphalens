# AlphaLens Engineering Evidence Index

Status date: 2026-10-26. All entries refer to preserved evidence in the isolated checkout or explicitly recorded temporary evidence paths.

## Source and data anchors

| Evidence | Identity |
|---|---|
| Engineering baseline | Commit `948913a7e2df47b785bef655deaa4843c7589bcf`; tree `d5c58d5b7c001c7b84889a80831a0d8c9b054b73`. |
| Retained Binance dataset | SHA-256 `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`; diagnostic evidence only, not research approval. |
| Five-feature schema | `03ba127a57ec783dc2cb5b6e5af15a79d38a1b51914f4b0df9a6b38e2ec5cbe0`. |
| Five-feature target | `14b0c2c7ca829ee014c629d95d68c251b5005b24718ad8977993152d5a510405`. |
| Protected test | Frozen by protocol; not materialized, accessed, or evaluated. |

## Reports and acceptance receipts

| Report | SHA-256 | Result |
|---|---|---|
| `ALPHALENS_CHECKPOINT03_COMPLETION_REPORT.md` | `fdde7380cbae3ed32f84e87aa7583b936ff54fb9e14e91e4171e1bc55bade0c2` | PARTIAL |
| `ALPHALENS_BATCH6Q_END_TO_END_INTEGRATION_REPORT.md` | `305d3bfbdb09b93be3df7534057f1163b84643ca5caea7bc84c710d7b12aa5bb` | Integration partial |
| `ALPHALENS_PUBLIC_PRODUCT_READINESS_BACKLOG.md` | `70479e9d0512c61e7f10e152af1a42120602f8fb8168187370d84cb6c471e4e6` | Backlog source |
| `ALPHALENS_BATCH6S_CONTINUOUS_RUNTIME_REPORT.md` | `2beebb3d3f6ebacbaae772dc71f49d9b2b5a176427a0dd295cbc31a849309ef3` | Offline runtime PASS |
| `ALPHALENS_CHECKPOINT04_ACCEPTANCE_MATRIX.md` | `40e5d5351eaffe7daccb48051f6333fa5c402dd20d97fbaf8a8496b25ed88ccc` | Offline PASS; live not verified |
| `ALPHALENS_BATCH6T_LIVE_INGESTION_REPORT.md` | `742c58da5e9fad506bb01144b52b6ae3f450568fd42adb06a67674a5fd16db16` | Live PARTIAL |
| `ALPHALENS_CHECKPOINT04_LIVE_ACCEPTANCE_MATRIX.md` | `45d190fc4b87b28bc47d4ffb3dd26e223b56051c637888a7fe06dfd1abf4dcf0` | Live PARTIAL |
| `ALPHALENS_BATCH6P_OPERATIONAL_READINESS_REPORT.md` | see file-local hash record | Planning/readiness only |
| `ALPHALENS_BATCH6P_RESEARCH_EXECUTION_APPROVAL_MATRIX.md` | see file-local hash record | Execution not authorized |
| `ALPHALENS_BATCH6O_FINAL_PROTOCOL_APPROVAL_PACKAGE.md` | see file-local hash record | Protocol approved; data absent |
| `ALPHALENS_NEXT_ENGINEERING_EXECUTION_REPORT.md` | generated after this execution completes | Batch 6U and parallel engineering status |
| `ALPHALENS_BATCH6V_NOTIFICATION_RELIABILITY_REPORT.md` | pending final hash below | Durable notification queue and multi-worker safety |

## Runtime evidence

- Corrected 5m-only live trial JSON: `/private/tmp/alphalens-batch6t-fixed-report.json`, SHA-256 `02d72802ac036f82f97cb1da872ad8877ac611e0aeaea2a2c13e32bf054b77c1`.
- Corrected live checkpoint JSON: `/private/tmp/alphalens-batch6t-fixed-checkpoint.json`, SHA-256 `ff23ea61c8cf92ce0de273b391f9623d92e7540f18679e4935d502ec0883d0ca`.
- Live frontend screenshot: `/private/tmp/alphalens-batch6t-screens-20261026/dashboard-settled.png`, SHA-256 `626076baae41acc6a1c4777433780703bf1396881d6112758633b73d0c2c3891`.
- Batch 6T disposable PostgreSQL/Redis instances were isolated, loopback-bound and stopped after the bounded trial; their data directories were retained. No protected service was changed.
- Batch 6U disposable PostgreSQL backup/restore: dump SHA-256 `ef92a065346dfc071679e57a1ad28e1bb0666cf137ad814260e3891157605dc2`; source/restored schema count 65/65.
- Batch 6U post-write backup/restore: dump SHA-256 `d8c54cb6dcdb88946493f5e573081bf906f96b9576a1cffb4abcff7fc66c38ae`; matching source/restored row-count vector SHA-256 `b571129147d249d03f0379e3dfeb5d81c76323e444508d695acae59bcce9c36d`.
- Batch 6U live trial is supervised as PID `17902`; current checkpoint SHA-256 `cdd279e085ce1b4f323d926837ad611a5661981fc88d07188808d4f4dcd210e0`, sequence 4 at `2026-10-26T17:55:00Z`; final report pending completion.
- `backend/app/runtime_notification/delivery.py` SHA-256 `a7edec8f9b3c066fb33d051f805f3512621dd3a7671cffd4cf570e4f2fbdf0b2`.
- `backend/tests/test_runtime_notification_delivery.py` SHA-256 `5d9e2baa7b6442fb9fbb6eb6a6f3860cd98f34d53cfd5d7be5c29db77ce28422`.
- Latest backend verification: 938 passed, 23 skipped, 497 subtests; focused auth/delivery additions 9 passed.
- Batch 6V queue migration head: `20261026_0041`; queue integration tests 4 passed; separate OS-process claim/recovery probes passed.
- Batch 6V queue source hashes: migration `6f0081ddd1166747b244dee9b8f3f98b62f025ac59a1f97828d4e7765ee53a60`; service `7e7c0e286bb17e8301542f839f7dd6708600655c5740e453896482f870250a7f`; tests `54d89f1453f91532882cae3533c058f72c25514eca2224f6fecb0f61856fdb78`.
- Batch 6V report content SHA-256 (excluding its hash section): `819cea36f9999b6ccfa3cccb3fe8693a7c692e96b04562387dc59fe544c54b24`.

## Batch 6W private-local product evidence

- Local product report: `ALPHALENS_BATCH6W_LOCAL_PRODUCT_REPORT.md`; content hash excluding its final hash line `2ca6b725ee1e5f58c94a96b21b9b0da5aeadfc4caf07f5d577261c92dac5c80c`.
- Owner handover: `ALPHALENS_LOCAL_LIVE_HANDOVER.md`; full hash `533c70e879782db7c61d15baacc9ed180d2b29768851111b6f5b2cf5af06bb21`.
- Isolated local state: `/private/tmp/alphalens-local-20261026`; ports `13003` frontend, `18003` API, `55448` PostgreSQL, `56395` Redis.
- Latest genuine live checkpoint: sequence 2, finalized candle `2026-10-26T18:10:00Z`, document hash `67616b36c4ceaeed6ca238a1057ef74b3809427c516f2743db77c6b2f7c8cbad`.
- Latest market response source digest: `368dbde77110048c8c1cb9fb25e97f1577740e5bf1b7f26aa2ba200aadb7365e`; result hash `6297dc3efebd1ac795f282a41b0b466b2ad760b444dbb1c2a23219d737810ca0`.
- Latest opportunity response hash: `76b34ccb8acd0898ee1bf7bb48f1ba8c648385d8e3a27647aea026d788341d49`, empty candidates and model-unavailable status.
- Local product test result: backend `938 passed, 27 skipped, 497 subtests`; frontend `32 passed`, typecheck/lint/build passed; changed runtime Ruff passed.
- Batch 6W-HOTFIX-01 report: `ALPHALENS_BATCH6W_HOTFIX01_API_STABILITY_REPORT.md`; frontend 33 tests passed, typecheck/lint/build passed, 40/40 real Opportunities endpoint polls returned HTTP 200 over approximately 10 minutes.

## Verification commands

## Batch 6Z evidence

- Multi-hour report: `ALPHALENS_BATCH6Z_MULTI_HOUR_VERIFICATION_REPORT.md`.
- Acceptance matrix: `ALPHALENS_BATCH6Z_ACCEPTANCE_MATRIX.md`.
- Economic quality report: `ALPHALENS_BATCH6Z_ECONOMIC_QUALITY_REPORT.md`.
- Isolated live worker: PID `34264`, PostgreSQL `127.0.0.1:55458`, state `/private/tmp/alphalens-batch6z-live-20261026`; current run is IN PROGRESS.
- Browser evidence: `/private/tmp/alphalens-batch6z-live-20261026/dashboard.png` and `browser-observation-2.jsonl`; early polling is HTTP 200 with no console errors.
- Migration rollback evidence: disposable PostgreSQL `127.0.0.1:55459`, `20261027_0043` → `20261026_0041` → `20261027_0043`.
- Owner backup before Batch 6Z: `5d807adc945b6349b366c857bcaad9cc7b6d99e772f8a471f64006a7ceb7158e`.
- Durable backup copy: `/Users/sonalingowda/Library/Application Support/AlphaLens/local-state-backups/pre_batch6z_20261026T1948Z.dump`, identical hash.
- Finalization snapshot `2026-10-26T19:58:31Z`: worker PID `34264`, browser PID `34353`, 2 finalized candles, 0 errors/gaps/reconnects; six-hour end not reached.

## Batch 6XY evidence

- Master implementation report: `ALPHALENS_BATCH6XY_MASTER_IMPLEMENTATION_REPORT.md`; content hash `fbfe429a3b55050f6aba028f89abfc247bf7171b5f6bb6d078d9539a8da90793`.
- Acceptance matrix: `ALPHALENS_BATCH6XY_ACCEPTANCE_MATRIX.md`; content hash `46db47c4416b8ceadac226ff97a0594c95e4406b217b6c3fa027ecc9ec31a621`.
- Pre-migration database backup: `/private/tmp/alphalens-local-20261026/backups/pre_batch6xy_20261026T192816Z.dump`; SHA-256 `45a743f73d503f4ef5b5240c5d0100e7bed8191e893e411c0b54ebcaa278463a`; `pg_restore --list` succeeded.
- Current local thesis migration head: `20261027_0043`; external notifications remain disabled and no model artifact is approved.

- `backend/.venv/bin/python -m pytest -q` → 934 passed, 23 skipped, 497 subtests.
- `backend/.venv/bin/ruff check backend/app backend/tests` → passed.
- `PATH=/Users/sonalingowda/.nvm/versions/node/v22.23.3/bin:$PATH npm run test -- --run` → 32 passed.
- Same Node 22 environment: `npm run typecheck`, `npm run lint`, `npm run build` → passed.
- `git diff --check` → passed.

