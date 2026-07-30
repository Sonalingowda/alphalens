# AlphaLens v2 Phase 1 Approved Baseline

## Status

Phase 1 — Scope Freeze and Contract Alignment is complete and human approved
as of 2026-07-30.

This manifest identifies the exact governance documents that form the approved
AlphaLens v2 implementation baseline. The document hashes are normative for
change detection.

## Approved Documents

| Document | SHA-256 |
| --- | --- |
| `ALPHALENS_V2_MIGRATION_PLAN.md` | `8ac1e60159ddc1776f334c7eba9e8a2606ade863f452400e1237e81d1c297b2c` |
| `COMPONENT_AUDIT.md` | `96c20897da37bfef99d311dd045d920d298163ce86c8430f95e5c3ea31a58914` |
| `IMPLEMENTATION_ORDER.md` | `7c0aff728bce715fdc224046fb1cfdeb2deb48845a393cc030c405ef2b0676a1` |
| `TARGET_ARCHITECTURE.md` | `101583eaf50de0ec3962428b6250ecbbeae0f4413c82222403f584fff962f60a` |
| `RISK_ASSESSMENT.md` | `3fd744e8c209af812230385d22969305c5322a16a527bb5595de104a69234401` |
| `ASSUMPTIONS_AND_UNKNOWNS.md` | `fc75db2cc37ee618dd1523d47b2aae9af8e25de76d359a4b249dede84ef0cd3f` |
| `ALPHALENS_V2_PRODUCT_CONTRACT.md` | `89525bd09cafbb4fff3d8db26a2ddfc39f495f92d2264795c7a0d8030024a196` |
| `ALPHALENS_V2_DECISION_CONTRACT.md` | `3b75a9f409cf43cdf0bfe5825bb20d26d8a214554345af65ead15bd5224818d6` |
| `ALPHALENS_V2_CONFIDENCE_POLICY.md` | `ee5e39a7c6c90fb6c268110c1b0a80db143548c48e559056ba29a2f226e8502d` |
| `ALPHALENS_V2_PHASE_1_ALIGNMENT_RECORD.md` | `cc9a490e490aef27cbf0506d1de2868925d7d0b1f6dee043000ba89910b51e7e` |

## Change Control

Phase 1 contracts and architecture references must not change unless a
documented architectural issue requires correction.

Every proposed change must include:

1. the architectural issue being addressed;
2. the reason the approved baseline cannot remain unchanged;
3. the exact document and section affected;
4. the proposed semantic change;
5. impact on downstream phases, interfaces, research evidence, and migration
   order;
6. compatibility and rollback considerations;
7. explicit human approval; and
8. regenerated hashes and an updated alignment record.

Silent edits, stylistic rewrites, retroactive semantic changes, and
implementation-led architecture changes are prohibited.

## Phase Boundary

This approval authorizes Phase 2 — Intraday Data Foundation according to
`IMPLEMENTATION_ORDER.md`.

It does not authorize intraday feature engineering, decision generation,
opportunity ranking, calibration implementation, scanner delivery, chart
overlay work, or v1 component removal.
