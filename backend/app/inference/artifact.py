"""Immutable Ridge inference artifact loading and verification."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
import math
from typing import Any, Mapping

import numpy as np


INFERENCE_ARTIFACT_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class InferencePrediction:
    value: float
    float_hex: str


@dataclass(frozen=True, slots=True)
class PackagedRidgeInference:
    """Fit-free Ridge inference using immutable numeric state."""

    feature_names: tuple[str, ...]
    scaler_means: np.ndarray
    scaler_scales: np.ndarray
    coefficients: np.ndarray
    intercept: float
    artifact_sha256: str
    state_sha256: str

    def predict(
        self,
        feature_values: tuple[Decimal | float, ...],
    ) -> InferencePrediction:
        return self.predict_batch((feature_values,))[0]

    def predict_mapping(
        self,
        feature_values: Mapping[str, Decimal | float],
    ) -> InferencePrediction:
        if set(feature_values) != set(self.feature_names):
            raise ValueError("Feature mapping does not match artifact schema.")
        return self.predict(
            tuple(feature_values[name] for name in self.feature_names)
        )

    def predict_batch(
        self,
        rows: tuple[tuple[Decimal | float, ...], ...],
    ) -> tuple[InferencePrediction, ...]:
        if not rows or any(
            len(row) != len(self.feature_names) for row in rows
        ):
            raise ValueError("Feature vectors do not match artifact schema.")
        matrix = np.asarray(
            [
                [float(value) for value in row]
                for row in rows
            ],
            dtype=np.float64,
        )
        if not np.all(np.isfinite(matrix)):
            raise ValueError("Feature vectors contain non-finite values.")
        transformed = matrix.copy()
        transformed -= self.scaler_means
        transformed /= self.scaler_scales
        predicted = np.asarray(
            transformed @ self.coefficients + self.intercept,
            dtype=np.float64,
        )
        if not np.all(np.isfinite(predicted)):
            raise ValueError("Artifact produced a non-finite prediction.")
        return tuple(
            InferencePrediction(
                value=float(value),
                float_hex=float(value).hex(),
            )
            for value in predicted
        )


def load_ridge_inference_artifact(
    payload: dict[str, Any],
    *,
    expected_artifact_sha256: str,
) -> PackagedRidgeInference:
    """Verify and load an artifact without importing a training library."""
    if hash_json(payload) != expected_artifact_sha256:
        raise ValueError("Inference artifact SHA-256 differs.")
    if (
        payload.get("artifact_version") != INFERENCE_ARTIFACT_VERSION
        or payload.get("model_family") != "ridge_regression"
    ):
        raise ValueError("Unsupported inference artifact.")
    core = payload.get("core")
    state_hash = payload.get("state_sha256")
    if (
        not isinstance(core, dict)
        or not isinstance(state_hash, str)
        or hash_json(core) != state_hash
    ):
        raise ValueError("Inference artifact state hash differs.")
    schema = core.get("ordered_feature_schema")
    state = core.get("numeric_state")
    if not isinstance(schema, list) or not isinstance(state, dict):
        raise ValueError("Inference artifact structure is incomplete.")
    names = tuple(item["name"] for item in schema)
    means = _float_array(state.get("scaler_means_float_hex"))
    scales = _float_array(state.get("scaler_scales_float_hex"))
    coefficients = _float_array(
        state.get("ridge_coefficients_float_hex")
    )
    intercept_hex = state.get("ridge_intercept_float_hex")
    if not isinstance(intercept_hex, str):
        raise ValueError("Ridge intercept is absent.")
    intercept = float.fromhex(intercept_hex)
    if (
        not names
        or len(set(names)) != len(names)
        or len(means) != len(names)
        or len(scales) != len(names)
        or len(coefficients) != len(names)
        or np.any(scales <= 0)
        or not math.isfinite(intercept)
    ):
        raise ValueError("Inference artifact dimensions are invalid.")
    for array in (means, scales, coefficients):
        array.setflags(write=False)
    return PackagedRidgeInference(
        feature_names=names,
        scaler_means=means,
        scaler_scales=scales,
        coefficients=coefficients,
        intercept=intercept,
        artifact_sha256=expected_artifact_sha256,
        state_sha256=state_hash,
    )


def build_artifact_envelope(
    *,
    core: dict[str, Any],
    created_at_iso: str,
) -> tuple[dict[str, Any], str]:
    state_hash = hash_json(core)
    payload = {
        "artifact_version": INFERENCE_ARTIFACT_VERSION,
        "model_family": "ridge_regression",
        "created_at": created_at_iso,
        "state_sha256": state_hash,
        "core": core,
    }
    return payload, hash_json(payload)


def hash_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _float_array(value: object) -> np.ndarray:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) for item in value)
    ):
        raise ValueError("Inference numeric state is incomplete.")
    array = np.asarray(
        [float.fromhex(item) for item in value],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(array)):
        raise ValueError("Inference numeric state is non-finite.")
    return array

