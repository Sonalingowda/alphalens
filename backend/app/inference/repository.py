"""Read-only loading of the immutable production inference artifact."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.artifact import (
    PackagedRidgeInference,
    hash_json,
    load_ridge_inference_artifact,
)
from app.persistence.models import ModelInferenceArtifactRecord


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


async def load_production_artifact(
    session: AsyncSession,
) -> LoadedProductionArtifact:
    """Verify and load the sole production artifact without training code."""
    record = (
        await session.scalars(
            select(ModelInferenceArtifactRecord)
        )
    ).one()
    if (
        hash_json(record.artifact_payload) != record.artifact_sha256
        or hash_json(record.artifact_payload["core"])
        != record.state_sha256
        or hash_json(record.verification_evidence)
        != record.verification_evidence_hash
        or not record.official_prediction_hash_verified
        or not record.artifact_only_inference_verified
        or record.model_tuned
        or record.experiment_modified
        or record.research_artifacts_modified
    ):
        raise ValueError("Production inference artifact failed verification.")
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

