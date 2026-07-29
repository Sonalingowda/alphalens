"""Deterministic chronological explainability tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import unittest
from uuid import UUID

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from app.research.dataset import (
    ModelObservation,
    ModelReadyDataset,
    ResearchSplit,
)
from app.research.explainability import (
    ExplainabilityError,
    ExplainabilitySource,
    SourceSplitEvidence,
    build_explainability_artifact,
)


class ExplainabilityTests(unittest.TestCase):
    def test_random_forest_artifact_is_deterministic(self) -> None:
        dataset = _dataset()
        source = _source(dataset, "random_forest_regression")

        first = build_explainability_artifact(dataset, source)
        second = build_explainability_artifact(dataset, source)

        self.assertEqual(first.configuration_hash, second.configuration_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.payload, second.payload)
        self.assertIn(
            "impurity_feature_importance",
            first.payload["methods"],
        )
        self.assertFalse(
            first.payload["verification"]["final_holdout_evaluated"]
        )
        self.assertFalse(
            first.payload["verification"]["feature_selection_performed"]
        )

    def test_xgboost_artifact_is_deterministic_without_impurity_method(
        self,
    ) -> None:
        dataset = _dataset()
        source = _source(dataset, "xgboost_regression")

        first = build_explainability_artifact(dataset, source)
        second = build_explainability_artifact(dataset, source)

        self.assertEqual(first.result_hash, second.result_hash)
        self.assertNotIn(
            "impurity_feature_importance",
            first.payload["methods"],
        )
        self.assertEqual(first.prediction_hashes_verified, 1)

    def test_prediction_mismatch_is_rejected(self) -> None:
        dataset = _dataset()
        source = _source(dataset, "random_forest_regression")
        invalid = replace(
            source,
            split_evidence=(
                SourceSplitEvidence(
                    sequence=1,
                    status="evaluated",
                    prediction_hash="0" * 64,
                ),
            ),
        )

        with self.assertRaises(ExplainabilityError):
            build_explainability_artifact(dataset, invalid)


def _dataset() -> ModelReadyDataset:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    observations = tuple(
        ModelObservation(
            prediction_timestamp=start + timedelta(days=index),
            label_available_at=start + timedelta(days=index + 5),
            feature_values=(
                Decimal(index + 1),
                Decimal((index + 1) ** 2),
                Decimal(index % 7),
            ),
            target_value=Decimal((index % 11) - 5) / Decimal("100"),
        )
        for index in range(110)
    )
    split = ResearchSplit(
        sequence=1,
        train_start=start,
        train_end=start + timedelta(days=99),
        purge_start=start + timedelta(days=100),
        purge_end=start + timedelta(days=104),
        test_start=start + timedelta(days=105),
        test_end=start + timedelta(days=109),
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
        feature_names=("feature_a", "feature_b", "feature_c"),
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
        validation_splits=(split,),
        point_in_time_validated=True,
    )


def _source(
    dataset: ModelReadyDataset,
    family: str,
) -> ExplainabilitySource:
    train = dataset.development_observations[:100]
    test = dataset.development_observations[105:110]
    x_train = np.asarray(
        [[float(value) for value in row.feature_values] for row in train]
    )
    y_train = np.asarray([float(row.target_value) for row in train])
    x_test = np.asarray(
        [[float(value) for value in row.feature_values] for row in test]
    )
    if family == "random_forest_regression":
        parameters = {
            "n_estimators": 10,
            "random_state": 42,
            "n_jobs": 1,
        }
        estimator = RandomForestRegressor(**parameters)
    else:
        parameters = {
            "n_estimators": 10,
            "objective": "reg:squarederror",
            "random_state": 42,
            "n_jobs": 1,
            "tree_method": "hist",
            "missing": "NaN",
        }
        constructor = dict(parameters)
        constructor["missing"] = np.nan
        estimator = XGBRegressor(**constructor)
    estimator.fit(x_train, y_train)
    prediction_hash = _prediction_hash(estimator.predict(x_test))
    return ExplainabilitySource(
        experiment_id=UUID(int=10 if family.startswith("random") else 11),
        model_family=family,  # type: ignore[arg-type]
        model_parameters=parameters,
        training_pipeline_version="1.0.0",
        experiment_configuration_hash="e" * 64,
        experiment_result_hash="f" * 64,
        model_dataset_hash=dataset.model_dataset_hash,
        feature_pipeline_version=dataset.feature_pipeline_version,
        target_version=dataset.target_version,
        validation_run_id=dataset.validation_run_id,
        split_hash=dataset.validation_split_hash,
        evaluated_split_count=1,
        evaluated_observation_count=5,
        split_evidence=(
            SourceSplitEvidence(
                sequence=1,
                status="evaluated",
                prediction_hash=prediction_hash,
            ),
        ),
    )


def _prediction_hash(predicted: np.ndarray) -> str:
    digest = sha256()
    for value in np.asarray(predicted, dtype=np.float64):
        digest.update((float(value).hex() + "\n").encode())
    return digest.hexdigest()


if __name__ == "__main__":
    unittest.main()
