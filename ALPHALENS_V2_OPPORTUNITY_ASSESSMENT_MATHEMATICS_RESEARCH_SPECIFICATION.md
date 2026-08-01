# AlphaLens v2 Opportunity Assessment Mathematics Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; not approved production policy

## 1. Scope

This specification defines a decomposable mathematical assessment space for a
detected candidate. It does not choose `BUY`, `SELL`, or `WAIT`; a future
approved decision policy alone may map a complete assessment to those canonical
stances. Failure or missing mandatory input is `UNAVAILABLE`, never `WAIT`.

## 2. Symbols and Component Space

For candidate (c), evidence package (E_c), context (X_c), proposition
(\phi\), and future parameter artifact (\Theta_A), define

\[
A(c,\phi)=(q_T,q_M,q_V,q_S,q_C,q_D,q_R,q_E),
\]

where the components are trend quality, momentum quality, volatility quality,
market-structure quality, signal consistency, data integrity, risk factors,
and evidence completeness. Each component is a typed result

\[
q_k=(r_k,d_k,m_k,\lambda_k),
\]

with raw sufficient statistics (r_k), declared domain (d_k), missing state
(m_k\in\{AVAILABLE,PARTIAL,UNAVAILABLE\}), and limitations (\lambda_k).
The word “quality” denotes a research dimension, not a favorable judgment.

## 3. Component Definitions

### 3.1 Trend Quality

(q_T=f_T(E_{trend},X_{trend};\Theta_T)) may describe direction agreement,
persistence, separation, slope, and directional strength from registered
features. It SHALL retain timeframe and dependency identity. EMA alignment or
ADX values have no favorable meaning until (f_T) is approved.

### 3.2 Momentum Quality

(q_M=f_M(E_{momentum},X_{momentum};\Theta_M)) may describe oscillator state,
change, divergence among registered measures, and directional compatibility
with (\phi). It SHALL NOT treat bounded oscillator levels or crossovers as
universal thresholds.

### 3.3 Volatility Quality

(q_V=f_V(E_{volatility},X_{volatility};\Theta_V)) may represent current scale,
relative scale, change, compression/expansion, and compatibility with the
candidate thesis. Volatility is unsigned; whether a regime supports or
contradicts (\phi) is policy-specific.

### 3.4 Market Structure Quality

(q_S=f_S(E_{structure},X_{structure};\Theta_S)) may describe confirmed swing
relations and causally available structure events. It remains unavailable until
a non-repainting structure ontology is approved. Confirmation lag and equality
semantics are mandatory inputs.

### 3.5 Signal Consistency

Let (y_j(\phi)\in\{+1,-1,0,\bot\}) represent approved supporting,
contradicting, contextual, or unavailable relations. Signal consistency is a
vector of agreement, contradiction, dependence, and temporal-alignment
statistics:

\[
q_C=f_C((y_j),\operatorname{Dep}(E),\operatorname{Age}(E);\Theta_C).
\]

No evidence count, majority vote, or independence assumption is approved.

### 3.6 Data Integrity

(q_D=f_D(Q,\operatorname{Prov}(E);\Theta_D)) records completeness, validation,
freshness, continuity, conflict, and provenance outcomes. Any structurally
mandatory failure makes the complete assessment undefined. Data integrity
SHALL NOT be traded against attractive market evidence.

### 3.7 Risk Factors

(q_R=f_R(E_{risk},V,S,L^*;\Theta_R)) is an ordered set of factual limitations
and adverse conditions. It is not expected loss, position risk, or execution
risk unless those quantities receive separate data and mathematical contracts.

### 3.8 Evidence Completeness

For a policy-declared mandatory set (M_\phi), optional set (O_\phi), and
available set (A_E), define raw coverage statistics

\[
n_M=|M_\phi\cap A_E|,\quad N_M=|M_\phi|,\quad
n_O=|O_\phi\cap A_E|,\quad N_O=|O_\phi|.
\]

The ratios (n_M/N_M) and (n_O/N_O) MAY be reported when denominators are
nonzero, but they are not scores or qualification thresholds. Missing mandatory
evidence makes assessment unavailable under the frozen fail-closed rule.

## 4. Assessment and Stance Interface

A future decision map has the form

\[
\delta(A,E;\Theta_\delta)\in\{BUY,SELL,WAIT,\bot\}.
\]

The mapping, proposition definitions, conflicts, parameters, and tie/abstention
rules are not specified here. (\bot) denotes inability to complete a valid
assessment and is not a canonical decision. `SELL` is a downward opportunity,
not an exit instruction.

## 5. Assumptions and Dependencies

The assessment depends on a valid candidate, complete Evidence Package, Market
Intelligence Ontology, Evidence Ontology, and future decision policy. It assumes
component semantics do not transfer automatically across instruments or
timeframes and that correlated evidence remains correlated.

## 6. Validation and Calibration

Research SHALL preregister each (f_k), its estimand, inputs, domain, missing
rule, population, directionality, and sensitivity variables. Validation SHALL
include chronology, ablation, redundancy, temporal stability, component
correlation, missingness, subgroup/timeframe analysis, and walk-forward
evaluation against a separately approved label policy. No favorable quality
interpretation or stance becomes production policy without approval.
