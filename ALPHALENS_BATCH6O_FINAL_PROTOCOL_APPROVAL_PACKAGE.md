# AlphaLens Batch 6O — Final Prospective Research Protocol Approval Package

Date: 2026-10-26  
Status: **PROPOSED FOR EXPLICIT APPROVAL / NOT EXECUTED**  
Market: Binance BTCUSDT only  
Timeframe: closed 5-minute candles, UTC  
Architecture: `btcusdt_5m_expected_move_ridge` contract `1.0.0`

This package freezes a prospective research protocol for review. It authorizes
no acquisition, data access, fitting, validation, protected-test evaluation,
artifact packaging, scoring, ranking, notification, deployment, or Gate 6/7
certification.

## 1. Frozen contract identity

| Field | Frozen value |
|---|---|
| Model family | `btcusdt_5m_expected_move_ridge` |
| Contract version | `1.0.0` |
| Feature schema hash | `03ba127a57ec783dc2cb5b6e5af15a79d38a1b51914f4b0df9a6b38e2ec5cbe0` |
| Target hash | `14b0c2c7ca829ee014c629d95d68c251b5005b24718ad8977993152d5a510405` |
| Features, exact order | `average_true_range`, `candle_range_fraction`, `bollinger_band_width`, `rolling_standard_deviation_20`, `average_directional_index` |
| Target | `absolute_forward_log_move = abs(log(close[t+5] / close[t]))` |
| Target meaning | Dimensionless, non-negative magnitude only; not direction, signed return, profit, or win probability |
| Horizon | Five completed 5m candles / 25 minutes from prediction-candle close to target-candle close |
| Full feature pre-roll | At least 200 prior closed candles before each model observation |
| Research purge | 250 observations, separate from runtime pre-roll |

The historical dataset and 4/5 result remain immutable negative evidence. The
historical source file SHA-256 is
`f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc`; the
canonical candle hash is
`396f715032ef2e1a5d6f0325803eb0b4e7095b64c97c17fdf38ae9643f4531d4`.

## 2. Exact prospective chronology

The following are frozen candidate boundaries, not execution authorization.

| Segment | Exact UTC membership | Use |
|---|---|---|
| Development source-collection window | `2026-10-13T00:00:00Z` through `2027-01-10T23:55:00Z`, inclusive, 5-minute cadence | Candidate source collection; not all rows are fitting rows |
| Development model-observation window | Begins no earlier than `2026-10-13T16:40:00Z` so the first model observation has 200 prior in-window closed candles; ends at `2027-01-10T03:05:00Z`, inclusive | Eligible model observations subject to chronological folds |
| Embargo/purge membership | `2027-01-10T03:10:00Z` through `2027-01-10T23:55:00Z`, inclusive; exactly 250 observations | Excluded from fitting and model selection; retained only as sealed chronology/context evidence |
| Protected-test model observations | `2027-01-11T00:00:00Z` through `2027-02-09T23:55:00Z`, inclusive; 8,640 observations | Final evaluation population; never shortened or used during development |
| Protected-test label-completion extension | Through `2027-02-10T00:20:00Z` for the final target candle close | Required only to complete labels for the final protected observation |

The development fitting cutoff is intentionally earlier than the end of the
development source-collection window. The 250 embargo rows are not fitting
observations, not validation observations, not feature-selection observations,
and not hyperparameter-selection observations. They must remain explicitly
identified in the split manifest and cannot be silently reassigned.

The protected-test window remains the full `2027-01-11T00:00:00Z` through
`2027-02-09T23:55:00Z` interval. The embargo does not shorten it. The first
protected observation may use the immediately preceding 200 closed candles as
feature context, including rows in the sealed embargo/context set, but those
rows remain inaccessible to development fitting and selection.

The candidate dates were taken from the prior planning package and remain
pending owner approval. They are not evidence that future candles exist.

## 3. Availability and label-completion rules

### Candle and feature availability

- Only Binance BTCUSDT candles with UTC-aligned five-minute open timestamps are
  eligible.
- A candle must be complete/closed before it can be an observation.
- For an observation candle opening at `t`, the registered feature availability
  cutoff is `t + 5 minutes`, the candle close.
- All feature dependencies must be point-in-time valid and available no later
  than that cutoff.
- The full pipeline requires at least 200 prior closed candles; the selected
  vector's 28-candle lower bound does not replace this full pre-roll rule.
- Missing, duplicate, out-of-order, gapped, late, stale, timezone-naive, or
  incomplete observations stop the run; no imputation or synthetic candle is
  permitted.

### Target label completion

For prediction candle open timestamp `t`:

- the target uses `close[t+5]`, the close of the candle opening at `t + 25
  minutes`;
- that target becomes available only when that future candle closes, at
  `t + 30 minutes`;
- the target is `abs(log(close[t+5] / close[t]))`, dimensionless and
  non-negative;
- a target row is eligible only when its label-completion timestamp is strictly
  after the prediction feature cutoff and is inside the authorized source
  boundary;
- the final development and protected-test source windows must include the
  required five-candle label-completion extension;
- missing or late labels are excluded with an immutable reason and stop the
  affected run if they violate the preregistered completeness rule.

The five-candle forecast horizon, 200-candle pre-roll, 250-observation purge,
and label-completion extension are recorded as separate fields in the manifest.

## 4. Prospective protected-test sealing plan

The protected period has not occurred and no protected dataset currently
exists. It must not be described as collected, sealed, or evaluated.

Before any development observation is examined:

1. Freeze this protocol version, its SHA-256, the source-availability cutoff,
   the boundary manifest, and the exact five-feature/target hashes.
2. Before the protected period begins, designate an independent custodian who
   is not a model developer, feature selector, tuner, or acceptance decision
   maker.
3. The custodian acquires only the authorized Binance BTCUSDT/5m closed-candle
   source into a separate protected destination. No protected credentials,
   files, database, or network endpoint may be available to development jobs.
4. At the end of acquisition, the custodian records raw-source SHA-256,
   canonical-candle SHA-256, exact first/last open timestamps, candle count,
   requested/received counts, collection timestamps, source availability
   cutoff, gap/duplicate results, and label-completion status.
5. The custodian writes a manifest containing the protected interval, the
   200-candle feature-context membership, the five-candle label extension, the
   source/code identity, and the seal timestamp.
6. The custodian seals the raw artifact, canonical artifact, manifest and
   hashes in append-only storage and provides only a seal receipt and metadata
   to the development team.
7. The protected data remains inaccessible to development fitting, feature
   selection, preprocessing choices, hyperparameter/model selection, debugging,
   diagnostics, threshold decisions, and routine reporting.
8. A separately authorized final evaluator may read it only after the
   development artifact/configuration and split manifest are immutable.
9. Every protected read, export, hash operation, and evaluation command is
   recorded in an append-only access log with actor, time, purpose, object
   hash, command identity, and result.

No future data may be sealed retroactively or substituted with the historical
July–October source. If the custodian, receipt, hashes, or access log is
unavailable, protected evaluation stops.

## 5. Roles and authority

| Role | Required independence and authority |
|---|---|
| Owner/release authority | Approves protocol, boundaries, execution authorization, and eventual artifact promotion separately |
| Research approver | Reviews the preregistration and confirms unchanged criteria before development execution |
| Development executor | May access only approved development data and disposable development writes; cannot access protected data |
| Protected-data custodian | Independently acquires, hashes, seals, stores, and controls the future protected dataset |
| Independent evaluator | Performs final protected evaluation after seal and immutable development decision; cannot tune or select the model |
| Evidence auditor | Verifies hashes, lineage, access logs, commands, results, and adverse findings |

No one person may act as both development selector and protected evaluator.
Unavailability of the designated reviewer or custodian is a stop condition.

## 6. Permitted future destinations and credentials

No destination or credential is provisioned by this package. If separately
approved, use:

- a new disposable development evidence root, for example
  `/private/tmp/alphalens-batch6o-development-<run-id>/`, never the original
  repository evidence directory;
- a new isolated development database/schema with a unique name and local-only
  endpoint, never protected PostgreSQL/Redis or production volumes;
- a separate protected custodian-controlled append-only destination, not
  mounted in the development environment;
- read-only market-data access limited to Binance Spot BTCUSDT klines; no order,
  account, trading, or withdrawal permissions;
- unique short-lived credentials stored in an approved secret manager, never
  copied into source, manifests, logs, reports, or development configuration;
- no network access from fitting after the approved source artifacts are
  materialized, unless separately reviewed and logged.

The exact host, database, credential reference, retention period, and custodian
must be approved before execution. This package does not create or access any
of them.

## 7. Immutable lineage and audit requirements

Each run must retain immutable records for:

1. source artifact, provider, exchange/symbol/timeframe, boundary, source
   availability cutoff, ingestion ID, requested/actual count, gap/duplicate
   report, raw/canonical hashes, and collection receipt;
2. feature pipeline version, registry schema/hash, ordered five-feature schema,
   definition versions, Decimal quantum, availability contract, pre-roll and
   dependency cutoff checks;
3. target identity/hash, formula, horizon, label-completion rule, source and
   feature parent hashes;
4. split plan, development-fitting cutoff, exact 250-row embargo membership,
   protected membership, label extension, split hash, and no-overlap proof;
5. run code commit/tree, script hash, lockfile/environment hashes, configuration
   hash, all random states, commands, exit codes, reviewer identities, and
   per-fold predictions/actuals/metrics;
6. protected seal receipt, custodian identity, access log hash, evaluation
   command identity, and independent review decision.

Historical UUIDs, hashes, 4/5 results, or missing database rows must not be
backfilled into this new lineage. Failed or unfavorable outputs must be
preserved, not overwritten.

## 8. Frozen research acceptance criteria

All five historical criteria remain mandatory and unchanged:

1. R² improvement over ATR×1.5 baseline `> 0.01`.
2. Correlation improvement `> 0.05`.
3. MAE reduction `> 5%`.
4. Monotonic predicted/actual calibration-bin means.
5. Positive MAE and R² improvement in every declared 30-day regime.

The historical result remains 4/5 because correlation improvement was
`+0.008663260`. It is preserved as negative evidence and cannot be promoted,
repaired by threshold changes, relabeled, or treated as the protected result.

## 9. Stop conditions

Stop the affected run immediately on any of the following:

- source, code, lockfile, contract, schema, target, or protocol hash mismatch;
- unavailable owner approval, research approver, custodian, or independent
  evaluator;
- missing, duplicate, gapped, out-of-order, incomplete, late, or stale candles;
- label completion outside the authorized boundary or future-data leakage;
- feature dependency cutoff violation or insufficient 200-candle pre-roll;
- split overlap, missing 250-row embargo membership, or embargo rows used for
  fitting/selection;
- protected data read, seal failure, access-log gap, or credential boundary
  violation;
- broken candle/feature/target/validation lineage or nondeterministic replay;
- any failed acceptance criterion, without changing its threshold;
- unexpected network access, protected endpoint, production write, artifact
  activation, scoring, ranking, notification, trading, or deployment attempt.

## 10. Explicit owner decision checklist

- [ ] Approve this final protocol package and its recorded SHA-256.
- [ ] Approve the exact development source-collection and model-observation
      boundaries.
- [ ] Approve embargo membership `2027-01-10T03:10:00Z` through
      `2027-01-10T23:55:00Z` and fitting cutoff `2027-01-10T03:05:00Z`.
- [ ] Approve the full protected interval without shortening it.
- [ ] Approve the 200-candle full-pipeline pre-roll and five-candle label
      completion extension.
- [ ] Approve the future source-availability cutoff and protected manifest.
- [ ] Appoint the independent custodian and independent evaluator.
- [ ] Approve append-only protected storage, seal receipt, and access logging.
- [ ] Approve development-only destination, isolated credentials, compute, and
      allowed writes.
- [ ] Approve the synchronized lineage and reproducibility requirements.
- [ ] Freeze all five acceptance criteria unchanged.
- [ ] Authorize development-only fitting/walk-forward execution separately.
- [ ] Authorize protected-test evaluation separately after sealing.
- [ ] Authorize artifact packaging/promotion separately after successful
      independent review.

## 11. Research-execution authorization status

**NOT AUTHORIZED.** This package is ready for explicit owner/research review
only. No data collection, protected access, fitting, training, validation,
artifact packaging, scoring, ranking, deployment, Gate 6 validation, or Gate 7
certification has occurred.

Final status: **Batch 6N ACCEPTED; Batch 6O PROTOCOL DRAFT PENDING APPROVAL;
Gate 6 NOT VALIDATED; Gate 7 BLOCKED.**
