"""Deterministic statistical validation of approved fold-level metrics."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import math
from typing import Any
from uuid import UUID

import numpy as np
from scipy import stats


STATISTICAL_REPORT_VERSION = "1.0.0"
BOOTSTRAP_RANDOM_SEED = 42
BOOTSTRAP_RESAMPLES = 10_000
CONFIDENCE_LEVEL = 0.95
SIGNIFICANCE_LEVEL = 0.05
MODEL_FAMILY_ORDER: tuple[str, ...] = (
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
)
PAIRWISE_COMPARISONS: tuple[tuple[str, str], ...] = (
    ("linear_regression", "ridge_regression"),
    ("linear_regression", "random_forest_regression"),
    ("linear_regression", "xgboost_regression"),
    ("ridge_regression", "random_forest_regression"),
    ("ridge_regression", "xgboost_regression"),
    ("random_forest_regression", "xgboost_regression"),
)
METRICS: tuple[str, ...] = ("mae", "rmse", "directional_accuracy")


@dataclass(frozen=True, slots=True)
class FoldMetricEvidence:
    sequence: int
    test_start: str
    test_end: str
    mae: Decimal
    rmse: Decimal
    directional_accuracy: Decimal
    prediction_hash: str


@dataclass(frozen=True, slots=True)
class StatisticalModelSource:
    experiment_id: UUID
    model_family: str
    configuration_hash: str
    result_hash: str
    model_dataset_hash: str
    feature_pipeline_version: str
    target_version: str
    validation_run_id: UUID
    split_hash: str
    final_holdout_evaluated: bool
    folds: tuple[FoldMetricEvidence, ...]


@dataclass(frozen=True, slots=True)
class ExplainabilityArtifactReference:
    artifact_id: UUID
    experiment_id: UUID
    model_family: str
    configuration_hash: str
    result_hash: str


@dataclass(frozen=True, slots=True)
class BuiltStatisticalValidationReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str


def build_statistical_validation_report(
    sources: tuple[StatisticalModelSource, ...],
    explainability_references: tuple[
        ExplainabilityArtifactReference,
        ...,
    ],
) -> BuiltStatisticalValidationReport:
    """Compare predeclared model pairs using approved fold evidence."""
    by_family = {source.model_family: source for source in sources}
    if set(by_family) != set(MODEL_FAMILY_ORDER) or len(sources) != 4:
        raise ValueError("Exactly four approved model sources are required.")
    ordered_sources = tuple(by_family[family] for family in MODEL_FAMILY_ORDER)
    _validate_sources(ordered_sources, explainability_references)

    configuration: dict[str, Any] = {
        "report_version": STATISTICAL_REPORT_VERSION,
        "model_families": MODEL_FAMILY_ORDER,
        "pairwise_comparisons": PAIRWISE_COMPARISONS,
        "metrics": METRICS,
        "difference_definition": "first_model_minus_second_model",
        "wilcoxon": {
            "alternative": "two-sided",
            "zero_method": "pratt",
            "correction": False,
            "method": "approx",
        },
        "paired_t_test": {
            "alternative": "two-sided",
            "assumption_gate": "shapiro_wilk_p_greater_or_equal_0.05",
            "normality_significance_level": SIGNIFICANCE_LEVEL,
        },
        "effect_sizes": {
            "cohens_d": "paired_cohens_dz",
            "wilcoxon": "matched_pairs_rank_biserial_correlation",
        },
        "bootstrap": {
            "method": "paired_fold_percentile_mean_difference",
            "confidence_level": CONFIDENCE_LEVEL,
            "resamples": BOOTSTRAP_RESAMPLES,
            "random_seed": BOOTSTRAP_RANDOM_SEED,
            "generator": "numpy_PCG64",
        },
        "multiple_comparison_correction": {
            "method": "Holm-Bonferroni",
            "wilcoxon_family_size": len(PAIRWISE_COMPARISONS)
            * len(METRICS),
            "paired_t_test_family": "all_assumption_eligible_tests",
            "significance_level": SIGNIFICANCE_LEVEL,
        },
        "stability": {
            "variance": "sample_variance_ddof_1",
            "coefficient_of_variation": "sample_std_divided_by_absolute_mean",
            "quartiles": "numpy_linear",
            "median_fold": "closest_observed_value_then_lowest_sequence",
        },
        "source_experiments": [
            {
                "experiment_id": str(source.experiment_id),
                "model_family": source.model_family,
                "configuration_hash": source.configuration_hash,
                "result_hash": source.result_hash,
            }
            for source in ordered_sources
        ],
        "explainability_artifacts": [
            {
                "artifact_id": str(reference.artifact_id),
                "experiment_id": str(reference.experiment_id),
                "model_family": reference.model_family,
                "configuration_hash": reference.configuration_hash,
                "result_hash": reference.result_hash,
            }
            for reference in sorted(
                explainability_references,
                key=lambda item: item.model_family,
            )
        ],
    }

    fold_metrics = {
        source.model_family: [
            {
                "sequence": fold.sequence,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "mae": format(fold.mae, "f"),
                "rmse": format(fold.rmse, "f"),
                "directional_accuracy": format(
                    fold.directional_accuracy,
                    "f",
                ),
                "prediction_hash": fold.prediction_hash,
            }
            for fold in source.folds
        ]
        for source in ordered_sources
    }
    stability = {
        source.model_family: {
            metric: _stability_summary(source.folds, metric)
            for metric in METRICS
        }
        for source in ordered_sources
    }
    comparisons = _pairwise_results(by_family)
    payload: dict[str, Any] = {
        "report_version": STATISTICAL_REPORT_VERSION,
        "configuration": configuration,
        "provenance": {
            "model_dataset_hash": ordered_sources[0].model_dataset_hash,
            "feature_pipeline_version": (
                ordered_sources[0].feature_pipeline_version
            ),
            "target_version": ordered_sources[0].target_version,
            "validation_run_id": str(
                ordered_sources[0].validation_run_id
            ),
            "split_hash": ordered_sources[0].split_hash,
        },
        "fold_level_metrics": fold_metrics,
        "stability_analysis": stability,
        "pairwise_comparisons": comparisons,
        "verification": {
            "model_count": len(ordered_sources),
            "pair_count": len(PAIRWISE_COMPARISONS),
            "metric_count": len(METRICS),
            "hypothesis_count": len(PAIRWISE_COMPARISONS)
            * len(METRICS),
            "evaluated_fold_count_per_model": len(
                ordered_sources[0].folds
            ),
            "prediction_hash_count_per_model": len(
                ordered_sources[0].folds
            ),
            "model_retraining_performed": False,
            "final_holdout_evaluated": False,
            "model_selection_performed": False,
            "economic_interpretation_performed": False,
        },
    }
    return BuiltStatisticalValidationReport(
        configuration=configuration,
        configuration_hash=_sha256_json(configuration),
        payload=payload,
        result_hash=_sha256_json(payload),
    )


def _validate_sources(
    sources: tuple[StatisticalModelSource, ...],
    explainability_references: tuple[
        ExplainabilityArtifactReference,
        ...,
    ],
) -> None:
    first = sources[0]
    common_fields = (
        "model_dataset_hash",
        "feature_pipeline_version",
        "target_version",
        "validation_run_id",
        "split_hash",
    )
    expected_sequences = tuple(fold.sequence for fold in first.folds)
    expected_boundaries = tuple(
        (fold.test_start, fold.test_end) for fold in first.folds
    )
    if not expected_sequences:
        raise ValueError("Approved fold evidence is empty.")
    for source in sources:
        if source.final_holdout_evaluated:
            raise ValueError("A source experiment evaluated the holdout.")
        if any(
            getattr(source, field) != getattr(first, field)
            for field in common_fields
        ):
            raise ValueError("Source experiment provenance differs.")
        if tuple(fold.sequence for fold in source.folds) != expected_sequences:
            raise ValueError("Source fold sequences differ.")
        if tuple(
            (fold.test_start, fold.test_end) for fold in source.folds
        ) != expected_boundaries:
            raise ValueError("Source fold boundaries differ.")
        if any(len(fold.prediction_hash) != 64 for fold in source.folds):
            raise ValueError("Source prediction registry is incomplete.")
    if len(explainability_references) != 2:
        raise ValueError("Two explainability artifacts are required.")
    for reference in explainability_references:
        source = next(
            (
                item
                for item in sources
                if item.model_family == reference.model_family
            ),
            None,
        )
        if source is None or source.experiment_id != reference.experiment_id:
            raise ValueError("Explainability provenance does not match.")


def _pairwise_results(
    sources: dict[str, StatisticalModelSource],
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(BOOTSTRAP_RANDOM_SEED)
    results: list[dict[str, Any]] = []
    for first_family, second_family in PAIRWISE_COMPARISONS:
        first = sources[first_family]
        second = sources[second_family]
        metric_results: dict[str, Any] = {}
        for metric in METRICS:
            first_values = _metric_array(first.folds, metric)
            second_values = _metric_array(second.folds, metric)
            differences = first_values - second_values
            wilcoxon_statistic, wilcoxon_p = _wilcoxon(differences)
            shapiro_statistic, shapiro_p = _shapiro(differences)
            t_eligible = (
                float(np.std(differences, ddof=1)) > 0
                and shapiro_p >= SIGNIFICANCE_LEVEL
            )
            if t_eligible:
                t_result = stats.ttest_rel(
                    first_values,
                    second_values,
                    alternative="two-sided",
                )
                t_test: dict[str, Any] = {
                    "performed": True,
                    "statistic": _number(float(t_result.statistic)),
                    "raw_p_value": _number(float(t_result.pvalue)),
                    "adjusted_p_value": None,
                }
                t_raw_p: float | None = float(t_result.pvalue)
            else:
                t_test = {
                    "performed": False,
                    "reason": (
                        "paired_differences_failed_predeclared_"
                        "normality_gate"
                    ),
                    "statistic": None,
                    "raw_p_value": None,
                    "adjusted_p_value": None,
                }
                t_raw_p = None
            ci_lower, ci_upper = _bootstrap_ci(differences, rng)
            sample_std = float(np.std(differences, ddof=1))
            cohens_d = (
                float(np.mean(differences)) / sample_std
                if sample_std > 0
                else None
            )
            metric_results[metric] = {
                "observation_count": len(differences),
                "difference_definition": (
                    f"{first_family}_minus_{second_family}"
                ),
                "mean_difference": _number(
                    float(np.mean(differences))
                ),
                "median_difference": _number(
                    float(np.median(differences))
                ),
                "confidence_interval_95": {
                    "lower": _number(ci_lower),
                    "upper": _number(ci_upper),
                    "method": "paired_fold_percentile_mean_difference",
                },
                "wilcoxon": {
                    "statistic": _number(wilcoxon_statistic),
                    "raw_p_value": _number(wilcoxon_p),
                    "adjusted_p_value": None,
                    "rank_biserial_correlation": _number(
                        _rank_biserial(differences)
                    ),
                    "_raw_p": wilcoxon_p,
                },
                "normality_assessment": {
                    "test": "Shapiro-Wilk",
                    "statistic": _number(shapiro_statistic),
                    "p_value": _number(shapiro_p),
                    "paired_t_test_assumption_satisfied": t_eligible,
                },
                "paired_t_test": {
                    **t_test,
                    "_raw_p": t_raw_p,
                },
                "effect_size": {
                    "paired_cohens_dz": (
                        _number(cohens_d)
                        if cohens_d is not None
                        else None
                    ),
                },
            }
        results.append(
            {
                "first_model": first_family,
                "second_model": second_family,
                "metrics": metric_results,
            }
        )
    _apply_holm(results, "wilcoxon")
    _apply_holm(results, "paired_t_test")
    return results


def _apply_holm(
    comparisons: list[dict[str, Any]],
    test_name: str,
) -> None:
    hypotheses: list[tuple[float, str, dict[str, Any]]] = []
    for comparison in comparisons:
        for metric in METRICS:
            test = comparison["metrics"][metric][test_name]
            raw_p = test.pop("_raw_p")
            if raw_p is not None:
                identifier = (
                    f"{comparison['first_model']}__"
                    f"{comparison['second_model']}__{metric}"
                )
                hypotheses.append((raw_p, identifier, test))
    ordered = sorted(hypotheses, key=lambda item: (item[0], item[1]))
    running_adjusted = 0.0
    family_size = len(ordered)
    for index, (raw_p, _, test) in enumerate(ordered):
        adjusted = min(
            1.0,
            max(
                running_adjusted,
                (family_size - index) * raw_p,
            ),
        )
        running_adjusted = adjusted
        test["adjusted_p_value"] = _number(adjusted)
        test["holm_family_size"] = family_size
        test["significant_at_0_05"] = adjusted < SIGNIFICANCE_LEVEL


def _stability_summary(
    folds: tuple[FoldMetricEvidence, ...],
    metric: str,
) -> dict[str, Any]:
    values = _metric_array(folds, metric)
    mean = float(np.mean(values))
    sample_std = float(np.std(values, ddof=1))
    variance = float(np.var(values, ddof=1))
    q1, q3 = np.quantile(values, (0.25, 0.75), method="linear")
    median = float(np.median(values))
    best_index = (
        int(np.argmax(values))
        if metric == "directional_accuracy"
        else int(np.argmin(values))
    )
    worst_index = (
        int(np.argmin(values))
        if metric == "directional_accuracy"
        else int(np.argmax(values))
    )
    median_index = min(
        range(len(folds)),
        key=lambda index: (
            abs(float(values[index]) - median),
            folds[index].sequence,
        ),
    )
    return {
        "mean": _number(mean),
        "sample_variance": _number(variance),
        "sample_standard_deviation": _number(sample_std),
        "coefficient_of_variation": (
            _number(sample_std / abs(mean)) if mean != 0 else None
        ),
        "median": _number(median),
        "interquartile_range": _number(float(q3 - q1)),
        "q1": _number(float(q1)),
        "q3": _number(float(q3)),
        "best_fold": _fold_reference(folds[best_index], metric),
        "worst_fold": _fold_reference(folds[worst_index], metric),
        "median_fold": _fold_reference(folds[median_index], metric),
    }


def _fold_reference(
    fold: FoldMetricEvidence,
    metric: str,
) -> dict[str, Any]:
    return {
        "sequence": fold.sequence,
        "test_start": fold.test_start,
        "test_end": fold.test_end,
        "value": format(getattr(fold, metric), "f"),
    }


def _metric_array(
    folds: tuple[FoldMetricEvidence, ...],
    metric: str,
) -> np.ndarray:
    return np.asarray(
        [float(getattr(fold, metric)) for fold in folds],
        dtype=np.float64,
    )


def _wilcoxon(differences: np.ndarray) -> tuple[float, float]:
    if np.all(differences == 0):
        return 0.0, 1.0
    result = stats.wilcoxon(
        differences,
        zero_method="pratt",
        correction=False,
        alternative="two-sided",
        method="approx",
    )
    return float(result.statistic), float(result.pvalue)


def _shapiro(differences: np.ndarray) -> tuple[float, float]:
    if float(np.std(differences, ddof=1)) == 0:
        return 1.0, 0.0
    result = stats.shapiro(differences)
    return float(result.statistic), float(result.pvalue)


def _rank_biserial(differences: np.ndarray) -> float:
    ranks = stats.rankdata(np.abs(differences), method="average")
    positive = float(np.sum(ranks[differences > 0]))
    negative = float(np.sum(ranks[differences < 0]))
    denominator = positive + negative
    return (positive - negative) / denominator if denominator else 0.0


def _bootstrap_ci(
    differences: np.ndarray,
    rng: np.random.Generator,
) -> tuple[float, float]:
    indexes = rng.integers(
        0,
        len(differences),
        size=(BOOTSTRAP_RESAMPLES, len(differences)),
    )
    means = np.mean(differences[indexes], axis=1)
    alpha = (1.0 - CONFIDENCE_LEVEL) / 2.0
    lower, upper = np.quantile(
        means,
        (alpha, 1.0 - alpha),
        method="linear",
    )
    return float(lower), float(upper)


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("Statistical result is non-finite.")
    return format(float(value), ".17g")


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
