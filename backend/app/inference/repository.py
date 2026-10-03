"""Read-only loading of the immutable production inference artifact."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.artifact import (
    PackagedExpectedMoveInference,
    PackagedRidgeInference,
    hash_json,
    load_expected_move_inference_artifact,
    load_ridge_inference_artifact,
)
from app.inference.lineage import verify_ridge_artifact_lineage
from app.persistence.models import (
    FinalModelSelectionReportRecord,
    HoldoutConsumptionRecord,
    HoldoutEvaluationReportRecord,
    ModelInferenceArtifactRecord,
    RegressionExperimentRecord,
    ValidationRunRecord,
)


ACTIVE_ARTIFACT_STATUS = "ACTIVE"
RETIRED_ARTIFACT_STATUS = "RETIRED"


@dataclass(frozen=True, slots=True)
class LoadedProductionArtifact:
    artifact_id: UUID
    configuration_hash: str
    artifact_sha256: str
    state_sha256: str
    model_family: str
    feature_pipeline_version: str
    target_version: str
    model_dataset_hash: str
    training_dataset_hash: str
    selected_experiment_id: UUID
    holdout_evaluation_report_id: UUID
    validation_run_id: UUID
    split_hash: str
    inference: PackagedRidgeInference


@dataclass(frozen=True, slots=True)
class LoadedExpectedMoveArtifact:
    artifact_id: UUID
    configuration_hash: str
    artifact_sha256: str
    state_sha256: str
    model_family: str
    feature_pipeline_version: str
    inference: PackagedExpectedMoveInference


async def load_production_artifact(
    session: AsyncSession,
) -> LoadedProductionArtifact:
    """Verify and load the explicitly active production artifact."""
    records = (
        await session.scalars(
            select(ModelInferenceArtifactRecord).where(
                ModelInferenceArtifactRecord.release_status
                == ACTIVE_ARTIFACT_STATUS
            )
        )
    ).all()
    if len(records) != 1:
        raise ValueError("Production requires exactly one inference artifact.")
    record = records[0]
    experiment = await session.get(RegressionExperimentRecord, record.selected_experiment_id)
    holdout = await session.get(HoldoutEvaluationReportRecord, record.holdout_evaluation_report_id)
    if experiment is None or holdout is None:
        raise ValueError("Production artifact lineage is incomplete.")
    selection = await session.get(FinalModelSelectionReportRecord, holdout.final_model_selection_report_id)
    validation = await session.get(ValidationRunRecord, record.validation_run_id)
    consumptions = (await session.scalars(
        select(HoldoutConsumptionRecord).where(
            HoldoutConsumptionRecord.validation_run_id == record.validation_run_id,
            HoldoutConsumptionRecord.holdout_evaluation_report_id == holdout.id,
        )
    )).all()
    if selection is None or validation is None:
        raise ValueError("Production artifact lineage is incomplete.")
    verify_ridge_artifact_lineage(
        artifact=record,
        experiment=experiment,
        selection=selection,
        holdout=holdout,
        validation=validation,
        holdout_consumption_count=len(consumptions),
        artifact_count=len(records),
        holdout_consumption_verified=all(
            item.validation_run_id == record.validation_run_id
            and item.holdout_evaluation_report_id == holdout.id
            and item.selected_experiment_id == record.selected_experiment_id
            and
            item.purpose == "official_final_evaluation"
            and item.official
            and item.irreversible
            for item in consumptions
        ),
    )
    inference = load_ridge_inference_artifact(
        record.artifact_payload,
        expected_artifact_sha256=record.artifact_sha256,
    )
    return LoadedProductionArtifact(
        artifact_id=record.id,
        configuration_hash=record.configuration_hash,
        artifact_sha256=record.artifact_sha256,
        state_sha256=record.state_sha256,
        model_family=record.model_family,
        feature_pipeline_version=record.feature_pipeline_version,
        target_version=record.target_version,
        model_dataset_hash=record.model_dataset_hash,
        training_dataset_hash=record.training_dataset_hash,
        selected_experiment_id=record.selected_experiment_id,
        holdout_evaluation_report_id=(
            record.holdout_evaluation_report_id
        ),
        validation_run_id=record.validation_run_id,
        split_hash=record.split_hash,
        inference=inference,
    )


async def load_expected_move_artifact(
    session: AsyncSession,
    *,
    model_family: str = "expected_move_ridge",
) -> LoadedExpectedMoveArtifact | None:
    """Load the expected-move artifact if present, or return None.

    Returns None when no expected-move artifact has been packaged yet,
    allowing the pipeline to fall back to V1.1 behavior.
    """
    record = (
        await session.scalars(
            select(ModelInferenceArtifactRecord).where(
                ModelInferenceArtifactRecord.model_family == model_family
            )
        )
    ).one_or_none()
    if record is None:
        return None
    if (
        hash_json(record.artifact_payload) != record.artifact_sha256
        or hash_json(record.artifact_payload["core"])
        != record.state_sha256
    ):
        raise ValueError("Expected-move inference artifact failed hash verification.")
    inference = load_expected_move_inference_artifact(
        record.artifact_payload,
        expected_artifact_sha256=record.artifact_sha256,
    )
    return LoadedExpectedMoveArtifact(
        artifact_id=record.id,
        configuration_hash=record.configuration_hash,
        artifact_sha256=record.artifact_sha256,
        state_sha256=record.state_sha256,
        model_family=record.model_family,
        feature_pipeline_version=record.feature_pipeline_version,
        inference=inference,
    )
