# AlphaLens Batch 6O — Prospective BTCUSDT/5m Research Protocol Draft

Date: 2026-10-26  
Status: **DRAFT / NOT APPROVED / NOT EXECUTED**  
Market: Binance BTCUSDT only  
Timeframe: closed 5-minute candles, UTC

This protocol preserves the accepted five-feature contract but authorizes no data collection, protected-test access, fitting, validation, packaging, activation, scoring, ranking, or deployment.

## Frozen contract inputs

| Field | Value |
|---|---|
| Model family/version | `btcusdt_5m_expected_move_ridge` / `1.0.0` |
| Schema hash | `03ba127a57ec783dc2cb5b6e5af15a79d38a1b51914f4b0df9a6b38e2ec5cbe0` |
| Target | `absolute_forward_log_move`, `expected_move_absolute_log_move.v1.0.0` |
| Target hash | `14b0c2c7ca829ee014c629d95d68c251b5005b24718ad8977993152d5a510405` |
| Formula | `abs(log(close[t+5] / close[t]))` |
| Horizon | Five completed 5m candles / 25 minutes |
| Features | ATR, candle range fraction, Bollinger width, rolling standard deviation 20, ADX, in the approved order |

The historical source file and result remain immutable negative/precedent evidence. The original evaluated source file SHA-256 is `f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`; its canonical candle hash is `396f715032ef2e1a5d6f0325803eb0b4e7095b64c97c17fdf38ae9643f4531d4`; its result remains 4/5 with the correlation criterion failed.

## Prospective boundaries

The forward-data documents propose, but do not approve:

| Boundary | Candidate value | Status |
|---|---|---|
| Development collection | `2026-10-13T00:00:00Z` through `2027-01-10T23:55:00Z` | Planning only |
| Protected test | `2027-01-11T00:00:00Z` through `2027-02-09T23:55:00Z` | Planning only; not sealed |
| Historical evaluated cutoff | `2026-10-12T10:05:00Z` | Excluded from new selection/diagnostics |

Before execution, the owner must approve an immutable source-availability cutoff, exact final boundaries, and a sealed protected-test artifact. The historical evaluated window cannot be reused for new model selection or acceptance decisions.

## Chronology, warmup and embargo

The prospective research must use expanding chronological folds with minimum train 500, test size 100, step size 100, and the historical 250-observation purge. At 5m, 250 observations equal 20h50m. The target horizon adds five future candles / 25 minutes, and the full feature pipeline requires at least 200 closed-candle pre-roll observations.

The 250-row gap is the minimum train/test separation because it covers EMA-200 pre-roll and exceeds the target horizon. It is not runtime feature warmup. The candidate planning documents show development and protected windows adjacent in calendar time and do not prove a materialized 250-row gap. The split manifest must therefore record the purge rows and demonstrate that no training row or target label crosses the test boundary before execution is approved.

## Protected-test controls

Before any development observation is examined:

1. Materialize the protected-test candle artifact and manifest with exact UTC timestamps, counts, source availability cutoff, source hash, canonical hash, and label-completion boundary.
2. Hash and seal it in an access-controlled location separate from development data and the fitting environment.
3. Record the seal hash, sealing timestamp, owner authorization, independent reviewer, permitted evaluator identity, and one-way access log.
4. Deny protected-test reads to feature selection, preprocessing, tuning, model selection, debugging, diagnostics, and development reporting.
5. Permit access only in a separately authorized final evaluation step after development configuration and artifact candidates are immutable.
6. Preserve the protected artifact and access log, including unfavorable results.

The independent reviewer must not be the person who selected features, hyperparameters, or the final model from development results. The protected test cannot be relabeled from the historical source or inferred from absent records.

## Synchronized lineage

Every prospective run must create new immutable records linking:

1. Candle source artifact, exchange/symbol/timeframe, complete-candle rule, source cutoff, ingestion ID, requested/actual count, gap/duplicate result, and source/canonical hashes.
2. Feature run, exact five-feature order, definition versions, registry hash, pipeline version, Decimal quantum, availability contract, pre-roll, and point-in-time dependency checks.
3. Target run, target name/version/hash, formula, five-candle horizon, label availability after prediction cutoff, and exact source/feature parents.
4. Split plan, chronological boundaries, train/purge/test membership, split hash, protected-test seal reference, and no-overlap proof.
5. Validation run, code commit/tree, lockfile/environment hashes, configuration hash, random-state record, per-fold predictions/actuals/metrics, and final result hash.
6. Candidate artifact only if all five criteria pass and independent approval is recorded; never backfill historical UUIDs or rewrite prior evidence.

## Model-fitting isolation and reproducibility

If separately authorized, fitting must run in a disposable isolated research database/filesystem with no protected-test mount, no production credentials, no external network after data preparation, and no writes to original source/evidence directories. It must record exact source commit/tree and script hash; dataset, feature, target, split, registry and configuration hashes; interpreter and lockfile identities; all random states; model parameters and preprocessing state; per-fold outputs and recomputation checks; reviewer identity; command lines; exit codes; and immutable evidence hashes.

No fitting is allowed until the owner approves the dataset boundaries and the research reviewer approves this preregistration. A failed criterion stops approval; it cannot trigger threshold relaxation, favorable-fold selection, feature substitution, or artifact promotion.

## Frozen acceptance criteria

All five historical criteria remain mandatory and unchanged:

1. R² improvement over ATR×1.5 baseline `> 0.01`.
2. Correlation improvement `> 0.05`.
3. MAE reduction `> 5%`.
4. Monotonic predicted/actual calibration-bin means.
5. Positive MAE and R² improvement in every declared 30-day regime.

The historical result is 4/5 because correlation improvement was `+0.008663260`. It remains unapproved and cannot be repaired by relabeling, retuning, favorable-fold selection, or reusing the evaluated source.

## Economic evaluation boundary

Predictive acceptance and economic evaluation are separate. No economic claim may be made from the five model criteria. A later separately approved study must preregister direction mapping, entry/exit/invalidation rules, exchange fees, spread, slippage, latency, position sizing, opportunity overlap, drawdown, net expectancy, losing signals, regime coverage, and outcome timing. The non-negative expected-move magnitude cannot be converted into profit or win probability without independent evidence.

## Required owner approvals before Batch 6O execution

- [ ] Approve this protocol version and its final SHA-256.
- [ ] Approve the prospective dataset source and availability cutoff.
- [ ] Approve exact development/protected UTC boundaries and split manifest.
- [ ] Approve the 250-observation purge/embargo and five-candle label boundary.
- [ ] Approve protected-test sealing, access authority, and independent reviewer.
- [ ] Approve isolated database/filesystem, compute, credentials, and allowed writes.
- [ ] Approve the exact five-feature schema/target hashes listed above.
- [ ] Approve fitting and development-only walk-forward execution.
- [ ] Approve independent review and artifact-promotion authority separately.
- [ ] Approve a separate economic-evaluation protocol if economic claims are later requested.

## Current status

**Batch 6N acceptance: ACCEPTED after targeted scope-binding repair.**

**Batch 6O: protocol draft prepared, not approved, not executed.** No data was collected, no protected data was accessed, no model was fitted, and no artifact was packaged or activated.

Gate 6 remains **NOT VALIDATED**. Gate 7 remains **BLOCKED**.
