"""Deterministic one-time evaluation of the selected Ridge holdout."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
import math
import platform
from typing import Any
from uuid import UUID

import numpy as np
import scipy
from scipy import stats
import sklearn
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.research.dataset import ModelObservation, ModelReadyDataset


HOLDOUT_EVALUATION_REPORT_VERSION = "1.0.0"
VALUE_QUANTUM = Decimal("0.000000000000000001")
EXTREME_ERROR_COUNT = 5


class HoldoutEvaluationError(ValueError):
    """Raised when official holdout evidence cannot be evaluated safely."""


@dataclass(frozen=True, slots=True)
class SelectedRidgeSpecification:
    experiment_id: UUID
    model_family: str
    model_parameters: dict[str, Any]
    preprocessing_parameters: dict[str, Any]
    evaluation_policy_parameters: dict[str, Any]
    training_pipeline_version: str
    experiment_configuration_hash: str
    experiment_result_hash: str
    model_dataset_hash: str
    feature_pipeline_version: str
    target_version: str
    validation_run_id: UUID
    split_hash: str
    development_mae: Decimal
    development_rmse: Decimal
    development_directional_accuracy: Decimal


@dataclass(frozen=True, slots=True)
class DevelopmentResidualEvidence:
    mean_residual: Decimal
    residual_variance: Decimal
    prediction_evidence_set_hash: str
    verified_split_prediction_hash_count: int
    prediction_evidence_count: int


@dataclass(frozen=True, slots=True)
class SourceArtifactReference:
    artifact_id: UUID
    artifact_type: str
    configuration_hash: str | None
    result_hash: str


@dataclass(frozen=True, slots=True)
class HoldoutPrediction:
    observation_index: int
    prediction_timestamp: datetime
    label_available_at: datetime
    actual: float
    predicted: float
    residual: float
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class EvaluatedHoldout:
    configuration: dict[str, Any]
    predictions: tuple[HoldoutPrediction, ...]
    holdout_dataset_hash: str
    training_dataset_hash: str
    holdout_prediction_hash: str
    prediction_evidence_set_hash: str
    metrics: dict[str, Any]
    development_comparison: dict[str, Any]
    training_observation_count: int
    purged_observation_count: int
    registered_holdout_observation_count: int
    eligible_holdout_observation_count: int
    excluded_missing_target_count: int
    first_evaluated_timestamp: datetime
    last_evaluated_timestamp: datetime


@dataclass(frozen=True, slots=True)
class BuiltHoldoutEvaluationReport:
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str


def evaluate_official_holdout(
    *,
    dataset: ModelReadyDataset,
    selected: SelectedRidgeSpecification,
    development_residuals: DevelopmentResidualEvidence,
    registered_holdout_timestamps: tuple[datetime, ...],
    holdout_observations: tuple[ModelObservation, ...],
    purge_gap_size: int,
    source_artifacts: tuple[SourceArtifactReference, ...],
) -> EvaluatedHoldout:
    """Perform the single registered fit and protected holdout prediction."""
    _validate_inputs(
        dataset,
        selected,
        development_residuals,
        registered_holdout_timestamps,
        holdout_observations,
        purge_gap_size,
        source_artifacts,
    )
    development = dataset.development_observations
    training = development[:-purge_gap_size]
    purged = development[-purge_gap_size:]
    if (
        not training
        or len(training) < int(
            selected.evaluation_policy_parameters[
                "minimum_training_observations"
            ]
        )
        or max(item.label_available_at for item in training)
        >= dataset.final_holdout_start
        or max(item.prediction_timestamp for item in training)
        >= min(item.prediction_timestamp for item in purged)
    ):
        raise HoldoutEvaluationError(
            "Final training window violates chronology or policy."
        )

    x_train, y_train = _arrays(training)
    x_holdout, y_holdout = _arrays(holdout_observations)
    pipeline = _registered_ridge_pipeline(selected)
    pipeline.fit(x_train, y_train)
    predicted = np.asarray(
        pipeline.predict(x_holdout),
        dtype=np.float64,
    )
    if (
        len(predicted) != len(holdout_observations)
        or not np.all(np.isfinite(predicted))
    ):
        raise HoldoutEvaluationError(
            "Official holdout predictions are incomplete or non-finite."
        )

    residuals = y_holdout - predicted
    holdout_prediction_hash = _sha256_lines(
        float(value).hex() for value in predicted
    )
    holdout_dataset_hash = _observation_hash(holdout_observations)
    training_dataset_hash = _observation_hash(training)
    predictions = tuple(
        _prediction_evidence(
            selected=selected,
            holdout_dataset_hash=holdout_dataset_hash,
            holdout_prediction_hash=holdout_prediction_hash,
            index=index,
            observation=observation,
            actual=float(actual),
            predicted=float(prediction),
            residual=float(residual),
        )
        for index, (observation, actual, prediction, residual) in enumerate(
            zip(
                holdout_observations,
                y_holdout,
                predicted,
                residuals,
                strict=True,
            ),
            start=1,
        )
    )
    evidence_set_hash = _sha256_lines(
        item.evidence_hash for item in predictions
    )
    metrics = _metrics(predictions)
    development_comparison = _development_comparison(
        selected,
        development_residuals,
        metrics,
    )
    excluded_count = (
        len(registered_holdout_timestamps)
        - len(holdout_observations)
    )
    configuration: dict[str, Any] = {
        "report_version": HOLDOUT_EVALUATION_REPORT_VERSION,
        "scope": "one_time_official_protected_holdout_evaluation",
        "selected_experiment": {
            "experiment_id": str(selected.experiment_id),
            "model_family": selected.model_family,
            "model_parameters": selected.model_parameters,
            "preprocessing_parameters": (
                selected.preprocessing_parameters
            ),
            "evaluation_policy_parameters": (
                selected.evaluation_policy_parameters
            ),
            "training_pipeline_version": (
                selected.training_pipeline_version
            ),
            "configuration_hash": (
                selected.experiment_configuration_hash
            ),
            "result_hash": selected.experiment_result_hash,
        },
        "final_fit_policy": {
            "strategy": "expanding_development_window",
            "pre_holdout_purge_observations": purge_gap_size,
            "training_labels_must_be_available_before_holdout": True,
            "scaler_fit_scope": "final_training_partition_only",
            "parameter_changes_permitted": False,
        },
        "holdout_policy": {
            "registered_start": dataset.final_holdout_start.isoformat(),
            "registered_end": dataset.final_holdout_end.isoformat(),
            "registered_observation_count": len(
                registered_holdout_timestamps
            ),
            "incomplete_forward_horizons": (
                "excluded_without_fabrication"
            ),
            "access_authorization": (
                "explicit_one_time_final_evaluation"
            ),
        },
        "metrics": {
            "mae": "mean_absolute_error",
            "rmse": "root_mean_squared_error",
            "directional_accuracy": (
                "mean_sign_predicted_equals_sign_actual"
            ),
            "residual": "actual_minus_predicted",
            "residual_variance": "sample_variance_ddof_1",
            "percentage_difference": (
                "100_times_holdout_minus_development_divided_by_"
                "absolute_development"
            ),
        },
        "error_distribution": {
            "quartiles": "numpy_linear",
            "skewness": "scipy_bias_false",
            "kurtosis": "scipy_excess_bias_false",
            "extreme_error_count": EXTREME_ERROR_COUNT,
        },
        "software_versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "source_artifacts": [
            _artifact_payload(item)
            for item in sorted(
                source_artifacts,
                key=lambda item: (
                    item.artifact_type,
                    str(item.artifact_id),
                ),
            )
        ],
    }
    return EvaluatedHoldout(
        configuration=configuration,
        predictions=predictions,
        holdout_dataset_hash=holdout_dataset_hash,
        training_dataset_hash=training_dataset_hash,
        holdout_prediction_hash=holdout_prediction_hash,
        prediction_evidence_set_hash=evidence_set_hash,
        metrics=metrics,
        development_comparison=development_comparison,
        training_observation_count=len(training),
        purged_observation_count=len(purged),
        registered_holdout_observation_count=len(
            registered_holdout_timestamps
        ),
        eligible_holdout_observation_count=len(holdout_observations),
        excluded_missing_target_count=excluded_count,
        first_evaluated_timestamp=(
            holdout_observations[0].prediction_timestamp
        ),
        last_evaluated_timestamp=(
            holdout_observations[-1].prediction_timestamp
        ),
    )


def build_holdout_evaluation_report(
    *,
    dataset: ModelReadyDataset,
    selected: SelectedRidgeSpecification,
    development_residuals: DevelopmentResidualEvidence,
    evaluated: EvaluatedHoldout,
) -> BuiltHoldoutEvaluationReport:
    """Build the immutable report from the one evaluated prediction set."""
    prediction_payload = [
        {
            "observation_index": item.observation_index,
            "prediction_timestamp": (
                item.prediction_timestamp.isoformat()
            ),
            "label_available_at": item.label_available_at.isoformat(),
            "actual_float_hex": item.actual.hex(),
            "predicted_float_hex": item.predicted.hex(),
            "residual_float_hex": item.residual.hex(),
            "actual": _number(item.actual),
            "predicted": _number(item.predicted),
            "residual": _number(item.residual),
            "absolute_error": _number(abs(item.residual)),
            "evidence_hash": item.evidence_hash,
        }
        for item in evaluated.predictions
    ]
    payload: dict[str, Any] = {
        "report_version": HOLDOUT_EVALUATION_REPORT_VERSION,
        "configuration": evaluated.configuration,
        "provenance": {
            "selected_experiment_id": str(selected.experiment_id),
            "model_dataset_hash": selected.model_dataset_hash,
            "holdout_dataset_hash": evaluated.holdout_dataset_hash,
            "training_dataset_hash": evaluated.training_dataset_hash,
            "feature_pipeline_version": (
                selected.feature_pipeline_version
            ),
            "target_version": selected.target_version,
            "validation_run_id": str(selected.validation_run_id),
            "split_hash": selected.split_hash,
            "source_ingestion_batch_id": str(
                dataset.source_ingestion_batch_id
            ),
            "source_feature_run_id": str(dataset.source_feature_run_id),
            "source_target_run_id": str(dataset.source_target_run_id),
        },
        "prediction_verification": {
            "development_prediction_hashes_verified": (
                development_residuals
                .verified_split_prediction_hash_count
            ),
            "development_prediction_evidence_count": (
                development_residuals.prediction_evidence_count
            ),
            "development_prediction_evidence_set_hash": (
                development_residuals.prediction_evidence_set_hash
            ),
            "holdout_prediction_hash": (
                evaluated.holdout_prediction_hash
            ),
            "holdout_prediction_evidence_set_hash": (
                evaluated.prediction_evidence_set_hash
            ),
            "holdout_prediction_evidence_count": len(
                evaluated.predictions
            ),
        },
        "holdout_coverage": {
            "registered_start": dataset.final_holdout_start.isoformat(),
            "registered_end": dataset.final_holdout_end.isoformat(),
            "first_evaluated_timestamp": (
                evaluated.first_evaluated_timestamp.isoformat()
            ),
            "last_evaluated_timestamp": (
                evaluated.last_evaluated_timestamp.isoformat()
            ),
            "registered_observation_count": (
                evaluated.registered_holdout_observation_count
            ),
            "eligible_observation_count": (
                evaluated.eligible_holdout_observation_count
            ),
            "excluded_missing_target_horizon_count": (
                evaluated.excluded_missing_target_count
            ),
        },
        "final_training_window": {
            "observation_count": (
                evaluated.training_observation_count
            ),
            "purged_observation_count": (
                evaluated.purged_observation_count
            ),
            "start": (
                dataset.development_observations[0]
                .prediction_timestamp.isoformat()
            ),
            "end": (
                dataset.development_observations[
                    evaluated.training_observation_count - 1
                ].prediction_timestamp.isoformat()
            ),
            "latest_label_available_at": max(
                item.label_available_at
                for item in dataset.development_observations[
                    : evaluated.training_observation_count
                ]
            ).isoformat(),
        },
        "holdout_metrics": evaluated.metrics,
        "development_vs_holdout": evaluated.development_comparison,
        "holdout_predictions": prediction_payload,
        "artifact_hashes": {
            "source_artifacts": evaluated.configuration[
                "source_artifacts"
            ],
            "development_prediction_evidence_set_sha256": (
                development_residuals.prediction_evidence_set_hash
            ),
            "holdout_dataset_sha256": evaluated.holdout_dataset_hash,
            "training_dataset_sha256": evaluated.training_dataset_hash,
            "holdout_prediction_sha256": (
                evaluated.holdout_prediction_hash
            ),
            "holdout_prediction_evidence_set_sha256": (
                evaluated.prediction_evidence_set_hash
            ),
        },
        "verification": {
            "official_holdout_evaluation": True,
            "holdout_access_count": 1,
            "holdout_consumption_required": True,
            "report_repeatability_verified": True,
            "development_prediction_hashes_verified": True,
            "model_parameters_modified": False,
            "feature_engineering_performed": False,
            "hyperparameter_tuning_performed": False,
            "experiment_records_modified": False,
            "replacement_model_trained": False,
            "backtest_performed": False,
            "trading_signal_generated": False,
        },
    }
    return BuiltHoldoutEvaluationReport(
        configuration=evaluated.configuration,
        configuration_hash=_sha256_json(evaluated.configuration),
        payload=payload,
        result_hash=_sha256_json(payload),
    )


def _validate_inputs(
    dataset: ModelReadyDataset,
    selected: SelectedRidgeSpecification,
    development_residuals: DevelopmentResidualEvidence,
    registered_holdout_timestamps: tuple[datetime, ...],
    holdout_observations: tuple[ModelObservation, ...],
    purge_gap_size: int,
    source_artifacts: tuple[SourceArtifactReference, ...],
) -> None:
    if (
        selected.model_family != "ridge_regression"
        or selected.model_parameters
        != {
            "alpha": "1.0",
            "fit_intercept": True,
            "solver": "svd",
        }
        or selected.preprocessing_parameters
        != {
            "name": "StandardScaler",
            "with_mean": True,
            "with_std": True,
            "fit_scope": "independent_training_partition_per_split",
        }
    ):
        raise HoldoutEvaluationError(
            "Selected Ridge model configuration differs."
        )
    if (
        not dataset.point_in_time_validated
        or selected.model_dataset_hash != dataset.model_dataset_hash
        or selected.feature_pipeline_version
        != dataset.feature_pipeline_version
        or selected.target_version != dataset.target_version
        or selected.validation_run_id != dataset.validation_run_id
        or selected.split_hash != dataset.validation_split_hash
    ):
        raise HoldoutEvaluationError(
            "Selected model and dataset provenance differ."
        )
    if (
        purge_gap_size <= 0
        or len(dataset.development_observations) <= purge_gap_size
        or development_residuals
        .verified_split_prediction_hash_count
        <= 0
        or development_residuals.prediction_evidence_count <= 0
        or len(
            development_residuals.prediction_evidence_set_hash
        )
        != 64
    ):
        raise HoldoutEvaluationError(
            "Development replay or purge evidence is incomplete."
        )
    if (
        not registered_holdout_timestamps
        or registered_holdout_timestamps[0]
        != dataset.final_holdout_start
        or registered_holdout_timestamps[-1]
        != dataset.final_holdout_end
        or tuple(sorted(set(registered_holdout_timestamps)))
        != registered_holdout_timestamps
    ):
        raise HoldoutEvaluationError(
            "Registered holdout timestamps differ."
        )
    registered = set(registered_holdout_timestamps)
    if (
        not holdout_observations
        or any(
            item.prediction_timestamp not in registered
            or item.label_available_at <= item.prediction_timestamp
            for item in holdout_observations
        )
        or tuple(
            item.prediction_timestamp for item in holdout_observations
        )
        != tuple(
            sorted(
                item.prediction_timestamp
                for item in holdout_observations
            )
        )
    ):
        raise HoldoutEvaluationError(
            "Eligible holdout observations are invalid."
        )
    expected_artifact_types = {
        "model_comparison_report",
        "statistical_validation_report",
        "residual_diagnostics_report",
        "market_regime_analysis_report",
        "final_model_selection_report",
        "random_forest_explainability_artifact",
        "xgboost_explainability_artifact",
    }
    if (
        {item.artifact_type for item in source_artifacts}
        != expected_artifact_types
        or any(len(item.result_hash) != 64 for item in source_artifacts)
    ):
        raise HoldoutEvaluationError(
            "Required immutable source artifacts are incomplete."
        )


def _registered_ridge_pipeline(
    selected: SelectedRidgeSpecification,
) -> Pipeline:
    parameters = dict(selected.model_parameters)
    parameters["alpha"] = float(parameters["alpha"])
    return Pipeline(
        steps=(
            (
                "scaler",
                StandardScaler(with_mean=True, with_std=True),
            ),
            ("regressor", Ridge(**parameters)),
        )
    )


def _arrays(
    observations: tuple[ModelObservation, ...],
) -> tuple[np.ndarray, np.ndarray]:
    features = np.asarray(
        [
            [float(value) for value in item.feature_values]
            for item in observations
        ],
        dtype=np.float64,
    )
    targets = np.asarray(
        [float(item.target_value) for item in observations],
        dtype=np.float64,
    )
    if (
        not len(observations)
        or not np.all(np.isfinite(features))
        or not np.all(np.isfinite(targets))
    ):
        raise HoldoutEvaluationError(
            "Official evaluation arrays are empty or non-finite."
        )
    return features, targets


def _metrics(
    predictions: tuple[HoldoutPrediction, ...],
) -> dict[str, Any]:
    actual = np.asarray(
        [item.actual for item in predictions],
        dtype=np.float64,
    )
    predicted = np.asarray(
        [item.predicted for item in predictions],
        dtype=np.float64,
    )
    residuals = actual - predicted
    q1, median, q3 = np.quantile(
        residuals,
        (0.25, 0.5, 0.75),
        method="linear",
    )
    ordered_best = sorted(
        predictions,
        key=lambda item: (
            abs(item.residual),
            item.prediction_timestamp,
        ),
    )[:EXTREME_ERROR_COUNT]
    ordered_worst = sorted(
        predictions,
        key=lambda item: (
            -abs(item.residual),
            item.prediction_timestamp,
        ),
    )[:EXTREME_ERROR_COUNT]
    return {
        "mae": _number(
            float(mean_absolute_error(actual, predicted))
        ),
        "rmse": _number(
            float(root_mean_squared_error(actual, predicted))
        ),
        "directional_accuracy": _number(
            float(np.mean(np.sign(predicted) == np.sign(actual)))
        ),
        "mean_residual": _number(float(np.mean(residuals))),
        "residual_variance": _number(
            float(np.var(residuals, ddof=1))
        ),
        "error_distribution": {
            "mean": _number(float(np.mean(residuals))),
            "median": _number(float(median)),
            "sample_variance": _number(
                float(np.var(residuals, ddof=1))
            ),
            "sample_standard_deviation": _number(
                float(np.std(residuals, ddof=1))
            ),
            "skewness": _number(
                float(stats.skew(residuals, bias=False))
            ),
            "excess_kurtosis": _number(
                float(
                    stats.kurtosis(
                        residuals,
                        fisher=True,
                        bias=False,
                    )
                )
            ),
            "minimum": _number(float(np.min(residuals))),
            "maximum": _number(float(np.max(residuals))),
            "q1": _number(float(q1)),
            "q3": _number(float(q3)),
            "interquartile_range": _number(float(q3 - q1)),
        },
        "best_prediction_errors": [
            _extreme_payload(item) for item in ordered_best
        ],
        "worst_prediction_errors": [
            _extreme_payload(item) for item in ordered_worst
        ],
    }


def _development_comparison(
    selected: SelectedRidgeSpecification,
    development: DevelopmentResidualEvidence,
    holdout_metrics: dict[str, Any],
) -> dict[str, Any]:
    development_values = {
        "mae": selected.development_mae,
        "rmse": selected.development_rmse,
        "directional_accuracy": (
            selected.development_directional_accuracy
        ),
        "mean_residual": development.mean_residual,
        "residual_variance": development.residual_variance,
    }
    comparison: dict[str, Any] = {}
    for metric, development_value in development_values.items():
        holdout_value = Decimal(holdout_metrics[metric])
        absolute_difference = holdout_value - development_value
        percentage_difference = (
            absolute_difference
            / abs(development_value)
            * Decimal(100)
            if development_value != 0
            else None
        )
        comparison[metric] = {
            "development": format(development_value, "f"),
            "holdout": format(holdout_value, "f"),
            "absolute_difference_holdout_minus_development": format(
                absolute_difference,
                "f",
            ),
            "percentage_difference": (
                _decimal_number(percentage_difference)
                if percentage_difference is not None
                else None
            ),
        }
    return comparison


def _prediction_evidence(
    *,
    selected: SelectedRidgeSpecification,
    holdout_dataset_hash: str,
    holdout_prediction_hash: str,
    index: int,
    observation: ModelObservation,
    actual: float,
    predicted: float,
    residual: float,
) -> HoldoutPrediction:
    evidence_hash = _sha256_json(
        {
            "experiment_id": str(selected.experiment_id),
            "experiment_configuration_hash": (
                selected.experiment_configuration_hash
            ),
            "experiment_result_hash": (
                selected.experiment_result_hash
            ),
            "model_dataset_hash": selected.model_dataset_hash,
            "holdout_dataset_hash": holdout_dataset_hash,
            "split_hash": selected.split_hash,
            "holdout_prediction_hash": holdout_prediction_hash,
            "observation_index": index,
            "prediction_timestamp": (
                observation.prediction_timestamp.isoformat()
            ),
            "label_available_at": (
                observation.label_available_at.isoformat()
            ),
            "actual_float_hex": actual.hex(),
            "predicted_float_hex": predicted.hex(),
            "residual_float_hex": residual.hex(),
        }
    )
    return HoldoutPrediction(
        observation_index=index,
        prediction_timestamp=observation.prediction_timestamp,
        label_available_at=observation.label_available_at,
        actual=actual,
        predicted=predicted,
        residual=residual,
        evidence_hash=evidence_hash,
    )


def _observation_hash(
    observations: tuple[ModelObservation, ...],
) -> str:
    return _sha256_lines(
        "|".join(
            (
                item.prediction_timestamp.isoformat(),
                item.label_available_at.isoformat(),
                *(format(value, "f") for value in item.feature_values),
                format(item.target_value, "f"),
            )
        )
        for item in observations
    )


def _extreme_payload(item: HoldoutPrediction) -> dict[str, Any]:
    return {
        "prediction_timestamp": item.prediction_timestamp.isoformat(),
        "actual": _number(item.actual),
        "predicted": _number(item.predicted),
        "residual": _number(item.residual),
        "absolute_error": _number(abs(item.residual)),
    }


def _artifact_payload(
    item: SourceArtifactReference,
) -> dict[str, Any]:
    return {
        "artifact_id": str(item.artifact_id),
        "artifact_type": item.artifact_type,
        "configuration_hash": item.configuration_hash,
        "result_hash": item.result_hash,
    }


def decimal_value(value: float) -> Decimal:
    """Return the canonical exact database representation."""
    if not math.isfinite(value):
        raise HoldoutEvaluationError("A holdout value is non-finite.")
    with localcontext() as context:
        context.prec = 50
        return Decimal(str(value)).quantize(
            VALUE_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise HoldoutEvaluationError("A holdout statistic is non-finite.")
    return format(float(value), ".17g")


def _decimal_number(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 50
        return format(
            value.quantize(
                VALUE_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            "f",
        )


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
