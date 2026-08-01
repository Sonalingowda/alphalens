# AlphaLens v2 Opportunity Detection Mathematics Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; not approved production policy

## 1. Scope

This specification defines the mathematical form of candidate detection. A
candidate means only that an approved policy found a market state eligible for
assessment. It has no stance, score, rank, confidence, profitability claim, or
plan. `BUY`, `SELL`, and `WAIT` remain assessment outcomes under the frozen
Decision Contract.

## 2. Symbols

For scope (u=(s,\tau)) and cutoff (t), let (X_{u,t}) be valid market
context, (E_{u,t}) the immutable evidence multiset, and (Q_{u,t}) data
quality. Let (\pi_D=(\Theta_D,\mathcal N,\mathcal S,\mathcal R,\mathcal O))
denote a future approved detection policy containing parameters, necessary
predicates, sufficient clauses, rejection rules, and deterministic ordering.

Each predicate is a total three-valued function

\[
p_j(X,E;\Theta_D)\in\{1,0,\bot\},
\]

where (1) means satisfied, (0) means evaluated and unsatisfied, and
(\bot) means unavailable or invalid. No numeric predicate or parameter value
is fixed here.

## 3. Opportunity-Candidate Definition

Structural eligibility is

\[
V_{u,t}=I_{scope}I_{complete}I_{chronology}I_{provenance}I_{policy},
\]

where each indicator equals one only after its frozen validation gate passes.
Given an approved policy, candidate detection MAY take the conjunctive-normal
form

\[
D_{u,t}=V_{u,t}\land\bigwedge_{j\in\mathcal N}[p_j=1]
\land\bigvee_{C\in\mathcal S}\bigwedge_{k\in C}[p_k=1].
\]

This is an interface, not an approved sufficient condition. (\mathcal N),
(\mathcal S), and all (p_j) remain research variables. If any mandatory
predicate is (\bot), the result is `UNAVAILABLE`, not zero and not `WAIT`.

## 4. Necessary, Sufficient, and Rejecting Conditions

Necessary structural conditions are valid scope, completed data, compatible
registered features, causal availability, complete provenance, and an approved
policy artifact. Quantitative necessary conditions SHALL be declared only by a
future policy.

A sufficient clause is a named, ordered set of policy predicates. No feature,
indicator combination, crossover, or context label is sufficient merely by
appearing in the feature library. Rejection function
(R(X,E;\Theta_D)\in\{1,0,\bot\}) SHALL dominate candidate creation when it is
one; an unresolved rejection rule yields `UNAVAILABLE`.

## 5. Evidence and Contradictions

Required evidence is the complete set of source artifacts used by each
evaluated predicate plus data-quality and policy traces. Supporting and
contradicting evidence are defined relative to a named proposition. Let

\[
\mathcal E=\mathcal E^+\uplus\mathcal E^-\uplus\mathcal E^0
\]

be supporting, contradicting, and contextual evidence. This partition is
policy-relative. Cardinality is not strength: no majority vote, reason count,
or implicit numeric aggregation is valid. An approved aggregation operator
(A_D(\mathcal E;\Theta_D)) MUST preserve item identities, polarity, severity
authority, missingness, and contradictions.

## 6. Detection Hypotheses

Research SHALL formulate falsifiable hypotheses without asserting them true:

- `DH-01`: an approved subset of point-in-time feature/context states may
  distinguish an assessment-eligible population from the full scan population.
- `DH-02`: data-quality and freshness gates may reduce invalid candidates.
- `DH-03`: combining nonredundant evidence families may be more stable than a
  single-feature predicate.
- `DH-04`: candidate definitions may not transfer across instruments or
  timeframes.
- `DH-05`: stricter eligibility may change both candidate quality and coverage;
  neither direction is assumed beneficial.

Each hypothesis requires a preregistered target/label policy, chronological
sample, comparison, metric, uncertainty method, and stopping rule.

## 7. Detection State Machine

Let states be (R) (`RECEIVED`), (V) (`VALIDATING`), (D) (`DETECTED`),
(N) (`NOT_DETECTED`), and (U) (`UNAVAILABLE`). Allowed transitions are

\[
R\rightarrow V,\qquad V\rightarrow\{D,N,U\}.
\]

(D) requires (D_{u,t}=1); (N) requires a complete valid evaluation with
(D_{u,t}=0); (U) requires at least one mandatory undefined or invalid gate.
Terminal attempts are immutable. Identical inputs and policy must yield the
same terminal state and candidate hash.

## 8. Assumptions and Dependencies

Detection depends on the Market Intelligence Ontology, Evidence Ontology,
data-quality artifacts, registered features, and a future approved policy. It
assumes causal source availability and a separately approved opportunity
identity rule. It SHALL NOT depend on score, rank, notification, explanation,
or future lifecycle state.

## 9. Validation and Calibration Requirements

Phase 5B SHALL estimate candidate prevalence, missingness, predicate overlap,
redundancy, temporal stability, sensitivity to every parameter, and stability
across approved populations. Walk-forward validation, multiplicity control,
protected evaluation, null/adverse reporting, and complete coverage reporting
are mandatory. Research findings SHALL NOT activate detection without a
separate immutable production-policy approval.
