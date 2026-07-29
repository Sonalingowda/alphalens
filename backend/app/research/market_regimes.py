"""Deterministic point-in-time market regime analysis."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import math
from statistics import median
from typing import Any, Literal
from uuid import UUID

import numpy as np

from app.research.dataset import ModelReadyDataset
from app.research.diagnostic_plots import DiagnosticPlot
from app.research.regime_plots import (
    error_by_regime,
    performance_by_regime,
    residual_distribution_by_regime,
)


ModelFamily = Literal[
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
]
TrendRegime = Literal["bull_trend", "bear_trend", "sideways_market"]
VolatilityRegime = Literal[
    "high_volatility_regime",
    "low_volatility_regime",
]

MARKET_REGIME_REPORT_VERSION = "1.0.0"
REGIME_RULE_VERSION = "1.0.0"
TREND_THRESHOLD = Decimal("0.01")
MODEL_FAMILY_ORDER: tuple[ModelFamily, ...] = (
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
REQUIRED_FEATURES = (
    "sma_20",
    "sma_50",
    "bollinger_20_2_lower",
    "bollinger_20_2_middle",
    "bollinger_20_2_upper",
)


class MarketRegimeAnalysisError(ValueError):
    """Raised when point-in-time regime evidence is invalid."""


@dataclass(frozen=True, slots=True)
class MarketRegimeAssignment:
    prediction_timestamp: Any
    trend_regime: TrendRegime
    volatility_regime: VolatilityRegime
    trend_spread: Decimal
    bollinger_relative_width: Decimal
    expanding_width_median: Decimal
    assignment_hash: str

    @property
    def regimes(self) -> tuple[str, str]:
        return self.trend_regime, self.volatility_regime


@dataclass(frozen=True, slots=True)
class RegimePredictionEvidence:
    experiment_id: UUID
    model_family: ModelFamily
    split_sequence: int
    prediction_timestamp: Any
    actual: float
    predicted: float
    residual: float
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class RegimeModelSource:
    experiment_id: UUID
    model_family: ModelFamily
    experiment_configuration_hash: str
    experiment_result_hash: str
    model_dataset_hash: str
    feature_pipeline_version: str
    target_version: str
    validation_run_id: UUID
    split_hash: str
    evaluated_split_count: int
    evaluated_observation_count: int
    final_holdout_evaluated: bool
    predictions: tuple[RegimePredictionEvidence, ...]


@dataclass(frozen=True, slots=True)
class ResearchArtifactReference:
    artifact_id: UUID
    artifact_type: str
    model_family: str | None
    configuration_hash: str
    result_hash: str


@dataclass(frozen=True, slots=True)
class MarketRegimePlot:
    model_family: ModelFamily
    plot: DiagnosticPlot


@dataclass(frozen=True, slots=True)
class BuiltMarketRegimeReport:
    assignments: tuple[MarketRegimeAssignment, ...]
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    plots: tuple[MarketRegimePlot, ...]


def classify_market_regimes(
    dataset: ModelReadyDataset,
) -> tuple[MarketRegimeAssignment, ...]:
    """Classify trend and volatility from features available through t."""
    if (
        not dataset.point_in_time_validated
        or dataset.feature_pipeline_version != "1.1.0"
        or dataset.target_version != "1.0.0"
    ):
        raise MarketRegimeAnalysisError(
            "The model dataset does not match approved provenance."
        )
    feature_index = {
        name: dataset.feature_names.index(name)
        for name in REQUIRED_FEATURES
    }
    ordered = tuple(
        sorted(
            dataset.development_observations,
            key=lambda item: item.prediction_timestamp,
        )
    )
    if any(
        observation.prediction_timestamp >= dataset.final_holdout_start
        for observation in ordered
    ):
        raise MarketRegimeAnalysisError(
            "Development features include final-holdout observations."
        )

    observed_widths: list[Decimal] = []
    assignments: list[MarketRegimeAssignment] = []
    for observation in ordered:
        values = observation.feature_values
        sma_20 = values[feature_index["sma_20"]]
        sma_50 = values[feature_index["sma_50"]]
        lower = values[feature_index["bollinger_20_2_lower"]]
        middle = values[feature_index["bollinger_20_2_middle"]]
        upper = values[feature_index["bollinger_20_2_upper"]]
        if sma_50 <= 0 or middle <= 0 or upper < lower:
            raise MarketRegimeAnalysisError(
                "A regime feature contains an invalid price relationship."
            )
        trend_spread = sma_20 / sma_50 - Decimal(1)
        relative_width = (upper - lower) / middle
        observed_widths.append(relative_width)
        width_median = median(observed_widths)
        if trend_spread > TREND_THRESHOLD:
            trend: TrendRegime = "bull_trend"
        elif trend_spread < -TREND_THRESHOLD:
            trend = "bear_trend"
        else:
            trend = "sideways_market"
        volatility: VolatilityRegime = (
            "high_volatility_regime"
            if relative_width >= width_median
            else "low_volatility_regime"
        )
        assignment_hash = _sha256_json(
            {
                "rule_version": REGIME_RULE_VERSION,
                "prediction_timestamp": (
                    observation.prediction_timestamp.isoformat()
                ),
                "sma_20": format(sma_20, "f"),
                "sma_50": format(sma_50, "f"),
                "bollinger_lower": format(lower, "f"),
                "bollinger_middle": format(middle, "f"),
                "bollinger_upper": format(upper, "f"),
                "trend_spread": format(trend_spread, "f"),
                "bollinger_relative_width": format(relative_width, "f"),
                "expanding_width_median": format(width_median, "f"),
                "trend_regime": trend,
                "volatility_regime": volatility,
            }
        )
        assignments.append(
            MarketRegimeAssignment(
                prediction_timestamp=observation.prediction_timestamp,
                trend_regime=trend,
                volatility_regime=volatility,
                trend_spread=trend_spread,
                bollinger_relative_width=relative_width,
                expanding_width_median=width_median,
                assignment_hash=assignment_hash,
            )
        )
    return tuple(assignments)


def build_market_regime_report(
    dataset: ModelReadyDataset,
    sources: tuple[RegimeModelSource, ...],
    *,
    statistical_report: ResearchArtifactReference,
    residual_report: ResearchArtifactReference,
    explainability_artifacts: tuple[
        ResearchArtifactReference,
        ...,
    ],
) -> BuiltMarketRegimeReport:
    all_assignments = classify_market_regimes(dataset)
    by_family = {source.model_family: source for source in sources}
    if set(by_family) != set(MODEL_FAMILY_ORDER) or len(sources) != 4:
        raise MarketRegimeAnalysisError(
            "Exactly four approved model sources are required."
        )
    ordered_sources = tuple(by_family[name] for name in MODEL_FAMILY_ORDER)
    prediction_timestamps = frozenset(
        item.prediction_timestamp
        for item in ordered_sources[0].predictions
    )
    assignments = tuple(
        item
        for item in all_assignments
        if item.prediction_timestamp in prediction_timestamps
    )
    _validate_sources(
        dataset,
        assignments,
        ordered_sources,
        statistical_report,
        residual_report,
        explainability_artifacts,
    )

    configuration: dict[str, Any] = {
        "report_version": MARKET_REGIME_REPORT_VERSION,
        "regime_rule_version": REGIME_RULE_VERSION,
        "scope": "chronological_development_predictions_only",
        "membership": {
            "trend_dimension": (
                "exactly_one_of_bull_bear_sideways_per_observation"
            ),
            "volatility_dimension": (
                "exactly_one_of_high_low_per_observation"
            ),
            "regime_memberships_per_observation": 2,
        },
        "regime_order": REGIME_ORDER,
        "definitions": {
            "trend_spread": "sma_20_divided_by_sma_50_minus_1",
            "bull_trend": "trend_spread_strictly_greater_than_0.01",
            "bear_trend": "trend_spread_strictly_less_than_minus_0.01",
            "sideways_market": (
                "trend_spread_between_minus_0.01_and_0.01_inclusive"
            ),
            "bollinger_relative_width": (
                "bollinger_20_2_upper_minus_lower_divided_by_middle"
            ),
            "volatility_reference": (
                "expanding_median_of_bollinger_relative_width_from_first_"
                "model_ready_development_observation_through_current_"
                "timestamp_including_pre_evaluation_warmup_observations"
            ),
            "high_volatility_regime": (
                "current_width_greater_than_or_equal_to_point_in_time_"
                "expanding_median"
            ),
            "low_volatility_regime": (
                "current_width_strictly_less_than_point_in_time_"
                "expanding_median"
            ),
        },
        "feature_inputs": REQUIRED_FEATURES,
        "point_in_time_rule": (
            "classification_at_t_uses_only_completed_features_at_t_and_"
            "volatility_widths_at_or_before_t"
        ),
        "metrics": {
            "mae": "mean_absolute_residual",
            "rmse": "root_mean_squared_residual",
            "directional_accuracy": (
                "mean_sign_predicted_equals_sign_actual"
            ),
            "residual": "actual_minus_predicted",
            "residual_variance": "sample_variance_ddof_1",
        },
        "stability": {
            "primary_performance_metric": "mae",
            "best_worst_tie_break": "regime_order",
            "fold_consistency": (
                "sample_standard_deviation_coefficient_of_variation_"
                "and_interquartile_range_over_nonempty_fold_metrics"
            ),
        },
        "visualizations": {
            "format": "deterministic_svg",
            "per_model": (
                "performance_by_regime_error_by_regime_"
                "residual_distribution_by_regime"
            ),
        },
        "source_experiments": [
            {
                "experiment_id": str(source.experiment_id),
                "model_family": source.model_family,
                "configuration_hash": (
                    source.experiment_configuration_hash
                ),
                "result_hash": source.experiment_result_hash,
            }
            for source in ordered_sources
        ],
        "statistical_validation_report": _reference_payload(
            statistical_report
        ),
        "residual_diagnostics_report": _reference_payload(
            residual_report
        ),
        "explainability_artifacts": [
            _reference_payload(reference)
            for reference in sorted(
                explainability_artifacts,
                key=lambda item: str(item.model_family),
            )
        ],
    }

    assignment_by_timestamp = {
        item.prediction_timestamp: item for item in assignments
    }
    model_results: dict[str, Any] = {}
    plots: list[MarketRegimePlot] = []
    for source in ordered_sources:
        result = _model_regime_analysis(source, assignment_by_timestamp)
        model_results[source.model_family] = result
        statistics = result["overall_regime_performance"]
        model_plots = (
            performance_by_regime(
                source.model_family,
                statistics,
                REGIME_ORDER,
            ),
            error_by_regime(
                source.model_family,
                statistics,
                REGIME_ORDER,
            ),
            residual_distribution_by_regime(
                source.model_family,
                statistics,
                REGIME_ORDER,
            ),
        )
        plots.extend(
            MarketRegimePlot(source.model_family, plot)
            for plot in model_plots
        )

    assignment_payload = [
        {
            "prediction_timestamp": item.prediction_timestamp.isoformat(),
            "trend_regime": item.trend_regime,
            "volatility_regime": item.volatility_regime,
            "trend_spread": format(item.trend_spread, "f"),
            "bollinger_relative_width": format(
                item.bollinger_relative_width,
                "f",
            ),
            "expanding_width_median": format(
                item.expanding_width_median,
                "f",
            ),
            "assignment_hash": item.assignment_hash,
        }
        for item in assignments
    ]
    plot_manifest = [
        {
            "model_family": item.model_family,
            "plot_type": item.plot.plot_type,
            "mime_type": item.plot.mime_type,
            "content_hash": item.plot.content_hash,
        }
        for item in plots
    ]
    payload: dict[str, Any] = {
        "report_version": MARKET_REGIME_REPORT_VERSION,
        "configuration": configuration,
        "provenance": {
            "model_dataset_hash": dataset.model_dataset_hash,
            "feature_pipeline_version": dataset.feature_pipeline_version,
            "target_version": dataset.target_version,
            "validation_run_id": str(dataset.validation_run_id),
            "split_hash": dataset.validation_split_hash,
        },
        "regime_assignments": assignment_payload,
        "regime_assignment_set_hash": _sha256_lines(
            item.assignment_hash for item in assignments
        ),
        "model_regime_analysis": model_results,
        "plot_manifest": plot_manifest,
        "verification": {
            "model_count": len(ordered_sources),
            "assignment_count": len(assignments),
            "prediction_evidence_count": sum(
                len(source.predictions) for source in ordered_sources
            ),
            "evaluated_split_count_per_model": (
                ordered_sources[0].evaluated_split_count
            ),
            "evaluated_observation_count_per_model": (
                ordered_sources[0].evaluated_observation_count
            ),
            "regime_memberships_per_observation": 2,
            "plot_count": len(plots),
            "point_in_time_validated": True,
            "final_holdout_evaluated": False,
            "model_retraining_performed": False,
            "experiments_modified": False,
            "feature_engineering_performed": False,
            "model_selection_performed": False,
            "economic_interpretation_performed": False,
        },
    }
    return BuiltMarketRegimeReport(
        assignments=assignments,
        configuration=configuration,
        configuration_hash=_sha256_json(configuration),
        payload=payload,
        result_hash=_sha256_json(payload),
        plots=tuple(plots),
    )


def _model_regime_analysis(
    source: RegimeModelSource,
    assignments: dict[Any, MarketRegimeAssignment],
) -> dict[str, Any]:
    grouped: dict[str, list[RegimePredictionEvidence]] = {
        name: [] for name in REGIME_ORDER
    }
    fold_grouped: dict[
        int,
        dict[str, list[RegimePredictionEvidence]],
    ] = {}
    for prediction in sorted(
        source.predictions,
        key=lambda item: item.prediction_timestamp,
    ):
        assignment = assignments[prediction.prediction_timestamp]
        fold = fold_grouped.setdefault(
            prediction.split_sequence,
            {name: [] for name in REGIME_ORDER},
        )
        for regime in assignment.regimes:
            grouped[regime].append(prediction)
            fold[regime].append(prediction)
    overall = {
        regime: _performance_metrics(rows)
        for regime, rows in grouped.items()
    }
    if any(item["observation_count"] == 0 for item in overall.values()):
        raise MarketRegimeAnalysisError(
            "At least one required regime has no observations."
        )
    fold_summaries = [
        {
            "split_sequence": sequence,
            "regimes": {
                regime: _performance_metrics(rows)
                for regime, rows in fold_grouped[sequence].items()
            },
        }
        for sequence in sorted(fold_grouped)
    ]
    stability = _stability_analysis(overall, fold_summaries)
    return {
        "experiment_id": str(source.experiment_id),
        "prediction_evidence_set_hash": _sha256_lines(
            item.evidence_hash
            for item in sorted(
                source.predictions,
                key=lambda row: row.prediction_timestamp,
            )
        ),
        "overall_regime_performance": overall,
        "fold_wise_performance": fold_summaries,
        "stability_across_regimes": stability,
    }


def _performance_metrics(
    rows: list[RegimePredictionEvidence],
) -> dict[str, Any]:
    if not rows:
        return {
            "observation_count": 0,
            "mae": None,
            "rmse": None,
            "directional_accuracy": None,
            "mean_residual": None,
            "residual_variance": None,
            "residual_distribution": None,
        }
    actual = np.asarray([item.actual for item in rows], dtype=np.float64)
    predicted = np.asarray(
        [item.predicted for item in rows],
        dtype=np.float64,
    )
    residuals = actual - predicted
    q05, q1, med, q3, q95 = np.quantile(
        residuals,
        (0.05, 0.25, 0.5, 0.75, 0.95),
        method="linear",
    )
    return {
        "observation_count": len(rows),
        "mae": _number(float(np.mean(np.abs(residuals)))),
        "rmse": _number(float(np.sqrt(np.mean(np.square(residuals))))),
        "directional_accuracy": _number(
            float(np.mean(np.sign(predicted) == np.sign(actual)))
        ),
        "mean_residual": _number(float(np.mean(residuals))),
        "residual_variance": (
            _number(float(np.var(residuals, ddof=1)))
            if len(rows) > 1
            else None
        ),
        "residual_distribution": {
            "p05": _number(float(q05)),
            "q1": _number(float(q1)),
            "median": _number(float(med)),
            "q3": _number(float(q3)),
            "p95": _number(float(q95)),
        },
    }


def _stability_analysis(
    overall: dict[str, dict[str, Any]],
    folds: list[dict[str, Any]],
) -> dict[str, Any]:
    metric_results: dict[str, Any] = {}
    for metric, higher_is_better in (
        ("mae", False),
        ("rmse", False),
        ("directional_accuracy", True),
    ):
        values = {
            regime: float(overall[regime][metric])
            for regime in REGIME_ORDER
        }
        ordered = sorted(
            REGIME_ORDER,
            key=lambda regime: (
                -values[regime] if higher_is_better else values[regime],
                REGIME_ORDER.index(regime),
            ),
        )
        metric_results[metric] = {
            "best_performing_regime": ordered[0],
            "best_value": _number(values[ordered[0]]),
            "worst_performing_regime": ordered[-1],
            "worst_value": _number(values[ordered[-1]]),
            "performance_spread": _number(
                max(values.values()) - min(values.values())
            ),
        }
    consistency: dict[str, Any] = {}
    for regime in REGIME_ORDER:
        consistency[regime] = {}
        for metric in ("mae", "rmse", "directional_accuracy"):
            values = np.asarray(
                [
                    float(fold["regimes"][regime][metric])
                    for fold in folds
                    if fold["regimes"][regime]["observation_count"] > 0
                ],
                dtype=np.float64,
            )
            mean = float(np.mean(values))
            standard_deviation = (
                float(np.std(values, ddof=1))
                if len(values) > 1
                else 0.0
            )
            q1, q3 = np.quantile(
                values,
                (0.25, 0.75),
                method="linear",
            )
            consistency[regime][metric] = {
                "nonempty_fold_count": len(values),
                "mean": _number(mean),
                "sample_standard_deviation": _number(
                    standard_deviation
                ),
                "coefficient_of_variation": (
                    _number(standard_deviation / abs(mean))
                    if mean != 0
                    else None
                ),
                "interquartile_range": _number(float(q3 - q1)),
            }
    return {
        "metric_spreads": metric_results,
        "fold_consistency": consistency,
    }


def _validate_sources(
    dataset: ModelReadyDataset,
    assignments: tuple[MarketRegimeAssignment, ...],
    sources: tuple[RegimeModelSource, ...],
    statistical_report: ResearchArtifactReference,
    residual_report: ResearchArtifactReference,
    explainability_artifacts: tuple[
        ResearchArtifactReference,
        ...,
    ],
) -> None:
    timestamps = tuple(
        item.prediction_timestamp for item in assignments
    )
    first = sources[0]
    common_fields = (
        "model_dataset_hash",
        "feature_pipeline_version",
        "target_version",
        "validation_run_id",
        "split_hash",
        "evaluated_split_count",
        "evaluated_observation_count",
    )
    for source in sources:
        if source.final_holdout_evaluated:
            raise MarketRegimeAnalysisError(
                "A source experiment evaluated the final holdout."
            )
        if any(
            getattr(source, field) != getattr(first, field)
            for field in common_fields
        ):
            raise MarketRegimeAnalysisError("Model provenance differs.")
        prediction_timestamps = tuple(
            item.prediction_timestamp
            for item in sorted(
                source.predictions,
                key=lambda row: row.prediction_timestamp,
            )
        )
        if prediction_timestamps != timestamps:
            raise MarketRegimeAnalysisError(
                "Prediction evidence does not cover every assignment."
            )
        if any(
            item.prediction_timestamp >= dataset.final_holdout_start
            for item in source.predictions
        ):
            raise MarketRegimeAnalysisError(
                "Prediction evidence reaches the final holdout."
            )
    provenance = (
        dataset.model_dataset_hash,
        dataset.feature_pipeline_version,
        dataset.target_version,
        dataset.validation_run_id,
        dataset.validation_split_hash,
    )
    source_provenance = (
        first.model_dataset_hash,
        first.feature_pipeline_version,
        first.target_version,
        first.validation_run_id,
        first.split_hash,
    )
    if provenance != source_provenance:
        raise MarketRegimeAnalysisError(
            "Model evidence does not match the active dataset."
        )
    if statistical_report.artifact_type != (
        "statistical_validation_report"
    ):
        raise MarketRegimeAnalysisError(
            "Statistical report reference is invalid."
        )
    if residual_report.artifact_type != "residual_diagnostics_report":
        raise MarketRegimeAnalysisError(
            "Residual report reference is invalid."
        )
    if (
        len(explainability_artifacts) != 2
        or {item.model_family for item in explainability_artifacts}
        != {"random_forest_regression", "xgboost_regression"}
    ):
        raise MarketRegimeAnalysisError(
            "Explainability references are incomplete."
        )


def _reference_payload(
    reference: ResearchArtifactReference,
) -> dict[str, Any]:
    return {
        "artifact_id": str(reference.artifact_id),
        "artifact_type": reference.artifact_type,
        "model_family": reference.model_family,
        "configuration_hash": reference.configuration_hash,
        "result_hash": reference.result_hash,
    }


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise MarketRegimeAnalysisError(
            "Regime analysis produced a non-finite result."
        )
    return format(float(value), ".17g")


def _sha256_lines(values: Any) -> str:
    digest = sha256()
    for value in values:
        digest.update((str(value) + "\n").encode())
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
