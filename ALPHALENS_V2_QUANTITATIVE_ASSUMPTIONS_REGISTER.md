# AlphaLens v2 Quantitative Assumptions Register

**Version:** Research Specification v1.0.0

**Status:** Canonical research register; no assumption is production approval

## 1. Scope and Interpretation

This register enumerates assumptions used by the Version 1.0.0 quantitative
research library. An assumption is a proposition requiring validation, not a
fact inferred from architecture. `Calibration dependency` names the artifact or
study that must resolve or monitor it. Failure SHALL be reported and SHALL NOT
be repaired by changing thresholds after protected evaluation.

Let \(\mathcal A=\{A_i\}\) be the registered assumption set,
\(V(A_i)\in\{SUPPORTED,CONTRADICTED,UNRESOLVED\}\) its study-specific validation
state, and \(Dep(A_i)\) its ordered calibration dependencies. No assumption is
treated as supported merely because it is required to make a candidate model
mathematically convenient.

## 2. Assumption Register

| Identifier | Description | Reason | Required validation | Risk if false | Calibration dependency |
| --- | --- | --- | --- | --- | --- |
| `MI-A01` | Completed OHLCV and feature provenance faithfully represent the declared source and cutoff. | All state variables derive from these artifacts. | Hash, source reconciliation, completeness, and chronology audits. | Every downstream quantity may be invalid. | Data-quality protocol. |
| `MI-A02` | Canonical UTC gives an unambiguous temporal order. | Point-in-time joins require one clock basis. | Clock, timezone, boundary, and drift tests. | Leakage, duplicate/missing windows, incorrect sessions. | Runtime clock policy. |
| `MI-A03` | Registered feature values retain frozen definitions and units. | Research references features rather than recomputing them. | Registry/version/hash replay and numerical regression. | Semantic mismatch and irreproducibility. | Feature registry release. |
| `MI-A04` | Context mappings may vary by population and timeframe. | Indicator distributions are not presumed invariant. | Cross-scope invariance and subgroup analysis. | Invalid transfer and misleading categories. | Context-definition study. |
| `MI-A05` | Candle volume is not executable liquidity. | Current data omit spread, depth, trades, and impact. | Future comparison with approved microstructure data. | False liquidity and execution-quality claims. | Future trade/quote/order-book contracts. |
| `MI-A06` | Causal structure confirmation introduces observable delay. | Swing confirmation can require later completed candles. | Event-time versus availability-time audit. | Repainting and future leakage. | Structure ontology study. |
| `EV-A01` | Source identity/version/hash uniquely determine evidence semantics. | Traceability requires stable meaning. | Collision, version, and semantic compatibility audit. | Evidence aliasing or silent reinterpretation. | Evidence registry governance. |
| `EV-A02` | Polarity has meaning only relative to a named proposition. | One observation may support one thesis and contradict another. | Proposition-to-policy trace tests. | Context-free directional claims. | Detection/assessment policy study. |
| `EV-A03` | Feature and context evidence may be dependent. | Many indicators share candles and intermediate features. | Dependency graph, correlation, conditional redundancy, and ablation studies. | Double counting and unstable scores. | Evidence interaction study. |
| `EV-A04` | Evidence count is not evidence strength. | Items differ in dependence, meaning, and authority. | Compare count-based summaries against preregistered alternatives. | Implicit arbitrary weighting. | Assessment/scoring study. |
| `EV-A05` | Observational association does not establish causation. | The data and design are observational. | Causal claims remain prohibited absent a causal design. | Fabricated explanations and overclaiming. | Any future causal research protocol. |
| `DT-A01` | Candidate eligibility is distinct from stance and quality. | Frozen architecture separates detection from assessment. | State/output contract tests and research trace audit. | Detection could smuggle decisions or scores. | Detection policy review. |
| `DT-A02` | Mandatory undefined predicates make detection unavailable. | Fail-closed semantics forbid imputing a negative result. | Missingness/fault injection and replay. | Failure mislabeled as no opportunity or `WAIT`. | Detection missing-input policy. |
| `DT-A03` | Candidate definitions may be population-specific. | Transferability has not been demonstrated. | Walk-forward cross-instrument/timeframe validation. | Unstable or biased coverage. | Detection population study. |
| `AS-A01` | Assessment components are separable for audit even when statistically dependent. | Explainability requires component traces. | Dependency and interaction analysis. | Misleading decomposition or double counting. | Assessment model study. |
| `AS-A02` | `WAIT` requires a complete valid assessment. | Frozen Decision Contract distinguishes abstention from failure. | State and missing-input validation. | Operational errors become decisions. | Decision-policy approval. |
| `AS-A03` | “Quality” component direction is not universal. | Favorable meaning depends on proposition and estimand. | Directionality and monotonicity studies. | Hidden business rule. | Assessment estimand study. |
| `SC-A01` | A score requires a separately defined quality estimand. | A scalar without meaning cannot be validated. | Estimand and measurement audit. | Numerically precise but meaningless ranking. | Scoring preregistration. |
| `SC-A02` | Normalization parameters are population- and time-bound. | Distributional transforms may drift. | Training-only fit, drift, and out-of-range tests. | Leakage and unstable scale. | Normalization study. |
| `SC-A03` | No default component weight is justified. | Equal and unequal weights both encode choices. | Candidate-weight comparison under nested chronological validation. | Arbitrary aggregation. | Weight study and approval. |
| `SC-A04` | Optional missingness may be informative or nonrandom. | Silent omission can change score meaning. | Missingness mechanism and sensitivity analysis. | Biased score and rank. | Missing-data study. |
| `RK-A01` | Numeric score ranges do not establish cross-scope comparability. | Equal numbers may represent different populations/estimands. | Measurement invariance and calibration analysis. | Invalid cross-market/timeframe order. | Comparability study. |
| `RK-A02` | Stable identity is required for duplicate suppression. | Similar market states are not necessarily one thesis. | Equivalence properties, collision, and continuation review. | Lost or duplicated opportunities. | Identity/continuation study. |
| `RK-A03` | Freshness and quality are distinct dimensions. | Age does not intrinsically determine evidence quality. | Freshness sensitivity and outcome analysis. | Hidden freshness weighting. | Freshness/ranking policy. |
| `PL-A01` | Entry-reference semantics match risk/reward distance equations. | A region must be reduced to a scalar only by policy. | Geometry reconstruction and sensitivity. | Inconsistent displayed ratios. | Plan construction study. |
| `PL-A02` | Directional price geometry is valid for the instrument convention. | Prices and inverse contracts may differ. | Instrument/unit review. | Sign and unit errors. | Instrument contract. |
| `PL-A03` | Candle prices do not establish executable fills. | OHLC contains no queue, spread, or fill evidence. | Future execution-data comparison if authorized. | Misstated achievable entry/exit. | Future microstructure contract. |
| `PL-A04` | Terminal levels omit path and intrabar ordering. | Both target and invalidation can occur within one candle. | Higher-resolution or conservative ambiguity study. | Biased outcome attribution. | Label/path policy. |
| `PL-A05` | Geometric risk/reward is not expectancy. | Expectancy also requires outcome probabilities and costs. | Explicit estimand and calibration study. | Profit implication without evidence. | Plan/outcome study. |
| `LC-A01` | Immutable event availability is monotone. | Deterministic replay requires nonregressing evidence. | Timestamp and predecessor audit. | Ambiguous historical state. | Runtime lifecycle validation. |
| `LC-A02` | Thesis continuation is not determined by symbol, timeframe, and direction alone. | Distinct opportunities can share those fields. | Identity-policy error analysis. | Incorrect merges or duplicate suppression. | Continuation study. |
| `LC-A03` | Freshness parameters are scope-specific until validated otherwise. | Cadence and feature windows differ. | Cross-scope survival/freshness analysis. | Premature or late expiration. | Freshness study. |
| `EX-A01` | Every canonical sentence can map to explicit evidence or disclosure. | Explanation must be auditable. | Complete sentence-to-source coverage. | Fabricated reasoning. | Template validation. |
| `EX-A02` | Deterministic templates can preserve quantitative meaning. | Canonical output cannot rely on free-form generation. | Value, locale, paraphrase, and comprehension tests. | Distortion or inconsistent claims. | Explanation-template study. |
| `EX-A03` | Material contradictions must remain visible. | Suppression would misrepresent evidence consistency. | Contradiction coverage audit and user comprehension study. | Overstated opportunity quality. | Explanation and qualification policy. |
| `RS-A01` | Historical associations may be nonstationary. | Financial-market populations change over time. | Walk-forward dispersion, drift, and subgroup analysis. | Unstable conclusions. | Every Phase 5B study. |
| `RS-A02` | Multiple research choices inflate false-discovery risk. | Many predicates/components may be compared. | Preregistered multiplicity control and complete experiment ledger. | Selection bias and unsupported claims. | Research protocol. |
| `RS-A03` | Protected evaluation cannot be reused for tuning. | Reuse invalidates its evidential role. | Access log and one-time evaluation audit. | Optimistic estimates. | Dataset/evaluation protocol. |

## 3. Governance

Every experiment SHALL reference the assumptions it relies upon and report
violations, uncertainty, and unresolved status. New assumptions require a new
compatible register version. Changed meaning or removal requires explicit
review; historical studies retain their referenced version.

Future calibration SHALL emit \(V(A_i)\) with evidence for every assumption
used by a selected specification. A contradicted mandatory assumption blocks
that specification; an unresolved assumption remains an explicit limitation.
