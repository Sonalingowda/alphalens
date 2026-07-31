# AlphaLens v2 Phase 1 Historical Expansion Frozen Baseline

## Status

- **Freeze date:** 2026-08-01
- **Human authority:** Explicit instruction to freeze Phase 1 after P1-08
- **P1-08 implementation commit:** `6555403f601b9c6bb145db8b830f59bc3f573dd0`
- **Architecture audit:** `ALPHALENS_V2_PHASE_1_ARCHITECTURE_AUDIT.md`
- **Implementation status:** Frozen
- **Operational archive verdict:** Not evaluated in this worktree

This baseline freezes the Phase 1 historical expansion implementation. It does
not authorize Phase 2 and does not claim that an unavailable real historical
archive satisfies the approved adequacy policy.

## Frozen Task Baseline

| Task | Commit | Frozen result |
| --- | --- | --- |
| P1-01 | Policy embodied by P1-02 commit and approved policy document | Acquisition, correction, conflict, availability, and adequacy rules frozen. |
| P1-02 | `3f74cc4b568d7c67b0da7b048d6aae106b089894` | Immutable historical coverage snapshots. |
| P1-03 | `ba55adbe37117279aa80623bb1a0022defa288ed` | Resumable bounded historical orchestration. |
| P1-04 | `332346bf94cf9d982f5b4fa1286fef83bfd01aec` | Immutable source-conflict handling. |
| P1-05 | `b798232db41749e6e20faea782ab7e1cb9977853` | Deterministic 5m/10m/15m synchronization. |
| P1-06 | `77fe8cd30da5f89c3293e226390c1546533b44de` | Historical freshness and acquisition adequacy reporting. |
| P1-07 | `9d6288e5741d88a00dfc3802255db788905f6574` | Read-only deterministic operational inspection. |
| P1-08 | `6555403f601b9c6bb145db8b830f59bc3f573dd0` | Immutable historical expansion readiness framework. |

## Frozen Scope

- Instrument: BTC/USD only.
- Native timeframes: 5m and 15m.
- Derived timeframe: 10m from exactly two complete adjacent 5m candles.
- Time standard: UTC.
- Provider policy: approved Kraken acquisition contract.
- Canonical behavior: insert or exact replay only; never overwrite conflicts.
- Adequacy behavior: acquisition-level Candidate C policy only.
- Readiness behavior: ready for later adequacy evaluation or explicitly
  blocked; never Phase 2 authorization.

## Frozen Guarantees

1. Canonical market evidence is immutable and Decimal-exact.
2. Coverage snapshots retain exact ordered candle and source-batch membership.
3. Acquisition is bounded, auditable, resumable, and idempotent.
4. Source conflicts retain both canonical and incoming evidence.
5. Every 10m candle retains two exact ordered 5m source members.
6. Quality is evaluated independently for 5m, 10m, and 15m.
7. Inspection is read-only and point-in-time.
8. Readiness reports are content-addressed, append-only, reproducible, and
   fail closed.
9. No readiness report can authorize Phase 2.
10. Missing, inadequate, conflicting, or corrupted evidence is reported as a
    blocker rather than repaired or fabricated.

## Database Baseline

| Revision | Purpose |
| --- | --- |
| `20260731_0028` | Historical coverage snapshots and memberships. |
| `20260731_0029` | Acquisition attempts, outcomes, and checkpoints. |
| `20260801_0030` | Immutable source conflicts. |
| `20260801_0031` | 10m derivation membership and synchronized coverage. |
| `20260802_0032` | Historical quality reports. |
| `20260802_0033` | Historical expansion readiness reports. |

The frozen migration graph has one head: `20260802_0033`.

## Validation Baseline

- Ruff: pass.
- Python compilation: pass.
- Focused Phase 1 regression suite: 86 tests passed.
- Full backend regression suite: 264 tests passed.
- Alembic single-head validation: pass.
- Offline PostgreSQL migration rendering: pass.
- Architecture audit: pass after recorded cleanup.

A live database validation was not represented as passing because no real
evidence database was available.

## Governing Artifact Hash Manifest

Hashes are SHA-256 over exact file bytes at freeze preparation.

| Artifact | SHA-256 |
| --- | --- |
| `AGENTS.md` | `49017eb9621b0132764582561b41bb1b5732223545ccf89a198fa773fd43faf0` |
| `ALPHALENS_V2_PROJECT_CONSTITUTION.md` | `24ffe86161e4116708f382d6f38cd7932d446df6595cbc41b0481b6b6d2ad3e8` |
| `ALPHALENS_V2_CORE_INTELLIGENCE_SPECIFICATION.md` | `22f339f4a451d1fee258c4f2d6ce5ddffdc78e0c720b2495916977984cc8b276` |
| `ALPHALENS_V2_IMPLEMENTATION_PLAN.md` | `ab81881ab458cffa6f0fe8ba322b5e6d0f9f7e2cf5b947762371935e29b9264a` |
| `ALPHALENS_V2_INTRADAY_DATA_ACQUISITION_POLICY.md` | `7582a39fa873d2eb5e534c3227c664946950571dd98d593a869daefaf90f535c` |

## Core Implementation Hash Manifest

| Artifact | SHA-256 |
| --- | --- |
| `backend/app/market_data/history.py` | `29284b3a7c7eeab7983af2149a7a8063175f63e7ef8fb4b40bd5dfe2a8ebe30f` |
| `backend/app/market_data/coverage.py` | `df8519e5707f5763612706bf64c74172629497655628c81231a00ff54a5937ef` |
| `backend/app/market_data/orchestration.py` | `ecf1bcc26889141c1150d0fee4c7fed6a88317a972c9bb7e00ef1f5d0e4a74f3` |
| `backend/app/market_data/conflicts.py` | `f449afc7e833070e07994469c5ce1de3b3038c0a367684c8bbbab2e320b67b32` |
| `backend/app/market_data/synchronization.py` | `56ecd9c3d16d30a5053ef8193ac6c3cc1ea566a34f907a80eca1d15e50caf44c` |
| `backend/app/market_data/quality.py` | `01198c01556dc0dc5fc3d6ad054839a48a8fe7417998414496103a51660b71aa` |
| `backend/app/market_data/inspection.py` | `e19b1e94e5cd4f9abf685bf2f926f33698e378a6d31188b72aab1db6dfa03355` |
| `backend/app/market_data/readiness.py` | `d3a2afbf13faab1f838a12234797bb3b349f4a8c374120bfc1485912b24a4da7` |
| `backend/app/market_data/readiness_validation.py` | `64cefee83aa37dde1736cf86a31dc861e56b40a571d858da2226c9330fdeb5c8` |
| `backend/app/persistence/candles.py` | `d1e933028f36db5526ff15971c215fdce1148689de103e9b866a9fbb6bc16700` |
| `backend/app/persistence/coverage.py` | `cb733145cdfdf3960204b82e891ea05067e41aded34b1069bde2be9cf574f008` |
| `backend/app/persistence/historical_orchestration.py` | `0f59a4b42c2657cda4d6f1a3ccd48ae69e22b318f137085d1d52c66fffb21f31` |
| `backend/app/persistence/conflicts.py` | `a2cfb436a3dc93938e5301c2be30e54f5b252e9e055e8851f2e260b2a07bd324` |
| `backend/app/persistence/synchronization.py` | `ed48208b2fa00f132619dcf68b3d7957f00c1720ee7d0083b927add11b200079` |
| `backend/app/persistence/quality.py` | `80ecb8e0aff9262a98f4455bba05a2d6f4dd0212be652b66703311fbbe95b583` |
| `backend/app/persistence/inspection.py` | `75d58888f34014310e80838527ba85ca7ba2829db694a16aadbcccc0133c6c67` |
| `backend/app/persistence/readiness.py` | `504fb6f34cd1c5f352477a04ffece004943867e97ece59bceb46650c00c338a4` |
| `backend/app/persistence/models.py` | `161529bd21d70eef58706ce05cbcc2f7bf34e0aba4fe5c487dc4681fbdea8eb2` |
| `backend/app/api/historical_inspection.py` | `58f6d1be5b25f81e67b89b0e3f821cd17d22d2c5fa820173471fc225ad4c555c` |
| `backend/app/historical_readiness.py` | `d08bb3e8ec9f4b96d3941e255af3bca65820c2a7150543e3c05f255ada31d8ac` |

## Migration Hash Manifest

| Artifact | SHA-256 |
| --- | --- |
| `backend/alembic/versions/20260731_0028_create_historical_coverage_snapshots.py` | `77ebba1bc2185ae4cfbcc450ee0b37389389bbdba7858707bbf47de886384c38` |
| `backend/alembic/versions/20260731_0029_create_historical_acquisition_checkpoints.py` | `11cb28b0ddc5bea52c0362c1b2a4c8ba6fbda7c1067e2171f9af7e463ebb20b3` |
| `backend/alembic/versions/20260801_0030_create_immutable_source_conflicts.py` | `f3bee0dfb531a2c3e62b5641d62631ce337b2291fb4ec8e8460f3c6de883926d` |
| `backend/alembic/versions/20260801_0031_create_synchronized_coverage.py` | `c4854df02005ae150ba711790e2e5bc08575c71b25eb28da4f9c142059c53e3a` |
| `backend/alembic/versions/20260802_0032_create_historical_quality_reports.py` | `d0bbe1098be83e5bba74c574c0b932b75a19bb2c821fb81d9ac1a915ebb19a2c` |
| `backend/alembic/versions/20260802_0033_create_historical_readiness_reports.py` | `a109125ccb1522ef6f4acdadf4aa7c20110e75f00c0f5645c867eb0b6a3e87da` |

## Test Hash Manifest

| Artifact | SHA-256 |
| --- | --- |
| `backend/tests/test_intraday_market_data.py` | `19e4c96799bd6eb1a74eb5df0dd3dc51a74a7978580efbed0a9410cda5ea9b9d` |
| `backend/tests/test_historical_coverage.py` | `9b0d82f84dfdb5c7eab99e2e5040e18f3f5ae1943abb93006238db3e36a84fe3` |
| `backend/tests/test_historical_orchestration.py` | `da9c0e4a40303743f063d594b7db9fae3c10cef2a92169052ca168dd0c916fd5` |
| `backend/tests/test_source_conflicts.py` | `7fe13b1aa7172426ebd99ec8ec0fad8ff75724e79b136709c2283fd37ff77d27` |
| `backend/tests/test_historical_synchronization.py` | `41e2c1a86ce3994fba63ea95518a0ec157d334091267d1b4d11fd387aa1c5413` |
| `backend/tests/test_historical_quality.py` | `6247f57513eb96a5d183e671873a6e4a05662c81374f065b5cd4328c5da3f50c` |
| `backend/tests/test_historical_inspection.py` | `4916dd2290fbfe1b68ca86c813d124ce2b9015e3bd0006a2355ed81eb23a0b6b` |
| `backend/tests/test_historical_readiness.py` | `43469fb47ec1359675f16a132b1c6a919bd7533ee9640c34f878979e41abc407` |

## Operational Readiness Procedure

After applying migrations to the authorized evidence database, produce the
real immutable verdict with an explicit UTC cutoff:

```bash
python -m app.historical_readiness --as-of 2026-08-01T00:00:00Z
```

The timestamp above is an invocation example, not a frozen operational cutoff.
The operator must choose and record the actual point-in-time cutoff for the
evidence being frozen.

## Change Control

Any change to a hashed artifact requires:

1. an explicit approved task;
2. rationale and impact analysis;
3. compatibility treatment for existing immutable evidence;
4. a version change when semantics or hashes can change;
5. focused and full regression validation;
6. an updated architecture audit; and
7. a new baseline manifest rather than silent alteration of this baseline.

## Phase Boundary

Phase 1 completion and freeze do not authorize Phase 2. Feature expansion,
labels, datasets, model research, decision generation, ranking, confidence,
scanner, chart, or UI work requires separate explicit approval.
