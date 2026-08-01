# AlphaLens v2 Calibration Dependency Map

**Version:** Research Specification v1.0.0

**Status:** Canonical research dependency map; not production approval

## 1. Scope and Legend

This map identifies empirical and approval requirements for every quantitative
quantity class in the Version 1.0.0 research library.

- **Required** means the activity is necessary before operational use.
- **Conditional** means necessity depends on whether the candidate quantity is
  selected for study or fitted from data.
- **No** means structural validation suffices for that column.

“Optimisation” means preregistered parameter/model selection under nested
chronological validation. It SHALL NOT mean profit maximization. Any optimization
requires a declared estimand, search space, objective, stopping rule, and untouched
outer evaluation.

Let \(\mathcal Q=\{q_i\}\) be the set of mathematical quantity classes and
write \(q_i\prec q_j\) when calibration or approval of \(q_i\) is a prerequisite
for \(q_j\). The relation SHALL be acyclic. The map assumes immutable datasets,
chronological availability, deterministic computation, and explicit absence
rather than inferred values; each assumption is governed by the Quantitative
Assumptions Register.

## 2. Dependency Matrix

| Quantity or relation | Historical calibration | Walk-forward validation | Statistical testing | Optimisation | Production approval | Principal dependencies |
| --- | --- | --- | --- | --- | --- | --- |
| Raw OHLCV identity and units | No | No | No | No | Required | Data contract, source validation |
| Registered feature mathematics | No; frozen | Regression required | No | No | Already governed | Feature Architecture Standard |
| Observation windows (W) | Required if interpreted | Required | Conditional | Conditional | Required | Label/estimand, feature availability |
| Multi-timeframe set (H) and joins | Required | Required | Conditional | Conditional | Required | Completion and availability rules |
| Trend context map (g_T,\theta_T) | Required | Required | Required | Conditional | Required | Trend features, population |
| Momentum context map (g_M,\theta_M) | Required | Required | Required | Conditional | Required | Momentum features, population |
| Volatility context map (g_V,\theta_V) | Required | Required | Required | Conditional | Required | Volatility features, scale |
| Structure confirmation (\mathcal C_{\theta_S}) | Required | Required | Required | Conditional | Required | Non-repainting ontology |
| BOS/CHOCH/state definitions | Required | Required | Required | Conditional | Required | Confirmed swings and break semantics |
| Session boundaries (B_C) | Required if used | Required | Required | Conditional | Required | UTC/venue calendar |
| Liquidity proxy (L^*) | Required if interpreted | Required | Required | Conditional | Required | OHLCV limitation; future microstructure data |
| Data-quality coordinates (Q) | Operational calibration conditional | Required for freshness | Conditional | No | Required | Validation and runtime policy |
| Evidence polarity | Required per proposition | Required | Required | No | Required | Approved proposition/policy |
| Evidence severity | Required per gate | Required | Required | No | Required | Qualification policy |
| Evidence dependence/redundancy | Required | Required | Required | Conditional | Required if aggregated | Evidence graph and population |
| Detection predicates (p_j) | Required | Required | Required | Conditional | Required | Label policy and context/evidence |
| Necessary/sufficient clause sets | Required | Required | Required | Conditional | Required | Predicate study, multiplicity control |
| Detection missing/freshness rules | Required | Required | Conditional | No | Required | Data-quality and runtime policy |
| Assessment functions (f_T,\ldots,f_R) | Required | Required | Required | Conditional | Required | Detection, evidence, estimand |
| Evidence completeness sets (M_\phi,O_\phi) | Required | Required | Conditional | No | Required | Qualification/decision policy |
| Stance map (\delta) | Required | Required | Required | Conditional | Required | Approved label policy |
| Score estimand | Required definition | Required | Required | No | Required | Product/research objective |
| Score component set (K) | Required | Required | Required | Conditional | Required | Assessment and evidence |
| Normalizations (N_k,\eta_k) | Required when fitted | Required | Required | Conditional | Required | Training population |
| Weights (w_k) | Required | Required | Required | Conditional | Required | Score estimand and components |
| Aggregator (G,\Theta_G) | Required | Required | Required | Conditional | Required | Normalized components and weights |
| Score output domain/direction | Required | Required | Required | No | Required | Aggregator and estimand |
| Score missing-data behavior | Required | Required | Required | Conditional | Required | Missingness study |
| Score sensitivity criteria | Required | Required | Conditional | No | Required | Complete score specification |
| Ranking comparability (\sim_R) | Required | Required | Required | No | Required | Score measurement invariance |
| Freshness ranking key (k_F) | Required if used | Required | Required | Conditional | Required | Lifecycle freshness policy |
| Duplicate relation (\equiv_I) | Required | Required | Conditional | No | Required | Identity/continuation policy |
| Final deterministic tie key | No outcome calibration required; design review required | Replay required | No | No | Required | Canonical immutable fields |
| Entry construction (\psi_E) | Required | Required | Required | Conditional | Required | Plan estimand and market evidence |
| Invalidation (\psi_I) | Required | Required | Required | Conditional | Required | Thesis definition and path policy |
| Targets (\psi_T) | Required | Required | Required | Conditional | Required | Outcome horizon and path policy |
| Plan reference (\psi_0) | Required | Required | Conditional | Conditional | Required | Price-source semantics |
| Scenario movement (M_j) | No after levels fixed | Reconstruction required | No | No | Required with plan | Entry and target levels |
| Geometric risk/reward (R,G_j,RR_j) | No after levels fixed | Reconstruction required | No | No | Required with plan | Scalar entry reference and levels |
| Statistical expected movement | Required | Required | Required | Conditional | Required | Outcome variable, horizon, estimator |
| Freshness (\mathcal F,\Theta_F) | Required | Required | Required | Conditional | Required | Runtime cadence and evidence validity |
| Expiration (\mathcal X,\Theta_X) | Required | Required | Required | Conditional | Required | Validity/freshness policy |
| Invalidation (\mathcal I,\Theta_I) | Required | Required | Required | Conditional | Required | Plan/thesis evidence |
| Continuation (\sim_C,\Theta_C) | Required | Required | Conditional | Conditional | Required | Identity and lifecycle history |
| Explanation ordering importance | Required if policy-derived | Required | Conditional | No | Required | Evidence/qualification trace |
| Explanation templates and locale | Human-factors calibration conditional | Deterministic replay required | Conditional | No | Required | Taxonomy/reason mappings |
| Confidence quantity | Required under separate study | Required | Required | Conditional | Separate explicit approval | Confidence Policy; currently absent |

## 3. Calibration Dependency Graph

\[
\begin{aligned}
Data/Features &\rightarrow Context/Evidence\\
&\rightarrow Label\ and\ Detection\ Studies\\
&\rightarrow Assessment/Decision\ Study\\
&\rightarrow Qualification\ Study\\
&\rightarrow Score\ Estimand/Components/Normalization/Weights\\
&\rightarrow Comparability/Ranking\\
&\rightarrow Lifecycle/Plan/Explanation\ Operations.
\end{aligned}
\]

Confidence, if ever researched, is a separate branch after a frozen decision
policy and outcome estimand. It SHALL NOT be inferred from score or rank.

## 4. Validation Requirements

Every calibrated artifact SHALL identify data version, population, evidence
cutoff, folds, purge/embargo where applicable, preprocessing, missingness,
parameters, objective, uncertainty method, multiplicity method, seeds,
configuration/code hashes, protected-test status, and human approval. A
dependency may activate only after every upstream required artifact is approved.

Future revisions SHALL add a quantity before it is calibrated, declare its
incoming and outgoing dependencies, and repeat the circularity review. Removal
or semantic change requires versioned review and SHALL NOT alter historical
calibration lineage.
