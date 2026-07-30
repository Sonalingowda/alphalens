"""One-time packaging and fit-free loading of selected Ridge inference."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

import numpy as np
import sklearn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.artifact import (
    INFERENCE_ARTIFACT_VERSION,
    PackagedRidgeInference,
    build_artifact_envelope,
    hash_json,
    load_ridge_inference_artifact,
)
from app.model_packaging.ridge import (
    build_ridge_artifact_core,
    replay_selected_ridge_for_packaging,
)
from app.persistence.holdout_evaluation import (
    APPROVED_SELECTED_RIDGE_EXPERIMENT_ID,
)
from app.persistence.models import (
    EngineeredFeatureRecord,
    HoldoutEvaluationReportRecord,
    HoldoutPredictionEvidenceRecord,
    ModelInferenceArtifactRecord,
    RegressionExperimentRecord,
)
from app.research.dataset import (
    MODEL_FEATURE_NAMES,
    ModelObservation,
    build_model_ready_dataset,
)


@dataclass(frozen=True, slots=True)
class PersistedInferenceArtifact:
    artifact_id: UUID
    created_at: datetime
    configuration_hash: str
    artifact_sha256: str
    state_sha256: str
    verification_evidence_hash: str
    created: bool


async def package_selected_ridge_inference_once(
    session: AsyncSession,
) -> PersistedInferenceArtifact:
    """Perform the one authorized fit, or verify an existing artifact."""
    async with session.begin():
        existing = (
            await session.scalars(
                select(ModelInferenceArtifactRecord).where(
                    ModelInferenceArtifactRecord.selected_experiment_id
                    == APPROVED_SELECTED_RIDGE_EXPERIMENT_ID
                )
            )
        ).one_or_none()
        if existing is not None:
            _verified_record(existing)
            return _persisted(existing, created=False)

        experiment = await session.get(
            RegressionExperimentRecord,
            APPROVED_SELECTED_RIDGE_EXPERIMENT_ID,
        )
        holdout = (
            await session.scalars(
                select(HoldoutEvaluationReportRecord).where(
                    HoldoutEvaluationReportRecord.selected_experiment_id
                    == APPROVED_SELECTED_RIDGE_EXPERIMENT_ID,
                    HoldoutEvaluationReportRecord
                    .official_holdout_evaluation
                    .is_(True),
                )
            )
        ).one()
        if experiment is None:
            raise ValueError("Selected Ridge experiment is unavailable.")
        _verify_sources(experiment, holdout)
        dataset = await build_model_ready_dataset(session)
        training = dataset.development_observations[
            : holdout.final_training_observation_count
        ]
        training_hash = _observation_hash(training)
        if (
            len(training) != 611
            or len(dataset.development_observations) - len(training) != 50
            or dataset.model_dataset_hash != holdout.model_dataset_hash
            or training_hash != holdout.training_dataset_hash
            or dataset.feature_names != MODEL_FEATURE_NAMES
        ):
            raise ValueError("Final packaging training evidence differs.")
        evidence, feature_rows = await _load_verification_inputs(
            session,
            holdout,
            dataset.source_feature_run_id,
        )
        verification_features = _verification_feature_vectors(
            evidence,
            feature_rows,
        )
        expected_float_hex = tuple(
            item.predicted_float_hex for item in evidence
        )
        if (
            len(evidence) != 5
            or _sha256_lines(expected_float_hex)
            != holdout.holdout_prediction_hash
        ):
            raise ValueError("Official prediction evidence differs.")
        software_versions = {
            **experiment.software_versions,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        }
        configuration = {
            "artifact_version": INFERENCE_ARTIFACT_VERSION,
            "scope": "authorized_selected_ridge_inference_packaging",
            "selected_experiment_id": str(experiment.id),
            "experiment_configuration_hash": (
                experiment.experiment_configuration_hash
            ),
            "experiment_result_hash": experiment.result_hash,
            "model_parameters": experiment.model_parameters,
            "preprocessing_parameters": (
                experiment.preprocessing_parameters
            ),
            "model_dataset_hash": dataset.model_dataset_hash,
            "training_dataset_hash": training_hash,
            "feature_pipeline_version": (
                dataset.feature_pipeline_version
            ),
            "target_version": dataset.target_version,
            "validation_run_id": str(dataset.validation_run_id),
            "split_hash": dataset.validation_split_hash,
            "final_training_observation_count": len(training),
            "purged_observation_count": 50,
            "ordered_feature_schema": list(dataset.feature_names),
            "software_versions": dict(sorted(software_versions.items())),
            "holdout_evaluation_report_id": str(holdout.id),
            "official_holdout_prediction_hash": (
                holdout.holdout_prediction_hash
            ),
        }
        configuration_hash = hash_json(configuration)

        # The only fit authorized by Engineering Phase 2.5.
        fitted_state = replay_selected_ridge_for_packaging(
            training_observations=training,
            model_parameters=experiment.model_parameters,
        )
        created_at = datetime.now(timezone.utc)
        core = build_ridge_artifact_core(
            state=fitted_state,
            configuration_hash=configuration_hash,
            feature_names=dataset.feature_names,
            feature_pipeline_version=dataset.feature_pipeline_version,
            model_dataset_hash=dataset.model_dataset_hash,
            training_dataset_hash=training_hash,
            software_versions=software_versions,
            provenance={
                "selected_experiment_id": str(experiment.id),
                "experiment_configuration_hash": (
                    experiment.experiment_configuration_hash
                ),
                "experiment_result_hash": experiment.result_hash,
                "holdout_evaluation_report_id": str(holdout.id),
                "holdout_configuration_hash": (
                    holdout.configuration_hash
                ),
                "holdout_result_hash": holdout.result_hash,
                "validation_run_id": str(dataset.validation_run_id),
                "split_hash": dataset.validation_split_hash,
                "source_ingestion_batch_id": str(
                    dataset.source_ingestion_batch_id
                ),
                "source_feature_run_id": str(
                    dataset.source_feature_run_id
                ),
                "source_target_run_id": str(
                    dataset.source_target_run_id
                ),
            },
        )
        artifact_payload, artifact_sha = build_artifact_envelope(
            core=core,
            created_at_iso=created_at.isoformat(),
        )
        repeated_payload, repeated_sha = build_artifact_envelope(
            core=core,
            created_at_iso=created_at.isoformat(),
        )
        if (
            artifact_payload != repeated_payload
            or artifact_sha != repeated_sha
        ):
            raise ValueError("Artifact packaging is not deterministic.")
        inference = load_ridge_inference_artifact(
            artifact_payload,
            expected_artifact_sha256=artifact_sha,
        )
        first_predictions = inference.predict_batch(
            verification_features
        )
        second_predictions = inference.predict_batch(
            verification_features
        )
        actual_float_hex = tuple(
            item.float_hex for item in first_predictions
        )
        if (
            actual_float_hex != expected_float_hex
            or actual_float_hex
            != tuple(item.float_hex for item in second_predictions)
            or _sha256_lines(actual_float_hex)
            != holdout.holdout_prediction_hash
        ):
            raise ValueError(
                "Artifact-only predictions differ from official evidence."
            )
        verification = {
            "artifact_only_inference": True,
            "training_invoked_during_inference": False,
            "verification_prediction_count": len(evidence),
            "official_prediction_hash": (
                holdout.holdout_prediction_hash
            ),
            "artifact_prediction_hash": _sha256_lines(
                actual_float_hex
            ),
            "all_prediction_float_hex_values_match": True,
            "repeatability_verified": True,
            "predictions": [
                {
                    "prediction_timestamp": (
                        evidence[index]
                        .prediction_timestamp.isoformat()
                    ),
                    "expected_float_hex": expected,
                    "artifact_float_hex": actual,
                    "source_prediction_evidence_hash": (
                        evidence[index].evidence_hash
                    ),
                    "match": expected == actual,
                }
                for index, (expected, actual) in enumerate(
                    zip(
                        expected_float_hex,
                        actual_float_hex,
                        strict=True,
                    )
                )
            ],
            "model_tuned": False,
            "experiment_modified": False,
            "research_artifacts_modified": False,
            "holdout_metrics_recomputed": False,
        }
        verification_hash = hash_json(verification)
        artifact_id = uuid4()
        state = core["numeric_state"]
        record = ModelInferenceArtifactRecord(
            id=artifact_id,
            artifact_version=INFERENCE_ARTIFACT_VERSION,
            model_family="ridge_regression",
            artifact_payload=artifact_payload,
            verification_evidence=verification,
            configuration_hash=configuration_hash,
            artifact_sha256=artifact_sha,
            state_sha256=artifact_payload["state_sha256"],
            verification_evidence_hash=verification_hash,
            selected_experiment_id=experiment.id,
            holdout_evaluation_report_id=holdout.id,
            model_dataset_hash=dataset.model_dataset_hash,
            training_dataset_hash=training_hash,
            feature_pipeline_version=dataset.feature_pipeline_version,
            target_version=dataset.target_version,
            validation_run_id=dataset.validation_run_id,
            split_hash=dataset.validation_split_hash,
            final_training_observation_count=len(training),
            purged_observation_count=50,
            feature_count=len(dataset.feature_names),
            coefficient_count=len(
                state["ridge_coefficients_float_hex"]
            ),
            scaler_mean_count=len(state["scaler_means_float_hex"]),
            scaler_scale_count=len(state["scaler_scales_float_hex"]),
            verification_prediction_count=len(evidence),
            official_prediction_hash=holdout.holdout_prediction_hash,
            deterministic_replay=True,
            official_prediction_hash_verified=True,
            artifact_only_inference_verified=True,
            model_tuned=False,
            experiment_modified=False,
            research_artifacts_modified=False,
            created_at=created_at,
        )
        session.add(record)
        await session.flush()
    return _persisted(record, created=True)


async def load_production_ridge_inference(
    session: AsyncSession,
) -> PackagedRidgeInference:
    """Load the selected model exclusively from its immutable artifact."""
    record = (
        await session.scalars(
            select(ModelInferenceArtifactRecord).where(
                ModelInferenceArtifactRecord.selected_experiment_id
                == APPROVED_SELECTED_RIDGE_EXPERIMENT_ID
            )
        )
    ).one()
    _verified_record(record)
    return load_ridge_inference_artifact(
        record.artifact_payload,
        expected_artifact_sha256=record.artifact_sha256,
    )


def _verify_sources(
    experiment: RegressionExperimentRecord,
    holdout: HoldoutEvaluationReportRecord,
) -> None:
    if (
        experiment.model_family != "ridge_regression"
        or experiment.feature_pipeline_version != "1.1.0"
        or experiment.target_version != "1.0.0"
        or experiment.id != holdout.selected_experiment_id
        or experiment.model_dataset_hash != holdout.model_dataset_hash
        or experiment.validation_run_id != holdout.validation_run_id
        or experiment.split_hash != holdout.split_hash
        or hash_json(holdout.report_configuration)
        != holdout.configuration_hash
        or hash_json(holdout.report_payload) != holdout.result_hash
        or not holdout.holdout_consumed
    ):
        raise ValueError("Selected experiment provenance differs.")


async def _load_verification_inputs(
    session: AsyncSession,
    holdout: HoldoutEvaluationReportRecord,
    feature_run_id: UUID,
) -> tuple[
    tuple[HoldoutPredictionEvidenceRecord, ...],
    tuple[tuple[Any, ...], ...],
]:
    evidence = tuple(
        (
            await session.scalars(
                select(HoldoutPredictionEvidenceRecord)
                .where(
                    HoldoutPredictionEvidenceRecord.report_id
                    == holdout.id
                )
                .order_by(
                    HoldoutPredictionEvidenceRecord.prediction_timestamp
                )
            )
        ).all()
    )
    timestamps = tuple(item.prediction_timestamp for item in evidence)
    rows = tuple(
        (
            await session.execute(
                select(
                    EngineeredFeatureRecord.candle_timestamp,
                    EngineeredFeatureRecord.feature_name,
                    EngineeredFeatureRecord.feature_value,
                )
                .where(
                    EngineeredFeatureRecord.computation_run_id
                    == feature_run_id,
                    EngineeredFeatureRecord.candle_timestamp.in_(
                        timestamps
                    ),
                )
                .order_by(
                    EngineeredFeatureRecord.candle_timestamp,
                    EngineeredFeatureRecord.feature_name,
                )
            )
        ).all()
    )
    if len(rows) != len(evidence) * len(MODEL_FEATURE_NAMES):
        raise ValueError("Holdout feature vectors are incomplete.")
    return evidence, rows


def _verification_feature_vectors(
    evidence: tuple[HoldoutPredictionEvidenceRecord, ...],
    rows: tuple[tuple[Any, ...], ...],
) -> tuple[tuple[Decimal, ...], ...]:
    values: dict[Any, dict[str, Decimal]] = {}
    for timestamp, name, value in rows:
        values.setdefault(timestamp, {})[name] = value
    result: list[tuple[Decimal, ...]] = []
    for item in evidence:
        by_name = values.get(item.prediction_timestamp)
        if by_name is None or tuple(sorted(by_name)) != MODEL_FEATURE_NAMES:
            raise ValueError("Holdout feature schema differs.")
        result.append(
            tuple(by_name[name] for name in MODEL_FEATURE_NAMES)
        )
    return tuple(result)


def _verified_record(record: ModelInferenceArtifactRecord) -> None:
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
        raise ValueError("Persisted inference artifact failed verification.")
    load_ridge_inference_artifact(
        record.artifact_payload,
        expected_artifact_sha256=record.artifact_sha256,
    )


def _persisted(
    record: ModelInferenceArtifactRecord,
    *,
    created: bool,
) -> PersistedInferenceArtifact:
    return PersistedInferenceArtifact(
        artifact_id=record.id,
        created_at=record.created_at,
        configuration_hash=record.configuration_hash,
        artifact_sha256=record.artifact_sha256,
        state_sha256=record.state_sha256,
        verification_evidence_hash=record.verification_evidence_hash,
        created=created,
    )


def _observation_hash(
    observations: tuple[ModelObservation, ...],
) -> str:
    return _sha256_lines(
        tuple(
            "|".join(
                (
                    item.prediction_timestamp.isoformat(),
                    item.label_available_at.isoformat(),
                    *(
                        format(value, "f")
                        for value in item.feature_values
                    ),
                    format(item.target_value, "f"),
                )
            )
            for item in observations
        )
    )


def _sha256_lines(values: tuple[str, ...]) -> str:
    digest = sha256()
    for value in values:
        digest.update((value + "\n").encode())
    return digest.hexdigest()

