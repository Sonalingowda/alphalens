"""Deterministic residual diagnostics tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import unittest
from uuid import UUID

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.research.dataset import (
    ModelObservation,
    ModelReadyDataset,
    ResearchSplit,
)
from app.research.residual_diagnostics import (
    ArtifactReference,
    PredictionEvidence,
    ReplaySplitEvidence,
    ReplayedModelPredictions,
    ResidualDiagnosticsError,
    ResidualExperimentSource,
    build_residual_diagnostics_report,
    replay_approved_experiment,
)


class ResidualDiagnosticsTests(unittest.TestCase):
    def test_replay_verifies_hash_and_never_touches_holdout(self) -> None:
        dataset, source = _linear_replay_fixture()

        replay = replay_approved_experiment(dataset, source)

        self.assertEqual(replay.verified_prediction_hash_count, 1)
        self.assertEqual(len(replay.predictions), 5)
        self.assertTrue(
            all(
                item.prediction_timestamp < dataset.final_holdout_start
                for item in replay.predictions
            )
        )

    def test_prediction_hash_mismatch_aborts(self) -> None:
        dataset, source = _linear_replay_fixture()
        changed_split = replace(
            source.split_evidence[0],
            prediction_hash="0" * 64,
        )

        with self.assertRaises(ResidualDiagnosticsError):
            replay_approved_experiment(
                dataset,
                replace(source, split_evidence=(changed_split,)),
            )

    def test_report_and_svg_artifacts_are_deterministic(self) -> None:
        replays = _report_replays()
        statistical = ArtifactReference(
            artifact_id=UUID(int=100),
            artifact_type="statistical_validation_report",
            model_family=None,
            configuration_hash="a" * 64,
            result_hash="b" * 64,
        )
        explainability = (
            ArtifactReference(
                artifact_id=UUID(int=101),
                artifact_type="model_explainability_artifact",
                model_family="random_forest_regression",
                configuration_hash="c" * 64,
                result_hash="d" * 64,
            ),
            ArtifactReference(
                artifact_id=UUID(int=102),
                artifact_type="model_explainability_artifact",
                model_family="xgboost_regression",
                configuration_hash="e" * 64,
                result_hash="f" * 64,
            ),
        )

        first = build_residual_diagnostics_report(
            replays,
            statistical_report=statistical,
            explainability_artifacts=explainability,
        )
        second = build_residual_diagnostics_report(
            tuple(reversed(replays)),
            statistical_report=statistical,
            explainability_artifacts=tuple(reversed(explainability)),
        )

        self.assertEqual(first.configuration_hash, second.configuration_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(
            [plot.plot.content_hash for plot in first.plots],
            [plot.plot.content_hash for plot in second.plots],
        )
        self.assertEqual(len(first.plots), 16)
        self.assertFalse(
            first.payload["verification"]["final_holdout_evaluated"]
        )


def _linear_replay_fixture() -> tuple[
    ModelReadyDataset,
    ResidualExperimentSource,
]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    train = tuple(
        _observation(start + timedelta(days=index), index)
        for index in range(100)
    )
    test = tuple(
        _observation(start + timedelta(days=index), index)
        for index in range(105, 110)
    )
    observations = train + test
    split = ResearchSplit(
        sequence=1,
        train_start=train[0].prediction_timestamp,
        train_end=train[-1].prediction_timestamp,
        purge_start=start + timedelta(days=100),
        purge_end=start + timedelta(days=104),
        test_start=test[0].prediction_timestamp,
        test_end=test[-1].prediction_timestamp,
    )
    x_train, y_train = _arrays(train)
    x_test, y_test = _arrays(test)
    pipeline = Pipeline(
        steps=(
            (
                "scaler",
                StandardScaler(with_mean=True, with_std=True),
            ),
            (
                "regressor",
                LinearRegression(fit_intercept=True, n_jobs=1),
            ),
        )
    )
    pipeline.fit(x_train, y_train)
    predicted = np.asarray(pipeline.predict(x_test), dtype=np.float64)
    prediction_hash = _prediction_hash(predicted)
    dataset = ModelReadyDataset(
        asset_identifier="BTC",
        quote_currency="USD",
        timeframe="1d",
        source_ingestion_batch_id=UUID(int=10),
        source_feature_run_id=UUID(int=11),
        source_target_run_id=UUID(int=12),
        validation_run_id=UUID(int=13),
        source_dataset_hash="1" * 64,
        model_dataset_hash="2" * 64,
        feature_pipeline_version="1.1.0",
        target_name="forward_log_return",
        target_version="1.0.0",
        target_definition_hash="3" * 64,
        validation_split_hash="4" * 64,
        feature_names=("first", "second"),
        source_observation_count=len(observations),
        total_eligible_observation_count=len(observations),
        development_eligible_observation_count=len(observations),
        holdout_eligible_observation_count=0,
        excluded_feature_warmup_count=0,
        excluded_missing_target_count=0,
        development_range_start=observations[0].prediction_timestamp,
        development_range_end=observations[-1].prediction_timestamp,
        final_holdout_start=start + timedelta(days=110),
        final_holdout_end=start + timedelta(days=119),
        development_observations=observations,
        validation_splits=(split,),
        point_in_time_validated=True,
    )
    source = ResidualExperimentSource(
        experiment_id=UUID(int=20),
        model_family="linear_regression",
        model_parameters={"fit_intercept": True, "n_jobs": 1},
        preprocessing_parameters={
            "name": "StandardScaler",
            "with_mean": True,
            "with_std": True,
            "fit_scope": "independent_training_partition_per_split",
        },
        evaluation_policy_parameters={
            "minimum_training_observations": 100
        },
        random_seeds=(),
        training_pipeline_version="1.1.0",
        experiment_configuration_hash="5" * 64,
        experiment_result_hash="6" * 64,
        model_dataset_hash=dataset.model_dataset_hash,
        feature_pipeline_version=dataset.feature_pipeline_version,
        target_version=dataset.target_version,
        validation_run_id=dataset.validation_run_id,
        split_hash=dataset.validation_split_hash,
        evaluated_split_count=1,
        evaluated_observation_count=5,
        final_holdout_evaluated=False,
        split_evidence=(
            ReplaySplitEvidence(
                split_record_id=1,
                sequence=1,
                train_start=split.train_start,
                train_end=split.train_end,
                test_start=split.test_start,
                test_end=split.test_end,
                status="evaluated",
                train_observation_count=100,
                test_observation_count=5,
                latest_train_label_available_at=(
                    train[-1].label_available_at
                ),
                mae=_decimal(mean_absolute_error(y_test, predicted)),
                rmse=_decimal(
                    root_mean_squared_error(y_test, predicted)
                ),
                directional_accuracy=_decimal(
                    float(
                        np.mean(
                            np.sign(predicted) == np.sign(y_test)
                        )
                    )
                ),
                prediction_hash=prediction_hash,
            ),
        ),
    )
    return dataset, source


def _report_replays() -> tuple[ReplayedModelPredictions, ...]:
    families = (
        "linear_regression",
        "ridge_regression",
        "random_forest_regression",
        "xgboost_regression",
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    replays: list[ReplayedModelPredictions] = []
    for family_index, family in enumerate(families, start=1):
        predictions: list[PredictionEvidence] = []
        for index in range(25):
            actual = (index - 12) / 1000
            predicted = actual * (0.5 + family_index / 20) + 0.001
            residual = actual - predicted
            predictions.append(
                PredictionEvidence(
                    experiment_id=UUID(int=family_index),
                    experiment_split_id=index // 5 + 1,
                    model_family=family,  # type: ignore[arg-type]
                    split_sequence=index // 5 + 1,
                    observation_index=index % 5 + 1,
                    prediction_timestamp=start + timedelta(days=index),
                    actual=actual,
                    predicted=predicted,
                    residual=residual,
                    source_prediction_hash=f"{family_index:x}" * 64,
                    evidence_hash=(
                        f"{family_index:x}" * 60 + f"{index:04x}"
                    ),
                )
            )
        source = ResidualExperimentSource(
            experiment_id=UUID(int=family_index),
            model_family=family,  # type: ignore[arg-type]
            model_parameters={},
            preprocessing_parameters={},
            evaluation_policy_parameters={
                "minimum_training_observations": 100
            },
            random_seeds=(),
            training_pipeline_version="1.0.0",
            experiment_configuration_hash=f"{family_index:x}" * 64,
            experiment_result_hash=f"{family_index + 4:x}" * 64,
            model_dataset_hash="a" * 64,
            feature_pipeline_version="1.1.0",
            target_version="1.0.0",
            validation_run_id=UUID(int=50),
            split_hash="b" * 64,
            evaluated_split_count=5,
            evaluated_observation_count=25,
            final_holdout_evaluated=False,
            split_evidence=(),
        )
        replays.append(
            ReplayedModelPredictions(
                source=source,
                predictions=tuple(predictions),
                verified_prediction_hash_count=5,
            )
        )
    return tuple(replays)


def _observation(timestamp: datetime, index: int) -> ModelObservation:
    return ModelObservation(
        prediction_timestamp=timestamp,
        label_available_at=timestamp + timedelta(days=5),
        feature_values=(
            Decimal(index),
            Decimal(index * index) / Decimal("100"),
        ),
        target_value=Decimal(index) / Decimal("1000"),
    )


def _arrays(
    observations: tuple[ModelObservation, ...],
) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray(
            [
                [float(value) for value in row.feature_values]
                for row in observations
            ],
            dtype=np.float64,
        ),
        np.asarray(
            [float(row.target_value) for row in observations],
            dtype=np.float64,
        ),
    )


def _prediction_hash(predicted: np.ndarray) -> str:
    digest = sha256()
    for value in predicted:
        digest.update((float(value).hex() + "\n").encode())
    return digest.hexdigest()


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000000000000000001"))


if __name__ == "__main__":
    unittest.main()
