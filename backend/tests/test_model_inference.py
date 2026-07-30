"""Tests for immutable fit-free Ridge inference artifacts."""

from copy import deepcopy
from decimal import Decimal
import inspect
import unittest
from uuid import UUID

from app.inference import artifact as inference_artifact_module
from app.inference.artifact import (
    build_artifact_envelope,
    load_ridge_inference_artifact,
)
from app.model_packaging.ridge import (
    FittedRidgeState,
    build_ridge_artifact_core,
)


class ModelInferenceArtifactTests(unittest.TestCase):
    def test_artifact_loads_and_predicts_expected_value(self) -> None:
        payload, artifact_hash = _artifact()

        model = load_ridge_inference_artifact(
            payload,
            expected_artifact_sha256=artifact_hash,
        )
        prediction = model.predict(
            (Decimal("3"), Decimal("6"))
        )

        self.assertEqual(prediction.value, -0.25)
        self.assertEqual(prediction.float_hex, (-0.25).hex())
        self.assertEqual(model.feature_names, ("feature_a", "feature_b"))

    def test_mapping_uses_artifact_feature_order(self) -> None:
        payload, artifact_hash = _artifact()
        model = load_ridge_inference_artifact(
            payload,
            expected_artifact_sha256=artifact_hash,
        )

        prediction = model.predict_mapping(
            {
                "feature_b": Decimal("6"),
                "feature_a": Decimal("3"),
            }
        )

        self.assertEqual(prediction.float_hex, (-0.25).hex())

    def test_artifact_and_state_hash_tampering_is_rejected(self) -> None:
        payload, artifact_hash = _artifact()
        tampered = deepcopy(payload)
        tampered["core"]["numeric_state"][
            "ridge_intercept_float_hex"
        ] = (1.0).hex()

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            load_ridge_inference_artifact(
                tampered,
                expected_artifact_sha256=artifact_hash,
            )

    def test_prediction_and_packaging_are_exactly_repeatable(self) -> None:
        first_payload, first_hash = _artifact()
        second_payload, second_hash = _artifact()
        first = load_ridge_inference_artifact(
            first_payload,
            expected_artifact_sha256=first_hash,
        )
        second = load_ridge_inference_artifact(
            second_payload,
            expected_artifact_sha256=second_hash,
        )
        features = ((Decimal("3"), Decimal("6")),) * 2

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_hash, second_hash)
        self.assertEqual(
            first.predict_batch(features),
            second.predict_batch(features),
        )

    def test_inference_has_no_training_api_or_dependency(self) -> None:
        payload, artifact_hash = _artifact()
        model = load_ridge_inference_artifact(
            payload,
            expected_artifact_sha256=artifact_hash,
        )
        source = inspect.getsource(inference_artifact_module)

        self.assertFalse(hasattr(model, "fit"))
        self.assertNotIn(".fit(", source)
        self.assertNotIn("sklearn", source)

    def test_invalid_feature_schema_is_rejected(self) -> None:
        payload, artifact_hash = _artifact()
        model = load_ridge_inference_artifact(
            payload,
            expected_artifact_sha256=artifact_hash,
        )

        with self.assertRaisesRegex(ValueError, "schema"):
            model.predict((Decimal("1"),))
        with self.assertRaisesRegex(ValueError, "schema"):
            model.predict_mapping({"feature_a": Decimal("1")})

    def test_numeric_state_is_read_only_after_loading(self) -> None:
        payload, artifact_hash = _artifact()
        model = load_ridge_inference_artifact(
            payload,
            expected_artifact_sha256=artifact_hash,
        )

        self.assertFalse(model.coefficients.flags.writeable)
        with self.assertRaises(ValueError):
            model.coefficients[0] = 10.0


def _artifact() -> tuple[dict, str]:
    core = build_ridge_artifact_core(
        state=FittedRidgeState(
            scaler_means=(1.0, 2.0),
            scaler_scales=(2.0, 4.0),
            coefficients=(0.5, -1.0),
            intercept=0.25,
        ),
        configuration_hash="a" * 64,
        feature_names=("feature_a", "feature_b"),
        feature_pipeline_version="1.1.0",
        model_dataset_hash="b" * 64,
        training_dataset_hash="c" * 64,
        software_versions={"numpy": "test"},
        provenance={"selected_experiment_id": str(UUID(int=1))},
    )
    return build_artifact_envelope(
        core=core,
        created_at_iso="2026-07-30T00:00:00+00:00",
    )
