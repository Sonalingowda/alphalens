# AlphaLens v2 Lifecycle Mathematics Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; no timing policy is approved

## 1. Scope

This specification formalizes the frozen opportunity lifecycle as an immutable
event graph. It does not define freshness durations, validity horizons,
continuation windows, invalidation prices, renewal rules, or notification policy.

## 2. State Space and Transition Relation

Let

\[
\mathcal L=\{D,Q,R,P,U,S,I,E,A\}
\]

denote `DETECTED`, `QUALIFIED`, `RANKED`, `PUBLISHED`, `UPDATED`,
`SUPERSEDED`, `INVALIDATED`, `EXPIRED`, and `ARCHIVED`. The allowed relation is

\[
\begin{aligned}
D&\rightarrow\{Q,E,A\},\\
Q&\rightarrow\{R,I,E,A\},\\
R&\rightarrow\{P,S,I,E\},\\
P&\rightarrow\{U,S,I,E\},\\
U&\rightarrow\{R,P,S,I,E\},\\
S&\rightarrow\{A\},\quad I\rightarrow\{A\},\quad E\rightarrow\{A\},\\
A&\rightarrow\varnothing.
\end{aligned}
\]

No reverse edge is valid. A renewed thesis receives a new identity unless a
future approved continuation policy authorizes a successor revision.

## 3. Event Sequence

For opportunity (o), history is

\[
H_o=(e_1,\ldots,e_n),\qquad e_k=(k,l_{k-1},l_k,t_k,a_k,z_k),
\]

where (k) is sequence, (l_{k-1}\rightarrow l_k) an allowed transition,
(t_k) occurrence, (a_k) availability, and (z_k) evidence/policy lineage.
Required invariants are

\[
k=1,\ldots,n;\quad t_k\le a_k;\quad a_k\le a_{k+1};\quad
pred(e_{k+1})=id(e_k).
\]

The current state is (l_n). Histories have one initial event, one current
head, no cycles, no missing predecessor, and no mutation. Prefix invariance
requires every prefix (H_o^{(j)}) remain byte-identical after later events.

## 4. Freshness and Expiration Interfaces

Let (F_o(t)) be the vector of source ages, validity boundaries, and health
states at resolution cutoff (t). A future freshness function

\[
\mathcal F(F_o(t);\Theta_F)\in\{CURRENT,STALE,\bot\}
\]

requires approved clocks, durations, mandatory sources, and failure rules.
Expiration predicate (\mathcal X(o,t;\Theta_X)) and invalidation predicate
(\mathcal I(o,X_t;\Theta_I)) are undefined until separately calibrated and
approved. Missing policies make publication unavailable rather than choosing
default timeouts.

## 5. Continuation and Supersession

Continuation is an equivalence-candidate relation

\[
o_i\sim_C o_j\iff C(scope,direction,policy,time,evidence;\Theta_C)=1.
\]

The function must establish compatible scope and direction, nonterminal
predecessor, allowed policy evolution, and time/evidence conditions. It must be
tested for reflexivity on identical versions, symmetric thesis comparison where
applicable, and absence of ambiguous multiple heads. Supersession names exactly
one successor and never implies user position activity.

## 6. State Preconditions

- (D) requires a valid candidate.
- (Q) requires a valid qualification record.
- (R) requires valid ranking membership.
- (P) requires an immutable publication projection.
- (U) requires a successor opportunity revision.
- (S) requires a named successor.
- (I) requires an approved invalidation predicate and evidence.
- (E) requires an approved validity boundary reached at the cutoff.
- (A) preserves the full terminal history while removing current visibility.

## 7. Assumptions and Dependencies

Lifecycle assumes globally stable identities, monotone availability, consistent
UTC clocks, immutable policy artifacts, and deterministic replay. It depends on
detection, qualification, ranking, publication, and future freshness/
continuation/invalidation policies but does not redefine them.

## 8. Validation and Future Calibration

Property validation SHALL cover allowed edges, terminal absorption, unique
heads, predecessor continuity, timestamp monotonicity, replay, concurrency,
prefix invariance, and identity collisions. Phase 5B must study freshness,
continuation, expiration, invalidation, and renewal definitions with
chronological data and sensitivity analysis. No duration or price rule is
approved here.
