# AlphaLens Batch 6P — Operational Readiness Report

Date: 2026-10-26  
Status: **OPERATIONAL READINESS ONLY / RESEARCH NOT AUTHORIZED**

## Decision summary

Batch 6N engineering is accepted and the Batch 6O protocol is owner-approved
as a design, but no prospective data exists or has been accessed. This batch
performed only offline checks and prepared future execution boundaries.

## Provenance verification

| Item | Verified value |
|---|---|
| Isolated baseline commit | `948913a7e2df47b785bef655deaa4843c7589bcf` |
| Isolated baseline tree | `d5c58d5b7c001c7b84889a80831a0d8c9b054b73` |
| Batch 6N acceptance report | SHA-256 `77dd135878dfac4a085c83bdd9cfd5905dda0d39e89139d344e23d9589c344be` |
| Batch 6O draft | SHA-256 `c6515e14ce6a41454cb3843f36ad55d62a7ae2c154e29521524c29acf1653dff` |
| Approved Batch 6O package | SHA-256 `ab1c18f7f434e6971527a6ab48716ecfab102c41b64bb7ebe37af534bb5fcb53` |
| Phase 0 freeze | SHA-256 `e975faee3c45726dfe92425aeb117042b46c4b7760824d905550721854ab3367`; preserved at `/private/tmp/alphalens-batch6d-isolated-infrastructure-20261026/` because absent from this worktree |
| Schema hash | `03ba127a57ec783dc2cb5b6e5af15a79d38a1b51914f4b0df9a6b38e2ec5cbe0` |
| Target hash | `14b0c2c7ca829ee014c629d95d68c251b5005b24718ad8977993152d5a510405` |
| Python lockfile | `backend/uv.lock`, SHA-256 `a5e324fb08966c96f8c72afc00917b2e333a3cecb61262a6a9899c633c052959` |
| Project declaration | `backend/pyproject.toml`, SHA-256 `549958cda8a13fdc019e3fe4e7b2ce44aae2b57158819719f9879dc1eb7e3610` |

The missing freeze file is a provenance-location issue, not a hash mismatch;
its independently preserved copy matches the owner-supplied hash. No source
provenance mismatch was found.

## Readiness inventory

### Verified

- Registered intraday feature pipeline: `backend/app/features/intraday_pipeline.py`,
  pipeline `2.7.0`; registry/hash support is in `backend/app/features/registry.py`.
- Contract-only five-feature boundary:
  `backend/app/inference/btcusdt_5m_contract.py`.
- Target/feature hash recomputation matches the approved values.
- Existing Binance ingestion implementation is
  `backend/scripts/run_live_ingestion_pipeline.py`; its endpoint is
  `https://api.binance.com/api/v3/klines` with `BTCUSDT`/`5m` behavior.
- Existing model-ready builder is
  `backend/app/research/dataset.py::build_model_ready_dataset`, but it encodes
  the separate BTC/USD/1d `forward_log_return` contract and must not be used
  as an implicit Batch 6O materializer.
- Existing generic split code is
  `backend/app/validation/splits.py`; its defaults differ from the approved
  Batch 6O historical configuration and must be explicitly configured.
- Existing artifact lineage and packaging interfaces are
  `backend/app/inference/lineage.py`, `backend/app/inference/artifact.py`, and
  `backend/app/persistence/model_inference.py`.
- Python 3.11.14 and `uv 0.12.1` are available in the current environment.
- Offline contract test: 6 passed, exit code 0.
- Ruff on the contract module/tests: passed, exit code 0.
- Host free space observed: approximately 17 GiB; no installation or large
  artifact operation was attempted.

### Proposed, not created

- Disposable development evidence root and isolated database described in the
  environment plan.
- Future Binance raw-page and canonical-candle manifests.
- Future protected custodian storage, seal receipt, and append-only access log.
- Future research run, split manifest, lineage records, and reviewer receipt.

### Missing operational prerequisites

- Actual prospective candles and source-availability cutoff.
- Owner-approved acquisition execution authorization.
- Independent custodian and independent research reviewer identities.
- Final source/canonical hashes, counts, gap report, and label-completion proof.
- Isolated research database/filesystem approval and write location.
- Explicit future credentials/secret reference, if Binance access requires one.
- A Batch 6O materialization path for the approved absolute-move target and
  five-feature contract; the existing daily dataset builder is not equivalent.
- Development fitting authorization, protected-test sealing authorization,
  protected evaluation authorization, and later artifact-promotion approval.

## Untouched services and resources

The original dirty checkout, protected Docker/Colima resources, existing
PostgreSQL/Redis services, historical datasets, evidence, backups, and cloud
resources were not connected to or modified. No external endpoint was called.

## Acceptance status

| Area | Status |
|---|---|
| Source and contract provenance | VERIFIED |
| Batch 6N engineering | OWNER APPROVED / ACCEPTED |
| Batch 6O protocol design | OWNER APPROVED |
| Prospective data availability | BLOCKED; data does not yet exist in evidence |
| Research environment | PROPOSED only |
| Research execution | NOT AUTHORIZED |
| Gate 6 | NOT VALIDATED |
| Gate 7 | BLOCKED |

Smallest next executable batch: owner authorizes setup of the isolated
development environment and, separately, development-only source acquisition.
Neither authorization permits protected-test access, model fitting, artifact
packaging, scoring, ranking, or deployment.
