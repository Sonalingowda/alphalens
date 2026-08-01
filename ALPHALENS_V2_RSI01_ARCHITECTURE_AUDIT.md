# AlphaLens v2 RSI-01 Architecture Audit

**Audit status:** Passed

**Scope:** RSI-01 implementation only

**Audit date:** 2026-08-01

## 1. Audit Summary

The RSI-01 implementation conforms to the approved Feature Architecture
Standard and RSI-01 Quantitative Specification.

RSI-01 is registered as `relative_strength_index` version `1.0.0`, consumes
canonical Close from the immutable source snapshot, emits one bounded
dimensionless Decimal output after the approved mathematical warm-up, and is
appended to deterministic pipeline version `2.3.0` after EMA-01.

The implementation extracts the pre-existing Wilder RSI mathematics into one
shared Decimal primitive. Both the legacy reference feature and RSI-01 now use
that primitive, eliminating duplicated seed, smoothing, and zero-state logic
without changing the legacy feature interface or results.

Every RSI-01 output after initialization retains one ordered value-level
reference to the immediately preceding RSI-01 output. The current Close and
the internal smoothed gain/loss state remain exactly reconstructable from the
immutable source snapshot and approved quantitative definition. Recursive
lineage does not create a registry self-dependency.

No RSI variant, Stochastic RSI, MACD, Bollinger Bands, VWAP, signal,
threshold, divergence, or other feature was implemented.

## 2. Governing Documents Reviewed

The audit reviewed:

- `ALPHALENS_V2_FEATURE_ARCHITECTURE_STANDARD.md`; and
- `ALPHALENS_V2_RSI01_QUANTITATIVE_SPECIFICATION.md`.

EMA-01 was reviewed only as the approved repository pattern for recursive
feature integration and predecessor provenance. EMA mathematics were not
reused or changed.

## 3. Architecture Verification

| Review area | Evidence | Result |
| --- | --- | --- |
| Mathematical fidelity | Period, adjacent Close changes, gain/loss magnitudes, arithmetic seed, Wilder smoothing, first-valid boundary, and zero-state rules match the approved specification. | Pass |
| No duplicated logic | One shared Wilder RSI primitive serves the legacy reference and RSI-01 wrapper. | Pass |
| Source input | RSI-01 declares canonical Close as its only feature-specific source field and has no upstream derived dependency. | Pass |
| Decimal arithmetic | Input is finite Decimal, recursive state uses an isolated 50-digit context, and output uses shared canonical quantization. | Pass |
| Intermediate precision | Smoothed gain and loss state remains at working precision and is not replaced by quantized output. | Pass |
| Warm-up | Output is omitted until 15 consecutive Close observations establish 14 changes; exact coverage begins at the fifteenth Close. | Pass |
| Edge cases | Positive gain with zero loss maps to 100, positive loss with zero gain maps to 0, and zero gain with zero loss maps to 50. | Pass |
| Output domain | Every output is dimensionless, finite, non-null, and within the closed interval from 0 through 100. | Pass |
| Deterministic execution | Repeated execution produces identical values, ordering, memberships, registry hash, and result hash. | Pass |
| Prefix invariance | Shared pipeline prefix validation and focused RSI prefix fixtures preserve every earlier output and membership. | Pass |
| Future isolation | A changed future Close changes no earlier RSI output or predecessor membership. | Pass |
| Point-in-time correctness | Output is available only at candle close; every recursive predecessor is from the immediately prior output and is available before its consumer. | Pass |
| Fail-closed validation | Missing, non-Decimal, invalid, duplicate, unordered, discontinuous, or unsupported source/dependency evidence rejects computation. | Pass |
| Immutable output | Feature values and predecessor memberships use frozen shared value contracts. | Pass |
| Registry integration | Identity, version, category, source input, output, recursive classification, continuity, warm-up, availability, and implementation reference are canonical. | Pass |
| Pipeline integration | RSI-01 executes last in registry order through the existing snapshot, validation, sorting, provenance, and hashing path. | Pass |
| Persistence compatibility | Existing non-null Decimal feature storage and ordered feature-value dependency memberships represent RSI-01 without schema changes. | Pass |
| Provenance completeness | Current Close comes from hashed source evidence; seed and hidden state are replayable from the frozen origin; later values retain exact prior-output lineage. | Pass |
| Hash stability | New registry content produces a new registry hash and pipeline version while historical Tier-A identity remains unchanged. | Pass |
| Test completeness | Focused tests cover mathematical fixtures, warm-up, zero cases, precision, validation, lineage, pipeline, persistence mapping, determinism, prefix invariance, and future isolation. | Pass |

## 4. Quantitative Verification

Independent fixed fixtures verify the first approved seed value and each
subsequent Wilder update for a mixed gain/loss sequence. The expected values
are hard-coded from the approved mathematics rather than generated by the
implementation under test.

Additional fixtures verify:

- an all-gain eligible sequence produces exactly 100;
- an all-loss eligible sequence produces exactly 0;
- an unchanged eligible sequence produces exactly 50;
- no output exists before the fifteenth Close;
- later output uses unquantized smoothed state rather than prematurely
  quantized averages;
- ambient Decimal context cannot change results; and
- all emitted values remain within the approved bounded domain.

The implementation produces only the RSI-01 level. Smoothed gain and loss are
internal deterministic state, not extra outputs.

## 5. Registry and Hash Audit

The production registry now contains, in order:

1. `candle_geometry`;
2. `true_range`;
3. `average_true_range`;
4. `exponential_moving_average`; and
5. `relative_strength_index`.

The RSI-01 release has:

- registry schema version `1.1.0`;
- canonical feature and output identifier `relative_strength_index`;
- definition version `1.0.0`;
- no derived dependencies;
- pipeline version `2.3.0`; and
- registry configuration hash
  `0dd6c93a08d00dcd41aea58f39b1e7d1092a69033f7e128d45dfcf47cd2bc227`.

The frozen Tier-A registry retains historical configuration hash
`c89cdef54e4a59689259d18e0571ca5ab9dfebe713115c27dffd0818a6858aac`.

RSI values and predecessor memberships participate in canonical result
hashing. No hash algorithm or historical snapshot was modified.

## 6. Persistence and Provenance Audit

No RSI-specific persistence model, table, column, or migration was created.

RSI-01 reuses:

- immutable engineered feature values;
- pipeline run and source evidence;
- registry snapshots and configuration hashes;
- run-to-value membership;
- ordered feature-value dependency membership;
- candle-close availability;
- source data and provenance hashes;
- result hashes; and
- activation and supersession safeguards.

The first RSI output has no fabricated predecessor. Every subsequent output
has exactly one ordinal-zero dependency membership pointing to the previous
RSI output of the same identifier, version, and output name. Pipeline
validation resolves the exact predecessor value and validates chronology and
availability before hashing or persistence.

The hidden smoothed gain and loss values do not require mutable persistence.
They are deterministically reconstructed by replaying the approved
mathematics over the immutable source history from its frozen origin.

## 7. Files Changed

### Files created

- `ALPHALENS_V2_RSI01_QUANTITATIVE_SPECIFICATION.md`
- `ALPHALENS_V2_RSI01_ARCHITECTURE_AUDIT.md`
- `backend/app/features/rsi.py`
- `backend/tests/test_rsi_features.py`

### Production files modified

- `backend/app/features/contracts.py`
- `backend/app/features/momentum.py`
- `backend/app/features/registry.py`
- `backend/app/features/intraday_pipeline.py`

### Regression tests modified

- `backend/tests/test_feature_registry.py`
- `backend/tests/test_intraday_feature_pipeline.py`
- `backend/tests/test_intraday_feature_persistence.py`
- `backend/tests/test_intraday_feature_live_validation.py`
- `backend/tests/test_atr_features.py`
- `backend/tests/test_ema_features.py`

The production persistence layer, database models, API, and Alembic migration
graph were not modified.

## 8. Validation Results

| Validation | Result |
| --- | --- |
| Ruff lint, complete backend | Pass |
| Python compilation, application, tests, and migrations | Pass |
| Focused RSI-01 tests | 14 passed |
| Existing feature regression selection | 86 passed |
| Full backend suite | 305 passed |
| Alembic graph | Pass; single head `20260802_0034` |
| Git whitespace/error check | Pass |

EMA-touched and RSI-touched tests continue to pass after the registry append.
The expected pipeline ordering and version assertions were updated to the new
immutable release identity.

## 9. Defects Corrected During Audit

No RSI mathematical or production architecture defect remained after the
implementation pass.

Two stale regression assumptions were corrected:

- the ATR regression previously assumed that every pipeline dependency
  membership belonged to ATR; it now filters by ATR consumer identity; and
- the EMA regression previously assumed EMA would remain permanently last in
  an append-only registry; it now locates EMA at its deterministic registered
  position.

These corrections do not change feature behavior. They make regression
assertions compatible with deterministic registry growth while retaining
strict feature-specific checks.

## 10. Remaining Blockers

There is no remaining implementation, migration, validation, or audit blocker
for RSI-01.

Live activation remains subject to the existing operational requirements for
complete validated source history, no unresolved source conflicts, and
transactional persistence. These are standard platform preconditions rather
than RSI defects.

RSI-02, RSI-03, RSI-04, Stochastic RSI, MACD, Bollinger Bands, VWAP, and every
other feature remain blocked pending separate quantitative specification and
explicit approval.

## 11. Final Audit Decision

RSI-01 is mathematically compliant, deterministic, point-in-time correct,
prefix invariant, future isolated, provenance complete, registry integrated,
and compatible with immutable persistence.

The implementation is approved by this audit for commit and release as
RSI-01 only. No additional indicator implementation is included or
authorized.
