"""Authorized one-time replay for selected Ridge artifact packaging."""

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.research.dataset import ModelObservation


@dataclass(frozen=True, slots=True)
class FittedRidgeState:
    scaler_means: tuple[float, ...]
    scaler_scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float


def replay_selected_ridge_for_packaging(
    *,
    training_observations: tuple[ModelObservation, ...],
    model_parameters: dict[str, Any],
) -> FittedRidgeState:
    """Fit exactly once under the approved packaging authorization."""
    if model_parameters != {
        "alpha": "1.0",
        "fit_intercept": True,
        "solver": "svd",
    }:
        raise ValueError("Selected Ridge parameters differ.")
    if len(training_observations) != 611:
        raise ValueError("Final packaging training window must contain 611.")
    matrix = np.asarray(
        [
            [float(value) for value in item.feature_values]
            for item in training_observations
        ],
        dtype=np.float64,
    )
    targets = np.asarray(
        [float(item.target_value) for item in training_observations],
        dtype=np.float64,
    )
    pipeline = Pipeline(
        steps=(
            (
                "scaler",
                StandardScaler(with_mean=True, with_std=True),
            ),
            (
                "regressor",
                Ridge(
                    alpha=float(model_parameters["alpha"]),
                    fit_intercept=model_parameters["fit_intercept"],
                    solver=model_parameters["solver"],
                ),
            ),
        )
    )
    pipeline.fit(matrix, targets)
    scaler = pipeline.named_steps["scaler"]
    ridge = pipeline.named_steps["regressor"]
    return FittedRidgeState(
        scaler_means=tuple(float(value) for value in scaler.mean_),
        scaler_scales=tuple(float(value) for value in scaler.scale_),
        coefficients=tuple(float(value) for value in ridge.coef_),
        intercept=float(ridge.intercept_),
    )


def build_ridge_artifact_core(
    *,
    state: FittedRidgeState,
    configuration_hash: str,
    feature_names: tuple[str, ...],
    feature_pipeline_version: str,
    model_dataset_hash: str,
    training_dataset_hash: str,
    software_versions: dict[str, str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if not feature_names or len(feature_names) != len(state.coefficients):
        raise ValueError("Feature schema and fitted state differ.")
    return {
        "configuration_hash": configuration_hash,
        "ordered_feature_schema": [
            {
                "position": index,
                "name": name,
                "dtype": "float64",
                "source_feature_pipeline_version": (
                    feature_pipeline_version
                ),
            }
            for index, name in enumerate(feature_names)
        ],
        "feature_metadata": {
            "count": len(feature_names),
            "ordering": "model_dataset_feature_order",
            "point_in_time_features": True,
        },
        "numeric_state": {
            "ridge_coefficients_float_hex": [
                value.hex() for value in state.coefficients
            ],
            "ridge_intercept_float_hex": state.intercept.hex(),
            "scaler_means_float_hex": [
                value.hex() for value in state.scaler_means
            ],
            "scaler_scales_float_hex": [
                value.hex() for value in state.scaler_scales
            ],
            "storage_encoding": "ieee754_binary64_hex",
        },
        "dataset_hash": model_dataset_hash,
        "training_hash": training_dataset_hash,
        "software_versions": dict(sorted(software_versions.items())),
        "provenance": provenance,
    }

