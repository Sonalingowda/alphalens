# Gate 06 scientific closure and future-data governance — 2026-11-11

Status: **negative development evidence preserved; Gate 06 NOT VALIDATED**

## Closure of the completed budget

The volatility lineage completed exactly 492 candidate-fold evaluations: three
predeclared Ridge candidates across 164 expanding folds and 16,400 test
observations per candidate. All candidates failed the frozen correlation
improvement criterion (`>0.05`); none was nominated, serialized as an
approved artifact, or activated.

The reproducible engineering result is distinct from scientific success. The
runner, source, protocol, dependency, Git, fold, checkpoint, result, and
negative-decision hashes are recorded in
`docs/GATE06_VOLATILITY_EXPERIMENT_RESULT_20261111.md`. The complete
prediction/residual archive remains private under the operational research
directory.

## Cumulative development-set risk

The prior Gate 06 development lineages include the historical baseline and
the subsequent fixed-candidate and volatility experiments. The current and
preceding retained development runs reuse the same isolated BTCUSDT/5m
development cutoff and chronological evaluation population. This is permitted
for engineering diagnosis, but repeated feature/candidate decisions against
the same development folds create adaptation and data-snooping risk. Their
negative results must not be treated as independent confirmations, and no
additional fitting or retuning is authorized under this lineage.

The source lineage also retains an explicit limitation: the original raw
provider response bytes are unavailable. Endpoint metadata is not treated as
raw-response proof. Any future claim must preserve this limitation or replace
it with independently custodied response evidence.

## Future-data approval package

No acquisition or protected evaluation is authorized by this document. A
future protocol must be approved before any new data is fetched or fitted.

1. **Prospective cutoff and custody:** record the exact UTC acquisition start,
   completion, and availability cutoff; retain raw provider response bytes,
   request parameters, TLS/source identity, response SHA-256, canonical candle
   hash, and immutable custody metadata.
2. **Separation:** establish a new source lineage with development, validation,
   and sealed protected-test windows created by an independent custodian.
   The fitting process receives development data only. The evaluator receives
   validation data only after the protocol and candidate budget are frozen.
3. **Coverage:** preregister minimum observation count, contiguous 5m
   coverage, missing/duplicate rejection, and minimum complete 30-day regime
   coverage. Any gap fails closed; no synthetic replacement is permitted.
4. **Point-in-time construction:** bind feature, target, scaling, selection,
   200-candle pre-roll, five-candle label extension, and 250-observation purge
   identities. Verify prefix invariance and no future timestamp access before
   fitting.
5. **Budget and hypothesis:** declare one falsifiable hypothesis, at most
   three candidates, fixed seeds/hyperparameters, fixed folds, and a single
   selection rule. No candidate expansion, repeated retuning, or favorable-fold
   selection is allowed.
6. **Acceptance:** preserve all five criteria: R² improvement `>0.01`,
   correlation improvement `>0.05`, MAE reduction `>5%`, monotonic
   calibration-bin actual means, and positive MAE/R² improvement in every
   required 30-day regime. Any failure rejects the candidate.
7. **Independent evaluation:** a separate custodian/evaluator must verify
   protected access logs, source hashes, fold membership, per-observation
   predictions/residuals, and result hashes without exposing protected labels
   to the research runner.
8. **Promotion:** artifact promotion requires all criteria, reproducible
   executable/dependency/data hashes, deterministic inference, a signed
   approval manifest, backup/recovery evidence, and explicit owner sign-off.

Until those conditions are separately approved and completed, Gate 06 remains
NOT VALIDATED, Gate 07 remains blocked, and no predictive artifact may be
activated.
