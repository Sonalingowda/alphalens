"""Transfer the approved production state between authorized databases.

The production prediction API requires exactly one verified
``ridge_regression`` row in ``model_inference_artifacts`` at startup
(see ``app.startup.verify_readiness``).  This script exports that row
byte-identically from an authorized source database and imports it into a
target database after re-verifying every recorded hash.  No artifact content
is ever generated or modified by this script.

Usage:
    python scripts/transfer_approved_state.py export --url <source-url> --output state.json
    python scripts/transfer_approved_state.py export-closure --url <source-url> --input state.json --output closure.json
    python scripts/transfer_approved_state.py bind-restore-manifest --input release.json --closure closure.json --output production-release.json
    python scripts/transfer_approved_state.py verify-target --url <target-url> --manifest release.json
    python scripts/transfer_approved_state.py import --url <target-url> --input state.json --manifest release.json
    python scripts/transfer_approved_state.py import-closure --url <target-url> --input closure.json --manifest release.json
    python scripts/transfer_approved_state.py bootstrap-release --url <target-url> --closure closure.json --manifest release.json
    python scripts/transfer_approved_state.py replace --url <target-url> --input state.json --manifest release.json

Both commands refuse placeholder/dev credentials when targeting an explicit
URL whose environment is not otherwise validated; the URLs are used verbatim
as provided by the operator.
"""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
import json
import sys
from typing import Any
from uuid import UUID
from urllib.parse import urlsplit

from sqlalchemy import and_, func, inspect, null, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import JSONB

from app.inference.artifact import hash_json, load_ridge_inference_artifact
from app.inference.lineage import verify_ridge_artifact_lineage
from app.infrastructure.schema import expected_schema_heads
from app.persistence.database import session_factory
from app.persistence.model_inference import _verify_sources
from app.persistence.models import (
    Base,
    FinalModelSelectionReportRecord,
    HoldoutConsumptionRecord,
    HoldoutEvaluationReportRecord,
    ModelInferenceArtifactRecord,
    RegressionExperimentRecord,
    ValidationRunRecord,
)
from app.inference.repository import (
    ACTIVE_ARTIFACT_STATUS,
    RETIRED_ARTIFACT_STATUS,
    load_production_artifact,
)


_COLUMNS = (
    "id",
    "artifact_version",
    "model_family",
    "artifact_payload",
    "verification_evidence",
    "configuration_hash",
    "artifact_sha256",
    "state_sha256",
    "verification_evidence_hash",
    "selected_experiment_id",
    "holdout_evaluation_report_id",
    "model_dataset_hash",
    "training_dataset_hash",
    "feature_pipeline_version",
    "target_version",
    "validation_run_id",
    "split_hash",
    "final_training_observation_count",
    "purged_observation_count",
    "feature_count",
    "coefficient_count",
    "scaler_mean_count",
    "scaler_scale_count",
    "verification_prediction_count",
    "official_prediction_hash",
    "deterministic_replay",
    "official_prediction_hash_verified",
    "artifact_only_inference_verified",
    "model_tuned",
    "experiment_modified",
    "research_artifacts_modified",
    "created_at",
)

_JSON_COLUMNS = frozenset({"artifact_payload", "verification_evidence"})
_DATETIME_COLUMNS = frozenset({"created_at"})
_UUID_COLUMNS = frozenset(
    {
        "id",
        "selected_experiment_id",
        "holdout_evaluation_report_id",
        "validation_run_id",
    }
)

_MODEL_BY_TABLE = {
    mapper.local_table.name: mapper.class_
    for mapper in Base.registry.mappers
}


def _parent_schema_requirements() -> tuple[
    dict[str, frozenset[str]], frozenset[tuple[str, str, str, str]]
]:
    """Derive the persisted FK closure from the canonical ORM metadata."""

    tables: set[str] = set()
    foreign_keys: set[tuple[str, str, str, str]] = set()
    pending = [
        "model_inference_artifacts",
        "regression_experiments",
        "holdout_evaluation_reports",
        "validation_runs",
    ]
    while pending:
        table_name = pending.pop()
        if table_name in tables:
            continue
        table = Base.metadata.tables.get(table_name)
        if table is None:
            raise RuntimeError(f"Unknown required transfer table: {table_name}")
        tables.add(table_name)
        for foreign_key in table.foreign_keys:
            target_table = foreign_key.column.table.name
            foreign_keys.add(
                (
                    table_name,
                    foreign_key.parent.name,
                    target_table,
                    foreign_key.column.name,
                )
            )
            pending.append(target_table)
    columns = {
        table_name: frozenset(
            {"id"}
            | {
                foreign_key.parent.name
                for foreign_key in Base.metadata.tables[table_name].foreign_keys
            }
        )
        for table_name in tables
    }
    columns["model_inference_artifacts"] = frozenset(_COLUMNS)
    return columns, frozenset(foreign_keys)


_REQUIRED_TABLE_COLUMNS, _REQUIRED_FOREIGN_KEYS = _parent_schema_requirements()
_REQUIRED_TABLE_COLUMNS = {
    **_REQUIRED_TABLE_COLUMNS,
    "model_inference_artifacts": frozenset((*_COLUMNS, "release_status")),
    "regression_experiments": _REQUIRED_TABLE_COLUMNS["regression_experiments"]
    | frozenset(
        {
            "model_family",
            "feature_pipeline_version",
            "target_version",
            "model_dataset_hash",
            "experiment_configuration_hash",
            "result_hash",
        }
    ),
    "holdout_evaluation_reports": _REQUIRED_TABLE_COLUMNS[
        "holdout_evaluation_reports"
    ]
    | frozenset(
        {
            "selected_experiment_id",
            "validation_run_id",
            "configuration_hash",
            "result_hash",
            "model_dataset_hash",
            "split_hash",
            "holdout_consumed",
            "report_configuration",
            "report_payload",
        }
    ),
    "validation_runs": _REQUIRED_TABLE_COLUMNS["validation_runs"]
    | frozenset({"source_ingestion_batch_id", "source_feature_run_id", "split_hash"}),
}

_REQUIRED_UNIQUE_COLUMNS = frozenset(
    {
        ("artifact_sha256",),
        ("configuration_hash",),
        ("selected_experiment_id",),
    }
)

_REQUIRED_CHECKS = frozenset({"ck_model_inference_artifacts_integrity"})
_RELEASE_MANIFEST_FORMAT = "alphalens-release-manifest/1"
_CLOSURE_FORMAT = "alphalens-approved-parent-closure/1"
_CLOSURE_ROOT_TABLES = (
    "model_inference_artifacts",
    "regression_experiments",
    "holdout_evaluation_reports",
    "validation_runs",
)
_RESTORE_MANIFEST_KEY = "restoration"
_BOOTSTRAP_MANIFEST_KEY = "bootstrap"
_EXPECTED_PRODUCTION_TARGET = {
    "environment": "production",
    "database_name": "railway",
    "database_user": "postgres",
    "host": "127.0.0.1",
    "port": 5432,
    "railway_project": "gallant-creation",
    "railway_project_id": "17e7ec94-2a0b-41ae-9dbb-396763923b05",
    "railway_environment": "production",
    "railway_environment_id": "e76627b5-ba51-49d3-af8f-74d11bb66c07",
    "railway_service": "alphalens",
    "railway_service_url": "https://alphalens-production-b009.up.railway.app",
}
_INGESTION_TABLE = "market_data_ingestion_batches"
_INGESTION_LIFECYCLE_COLUMNS = frozenset({"is_active", "superseded_at"})
_ACTIVE_LINEAGE_TABLES = (
    "market_data_ingestion_batches",
    "feature_pipeline_runs",
    "forward_log_return_target_runs",
    "validation_runs",
)
_APPROVED_ARTIFACT_ID = "a6576881-77d2-4947-a8b6-5b3707d8e76a"
_APPROVED_ARTIFACT_SHA256 = "88644e3d2316f3c0ef99a40761aecabd1206d63f0c39784a6bb2475b07832bcd"
_APPROVED_INGESTION_ID = "28736e3d-86dd-4fe8-9743-e34fa8adf177"
_APPROVED_INGESTION_ROW_SHA256 = "e9aa62533e8b03a9eb56472985e2763a5e82f0faaf7a107a7654c5b1ae3d4511"
_LEGACY_INGESTION_ID = "a453a1ab-bd49-4d65-8612-d351bf639b3b"
_LEGACY_INGESTION_ROW_SHA256 = "8a1d86d3c48495d75bc659e3b90529198e64c0008b991e521439239dd82af49c"
_LEGACY_FEATURE_RUN_ID = "df6ec190-5b99-4b72-b894-eb50ce087c10"
_LEGACY_FEATURE_RUN_ROW_SHA256 = "30943f7222aaacfa7f3dbb8781a65b906d87f458a415c034d8448daf2fca578b"
_LEGACY_VALIDATION_RUN_ID = "f2e941a7-4c9c-4d2a-a095-f09b80eb43d0"
_LEGACY_VALIDATION_RUN_ROW_SHA256 = "5ce7ce2fa6a4f3e5273e6fb492d554630a05ca70accf2a346a480122b733fe17"
_LEGACY_TARGET_RUN_ID = "5d0bf506-71b6-4369-8724-175e33e7f091"
_LEGACY_TARGET_RUN_ROW_SHA256 = "8a4568ee088f321007fa8d79dfcc08b452a8b0c2c2f0ccd0b0799bbd4bf94cd6"
_LEGACY_ARTIFACT_ID = "c288085a-54b6-4fa9-8a87-08f78745c34d"
_LEGACY_ARTIFACT_SHA256 = "e098c2689c4d90f459332d217eb33f05a5f04d1a230325bfb17f0f5de6dd1130"
_HOLDOUT_CONSUMPTION_COLUMNS = (
    "validation_run_id",
    "holdout_evaluation_report_id",
    "selected_experiment_id",
    "purpose",
    "official",
    "irreversible",
    "consumed_at",
)


class TransferPreflightError(ValueError):
    """Raised when approved-state transfer cannot safely proceed."""


def _normalise_host(value: str) -> str:
    return value.split("/", 1)[0]


async def read_target_identity(session) -> dict[str, str | int]:
    row = (
        await session.execute(
            text(
                "SELECT current_database(), current_user, "
                "inet_server_addr()::text, inet_server_port()"
            )
        )
    ).one()
    return {
        "database_name": str(row[0]),
        "database_user": str(row[1]),
        "host": _normalise_host(str(row[2])),
        "port": int(row[3]),
    }


def verify_target_identity(
    actual: dict[str, str | int], expected: dict[str, Any]
) -> None:
    """Fail closed when a later release targets the wrong database."""
    if expected.get("environment") != "production":
        raise TransferPreflightError("Release target must be production.")
    for key in ("database_name", "host", "port"):
        expected_value = expected.get(key)
        actual_value = actual.get(key)
        if key == "host" and isinstance(expected_value, str):
            expected_value = _normalise_host(expected_value)
        if expected_value != actual_value:
            raise TransferPreflightError("Release target identity differs.")


def _validate_release_manifest(
    manifest: dict,
    row: dict,
    target_identity: dict[str, str | int],
) -> None:
    """Require explicit human approval bound to one immutable artifact."""
    if manifest.get("format") != _RELEASE_MANIFEST_FORMAT:
        raise TransferPreflightError("Unrecognized release manifest format.")
    recorded_hash = manifest.get("manifest_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_sha256", None)
    if not isinstance(recorded_hash, str) or hash_json(unsigned) != recorded_hash:
        raise TransferPreflightError("Release manifest hash verification failed.")
    if manifest.get("approved") is not True:
        raise TransferPreflightError("Explicit human release approval is required.")
    if manifest.get("release_action") != "IMPORT_FOR_RELEASE_REVIEW":
        raise TransferPreflightError("Release action is not import-for-review.")
    if not isinstance(manifest.get("approved_by"), str) or not manifest["approved_by"].strip():
        raise TransferPreflightError("Release approver is required.")
    try:
        datetime.fromisoformat(str(manifest["approved_at"]))
    except (KeyError, TypeError, ValueError) as error:
        raise TransferPreflightError("Release approval timestamp is invalid.") from error
    backup = manifest.get("backup")
    rollback = manifest.get("rollback")
    target = manifest.get("target")
    if (
        not isinstance(backup, dict)
        or not backup.get("backup_id")
        or not isinstance(backup.get("sha256"), str)
        or len(backup["sha256"]) != 64
        or not isinstance(rollback, dict)
        or not rollback.get("reference")
        or not isinstance(target, dict)
    ):
        raise TransferPreflightError("Backup, rollback, and target bindings are required.")
    verify_target_identity(target_identity, target)
    artifact = manifest.get("artifact")
    if not isinstance(artifact, dict):
        raise TransferPreflightError("Release artifact binding is required.")
    expected_artifact = {
        "artifact_id": row["id"],
        "artifact_sha256": row["artifact_sha256"],
        "model_family": row["model_family"],
        "artifact_version": row["artifact_version"],
        "configuration_hash": row["configuration_hash"],
        "training_dataset_hash": row["training_dataset_hash"],
        "model_parameters": {
            "alpha": "1.0",
            "fit_intercept": True,
            "solver": "svd",
        },
        "selected_experiment_id": row["selected_experiment_id"],
        "holdout_evaluation_report_id": row["holdout_evaluation_report_id"],
        "validation_run_id": row["validation_run_id"],
        "model_dataset_hash": row["model_dataset_hash"],
        "feature_pipeline_version": row["feature_pipeline_version"],
        "target_version": row["target_version"],
        "split_hash": row["split_hash"],
        "official_prediction_hash": row["official_prediction_hash"],
        "final_training_observation_count": 610,
        "holdout_consumption_status": "official_irreversible_once",
    }
    if any(artifact.get(key) != value for key, value in expected_artifact.items()):
        raise TransferPreflightError("Release artifact binding differs.")


def _validate_bootstrap_manifest(
    manifest: dict,
    artifact: dict,
    closure_document: dict,
    tables: dict[str, list[dict]],
) -> dict[str, Any]:
    """Bind a fresh-target release to its exact approved closure."""
    _validate_canonical_bootstrap_artifact(artifact)
    binding = manifest.get(_BOOTSTRAP_MANIFEST_KEY)
    if not isinstance(binding, dict):
        raise TransferPreflightError("Bootstrap manifest binding is required.")
    expected = {
        "closure_sha256": closure_document.get("closure_sha256"),
        "closure_record_count": closure_document.get("closure_record_count"),
        "closure_records_sha256": hash_json(_closure_record_bindings(tables)),
        "source_schema_heads": sorted(
            str(value) for value in closure_document.get("source_schema_heads", ())
        ),
        "artifact_id": artifact.get("id"),
        "artifact_sha256": artifact.get("artifact_sha256"),
    }
    if any(binding.get(key) != value for key, value in expected.items()):
        raise TransferPreflightError("Bootstrap closure binding differs.")
    return binding


def _validate_replacement_manifest(
    manifest: dict,
    new_row: dict,
    old_record: ModelInferenceArtifactRecord,
) -> None:
    replacement = manifest.get("replacement")
    if not isinstance(replacement, dict):
        raise TransferPreflightError("Replacement binding is required.")
    if (
        replacement.get("old_artifact_id") != str(old_record.id)
        or replacement.get("old_artifact_sha256") != old_record.artifact_sha256
        or replacement.get("new_artifact_id") != new_row["id"]
        or replacement.get("new_artifact_sha256") != new_row["artifact_sha256"]
    ):
        raise TransferPreflightError("Replacement artifact binding differs.")


def _closure_record_bindings(tables: dict[str, list[dict]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "table": table_name,
                "primary_key": row["primary_key"],
                "row_sha256": row["row_sha256"],
            }
            for table_name, rows in tables.items()
            for row in rows
        ),
        key=lambda item: (item["table"], hash_json(item["primary_key"])),
    )


def _historical_active_rows() -> list[dict[str, str]]:
    return [
        {
            "table": _INGESTION_TABLE,
            "id": _LEGACY_INGESTION_ID,
            "row_sha256": _LEGACY_INGESTION_ROW_SHA256,
            "status_after": "INACTIVE",
        },
        {
            "table": "feature_pipeline_runs",
            "id": _LEGACY_FEATURE_RUN_ID,
            "row_sha256": _LEGACY_FEATURE_RUN_ROW_SHA256,
            "status_after": "INACTIVE",
        },
        {
            "table": "forward_log_return_target_runs",
            "id": _LEGACY_TARGET_RUN_ID,
            "row_sha256": _LEGACY_TARGET_RUN_ROW_SHA256,
            "status_after": "INACTIVE",
        },
        {
            "table": "validation_runs",
            "id": _LEGACY_VALIDATION_RUN_ID,
            "row_sha256": _LEGACY_VALIDATION_RUN_ROW_SHA256,
            "status_after": "INACTIVE",
        },
    ]


def _validate_canonical_production_target(manifest: dict) -> None:
    target = manifest.get("target")
    if not isinstance(target, dict) or any(
        target.get(key) != value
        for key, value in _EXPECTED_PRODUCTION_TARGET.items()
    ):
        raise TransferPreflightError(
            "Production-bound manifest target differs from the approved production target."
        )


def _validate_canonical_bootstrap_artifact(artifact: dict) -> None:
    """Bind fresh-target bootstrap to the approved release artifact."""
    if (
        artifact.get("id") != _APPROVED_ARTIFACT_ID
        or artifact.get("artifact_sha256") != _APPROVED_ARTIFACT_SHA256
    ):
        raise TransferPreflightError(
            "Fresh-target bootstrap is bound to an unexpected artifact."
        )


def _build_restore_manifest(
    manifest: dict,
    closure_document: dict,
) -> dict:
    """Derive the combined-restore binding without contacting any database."""
    artifact, tables = _validate_closure_document(closure_document)
    _validate_closure_relationships(tables)
    _validate_canonical_bootstrap_artifact(artifact)
    _validate_canonical_production_target(manifest)
    target = manifest["target"]
    _validate_release_manifest(
        manifest,
        artifact,
        {
            "database_name": target["database_name"],
            "host": target["host"],
            "port": target["port"],
        },
    )
    historical_rows = _historical_active_rows()
    derived = dict(manifest)
    derived["restoration"] = {
        "closure_sha256": closure_document["closure_sha256"],
        "closure_record_count": closure_document["closure_record_count"],
        "closure_records_sha256": hash_json(_closure_record_bindings(tables)),
        "approved_ingestion_batch_id": _APPROVED_INGESTION_ID,
        "approved_ingestion_row_sha256": _APPROVED_INGESTION_ROW_SHA256,
        "legacy_ingestion_batch_id": _LEGACY_INGESTION_ID,
        "legacy_ingestion_row_sha256": _LEGACY_INGESTION_ROW_SHA256,
        "legacy_ingestion_status_after": "INACTIVE",
        "historical_active_rows": historical_rows,
        "historical_active_rows_sha256": hash_json(historical_rows),
        "legacy_artifact_id": _LEGACY_ARTIFACT_ID,
        "legacy_artifact_sha256": _LEGACY_ARTIFACT_SHA256,
        "legacy_artifact_status_after": RETIRED_ARTIFACT_STATUS,
        "active_artifact_id": _APPROVED_ARTIFACT_ID,
        "active_artifact_sha256": _APPROVED_ARTIFACT_SHA256,
    }
    derived.pop("manifest_sha256", None)
    derived["manifest_sha256"] = hash_json(derived)
    _validate_restore_manifest(derived, artifact, closure_document, tables)
    return derived


def _validate_restore_manifest(
    manifest: dict,
    artifact: dict,
    closure_document: dict,
    tables: dict[str, list[dict]],
) -> dict[str, Any]:
    """Bind one combined restore to the exact closure and both old/new rows."""
    binding = manifest.get(_RESTORE_MANIFEST_KEY)
    if not isinstance(binding, dict):
        raise TransferPreflightError("Combined restoration manifest binding is required.")
    if (
        artifact.get("id") != _APPROVED_ARTIFACT_ID
        or artifact.get("artifact_sha256") != _APPROVED_ARTIFACT_SHA256
    ):
        raise TransferPreflightError("Combined restore is bound to an unexpected artifact.")
    ingestion_rows = tables.get(_INGESTION_TABLE, [])
    if len(ingestion_rows) != 1:
        raise TransferPreflightError("Closure must contain exactly one ingestion parent.")
    ingestion = ingestion_rows[0]
    replacement = manifest.get("replacement")
    if not isinstance(replacement, dict):
        raise TransferPreflightError("Artifact replacement binding is required.")
    historical_rows = _historical_active_rows()
    expected = {
        "closure_sha256": closure_document["closure_sha256"],
        "closure_record_count": closure_document["closure_record_count"],
        "closure_records_sha256": hash_json(_closure_record_bindings(tables)),
        "approved_ingestion_batch_id": ingestion["primary_key"]["id"],
        "approved_ingestion_row_sha256": ingestion["row_sha256"],
        "legacy_ingestion_status_after": "INACTIVE",
        "historical_active_rows": historical_rows,
        "historical_active_rows_sha256": hash_json(historical_rows),
        "legacy_artifact_status_after": RETIRED_ARTIFACT_STATUS,
        "active_artifact_id": artifact["id"],
        "active_artifact_sha256": artifact["artifact_sha256"],
    }
    if any(binding.get(key) != value for key, value in expected.items()):
        raise TransferPreflightError("Combined restoration manifest binding differs.")
    if (
        replacement.get("new_artifact_id") != artifact["id"]
        or replacement.get("new_artifact_sha256") != artifact["artifact_sha256"]
        or binding.get("legacy_artifact_id") != replacement.get("old_artifact_id")
        or binding.get("legacy_artifact_sha256")
        != replacement.get("old_artifact_sha256")
    ):
        raise TransferPreflightError("Combined artifact replacement binding differs.")
    if (
        binding.get("legacy_ingestion_batch_id")
        == binding.get("approved_ingestion_batch_id")
    ):
        raise TransferPreflightError("Old and approved ingestion identities must differ.")
    for name in (
        "legacy_ingestion_batch_id",
        "legacy_ingestion_row_sha256",
    ):
        if not isinstance(binding.get(name), str) or not binding[name]:
            raise TransferPreflightError(
                f"Combined restoration manifest is missing {name}."
            )
    if len(binding["legacy_ingestion_row_sha256"]) != 64:
        raise TransferPreflightError("Legacy ingestion row hash is invalid.")
    if binding.get("legacy_artifact_status_after") != RETIRED_ARTIFACT_STATUS:
        raise TransferPreflightError("Legacy artifact must remain RETIRED.")
    if (
        binding.get("approved_ingestion_batch_id") != _APPROVED_INGESTION_ID
        or binding.get("approved_ingestion_row_sha256")
        != _APPROVED_INGESTION_ROW_SHA256
        or binding.get("legacy_ingestion_batch_id") != _LEGACY_INGESTION_ID
        or binding.get("legacy_ingestion_row_sha256")
        != _LEGACY_INGESTION_ROW_SHA256
        or binding.get("historical_active_rows") != historical_rows
        or binding.get("historical_active_rows_sha256")
        != hash_json(historical_rows)
        or binding.get("legacy_artifact_id") != _LEGACY_ARTIFACT_ID
        or binding.get("legacy_artifact_sha256") != _LEGACY_ARTIFACT_SHA256
    ):
        raise TransferPreflightError("Combined restore differs from approved parent/artifact identities.")
    return binding


async def _verify_closure_lineage(
    artifact: dict,
    tables: dict[str, list[dict]],
) -> None:
    """Verify research-to-artifact lineage from the approved closure alone."""
    values = {
        table_name: _closure_values(Base.metadata.tables[table_name], rows[0])
        for table_name, rows in tables.items()
        if table_name != "holdout_consumptions" and len(rows) == 1
    }
    required = (
        "regression_experiments",
        "final_model_selection_reports",
        "holdout_evaluation_reports",
        "validation_runs",
        "holdout_consumptions",
    )
    if any(
        table_name not in tables or len(tables[table_name]) != 1
        for table_name in required
    ):
        raise TransferPreflightError(
            "Approved closure is missing a unique artifact lineage record."
        )
    consumption_table = Base.metadata.tables["holdout_consumptions"]
    consumption = _closure_values(consumption_table, tables["holdout_consumptions"][0])
    selection = values["final_model_selection_reports"]
    experiment = values["regression_experiments"]
    holdout = values["holdout_evaluation_reports"]
    validation = values["validation_runs"]
    try:
        verify_ridge_artifact_lineage(
            artifact=artifact,
            experiment=experiment,
            selection=selection,
            holdout=holdout,
            validation=validation,
            holdout_consumption_count=1,
            artifact_count=1,
            holdout_consumption_verified=(
                consumption["validation_run_id"] == validation["id"]
                and consumption["holdout_evaluation_report_id"] == holdout["id"]
                and consumption["selected_experiment_id"] == experiment["id"]
                and consumption["purpose"] == "official_final_evaluation"
                and consumption["official"] is True
                and consumption["irreversible"] is True
            ),
        )
    except ValueError as error:
        raise TransferPreflightError(str(error)) from error


async def _preflight_restore_release_state(
    session,
    manifest: dict,
    closure_document: dict,
    artifact: dict,
    tables: dict[str, list[dict]],
) -> dict[str, Any]:
    """Perform every restore-release precondition without changing target state."""
    target_identity = await read_target_identity(session)
    _validate_release_manifest(manifest, artifact, target_identity)
    binding = _validate_restore_manifest(manifest, artifact, closure_document, tables)
    await _preflight_schema(session)
    if frozenset(closure_document.get("source_schema_heads", ())) != expected_schema_heads():
        raise TransferPreflightError("Approved closure schema heads are incompatible.")
    _verify_row(artifact)
    await _verify_closure_lineage(artifact, tables)

    artifact_records = (
        await session.scalars(select(ModelInferenceArtifactRecord))
    ).all()
    active_artifacts = [
        record
        for record in artifact_records
        if record.release_status == ACTIVE_ARTIFACT_STATUS
    ]
    if active_artifacts:
        raise TransferPreflightError("Unexpected active inference artifact exists.")
    legacy_id = _uuid(binding["legacy_artifact_id"], "legacy_artifact_id")
    legacy = await session.get(ModelInferenceArtifactRecord, legacy_id)
    if (
        len(artifact_records) != 1
        or legacy is None
        or legacy.artifact_sha256 != binding["legacy_artifact_sha256"]
        or legacy.release_status != RETIRED_ARTIFACT_STATUS
    ):
        raise TransferPreflightError(
            "Expected retired legacy artifact is missing or differs."
        )
    approved_id = _uuid(binding["active_artifact_id"], "active_artifact_id")
    if await session.get(ModelInferenceArtifactRecord, approved_id) is not None:
        raise TransferPreflightError(
            "Approved artifact already exists; controlled restore precondition differs."
        )

    historical_by_table = {
        item["table"]: item for item in binding["historical_active_rows"]
    }
    for table_name in _ACTIVE_LINEAGE_TABLES:
        table = Base.metadata.tables[table_name]
        incoming_rows = tables.get(table_name, [])
        if len(incoming_rows) != 1:
            raise TransferPreflightError(
                f"Closure must contain exactly one row in {table_name}."
            )
        incoming = _closure_values(table, incoming_rows[0])
        predecessor_binding = historical_by_table[table_name]
        predecessor_id = _uuid(predecessor_binding["id"], f"{table_name}.legacy_id")
        active_rows = (
            await session.execute(
                select(table).where(
                    table.c.asset_identifier == incoming["asset_identifier"],
                    table.c.quote_currency == incoming["quote_currency"],
                    table.c.timeframe == incoming["timeframe"],
                    *(
                        (table.c.target_name == incoming["target_name"],)
                        if "target_name" in incoming
                        else ()
                    ),
                    table.c.is_active.is_(True),
                )
            )
        ).mappings().all()
        if len(active_rows) != 1 or active_rows[0]["id"] != predecessor_id:
            raise TransferPreflightError(
                f"Unexpected active predecessor in {table_name}."
            )
        predecessor = dict(active_rows[0])
        if (
            predecessor["superseded_at"] is not None
            or hash_json(_canonical_db_values(table, predecessor))
            != predecessor_binding["row_sha256"]
        ):
            raise TransferPreflightError(
                f"Historical row hash precondition failed in {table_name}."
            )

    for table_name, rows in tables.items():
        table = Base.metadata.tables[table_name]
        for row in rows:
            existing = await _existing_closure_row(session, table, row)
            if existing is not None:
                raise TransferPreflightError(
                    "Conflicting or duplicate approved closure identity exists: "
                    f"{table_name}:{row['primary_key']}"
                )

    return {
        "preconditions": "PASS",
        "target_identity": "PASS",
        "schema": "PASS",
        "ingestion_parent": "PASS",
        "historical_parent": "PASS",
        "legacy_artifact": "PASS",
        "approved_artifact": "PASS",
        "lineage_closure": "PASS",
        "artifact_loader": "PASS",
        "deterministic_integrity": "PASS",
        "manifest": "PASS",
        "conflicts": "NONE",
        "mutation_performed": "NO",
        "production_rows_changed": "NO",
        "schema_heads": sorted(
            str(value)
            for value in (
                await session.execute(text("SELECT version_num FROM alembic_version"))
            ).scalars()
        ),
        "database_name": target_identity["database_name"],
        "host": target_identity["host"],
        "port": target_identity["port"],
        "approved_ingestion_batch_id": binding["approved_ingestion_batch_id"],
        "approved_ingestion_row_sha256": binding["approved_ingestion_row_sha256"],
        "historical_ingestion_batch_id": binding["legacy_ingestion_batch_id"],
        "historical_ingestion_row_sha256": binding["legacy_ingestion_row_sha256"],
        "approved_artifact_id": binding["active_artifact_id"],
        "approved_artifact_sha256": binding["active_artifact_sha256"],
        "legacy_artifact_id": binding["legacy_artifact_id"],
        "legacy_artifact_sha256": binding["legacy_artifact_sha256"],
        "closure_sha256": binding["closure_sha256"],
        "closure_record_count": binding["closure_record_count"],
    }


@dataclass(frozen=True, slots=True)
class SchemaSnapshot:
    heads: frozenset[str]
    tables: frozenset[str]
    columns: dict[str, frozenset[str]]
    foreign_keys: frozenset[tuple[str, str, str, str]]
    unique_columns: frozenset[tuple[str, ...]]
    checks: frozenset[str]


def _serialize(record: ModelInferenceArtifactRecord) -> dict:
    row = {}
    for column in _COLUMNS:
        value = getattr(record, column)
        if column in _DATETIME_COLUMNS:
            value = value.isoformat()
        elif column in _UUID_COLUMNS and value is not None:
            value = str(value)
        row[column] = value
    return row


def _schema_snapshot_sync(sync_session: Any, heads: frozenset[str]) -> SchemaSnapshot:
    inspector = inspect(sync_session.connection())
    tables = frozenset(inspector.get_table_names())
    columns = {
        table: frozenset(item["name"] for item in inspector.get_columns(table))
        for table in _REQUIRED_TABLE_COLUMNS
        if table in tables
    }
    foreign_keys: set[tuple[str, str, str, str]] = set()
    for table in _REQUIRED_TABLE_COLUMNS:
        if table not in tables:
            continue
        for foreign_key in inspector.get_foreign_keys(table):
            referred_table = foreign_key.get("referred_table")
            referred_columns = foreign_key.get("referred_columns") or ()
            constrained_columns = foreign_key.get("constrained_columns") or ()
            if (
                referred_table
                and len(referred_columns) == 1
                and len(constrained_columns) == 1
            ):
                foreign_keys.add(
                    (
                        table,
                        constrained_columns[0],
                        referred_table,
                        referred_columns[0],
                    )
                )
    unique_columns: set[tuple[str, ...]] = set()
    for constraint in inspector.get_unique_constraints(
        "model_inference_artifacts"
    ):
        unique_columns.add(tuple(sorted(constraint.get("column_names") or ())))
    checks = frozenset(
        constraint.get("name")
        for constraint in inspector.get_check_constraints(
            "model_inference_artifacts"
        )
        if constraint.get("name")
    )
    return SchemaSnapshot(
        heads=heads,
        tables=tables,
        columns=columns,
        foreign_keys=frozenset(foreign_keys),
        unique_columns=frozenset(unique_columns),
        checks=checks,
    )


def _validate_schema_snapshot(snapshot: SchemaSnapshot) -> None:
    expected_heads = expected_schema_heads()
    if snapshot.heads != expected_heads:
        raise TransferPreflightError(
            "Destination schema heads are incompatible: "
            f"expected {sorted(expected_heads)}, got {sorted(snapshot.heads)}."
        )
    missing_tables = sorted(set(_REQUIRED_TABLE_COLUMNS) - snapshot.tables)
    if missing_tables:
        raise TransferPreflightError(
            "Destination is missing required tables: "
            + ", ".join(missing_tables)
        )
    missing_columns = {
        table: sorted(columns - snapshot.columns.get(table, frozenset()))
        for table, columns in _REQUIRED_TABLE_COLUMNS.items()
        if columns - snapshot.columns.get(table, frozenset())
    }
    if missing_columns:
        raise TransferPreflightError(
            f"Destination is missing required columns: {missing_columns}"
        )
    missing_foreign_keys = sorted(
        _REQUIRED_FOREIGN_KEYS - snapshot.foreign_keys
    )
    if missing_foreign_keys:
        raise TransferPreflightError(
            f"Destination is missing required foreign keys: {missing_foreign_keys}"
        )
    missing_unique = sorted(
        _REQUIRED_UNIQUE_COLUMNS - snapshot.unique_columns
    )
    if missing_unique:
        raise TransferPreflightError(
            f"Destination is missing required uniqueness constraints: {missing_unique}"
        )
    missing_checks = sorted(_REQUIRED_CHECKS - snapshot.checks)
    if missing_checks:
        raise TransferPreflightError(
            "Destination is missing required integrity checks: "
            + ", ".join(missing_checks)
        )


async def _preflight_schema(session, *, require_lifecycle: bool = True) -> None:
    try:
        heads = frozenset(
            str(value)
            for value in (
                await session.execute(
                    text("SELECT version_num FROM alembic_version")
                )
            ).scalars()
        )
        snapshot = await session.run_sync(
            lambda sync_session: _schema_snapshot_sync(sync_session, heads)
        )
    except (SQLAlchemyError, KeyError) as error:
        raise TransferPreflightError(
            "Destination schema preflight could not be completed."
        ) from error
    if require_lifecycle:
        _validate_schema_snapshot(snapshot)
        return
    source_columns = {
        table: columns - {"release_status"}
        for table, columns in _REQUIRED_TABLE_COLUMNS.items()
    }
    missing_columns = {
        table: sorted(columns - snapshot.columns.get(table, frozenset()))
        for table, columns in source_columns.items()
        if columns - snapshot.columns.get(table, frozenset())
    }
    if missing_columns:
        raise TransferPreflightError(
            f"Source schema is missing required closure columns: {missing_columns}"
        )
    missing_tables = sorted(set(source_columns) - snapshot.tables)
    if missing_tables:
        raise TransferPreflightError(
            "Source schema is missing required closure tables: "
            + ", ".join(missing_tables)
        )
    missing_foreign_keys = sorted(_REQUIRED_FOREIGN_KEYS - snapshot.foreign_keys)
    if missing_foreign_keys:
        raise TransferPreflightError(
            f"Source schema is missing required closure foreign keys: {missing_foreign_keys}"
        )


def _validate_document(document: object) -> list[dict]:
    if not isinstance(document, dict):
        raise TransferPreflightError("Approved-state document must be an object.")
    if document.get("format") != "alphalens-approved-state/1":
        raise TransferPreflightError("Unrecognized approved-state document format.")
    rows = document.get("model_inference_artifacts")
    if not isinstance(rows, list) or not rows or any(
        not isinstance(row, dict) for row in rows
    ):
        raise TransferPreflightError(
            "Approved-state document must contain one or more artifact rows."
        )
    identities = [row.get("id") for row in rows]
    if any(not isinstance(identity, str) for identity in identities):
        raise TransferPreflightError("Every artifact row must have an identity.")
    if len(set(identities)) != len(identities):
        raise TransferPreflightError("Approved-state document contains duplicate artifact identities.")
    hashes = [row.get("artifact_sha256") for row in rows]
    if any(not isinstance(artifact_hash, str) for artifact_hash in hashes):
        raise TransferPreflightError("Every artifact row must have an artifact hash.")
    if len(set(hashes)) != len(hashes):
        raise TransferPreflightError("Approved-state document contains duplicate artifact hashes.")
    for row in rows:
        missing = sorted(set(_COLUMNS) - set(row))
        if missing:
            raise TransferPreflightError(
                "Artifact row is missing required columns: " + ", ".join(missing)
            )
        _verify_row(row)
    return rows


def _verify_row(row: dict) -> None:
    try:
        payload = row["artifact_payload"]
        if hash_json(payload) != row["artifact_sha256"]:
            raise TransferPreflightError(
            f"Artifact {row['id']} failed artifact_sha256 verification."
            )
        if hash_json(payload["core"]) != row["state_sha256"]:
            raise TransferPreflightError(
            f"Artifact {row['id']} failed state_sha256 verification."
            )
        if hash_json(row["verification_evidence"]) != row["verification_evidence_hash"]:
            raise TransferPreflightError(
            f"Artifact {row['id']} failed verification_evidence_hash check."
            )
        load_ridge_inference_artifact(
            payload,
            expected_artifact_sha256=row["artifact_sha256"],
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, TransferPreflightError):
            raise
        raise TransferPreflightError(
            f"Artifact {row.get('id', '<unknown>')} failed structural verification."
        ) from error


def _uuid(value: object, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (AttributeError, ValueError) as error:
        raise TransferPreflightError(
            f"Artifact field {field} is not a valid UUID."
        ) from error


def _required_provenance(row: dict) -> dict[str, str]:
    try:
        core = row["artifact_payload"]["core"]
        provenance = core["provenance"]
    except (KeyError, TypeError) as error:
        raise TransferPreflightError(
            "Artifact provenance is missing from artifact_payload.core."
        ) from error
    if not isinstance(provenance, dict):
        raise TransferPreflightError("Artifact provenance must be an object.")
    required = (
        "selected_experiment_id",
        "experiment_configuration_hash",
        "experiment_result_hash",
        "holdout_evaluation_report_id",
        "holdout_configuration_hash",
        "holdout_result_hash",
        "validation_run_id",
        "split_hash",
        "source_ingestion_batch_id",
        "source_feature_run_id",
        "source_target_run_id",
    )
    missing = [key for key in required if not isinstance(provenance.get(key), str)]
    if missing:
        raise TransferPreflightError(
            "Artifact provenance is missing required fields: "
            + ", ".join(missing)
        )
    return {key: provenance[key] for key in required}


def _validate_semantic_provenance(
    row: dict,
    experiment: RegressionExperimentRecord,
    holdout: HoldoutEvaluationReportRecord,
    validation: ValidationRunRecord,
    selection: object | None = None,
    holdout_consumption_count: int = 1,
    holdout_consumption_verified: bool = False,
) -> None:
    _verify_sources(experiment, holdout)
    payload = row["artifact_payload"]
    core = payload["core"]
    if (
        payload.get("artifact_version") != row["artifact_version"]
        or payload.get("model_family") != row["model_family"]
        or core.get("configuration_hash") != row["configuration_hash"]
        or core.get("dataset_hash") != row["model_dataset_hash"]
        or core.get("training_hash") != row["training_dataset_hash"]
    ):
        raise TransferPreflightError(
            "Artifact payload identity differs from its recorded columns."
        )
    provenance = _required_provenance(row)
    expected = {
        "selected_experiment_id": str(experiment.id),
        "experiment_configuration_hash": experiment.experiment_configuration_hash,
        "experiment_result_hash": experiment.result_hash,
        "holdout_evaluation_report_id": str(holdout.id),
        "holdout_configuration_hash": holdout.configuration_hash,
        "holdout_result_hash": holdout.result_hash,
        "validation_run_id": str(validation.id),
        "split_hash": row["split_hash"],
        "source_ingestion_batch_id": str(experiment.source_ingestion_batch_id),
        "source_feature_run_id": str(experiment.source_feature_run_id),
        "source_target_run_id": str(experiment.source_target_run_id),
    }
    if provenance != expected:
        raise TransferPreflightError(
            "Artifact semantic provenance differs from the referenced parent records."
        )
    if (
        str(row["selected_experiment_id"]) != str(holdout.selected_experiment_id)
        or str(row["validation_run_id"]) != str(holdout.validation_run_id)
        or row["model_dataset_hash"] != holdout.model_dataset_hash
        or row["split_hash"] != holdout.split_hash
        or str(row["validation_run_id"]) != str(validation.id)
        or row["split_hash"] != validation.split_hash
    ):
        raise TransferPreflightError(
            "Artifact parent identity or provenance fields are inconsistent."
        )
    if selection is None:
        selection = type("Selection", (), {
            "selected_model_family": "ridge_regression",
            "selected_experiment_id": experiment.id,
            "validation_run_id": validation.id,
            "model_dataset_hash": row["model_dataset_hash"],
            "feature_pipeline_version": "1.1.0",
            "target_version": "1.0.0",
            "split_hash": row["split_hash"],
        })()
    try:
        verify_ridge_artifact_lineage(
            artifact=row,
            experiment=experiment,
            selection=selection,
            holdout=holdout,
            validation=validation,
            holdout_consumption_count=holdout_consumption_count,
            artifact_count=1,
            holdout_consumption_verified=holdout_consumption_verified,
        )
    except ValueError as error:
        raise TransferPreflightError(str(error)) from error


async def _preflight_parent_closure(session, row: dict) -> None:
    roots = (
        (
            RegressionExperimentRecord,
            _uuid(row["selected_experiment_id"], "selected_experiment_id"),
        ),
        (
            HoldoutEvaluationReportRecord,
            _uuid(row["holdout_evaluation_report_id"], "holdout_evaluation_report_id"),
        ),
        (
            ValidationRunRecord,
            _uuid(row["validation_run_id"], "validation_run_id"),
        ),
    )
    queue = list(roots)
    root_keys = {
        (model.__table__.name, str(identifier))
        for model, identifier in roots
    }
    visited: set[tuple[str, str]] = set()
    records: dict[str, Any] = {}
    missing: list[str] = []
    while queue:
        model, identifier = queue.pop()
        table_name = model.__table__.name
        key = (table_name, str(identifier))
        if key in visited:
            continue
        visited.add(key)
        record = await session.get(model, identifier)
        if record is None:
            missing.append(f"{table_name}:{identifier}")
            continue
        if key in root_keys:
            records[table_name] = record
        for foreign_key in model.__table__.foreign_keys:
            referenced_id = getattr(record, foreign_key.parent.name, None)
            if referenced_id is None:
                continue
            referenced_model = _MODEL_BY_TABLE.get(foreign_key.column.table.name)
            if referenced_model is None:
                raise TransferPreflightError(
                    "Transfer parent closure references an unmapped table: "
                    + foreign_key.column.table.name
                )
            queue.append((referenced_model, referenced_id))
    if missing:
        raise TransferPreflightError(
            "Missing required parent-record dependencies: " + ", ".join(missing)
        )
    experiment = records["regression_experiments"]
    holdout = records["holdout_evaluation_reports"]
    validation = records["validation_runs"]
    selection = await session.get(
        FinalModelSelectionReportRecord,
        holdout.final_model_selection_report_id,
    )
    consumptions = (
        await session.scalars(
            select(HoldoutConsumptionRecord).where(
                HoldoutConsumptionRecord.validation_run_id == validation.id,
                HoldoutConsumptionRecord.holdout_evaluation_report_id == holdout.id,
            )
        )
    ).all()
    if selection is None:
        raise TransferPreflightError("Missing final model selection parent record.")
    _validate_semantic_provenance(
        row,
        experiment,
        holdout,
        validation,
        selection,
        len(consumptions),
        all(
            item.validation_run_id == validation.id
            and item.holdout_evaluation_report_id == holdout.id
            and item.selected_experiment_id == experiment.id
            and
            item.purpose == "official_final_evaluation"
            and item.official
            and item.irreversible
            for item in consumptions
        ),
    )


def _same_artifact(existing: ModelInferenceArtifactRecord, row: dict) -> bool:
    for field in (
        "artifact_version",
        "model_family",
        "artifact_sha256",
        "state_sha256",
        "verification_evidence_hash",
        "configuration_hash",
    ):
        if getattr(existing, field) != row[field]:
            return False
    return all(
        str(getattr(existing, field)) == str(row[field])
        for field in (
            "selected_experiment_id",
            "holdout_evaluation_report_id",
            "validation_run_id",
        )
    )


async def _preflight_existing(
    session, row: dict
) -> bool:
    existing = await session.get(ModelInferenceArtifactRecord, _uuid(row["id"], "id"))
    if existing is None:
        return False
    if not _same_artifact(existing, row):
        raise TransferPreflightError(
            "Artifact ID/hash conflict: an existing artifact has the same ID "
            "with different canonical content or provenance."
        )
    return True


async def _preflight_import(session, rows: list[dict]) -> list[bool]:
    await _preflight_schema(session)
    active = (
        await session.scalars(
            select(ModelInferenceArtifactRecord).where(
                ModelInferenceArtifactRecord.release_status
                == ACTIVE_ARTIFACT_STATUS
            )
        )
    ).all()
    existing: list[bool] = []
    for row in rows:
        await _preflight_parent_closure(session, row)
        if active and any(
            item.id != _uuid(row["id"], "id") for item in active
        ):
            raise TransferPreflightError(
                "An active artifact already exists; use the replacement operation."
            )
        existing.append(await _preflight_existing(session, row))
    return existing


def _record_from_row(row: dict, *, release_status: str) -> ModelInferenceArtifactRecord:
    values = {
        column: (
            datetime.fromisoformat(row[column])
            if column in _DATETIME_COLUMNS
            else _uuid(row[column], column)
            if column in _UUID_COLUMNS
            else row[column]
        )
        for column in _COLUMNS
    }
    values["release_status"] = release_status
    return ModelInferenceArtifactRecord(**values)


def _json_value(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return {"__alphalens_type__": "decimal", "value": str(value)}
    if isinstance(value, bytes):
        return {
            "__alphalens_type__": "bytes",
            "value": value.hex(),
        }
    return value


def _restore_value(column: Any, value: object) -> object:
    python_type = getattr(column.type, "python_type", None)
    if (
        isinstance(value, dict)
        and value.get("__alphalens_type__") == "sql_null"
        and isinstance(column.type, JSONB)
    ):
        return null()
    if isinstance(value, dict) and value.get("__alphalens_type__") == "decimal":
        return Decimal(str(value["value"]))
    if isinstance(value, dict) and value.get("__alphalens_type__") == "bytes":
        return bytes.fromhex(str(value["value"]))
    if isinstance(value, str) and python_type is datetime:
        return datetime.fromisoformat(value)
    if isinstance(value, str) and python_type is date:
        return date.fromisoformat(value)
    if isinstance(value, str) and python_type is UUID:
        return UUID(value)
    if isinstance(value, dict) and python_type is Decimal:
        return Decimal(str(value["value"]))
    return value


def _canonical_db_values(table: Any, mapping: dict[str, object]) -> dict[str, object]:
    return {
        column.name: (
            {"__alphalens_type__": "sql_null"}
            if mapping[column.name] is None and isinstance(column.type, JSONB)
            else _json_value(mapping[column.name])
        )
        for column in table.columns
        if column.name in mapping
    }


def _row_identity(table: Any, mapping: dict[str, object]) -> dict[str, object]:
    primary_key = tuple(column.name for column in table.primary_key.columns)
    if not primary_key or any(mapping.get(name) is None for name in primary_key):
        raise TransferPreflightError(
            f"Closure table {table.name} has no complete primary-key identity."
        )
    return {name: _json_value(mapping[name]) for name in primary_key}


def _closure_row(table: Any, mapping: dict[str, object]) -> dict[str, object]:
    values = _canonical_db_values(table, mapping)
    return {
        "primary_key": _row_identity(table, mapping),
        "values": values,
        "row_sha256": hash_json(values),
    }


def _closure_rows_hash(table: Any, rows: list[dict[str, object]]) -> str:
    return hash_json(
        {
            "table": table.name,
            "rows": sorted(rows, key=lambda row: hash_json(row)),
        }
    )


def _closure_table_order(table_names: set[str]) -> tuple[str, ...]:
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(table_name: str) -> None:
        if table_name in visited:
            return
        if table_name in visiting:
            raise TransferPreflightError("Closure foreign-key graph contains a cycle.")
        visiting.add(table_name)
        table = Base.metadata.tables[table_name]
        for foreign_key in table.foreign_keys:
            parent = foreign_key.column.table.name
            if parent in table_names and parent != table_name:
                visit(parent)
        visiting.remove(table_name)
        visited.add(table_name)
        ordered.append(table_name)

    for table_name in sorted(table_names):
        visit(table_name)
    return tuple(ordered)


def _validate_closure_document(document: object) -> tuple[dict, dict[str, list[dict]]]:
    if not isinstance(document, dict) or document.get("format") != _CLOSURE_FORMAT:
        raise TransferPreflightError("Unrecognized approved parent-closure format.")
    recorded_hash = document.get("closure_sha256")
    unsigned = dict(document)
    unsigned.pop("closure_sha256", None)
    if not isinstance(recorded_hash, str) or hash_json(unsigned) != recorded_hash:
        raise TransferPreflightError("Parent-closure hash verification failed.")
    tables = document.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise TransferPreflightError("Parent closure must contain persisted tables.")
    normalized: dict[str, list[dict]] = {}
    identities: set[tuple[str, str]] = set()
    for table_name, table_rows in tables.items():
        if table_name not in Base.metadata.tables or not isinstance(table_rows, list):
            raise TransferPreflightError(f"Invalid closure table: {table_name}.")
        table = Base.metadata.tables[table_name]
        normalized[table_name] = []
        for row in table_rows:
            if not isinstance(row, dict) or not isinstance(row.get("values"), dict):
                raise TransferPreflightError(f"Invalid closure row in {table_name}.")
            values = row["values"]
            if row.get("row_sha256") != hash_json(values):
                raise TransferPreflightError(
                    f"Closure row hash verification failed in {table_name}."
                )
            primary_key = row.get("primary_key")
            if table_name == "holdout_consumptions":
                expected_key = {
                    name: values.get(name) for name in _HOLDOUT_CONSUMPTION_COLUMNS[:3]
                }
            else:
                expected_key = {
                    column.name: values.get(column.name)
                    for column in table.primary_key.columns
                }
            if primary_key != expected_key:
                raise TransferPreflightError(
                    f"Closure primary-key identity differs in {table_name}."
                )
            identity = (table_name, hash_json(primary_key))
            if identity in identities:
                raise TransferPreflightError(
                    f"Duplicate closure identity in {table_name}."
                )
            identities.add(identity)
            normalized[table_name].append(row)
    artifact = document.get("artifact")
    if not isinstance(artifact, dict):
        raise TransferPreflightError("Parent closure must include its artifact row.")
    _validate_document(
        {"format": "alphalens-approved-state/1", "model_inference_artifacts": [artifact]}
    )
    artifact_rows = tables.get("model_inference_artifacts", [])
    if len(artifact_rows) != 1:
        raise TransferPreflightError(
            "Parent closure must contain exactly one artifact table row."
        )
    artifact_values = artifact_rows[0]["values"]
    if any(artifact_values.get(column) != artifact.get(column) for column in _COLUMNS):
        raise TransferPreflightError(
            "Parent-closure artifact row differs from its canonical artifact document."
        )
    expected_count = sum(len(rows) for rows in normalized.values())
    if document.get("closure_record_count") != expected_count:
        raise TransferPreflightError("Parent-closure record count differs.")
    if document.get("artifact_id") != artifact["id"]:
        raise TransferPreflightError("Parent-closure artifact identity differs.")
    return artifact, normalized


async def _fetch_table_row(
    session,
    table: Any,
    identity: dict[str, object],
    column_names: frozenset[str] | None = None,
) -> dict[str, object]:
    predicates = []
    for column_name, value in identity.items():
        column = table.c.get(column_name)
        if column is None:
            raise TransferPreflightError(
                f"Closure identity references unknown column {table.name}.{column_name}."
            )
        predicates.append(column == _restore_value(column, value))
    selected_columns = [
        column
        for column in table.columns
        if column_names is None or column.name in column_names
    ]
    result = await session.execute(
        select(*selected_columns).where(and_(*predicates))
    )
    rows = result.mappings().all()
    if len(rows) != 1:
        raise TransferPreflightError(
            f"Closure record {table.name}:{identity} is missing or ambiguous."
        )
    return dict(rows[0])


async def _build_parent_closure(session, artifact: dict) -> dict:
    tables: dict[str, dict[str, dict[str, object]]] = {}
    queue: list[tuple[str, dict[str, object]]] = []
    artifact_table = Base.metadata.tables["model_inference_artifacts"]
    queue.append(("model_inference_artifacts", {"id": artifact["id"]}))
    queue.extend(
        (
            table_name,
            {"id": artifact[field]},
        )
        for table_name, field in (
            ("regression_experiments", "selected_experiment_id"),
            ("holdout_evaluation_reports", "holdout_evaluation_report_id"),
            ("validation_runs", "validation_run_id"),
        )
    )
    while queue:
        table_name, identity = queue.pop()
        table = Base.metadata.tables[table_name]
        table_records = tables.setdefault(table_name, {})
        identity_hash = hash_json(identity)
        if identity_hash in table_records:
            continue
        mapping = await _fetch_table_row(
            session,
            table,
            identity,
            frozenset(_COLUMNS) if table_name == "model_inference_artifacts" else None,
        )
        table_records[identity_hash] = mapping
        for foreign_key in table.foreign_keys:
            value = mapping.get(foreign_key.parent.name)
            if value is not None:
                queue.append(
                    (
                        foreign_key.column.table.name,
                        {foreign_key.column.name: _json_value(value)},
                    )
                )

    consumption_table = Base.metadata.tables["holdout_consumptions"]
    consumption_rows = (
        await session.execute(
            select(consumption_table).where(
                and_(
                    consumption_table.c.validation_run_id == UUID(artifact["validation_run_id"]),
                    consumption_table.c.holdout_evaluation_report_id
                    == UUID(artifact["holdout_evaluation_report_id"]),
                )
            )
        )
    ).mappings().all()
    if len(consumption_rows) != 1:
        raise TransferPreflightError(
            "Approved artifact must have exactly one holdout consumption record."
        )
    tables["holdout_consumptions"] = {
        hash_json(
            {
                name: _json_value(row[name])
                for name in _HOLDOUT_CONSUMPTION_COLUMNS[:3]
            }
        ): dict(row)
        for row in consumption_rows
    }

    serialized: dict[str, list[dict]] = {}
    for table_name, records in tables.items():
        table = Base.metadata.tables[table_name]
        if table_name == "holdout_consumptions":
            serialized[table_name] = [
                {
                    "primary_key": {
                        name: _json_value(row[name])
                        for name in _HOLDOUT_CONSUMPTION_COLUMNS[:3]
                    },
                    "values": {
                        name: _json_value(row[name]) for name in _HOLDOUT_CONSUMPTION_COLUMNS
                    },
                    "row_sha256": hash_json(
                        {name: _json_value(row[name]) for name in _HOLDOUT_CONSUMPTION_COLUMNS}
                    ),
                }
                for row in records.values()
            ]
        else:
            serialized[table_name] = [
                _closure_row(table, row) for row in records.values()
            ]
    artifact_mapping = tables["model_inference_artifacts"][hash_json({"id": artifact["id"]})]
    artifact_values = _canonical_db_values(artifact_table, artifact_mapping)
    artifact_row = {
        name: artifact_values[name]
        for name in _COLUMNS
        if name in artifact_values
    }
    _validate_document(
        {"format": "alphalens-approved-state/1", "model_inference_artifacts": [artifact_row]}
    )
    closure = {
        "format": _CLOSURE_FORMAT,
        "artifact_id": artifact_row["id"],
        "artifact": artifact_row,
        "source_schema_heads": sorted(
            str(value)
            for value in (
                await session.execute(text("SELECT version_num FROM alembic_version"))
            ).scalars()
        ),
        "tables": {
            table_name: sorted(rows, key=lambda row: hash_json(row))
            for table_name, rows in sorted(serialized.items())
        },
    }
    closure["closure_record_count"] = sum(
        len(rows) for rows in closure["tables"].values()
    )
    closure["closure_sha256"] = hash_json(closure)
    return closure


def _closure_values(table: Any, row: dict) -> dict[str, object]:
    return {
        column.name: _restore_value(column, row["values"][column.name])
        for column in table.columns
        if column.name in row["values"]
    }


def _closure_identity(table_name: str, row: dict) -> dict[str, object]:
    if table_name == "holdout_consumptions":
        return {
            name: row["primary_key"][name]
            for name in _HOLDOUT_CONSUMPTION_COLUMNS[:3]
        }
    return dict(row["primary_key"])


def _validate_closure_relationships(tables: dict[str, list[dict]]) -> None:
    identities = {
        (table_name, hash_json(_closure_identity(table_name, row)))
        for table_name, rows in tables.items()
        for row in rows
    }
    for table_name, rows in tables.items():
        if table_name == "holdout_consumptions":
            continue
        table = Base.metadata.tables[table_name]
        for row in rows:
            values = row["values"]
            for foreign_key in table.foreign_keys:
                value = values.get(foreign_key.parent.name)
                if value is None:
                    continue
                target_identity = {
                    foreign_key.column.name: value,
                }
                if (
                    foreign_key.column.table.name,
                    hash_json(target_identity),
                ) not in identities:
                    raise TransferPreflightError(
                        "Parent closure omits a referenced record: "
                        f"{table_name}.{foreign_key.parent.name}."
                    )


async def _existing_closure_row(session, table: Any, row: dict) -> dict | None:
    identity = _closure_identity(table.name, row)
    if table.name == "holdout_consumptions":
        predicates = [
            table.c[name] == _restore_value(table.c[name], value)
            for name, value in identity.items()
        ]
    else:
        predicates = [
            table.c[name] == _restore_value(table.c[name], value)
            for name, value in identity.items()
        ]
    existing = (await session.execute(select(table).where(and_(*predicates)))).mappings().all()
    if len(existing) > 1:
        raise TransferPreflightError(
            f"Target contains duplicate closure identity {table.name}:{identity}."
        )
    return dict(existing[0]) if existing else None


def _same_closure_row(table: Any, existing: dict, row: dict) -> bool:
    incoming = row["values"]
    existing_values = _canonical_db_values(table, existing)
    for column in table.columns:
        if column.name == "release_status" and table.name == "model_inference_artifacts":
            continue
        if column.name not in incoming:
            return False
        if existing_values.get(column.name) != incoming[column.name]:
            return False
    return True


async def _export_closure(
    url: str,
    input_path: str,
    output_path: str,
) -> int:
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    with open(input_path, encoding="utf-8") as handle:
        document = json.load(handle)
    rows = _validate_document(document)
    if len(rows) != 1:
        raise TransferPreflightError("Closure export requires exactly one artifact row.")
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            await _preflight_schema(session, require_lifecycle=False)
            artifact_table = Base.metadata.tables["model_inference_artifacts"]
            mapping = await _fetch_table_row(
                session,
                artifact_table,
                {"id": rows[0]["id"]},
                frozenset(_COLUMNS),
            )
            source_artifact = {
                name: _json_value(mapping[name])
                for name in _COLUMNS
                if name in mapping
            }
            _validate_document(
                {
                    "format": "alphalens-approved-state/1",
                    "model_inference_artifacts": [source_artifact],
                }
            )
            if source_artifact["artifact_sha256"] != rows[0]["artifact_sha256"]:
                raise TransferPreflightError("Source artifact hash differs from approved payload.")
            await _preflight_parent_closure(session, source_artifact)
            closure = await _build_parent_closure(session, source_artifact)
    finally:
        await engine.dispose()
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(closure, handle, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "status": "closure_exported",
                "artifact_id": closure["artifact_id"],
                "artifact_sha256": source_artifact["artifact_sha256"],
                "closure_record_count": closure["closure_record_count"],
                "closure_sha256": closure["closure_sha256"],
                "output": output_path,
            },
            sort_keys=True,
        )
    )
    return 0


async def _import_closure(
    url: str,
    input_path: str,
    manifest_path: str,
) -> int:
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    with open(input_path, encoding="utf-8") as handle:
        document = json.load(handle)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    artifact, tables = _validate_closure_document(document)
    _validate_closure_relationships(tables)
    engine = create_async_engine(url)
    inserted = 0
    skipped = 0
    try:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            async with session.begin():
                target_identity = await read_target_identity(session)
                _validate_release_manifest(manifest, artifact, target_identity)
                await _preflight_schema(session)
                for table_name in _closure_table_order(set(tables)):
                    table = Base.metadata.tables[table_name]
                    for row in tables[table_name]:
                        existing = await _existing_closure_row(session, table, row)
                        if existing is not None:
                            if not _same_closure_row(table, existing, row):
                                raise TransferPreflightError(
                                    "Conflicting parent identity/hash exists in target: "
                                    f"{table_name}:{row['primary_key']}"
                                )
                            skipped += 1
                            continue
                        values = _closure_values(table, row)
                        if table_name == "model_inference_artifacts":
                            values["release_status"] = RETIRED_ARTIFACT_STATUS
                        await session.execute(table.insert().values(values))
                        inserted += 1
                await session.flush()
                await _preflight_parent_closure(session, artifact)
                staged = await _existing_closure_row(
                    session,
                    Base.metadata.tables["model_inference_artifacts"],
                    tables["model_inference_artifacts"][0],
                )
                if staged is None or staged.get("release_status") != RETIRED_ARTIFACT_STATUS:
                    raise TransferPreflightError(
                        "Approved artifact was not staged as RETIRED."
                    )
    finally:
        await engine.dispose()
    print(
        json.dumps(
            {
                "status": "closure_imported",
                "artifact_id": artifact["id"],
                "artifact_sha256": artifact["artifact_sha256"],
                "closure_sha256": document["closure_sha256"],
                "rows_inserted": inserted,
                "rows_skipped_existing": skipped,
                "activation": "not_performed",
            },
            sort_keys=True,
        )
    )
    return 0


async def _bootstrap_release(
    url: str,
    closure_path: str,
    manifest_path: str,
) -> int:
    """Atomically initialize an empty production target with approved state.

    This is the fresh-target counterpart to ``restore-release``.  It inserts
    the complete approved parent closure and activates the approved artifact
    in one transaction.  It never generates or changes artifact content and
    refuses any target that already contains a closure row or artifact.
    """
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    with open(closure_path, encoding="utf-8") as handle:
        closure_document = json.load(handle)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    artifact, tables = _validate_closure_document(closure_document)
    _validate_closure_relationships(tables)
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            async with session.begin():
                target_identity = await read_target_identity(session)
                _validate_release_manifest(manifest, artifact, target_identity)
                _validate_bootstrap_manifest(
                    manifest, artifact, closure_document, tables
                )
                await _preflight_schema(session)
                if frozenset(closure_document.get("source_schema_heads", ())) != expected_schema_heads():
                    raise TransferPreflightError(
                        "Approved closure schema heads are incompatible."
                    )
                await _verify_closure_lineage(artifact, tables)
                existing_artifacts = (
                    await session.scalars(select(ModelInferenceArtifactRecord))
                ).all()
                existing_rows = []
                for table_name, rows in tables.items():
                    table = Base.metadata.tables[table_name]
                    for row in rows:
                        existing = await _existing_closure_row(session, table, row)
                        if existing is not None:
                            existing_rows.append((table, existing, row))
                if existing_artifacts or existing_rows:
                    exact_existing_state = (
                        len(existing_artifacts) == 1
                        and _same_artifact(existing_artifacts[0], artifact)
                        and existing_artifacts[0].release_status
                        == ACTIVE_ARTIFACT_STATUS
                        and len(existing_rows) == closure_document["closure_record_count"]
                        and all(
                            _same_closure_row(table, existing, row)
                            for table, existing, row in existing_rows
                        )
                    )
                    if not exact_existing_state:
                        raise TransferPreflightError(
                            "Fresh-target bootstrap found a partial or conflicting release state."
                        )
                    await _preflight_parent_closure(session, artifact)
                    loaded = await load_production_artifact(session)
                    if (
                        loaded.artifact_id != _uuid(artifact["id"], "artifact.id")
                        or loaded.artifact_sha256 != artifact["artifact_sha256"]
                    ):
                        raise TransferPreflightError(
                            "Existing bootstrap state failed post-load verification."
                        )
                    result_status = "already_bootstrapped"
                else:
                    for table_name in _closure_table_order(set(tables)):
                        table = Base.metadata.tables[table_name]
                        for row in tables[table_name]:
                            values = _closure_values(table, row)
                            if table_name == "model_inference_artifacts":
                                values["release_status"] = ACTIVE_ARTIFACT_STATUS
                            await session.execute(table.insert().values(values))
                    result_status = "bootstrapped"
                await session.flush()
                if result_status == "bootstrapped":
                    _verify_row(artifact)
                    await _preflight_parent_closure(session, artifact)
                    loaded = await load_production_artifact(session)
                if (
                    loaded.artifact_id != _uuid(artifact["id"], "artifact.id")
                    or loaded.artifact_sha256 != artifact["artifact_sha256"]
                ):
                    raise TransferPreflightError(
                        "Bootstrapped production artifact failed post-insert verification."
                    )
                result = {
                    "status": result_status,
                    "schema_heads": sorted(
                        str(value)
                        for value in (
                            await session.execute(
                                text("SELECT version_num FROM alembic_version")
                            )
                        ).scalars()
                    ),
                    "artifact_id": str(loaded.artifact_id),
                    "artifact_sha256": loaded.artifact_sha256,
                    "closure_sha256": closure_document["closure_sha256"],
                    "closure_record_count": closure_document["closure_record_count"],
                    "active_artifact_count": 1,
                    "lineage": "PASS",
                    "loader": "PASS",
                }
    finally:
        await engine.dispose()
    print(json.dumps(result, sort_keys=True))
    return 0


async def _verify_restored_state(
    session,
    manifest: dict,
    closure_document: dict,
    artifact: dict,
    tables: dict[str, list[dict]],
) -> dict[str, Any]:
    """Read-only verification shared by restore commit and verify-restore."""
    binding = _validate_restore_manifest(manifest, artifact, closure_document, tables)
    await _preflight_schema(session)
    ingestion_table = Base.metadata.tables[_INGESTION_TABLE]
    approved_id = _uuid(binding["approved_ingestion_batch_id"], "approved_ingestion_batch_id")
    legacy_id = _uuid(binding["legacy_ingestion_batch_id"], "legacy_ingestion_batch_id")
    ingestion_rows = (
        await session.execute(
            select(ingestion_table).where(
                ingestion_table.c.id.in_((approved_id, legacy_id))
            )
        )
    ).mappings().all()
    by_id = {row["id"]: dict(row) for row in ingestion_rows}
    if len(by_id) != 2 or approved_id not in by_id or legacy_id not in by_id:
        raise TransferPreflightError("Expected approved and historical ingestion rows are required.")
    approved_ingestion = by_id[approved_id]
    if not approved_ingestion["is_active"] or not _same_closure_row(
        ingestion_table, approved_ingestion, tables[_INGESTION_TABLE][0]
    ):
        raise TransferPreflightError("Approved ingestion row is not exact and active.")
    legacy_ingestion = by_id[legacy_id]
    legacy_canonical = _canonical_db_values(ingestion_table, legacy_ingestion)
    legacy_canonical["is_active"] = True
    legacy_canonical["superseded_at"] = None
    if (
        legacy_ingestion["is_active"]
        or legacy_ingestion["superseded_at"] is None
        or hash_json(legacy_canonical) != binding["legacy_ingestion_row_sha256"]
    ):
        raise TransferPreflightError("Historical ingestion row identity or content differs.")
    active_ingestions = (
        await session.execute(
            select(ingestion_table.c.id).where(
                ingestion_table.c.asset_identifier
                == approved_ingestion["asset_identifier"],
                ingestion_table.c.quote_currency
                == approved_ingestion["quote_currency"],
                ingestion_table.c.timeframe == approved_ingestion["timeframe"],
                ingestion_table.c.is_active.is_(True),
            )
        )
    ).scalars().all()
    if active_ingestions != [approved_id]:
        raise TransferPreflightError("Active ingestion parent set differs from approved state.")

    for table_name in _ACTIVE_LINEAGE_TABLES[1:]:
        table = Base.metadata.tables[table_name]
        approved_rows = tables.get(table_name, [])
        if len(approved_rows) != 1:
            raise TransferPreflightError(
                f"Closure must contain exactly one active {table_name} row."
            )
        approved_values = _closure_values(table, approved_rows[0])
        approved_parent_id = approved_values["id"]
        approved_parent = (
            await session.execute(
                select(table).where(table.c.id == approved_parent_id)
            )
        ).mappings().first()
        if (
            approved_parent is None
            or not approved_parent["is_active"]
            or not _same_closure_row(table, dict(approved_parent), approved_rows[0])
        ):
            raise TransferPreflightError(
                f"Approved active row differs in {table_name}."
            )
        active_parents = (
            await session.execute(
                select(table.c.id).where(
                    table.c.asset_identifier == approved_values["asset_identifier"],
                    table.c.quote_currency == approved_values["quote_currency"],
                    table.c.timeframe == approved_values["timeframe"],
                    *(
                        (table.c.target_name == approved_values["target_name"],)
                        if "target_name" in approved_values
                        else ()
                    ),
                    table.c.is_active.is_(True),
                )
            )
        ).scalars().all()
        if active_parents != [approved_parent_id]:
            raise TransferPreflightError(
                f"Active logical parent set differs in {table_name}."
            )

    for historical in binding["historical_active_rows"]:
        table = Base.metadata.tables[historical["table"]]
        historical_id = _uuid(historical["id"], f"{historical['table']}.id")
        row = (
            await session.execute(
                select(table).where(table.c.id == historical_id)
            )
        ).mappings().first()
        if row is None or row["is_active"] or row["superseded_at"] is None:
            raise TransferPreflightError(
                f"Historical active row was not preserved: {historical['table']}:{historical['id']}"
            )
        original = _canonical_db_values(table, dict(row))
        original["is_active"] = True
        original["superseded_at"] = None
        if hash_json(original) != historical["row_sha256"]:
            raise TransferPreflightError(
                f"Historical row hash differs: {historical['table']}:{historical['id']}"
            )

    for table_name, rows in tables.items():
        table = Base.metadata.tables[table_name]
        for row in rows:
            existing = await _existing_closure_row(session, table, row)
            if existing is None or not _same_closure_row(table, existing, row):
                raise TransferPreflightError(
                    f"Restored closure row is missing or differs: {table_name}:{row['primary_key']}"
                )

    artifact_rows = (
        await session.scalars(select(ModelInferenceArtifactRecord))
    ).all()
    expected_old_id = _uuid(manifest["replacement"]["old_artifact_id"], "replacement.old_artifact_id")
    approved_artifact_id = _uuid(artifact["id"], "artifact.id")
    if {record.id for record in artifact_rows} != {expected_old_id, approved_artifact_id}:
        raise TransferPreflightError("Unexpected inference artifact rows exist.")
    old_record = await session.get(ModelInferenceArtifactRecord, expected_old_id)
    active_artifacts = [
        record for record in artifact_rows
        if record.release_status == ACTIVE_ARTIFACT_STATUS
    ]
    if (
        old_record is None
        or old_record.artifact_sha256 != binding.get("legacy_artifact_sha256")
        or old_record.release_status != RETIRED_ARTIFACT_STATUS
        or len(active_artifacts) != 1
        or active_artifacts[0].id != approved_artifact_id
        or not _same_artifact(active_artifacts[0], artifact)
    ):
        raise TransferPreflightError("Final artifact identity or lifecycle state differs.")
    await _preflight_parent_closure(session, artifact)
    _verify_row(artifact)
    loaded = await load_production_artifact(session)
    if (
        loaded.artifact_id != approved_artifact_id
        or loaded.artifact_sha256 != artifact["artifact_sha256"]
    ):
        raise TransferPreflightError("Production artifact loader verification failed.")
    return {
        "schema_heads": sorted(
            str(value)
            for value in (
                await session.execute(text("SELECT version_num FROM alembic_version"))
            ).scalars()
        ),
        "artifact_id": str(loaded.artifact_id),
        "artifact_sha256": loaded.artifact_sha256,
        "active_artifact_count": len(active_artifacts),
        "legacy_artifact_id": str(expected_old_id),
        "legacy_artifact_status": old_record.release_status,
        "approved_ingestion_batch_id": str(approved_id),
        "historical_ingestion_batch_id": str(legacy_id),
        "closure_sha256": closure_document["closure_sha256"],
        "closure_record_count": closure_document["closure_record_count"],
        "lineage": "PASS",
        "integrity_and_replay_evidence": "PASS",
        "loader": "PASS",
    }


async def _restore_release_transaction(
    session,
    manifest: dict,
    closure_document: dict,
    artifact: dict,
    tables: dict[str, list[dict]],
    *,
    failure_point: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Restore ingestion lineage, closure, and artifact in one transaction."""
    async with session.begin():
        target_identity = await read_target_identity(session)
        _validate_release_manifest(manifest, artifact, target_identity)
        binding = _validate_restore_manifest(manifest, artifact, closure_document, tables)
        await _preflight_schema(session)

        ingestion_table = Base.metadata.tables[_INGESTION_TABLE]
        approved_row = tables[_INGESTION_TABLE][0]
        approved_values = _closure_values(ingestion_table, approved_row)
        approved_id = approved_values["id"]
        approved_existing = (
            await session.execute(
                select(ingestion_table)
                .where(ingestion_table.c.id == approved_id)
                .with_for_update()
            )
        ).mappings().first()
        if approved_existing is not None:
            result = await _verify_restored_state(
                session, manifest, closure_document, artifact, tables
            )
            return "already_restored", result

        active_artifacts = (
            await session.scalars(
                select(ModelInferenceArtifactRecord)
                .where(ModelInferenceArtifactRecord.release_status == ACTIVE_ARTIFACT_STATUS)
                .with_for_update()
            )
        ).all()
        if active_artifacts:
            raise TransferPreflightError("Unexpected active inference artifact exists.")
        expected_old_artifact_id = _uuid(
            manifest["replacement"]["old_artifact_id"],
            "replacement.old_artifact_id",
        )
        expected_old_artifact = await session.get(
            ModelInferenceArtifactRecord,
            expected_old_artifact_id,
            with_for_update=True,
        )
        if (
            expected_old_artifact is None
            or expected_old_artifact.artifact_sha256
            != binding["legacy_artifact_sha256"]
            or expected_old_artifact.release_status != RETIRED_ARTIFACT_STATUS
        ):
            raise TransferPreflightError(
                "Expected retired legacy artifact is missing or differs."
            )

        historical_by_table = {
            item["table"]: item for item in binding["historical_active_rows"]
        }
        predecessors: dict[str, dict[str, Any]] = {}
        for table_name in _ACTIVE_LINEAGE_TABLES:
            table = Base.metadata.tables[table_name]
            incoming_rows = tables.get(table_name, [])
            if len(incoming_rows) != 1:
                raise TransferPreflightError(
                    f"Closure must contain exactly one row in {table_name}."
                )
            incoming = incoming_rows[0]
            values = _closure_values(table, incoming)
            if values.get("is_active") is not True:
                raise TransferPreflightError(
                    f"Approved closure parent must be active in {table_name}."
                )
            predecessor_binding = historical_by_table[table_name]
            old_id = _uuid(predecessor_binding["id"], f"{table_name}.legacy_id")
            active_rows = (
                await session.execute(
                    select(table)
                    .where(
                        table.c.asset_identifier == values["asset_identifier"],
                        table.c.quote_currency == values["quote_currency"],
                        table.c.timeframe == values["timeframe"],
                        *(
                            (table.c.target_name == values["target_name"],)
                            if "target_name" in values
                            else ()
                        ),
                        table.c.is_active.is_(True),
                    )
                    .with_for_update()
                )
            ).mappings().all()
            if len(active_rows) != 1 or active_rows[0]["id"] != old_id:
                raise TransferPreflightError(
                    f"Unexpected active predecessor in {table_name}."
                )
            predecessor = dict(active_rows[0])
            if hash_json(_canonical_db_values(table, predecessor)) != predecessor_binding[
                "row_sha256"
            ]:
                raise TransferPreflightError(
                    f"Historical row hash precondition failed in {table_name}."
                )
            predecessors[table_name] = predecessor

        for table_name in _ACTIVE_LINEAGE_TABLES:
            table = Base.metadata.tables[table_name]
            predecessor = predecessors[table_name]
            await session.execute(
                table.update()
                .where(table.c.id == predecessor["id"])
                .values(is_active=False, superseded_at=func.now())
            )
            preserved = (
                await session.execute(
                    select(table).where(table.c.id == predecessor["id"])
                )
            ).mappings().one()
            before_immutable = {
                key: value
                for key, value in _canonical_db_values(table, predecessor).items()
                if key not in _INGESTION_LIFECYCLE_COLUMNS
            }
            after_immutable = {
                key: value
                for key, value in _canonical_db_values(table, dict(preserved)).items()
                if key not in _INGESTION_LIFECYCLE_COLUMNS
            }
            if after_immutable != before_immutable or preserved["is_active"]:
                raise TransferPreflightError(
                    f"Historical row was not preserved in {table_name}."
                )
        if failure_point == "after_parent_retirement":
            raise RuntimeError("Injected restore failure after parent retirement.")

        for table_name in _closure_table_order(set(tables)):
            if table_name not in _ACTIVE_LINEAGE_TABLES:
                continue
            table = Base.metadata.tables[table_name]
            for row in tables[table_name]:
                values = _closure_values(table, row)
                await session.execute(table.insert().values(values))
        await session.flush()
        if failure_point == "after_parent_restoration":
            raise RuntimeError("Injected restore failure after parent restoration.")

        for table_name in _closure_table_order(set(tables)):
            if table_name in _ACTIVE_LINEAGE_TABLES:
                continue
            table = Base.metadata.tables[table_name]
            for row in tables[table_name]:
                existing = await _existing_closure_row(session, table, row)
                if existing is not None:
                    if not _same_closure_row(table, existing, row):
                        raise TransferPreflightError(
                            f"Conflicting closure row: {table_name}:{row['primary_key']}"
                        )
                    continue
                values = _closure_values(table, row)
                if table_name == "model_inference_artifacts":
                    values["release_status"] = RETIRED_ARTIFACT_STATUS
                await session.execute(table.insert().values(values))
        await session.flush()
        await _preflight_parent_closure(session, artifact)
        if failure_point == "during_closure_verification":
            raise RuntimeError("Injected restore failure during closure verification.")

        old_artifact_id = _uuid(manifest["replacement"]["old_artifact_id"], "replacement.old_artifact_id")
        old_artifact = await session.get(
            ModelInferenceArtifactRecord, old_artifact_id, with_for_update=True
        )
        if (
            old_artifact is None
            or old_artifact.artifact_sha256 != manifest["replacement"]["old_artifact_sha256"]
            or old_artifact.release_status != RETIRED_ARTIFACT_STATUS
        ):
            raise TransferPreflightError("Expected retired legacy artifact is missing or differs.")
        active = (
            await session.scalars(
                select(ModelInferenceArtifactRecord)
                .where(ModelInferenceArtifactRecord.release_status == ACTIVE_ARTIFACT_STATUS)
                .with_for_update()
            )
        ).all()
        new_id = _uuid(artifact["id"], "artifact.id")
        new_artifact = await session.get(
            ModelInferenceArtifactRecord, new_id, with_for_update=True
        )
        if len(active) == 1 and active[0].id == new_id:
            if new_artifact is None or not _same_artifact(new_artifact, artifact):
                raise TransferPreflightError("Active approved artifact differs from closure.")
        else:
            if active:
                raise TransferPreflightError("Unexpected active inference artifact exists.")
            if new_artifact is None or new_artifact.release_status != RETIRED_ARTIFACT_STATUS:
                raise TransferPreflightError("Approved artifact was not staged as RETIRED.")
            _validate_replacement_manifest(manifest, artifact, old_artifact)
            new_artifact.release_status = ACTIVE_ARTIFACT_STATUS
            await session.flush()
        if failure_point == "after_artifact_activation":
            raise RuntimeError("Injected restore failure after artifact activation.")
        result = await _verify_restored_state(
            session, manifest, closure_document, artifact, tables
        )
        if failure_point == "after_final_verification":
            raise RuntimeError("Injected restore failure after final verification.")
        return ("already_restored" if approved_existing is not None else "restored"), result


async def _restore_release(
    url: str,
    closure_path: str,
    manifest_path: str,
    *,
    failure_point: str | None = None,
) -> int:
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    with open(closure_path, encoding="utf-8") as handle:
        closure_document = json.load(handle)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    artifact, tables = _validate_closure_document(closure_document)
    _validate_closure_relationships(tables)
    _validate_restore_manifest(manifest, artifact, closure_document, tables)
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            outcome, result = await _restore_release_transaction(
                session,
                manifest,
                closure_document,
                artifact,
                tables,
                failure_point=failure_point,
            )
    finally:
        await engine.dispose()
    print(json.dumps({"status": outcome, **result}, sort_keys=True))
    return 0


async def _verify_restore(url: str, closure_path: str, manifest_path: str) -> int:
    """Read-only verification of the complete restored artifact release."""
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    with open(closure_path, encoding="utf-8") as handle:
        closure_document = json.load(handle)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    artifact, tables = _validate_closure_document(closure_document)
    _validate_closure_relationships(tables)
    _validate_restore_manifest(manifest, artifact, closure_document, tables)
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            identity = await read_target_identity(session)
            _validate_release_manifest(manifest, artifact, identity)
            result = await _verify_restored_state(
                session, manifest, closure_document, artifact, tables
            )
    finally:
        await engine.dispose()
    print(json.dumps({"status": "PASS", **result}, sort_keys=True))
    return 0


async def _preflight_restore_release(
    url: str,
    closure_path: str,
    manifest_path: str,
) -> int:
    """Run the complete restore gate without any target mutation."""
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    try:
        with open(closure_path, encoding="utf-8") as handle:
            closure_document = json.load(handle)
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        artifact, tables = _validate_closure_document(closure_document)
        _validate_closure_relationships(tables)
        engine = create_async_engine(url)
        try:
            factory = async_sessionmaker(engine)
            async with factory() as session:
                result = await _preflight_restore_release_state(
                    session, manifest, closure_document, artifact, tables
                )
                await session.rollback()
        finally:
            await engine.dispose()
    except (TransferPreflightError, SQLAlchemyError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "PRECONDITIONS FAIL",
                    "reason": str(error),
                    "mutation_performed": "NO",
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


async def _export(url: str | None, output_path: str) -> int:
    if url is not None:
        _require_postgres(url)
        from app.persistence.database import create_async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(create_async_engine(url))
    else:
        factory = session_factory
    async with factory() as session:
        await _preflight_schema(session)
        records = (
            await session.scalars(select(ModelInferenceArtifactRecord))
        ).all()
    rows = [_serialize(record) for record in records]
    rows = _validate_document(
        {"format": "alphalens-approved-state/1", "model_inference_artifacts": rows}
    )
    async with factory() as session:
        for row in rows:
            await _preflight_parent_closure(session, row)
    document = {
        "format": "alphalens-approved-state/1",
        "model_inference_artifacts": rows,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "status": "exported",
                "rows": len(rows),
                "output": output_path,
            },
            sort_keys=True,
        )
    )
    return 0


async def _import(url: str | None, input_path: str, manifest_path: str) -> int:
    if url is not None:
        _require_postgres(url)
        from app.persistence.database import create_async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(create_async_engine(url))
    else:
        factory = session_factory
    with open(input_path, encoding="utf-8") as handle:
        document = json.load(handle)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    rows = _validate_document(document)
    if len(rows) != 1:
        raise TransferPreflightError(
            "Release import requires exactly one canonical artifact row."
        )
    imported = 0
    skipped_flags: list[bool]
    async with factory() as session:
        target_identity = await read_target_identity(session)
        _validate_release_manifest(manifest, rows[0], target_identity)
        skipped_flags = await _preflight_import(session, rows)
        for row, already_exists in zip(rows, skipped_flags, strict=True):
            if already_exists:
                continue
            session.add(_record_from_row(row, release_status=ACTIVE_ARTIFACT_STATUS))
            imported += 1
        await session.commit()
    skipped = sum(skipped_flags)
    print(
        json.dumps(
            {
                "status": "imported",
                "rows_imported": imported,
                "rows_skipped_existing": skipped,
                "hashes_verified": len(rows),
            },
            sort_keys=True,
        )
    )
    return 0


async def _replace(url: str | None, input_path: str, manifest_path: str) -> int:
    """Atomically retire the expected artifact and activate the approved one."""
    if url is not None:
        _require_postgres(url)
        from app.persistence.database import create_async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        factory = async_sessionmaker(create_async_engine(url))
    else:
        factory = session_factory
    with open(input_path, encoding="utf-8") as handle:
        document = json.load(handle)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    rows = _validate_document(document)
    if len(rows) != 1:
        raise TransferPreflightError(
            "Artifact replacement requires exactly one canonical artifact row."
        )
    row = rows[0]
    async with factory() as session:
        async with session.begin():
            target_identity = await read_target_identity(session)
            _validate_release_manifest(manifest, row, target_identity)
            await _preflight_schema(session)
            await _preflight_parent_closure(session, row)

            active = (
                await session.scalars(
                    select(ModelInferenceArtifactRecord)
                    .where(
                        ModelInferenceArtifactRecord.release_status
                        == ACTIVE_ARTIFACT_STATUS
                    )
                    .with_for_update()
                )
            ).all()
            old_id = _uuid(
                manifest["replacement"]["old_artifact_id"],
                "replacement.old_artifact_id",
            )
            old_record = await session.get(
                ModelInferenceArtifactRecord,
                old_id,
                with_for_update=True,
            )
            if old_record is None:
                raise TransferPreflightError("Expected old artifact is missing.")
            _validate_replacement_manifest(manifest, row, old_record)
            new_id = _uuid(row["id"], "id")
            new_record = await session.get(
                ModelInferenceArtifactRecord,
                new_id,
                with_for_update=True,
            )

            if (
                len(active) == 1
                and active[0].id == new_id
                and new_record is not None
                and _same_artifact(new_record, row)
                and old_record.release_status == RETIRED_ARTIFACT_STATUS
            ):
                loaded = await load_production_artifact(session)
                if loaded.artifact_id != new_id:
                    raise TransferPreflightError(
                        "Idempotent replacement loaded an unexpected artifact."
                    )
                print(
                    json.dumps(
                        {
                            "status": "already_replaced",
                            "active_artifact_id": str(loaded.artifact_id),
                            "active_artifact_sha256": loaded.artifact_sha256,
                        },
                        sort_keys=True,
                    )
                )
                return 0

            old_is_expected_active = (
                len(active) == 1
                and active[0].id == old_id
                and active[0].artifact_sha256 == old_record.artifact_sha256
                and old_record.release_status == ACTIVE_ARTIFACT_STATUS
            )
            old_is_expected_retired = (
                not active
                and old_record.release_status == RETIRED_ARTIFACT_STATUS
            )
            if not (old_is_expected_active or old_is_expected_retired):
                raise TransferPreflightError(
                    "Expected old artifact is neither the sole active artifact "
                    "nor the verified retired legacy artifact."
                )
            if old_record.artifact_sha256 != manifest["replacement"]["old_artifact_sha256"]:
                raise TransferPreflightError("Old artifact hash precondition failed.")
            if new_record is not None and (
                not _same_artifact(new_record, row)
                or new_record.release_status != RETIRED_ARTIFACT_STATUS
            ):
                raise TransferPreflightError(
                    "Approved replacement artifact identity exists with conflicting content or status."
                )

            if old_is_expected_active:
                old_record.release_status = RETIRED_ARTIFACT_STATUS
                await session.flush()
            if new_record is None:
                session.add(_record_from_row(row, release_status=ACTIVE_ARTIFACT_STATUS))
            else:
                new_record.release_status = ACTIVE_ARTIFACT_STATUS
            await session.flush()
            active_after = (
                await session.scalars(
                    select(ModelInferenceArtifactRecord).where(
                        ModelInferenceArtifactRecord.release_status
                        == ACTIVE_ARTIFACT_STATUS
                    )
                )
            ).all()
            if len(active_after) != 1 or active_after[0].id != new_id:
                raise TransferPreflightError(
                    "Replacement did not produce exactly one active artifact."
                )
            loaded = await load_production_artifact(session)
            if (
                loaded.artifact_id != new_id
                or loaded.artifact_sha256 != row["artifact_sha256"]
            ):
                raise TransferPreflightError(
                    "Replacement artifact failed post-activation verification."
                )
        print(
            json.dumps(
                {
                    "status": "replaced",
                    "retired_artifact_id": str(old_id),
                    "active_artifact_id": str(loaded.artifact_id),
                    "active_artifact_sha256": loaded.artifact_sha256,
                },
                sort_keys=True,
            )
        )
    return 0


async def _verify_target(url: str, manifest_path: str) -> int:
    """Read-only target identity check for an explicitly authorized release."""
    _require_postgres(url)
    from app.persistence.database import create_async_engine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or manifest.get("format") != _RELEASE_MANIFEST_FORMAT:
        raise TransferPreflightError("Unrecognized release manifest format.")
    unsigned = dict(manifest)
    recorded_hash = unsigned.pop("manifest_sha256", None)
    if not isinstance(recorded_hash, str) or hash_json(unsigned) != recorded_hash:
        raise TransferPreflightError("Release manifest hash verification failed.")
    engine = create_async_engine(url)
    try:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            identity = await read_target_identity(session)
    finally:
        await engine.dispose()
    verify_target_identity(identity, manifest.get("target", {}))
    print(
        json.dumps(
            {
                "status": "target_verified",
                "database_name": identity["database_name"],
                "host": identity["host"],
                "port": identity["port"],
            },
            sort_keys=True,
        )
    )
    return 0


def _bind_restore_manifest(
    input_path: str,
    closure_path: str,
    output_path: str,
) -> int:
    """Create a production-bound manifest using local approved inputs only."""
    with open(input_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    with open(closure_path, encoding="utf-8") as handle:
        closure_document = json.load(handle)
    derived = _build_restore_manifest(manifest, closure_document)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(derived, handle, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "status": "production_restore_manifest_bound",
                "artifact_id": derived["artifact"]["artifact_id"],
                "artifact_sha256": derived["artifact"]["artifact_sha256"],
                "closure_sha256": derived["restoration"]["closure_sha256"],
                "manifest_sha256": derived["manifest_sha256"],
                "output": output_path,
                "production_contacted": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _require_postgres(url: str) -> None:
    if urlsplit(url).scheme != "postgresql+asyncpg":
        raise ValueError(
            "Approved-state transfer requires a postgresql+asyncpg URL."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in (
        "export",
        "export-closure",
        "bind-restore-manifest",
        "import",
        "import-closure",
        "bootstrap-release",
        "replace",
        "restore-release",
        "preflight-restore-release",
        "verify-restore",
        "verify-target",
    ):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--url", default=None)
        if name == "export":
            subparser.add_argument("--output", required=True)
        elif name == "export-closure":
            subparser.add_argument("--input", required=True)
            subparser.add_argument("--output", required=True)
        elif name == "bind-restore-manifest":
            subparser.add_argument("--input", required=True)
            subparser.add_argument("--closure", required=True)
            subparser.add_argument("--output", required=True)
        elif name in {"import", "import-closure", "replace"}:
            subparser.add_argument("--input", required=True)
            subparser.add_argument("--manifest", required=True)
        elif name in {"restore-release", "preflight-restore-release", "verify-restore"}:
            subparser.add_argument("--closure", required=True)
            subparser.add_argument("--manifest", required=True)
        elif name == "bootstrap-release":
            subparser.add_argument("--closure", required=True)
            subparser.add_argument("--manifest", required=True)
        else:
            subparser.add_argument("--manifest", required=True)
    arguments = parser.parse_args()
    if arguments.command == "export":
        return asyncio.run(_export(arguments.url, arguments.output))
    if arguments.command == "export-closure":
        if arguments.url is None:
            parser.error("export-closure requires --url")
        return asyncio.run(
            _export_closure(arguments.url, arguments.input, arguments.output)
        )
    if arguments.command == "bind-restore-manifest":
        if arguments.url is not None:
            parser.error("bind-restore-manifest is local-only and does not accept --url")
        return _bind_restore_manifest(
            arguments.input, arguments.closure, arguments.output
        )
    if arguments.command == "verify-target":
        if arguments.url is None:
            parser.error("verify-target requires --url")
        return asyncio.run(_verify_target(arguments.url, arguments.manifest))
    if arguments.command == "replace":
        if arguments.url is None:
            parser.error("replace requires --url")
        return asyncio.run(_replace(arguments.url, arguments.input, arguments.manifest))
    if arguments.command == "bootstrap-release":
        if arguments.url is None:
            parser.error("bootstrap-release requires --url")
        return asyncio.run(
            _bootstrap_release(
                arguments.url, arguments.closure, arguments.manifest
            )
        )
    if arguments.command == "restore-release":
        if arguments.url is None:
            parser.error("restore-release requires --url")
        return asyncio.run(
            _restore_release(
                arguments.url, arguments.closure, arguments.manifest
            )
        )
    if arguments.command == "preflight-restore-release":
        if arguments.url is None:
            parser.error("preflight-restore-release requires --url")
        return asyncio.run(
            _preflight_restore_release(
                arguments.url, arguments.closure, arguments.manifest
            )
        )
    if arguments.command == "verify-restore":
        if arguments.url is None:
            parser.error("verify-restore requires --url")
        return asyncio.run(
            _verify_restore(
                arguments.url, arguments.closure, arguments.manifest
            )
        )
    if arguments.command == "import-closure":
        if arguments.url is None:
            parser.error("import-closure requires --url")
        return asyncio.run(
            _import_closure(arguments.url, arguments.input, arguments.manifest)
        )
    return asyncio.run(_import(arguments.url, arguments.input, arguments.manifest))


if __name__ == "__main__":
    sys.exit(main())
