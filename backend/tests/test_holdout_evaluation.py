"""Tests for deterministic one-time protected holdout evaluation."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.research.dataset import (
    MODEL_FEATURE_NAMES,
    ModelObservation,
    ModelReadyDataset,
)
from app.research.holdout_evaluation import (
    DevelopmentResidualEvidence,
    HoldoutEvaluationError,
    SelectedRidgeSpecification,
    SourceArtifactReference,
    build_holdout_evaluation_report,
    evaluate_official_holdout,
)


class HoldoutEvaluationTests(unittest.TestCase):
    def test_evaluation_and_report_are_deterministic(self) -> None:
        inputs = _inputs()

        first_evaluation = evaluate_official_holdout(**inputs)
        second_evaluation = evaluate_official_holdout(**inputs)
        first_report = build_holdout_evaluation_report(
            dataset=inputs["dataset"],
            selected=inputs["selected"],
            development_residuals=inputs["development_residuals"],
            evaluated=first_evaluation,
        )
        second_report = build_holdout_evaluation_report(
            dataset=inputs["dataset"],
            selected=inputs["selected"],
            development_residuals=inputs["development_residuals"],
            evaluated=second_evaluation,
        )

        self.assertEqual(
            first_evaluation.holdout_prediction_hash,
            second_evaluation.holdout_prediction_hash,
        )
        self.assertEqual(
            first_evaluation.prediction_evidence_set_hash,
            second_evaluation.prediction_evidence_set_hash,
        )
        self.assertEqual(
            first_report.configuration_hash,
            second_report.configuration_hash,
        )
        self.assertEqual(first_report.result_hash, second_report.result_hash)
        self.assertEqual(first_evaluation.training_observation_count, 110)
        self.assertEqual(first_evaluation.purged_observation_count, 50)
        self.assertEqual(
            first_evaluation.registered_holdout_observation_count,
            10,
        )
        self.assertEqual(
            first_evaluation.eligible_holdout_observation_count,
            5,
        )
        self.assertEqual(first_evaluation.excluded_missing_target_count, 5)
        self.assertEqual(
            len(first_report.payload["holdout_predictions"]),
            5,
        )
        self.assertTrue(
            first_report.payload["verification"][
                "report_repeatability_verified"
            ]
        )

    def test_registered_ridge_parameters_are_immutable(self) -> None:
        inputs = _inputs()
        inputs["selected"] = replace(
            inputs["selected"],
            model_parameters={
                "alpha": "2.0",
                "fit_intercept": True,
                "solver": "svd",
            },
        )

        with self.assertRaisesRegex(
            HoldoutEvaluationError,
            "configuration differs",
        ):
            evaluate_official_holdout(**inputs)

    def test_every_required_source_artifact_is_mandatory(self) -> None:
        inputs = _inputs()
        inputs["source_artifacts"] = inputs["source_artifacts"][:-1]

        with self.assertRaisesRegex(
            HoldoutEvaluationError,
            "source artifacts",
        ):
            evaluate_official_holdout(**inputs)

    def test_holdout_label_must_be_strictly_forward(self) -> None:
        inputs = _inputs()
        first = inputs["holdout_observations"][0]
        inputs["holdout_observations"] = (
            replace(
                first,
                label_available_at=first.prediction_timestamp,
            ),
            *inputs["holdout_observations"][1:],
        )

        with self.assertRaisesRegex(
            HoldoutEvaluationError,
            "observations are invalid",
        ):
            evaluate_official_holdout(**inputs)

    def test_insufficient_final_training_sample_is_rejected(self) -> None:
        inputs = _inputs(development_count=149)

        with self.assertRaisesRegex(
            HoldoutEvaluationError,
            "training window",
        ):
            evaluate_official_holdout(**inputs)


def _inputs(development_count: int = 160) -> dict:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    holdout_start = start + timedelta(days=170)
    development = tuple(
        _observation(start + timedelta(days=index), index)
        for index in range(development_count)
    )
    registered = tuple(
        holdout_start + timedelta(days=index) for index in range(10)
    )
    holdout = tuple(
        _observation(timestamp, 170 + index)
        for index, timestamp in enumerate(registered[:5])
    )
    validation_id = UUID(int=4)
    dataset = ModelReadyDataset(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        source_ingestion_batch_id=UUID(int=1),
        source_feature_run_id=UUID(int=2),
        source_target_run_id=UUID(int=3),
        validation_run_id=validation_id,
        source_dataset_hash="a" * 64,
        model_dataset_hash="b" * 64,
        feature_pipeline_version="1.1.0",
        target_name="forward_log_return",
        target_version="1.0.0",
        target_definition_hash="c" * 64,
        validation_split_hash="d" * 64,
        feature_names=MODEL_FEATURE_NAMES,
        source_observation_count=720,
        total_eligible_observation_count=665,
        development_eligible_observation_count=development_count,
        holdout_eligible_observation_count=5,
        excluded_feature_warmup_count=49,
        excluded_missing_target_count=5,
        development_range_start=development[0].prediction_timestamp,
        development_range_end=development[-1].prediction_timestamp,
        final_holdout_start=registered[0],
        final_holdout_end=registered[-1],
        development_observations=development,
        validation_splits=(),
        point_in_time_validated=True,
    )
    selected = SelectedRidgeSpecification(
        experiment_id=UUID(int=5),
        model_family="ridge_regression",
        model_parameters={
            "alpha": "1.0",
            "fit_intercept": True,
            "solver": "svd",
        },
        preprocessing_parameters={
            "name": "StandardScaler",
            "with_mean": True,
            "with_std": True,
            "fit_scope": "independent_training_partition_per_split",
        },
        evaluation_policy_parameters={
            "minimum_training_observations": 100,
        },
        training_pipeline_version="1.1.0",
        experiment_configuration_hash="e" * 64,
        experiment_result_hash="f" * 64,
        model_dataset_hash=dataset.model_dataset_hash,
        feature_pipeline_version=dataset.feature_pipeline_version,
        target_version=dataset.target_version,
        validation_run_id=dataset.validation_run_id,
        split_hash=dataset.validation_split_hash,
        development_mae=Decimal("0.04"),
        development_rmse=Decimal("0.05"),
        development_directional_accuracy=Decimal("0.52"),
    )
    return {
        "dataset": dataset,
        "selected": selected,
        "development_residuals": DevelopmentResidualEvidence(
            mean_residual=Decimal("-0.001"),
            residual_variance=Decimal("0.003"),
            prediction_evidence_set_hash="1" * 64,
            verified_split_prediction_hash_count=102,
            prediction_evidence_count=510,
        ),
        "registered_holdout_timestamps": registered,
        "holdout_observations": holdout,
        "purge_gap_size": 50,
        "source_artifacts": _source_artifacts(),
    }


def _observation(timestamp: datetime, index: int) -> ModelObservation:
    base = Decimal(index + 1)
    features = tuple(
        (
            base * Decimal(feature_index + 1)
            + Decimal((index + feature_index) % 7) / Decimal("100")
        )
        for feature_index in range(len(MODEL_FEATURE_NAMES))
    )
    target = (
        Decimal("0.0002") * base
        + Decimal((index % 5) - 2) / Decimal("1000")
    )
    return ModelObservation(
        prediction_timestamp=timestamp,
        label_available_at=timestamp + timedelta(days=5),
        feature_values=features,
        target_value=target,
    )


def _source_artifacts() -> tuple[SourceArtifactReference, ...]:
    types = (
        "model_comparison_report",
        "statistical_validation_report",
        "residual_diagnostics_report",
        "market_regime_analysis_report",
        "final_model_selection_report",
        "random_forest_explainability_artifact",
        "xgboost_explainability_artifact",
    )
    return tuple(
        SourceArtifactReference(
            artifact_id=UUID(int=100 + index),
            artifact_type=artifact_type,
            configuration_hash=str(index) * 64,
            result_hash=str(index + 1) * 64,
        )
        for index, artifact_type in enumerate(types, start=1)
    )
