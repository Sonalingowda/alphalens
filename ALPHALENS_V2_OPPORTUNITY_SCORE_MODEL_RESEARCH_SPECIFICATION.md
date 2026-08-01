# AlphaLens v2 Opportunity Score Model Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; no score is approved

## 1. Scope

This specification defines interfaces for researching a transparent opportunity
score. A score is not a decision, confidence, probability, expected return,
risk/reward ratio, or guarantee. No estimand, component set, normalization,
weight, scale, aggregation equation, or production range is selected here.

## 2. Symbols and Component Model

For an approved component index set (K), raw component (r_k\in\mathcal D_k),
availability (m_k), and immutable evidence (E_k), define a component record

\[
C_k=(k,v_k,r_k,\mathcal D_k,m_k,E_k,N_k,W_k,\ell_k),
\]

where (N_k) is a normalization reference, (W_k) a weight reference when
approved, and (\ell_k) limitations. The ordered vector (C=(C_k)_{k\in K})
must remain reconstructible; an opaque scalar is prohibited.

## 3. Normalization Interface

A normalization is a versioned mapping

\[
z_k=N_k(r_k;\eta_k,\mathcal P_k,t_f),
\]

with parameters (\eta_k), reference population (\mathcal P_k), and freeze
time (t_f). Candidate research families MAY include fixed-domain transforms,
training-only empirical distributions, or robust location/scale transforms.
No family is selected. Research SHALL define out-of-domain and missing behavior
before evaluation. Runtime cross-sectional refitting is prohibited unless a
future approved policy explicitly studies and authorizes it.

## 4. Weight and Aggregation Interfaces

Let (w=(w_k)) be a future immutable weight artifact with declared domain and
constraints. No equal-weight default exists. Aggregation is an interface

\[
S=G((z_k,m_k,E_k)_{k\in K};w,\Theta_G),
\]

where (G), (w), output domain, units, and missing rule require Phase 5B
calibration and approval. This expression defines function inputs only; it is
not an approved production equation.

## 5. Missing Data

Each component SHALL be declared mandatory or optional. A missing mandatory
component makes (S=\bot). Optional absence requires a preregistered rule;
omission, renormalization, model-based imputation, or reduced component sets
are research alternatives, not defaults. Zero substitution, stale carry-forward,
and silent reweighting are prohibited.

## 6. Versioning and Extensibility

Score identity SHALL bind estimand, population, (K), (N), (w), (G),
precision, missing rule, evidence cutoff, code, and configuration. A change to
any semantic element requires a new score-policy version. New components MAY
be researched as new versions; historical scores remain immutable.

## 7. Sensitivity and Robustness

For a candidate research specification, sensitivity SHALL include, where
mathematically defined:

\[
\frac{\partial S}{\partial z_k},\qquad
\frac{\partial S}{\partial w_k},\qquad
\Delta_k S=S(C)-S(C\setminus C_k),
\]

plus perturbation of normalization parameters, windows, missingness, population
composition, and rounding. Nondifferentiable (G) requires finite perturbation
or exact local-change analysis. Sensitivity describes model behavior, not
predictive validity.

## 8. Assumptions and Dependencies

Scoring requires a valid `BUY` or `SELL` opportunity, qualification record,
evidence package, component definitions, and approved normalization/weight/
aggregation artifacts. It assumes a separately defined opportunity-quality
estimand and semantic comparability for any later ranking use.

## 9. Validation and Calibration

Phase 5B SHALL preregister the estimand, label/outcome relationship if any,
population, components, transforms, constraints, validation metrics,
chronological folds, uncertainty, multiplicity, sensitivity, adequacy criteria,
and protected test. Candidate specifications SHALL be compared using identical
out-of-fold observations and shall report null, adverse, unstable, and subgroup
results. Confidence calibration is a separate study. No score becomes
production policy through research performance alone.
