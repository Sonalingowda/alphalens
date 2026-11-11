# Gate 06–09 execution status

Date: 2026-11-11
Branch: `gate9d2/owner-infrastructure-20261105`
Evidence baseline: `ba760211b2c4a8a76a837b242fd7e0576099f589`

## Gate 06 result

Gate 06 remains **BLOCKED / NOT VALIDATED**. No model artifact was created,
activated, or promoted, and the protected test was not accessed.

The retained historical source is outside this repository at:

`/Users/sonalingowda/Downloads/alphalens/backend/evidence/expected_move_binance_btcusdt_5m.json`

Read-only identity checks on 2026-11-11 found:

- file SHA-256: `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`;
- 25,920 rows, `BTCUSDT`, `5m`, and the documented Binance source metadata;
- canonical candle dataset hash recorded by the protocol:
  `396f715032ef2e1a5d6f0325803eb0b4e7095b64c97c17fdf38ae9643f4531d4`.

The historical result artifact is recoverable only from the pre-release Git
object `1630b1ec2c66a5857c84d4e950650d7b5766b82d`, not from the current release
tree. Its recorded run used 251 expanding folds, 25,100 test observations,
500-observation minimum training, 100-observation tests, 100-observation
steps, a 250-observation purge, five-candle target horizon, and 30-day regime
analysis. The recorded aggregate result was:

- Ridge MAE `0.0012136077545989285` versus ATR baseline
  `0.001309287747582574`;
- R² improvement `+0.09218926671991223`;
- correlation improvement `+0.008663260` (Ridge `0.43320473501007145`,
  ATR `0.43383191434221813`).

The exact frozen criteria require:

1. R² improvement over ATR×1.5 `> 0.01`;
2. correlation improvement `> 0.05`;
3. MAE reduction `> 5%`;
4. monotonic predicted/actual calibration-bin means; and
5. positive MAE and R² improvement in every declared 30-day regime.

Criterion 2 failed: `+0.008663260` is below `+0.05`. The legacy script also
contained a governance defect: it returned `VALIDATED` for `criteria_met >= 4`.
That result label conflicts with the frozen all-five-criteria protocol. The
current repository correctly preserves the run as negative evidence and keeps
Gate 06 unvalidated; the legacy script was not restored or executed against
the owner database.

## Reproducibility and integrity audit

The source hash, source identity, chronology parameters, feature/target
definitions, purge rule, and recorded aggregate result were independently
reconciled from the retained source and Git history. A fresh numerical
re-execution was **not claimed** because the current release does not contain
the historical research runner/result lineage, and reconstructing it from
history would not establish that the exact original environment, dependency
versions, feature implementation, random state, and per-fold evidence were
unchanged. The historical result therefore remains recorded evidence, not a
new certification.

The retained protocol explicitly requires point-in-time features, chronological
folds, a purge/embargo, immutable source hashes, and a separately sealed
protected period. No protected rows were read. No synthetic rows were written
to PostgreSQL, and no production artifact was produced.

## Gate 07

Gate 07 remains **BLOCKED** on the absence of a validated predictive artifact.
Model-independent runtime behavior remains fail-closed: opportunity APIs label
model output as unavailable without an approved artifact, and the dashboard
reports model unavailability rather than fabricating scores or confidence.

## Gate 08 preparation

Deployment preparation may continue, but production deployment is **NOT
AUTHORIZED**. Existing work covers loopback runtime isolation, Clerk/CORS
boundaries, readiness versus artifact health, migration/recovery evidence, and
rollback documentation. Production image provenance, staging smoke evidence,
external monitoring, and an approved model remain release prerequisites.

## Gate 09 preparation

Certification automation and evidence collection may continue, but Gate 09 is
**NOT REACHABLE** while Gate 06 and Gate 07 are unresolved and no deployment
evidence exists. This document intentionally does not mark any blocked gate as
passed.

## Next bounded research package

Before any new fitting or validation, obtain explicit approval for a new
development-only run that freezes: the source-availability cutoff, development
and protected windows, the 250-row purge, the 200-candle feature pre-roll, the
five-candle label extension, the exact feature/target hashes, dependency
lockfile, random-state policy, per-fold evidence retention, and independent
protected-test custodian/evaluator. The five criteria and thresholds remain
unchanged. Any new run must use a new lineage and must preserve unfavorable
results.
