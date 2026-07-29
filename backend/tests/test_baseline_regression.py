"""Deterministic chronological baseline regression tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from uuid import UUID

from app.research.baseline_regression import (
    EVALUATION_POLICY_VERSION,
    MINIMUM_TRAINING_OBSERVATIONS,
    RANDOM_FOREST_RANDOM_STATE,
    RIDGE_ALPHA,
    XGBOOST_MODEL_PARAMETERS,
    XGBOOST_RANDOM_STATE,
    BaselineExperimentError,
    run_baseline_evaluation,
)
from app.research.dataset import (
    ModelObservation,
    ModelReadyDataset,
    ResearchSplit,
)


class BaselineRegressionTests(unittest.TestCase):
    def test_linear_regression_enforces_minimum_training_policy(self) -> None:
        dataset = _dataset()

        first = run_baseline_evaluation(dataset, "linear_regression")
        second = run_baseline_evaluation(dataset, "linear_regression")

        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(
            first.experiment_configuration_hash,
            second.experiment_configuration_hash,
        )
        self.assertEqual(first.evaluated_split_count, 1)
        self.assertEqual(first.skipped_split_count, 2)
        self.assertEqual(first.evaluated_observation_count, 5)
        self.assertEqual(first.split_evaluations[0].status, "skipped")
        self.assertEqual(
            first.split_evaluations[0].exclusion_reason,
            (
                "minimum_training_observations_not_met:"
                f"required={MINIMUM_TRAINING_OBSERVATIONS},observed=0"
            ),
        )
        self.assertEqual(first.split_evaluations[1].status, "skipped")
        self.assertEqual(
            first.split_evaluations[1].train_observation_count,
            99,
        )
        self.assertEqual(
            first.split_evaluations[1].exclusion_reason,
            (
                "minimum_training_observations_not_met:"
                f"required={MINIMUM_TRAINING_OBSERVATIONS},observed=99"
            ),
        )
        self.assertEqual(
            first.evaluation_policy_parameters[
                "minimum_training_observations"
            ],
            MINIMUM_TRAINING_OBSERVATIONS,
        )
        self.assertFalse(first.final_holdout_evaluated)
        self.assertTrue(first.point_in_time_validated)

    def test_ridge_uses_fixed_predeclared_alpha(self) -> None:
        result = run_baseline_evaluation(
            _dataset(),
            "ridge_regression",
        )

        self.assertEqual(
            result.model_parameters["alpha"],
            format(Decimal(str(RIDGE_ALPHA)), "f"),
        )
        self.assertEqual(result.model_parameters["solver"], "svd")
        self.assertEqual(result.random_seeds, ())

    def test_random_forest_is_fixed_unscaled_and_deterministic(self) -> None:
        dataset = _dataset()

        first = run_baseline_evaluation(
            dataset,
            "random_forest_regression",
        )
        second = run_baseline_evaluation(
            dataset,
            "random_forest_regression",
        )

        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(
            first.experiment_configuration_hash,
            second.experiment_configuration_hash,
        )
        self.assertEqual(first.model_parameters["n_estimators"], 100)
        self.assertEqual(first.model_parameters["max_depth"], None)
        self.assertEqual(first.model_parameters["n_jobs"], 1)
        self.assertEqual(
            first.model_parameters["random_state"],
            RANDOM_FOREST_RANDOM_STATE,
        )
        self.assertEqual(first.random_seeds, (RANDOM_FOREST_RANDOM_STATE,))
        self.assertEqual(first.preprocessing_parameters["name"], "none")
        self.assertEqual(
            first.evaluation_policy_parameters["version"],
            EVALUATION_POLICY_VERSION,
        )

    def test_xgboost_is_fixed_unscaled_and_deterministic(self) -> None:
        dataset = _dataset()

        first = run_baseline_evaluation(
            dataset,
            "xgboost_regression",
        )
        second = run_baseline_evaluation(
            dataset,
            "xgboost_regression",
        )

        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(
            first.experiment_configuration_hash,
            second.experiment_configuration_hash,
        )
        self.assertEqual(
            first.model_parameters,
            XGBOOST_MODEL_PARAMETERS,
        )
        self.assertEqual(first.random_seeds, (XGBOOST_RANDOM_STATE,))
        self.assertEqual(first.preprocessing_parameters["name"], "none")
        self.assertEqual(
            first.evaluation_policy_parameters["version"],
            EVALUATION_POLICY_VERSION,
        )
        self.assertEqual(first.software_versions["xgboost"], "3.2.0")

    def test_label_overlap_with_test_is_rejected(self) -> None:
        dataset = _dataset()
        observations = tuple(
            replace(
                row,
                label_available_at=(
                    dataset.validation_splits[2].test_start
                    if index == 99
                    else row.label_available_at
                ),
            )
            for index, row in enumerate(dataset.development_observations)
        )

        with self.assertRaises(BaselineExperimentError):
            run_baseline_evaluation(
                replace(dataset, development_observations=observations),
                "linear_regression",
            )

    def test_final_holdout_observation_is_rejected(self) -> None:
        dataset = _dataset()
        holdout_row = replace(
            dataset.development_observations[-1],
            prediction_timestamp=dataset.final_holdout_start,
        )

        with self.assertRaises(BaselineExperimentError):
            run_baseline_evaluation(
                replace(
                    dataset,
                    development_observations=(
                        dataset.development_observations + (holdout_row,)
                    ),
                ),
                "linear_regression",
            )


def _dataset() -> ModelReadyDataset:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observations = tuple(
        ModelObservation(
            prediction_timestamp=start + timedelta(days=index),
            label_available_at=start + timedelta(days=index + 5),
            feature_values=(
                Decimal(index + 1),
                Decimal((index + 1) ** 2),
            ),
            target_value=Decimal(index - 55) / Decimal("1000"),
        )
        for index in range(110)
    )
    splits = (
        ResearchSplit(
            sequence=1,
            train_start=start - timedelta(days=20),
            train_end=start - timedelta(days=10),
            purge_start=start - timedelta(days=9),
            purge_end=start - timedelta(days=1),
            test_start=start,
            test_end=start + timedelta(days=4),
        ),
        ResearchSplit(
            sequence=2,
            train_start=start,
            train_end=start + timedelta(days=98),
            purge_start=start + timedelta(days=99),
            purge_end=start + timedelta(days=103),
            test_start=start + timedelta(days=104),
            test_end=start + timedelta(days=108),
        ),
        ResearchSplit(
            sequence=3,
            train_start=start,
            train_end=start + timedelta(days=99),
            purge_start=start + timedelta(days=100),
            purge_end=start + timedelta(days=104),
            test_start=start + timedelta(days=105),
            test_end=start + timedelta(days=109),
        ),
    )
    return ModelReadyDataset(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        source_ingestion_batch_id=UUID(int=1),
        source_feature_run_id=UUID(int=2),
        source_target_run_id=UUID(int=3),
        validation_run_id=UUID(int=4),
        source_dataset_hash="a" * 64,
        model_dataset_hash="b" * 64,
        feature_pipeline_version="1.1.0",
        target_name="forward_log_return",
        target_version="1.0.0",
        target_definition_hash="c" * 64,
        validation_split_hash="d" * 64,
        feature_names=("feature_a", "feature_b"),
        source_observation_count=115,
        total_eligible_observation_count=110,
        development_eligible_observation_count=110,
        holdout_eligible_observation_count=0,
        excluded_feature_warmup_count=3,
        excluded_missing_target_count=2,
        development_range_start=start,
        development_range_end=start + timedelta(days=109),
        final_holdout_start=start + timedelta(days=110),
        final_holdout_end=start + timedelta(days=114),
        development_observations=observations,
        validation_splits=splits,
        point_in_time_validated=True,
    )


if __name__ == "__main__":
    unittest.main()
