# Gate 06 root-cause hypotheses and next experiment package

Status: **diagnostic only; no new fitting authorized**

## Evidence boundary

The current development results retain fold-level aggregate metrics and
regime summaries, but not per-observation prediction/residual vectors. Residual
autocorrelation, individual error distributions, and observation-level
information-content tests therefore remain **not verified**. No missing values
were reconstructed.

## Ranked hypotheses

1. **Source-lineage mismatch (confirmed provenance defect).** The retained file
   spans 2026-07-14 through 2026-10-12, while the historical result records
   2026-05-22 through 2026-08-20 and a different timestamp hash. This explains
   why exact numerical reproduction is unavailable, but does not explain the
   repeated low correlation within the new lineage.

2. **Weak incremental signal over ATR volatility.** In the new lineage Ridge
   improves MAE and R², while aggregate correlation improves only about
   `+0.00866`. The ATR comparator already captures volatility level, so the
   remaining feature signal may explain magnitude error without improving rank
   correlation. Falsifier: a predeclared alternative target or feature family
   must improve correlation by more than `0.05` under the same chronology and
   comparator without harming the other four criteria.

3. **Regime nonstationarity.** New-lineage regime correlation improvements were
   approximately `-0.0106`, `+0.0076`, and `+0.0209`; all regimes passed MAE/R²
   improvement and calibration, but none approached `+0.05`. Falsifier: a
   preregistered regime-conditional model must pass the correlation threshold
   in every required regime without selecting favorable regimes.

4. **Horizon/feature information mismatch.** The frozen target is a 25-minute
   absolute log move. Features are point-in-time volatility/trend indicators,
   and may be better aligned with conditional variance than with observation
   ranking at this horizon. Falsifier: an explicitly approved, point-in-time
   horizon comparison with unchanged splits and a fixed candidate budget.

5. **Model-family limitation.** Ridge alpha changes from `0.1` to `10.0`
   altered correlation only in the sixth decimal place, so regularization is
   not the demonstrated cause. A different model family is only a hypothesis;
   it has not been tested and cannot be called superior without a new approved
   experiment.

## Required next experiment protocol

Before any new fit, separately approve a new development lineage containing:

- an immutable source-availability cutoff and complete source/canonical hashes;
- an exact development window and a separately sealed protected window;
- the frozen 200-candle feature pre-roll, five-candle label extension, and
  250-observation purge;
- fixed feature/target definitions and comparator;
- a predeclared maximum of three candidate specifications, including at most
  one alternative model family or one alternative target—not both;
- deterministic seeds, dependency lock hash, code tree hash, and per-observation
  predictions/residuals retained outside Git;
- no protected reads during fitting or selection; and
- rejection if any of the five criteria fails, with no threshold changes.

The next run must first resolve the source-lineage discrepancy. Until then,
Gate 06 remains not validated and no artifact may be nominated.

