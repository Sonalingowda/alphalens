"""Equal-domain deterministic scoring for final model selection."""

from decimal import Decimal, localcontext
from typing import Any


MODEL_FAMILY_ORDER: tuple[str, ...] = (
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
)
REGIME_ORDER: tuple[str, ...] = (
    "bull_trend",
    "bear_trend",
    "sideways_market",
    "high_volatility_regime",
    "low_volatility_regime",
)
METRICS: tuple[str, ...] = (
    "mae",
    "rmse",
    "directional_accuracy",
)
SCORE_QUANTUM = Decimal("0.000000000000000001")
SIGNIFICANCE_LEVEL = Decimal("0.05")


class FinalModelSelectionError(ValueError):
    """Raised when immutable selection evidence is incomplete or differs."""


def performance_domain(
    models: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    criteria: list[tuple[str, dict[str, Decimal], bool]] = []
    for metric in METRICS:
        criteria.append(
            (
                metric,
                {
                    family: Decimal(models[family]["metrics"][metric])
                    for family in MODEL_FAMILY_ORDER
                },
                metric == "directional_accuracy",
            )
        )
    scores, criterion_scores = _ranked_domain(criteria)
    return {
        family: {
            "metrics": models[family]["metrics"],
            "criterion_scores": criterion_scores[family],
            "score": scores[family],
        }
        for family in MODEL_FAMILY_ORDER
    }


def statistical_domain(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    points = {family: Decimal(0) for family in MODEL_FAMILY_ORDER}
    comparisons = {family: [] for family in MODEL_FAMILY_ORDER}
    comparison_counts = {family: 0 for family in MODEL_FAMILY_ORDER}
    for pair in payload["pairwise_comparisons"]:
        first = pair["first_model"]
        second = pair["second_model"]
        if first not in points or second not in points:
            raise FinalModelSelectionError(
                "Statistical comparison contains an unapproved model."
            )
        for metric in METRICS:
            evidence = pair["metrics"][metric]
            lower = Decimal(
                evidence["confidence_interval_95"]["lower"]
            )
            upper = Decimal(
                evidence["confidence_interval_95"]["upper"]
            )
            difference = Decimal(evidence["mean_difference"])
            wilcoxon = evidence["wilcoxon"]
            decisive = bool(wilcoxon["significant_at_0_05"]) and (
                (lower > 0 and difference > 0)
                or (upper < 0 and difference < 0)
            )
            favored: str | None = None
            if decisive:
                first_better = (
                    difference > 0
                    if metric == "directional_accuracy"
                    else difference < 0
                )
                favored = first if first_better else second
                points[favored] += Decimal(1)
            else:
                points[first] += Decimal("0.5")
                points[second] += Decimal("0.5")
            comparison_counts[first] += 1
            comparison_counts[second] += 1
            summary = {
                "other_model": second,
                "metric": metric,
                "difference_definition": evidence[
                    "difference_definition"
                ],
                "mean_difference": evidence["mean_difference"],
                "bootstrap_confidence_interval_95": evidence[
                    "confidence_interval_95"
                ],
                "wilcoxon": wilcoxon,
                "effect_size": evidence["effect_size"],
                "paired_t_test": evidence["paired_t_test"],
                "decisive_under_selection_rule": decisive,
                "favored_model": favored,
            }
            comparisons[first].append(summary)
            reverse = dict(summary)
            reverse["other_model"] = first
            comparisons[second].append(reverse)
    if any(count != 9 for count in comparison_counts.values()):
        raise FinalModelSelectionError(
            "Statistical pairwise evidence coverage is incomplete."
        )
    return {
        family: {
            "points": number(points[family]),
            "maximum_points": "9",
            "score": points[family] / Decimal(9),
            "comparisons": sorted(
                comparisons[family],
                key=lambda item: (item["other_model"], item["metric"]),
            ),
        }
        for family in MODEL_FAMILY_ORDER
    }


def residual_domain(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    diagnostics = payload["model_diagnostics"]
    criterion_values: dict[str, dict[str, Decimal]] = {
        "absolute_mean_residual": {},
        "sample_variance": {},
        "absolute_median_residual": {},
        "absolute_skewness": {},
        "absolute_excess_kurtosis": {},
        "maximum_absolute_autocorrelation": {},
        "heteroscedasticity_non_rejection_count": {},
    }
    summaries: dict[str, dict[str, Any]] = {}
    for family in MODEL_FAMILY_ORDER:
        diagnostic = diagnostics[family]
        distribution = diagnostic["residual_distribution"]
        heteroscedasticity = diagnostic["heteroscedasticity_tests"]
        non_rejections = sum(
            Decimal(test["p_value"]) >= SIGNIFICANCE_LEVEL
            for test in heteroscedasticity.values()
        )
        values = {
            "absolute_mean_residual": abs(
                Decimal(distribution["mean"])
            ),
            "sample_variance": Decimal(
                distribution["sample_variance"]
            ),
            "absolute_median_residual": abs(
                Decimal(distribution["median"])
            ),
            "absolute_skewness": abs(
                Decimal(distribution["skewness"])
            ),
            "absolute_excess_kurtosis": abs(
                Decimal(distribution["excess_kurtosis"])
            ),
            "maximum_absolute_autocorrelation": max(
                abs(Decimal(item["autocorrelation"]))
                for item in diagnostic["autocorrelation"]
            ),
            "heteroscedasticity_non_rejection_count": Decimal(
                non_rejections
            ),
        }
        for name, value in values.items():
            criterion_values[name][family] = value
        summaries[family] = {
            "overall_residual_summary": diagnostic[
                "overall_residual_summary"
            ],
            "distribution_characteristics": distribution,
            "heteroscedasticity_tests": heteroscedasticity,
            "autocorrelation": diagnostic["autocorrelation"],
            "derived_selection_criteria": {
                name: number(value) for name, value in values.items()
            },
        }
    criteria = [
        (
            name,
            values,
            name == "heteroscedasticity_non_rejection_count",
        )
        for name, values in criterion_values.items()
    ]
    scores, criterion_scores = _ranked_domain(criteria)
    return {
        family: {
            **summaries[family],
            "criterion_scores": criterion_scores[family],
            "score": scores[family],
        }
        for family in MODEL_FAMILY_ORDER
    }


def market_domain(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    analysis = payload["model_regime_analysis"]
    criteria: list[tuple[str, dict[str, Decimal], bool]] = []
    for regime in REGIME_ORDER:
        for metric in METRICS:
            criteria.append(
                (
                    f"{regime}:{metric}",
                    {
                        family: Decimal(
                            analysis[family][
                                "overall_regime_performance"
                            ][regime][metric]
                        )
                        for family in MODEL_FAMILY_ORDER
                    },
                    metric == "directional_accuracy",
                )
            )
    for metric in METRICS:
        criteria.append(
            (
                f"regime_spread:{metric}",
                {
                    family: Decimal(
                        analysis[family]["stability_across_regimes"][
                            "metric_spreads"
                        ][metric]["performance_spread"]
                    )
                    for family in MODEL_FAMILY_ORDER
                },
                False,
            )
        )
    mean_cv: dict[str, Decimal] = {}
    for family in MODEL_FAMILY_ORDER:
        values = [
            Decimal(summary[metric]["coefficient_of_variation"])
            for summary in analysis[family][
                "stability_across_regimes"
            ]["fold_consistency"].values()
            for metric in METRICS
        ]
        mean_cv[family] = mean(tuple(values))
    criteria.append(("mean_fold_coefficient_of_variation", mean_cv, False))
    scores, criterion_scores = _ranked_domain(criteria)
    return {
        family: {
            "overall_regime_performance": analysis[family][
                "overall_regime_performance"
            ],
            "regime_stability": analysis[family][
                "stability_across_regimes"
            ],
            "mean_fold_coefficient_of_variation": number(
                mean_cv[family]
            ),
            "criterion_scores": criterion_scores[family],
            "score": scores[family],
        }
        for family in MODEL_FAMILY_ORDER
    }


def _ranked_domain(
    criteria: list[tuple[str, dict[str, Decimal], bool]],
) -> tuple[dict[str, Decimal], dict[str, dict[str, str]]]:
    totals = {family: Decimal(0) for family in MODEL_FAMILY_ORDER}
    details = {family: {} for family in MODEL_FAMILY_ORDER}
    for name, values, higher_is_better in criteria:
        scores = _rank_scores(values, higher_is_better=higher_is_better)
        for family in MODEL_FAMILY_ORDER:
            totals[family] += scores[family]
            details[family][name] = number(scores[family])
    count = Decimal(len(criteria))
    return (
        {family: totals[family] / count for family in MODEL_FAMILY_ORDER},
        details,
    )


def _rank_scores(
    values: dict[str, Decimal],
    *,
    higher_is_better: bool,
) -> dict[str, Decimal]:
    if set(values) != set(MODEL_FAMILY_ORDER):
        raise FinalModelSelectionError(
            "A scoring criterion does not cover all approved models."
        )
    ordered = sorted(
        MODEL_FAMILY_ORDER,
        key=lambda family: (
            -values[family]
            if higher_is_better
            else values[family],
            family,
        ),
    )
    scores: dict[str, Decimal] = {}
    index = 0
    denominator = Decimal(len(ordered) - 1)
    while index < len(ordered):
        end = index + 1
        while (
            end < len(ordered)
            and values[ordered[end]] == values[ordered[index]]
        ):
            end += 1
        occupied = tuple(
            Decimal(len(ordered) - 1 - rank) / denominator
            for rank in range(index, end)
        )
        tied_score = mean(occupied)
        for family in ordered[index:end]:
            scores[family] = tied_score
        index = end
    return scores


def mean(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        raise FinalModelSelectionError("Cannot average empty evidence.")
    with localcontext() as context:
        context.prec = 50
        return sum(values, Decimal(0)) / Decimal(len(values))


def number(value: Decimal) -> str:
    return format(value.quantize(SCORE_QUANTUM), "f")


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return number(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    return value
