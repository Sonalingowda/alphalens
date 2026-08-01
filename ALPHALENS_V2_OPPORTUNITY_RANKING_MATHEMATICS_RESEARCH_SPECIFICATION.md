# AlphaLens v2 Opportunity Ranking Mathematics Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; no ranking policy is approved

## 1. Scope

This specification defines the theoretical ordering of current qualified
opportunities. Ranking is relative within an immutable candidate set. It does
not change stance, qualification, score semantics, confidence, or lifecycle
evidence.

## 2. Symbols

At ranking cutoff (t), let (\mathcal O_t) be the frozen set of eligible
opportunity revisions. Each (o\in\mathcal O_t) has scope (u_o), score
(S_o) under policy (\pi_S), evidence cutoff (c_o), availability (a_o),
freshness vector (F_o), and immutable identity (I_o). A ranking policy
(\pi_R) declares comparability relation (\sim_R), ordering key, duplicate
identity, and tie key.

## 3. Eligibility and Dominance

Only structurally valid, current, qualified opportunities with approved scores
enter the rankable set. Let (o_i\succ o_j) denote policy-approved strict
dominance. At minimum, dominance SHALL be irreflexive and transitive on each
comparable set. Score monotonicity requires

\[
S_i>S_j\implies o_i\succ o_j
\]

only if the scoring policy states that higher values mean greater values of the
same estimand and all preceding ranking keys are equal. No such direction is
assumed here.

Pareto dominance across transparent components MAY be researched:

\[
o_i\succ_P o_j \iff (\forall k, z_{ik}\succeq_k z_{jk})
\land(\exists k,z_{ik}\succ_k z_{jk}),
\]

but component directions and treatment of incomparability remain unresolved.

## 4. Freshness and Stability

Define evidence age vector (F_o(t)=(t-c_o,t-a_o,\ldots)) only for compatible
timestamp semantics. Freshness may exclude stale items or enter ordering only
under an approved policy; it SHALL NOT silently override quality. A rank change
from a changed candidate set creates a new snapshot and never rewrites an old
rank.

Rank stability research SHALL report set-overlap and order-change statistics
between adjacent snapshots, conditional on additions, removals, revisions, and
score changes. Stability is not optimized at the cost of falsifying current
order.

## 5. Cross-Market and Cross-Timeframe Comparability

Define (o_i\sim_R o_j) only when score estimand, component meanings,
normalization population, units, policy version, and validation evidence are
semantically comparable across their scopes. Otherwise separate partitions
must be ranked. A common numeric range alone does not establish comparability.
Transferability requires out-of-sample calibration and invariance analysis.

## 6. Duplicate Suppression

An approved equivalence relation (o_i\equiv_I o_j) SHALL encode thesis
identity and continuation. Similar symbol, timeframe, direction, indicators,
or score does not establish equivalence. Each equivalence class contributes its
unique current head; suppressed members and reasons remain auditable.

## 7. Stable Total Ordering Interface

For a comparable partition, a future lexicographic key MAY have form

\[
K(o)=(k_S(o),k_F(o),k_U(o),k_I(o)),
\]

where score, freshness, scope, and immutable identity elements and their
directions are explicitly approved. (k_I) must resolve every remaining tie
without randomness, insertion order, locale, database order, or hidden numeric
precision. This form selects no key or direction.

## 8. Assumptions and Dependencies

Ranking depends on qualification, score semantics, lifecycle/freshness,
identity/continuation, and a frozen candidate set. It assumes no cross-scope
comparability until established and no confidence semantics for rank.

## 9. Validation and Calibration

Research SHALL test monotonicity, permutation invariance, tie completeness,
duplicate equivalence properties, snapshot replay, sensitivity to candidate-set
composition, cross-scope invariance, temporal stability, and rank churn.
Walk-forward validation and production approval are required for score
direction, comparability, freshness use, identity, and final tie keys.
