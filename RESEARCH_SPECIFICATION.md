# AlphaLens Quantitative Research Specification

## Document Status

**Status:** Proposed — Pending Human Review

This document is a design-review artifact. It compares candidate research
questions, prediction targets, baseline models, evaluation measures, and
chronological controls. It does not approve a target, define a production
label, authorize model development, or report experimental evidence.

No label generation, model training, feature selection, hyperparameter
tuning, prediction, or backtesting may begin until the relevant quantitative
definitions in this specification have received explicit documented human
approval.

## Purpose

AlphaLens must decide what future quantity a research experiment is intended
to estimate before deciding how to estimate it. A prediction target determines:

- what constitutes one research observation;
- when its label becomes knowable;
- which validation boundaries are leakage-safe;
- which metrics are meaningful;
- what practical decision, if any, could consume the output; and
- what claims the resulting evidence can and cannot support.

The options below are deliberately evaluated without selecting a preferred
path. Ease of implementation is not evidence of research value.

## Governing Research Rules

Every future experiment governed by this specification must remain:

- statistically defensible;
- auditable;
- explainable; and
- exactly reproducible from recorded point-in-time evidence.

The following controls are mandatory:

1. Features at prediction timestamp \(t\) may contain only information
   available at or before \(t\).
2. Labels may use future observations because they describe the research
   outcome, but label data must never enter features, preprocessing, model
   selection, or fitting for that prediction.
3. All development and evaluation partitions must be chronological. Random,
   shuffled, and conventional k-fold splits are prohibited.
4. Training observations whose label windows overlap an evaluation boundary
   must be purged.
5. The final holdout must remain inaccessible during target refinement,
   feature refinement, model selection, and parameter selection.
6. Missing or incomplete future observations must make the affected label
   ineligible. They must not be interpolated or fabricated.
7. Target definitions, thresholds, horizons, metrics, execution assumptions,
   benchmarks, and label versions must be frozen before evaluation.
8. Repeated comparison of target variants is a form of multiple hypothesis
   testing and data snooping. Every attempted variant must be recorded,
   including unsuccessful variants.

## Current Research Evidence Boundary

The synchronized research dataset currently contains:

- one market: BTC/USD;
- one timeframe: daily;
- 720 validated completed candles;
- a deterministic point-in-time feature pipeline;
- a maximum existing feature lookback of 50 observations;
- expanding walk-forward validation infrastructure;
- a 50-observation purge/embargo mechanism; and
- an isolated final holdout mechanism.

These facts describe available evidence; they do not establish that the sample
is sufficient for any candidate target or model. Effective sample size will be
lower than 720 after feature warm-up, forward-label availability, purging,
holdout reservation, and dependence from overlapping label windows.

The existing validation defaults were verified as infrastructure settings.
They are not automatically approved as model-research settings. In particular,
minimum training size, test size, step size, embargo, and holdout size must be
reviewed after a target and prediction horizon are selected.

## Common Target-Definition Contract

Before any candidate becomes implementable, its approved definition must
record all of the following:

- target name and immutable target-version identifier;
- asset, quote currency, and timeframe;
- prediction timestamp and information cutoff;
- prediction horizon \(H\), expressed in observations rather than assumed
  wall-clock time;
- exact source price or path fields used by the label;
- mathematical formula and numerical precision;
- class thresholds and equality handling, if applicable;
- treatment of missing, invalid, or incomplete future candles;
- first and last eligible prediction timestamps;
- label-availability timestamp;
- feature pipeline version and source dataset hash;
- chronological split configuration and its deterministic hash;
- primary evaluation metric and secondary diagnostics;
- benchmark definition;
- every random seed used by stochastic estimators; and
- code and configuration versions.

### Prediction-Time Convention

If a feature uses candle \(t\)'s closing value, the prediction cannot be
represented as available before that close. A trading interpretation must
therefore specify an execution point after the information cutoff, such as the
next available market observation, and must not assume execution at the same
close used to construct the feature.

### Candidate Horizon Families

No horizon is approved by this document. Reasonable daily-data candidates for
comparison include:

- short: 1–3 observations;
- intermediate: 5–10 observations; and
- longer: 20–30 observations.

Shorter horizons provide more eligible and less-overlapping observations but
are more exposed to market microstructure noise and transaction costs. Longer
horizons may express slower dynamics but reduce effective sample size, increase
label overlap, and require larger purge and holdout reservations.

## Candidate Prediction Targets

## 1. Binary Direction Prediction

### Candidate Target

For horizon \(H\), a basic candidate is:

\[
y_t^{(H)} =
\begin{cases}
1 & \text{if } C_{t+H} > C_t \\
0 & \text{otherwise}
\end{cases}
\]

where \(C_t\) is the completed close at prediction timestamp \(t\).

An alternative definition could introduce a fixed or volatility-scaled neutral
threshold and either omit neutral observations or define a separate class.
That alternative materially changes the research question and would require
separate approval and target versioning.

### Required Label Generation

- Align each eligible feature timestamp \(t\) with the completed close at
  \(t+H\).
- Emit a label only when both closes exist and are validated.
- Define how exact equality is classified.
- Record the timestamp at which \(C_{t+H}\) became available.
- Exclude the final \(H\) source observations unless later completed data is
  added under a new dataset version.

### Strengths

- Directly represents the sign of the future close-to-close move.
- Produces probabilities that can support explicit confidence thresholds if
  probability calibration is separately validated.
- Supports clear class-conditional diagnostics.
- Is insensitive to the units of the underlying price.

### Weaknesses

- Treats economically tiny and very large moves as equivalent.
- A zero threshold may make labels sensitive to noise and transaction costs.
- Class balance can change materially across market regimes.
- Classification accuracy can look acceptable while having no economic value.
- Threshold selection can become a source of data snooping.

### Data Requirements

- Validated closes at \(t\) and \(t+H\).
- Enough observations from both classes in every development split.
- Sufficient regime diversity to assess whether results are temporally stable.
- More data for longer horizons because overlapping labels reduce independent
  information.

### Evaluation Metrics

Primary-metric candidates include PR-AUC, ROC-AUC, macro F1, or a
pre-specified class precision/recall measure, depending on the intended
decision. Directional accuracy is an intuitive secondary measure. Probability
outputs also require calibration diagnostics; classification accuracy alone
is insufficient.

### Leakage Considerations

- The training origin \(t\) is not fully labeled until \(t+H\).
- Training examples whose label intervals cross into a test period must be
  purged.
- A direction threshold estimated from future or full-dataset volatility
  would leak information.
- Class balancing, probability calibration, and threshold selection must be
  fitted independently inside each training fold.
- Overlapping \(H\)-period labels create dependent observations.

### Practical Trading Implications

The output answers a direction question, not whether a move exceeds costs or
supports a profitable trade. Any trading use would need a separately approved
mapping from probability to position, an execution convention, turnover
controls, fees, spread/slippage assumptions, and risk limits.

## 2. Forward Return Regression

### Candidate Target

Simple forward return:

\[
y_t^{(H)} = \frac{C_{t+H}}{C_t} - 1
\]

or log forward return:

\[
y_t^{(H)} = \log\left(\frac{C_{t+H}}{C_t}\right)
\]

Simple and log return are different quantitative definitions. One must be
approved and versioned before label generation.

### Required Label Generation

- Join the feature origin at \(t\) to the validated close at \(t+H\).
- Compute the approved return form using exact recorded inputs.
- Reject labels with missing, incomplete, nonpositive, or invalid source
  prices.
- Preserve sufficient precision and record the label-availability timestamp.
- Exclude source observations that lack a complete forward horizon.

### Strengths

- Preserves both direction and magnitude.
- Allows downstream decisions to distinguish negligible from material moves.
- Supports direct residual analysis and magnitude-sensitive evaluation.
- Can be converted to directional outputs without discarding magnitude during
  fitting.

### Weaknesses

- Financial returns are noisy, heavy-tailed, heteroskedastic, and unstable.
- Squared-error objectives can be dominated by a small number of large moves.
- Point predictions can obscure the uncertainty and asymmetry of outcomes.
- Extreme-event treatment can materially affect conclusions.
- A low aggregate error does not imply useful directional or economic value.

### Data Requirements

- Validated closes at both endpoints.
- Enough observations to characterize tail behavior without allowing a few
  events to dominate the study.
- Multiple market conditions and adequate test observations at the selected
  horizon.
- A documented policy for extreme but valid observations; valid extremes must
  not be silently removed.

### Evaluation Metrics

MAE and RMSE are principal predictive-error candidates. MAE is less dominated
by extreme residuals; RMSE penalizes large misses more strongly. Directional
accuracy can be a secondary diagnostic based on the sign of predicted and
realized returns. Economic metrics apply only after a separate trading rule is
frozen.

### Leakage Considerations

- The full return label is unavailable until \(t+H\).
- Overlapping return windows induce serial dependence.
- Normalization, clipping, winsorization, or target transformation parameters
  must be learned from each training fold only.
- Cross-sectional normalization is not applicable to a single-asset dataset
  and must not be implied.
- Purge and holdout lengths must accommodate the forward horizon.

### Practical Trading Implications

Return magnitude may support ranking, thresholding, or position sizing, but a
point estimate is not a trading instruction. Costs, forecast uncertainty,
exposure constraints, and execution timing can dominate small predicted
returns.

## 3. Volatility Prediction

### Candidate Target

A close-to-close realized-volatility candidate over the future path is:

\[
y_t^{(H)} =
\sqrt{\sum_{i=1}^{H} r_{t+i}^{2}}
\]

where \(r_{t+i}\) is the approved simple or log one-period return. An
annualized version could multiply by a fixed scale factor. Range-based
estimators using future high and low values are another target family, not an
interchangeable implementation detail.

The return definition, aggregation, degrees-of-freedom convention, and any
annualization must be explicitly approved.

### Required Label Generation

- Collect every validated completed candle in the forward interval
  \((t,t+H]\).
- Compute each approved one-period return and the approved aggregate.
- Reject the label if any required future candle is missing or incomplete.
- Record whether the target is raw variance, volatility, log volatility, or an
  annualized quantity.

### Strengths

- Addresses risk magnitude without requiring a directional forecast.
- Volatility is often more persistent than signed returns.
- Has practical uses in exposure sizing, risk limits, and monitoring.
- Produces a nonnegative target with an economically clear unit when defined
  carefully.

### Weaknesses

- Different realized-volatility estimators answer different questions.
- Volatility clustering and extreme events create strongly nonstationary
  residual behavior.
- A point estimate does not describe tail loss or direction.
- Annualization can be misleading when observations are dependent or markets
  trade continuously.
- Multi-day labels overlap heavily unless evaluation steps are widened.

### Data Requirements

- Complete validated future paths, not only endpoint closes.
- Enough high-volatility and low-volatility periods for chronological
  evaluation.
- Consistent daily boundaries and market-session conventions.
- A longer history than direction labels may require to cover varied
  volatility regimes adequately.

### Evaluation Metrics

MAE and RMSE apply to volatility in its approved unit. Error on log volatility
or a volatility-specific loss such as QLIKE could be considered, but each
would need approval. Directional accuracy, ROC-AUC, and PR-AUC do not apply
unless the target is redefined as a classification problem.

### Leakage Considerations

- Every future return inside \((t,t+H]\) is label-only information.
- Rolling volatility used as a feature must end at \(t\); realized volatility
  used as the target must start after \(t\).
- Target scaling or volatility-regime thresholds must be estimated within
  training data only.
- Purging must cover the complete future path, not merely the endpoint.

### Practical Trading Implications

A volatility forecast may inform position size or risk allocation, but it does
not identify long versus short direction. Any risk-sizing interpretation must
define leverage caps, forecast-to-position mapping, and response to extreme
forecasts before economic evaluation.

## 4. Trend-Strength Prediction

### Candidate Target

One bounded candidate is future directional efficiency:

\[
y_t^{(H)} =
\frac{|C_{t+H}-C_t|}
{\sum_{i=1}^{H}|C_{t+i}-C_{t+i-1}|}
\]

when the denominator is positive. Values near one represent a relatively
direct path; values near zero represent a path with substantial reversal.

Other possible targets include absolute forward return normalized by a
predefined risk measure or a future-window trend statistic. These alternatives
do not measure exactly the same construct and require separate approval.

### Required Label Generation

- Collect the complete validated future path from \(t+1\) through \(t+H\).
- Compute the approved path-efficiency or trend statistic.
- Define handling of a zero denominator.
- Decide whether direction is deliberately omitted, encoded separately, or
  incorporated into a signed target.
- Reject labels with gaps or incomplete candles.

### Strengths

- Distinguishes persistent movement from choppy movement.
- Can describe trend quality independently of raw price scale.
- May be relevant to choosing between trend-following and mean-reversion
  behavior.
- A bounded efficiency target can be interpretable.

### Weaknesses

- “Trend strength” has no single canonical definition.
- The target can overlap conceptually with volatility or absolute return.
- Path-based labels create strong overlap between adjacent observations.
- An unsigned target does not supply direction.
- Small definitional changes can materially change the research question.

### Data Requirements

- Every completed candle along the forward path.
- Sufficient examples of persistent trends, reversals, and range-bound
  periods.
- Longer histories for stable coverage of relatively rare sustained trends.
- A definition robust to price scale and numerical edge cases.

### Evaluation Metrics

MAE and RMSE apply to a continuous trend-strength target. If strength is
converted to approved ordered categories, macro F1, per-class precision and
recall, and ordinal-error diagnostics become applicable. Economic metrics
require a separately defined trading policy.

### Leakage Considerations

- All future path values belong exclusively to the label.
- A normalization denominator estimated using future or full-dataset
  volatility would leak information.
- Adjacent targets share most future candles when \(H>1\).
- Any threshold defining “strong” versus “weak” must be frozen using
  development data only.

### Practical Trading Implications

Trend strength could influence strategy selection, exposure persistence, or
trade filtering. It cannot independently determine direction, expected
return, or profitability.

## 5. Multi-Class Market Regime Prediction

### Candidate Target

A forward directional regime candidate could define:

\[
y_t^{(H)} =
\begin{cases}
\text{bearish} & R_t^{(H)} < -\theta \\
\text{neutral} & |R_t^{(H)}| \leq \theta \\
\text{bullish} & R_t^{(H)} > \theta
\end{cases}
\]

where \(R_t^{(H)}\) is an approved forward return and \(\theta\) is a fixed,
pre-approved threshold.

A richer regime definition could combine direction and future volatility, for
example bullish/high-volatility or bearish/low-volatility classes. Such a
definition increases dimensionality and is a separate candidate rather than
an automatic extension.

### Required Label Generation

- Generate the approved underlying future return, volatility, or path
  statistic.
- Apply thresholds fixed before evaluation.
- Define all boundary and equality behavior.
- Record class vocabulary and ordering as part of the target version.
- Reject labels whose full required future window is unavailable.

### Strengths

- Can represent a neutral state rather than forcing every small move into an
  up/down class.
- Produces outputs that may map to differentiated risk or strategy states.
- Supports richer error analysis than a binary target.
- Can combine direction and market intensity when enough evidence exists.

### Weaknesses

- Thresholds are subjective and can be optimized through data snooping.
- Additional classes reduce observations per class and worsen imbalance.
- Regime boundaries may drift as market behavior changes.
- Misclassification costs are not necessarily symmetric.
- Complex regime definitions can become difficult to explain and reproduce.
- The current single-asset daily sample may provide too few examples for
  stable evaluation of rare classes.

### Data Requirements

- Adequate examples of every class in each chronological training and test
  period.
- A longer and more diverse history as class count increases.
- Threshold stability checks confined to development data.
- Complete future paths for any class definition using volatility or trend
  characteristics.

### Evaluation Metrics

Macro F1 and per-class precision/recall prevent dominant classes from hiding
minority-class failure. A confusion matrix is essential. One-vs-rest ROC-AUC
and PR-AUC may be secondary diagnostics if each class has adequate support.
Overall accuracy alone is insufficient. If classes are ordered, distance-aware
errors may be considered.

### Leakage Considerations

- Quantile-derived or volatility-scaled thresholds must be fitted within each
  training fold; full-dataset thresholds leak distributional information.
- Class rebalancing and probability calibration must occur inside training
  folds.
- Regime labels based on future paths require purging through the entire
  horizon.
- Changing class definitions after reviewing holdout results is prohibited.

### Practical Trading Implications

Regime probabilities may support conditional strategy or exposure rules, but
each class needs a predeclared action and asymmetric error cost. A regime label
does not by itself establish an investable strategy.

## Target Comparison

| Candidate | Output | Preserves magnitude | Uses full future path | Typical imbalance risk | Primary practical interpretation |
|---|---|---:|---:|---:|---|
| Binary direction | Probability/class | No | No | Moderate, regime-dependent | Sign of endpoint move |
| Forward return | Continuous return | Yes | No | Not class-based; heavy tails | Direction and endpoint magnitude |
| Volatility | Nonnegative continuous value | Risk magnitude only | Yes | Extreme-value concentration | Future risk intensity |
| Trend strength | Continuous or ordinal strength | Path quality | Yes | Definition-dependent | Persistence versus choppiness |
| Multi-class regime | Class probabilities | Coarse, thresholded | Definition-dependent | High as classes increase | Conditional market state |

None of these targets dominates the others. They answer different research
questions and require different evidence, validation boundaries, and practical
interpretations.

## Baseline Model Survey

No model is approved by this survey. Every estimator would consume the same
chronologically valid development splits for a selected target, and every
preprocessing operation would be fitted separately within each training
window.

### Non-Learned Reference Baselines

Every model study should include target-appropriate reference rules:

- classification: majority-class frequency and a fixed prior estimated from
  the training window;
- return regression: zero return and training-window mean or median;
- volatility: training-window mean/median and approved persistence baseline;
- trend strength: training-window mean/median; and
- regimes: majority class and training-window class priors.

These references are controls, not claims of predictive performance.

### Logistic Regression

- **Applicable targets:** Binary and multi-class classification.
- **Assumptions:** Linear relationship between features and class log-odds,
  correctly specified regularization, and a sufficiently stable conditional
  relationship. Temporal observations are not truly independent, so
  conventional independent-sample inference must not be assumed.
- **Interpretability:** High relative to tree ensembles. Coefficient signs and
  magnitudes are inspectable after accounting for feature scale and
  collinearity.
- **Computational cost:** Low.
- **Financial time-series suitability:** Strong as a transparent linear
  baseline, not as a time-series model by itself.
- **Expected strengths:** Reproducible, regularizable, efficient, and capable
  of probability output.
- **Expected limitations:** Cannot represent nonlinear interactions without
  explicitly approved transformations; sensitive to scaling,
  multicollinearity, outliers, and regime change.

### Linear and Ridge Regression

- **Applicable targets:** Forward return, volatility, and continuous
  trend-strength regression.
- **Assumptions:** The conditional target mean is adequately represented by a
  linear combination of features. Ordinary least squares additionally relies
  on residual assumptions for conventional inference that are unlikely to
  hold automatically in financial time series. Ridge regression adds an
  approved shrinkage parameter but does not remove temporal dependence.
- **Interpretability:** High. Coefficient direction and magnitude are directly
  inspectable after feature scaling and collinearity are considered.
- **Computational cost:** Low.
- **Financial time-series suitability:** Useful as a transparent continuous
  baseline and as a check on whether nonlinear ensembles add evidence beyond a
  regularized linear relationship.
- **Expected strengths:** Deterministic, efficient, auditable, and resistant to
  unnecessary functional complexity.
- **Expected limitations:** Sensitive to scaling, outliers, collinearity, and
  regime instability; cannot capture nonlinear thresholds or interactions
  without explicitly specified transformations.

### Random Forest

- **Applicable targets:** Classification and regression.
- **Assumptions:** Few parametric assumptions, but still assumes that the
  historical feature-target relationship is informative for later periods.
- **Interpretability:** Medium to low. Aggregate importance and partial
  dependence are available but can be biased or misleading with correlated
  features.
- **Computational cost:** Moderate and parallelizable.
- **Financial time-series suitability:** Can model nonlinearities in tabular
  lagged features but has no inherent chronology or extrapolation mechanism.
- **Expected strengths:** Handles nonlinear interactions, requires little
  scaling, and is comparatively robust to individual noisy features.
- **Expected limitations:** Can overfit noisy small samples, produces
  piecewise-constant predictions, extrapolates poorly, and may yield poorly
  calibrated probabilities.

### Gradient Boosted Trees

- **Applicable targets:** Classification and regression.
- **Assumptions:** An additive sequence of shallow trees can approximate a
  stable feature-target mapping; loss and regularization are correctly chosen.
- **Interpretability:** Medium to low. Global and local explanations are
  possible but less direct than a linear model.
- **Computational cost:** Moderate because trees are fitted sequentially.
- **Financial time-series suitability:** Often suitable for nonlinear tabular
  data, provided chronology is externalized through validation.
- **Expected strengths:** Captures interactions, supports varied losses, and
  can perform well without feature scaling.
- **Expected limitations:** Sensitive to tree depth, learning rate, stopping,
  and noisy features; repeated tuning presents substantial data-snooping risk.

### XGBoost

- **Applicable targets:** Classification and regression.
- **Assumptions:** Regularized boosted trees can learn a sufficiently stable
  tabular mapping under the chosen objective.
- **Interpretability:** Medium to low. Feature attribution is possible but
  correlated indicators complicate causal interpretation.
- **Computational cost:** Moderate to high, depending on sample size and search
  breadth.
- **Financial time-series suitability:** Strong candidate for structured
  nonlinear baselines, but it does not independently prevent temporal leakage.
- **Expected strengths:** Regularization, flexible objectives, robust
  engineering, missing-value handling, and strong interaction modeling.
- **Expected limitations:** Large tuning surface, probability calibration
  concerns, instability under regime change, and high risk of overfitting a
  small development sample.

### LightGBM

- **Applicable targets:** Classification and regression.
- **Assumptions:** Histogram-based, leaf-wise boosted trees can learn a stable
  mapping and sample size is sufficient to control leaf complexity.
- **Interpretability:** Medium to low, similar to other boosted-tree systems.
- **Computational cost:** Low to moderate at scale; its efficiency advantage
  may be immaterial for the current dataset.
- **Financial time-series suitability:** Suitable for larger tabular research
  sets with careful chronological validation.
- **Expected strengths:** Fast training, efficient memory use, categorical
  support where relevant, and expressive nonlinear fits.
- **Expected limitations:** Leaf-wise growth can overfit small datasets,
  tuning is consequential, and results can be sensitive to binning and
  minimum-leaf settings.

### CatBoost

- **Applicable targets:** Classification and regression.
- **Assumptions:** Ordered boosting and tree ensembles can learn a stable
  feature-target mapping; categorical handling is most valuable when genuine
  categorical features exist.
- **Interpretability:** Medium to low.
- **Computational cost:** Moderate to high.
- **Financial time-series suitability:** Potentially useful for mixed tabular
  data, although the present engineered feature set is predominantly numeric.
- **Expected strengths:** Strong controls against prediction shift in
  categorical encoding, limited preprocessing requirements, and robust default
  behavior.
- **Expected limitations:** Additional computational complexity, limited
  present benefit without categorical inputs, and the same temporal
  instability and overfitting risks as other boosting methods.
- **Stack status:** CatBoost is not in the currently approved technology stack.
  It is included only because it is a relevant survey candidate. Its future
  implementation would require an explicit stack amendment and is not
  authorized by this document.

## Model Comparison

| Model | Target types | Relative interpretability | Relative cost | Nonlinearity | Principal research risk |
|---|---|---:|---:|---:|---|
| Logistic Regression | Classification | High | Low | Low unless specified | Misspecified linear boundary |
| Linear/Ridge Regression | Regression | High | Low | Low unless specified | Misspecified linear response |
| Random Forest | Both | Medium–low | Moderate | High | Noisy-sample overfit |
| Gradient Boosted Trees | Both | Medium–low | Moderate | High | Tuning/data snooping |
| XGBoost | Both | Medium–low | Moderate–high | High | Complex tuning and instability |
| LightGBM | Both | Medium–low | Low–moderate | High | Leaf-wise overfit on small data |
| CatBoost | Both | Medium–low | Moderate–high | High | Added stack and model complexity |

No model family should receive broader tuning effort merely because it exposes
more parameters. Comparison budgets and search spaces must be fixed before
evaluation.

## Evaluation Design

## Chronological Evaluation Unit

Evaluation must use expanding walk-forward splits with:

- training confined to observations available before the split;
- target-aware purging between training and test origins;
- preprocessing and estimator fitting repeated within each training window;
- non-overlapping test windows unless dependence is explicitly accepted and
  reported;
- the final holdout excluded from all iteration; and
- split boundaries, data hashes, configurations, and results retained as audit
  records.

Fold results must be reported individually as well as in an explicitly
approved aggregate. Aggregation must not obscure a period in which the model
failed materially.

## Classification Metrics

### Precision

\[
\text{Precision} = \frac{TP}{TP+FP}
\]

Precision measures how often predicted positive cases are positive. It matters
when false positive actions are costly. The positive class must be declared.

### Recall

\[
\text{Recall} = \frac{TP}{TP+FN}
\]

Recall measures how many realized positive cases were identified. It matters
when missed positive cases are costly.

### F1

\[
F1 = 2\frac{\text{Precision}\cdot\text{Recall}}
{\text{Precision}+\text{Recall}}
\]

F1 balances precision and recall at a fixed decision threshold. It ignores
true negatives and does not assess probability calibration. Multi-class
studies must declare macro, weighted, or per-class treatment; macro F1 is more
sensitive to minority-class failure.

### ROC-AUC

ROC-AUC measures ranking across true-positive and false-positive rates over
all thresholds. It applies to binary direction and one-vs-rest multi-class
problems. It can appear optimistic under severe class imbalance and does not
define an operating threshold.

### PR-AUC

PR-AUC summarizes precision-recall trade-offs and is generally more sensitive
to minority-class performance. Its baseline depends on class prevalence, so
prevalence must be reported for every fold.

### Directional Accuracy

\[
\text{Directional Accuracy}
= \frac{\#\{\operatorname{sign}(\hat{y}_t)
=\operatorname{sign}(y_t)\}}{N}
\]

Directional accuracy applies directly to binary direction and secondarily to
signed return regression. Zero predictions, zero returns, and neutral classes
require explicit handling. It weights all correctly predicted directions
equally regardless of magnitude or cost.

## Regression Metrics

### MAE

\[
\text{MAE} = \frac{1}{N}\sum_{t=1}^{N}|y_t-\hat{y}_t|
\]

MAE applies to forward return, volatility, and continuous trend-strength
targets. It is comparatively robust to large residuals and remains in the
target's unit.

### RMSE

\[
\text{RMSE}
= \sqrt{\frac{1}{N}\sum_{t=1}^{N}(y_t-\hat{y}_t)^2}
\]

RMSE applies to the same continuous targets but penalizes large errors more
strongly. For heavy-tailed returns it may be dominated by a few events; that
behavior is a property to report, not silently remove.

## Economic and Risk Metrics

Sharpe Ratio, Information Ratio, and Maximum Drawdown do not evaluate a raw
prediction target. They evaluate a time-ordered return stream produced by a
fully specified decision policy. They may be considered only after the
following are frozen:

- prediction-to-position mapping;
- execution timestamp and price;
- fees, spread, slippage, and market-impact assumptions;
- position limits and leverage;
- turnover and rebalance rules;
- benchmark and risk-free-rate conventions; and
- treatment of unavailable predictions.

### Sharpe Ratio

Sharpe Ratio is mean excess strategy return divided by return standard
deviation, with an approved annualization convention. Serial dependence,
overlapping holding periods, and continuously traded crypto markets complicate
annualization. It belongs to policy/backtest evaluation, not pure
classification or regression evaluation.

### Information Ratio

Information Ratio is mean active return relative to a declared benchmark
divided by tracking error. It requires a benchmark fixed before evaluation and
is meaningful only for an implemented decision policy.

### Maximum Drawdown

Maximum Drawdown is the largest peak-to-trough decline of the evaluated equity
curve. It is path-dependent and sensitive to the evaluation period, sizing,
costs, and initial conditions. It must be reported with return metrics rather
than used as a standalone predictive score.

## Metric Applicability

| Metric | Binary direction | Return regression | Volatility | Trend strength | Multi-class regime |
|---|---:|---:|---:|---:|---:|
| Precision / Recall | Primary or diagnostic | No | No | If classified | Per class |
| F1 | Primary or diagnostic | No | No | If classified | Macro/per class |
| ROC-AUC | Ranking diagnostic | No | No | If classified | One-vs-rest |
| PR-AUC | Primary under imbalance | No | No | If classified | One-vs-rest |
| MAE | No | Primary candidate | Primary candidate | Primary candidate | No |
| RMSE | No | Primary candidate | Primary candidate | Primary candidate | No |
| Directional Accuracy | Direct | Secondary | No | Only if signed | Related confusion diagnostic |
| Sharpe Ratio | Policy only | Policy only | Risk policy only | Policy only | Policy only |
| Information Ratio | Policy only | Policy only | Risk policy only | Policy only | Policy only |
| Maximum Drawdown | Policy only | Policy only | Risk policy only | Policy only | Policy only |

Exactly one primary model-selection metric should be approved for a given
research path. Other metrics remain diagnostics. Selecting a model after
reviewing many metrics and reporting only the best-looking one is prohibited.

## Label Leakage and Horizon Analysis

## Label Availability

For every candidate in this document, a label at origin \(t\) is unavailable
until at least \(t+H\). Path-based volatility, trend, and composite regime
labels require every observation through \(t+H\), not only the endpoint.

A training process executed at historical cutoff \(T\) may include only
origins whose labels were fully available at \(T\).

## Purge and Embargo Requirement

Let:

- \(H\) be the target's maximum forward horizon;
- \(W\) be the maximum feature lookback, currently 50 observations; and
- \(G\) be the gap between the last training origin and first test origin.

Under the current conservative separation policy:

\[
G \geq \max(H, W)
\]

The \(H\) component prevents a training label from extending into the test
period. The \(W\) component preserves the existing guarantee that the first
test feature's historical input window is separated from training origins.
If a future target uses an event window longer than its nominal endpoint
horizon, its full information span replaces \(H\).

This formula is a candidate validation rule requiring approval with the target.
The currently configured 50-observation gap is sufficient only for candidates
whose full label horizon does not exceed 50 observations.

## Feature Alignment

For a prediction at completed candle \(t\):

- permitted features end at \(t\);
- the label window begins strictly after \(t\);
- rolling feature warm-up may use observations before \(t\);
- no feature may be recomputed using label-window observations;
- scaling, imputation, calibration, and selection parameters must be learned
  from the training window only; and
- a same-close execution assumption is invalid when that close is part of the
  information set.

## Overlapping Labels

When \(H>1\), labels at adjacent origins share future candles. Consequences
include:

- correlated residuals and classification errors;
- reduced effective sample size;
- overly narrow uncertainty estimates under independent-observation
  assumptions;
- possible overlap between consecutive test windows; and
- repeated economic exposure if predictions are converted to positions.

Candidate controls include setting the evaluation step to at least \(H\),
using non-overlapping evaluation origins, or retaining overlap while applying
dependence-aware inference and explicitly reporting it. The choice must be
approved before experiments.

## Final Holdout Sizing

The final \(H\) raw candles cannot serve as labeled prediction origins without
later data. Therefore, a holdout intended to contain \(K\) evaluable origins
requires at least \(K+H\) completed candles after the development boundary,
and potentially more for non-overlapping origins.

The current 10-observation holdout must not be assumed suitable for every
horizon. Its label-aware size and access rule must be approved before target
generation.

## Horizon Trade-Off Summary

| Horizon characteristic | Shorter \(H\) | Longer \(H\) |
|---|---|---|
| Eligible labeled origins | More | Fewer |
| Label overlap | Lower, but present for \(H>1\) | Higher |
| Required purge | Smaller unless \(W\) dominates | Larger |
| Holdout raw-data requirement | Smaller | Larger |
| Sensitivity to short-term noise/costs | Higher | Potentially lower |
| Regime exposure per sample | Narrower | Broader |
| Effective independent evidence | Higher relative to same history | Lower |
| Feedback delay in live use | Shorter | Longer |

## Data-Snooping Controls

Before opening the final holdout, a future approved research plan must freeze:

- one primary target and target version;
- one or a tightly limited set of predeclared horizons;
- one primary metric;
- model families and their comparison budgets;
- preprocessing and calibration procedures;
- hyperparameter search spaces and stopping rules;
- decision thresholds, if applicable;
- benchmark definitions; and
- criteria for concluding that evidence is insufficient.

All variants attempted on development data must be logged. The final holdout
must not be reused to revise the target, horizon, features, model, or
thresholds. If revisions are necessary after holdout review, that holdout
becomes development evidence and a new untouched holdout is required.

## Reproducibility Record for Future Experiments

Every future experiment record must contain:

- immutable experiment identifier;
- code commit or equivalent code-version identifier;
- source ingestion batch and dataset hash;
- feature run and pipeline version;
- target definition and target version;
- eligible-origin count and excluded-origin reasons;
- validation run identifier and split hash;
- exact train, purge, test, and holdout boundaries;
- model family and complete estimator parameters;
- preprocessing parameters fitted for each split;
- random seeds and deterministic-execution settings;
- prediction and metric artifacts for each fold;
- reference-baseline results;
- software dependency versions; and
- explicit indication of whether the final holdout was accessed.

No failed or superseded experiment record may be deleted merely because its
result is unfavorable.

## Candidate Research Paths

The following paths are alternatives for review. They are not ranked.

### Path A — Directional Probability

- **Question:** Is the future endpoint close above the current close?
- **Candidate targets:** Binary direction at a predeclared short or
  intermediate horizon.
- **Baseline model families:** Logistic Regression, Random Forest, and
  boosted-tree classifiers.
- **Potential primary metrics:** PR-AUC, ROC-AUC, or macro F1.
- **Trade-off:** Clear directional interpretation and probability output, but
  discards magnitude and may reward economically immaterial moves.

### Path B — Forward Return Magnitude

- **Question:** What signed return occurs over the future horizon?
- **Candidate targets:** Simple or log forward return.
- **Baseline model families:** Linear/Ridge Regression, Random Forest, and
  boosted-tree regressors; direction classifiers can serve only as references,
  not equivalent models.
- **Potential primary metrics:** MAE or RMSE, with directional accuracy as a
  diagnostic.
- **Trade-off:** Retains magnitude and sign but is strongly affected by noisy,
  heavy-tailed outcomes and extreme-event treatment.

### Path C — Future Risk Intensity

- **Question:** How volatile is the complete future path?
- **Candidate targets:** Realized variance, realized volatility, or log
  volatility under one approved estimator.
- **Baseline model families:** Linear/Ridge Regression, Random Forest, and
  boosted-tree regressors, compared with a predeclared
  volatility-persistence reference.
- **Potential primary metrics:** MAE, RMSE, or an approved
  volatility-specific loss.
- **Trade-off:** Potentially more persistent and useful for risk sizing, but
  supplies no direction and requires path-complete labels.

### Path D — Trend Persistence

- **Question:** How directly does price move through the future window?
- **Candidate targets:** Bounded path efficiency, normalized absolute return,
  or an approved future trend statistic.
- **Baseline model families:** Linear/Ridge Regression, regression trees, and
  boosted-tree regressors; classification models only if strength categories
  are explicitly approved.
- **Potential primary metrics:** MAE or RMSE for continuous targets; macro F1
  for approved categories.
- **Trade-off:** Captures path quality but lacks a canonical definition and can
  overlap substantially with volatility and absolute-return research.

### Path E — Forward Market Regime

- **Question:** Which predeclared future market state occurs?
- **Candidate targets:** Bearish/neutral/bullish or a limited
  direction-volatility class system.
- **Baseline model families:** Multinomial Logistic Regression, Random Forest,
  and boosted-tree classifiers.
- **Potential primary metrics:** Macro F1 or per-class PR-AUC.
- **Trade-off:** Richer decision states and explicit neutrality, but fewer
  samples per class, threshold instability, and greater data-snooping risk.

## Decisions Required Before Implementation

Explicit human approval is required for:

1. the research question and target family;
2. exact label formula and immutable target version;
3. prediction horizon or predeclared horizon set;
4. prediction-time and execution-time conventions;
5. equality, neutral-zone, threshold, and missing-data treatment;
6. label-aware purge, test-step, and holdout sizes;
7. primary metric and aggregation procedure;
8. eligible model families and equalized comparison budgets;
9. baseline and benchmark definitions;
10. probability calibration or target transformation, if any;
11. dependence-aware uncertainty methodology;
12. criteria for insufficient evidence; and
13. whether any out-of-stack surveyed model warrants a separately approved
    technology-stack amendment.

Until those decisions are approved, AlphaLens has no adopted prediction label,
no authorized machine-learning experiment, and no basis for predictive or
trading claims.
