"""Immutable persistence for baseline regression experiments."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    HoldoutConsumptionRecord,
    RegressionExperimentRecord,
    RegressionExperimentSplitRecord,
)
from app.research.baseline_regression import (
    BaselineEvaluation,
    ModelFamily,
    run_baseline_evaluation,
)
from app.research.dataset import (
    ModelReadyDataset,
    build_model_ready_dataset,
)


@dataclass(frozen=True, slots=True)
class PersistedBaselineExperiment:
    experiment_id: UUID
    completed_at: datetime
    dataset: ModelReadyDataset
    evaluation: BaselineEvaluation


async def run_and_persist_baseline_experiment(
    session: AsyncSession,
    model_family: ModelFamily,
) -> PersistedBaselineExperiment:
    async with session.begin():
        dataset = await build_model_ready_dataset(session)
        if (
            await session.get(
                HoldoutConsumptionRecord,
                dataset.validation_run_id,
            )
            is not None
        ):
            raise ValueError(
                "Official holdout is consumed; model development is closed."
            )
        evaluation = run_baseline_evaluation(dataset, model_family)
        experiment_id = uuid4()
        completed_at = datetime.now(timezone.utc)

        session.add(
            RegressionExperimentRecord(
                id=experiment_id,
                model_family=evaluation.model_family,
                model_parameters=evaluation.model_parameters,
                preprocessing_parameters=(
                    evaluation.preprocessing_parameters
                ),
                evaluation_policy_parameters=(
                    evaluation.evaluation_policy_parameters
                ),
                random_seeds=list(evaluation.random_seeds),
                training_pipeline_version=(
                    evaluation.training_pipeline_version
                ),
                training_code_hash=evaluation.training_code_hash,
                source_ingestion_batch_id=(
                    dataset.source_ingestion_batch_id
                ),
                source_feature_run_id=dataset.source_feature_run_id,
                source_target_run_id=dataset.source_target_run_id,
                validation_run_id=dataset.validation_run_id,
                source_dataset_hash=dataset.source_dataset_hash,
                model_dataset_hash=dataset.model_dataset_hash,
                feature_pipeline_version=(
                    dataset.feature_pipeline_version
                ),
                feature_names=list(dataset.feature_names),
                target_name=dataset.target_name,
                target_version=dataset.target_version,
                target_definition_hash=dataset.target_definition_hash,
                split_hash=dataset.validation_split_hash,
                source_observation_count=dataset.source_observation_count,
                model_eligible_observation_count=(
                    dataset.total_eligible_observation_count
                ),
                development_eligible_observation_count=(
                    dataset.development_eligible_observation_count
                ),
                holdout_eligible_observation_count=(
                    dataset.holdout_eligible_observation_count
                ),
                excluded_feature_warmup_count=(
                    dataset.excluded_feature_warmup_count
                ),
                excluded_missing_target_count=(
                    dataset.excluded_missing_target_count
                ),
                validation_split_count=len(dataset.validation_splits),
                evaluated_split_count=evaluation.evaluated_split_count,
                skipped_split_count=evaluation.skipped_split_count,
                evaluated_observation_count=(
                    evaluation.evaluated_observation_count
                ),
                aggregate_mae=evaluation.aggregate_mae,
                aggregate_rmse=evaluation.aggregate_rmse,
                aggregate_directional_accuracy=(
                    evaluation.aggregate_directional_accuracy
                ),
                aggregation_method=evaluation.aggregation_method,
                software_versions=evaluation.software_versions,
                experiment_configuration_hash=(
                    evaluation.experiment_configuration_hash
                ),
                result_hash=evaluation.result_hash,
                point_in_time_validated=(
                    evaluation.point_in_time_validated
                ),
                final_holdout_evaluated=(
                    evaluation.final_holdout_evaluated
                ),
                completed_at=completed_at,
            )
        )
        session.add_all(
            [
                RegressionExperimentSplitRecord(
                    experiment_id=experiment_id,
                    split_sequence=result.sequence,
                    train_start=result.train_start,
                    train_end=result.train_end,
                    test_start=result.test_start,
                    test_end=result.test_end,
                    train_observation_count=(
                        result.train_observation_count
                    ),
                    test_observation_count=result.test_observation_count,
                    status=result.status,
                    exclusion_reason=result.exclusion_reason,
                    latest_train_label_available_at=(
                        result.latest_train_label_available_at
                    ),
                    mae=result.mae,
                    rmse=result.rmse,
                    directional_accuracy=result.directional_accuracy,
                    prediction_hash=result.prediction_hash,
                )
                for result in evaluation.split_evaluations
            ]
        )
        await session.flush()

    return PersistedBaselineExperiment(
        experiment_id=experiment_id,
        completed_at=completed_at,
        dataset=dataset,
        evaluation=evaluation,
    )
