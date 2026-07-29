"""Immutable persistence for approved model explainability artifacts."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
    RegressionExperimentSplitRecord,
)
from app.research.dataset import build_model_ready_dataset
from app.research.explainability import (
    EXPLAINABILITY_REPORT_VERSION,
    PERMUTATION_RANDOM_STATE,
    PERMUTATION_REPEATS,
    BuiltExplainabilityArtifact,
    ExplainabilitySource,
    SourceSplitEvidence,
    build_explainability_artifact,
)


APPROVED_EXPLAINABILITY_EXPERIMENTS: dict[str, UUID] = {
    "random_forest_regression": UUID(
        "50c8db70-b323-49a0-ad51-09e2cef7081a"
    ),
    "xgboost_regression": UUID(
        "ae78c39e-abef-4ec0-81df-e99d3922da6f"
    ),
}


@dataclass(frozen=True, slots=True)
class PersistedExplainabilityArtifact:
    artifact_id: UUID
    generated_at: datetime
    built: BuiltExplainabilityArtifact
    created: bool


async def create_explainability_artifact(
    session: AsyncSession,
    model_family: str,
) -> PersistedExplainabilityArtifact:
    approved_id = APPROVED_EXPLAINABILITY_EXPERIMENTS.get(model_family)
    if approved_id is None:
        raise ValueError(
            f"Explainability is not approved for {model_family}."
        )

    async with session.begin():
        dataset = await build_model_ready_dataset(session)
        experiment = await session.get(
            RegressionExperimentRecord,
            approved_id,
        )
        if experiment is None or experiment.model_family != model_family:
            raise ValueError(
                f"The approved {model_family} experiment is unavailable."
            )
        split_records = tuple(
            (
                await session.scalars(
                    select(RegressionExperimentSplitRecord)
                    .where(
                        RegressionExperimentSplitRecord.experiment_id
                        == experiment.id
                    )
                    .order_by(
                        RegressionExperimentSplitRecord.split_sequence
                    )
                )
            ).all()
        )
        source = ExplainabilitySource(
            experiment_id=experiment.id,
            model_family=model_family,  # type: ignore[arg-type]
            model_parameters=experiment.model_parameters,
            training_pipeline_version=(
                experiment.training_pipeline_version
            ),
            experiment_configuration_hash=(
                experiment.experiment_configuration_hash
            ),
            experiment_result_hash=experiment.result_hash,
            model_dataset_hash=experiment.model_dataset_hash,
            feature_pipeline_version=experiment.feature_pipeline_version,
            target_version=experiment.target_version,
            validation_run_id=experiment.validation_run_id,
            split_hash=experiment.split_hash,
            evaluated_split_count=experiment.evaluated_split_count,
            evaluated_observation_count=(
                experiment.evaluated_observation_count
            ),
            split_evidence=tuple(
                SourceSplitEvidence(
                    sequence=split.split_sequence,
                    status=split.status,
                    prediction_hash=split.prediction_hash,
                )
                for split in split_records
            ),
        )
        built = build_explainability_artifact(dataset, source)
        existing = (
            await session.scalars(
                select(ModelExplainabilityArtifactRecord).where(
                    ModelExplainabilityArtifactRecord.experiment_id
                    == experiment.id,
                    ModelExplainabilityArtifactRecord.configuration_hash
                    == built.configuration_hash,
                    ModelExplainabilityArtifactRecord.result_hash
                    == built.result_hash,
                )
            )
        ).one_or_none()
        if existing is not None:
            return PersistedExplainabilityArtifact(
                artifact_id=existing.id,
                generated_at=existing.generated_at,
                built=built,
                created=False,
            )

        artifact_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        session.add(
            ModelExplainabilityArtifactRecord(
                id=artifact_id,
                experiment_id=experiment.id,
                model_family=experiment.model_family,
                report_version=EXPLAINABILITY_REPORT_VERSION,
                method_configuration=built.configuration,
                artifact_payload=built.payload,
                configuration_hash=built.configuration_hash,
                result_hash=built.result_hash,
                model_dataset_hash=dataset.model_dataset_hash,
                feature_pipeline_version=dataset.feature_pipeline_version,
                target_version=dataset.target_version,
                validation_run_id=dataset.validation_run_id,
                split_hash=dataset.validation_split_hash,
                permutation_random_seed=PERMUTATION_RANDOM_STATE,
                permutation_repeats=PERMUTATION_REPEATS,
                evaluated_split_count=experiment.evaluated_split_count,
                evaluated_observation_count=(
                    experiment.evaluated_observation_count
                ),
                prediction_hashes_verified=(
                    built.prediction_hashes_verified
                ),
                point_in_time_validated=True,
                final_holdout_evaluated=False,
                generated_at=generated_at,
            )
        )
        await session.flush()

    return PersistedExplainabilityArtifact(
        artifact_id=artifact_id,
        generated_at=generated_at,
        built=built,
        created=True,
    )
