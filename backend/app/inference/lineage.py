"""Fail-closed verification of the immutable Ridge artifact lineage."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.inference.artifact import hash_json, load_ridge_inference_artifact


def _value(record: object | Mapping[str, Any], name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


def _same_id(left: object, right: object) -> bool:
    return str(left) == str(right)


def verify_ridge_artifact_lineage(
    *,
    artifact: object | Mapping[str, Any],
    experiment: object | Mapping[str, Any],
    selection: object | Mapping[str, Any],
    holdout: object | Mapping[str, Any],
    validation: object | Mapping[str, Any],
    holdout_consumption_count: int,
    artifact_count: int,
    holdout_consumption_verified: bool = False,
) -> None:
    """Verify the complete immutable research-to-artifact contract."""
    try:
        UUID(str(_value(artifact, "id")))
    except (AttributeError, ValueError) as error:
        raise ValueError("Artifact identity is invalid.") from error
    if (
        artifact_count != 1
        or holdout_consumption_count != 1
        or not holdout_consumption_verified
    ):
        raise ValueError("Artifact or holdout identity is not unique.")
    if (
        _value(artifact, "model_family") != "ridge_regression"
        or _value(artifact, "artifact_version") != "1.0.0"
        or _value(artifact, "final_training_observation_count") != 610
        or _value(artifact, "purged_observation_count") != 50
        or _value(artifact, "feature_pipeline_version") != "1.1.0"
        or _value(artifact, "target_version") != "1.0.0"
        or not _value(artifact, "deterministic_replay")
        or not _value(artifact, "official_prediction_hash_verified")
        or not _value(artifact, "artifact_only_inference_verified")
        or _value(artifact, "model_tuned")
        or _value(artifact, "experiment_modified")
        or _value(artifact, "research_artifacts_modified")
    ):
        raise ValueError("Artifact identity or integrity differs.")
    payload = _value(artifact, "artifact_payload")
    verification = _value(artifact, "verification_evidence")
    if (
        not isinstance(payload, Mapping)
        or not isinstance(verification, Mapping)
        or hash_json(payload) != _value(artifact, "artifact_sha256")
        or hash_json(payload.get("core")) != _value(artifact, "state_sha256")
        or hash_json(verification) != _value(artifact, "verification_evidence_hash")
    ):
        raise ValueError("Artifact hash verification failed.")
    core = payload.get("core")
    if (
        not isinstance(core, Mapping)
        or core.get("configuration_hash") != _value(artifact, "configuration_hash")
        or core.get("dataset_hash") != _value(artifact, "model_dataset_hash")
        or core.get("training_hash") != _value(artifact, "training_dataset_hash")
    ):
        raise ValueError("Artifact payload provenance differs.")
    provenance = core.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("Artifact provenance is missing.")
    expected_provenance = {
        "selected_experiment_id": str(_value(experiment, "id")),
        "experiment_configuration_hash": _value(
            experiment, "experiment_configuration_hash"
        ),
        "experiment_result_hash": _value(experiment, "result_hash"),
        "holdout_evaluation_report_id": str(_value(holdout, "id")),
        "holdout_configuration_hash": _value(holdout, "configuration_hash"),
        "holdout_result_hash": _value(holdout, "result_hash"),
        "validation_run_id": str(_value(validation, "id")),
        "split_hash": _value(validation, "split_hash"),
        "source_ingestion_batch_id": str(
            _value(experiment, "source_ingestion_batch_id")
        ),
        "source_feature_run_id": str(
            _value(experiment, "source_feature_run_id")
        ),
        "source_target_run_id": str(
            _value(experiment, "source_target_run_id")
        ),
    }
    if any(provenance.get(key) != value for key, value in expected_provenance.items()):
        raise ValueError("Artifact parent provenance differs.")
    if (
        core.get("configuration_hash") != _value(experiment, "experiment_configuration_hash")
        and provenance.get("experiment_configuration_hash")
        != _value(experiment, "experiment_configuration_hash")
    ):
        raise ValueError("Model configuration lineage differs.")
    if (
        not isinstance(verification.get("official_prediction_hash"), str)
        or verification.get("official_prediction_hash")
        != _value(artifact, "official_prediction_hash")
        or verification.get("artifact_prediction_hash")
        != _value(artifact, "official_prediction_hash")
        or verification.get("verification_prediction_count")
        != _value(artifact, "verification_prediction_count")
        or verification.get("repeatability_verified") is not True
        or verification.get("all_prediction_float_hex_values_match") is not True
    ):
        raise ValueError("Deterministic prediction evidence differs.")
    load_ridge_inference_artifact(
        dict(payload),
        expected_artifact_sha256=_value(artifact, "artifact_sha256"),
    )
    if (
        _value(selection, "selected_model_family") != "ridge_regression"
        or not _same_id(
            _value(selection, "id"),
            _value(holdout, "final_model_selection_report_id"),
        )
        or not _same_id(_value(selection, "selected_experiment_id"), _value(artifact, "selected_experiment_id"))
        or not _same_id(_value(selection, "validation_run_id"), _value(artifact, "validation_run_id"))
        or _value(selection, "model_dataset_hash") != _value(artifact, "model_dataset_hash")
        or _value(selection, "feature_pipeline_version") != _value(artifact, "feature_pipeline_version")
        or _value(selection, "target_version") != _value(artifact, "target_version")
        or _value(selection, "split_hash") != _value(artifact, "split_hash")
        or _value(selection, "point_in_time_validated") is not True
        or _value(selection, "repeatability_verified") is not True
        or _value(selection, "artifact_hashes_verified") is not True
        or _value(selection, "final_holdout_evaluated") is not False
    ):
        raise ValueError("Final selection lineage differs.")
    if (
        not _same_id(_value(experiment, "id"), _value(artifact, "selected_experiment_id"))
        or _value(experiment, "model_family") != "ridge_regression"
        or _value(experiment, "feature_pipeline_version") != "1.1.0"
        or _value(experiment, "target_version") != "1.0.0"
        or _value(experiment, "model_dataset_hash") != _value(artifact, "model_dataset_hash")
        or not _same_id(_value(experiment, "validation_run_id"), _value(artifact, "validation_run_id"))
        or _value(experiment, "split_hash") != _value(artifact, "split_hash")
        or _value(experiment, "model_parameters") is None
        or _value(experiment, "model_parameters")
        != {"alpha": "1.0", "fit_intercept": True, "solver": "svd"}
        or _value(experiment, "experiment_configuration_hash")
        != provenance.get("experiment_configuration_hash")
    ):
        raise ValueError("Experiment lineage differs.")
    if (
        not _same_id(_value(holdout, "id"), _value(artifact, "holdout_evaluation_report_id"))
        or not _same_id(_value(holdout, "selected_experiment_id"), _value(artifact, "selected_experiment_id"))
        or not _same_id(_value(holdout, "validation_run_id"), _value(artifact, "validation_run_id"))
        or _value(holdout, "model_dataset_hash") != _value(artifact, "model_dataset_hash")
        or _value(holdout, "split_hash") != _value(artifact, "split_hash")
        or not _value(holdout, "official_holdout_evaluation")
        or not _value(holdout, "holdout_evaluated")
        or not _value(holdout, "holdout_consumed")
        or _value(holdout, "official_holdout_evaluation") is not True
        or _value(holdout, "development_prediction_hashes_match") is not True
        or _value(holdout, "artifact_hashes_verified") is not True
        or _value(holdout, "model_parameters_modified") is not False
        or _value(holdout, "feature_engineering_performed") is not False
        or _value(holdout, "hyperparameter_tuning_performed") is not False
        or _value(holdout, "experiments_modified") is not False
        or hash_json(_value(holdout, "report_configuration")) != _value(holdout, "configuration_hash")
        or hash_json(_value(holdout, "report_payload")) != _value(holdout, "result_hash")
    ):
        raise ValueError("Holdout lineage or consumption differs.")
    if (
        not _same_id(_value(validation, "id"), _value(artifact, "validation_run_id"))
        or _value(validation, "split_hash") != _value(artifact, "split_hash")
    ):
        raise ValueError("Validation lineage differs.")
