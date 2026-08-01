# AlphaLens v2 Quantitative Research Library Review

**Version:** Research Specification v1.0.0

**Status:** Final internal-consistency review

## 1. Scope

This review evaluates the Version 1.0.0 quantitative research specifications
for completeness, consistency, terminology, dependency direction, assumptions,
and prohibited production content. It does not validate predictive usefulness
and does not approve a production policy.

Let \(\mathcal D\) denote the reviewed document set and \(G=(\mathcal D,E)\)
its definition-dependency graph. The review requires \(G\) to be acyclic and
every unresolved numeric choice to map to an explicit calibration variable or
policy artifact. It assumes the frozen contracts are authoritative and that no
review finding may weaken their fail-closed behavior.

## 2. Documents Reviewed

1. Market Intelligence Ontology Research Specification
2. Opportunity Detection Mathematics Research Specification
3. Quantitative Evidence Ontology Research Specification
4. Opportunity Assessment Mathematics Research Specification
5. Opportunity Score Model Research Specification
6. Opportunity Ranking Mathematics Research Specification
7. Opportunity Plan Mathematics Research Specification
8. Lifecycle Mathematics Research Specification
9. Explainability Mathematics Research Specification
10. Quantitative Assumptions Register
11. Calibration Dependency Map

The review also checked compatibility with the frozen Decision, Market Context,
Evidence, Detection, Qualification, Scoring, Ranking, Plan, Lifecycle,
Explainability, Confidence, and Research contracts.

## 3. Canonical Terminology Review

| Term | Canonical meaning | Consistency result |
| --- | --- | --- |
| Candidate | Non-directional eligibility record preceding assessment | Consistent |
| `BUY` | Qualifying upward opportunity assessment | Consistent |
| `SELL` | Qualifying downward opportunity assessment, never exit | Consistent |
| `WAIT` | Completed valid abstaining assessment, never failure | Consistent |
| `UNAVAILABLE` / (\bot) | Evaluation cannot be completed validly | Consistent |
| Evidence | Typed proposition-relative observation with provenance | Consistent |
| Score | Policy-defined opportunity-quality quantity, not confidence | Consistent |
| Rank | Relative order in one immutable comparable set | Consistent |
| Confidence | Separately calibrated optional quantity; currently absent | Consistent |
| Plan | Optional informational scenario geometry, not execution | Consistent |
| Liquidity proxy | Explicitly limited OHLCV-derived context, not liquidity | Consistent |
| Expected movement | Reserved for a defined statistical estimand | Consistent |

## 4. Dependency and Circularity Review

The mathematical dependency graph is

\[
Data\rightarrow Features\rightarrow Market\ State\rightarrow Evidence
\rightarrow Detection\rightarrow Assessment\rightarrow Qualification
\rightarrow Score\rightarrow Ranking\rightarrow Lifecycle/Publication,
\]

with Plan as an optional post-assessment branch and Explanation as a terminal
projection of verified evidence/policy traces. Calibration artifacts govern
functions but do not consume downstream outputs as definitions.

No circular definition was found. In particular:

- detection does not depend on score or stance;
- evidence meaning does not depend on explanation;
- scoring does not define qualification or confidence;
- ranking does not redefine score;
- lifecycle does not infer decisions;
- explanation does not create evidence;
- plan geometry does not define predicted success.

## 5. Mathematical Completeness Review

The library defines typed state spaces, information sets, windows, causal
availability, evidence algebra, three-valued predicates, candidate state
transitions, assessment components, score/normalization/weight interfaces,
partial and total ordering interfaces, plan geometry, lifecycle transition
graphs, explanation traceability, assumptions, and calibration dependencies.

All unresolved quantitative choices are represented by named variables,
functions, parameter artifacts, populations, or policies. No unresolved choice
is silently mapped to zero, neutrality, equal weighting, carry-forward,
majority vote, or a default threshold.

The framework is mathematically complete as a research architecture. It is not
numerically instantiated and therefore is not production policy.

## 6. Assumption Review

Every material assumption identified during review appears in the Quantitative
Assumptions Register. The highest-risk assumptions concern source validity,
nonstationarity, evidence dependence, cross-scope transfer, structure
confirmation delay, missing-not-at-random evidence, identity/continuation,
intrabar path ambiguity, and user interpretation.

No assumption of market efficiency, inefficiency, normal returns, independent
observations, stationary distributions, frictionless execution, fillability,
profitability, predictive ability, or calibrated certainty is made.

## 7. Threshold, Weight, and Claim Audit

The review found no production threshold, feature cutoff, score weight,
confidence value, target multiple, fixed horizon, freshness duration, or
notification trigger. Numeric constants appear only in identities, algebraic
sign conventions, structural equations, state counts, or version numbers.

No specification claims statistical significance, predictive performance,
profitability, causal effect, execution quality, or future-price certainty.

## 8. Validation and Calibration Coverage

Every mathematical family identifies chronology, point-in-time availability,
walk-forward validation, sensitivity, missingness, subgroup/scope stability,
provenance, reproducibility, and production approval requirements. The
Calibration Dependency Map orders these studies and separates confidence as a
later independent branch.

Required quantitative inputs remain unknown by design: label/estimand,
populations, context definitions, predicates, component directions,
normalizations, weights, aggregators, comparability, timing rules, plan
construction, and explanation templates.

## 9. Risks and Required Controls

- **Researcher degrees of freedom:** preregistration and immutable experiment
  ledgers are mandatory.
- **Multiple comparisons:** the test family and correction must be selected
  before results.
- **Temporal dependence:** chronological splits, purge, and embargo require
  dataset-specific approval.
- **Regime instability:** per-fold and subgroup dispersion must be reported.
- **Protected-test leakage:** one-time access and immutable audit are required.
- **Economic overinterpretation:** outcome metrics do not imply execution or
  profitability.
- **Negative findings:** null, adverse, and unstable results must be retained.

## 10. Review Determination

The Version 1.0.0 research library is internally consistent, mathematically
complete at the policy-neutral interface level, terminology-aligned, acyclic,
explicit about assumptions, and free of production thresholds, weights,
confidence values, and unsupported claims. It is ready to govern Phase 5B
preregistration and calibration research. It does not authorize production
activation.

Future calibration findings SHALL be checked against this review before any
research specification is promoted. A discovered hidden assumption, circular
definition, unsupported claim, or undeclared threshold reopens the review and
blocks promotion.
