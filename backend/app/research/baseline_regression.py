"""Deterministic chronological regression baselines."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
from typing import Literal

import numpy as np
import sklearn
import xgboost
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from app.research.dataset import (
    ModelObservation,
    ModelReadyDataset,
    ResearchSplit,
)


ModelFamily = Literal[
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
]

TRAINING_PIPELINE_VERSION = "1.3.0"
EVALUATION_POLICY_VERSION = "1.1.0"
MINIMUM_TRAINING_OBSERVATIONS = 100
RIDGE_ALPHA = 1.0
RANDOM_FOREST_RANDOM_STATE = 42
XGBOOST_RANDOM_STATE = 42
XGBOOST_MODEL_PARAMETERS: dict[str, object] = {
    "objective": "reg:squarederror",
    "base_score": None,
    "booster": "gbtree",
    "callbacks": None,
    "colsample_bylevel": 1.0,
    "colsample_bynode": 1.0,
    "colsample_bytree": 1.0,
    "device": "cpu",
    "early_stopping_rounds": None,
    "enable_categorical": False,
    "eval_metric": None,
    "feature_types": None,
    "feature_weights": None,
    "gamma": 0.0,
    "grow_policy": "depthwise",
    "importance_type": None,
    "interaction_constraints": None,
    "learning_rate": 0.1,
    "max_bin": 256,
    "max_cat_threshold": None,
    "max_cat_to_onehot": None,
    "max_delta_step": 0.0,
    "max_depth": 6,
    "max_leaves": 0,
    "min_child_weight": 1.0,
    "missing": "NaN",
    "monotone_constraints": None,
    "multi_strategy": "one_output_per_tree",
    "n_estimators": 100,
    "n_jobs": 1,
    "num_parallel_tree": 1,
    "random_state": XGBOOST_RANDOM_STATE,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "sampling_method": "uniform",
    "scale_pos_weight": 1.0,
    "subsample": 1.0,
    "tree_method": "hist",
    "validate_parameters": True,
    "verbosity": 0,
}
METRIC_QUANTUM = Decimal("0.000000000000000001")


class BaselineExperimentError(ValueError):
    """Raised when a chronological baseline cannot be evaluated."""


@dataclass(frozen=True, slots=True)
class SplitEvaluation:
    sequence: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_observation_count: int
    test_observation_count: int
    status: str
    exclusion_reason: str | None
    latest_train_label_available_at: datetime | None
    mae: Decimal | None
    rmse: Decimal | None
    directional_accuracy: Decimal | None
    prediction_hash: str | None


@dataclass(frozen=True, slots=True)
class BaselineEvaluation:
    model_family: ModelFamily
    model_parameters: dict[str, object]
    preprocessing_parameters: dict[str, object]
    evaluation_policy_parameters: dict[str, object]
    random_seeds: tuple[int, ...]
    training_pipeline_version: str
    training_code_hash: str
    experiment_configuration_hash: str
    result_hash: str
    split_evaluations: tuple[SplitEvaluation, ...]
    evaluated_split_count: int
    skipped_split_count: int
    evaluated_observation_count: int
    aggregate_mae: Decimal
    aggregate_rmse: Decimal
    aggregate_directional_accuracy: Decimal
    aggregation_method: str
    software_versions: dict[str, str]
    point_in_time_validated: bool
    final_holdout_evaluated: bool


def run_baseline_evaluation(
    dataset: ModelReadyDataset,
    model_family: ModelFamily,
) -> BaselineEvaluation:
    """Fit fresh preprocessing and estimator instances inside every split."""
    if model_family not in (
        "linear_regression",
        "ridge_regression",
        "random_forest_regression",
        "xgboost_regression",
    ):
        raise BaselineExperimentError(
            f"Unsupported baseline model family: {model_family}."
        )
    if not dataset.point_in_time_validated:
        raise BaselineExperimentError(
            "Model-ready dataset failed point-in-time validation."
        )
    if any(
        observation.prediction_timestamp >= dataset.final_holdout_start
        for observation in dataset.development_observations
    ):
        raise BaselineExperimentError(
            "Development observations contain final-holdout timestamps."
        )

    model_parameters = _model_parameters(model_family)
    preprocessing_parameters = _preprocessing_parameters(model_family)
    evaluation_policy_parameters: dict[str, object] = {
        "name": "minimum_training_observations",
        "version": EVALUATION_POLICY_VERSION,
        "minimum_training_observations": MINIMUM_TRAINING_OBSERVATIONS,
        "comparison": (
            "train_observation_count >= minimum_training_observations"
        ),
        "applies_to": "all_baseline_model_families",
    }
    random_seeds = _random_seeds(model_family)
    configuration_hash = _configuration_hash(
        dataset,
        model_family,
        model_parameters,
        preprocessing_parameters,
        evaluation_policy_parameters,
        random_seeds,
    )

    split_results: list[SplitEvaluation] = []
    pooled_actual: list[float] = []
    pooled_predicted: list[float] = []
    for split in dataset.validation_splits:
        result, actual, predicted = _evaluate_split(
            dataset.development_observations,
            split,
            model_family,
        )
        split_results.append(result)
        pooled_actual.extend(actual)
        pooled_predicted.extend(predicted)

    if not pooled_actual:
        raise BaselineExperimentError(
            "No validation split contains evaluable observations."
        )
    actual_array = np.asarray(pooled_actual, dtype=np.float64)
    predicted_array = np.asarray(pooled_predicted, dtype=np.float64)
    aggregate_mae = _metric_decimal(
        mean_absolute_error(actual_array, predicted_array)
    )
    aggregate_rmse = _metric_decimal(
        root_mean_squared_error(actual_array, predicted_array)
    )
    aggregate_directional_accuracy = _metric_decimal(
        float(
            np.mean(
                np.sign(predicted_array) == np.sign(actual_array)
            )
        )
    )
    evaluations = tuple(split_results)
    result_hash = _result_hash(
        evaluations,
        aggregate_mae,
        aggregate_rmse,
        aggregate_directional_accuracy,
    )

    return BaselineEvaluation(
        model_family=model_family,
        model_parameters=model_parameters,
        preprocessing_parameters=preprocessing_parameters,
        evaluation_policy_parameters=evaluation_policy_parameters,
        random_seeds=random_seeds,
        training_pipeline_version=TRAINING_PIPELINE_VERSION,
        training_code_hash=_training_code_hash(),
        experiment_configuration_hash=configuration_hash,
        result_hash=result_hash,
        split_evaluations=evaluations,
        evaluated_split_count=sum(
            result.status == "evaluated" for result in evaluations
        ),
        skipped_split_count=sum(
            result.status == "skipped" for result in evaluations
        ),
        evaluated_observation_count=len(pooled_actual),
        aggregate_mae=aggregate_mae,
        aggregate_rmse=aggregate_rmse,
        aggregate_directional_accuracy=(
            aggregate_directional_accuracy
        ),
        aggregation_method="pooled_out_of_sample_predictions",
        software_versions={
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        point_in_time_validated=True,
        final_holdout_evaluated=False,
    )


def _evaluate_split(
    observations: tuple[ModelObservation, ...],
    split: ResearchSplit,
    model_family: ModelFamily,
) -> tuple[SplitEvaluation, list[float], list[float]]:
    train = tuple(
        observation
        for observation in observations
        if split.train_start
        <= observation.prediction_timestamp
        <= split.train_end
    )
    test = tuple(
        observation
        for observation in observations
        if split.test_start
        <= observation.prediction_timestamp
        <= split.test_end
    )
    if len(train) < MINIMUM_TRAINING_OBSERVATIONS:
        return (
            SplitEvaluation(
                sequence=split.sequence,
                train_start=split.train_start,
                train_end=split.train_end,
                test_start=split.test_start,
                test_end=split.test_end,
                train_observation_count=len(train),
                test_observation_count=len(test),
                status="skipped",
                exclusion_reason=(
                    "minimum_training_observations_not_met:"
                    f"required={MINIMUM_TRAINING_OBSERVATIONS},"
                    f"observed={len(train)}"
                ),
                latest_train_label_available_at=(
                    max(row.label_available_at for row in train)
                    if train
                    else None
                ),
                mae=None,
                rmse=None,
                directional_accuracy=None,
                prediction_hash=None,
            ),
            [],
            [],
        )
    if not test:
        return (
            SplitEvaluation(
                sequence=split.sequence,
                train_start=split.train_start,
                train_end=split.train_end,
                test_start=split.test_start,
                test_end=split.test_end,
                train_observation_count=len(train),
                test_observation_count=0,
                status="skipped",
                exclusion_reason="no_model_ready_test_observations",
                latest_train_label_available_at=max(
                    row.label_available_at for row in train
                ),
                mae=None,
                rmse=None,
                directional_accuracy=None,
                prediction_hash=None,
            ),
            [],
            [],
        )

    latest_train_label_available_at = max(
        row.label_available_at for row in train
    )
    if latest_train_label_available_at >= split.test_start:
        raise BaselineExperimentError(
            f"Training labels overlap test split {split.sequence}."
        )
    if max(row.prediction_timestamp for row in train) >= min(
        row.prediction_timestamp for row in test
    ):
        raise BaselineExperimentError(
            f"Chronology is invalid for split {split.sequence}."
        )

    x_train, y_train = _arrays(train)
    x_test, y_test = _arrays(test)
    pipeline = _new_pipeline(model_family)
    pipeline.fit(x_train, y_train)
    predicted = np.asarray(pipeline.predict(x_test), dtype=np.float64)
    mae = _metric_decimal(mean_absolute_error(y_test, predicted))
    rmse = _metric_decimal(root_mean_squared_error(y_test, predicted))
    directional_accuracy = _metric_decimal(
        float(np.mean(np.sign(predicted) == np.sign(y_test)))
    )

    return (
        SplitEvaluation(
            sequence=split.sequence,
            train_start=split.train_start,
            train_end=split.train_end,
            test_start=split.test_start,
            test_end=split.test_end,
            train_observation_count=len(train),
            test_observation_count=len(test),
            status="evaluated",
            exclusion_reason=None,
            latest_train_label_available_at=(
                latest_train_label_available_at
            ),
            mae=mae,
            rmse=rmse,
            directional_accuracy=directional_accuracy,
            prediction_hash=_prediction_hash(predicted),
        ),
        y_test.tolist(),
        predicted.tolist(),
    )


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
    if not np.all(np.isfinite(features)) or not np.all(
        np.isfinite(targets)
    ):
        raise BaselineExperimentError(
            "Model-ready arrays contain non-finite values."
        )
    return features, targets


def _new_estimator(
    model_family: ModelFamily,
) -> LinearRegression | Ridge | RandomForestRegressor | XGBRegressor:
    if model_family == "linear_regression":
        return LinearRegression(fit_intercept=True, n_jobs=1)
    if model_family == "ridge_regression":
        return Ridge(
            alpha=RIDGE_ALPHA,
            fit_intercept=True,
            solver="svd",
        )
    if model_family == "random_forest_regression":
        return RandomForestRegressor(
            n_estimators=100,
            criterion="squared_error",
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            min_weight_fraction_leaf=0.0,
            max_features=1.0,
            max_leaf_nodes=None,
            min_impurity_decrease=0.0,
            bootstrap=True,
            oob_score=False,
            n_jobs=1,
            random_state=RANDOM_FOREST_RANDOM_STATE,
            verbose=0,
            warm_start=False,
            ccp_alpha=0.0,
            max_samples=None,
            monotonic_cst=None,
        )
    constructor_parameters = dict(XGBOOST_MODEL_PARAMETERS)
    constructor_parameters["missing"] = np.nan
    estimator = XGBRegressor(**constructor_parameters)
    effective_parameters = estimator.get_params(deep=False)
    effective_parameters["missing"] = "NaN"
    if effective_parameters != XGBOOST_MODEL_PARAMETERS:
        raise BaselineExperimentError(
            "XGBoost effective parameters differ from the immutable "
            "experiment configuration."
        )
    return estimator


def _new_pipeline(model_family: ModelFamily) -> Pipeline:
    if model_family in (
        "random_forest_regression",
        "xgboost_regression",
    ):
        return Pipeline(
            steps=(("regressor", _new_estimator(model_family)),)
        )
    return Pipeline(
        steps=(
            (
                "scaler",
                StandardScaler(with_mean=True, with_std=True),
            ),
            ("regressor", _new_estimator(model_family)),
        )
    )


def _model_parameters(
    model_family: ModelFamily,
) -> dict[str, object]:
    if model_family == "linear_regression":
        return {
            "fit_intercept": True,
            "n_jobs": 1,
        }
    if model_family == "ridge_regression":
        return {
            "alpha": format(Decimal(str(RIDGE_ALPHA)), "f"),
            "fit_intercept": True,
            "solver": "svd",
        }
    if model_family == "random_forest_regression":
        return {
            "n_estimators": 100,
            "criterion": "squared_error",
            "max_depth": None,
            "min_samples_split": 2,
            "min_samples_leaf": 1,
            "min_weight_fraction_leaf": 0.0,
            "max_features": 1.0,
            "max_leaf_nodes": None,
            "min_impurity_decrease": 0.0,
            "bootstrap": True,
            "oob_score": False,
            "n_jobs": 1,
            "random_state": RANDOM_FOREST_RANDOM_STATE,
            "verbose": 0,
            "warm_start": False,
            "ccp_alpha": 0.0,
            "max_samples": None,
            "monotonic_cst": None,
        }
    return dict(XGBOOST_MODEL_PARAMETERS)


def _preprocessing_parameters(
    model_family: ModelFamily,
) -> dict[str, object]:
    if model_family in (
        "random_forest_regression",
        "xgboost_regression",
    ):
        return {
            "name": "none",
            "reason": "tree_model_scale_invariant",
        }
    return {
        "name": "StandardScaler",
        "with_mean": True,
        "with_std": True,
        "fit_scope": "independent_training_partition_per_split",
    }


def _random_seeds(model_family: ModelFamily) -> tuple[int, ...]:
    if model_family == "random_forest_regression":
        return (RANDOM_FOREST_RANDOM_STATE,)
    if model_family == "xgboost_regression":
        return (XGBOOST_RANDOM_STATE,)
    return ()


def _metric_decimal(value: float) -> Decimal:
    if not math.isfinite(value):
        raise BaselineExperimentError(
            "Baseline evaluation produced a non-finite metric."
        )
    with localcontext() as context:
        context.prec = 50
        return Decimal(str(value)).quantize(
            METRIC_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        )


def _configuration_hash(
    dataset: ModelReadyDataset,
    model_family: ModelFamily,
    model_parameters: dict[str, object],
    preprocessing_parameters: dict[str, object],
    evaluation_policy_parameters: dict[str, object],
    random_seeds: tuple[int, ...],
) -> str:
    return _sha256_json(
        {
            "feature_names": dataset.feature_names,
            "model_dataset_hash": dataset.model_dataset_hash,
            "model_family": model_family,
            "model_parameters": model_parameters,
            "preprocessing_parameters": preprocessing_parameters,
            "evaluation_policy_parameters": (
                evaluation_policy_parameters
            ),
            "random_seeds": random_seeds,
            "source_dataset_hash": dataset.source_dataset_hash,
            "split_hash": dataset.validation_split_hash,
            "target_definition_hash": dataset.target_definition_hash,
            "training_pipeline_version": TRAINING_PIPELINE_VERSION,
        }
    )


def _result_hash(
    evaluations: tuple[SplitEvaluation, ...],
    aggregate_mae: Decimal,
    aggregate_rmse: Decimal,
    aggregate_directional_accuracy: Decimal,
) -> str:
    return _sha256_json(
        {
            "aggregate": {
                "directional_accuracy": format(
                    aggregate_directional_accuracy,
                    "f",
                ),
                "mae": format(aggregate_mae, "f"),
                "rmse": format(aggregate_rmse, "f"),
            },
            "splits": [
                {
                    "directional_accuracy": (
                        format(result.directional_accuracy, "f")
                        if result.directional_accuracy is not None
                        else None
                    ),
                    "mae": (
                        format(result.mae, "f")
                        if result.mae is not None
                        else None
                    ),
                    "prediction_hash": result.prediction_hash,
                    "rmse": (
                        format(result.rmse, "f")
                        if result.rmse is not None
                        else None
                    ),
                    "sequence": result.sequence,
                    "status": result.status,
                    "test_observation_count": (
                        result.test_observation_count
                    ),
                    "train_observation_count": (
                        result.train_observation_count
                    ),
                }
                for result in evaluations
            ],
        }
    )


def _prediction_hash(predicted: np.ndarray) -> str:
    digest = sha256()
    for value in predicted:
        digest.update((float(value).hex() + "\n").encode())
    return digest.hexdigest()


def _training_code_hash() -> str:
    digest = sha256()
    paths = (
        Path(__file__),
        Path(__file__).with_name("dataset.py"),
    )
    for path in sorted(paths):
        digest.update((path.name + "\n").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
