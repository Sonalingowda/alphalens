"""Deterministic out-of-sample explainability for approved tree baselines."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
from typing import Any, Literal
from uuid import UUID

import numpy as np
import shap
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from xgboost import XGBRegressor

from app.research.dataset import ModelObservation, ModelReadyDataset


ExplainableModelFamily = Literal[
    "random_forest_regression",
    "xgboost_regression",
]

EXPLAINABILITY_REPORT_VERSION = "1.0.0"
EVALUATION_POLICY_VERSION = "1.1.0"
MINIMUM_TRAINING_OBSERVATIONS = 100
PERMUTATION_REPEATS = 10
PERMUTATION_RANDOM_STATE = 42
PERMUTATION_SCORING = "neg_mean_absolute_error"
VALUE_QUANTUM = Decimal("0.000000000000000001")


class ExplainabilityError(ValueError):
    """Raised when approved experiment evidence cannot be reproduced."""


@dataclass(frozen=True, slots=True)
class SourceSplitEvidence:
    sequence: int
    status: str
    prediction_hash: str | None


@dataclass(frozen=True, slots=True)
class ExplainabilitySource:
    experiment_id: UUID
    model_family: ExplainableModelFamily
    model_parameters: dict[str, Any]
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
    split_evidence: tuple[SourceSplitEvidence, ...]


@dataclass(frozen=True, slots=True)
class BuiltExplainabilityArtifact:
    model_family: ExplainableModelFamily
    configuration: dict[str, Any]
    configuration_hash: str
    payload: dict[str, Any]
    result_hash: str
    prediction_hashes_verified: int


def build_explainability_artifact(
    dataset: ModelReadyDataset,
    source: ExplainabilitySource,
) -> BuiltExplainabilityArtifact:
    """Refit approved splits and explain only chronological test rows."""
    _validate_source(dataset, source)
    feature_count = len(dataset.feature_names)
    evidence_by_sequence = {
        evidence.sequence: evidence for evidence in source.split_evidence
    }
    if set(evidence_by_sequence) != {
        split.sequence for split in dataset.validation_splits
    }:
        raise ExplainabilityError(
            "Source experiment split evidence is incomplete."
        )

    impurity_values: list[tuple[np.ndarray, int]] = []
    permutation_sum = np.zeros(feature_count, dtype=np.float64)
    permutation_square_sum = np.zeros(feature_count, dtype=np.float64)
    permutation_weight = 0
    shap_absolute_sum = np.zeros(feature_count, dtype=np.float64)
    explained_observation_count = 0
    prediction_hashes_verified = 0

    for split in dataset.validation_splits:
        train, test = _split_observations(
            dataset.development_observations,
            split.train_start,
            split.train_end,
            split.test_start,
            split.test_end,
        )
        evidence = evidence_by_sequence[split.sequence]
        if len(train) < MINIMUM_TRAINING_OBSERVATIONS or not test:
            if evidence.status != "skipped":
                raise ExplainabilityError(
                    f"Split {split.sequence} skip status does not match."
                )
            continue
        if evidence.status != "evaluated" or evidence.prediction_hash is None:
            raise ExplainabilityError(
                f"Split {split.sequence} evaluation evidence is invalid."
            )

        x_train, y_train = _arrays(train)
        x_test, y_test = _arrays(test)
        estimator = _new_estimator(source)
        estimator.fit(x_train, y_train)
        predicted = np.asarray(estimator.predict(x_test), dtype=np.float64)
        if _prediction_hash(predicted) != evidence.prediction_hash:
            raise ExplainabilityError(
                f"Split {split.sequence} predictions do not reproduce "
                "the approved experiment."
            )
        prediction_hashes_verified += 1

        if source.model_family == "random_forest_regression":
            impurity_values.append(
                (
                    np.asarray(
                        estimator.feature_importances_,
                        dtype=np.float64,
                    ),
                    len(test),
                )
            )

        permutation = permutation_importance(
            estimator,
            x_test,
            y_test,
            scoring=PERMUTATION_SCORING,
            n_repeats=PERMUTATION_REPEATS,
            random_state=PERMUTATION_RANDOM_STATE,
            n_jobs=1,
        )
        permutation_matrix = np.asarray(
            permutation.importances,
            dtype=np.float64,
        )
        permutation_sum += (
            np.sum(permutation_matrix, axis=1) * len(test)
        )
        permutation_square_sum += (
            np.sum(np.square(permutation_matrix), axis=1) * len(test)
        )
        permutation_weight += PERMUTATION_REPEATS * len(test)

        explainer = shap.TreeExplainer(
            estimator,
            feature_perturbation="tree_path_dependent",
            model_output="raw",
        )
        shap_values = np.asarray(
            explainer.shap_values(
                x_test,
                check_additivity=True,
            ),
            dtype=np.float64,
        )
        if shap_values.shape != (len(test), feature_count):
            raise ExplainabilityError(
                f"Split {split.sequence} returned an invalid SHAP shape."
            )
        shap_absolute_sum += np.sum(np.abs(shap_values), axis=0)
        explained_observation_count += len(test)

    if (
        prediction_hashes_verified != source.evaluated_split_count
        or explained_observation_count != source.evaluated_observation_count
        or permutation_weight == 0
    ):
        raise ExplainabilityError(
            "Explainability coverage does not match the source experiment."
        )

    permutation_mean = permutation_sum / permutation_weight
    permutation_variance = np.maximum(
        permutation_square_sum / permutation_weight
        - np.square(permutation_mean),
        0.0,
    )
    shap_mean_absolute = (
        shap_absolute_sum / explained_observation_count
    )
    methods: dict[str, Any] = {
        "permutation_importance": {
            "value_definition": "mean_increase_in_mae",
            "ranking": _rank_features(
                dataset.feature_names,
                permutation_mean,
                np.sqrt(permutation_variance),
                "mean_mae_increase",
                positive_normalization=True,
            ),
        },
        "tree_shap": {
            "value_definition": "mean_absolute_shap_value",
            "ranking": _rank_features(
                dataset.feature_names,
                shap_mean_absolute,
                None,
                "mean_absolute_shap_value",
                positive_normalization=False,
            ),
        },
    }
    if impurity_values:
        impurity_mean, impurity_std = _weighted_mean_std(
            impurity_values
        )
        methods["impurity_feature_importance"] = {
            "value_definition": "mean_normalized_impurity_reduction",
            "ranking": _rank_features(
                dataset.feature_names,
                impurity_mean,
                impurity_std,
                "mean_importance",
                positive_normalization=False,
            ),
        }

    configuration: dict[str, Any] = {
        "report_version": EXPLAINABILITY_REPORT_VERSION,
        "source_experiment_id": str(source.experiment_id),
        "source_experiment_configuration_hash": (
            source.experiment_configuration_hash
        ),
        "source_experiment_result_hash": source.experiment_result_hash,
        "model_family": source.model_family,
        "model_parameters": source.model_parameters,
        "evaluation_policy_version": EVALUATION_POLICY_VERSION,
        "minimum_training_observations": (
            MINIMUM_TRAINING_OBSERVATIONS
        ),
        "permutation": {
            "scoring": PERMUTATION_SCORING,
            "n_repeats": PERMUTATION_REPEATS,
            "random_state": PERMUTATION_RANDOM_STATE,
            "n_jobs": 1,
            "scope": "each_chronological_development_test_split",
        },
        "tree_shap": {
            "explainer": "TreeExplainer",
            "feature_perturbation": "tree_path_dependent",
            "model_output": "raw",
            "check_additivity": True,
            "scope": "each_chronological_development_test_split",
        },
        "aggregation": "test_observation_weighted_across_splits",
        "feature_names": dataset.feature_names,
        "model_dataset_hash": dataset.model_dataset_hash,
        "validation_run_id": str(dataset.validation_run_id),
        "split_hash": dataset.validation_split_hash,
    }
    payload: dict[str, Any] = {
        "report_version": EXPLAINABILITY_REPORT_VERSION,
        "model_family": source.model_family,
        "source_experiment_id": str(source.experiment_id),
        "provenance": {
            "model_dataset_hash": dataset.model_dataset_hash,
            "feature_pipeline_version": dataset.feature_pipeline_version,
            "target_version": dataset.target_version,
            "validation_run_id": str(dataset.validation_run_id),
            "split_hash": dataset.validation_split_hash,
            "source_experiment_configuration_hash": (
                source.experiment_configuration_hash
            ),
            "source_experiment_result_hash": (
                source.experiment_result_hash
            ),
        },
        "configuration": configuration,
        "methods": methods,
        "verification": {
            "evaluated_split_count": source.evaluated_split_count,
            "evaluated_observation_count": (
                source.evaluated_observation_count
            ),
            "prediction_hashes_verified": (
                prediction_hashes_verified
            ),
            "point_in_time_validated": True,
            "final_holdout_evaluated": False,
            "causal_interpretation_performed": False,
            "feature_selection_performed": False,
        },
    }
    return BuiltExplainabilityArtifact(
        model_family=source.model_family,
        configuration=configuration,
        configuration_hash=_sha256_json(configuration),
        payload=payload,
        result_hash=_sha256_json(payload),
        prediction_hashes_verified=prediction_hashes_verified,
    )


def _validate_source(
    dataset: ModelReadyDataset,
    source: ExplainabilitySource,
) -> None:
    if source.model_family not in (
        "random_forest_regression",
        "xgboost_regression",
    ):
        raise ExplainabilityError("Unsupported explainability model family.")
    checks = (
        source.model_dataset_hash == dataset.model_dataset_hash,
        source.feature_pipeline_version == dataset.feature_pipeline_version,
        source.target_version == dataset.target_version,
        source.validation_run_id == dataset.validation_run_id,
        source.split_hash == dataset.validation_split_hash,
        dataset.point_in_time_validated,
    )
    if not all(checks):
        raise ExplainabilityError(
            "Source experiment provenance does not match the dataset."
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


def _new_estimator(
    source: ExplainabilitySource,
) -> RandomForestRegressor | XGBRegressor:
    parameters = dict(source.model_parameters)
    if source.model_family == "random_forest_regression":
        return RandomForestRegressor(**parameters)
    if parameters.get("missing") == "NaN":
        parameters["missing"] = np.nan
    return XGBRegressor(**parameters)


def _weighted_mean_std(
    values: list[tuple[np.ndarray, int]],
) -> tuple[np.ndarray, np.ndarray]:
    total_weight = sum(weight for _, weight in values)
    mean = sum(value * weight for value, weight in values) / total_weight
    variance = (
        sum(
            np.square(value - mean) * weight
            for value, weight in values
        )
        / total_weight
    )
    return mean, np.sqrt(np.maximum(variance, 0.0))


def _rank_features(
    names: tuple[str, ...],
    values: np.ndarray,
    standard_deviations: np.ndarray | None,
    value_name: str,
    *,
    positive_normalization: bool,
) -> list[dict[str, Any]]:
    if positive_normalization:
        normalization_values = np.maximum(values, 0.0)
    else:
        normalization_values = values
    total = float(np.sum(normalization_values))
    normalized = (
        normalization_values / total
        if total > 0
        else np.zeros_like(normalization_values)
    )
    order = sorted(
        range(len(names)),
        key=lambda index: (-float(values[index]), names[index]),
    )
    return [
        {
            "rank": rank,
            "feature_name": names[index],
            value_name: _value_string(values[index]),
            "standard_deviation": (
                _value_string(standard_deviations[index])
                if standard_deviations is not None
                else None
            ),
            "normalized_importance": _value_string(normalized[index]),
        }
        for rank, index in enumerate(order, start=1)
    ]


def _value_string(value: float) -> str:
    with localcontext() as context:
        context.prec = 50
        return format(
            Decimal(str(float(value))).quantize(
                VALUE_QUANTUM,
                rounding=ROUND_HALF_EVEN,
            ),
            "f",
        )


def _prediction_hash(predicted: np.ndarray) -> str:
    digest = sha256()
    for value in predicted:
        digest.update((float(value).hex() + "\n").encode())
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
