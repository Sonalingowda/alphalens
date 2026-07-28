# AlphaLens Agent Operating Manual

## Purpose and Authority

This document is the permanent operating manual for every AI coding agent working on AlphaLens.

Repository instructions and explicit human instructions must be followed. The approved system architecture, quantitative research philosophy, product direction, technology stack, and implementation strategy are frozen. Architecture is immutable during implementation: implementation must follow architecture, and implementation work must never redesign it.

## Required Working Method

Every agent must:

1. Inspect the repository before modifying it.
2. Understand the relevant architecture, research rules, existing implementation, and approved phase before implementing anything.
3. Build exactly one explicitly approved phase at a time.
4. Remain within the authorized scope of that phase.
5. Stop after completing the approved phase.
6. Wait for explicit human review and approval before beginning another phase.
7. Document every assumption, including its basis and its effect on the work.
8. Use professional, precise, and domain-appropriate naming.
9. Keep implementation modular and responsibilities clearly separated.
10. Use strong typing wherever the approved implementation language and framework support it.
11. Avoid oversized files and split responsibilities only along clear architectural boundaries.
12. Avoid unnecessary abstraction.
13. Avoid premature optimisation.
14. Avoid premature microservices.
15. Use environment variables for environment-specific configuration and secrets.
16. Extend existing files before creating new ones whenever reasonable.
17. Keep the repository intentionally small, focused, and maintainable.

If requirements are ambiguous, conflict with the frozen architecture, or appear to require work beyond the approved phase, stop and request explicit human direction. Do not resolve ambiguity by silently changing architecture or quantitative definitions.

## Git Safety Rules

- Never delete existing files unless explicitly instructed.
- Never rename existing files unless explicitly instructed.
- Never rewrite existing files unless explicitly instructed.
- Prefer extending existing files over creating new ones.
- If structural repository changes appear necessary, explain them first and wait for explicit approval.
- Inspect the working tree before making changes and preserve unrelated human work.
- Do not begin work belonging to an unapproved phase.

## Quantitative Research Constitution — Complete Restatement

The following rules restate the complete AlphaLens quantitative research constitution. They are permanent constraints on all research and implementation.

### Required Research Qualities

All AlphaLens research must be:

- **Statistically defensible:** Methods, samples, assumptions, validation procedures, comparisons, and conclusions must be appropriate to the question and supported by evidence. Reported results must withstand informed statistical scrutiny.
- **Auditable:** Every material input, transformation, decision, parameter, output, and research claim must be traceable through retained records.
- **Explainable:** Methods, assumptions, limitations, outputs, and the basis for conclusions must be understandable to qualified reviewers. Results must not depend on unexplained or misleading behavior.
- **Reproducible:** An authorized reviewer must be able to recreate every experiment and result exactly from the recorded code, configuration, data, parameters, and random state.

These qualities are mandatory. Convenience, speed, presentation, or apparent performance never justifies weakening them.

### Absolute Prohibitions

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

### Chronological Validation

All training, validation, testing, benchmarking, and backtesting involving time-dependent market information must preserve chronology. At every evaluated point in time, the research process may use only information that would actually have been available then. Dataset construction, feature computation, target construction, model fitting, model selection, parameter selection, evaluation, and reporting must respect this rule.

### Mandatory Safeguards

Every research workflow must actively prevent, detect, assess, and document:

- **Target leakage:** Features, preprocessing, selection, or training must not expose the target or information derived from the target in a way unavailable at prediction time.
- **Survivorship bias:** Datasets and conclusions must not improperly exclude entities that disappeared, failed, were delisted, or otherwise left the observable universe.
- **Data snooping:** Repeated testing, feature selection, parameter tuning, benchmark selection, or hypothesis refinement must not exploit evaluation data or inflate reported evidence.

When any of these risks cannot be ruled out, the limitation must be made explicit and the affected result must not be represented as stronger than the evidence supports.

### Reproducibility and Point-in-Time Evidence

Every experiment must be reproducible.

Future implementation must ensure that the following can be recorded for every experiment:

- code version;
- configuration;
- dataset version;
- experiment parameters; and
- every random seed.

The record must be sufficient to reproduce every result exactly. Every research claim must be reproducible from logged code and data corresponding to a specific point in time. Data revisions, corrections, or later availability must not be silently substituted for the point-in-time evidence underlying a claim.

### Approval and Integrity

Quantitative definitions, validation rules, metrics, targets, benchmarks, and interpretations remain unchanged unless an explicit human approval is documented. Any approved change must be made auditable and must not be applied retroactively in a way that misrepresents prior results.

If a requested implementation would violate any research rule, the agent must stop, identify the conflict, and wait for explicit human direction. Human direction may authorize a documented quantitative change, but it may not be inferred from schedule pressure, convenience, or a request to improve results.

## Phase Boundary

Completion of a phase does not authorize the next phase. After completing the currently approved phase, report the result and stop. Further work requires explicit human approval.
