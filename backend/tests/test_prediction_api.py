"""Endpoint, security, and repeatability tests for prediction API v1."""

import inspect
from pathlib import Path
import unittest
from uuid import UUID

import numpy as np
from fastapi.testclient import TestClient

from app.api.application import create_prediction_app
from app.inference.artifact import PackagedRidgeInference
from app.inference.repository import LoadedProductionArtifact
from app.inference.service import ProductionPredictionService
from app.research.dataset import MODEL_FEATURE_NAMES


class PredictionAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.audits = []

        async def artifact_provider():
            return _artifact()

        async def audit_writer(audit):
            self.audits.append(audit)
            return UUID(int=len(self.audits))

        async def dashboard_provider():
            return {
                "snapshot_version": "1.0.0",
                "generated_at": "2026-07-30T00:00:00+00:00",
                "prediction": None,
                "portfolio": {"available": False},
                "provenance": {
                    "inference_artifact_id": str(UUID(int=10))
                },
            }

        self.app = create_prediction_app(
            artifact_provider=artifact_provider,
            audit_writer=audit_writer,
            dashboard_provider=dashboard_provider,
        )
        self.client = TestClient(self.app)

    def test_health_and_version_endpoints(self) -> None:
        health = self.client.get("/api/v1/health")
        alias = self.client.get("/health")
        version = self.client.get("/api/v1/version")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "healthy")
        self.assertEqual(health.json()["artifact_status"], "verified")
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(version.status_code, 200)
        self.assertEqual(version.json()["api_version"], "1.0.0")
        self.assertTrue(version.json()["read_only"])
        self.assertEqual(
            health.headers["X-AlphaLens-API-Version"],
            "1.0.0",
        )

    def test_model_endpoint_returns_exact_ordered_schema(self) -> None:
        response = self.client.get("/api/v1/model")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["feature_count"], 12)
        self.assertEqual(
            payload["ordered_feature_names"],
            list(MODEL_FEATURE_NAMES),
        )
        self.assertEqual(payload["artifact_sha256"], "a" * 64)
        self.assertEqual(len(payload["schema_hash"]), 64)
        self.assertNotIn("coefficients", payload)

    def test_prediction_is_deterministic_and_audited(self) -> None:
        body = _request()

        first = self.client.post("/api/v1/predict", json=body)
        second = self.client.post("/api/v1/predict", json=body)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_payload = first.json()
        second_payload = second.json()
        self.assertEqual(
            first_payload["predicted_forward_log_return"],
            "0.02",
        )
        self.assertEqual(
            first_payload["predicted_float_hex"],
            (0.02).hex(),
        )
        self.assertEqual(
            first_payload["prediction_hash"],
            second_payload["prediction_hash"],
        )
        self.assertEqual(
            first_payload["feature_vector_hash"],
            second_payload["feature_vector_hash"],
        )
        self.assertEqual(
            first_payload["artifact_identifier"],
            str(UUID(int=10)),
        )
        self.assertEqual(len(self.audits), 2)
        self.assertTrue(
            all(item.prediction_hash for item in self.audits)
        )
        self.assertTrue(
            all(item.outcome == "success" for item in self.audits)
        )

    def test_feature_count_order_and_name_are_rejected(self) -> None:
        count = _request()
        count["features"] = count["features"][:-1]
        order = _request()
        order["features"][0], order["features"][1] = (
            order["features"][1],
            order["features"][0],
        )
        names = _request()
        names["features"][0]["name"] = "unknown_feature"

        count_response = self.client.post(
            "/api/v1/predict",
            json=count,
        )
        order_response = self.client.post(
            "/api/v1/predict",
            json=order,
        )
        name_response = self.client.post(
            "/api/v1/predict",
            json=names,
        )

        self.assertEqual(
            count_response.json()["error"]["code"],
            "FEATURE_COUNT_MISMATCH",
        )
        self.assertEqual(
            order_response.json()["error"]["code"],
            "FEATURE_ORDER_MISMATCH",
        )
        self.assertEqual(
            name_response.json()["error"]["code"],
            "FEATURE_NAME_MISMATCH",
        )

    def test_missing_field_and_schema_hash_mismatch_are_rejected(self) -> None:
        missing = _request()
        missing.pop("schema_hash")
        mismatch = _request()
        mismatch["schema_hash"] = "0" * 64

        missing_response = self.client.post(
            "/api/v1/predict",
            json=missing,
        )
        mismatch_response = self.client.post(
            "/api/v1/predict",
            json=mismatch,
        )

        self.assertEqual(missing_response.status_code, 422)
        self.assertEqual(
            missing_response.json()["error"]["code"],
            "REQUEST_SCHEMA_INVALID",
        )
        self.assertEqual(mismatch_response.status_code, 422)
        self.assertEqual(
            mismatch_response.json()["error"]["code"],
            "SCHEMA_HASH_MISMATCH",
        )

    def test_invalid_decimal_and_extra_fields_are_rejected(self) -> None:
        invalid = _request()
        invalid["features"][0]["value"] = "NaN"
        extra = _request()
        extra["training"] = True

        invalid_response = self.client.post(
            "/api/v1/predict",
            json=invalid,
        )
        extra_response = self.client.post(
            "/api/v1/predict",
            json=extra,
        )

        self.assertEqual(
            invalid_response.json()["error"]["code"],
            "FEATURE_VALUE_INVALID",
        )
        self.assertEqual(
            extra_response.json()["error"]["code"],
            "REQUEST_SCHEMA_INVALID",
        )

    def test_request_size_limit_is_enforced(self) -> None:
        audits = []

        async def provider():
            return _artifact()

        async def writer(audit):
            audits.append(audit)
            return UUID(int=100)

        client = TestClient(
            create_prediction_app(
                maximum_request_bytes=64,
                artifact_provider=provider,
                audit_writer=writer,
            )
        )

        response = client.post(
            "/api/v1/predict",
            content=b"x" * 65,
            headers={"content-type": "application/json"},
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(
            response.json()["error"]["code"],
            "REQUEST_TOO_LARGE",
        )
        self.assertEqual(audits[0].request_size_bytes, 65)

    def test_artifact_failure_is_structured_and_audited(self) -> None:
        audits = []

        async def failed_provider():
            raise ValueError("unavailable")

        async def writer(audit):
            audits.append(audit)
            return UUID(int=200)

        client = TestClient(
            create_prediction_app(
                artifact_provider=failed_provider,
                audit_writer=writer,
            )
        )

        response = client.get("/api/v1/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "ARTIFACT_UNAVAILABLE",
        )
        self.assertEqual(audits[0].error_code, "ARTIFACT_UNAVAILABLE")

    def test_metrics_report_operational_timing_counters(self) -> None:
        self.client.get("/api/v1/version")
        self.client.post("/api/v1/predict", json=_request())

        response = self.client.get("/api/v1/metrics")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["request_count"], 2)
        self.assertEqual(payload["prediction_count"], 1)
        self.assertGreaterEqual(
            payload["maximum_latency_microseconds"],
            0,
        )

    def test_resource_endpoint_reports_process_uptime_and_usage(self) -> None:
        response = self.client.get("/api/v1/resources")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["api_version"], "1.0.0")
        self.assertGreaterEqual(payload["uptime_seconds"], 0)
        self.assertGreaterEqual(
            payload["maximum_resident_set_bytes"],
            1,
        )

    def test_cors_allows_only_configured_origin(self) -> None:
        client = TestClient(
            create_prediction_app(
                artifact_provider=self.app.state.artifact_provider,
                audit_writer=self.app.state.audit_writer,
                dashboard_provider=self.app.state.dashboard_provider,
                cors_allowed_origins=("https://dashboard.example.com",),
            )
        )

        allowed = client.options(
            "/api/v1/predict",
            headers={
                "Origin": "https://dashboard.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        denied = client.options(
            "/api/v1/predict",
            headers={
                "Origin": "https://untrusted.example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(
            allowed.headers["access-control-allow-origin"],
            "https://dashboard.example.com",
        )
        self.assertNotIn(
            "access-control-allow-origin",
            denied.headers,
        )

    def test_dashboard_endpoint_returns_read_only_projection(self) -> None:
        response = self.client.get("/api/v1/dashboard")
        alias = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(
            response.json()["snapshot_version"],
            "1.0.0",
        )
        self.assertFalse(response.json()["portfolio"]["available"])
        self.assertEqual(
            response.json()["provenance"]["inference_artifact_id"],
            str(UUID(int=10)),
        )
        self.assertEqual(
            response.headers["Cache-Control"],
            "no-store",
        )

    def test_dashboard_failure_is_structured(self) -> None:
        async def unavailable():
            raise ValueError("invalid report hash")

        client = TestClient(
            create_prediction_app(
                artifact_provider=self.app.state.artifact_provider,
                audit_writer=self.app.state.audit_writer,
                dashboard_provider=unavailable,
            )
        )

        response = client.get("/api/v1/dashboard")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "DASHBOARD_DATA_UNAVAILABLE",
        )

    def test_unknown_routes_and_methods_use_structured_errors(self) -> None:
        missing = self.client.get("/api/v1/unknown")
        method = self.client.get("/api/v1/predict")

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            missing.json()["error"]["code"],
            "ROUTE_NOT_FOUND",
        )
        self.assertEqual(method.status_code, 405)
        self.assertEqual(
            method.json()["error"]["code"],
            "METHOD_NOT_ALLOWED",
        )

    def test_api_and_shared_inference_have_no_training_surface(self) -> None:
        roots = (
            Path(inspect.getfile(create_prediction_app)).parent,
            Path(inspect.getfile(ProductionPredictionService)).parent,
        )
        files = {
            path
            for root in roots
            for path in root.glob("*.py")
            if path.name not in {"artifact.py"}
        }
        source = "\n".join(
            path.read_text() for path in sorted(files)
        )

        self.assertNotIn(".fit(", source)
        self.assertNotIn("model_packaging", source)
        self.assertNotIn("sklearn", source)


def _request() -> dict:
    service = ProductionPredictionService(_artifact())
    return {
        "api_version": "1.0.0",
        "schema_hash": service.schema_hash,
        "prediction_timestamp": "2026-07-28T00:00:00+00:00",
        "features": [
            {"name": name, "value": str(index + 1)}
            for index, name in enumerate(MODEL_FEATURE_NAMES)
        ],
    }


def _artifact() -> LoadedProductionArtifact:
    size = len(MODEL_FEATURE_NAMES)
    means = np.zeros(size, dtype=np.float64)
    scales = np.ones(size, dtype=np.float64)
    coefficients = np.zeros(size, dtype=np.float64)
    for array in (means, scales, coefficients):
        array.setflags(write=False)
    inference = PackagedRidgeInference(
        feature_names=MODEL_FEATURE_NAMES,
        scaler_means=means,
        scaler_scales=scales,
        coefficients=coefficients,
        intercept=0.02,
        artifact_sha256="a" * 64,
        state_sha256="b" * 64,
    )
    return LoadedProductionArtifact(
        artifact_id=UUID(int=10),
        configuration_hash="c" * 64,
        artifact_sha256="a" * 64,
        state_sha256="b" * 64,
        model_family="ridge_regression",
        feature_pipeline_version="1.1.0",
        target_version="1.0.0",
        model_dataset_hash="d" * 64,
        training_dataset_hash="e" * 64,
        selected_experiment_id=UUID(int=2),
        holdout_evaluation_report_id=UUID(int=3),
        validation_run_id=UUID(int=4),
        split_hash="f" * 64,
        inference=inference,
    )
