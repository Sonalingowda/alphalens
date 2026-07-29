"""Deterministic residual diagnostics from approved experiment replays."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
import math
from typing import Any, Literal
from uuid import UUID

import numpy as np
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from app.research.dataset import ModelObservation, ModelReadyDataset
from app.research.diagnostic_plots import (
    DiagnosticPlot,
    residual_histogram,
    residual_qq_plot,
    residual_vs_actual,
    residual_vs_predicted,
)


ModelFamily = Literal[
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
]

RESIDUAL_DIAGNOSTICS_REPORT_VERSION = "1.0.0"
MODEL_FAMILY_ORDER: tuple[ModelFamily, ...] = (
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
)
HISTOGRAM_BIN_COUNT = 20
AUTOCORRELATION_MAX_LAG = 20
EXTREME_ERROR_COUNT = 10
VALUE_QUANTUM = Decimal("0.000000000000000001")


class ResidualDiagnosticsError(ValueError):
    """Raised when approved residual evidence cannot be reproduced."""


@dataclass(frozen=True, slots=True)
class ReplaySplitEvidence:
    split_record_id: int
    sequence: int
    train_start: Any
    train_end: Any
    test_start: Any
    test_end: Any
    status: str
    train_observation_count: int
    test_observation_count: int
    latest_train_label_available_at: Any
    mae: Decimal | None
    rmse: Decimal | None
    directional_accuracy: Decimal | None
    prediction_hash: str | None


@dataclass(frozen=True, slots=True)
class ResidualExperimentSource:
    experiment_id: UUID
    model_family: ModelFamily
    model_parameters: dict[str, Any]
    preprocessing_parameters: dict[str, Any]
    evaluation_policy_parameters: dict[str, Any]
    random_seeds: tuple[int, ...]
    training_pipeline_version: str
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
    split_evidence: tuple[ReplaySplitEvidence, ...]


@dataclass(frozen=True, slots=True)
class PredictionEvidence:
    experiment_id: UUID
    experiment_split_id: int
    model_family: ModelFamily
    split_sequence: int
    observation_index: int
    prediction_timestamp: Any
    actual: float
    predicted: float
    residual: float
    source_prediction_hash: str
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class ReplayedModelPredictions:
    source: ResidualExperimentSource
    predictions: tuple[PredictionEvidence, ...]
    verified_prediction_hash_count: int


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: UUID
    artifact_type: str
    model_family: str | None
    configuration_hash: str
    result_hash: str


@dataclass(frozen=True, slots=True)
class ModelPlotArtifact:
    model_family: ModelFamily
    plot: DiagnosticPlot


@dataclass(frozen=True, slots=True)
class BuiltResidualDiagnosticsReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    plots: tuple[ModelPlotArtifact, ...]


def replay_approved_experiment(
    dataset: ModelReadyDataset,
    source: ResidualExperimentSource,
) -> ReplayedModelPredictions:
    """Replay exact registered split fits and verify every prediction hash."""
    _validate_source(dataset, source)
    evidence_by_sequence = {
        evidence.sequence: evidence for evidence in source.split_evidence
    }
    if set(evidence_by_sequence) != {
        split.sequence for split in dataset.validation_splits
    }:
        raise ResidualDiagnosticsError(
            "Experiment split evidence is incomplete."
        )

    predictions: list[PredictionEvidence] = []
    verified_hashes = 0
    observed_timestamps: set[Any] = set()
    for split in dataset.validation_splits:
        source_split = evidence_by_sequence[split.sequence]
        _validate_split_boundaries(split, source_split)
        train, test = _split_observations(
            dataset.development_observations,
            split.train_start,
            split.train_end,
            split.test_start,
            split.test_end,
        )
        if len(train) != source_split.train_observation_count:
            raise ResidualDiagnosticsError(
                f"Split {split.sequence} training count differs."
            )
        if len(test) != source_split.test_observation_count:
            raise ResidualDiagnosticsError(
                f"Split {split.sequence} test count differs."
            )
        minimum_training = int(
            source.evaluation_policy_parameters[
                "minimum_training_observations"
            ]
        )
        if len(train) < minimum_training or not test:
            if (
                source_split.status != "skipped"
                or source_split.prediction_hash is not None
            ):
                raise ResidualDiagnosticsError(
                    f"Split {split.sequence} skip evidence differs."
                )
            continue
        if (
            source_split.status != "evaluated"
            or source_split.prediction_hash is None
        ):
            raise ResidualDiagnosticsError(
                f"Split {split.sequence} evaluation evidence differs."
            )
        latest_train_label = max(
            observation.label_available_at for observation in train
        )
        if (
            latest_train_label != source_split.latest_train_label_available_at
            or latest_train_label >= split.test_start
            or max(row.prediction_timestamp for row in train)
            >= min(row.prediction_timestamp for row in test)
        ):
            raise ResidualDiagnosticsError(
                f"Split {split.sequence} violates chronology."
            )
        if any(
            row.prediction_timestamp >= dataset.final_holdout_start
            for row in test
        ):
            raise ResidualDiagnosticsError(
                "Replay attempted to access the protected final holdout."
            )

        x_train, y_train = _arrays(train)
        x_test, y_test = _arrays(test)
        pipeline = _registered_pipeline(source)
        pipeline.fit(x_train, y_train)
        predicted = np.asarray(pipeline.predict(x_test), dtype=np.float64)
        prediction_hash = _prediction_hash(predicted)
        if prediction_hash != source_split.prediction_hash:
            raise ResidualDiagnosticsError(
                f"Split {split.sequence} prediction hash differs: "
                f"expected {source_split.prediction_hash}, "
                f"observed {prediction_hash}."
            )
        _verify_fold_metrics(source_split, y_test, predicted)
        verified_hashes += 1

        for observation_index, (observation, actual, prediction) in enumerate(
            zip(test, y_test, predicted, strict=True),
            start=1,
        ):
            timestamp = observation.prediction_timestamp
            if timestamp in observed_timestamps:
                raise ResidualDiagnosticsError(
                    "Development prediction timestamps overlap across folds."
                )
            observed_timestamps.add(timestamp)
            actual_value = float(actual)
            predicted_value = float(prediction)
            residual_value = actual_value - predicted_value
            evidence_hash = _prediction_evidence_hash(
                source=source,
                split=source_split,
                observation_index=observation_index,
                prediction_timestamp=timestamp,
                actual=actual_value,
                predicted=predicted_value,
                residual=residual_value,
            )
            predictions.append(
                PredictionEvidence(
                    experiment_id=source.experiment_id,
                    experiment_split_id=source_split.split_record_id,
                    model_family=source.model_family,
                    split_sequence=split.sequence,
                    observation_index=observation_index,
                    prediction_timestamp=timestamp,
                    actual=actual_value,
                    predicted=predicted_value,
                    residual=residual_value,
                    source_prediction_hash=prediction_hash,
                    evidence_hash=evidence_hash,
                )
            )

    if (
        verified_hashes != source.evaluated_split_count
        or len(predictions) != source.evaluated_observation_count
    ):
        raise ResidualDiagnosticsError(
            "Replayed prediction coverage differs from the experiment."
        )
    return ReplayedModelPredictions(
        source=source,
        predictions=tuple(predictions),
        verified_prediction_hash_count=verified_hashes,
    )


def build_residual_diagnostics_report(
    replays: tuple[ReplayedModelPredictions, ...],
    *,
    statistical_report: ArtifactReference,
    explainability_artifacts: tuple[ArtifactReference, ...],
) -> BuiltResidualDiagnosticsReport:
    """Build measured residual summaries and deterministic SVG artifacts."""
    by_family = {replay.source.model_family: replay for replay in replays}
    if set(by_family) != set(MODEL_FAMILY_ORDER) or len(replays) != 4:
        raise ResidualDiagnosticsError(
            "Exactly four approved experiment replays are required."
        )
    ordered = tuple(by_family[family] for family in MODEL_FAMILY_ORDER)
    _validate_replay_provenance(
        ordered,
        statistical_report,
        explainability_artifacts,
    )

    configuration: dict[str, Any] = {
        "report_version": RESIDUAL_DIAGNOSTICS_REPORT_VERSION,
        "residual_definition": "actual_minus_predicted",
        "scope": "chronological_development_predictions_only",
        "model_families": MODEL_FAMILY_ORDER,
        "histogram": {
            "bin_count": HISTOGRAM_BIN_COUNT,
            "binning": "numpy_equal_width_observed_range",
        },
        "qq_plot": {
            "distribution": "normal",
            "plotting_positions": "(rank_minus_0.5)_divided_by_n",
            "reference_line": "least_squares_fit",
        },
        "autocorrelation": {
            "lags": list(range(1, AUTOCORRELATION_MAX_LAG + 1)),
            "method": "pearson_correlation_chronological_residuals",
        },
        "heteroscedasticity": {
            "breusch_pagan": {
                "auxiliary_regressors": ["intercept", "predicted"],
                "statistic": "n_times_r_squared",
                "reference_distribution": "chi_squared_df_1",
            },
            "white": {
                "auxiliary_regressors": [
                    "intercept",
                    "predicted",
                    "predicted_squared",
                ],
                "statistic": "n_times_r_squared",
                "reference_distribution": "chi_squared_df_2",
            },
        },
        "extreme_error_count": EXTREME_ERROR_COUNT,
        "variance": "sample_variance_ddof_1",
        "skewness": "scipy_bias_false",
        "kurtosis": "scipy_fisher_true_bias_false",
        "plot_format": "deterministic_svg",
        "source_experiments": [
            {
                "experiment_id": str(replay.source.experiment_id),
                "model_family": replay.source.model_family,
                "model_parameters": replay.source.model_parameters,
                "preprocessing_parameters": (
                    replay.source.preprocessing_parameters
                ),
                "experiment_configuration_hash": (
                    replay.source.experiment_configuration_hash
                ),
                "experiment_result_hash": (
                    replay.source.experiment_result_hash
                ),
            }
            for replay in ordered
        ],
        "statistical_validation_report": _reference_payload(
            statistical_report
        ),
        "explainability_artifacts": [
            _reference_payload(reference)
            for reference in sorted(
                explainability_artifacts,
                key=lambda item: str(item.model_family),
            )
        ],
    }

    model_diagnostics: dict[str, Any] = {}
    plots: list[ModelPlotArtifact] = []
    for replay in ordered:
        diagnostics, model_plots = _model_diagnostics(replay)
        model_diagnostics[replay.source.model_family] = diagnostics
        plots.extend(
            ModelPlotArtifact(
                model_family=replay.source.model_family,
                plot=plot,
            )
            for plot in model_plots
        )
    plot_manifest = [
        {
            "model_family": artifact.model_family,
            "plot_type": artifact.plot.plot_type,
            "mime_type": artifact.plot.mime_type,
            "content_hash": artifact.plot.content_hash,
        }
        for artifact in plots
    ]
    first = ordered[0].source
    payload: dict[str, Any] = {
        "report_version": RESIDUAL_DIAGNOSTICS_REPORT_VERSION,
        "configuration": configuration,
        "provenance": {
            "model_dataset_hash": first.model_dataset_hash,
            "feature_pipeline_version": first.feature_pipeline_version,
            "target_version": first.target_version,
            "validation_run_id": str(first.validation_run_id),
            "split_hash": first.split_hash,
        },
        "model_diagnostics": model_diagnostics,
        "plot_manifest": plot_manifest,
        "verification": {
            "model_count": len(ordered),
            "evaluated_split_count_per_model": (
                ordered[0].source.evaluated_split_count
            ),
            "evaluated_observation_count_per_model": len(
                ordered[0].predictions
            ),
            "prediction_hashes_verified_per_model": (
                ordered[0].verified_prediction_hash_count
            ),
            "prediction_evidence_count": sum(
                len(replay.predictions) for replay in ordered
            ),
            "plot_count": len(plots),
            "deterministic_replay_performed": True,
            "experiment_records_modified": False,
            "final_holdout_evaluated": False,
            "model_tuning_performed": False,
            "model_selection_performed": False,
            "economic_interpretation_performed": False,
        },
    }
    return BuiltResidualDiagnosticsReport(
        configuration=configuration,
        configuration_hash=_sha256_json(configuration),
        payload=payload,
        result_hash=_sha256_json(payload),
        plots=tuple(plots),
    )


def _model_diagnostics(
    replay: ReplayedModelPredictions,
) -> tuple[dict[str, Any], tuple[DiagnosticPlot, ...]]:
    ordered = tuple(
        sorted(
            replay.predictions,
            key=lambda item: (
                item.prediction_timestamp,
                item.split_sequence,
            ),
        )
    )
    actual = np.asarray([item.actual for item in ordered], dtype=np.float64)
    predicted = np.asarray(
        [item.predicted for item in ordered],
        dtype=np.float64,
    )
    residuals = np.asarray(
        [item.residual for item in ordered],
        dtype=np.float64,
    )
    counts, edges = np.histogram(residuals, bins=HISTOGRAM_BIN_COUNT)
    title = replay.source.model_family.replace("_", " ").title()
    plots = (
        residual_histogram(
            residuals,
            title=f"{title}: Residual Histogram",
            bin_count=HISTOGRAM_BIN_COUNT,
        ),
        residual_qq_plot(
            residuals,
            title=f"{title}: Normal QQ Plot",
        ),
        residual_vs_predicted(
            predicted,
            residuals,
            title=f"{title}: Residual vs Predicted",
        ),
        residual_vs_actual(
            actual,
            residuals,
            title=f"{title}: Residual vs Actual",
        ),
    )
    return (
        {
            "experiment_id": str(replay.source.experiment_id),
            "observation_count": len(ordered),
            "prediction_evidence_set_hash": _sha256_lines(
                item.evidence_hash for item in ordered
            ),
            "residual_distribution": {
                **_distribution_summary(residuals),
                "histogram": {
                    "counts": [int(value) for value in counts],
                    "bin_edges": [_number(float(value)) for value in edges],
                },
            },
            "autocorrelation": _autocorrelation(residuals),
            "heteroscedasticity_tests": _heteroscedasticity_tests(
                predicted,
                residuals,
            ),
            "best_prediction_errors": _extreme_errors(
                ordered,
                best=True,
            ),
            "worst_prediction_errors": _extreme_errors(
                ordered,
                best=False,
            ),
            "fold_summaries": _fold_summaries(ordered),
            "overall_residual_summary": {
                "mean_absolute_error": _number(
                    float(np.mean(np.abs(residuals)))
                ),
                "root_mean_squared_error": _number(
                    float(np.sqrt(np.mean(np.square(residuals))))
                ),
                "actual_mean": _number(float(np.mean(actual))),
                "predicted_mean": _number(float(np.mean(predicted))),
                "residual_mean": _number(float(np.mean(residuals))),
            },
        },
        plots,
    )


def _distribution_summary(values: np.ndarray) -> dict[str, Any]:
    q1, median, q3 = np.quantile(
        values,
        (0.25, 0.5, 0.75),
        method="linear",
    )
    return {
        "mean": _number(float(np.mean(values))),
        "median": _number(float(median)),
        "sample_variance": _number(float(np.var(values, ddof=1))),
        "sample_standard_deviation": _number(
            float(np.std(values, ddof=1))
        ),
        "skewness": _number(float(stats.skew(values, bias=False))),
        "excess_kurtosis": _number(
            float(stats.kurtosis(values, fisher=True, bias=False))
        ),
        "minimum": _number(float(np.min(values))),
        "maximum": _number(float(np.max(values))),
        "q1": _number(float(q1)),
        "q3": _number(float(q3)),
        "interquartile_range": _number(float(q3 - q1)),
    }


def _autocorrelation(residuals: np.ndarray) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for lag in range(1, AUTOCORRELATION_MAX_LAG + 1):
        earlier = residuals[:-lag]
        later = residuals[lag:]
        if float(np.std(earlier)) == 0 or float(np.std(later)) == 0:
            coefficient: str | None = None
        else:
            coefficient = _number(
                float(np.corrcoef(earlier, later)[0, 1])
            )
        results.append(
            {
                "lag": lag,
                "paired_observation_count": len(earlier),
                "autocorrelation": coefficient,
            }
        )
    return results


def _heteroscedasticity_tests(
    predicted: np.ndarray,
    residuals: np.ndarray,
) -> dict[str, Any]:
    squared = np.square(residuals)
    intercept = np.ones(len(predicted), dtype=np.float64)
    return {
        "breusch_pagan": _lm_test(
            squared,
            np.column_stack((intercept, predicted)),
            degrees_of_freedom=1,
        ),
        "white": _lm_test(
            squared,
            np.column_stack(
                (intercept, predicted, np.square(predicted))
            ),
            degrees_of_freedom=2,
        ),
    }


def _lm_test(
    dependent: np.ndarray,
    design: np.ndarray,
    *,
    degrees_of_freedom: int,
) -> dict[str, Any]:
    coefficients, *_ = np.linalg.lstsq(design, dependent, rcond=None)
    fitted = design @ coefficients
    centered = dependent - float(np.mean(dependent))
    total_sum_squares = float(np.sum(np.square(centered)))
    residual_sum_squares = float(np.sum(np.square(dependent - fitted)))
    r_squared = (
        max(0.0, min(1.0, 1.0 - residual_sum_squares / total_sum_squares))
        if total_sum_squares > 0
        else 0.0
    )
    statistic = len(dependent) * r_squared
    return {
        "statistic": _number(statistic),
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": _number(
            float(stats.chi2.sf(statistic, degrees_of_freedom))
        ),
        "r_squared": _number(r_squared),
        "observation_count": len(dependent),
    }


def _extreme_errors(
    observations: tuple[PredictionEvidence, ...],
    *,
    best: bool,
) -> list[dict[str, Any]]:
    ordered = sorted(
        observations,
        key=lambda item: (
            abs(item.residual) if best else -abs(item.residual),
            item.prediction_timestamp,
        ),
    )[:EXTREME_ERROR_COUNT]
    return [_prediction_payload(item) for item in ordered]


def _fold_summaries(
    observations: tuple[PredictionEvidence, ...],
) -> list[dict[str, Any]]:
    grouped: dict[int, list[PredictionEvidence]] = {}
    for observation in observations:
        grouped.setdefault(observation.split_sequence, []).append(
            observation
        )
    summaries: list[dict[str, Any]] = []
    for sequence in sorted(grouped):
        rows = sorted(
            grouped[sequence],
            key=lambda item: item.prediction_timestamp,
        )
        residuals = np.asarray(
            [item.residual for item in rows],
            dtype=np.float64,
        )
        summaries.append(
            {
                "split_sequence": sequence,
                "test_start": rows[0].prediction_timestamp.isoformat(),
                "test_end": rows[-1].prediction_timestamp.isoformat(),
                "observation_count": len(rows),
                "residual_mean": _number(float(np.mean(residuals))),
                "residual_median": _number(float(np.median(residuals))),
                "sample_variance": _number(
                    float(np.var(residuals, ddof=1))
                ),
                "mean_absolute_error": _number(
                    float(np.mean(np.abs(residuals)))
                ),
                "root_mean_squared_error": _number(
                    float(np.sqrt(np.mean(np.square(residuals))))
                ),
                "minimum_residual": _number(float(np.min(residuals))),
                "maximum_residual": _number(float(np.max(residuals))),
            }
        )
    return summaries


def _prediction_payload(
    item: PredictionEvidence,
) -> dict[str, Any]:
    return {
        "split_sequence": item.split_sequence,
        "observation_index": item.observation_index,
        "prediction_timestamp": item.prediction_timestamp.isoformat(),
        "actual": _number(item.actual),
        "predicted": _number(item.predicted),
        "residual": _number(item.residual),
        "absolute_error": _number(abs(item.residual)),
        "evidence_hash": item.evidence_hash,
    }


def _validate_source(
    dataset: ModelReadyDataset,
    source: ResidualExperimentSource,
) -> None:
    if source.model_family not in MODEL_FAMILY_ORDER:
        raise ResidualDiagnosticsError("Unsupported model family.")
    if source.final_holdout_evaluated:
        raise ResidualDiagnosticsError(
            "The source experiment evaluated the final holdout."
        )
    checks = (
        source.model_dataset_hash == dataset.model_dataset_hash,
        source.feature_pipeline_version == dataset.feature_pipeline_version,
        source.target_version == dataset.target_version,
        source.validation_run_id == dataset.validation_run_id,
        source.split_hash == dataset.validation_split_hash,
        dataset.point_in_time_validated,
    )
    if not all(checks):
        raise ResidualDiagnosticsError(
            "Experiment provenance does not match the active dataset."
        )
    if source.evaluation_policy_parameters.get(
        "minimum_training_observations"
    ) != 100:
        raise ResidualDiagnosticsError(
            "The approved minimum training policy differs."
        )


def _validate_split_boundaries(
    split: Any,
    source: ReplaySplitEvidence,
) -> None:
    expected = (
        split.train_start,
        split.train_end,
        split.test_start,
        split.test_end,
    )
    observed = (
        source.train_start,
        source.train_end,
        source.test_start,
        source.test_end,
    )
    if expected != observed:
        raise ResidualDiagnosticsError(
            f"Split {split.sequence} boundaries differ."
        )


def _validate_replay_provenance(
    replays: tuple[ReplayedModelPredictions, ...],
    statistical_report: ArtifactReference,
    explainability_artifacts: tuple[ArtifactReference, ...],
) -> None:
    first = replays[0].source
    fields = (
        "model_dataset_hash",
        "feature_pipeline_version",
        "target_version",
        "validation_run_id",
        "split_hash",
        "evaluated_split_count",
        "evaluated_observation_count",
    )
    for replay in replays:
        if any(
            getattr(replay.source, field) != getattr(first, field)
            for field in fields
        ):
            raise ResidualDiagnosticsError("Replay provenance differs.")
        if (
            replay.verified_prediction_hash_count
            != replay.source.evaluated_split_count
        ):
            raise ResidualDiagnosticsError(
                "Not every split prediction hash was verified."
            )
    if statistical_report.artifact_type != "statistical_validation_report":
        raise ResidualDiagnosticsError(
            "The statistical report reference is invalid."
        )
    if (
        len(explainability_artifacts) != 2
        or {item.model_family for item in explainability_artifacts}
        != {"random_forest_regression", "xgboost_regression"}
    ):
        raise ResidualDiagnosticsError(
            "The approved explainability references are incomplete."
        )


def _registered_pipeline(
    source: ResidualExperimentSource,
) -> Pipeline:
    parameters = dict(source.model_parameters)
    if source.model_family == "linear_regression":
        estimator: Any = LinearRegression(**parameters)
    elif source.model_family == "ridge_regression":
        parameters["alpha"] = float(parameters["alpha"])
        estimator = Ridge(**parameters)
    elif source.model_family == "random_forest_regression":
        estimator = RandomForestRegressor(**parameters)
    else:
        if parameters.get("missing") == "NaN":
            parameters["missing"] = np.nan
        estimator = XGBRegressor(**parameters)

    preprocessing = source.preprocessing_parameters
    if source.model_family in (
        "linear_regression",
        "ridge_regression",
    ):
        expected = {
            "name": "StandardScaler",
            "with_mean": True,
            "with_std": True,
            "fit_scope": "independent_training_partition_per_split",
        }
        if preprocessing != expected:
            raise ResidualDiagnosticsError(
                "Registered scaler configuration differs."
            )
        return Pipeline(
            steps=(
                (
                    "scaler",
                    StandardScaler(with_mean=True, with_std=True),
                ),
                ("regressor", estimator),
            )
        )
    if preprocessing.get("name") != "none":
        raise ResidualDiagnosticsError(
            "Registered tree preprocessing configuration differs."
        )
    return Pipeline(steps=(("regressor", estimator),))


def _verify_fold_metrics(
    source: ReplaySplitEvidence,
    actual: np.ndarray,
    predicted: np.ndarray,
) -> None:
    observed = (
        _decimal(mean_absolute_error(actual, predicted)),
        _decimal(root_mean_squared_error(actual, predicted)),
        _decimal(
            float(np.mean(np.sign(predicted) == np.sign(actual)))
        ),
    )
    expected = (
        source.mae,
        source.rmse,
        source.directional_accuracy,
    )
    if observed != expected:
        raise ResidualDiagnosticsError(
            f"Split {source.sequence} metrics do not reproduce."
        )


def _split_observations(
    observations: tuple[ModelObservation, ...],
    train_start: Any,
    train_end: Any,
    test_start: Any,
    test_end: Any,
) -> tuple[tuple[ModelObservation, ...], tuple[ModelObservation, ...]]:
    train = tuple(
        row
        for row in observations
        if train_start <= row.prediction_timestamp <= train_end
    )
    test = tuple(
        row
        for row in observations
        if test_start <= row.prediction_timestamp <= test_end
    )
    return train, test


def _arrays(
    observations: tuple[ModelObservation, ...],
) -> tuple[np.ndarray, np.ndarray]:
    features = np.asarray(
        [
            [float(value) for value in row.feature_values]
            for row in observations
        ],
        dtype=np.float64,
    )
    targets = np.asarray(
        [float(row.target_value) for row in observations],
        dtype=np.float64,
    )
    return features, targets


def _prediction_hash(predicted: np.ndarray) -> str:
    return _sha256_lines(float(value).hex() for value in predicted)


def _prediction_evidence_hash(
    *,
    source: ResidualExperimentSource,
    split: ReplaySplitEvidence,
    observation_index: int,
    prediction_timestamp: Any,
    actual: float,
    predicted: float,
    residual: float,
) -> str:
    return _sha256_json(
        {
            "experiment_id": str(source.experiment_id),
            "experiment_configuration_hash": (
                source.experiment_configuration_hash
            ),
            "experiment_result_hash": source.experiment_result_hash,
            "model_dataset_hash": source.model_dataset_hash,
            "split_hash": source.split_hash,
            "split_sequence": split.sequence,
            "source_prediction_hash": split.prediction_hash,
            "observation_index": observation_index,
            "prediction_timestamp": prediction_timestamp.isoformat(),
            "actual_float_hex": actual.hex(),
            "predicted_float_hex": predicted.hex(),
            "residual_float_hex": residual.hex(),
        }
    )


def _decimal(value: float) -> Decimal:
    if not math.isfinite(value):
        raise ResidualDiagnosticsError("A replayed value is non-finite.")
    with localcontext() as context:
        context.prec = 50
        return Decimal(str(value)).quantize(
            VALUE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def decimal_value(value: float) -> Decimal:
    """Return the canonical database representation of a replayed value."""
    return _decimal(value)


def _reference_payload(reference: ArtifactReference) -> dict[str, Any]:
    return {
        "artifact_id": str(reference.artifact_id),
        "artifact_type": reference.artifact_type,
        "model_family": reference.model_family,
        "configuration_hash": reference.configuration_hash,
        "result_hash": reference.result_hash,
    }


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise ResidualDiagnosticsError(
            "Residual diagnostic produced a non-finite result."
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
