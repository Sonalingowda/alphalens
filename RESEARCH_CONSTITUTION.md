# AlphaLens Research Constitution

## Purpose and Authority

This document is the permanent quantitative constitution of AlphaLens. It governs all research, data handling, validation, evaluation, reporting, and future implementation.

No implementation decision, delivery deadline, apparent performance improvement, or presentation goal may weaken these rules. Quantitative definitions may change only through explicit, documented human approval.

## Required Research Qualities

All AlphaLens research must be:

- **Statistically defensible:** Methods, samples, assumptions, validation procedures, comparisons, and conclusions must be appropriate to the question and supported by evidence. Reported results must withstand informed statistical scrutiny.
- **Auditable:** Every material input, transformation, decision, parameter, output, and research claim must be traceable through retained records.
- **Explainable:** Methods, assumptions, limitations, outputs, and the basis for conclusions must be understandable to qualified reviewers. Results must not depend on unexplained or misleading behavior.
- **Reproducible:** An authorized reviewer must be able to recreate every experiment and result exactly from the recorded code, configuration, data, parameters, and random state.

These qualities are mandatory. Convenience, speed, presentation, or apparent performance never justifies weakening them.

## Absolute Prohibitions

AlphaLens must never:

- fabricate market data;
- fabricate predictions;
- fabricate probabilities;
- fabricate benchmark results;
- fabricate historical performance;
- fabricate backtests;
- fabricate evaluation metrics;
- present fake, simulated, placeholder, incomplete, or nonfunctional behavior as real functionality;
- modify any quantitative definition without explicit, documented human approval;
- introduce or permit look-ahead bias;
- use future information that would not have been available at the evaluated point in time; or
- use random train/test splitting for time-dependent market research.

No output may imply evidentiary support that the recorded data and methodology do not provide.

## Chronological Validation

All training, validation, testing, benchmarking, and backtesting involving time-dependent market information must preserve chronology. At every evaluated point in time, the research process may use only information that would actually have been available then. Dataset construction, feature computation, target construction, model fitting, model selection, parameter selection, evaluation, and reporting must respect this rule.

## Mandatory Safeguards

Every research workflow must actively prevent, detect, assess, and document:

- **Target leakage:** Features, preprocessing, selection, or training must not expose the target or information derived from the target in a way unavailable at prediction time.
- **Survivorship bias:** Datasets and conclusions must not improperly exclude entities that disappeared, failed, were delisted, or otherwise left the observable universe.
- **Data snooping:** Repeated testing, feature selection, parameter tuning, benchmark selection, or hypothesis refinement must not exploit evaluation data or inflate reported evidence.

When any of these risks cannot be ruled out, the limitation must be made explicit and the affected result must not be represented as stronger than the evidence supports.

## Reproducibility and Point-in-Time Evidence

Every experiment must be reproducible.

Future implementation must ensure that the following can be recorded for every experiment:

- code version;
- configuration;
- dataset version;
- experiment parameters; and
- every random seed.

The record must be sufficient to reproduce every result exactly. Every research claim must be reproducible from logged code and data corresponding to a specific point in time. Data revisions, corrections, or later availability must not be silently substituted for the point-in-time evidence underlying a claim.

## Approval and Integrity

Quantitative definitions, validation rules, metrics, targets, benchmarks, and interpretations remain unchanged unless an explicit human approval is documented. Any approved change must be made auditable and must not be applied retroactively in a way that misrepresents prior results.

If requested work would violate this constitution, work must stop, the conflict must be identified, and explicit human direction must be requested. Human direction may authorize a documented quantitative change, but authorization must not be inferred from schedule pressure, convenience, or a request to improve results.
