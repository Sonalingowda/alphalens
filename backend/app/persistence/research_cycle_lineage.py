"""Resolve immutable research evidence within the current dataset lineage."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
)
from app.research.dataset import ModelReadyDataset

MODEL_FAMILIES = (
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
)
EXPLAINABILITY_MODEL_FAMILIES = (
    "random_forest_regression",
    "xgboost_regression",
)


async def current_cycle_experiments(
    session: AsyncSession,
    dataset: ModelReadyDataset,
) -> tuple[RegressionExperimentRecord, ...]:
    records = tuple(
        (
            await session.scalars(
                select(RegressionExperimentRecord).where(
                    RegressionExperimentRecord.model_dataset_hash
                    == dataset.model_dataset_hash,
                    RegressionExperimentRecord.validation_run_id
                    == dataset.validation_run_id,
                    RegressionExperimentRecord.split_hash
                    == dataset.validation_split_hash,
                )
            )
        ).all()
    )
    by_family = {record.model_family: record for record in records}
    if (
        len(records) != len(MODEL_FAMILIES)
        or set(by_family) != set(MODEL_FAMILIES)
    ):
        raise ValueError("Current-cycle experiment set is incomplete or ambiguous.")
    if any(
        not record.point_in_time_validated or record.final_holdout_evaluated
        for record in records
    ):
        raise ValueError("Current-cycle experiment eligibility differs.")
    return tuple(by_family[family] for family in MODEL_FAMILIES)


async def current_cycle_explainability(
    session: AsyncSession,
    experiments: tuple[RegressionExperimentRecord, ...],
) -> tuple[ModelExplainabilityArtifactRecord, ...]:
    experiment_by_family = {item.model_family: item for item in experiments}
    if set(experiment_by_family) != set(MODEL_FAMILIES):
        raise ValueError("Current-cycle experiment set is incomplete.")
    experiment_ids = tuple(
        experiment_by_family[family].id
        for family in EXPLAINABILITY_MODEL_FAMILIES
    )
    artifacts = tuple(
        (
            await session.scalars(
                select(ModelExplainabilityArtifactRecord).where(
                    ModelExplainabilityArtifactRecord.experiment_id.in_(
                        experiment_ids
                    )
                )
            )
        ).all()
    )
    by_family = {artifact.model_family: artifact for artifact in artifacts}
    if (
        len(artifacts) != len(EXPLAINABILITY_MODEL_FAMILIES)
        or set(by_family) != set(EXPLAINABILITY_MODEL_FAMILIES)
    ):
        raise ValueError("Current-cycle explainability evidence is incomplete or ambiguous.")
    for family, artifact in by_family.items():
        experiment = experiment_by_family[family]
        if (
            artifact.experiment_id != experiment.id
            or artifact.model_dataset_hash != experiment.model_dataset_hash
            or artifact.validation_run_id != experiment.validation_run_id
            or artifact.split_hash != experiment.split_hash
            or artifact.final_holdout_evaluated
        ):
            raise ValueError("Current-cycle explainability provenance differs.")
    return tuple(by_family[family] for family in EXPLAINABILITY_MODEL_FAMILIES)


async def current_cycle_report(
    session: AsyncSession,
    report_model: type,
    dataset: ModelReadyDataset,
) -> object:
    return (
        await session.scalars(
            select(report_model).where(
                report_model.model_dataset_hash == dataset.model_dataset_hash,
                report_model.validation_run_id == dataset.validation_run_id,
                report_model.split_hash == dataset.validation_split_hash,
                report_model.final_holdout_evaluated.is_(False),
            )
        )
    ).one()
