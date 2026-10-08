"""Fail-closed tests for the approved-state transfer preflight."""

from __future__ import annotations

import importlib.util
import copy
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from uuid import UUID

from app.inference.artifact import build_artifact_envelope
from app.model_packaging.ridge import FittedRidgeState, build_ridge_artifact_core
from app.persistence.models import (
    HoldoutEvaluationReportRecord,
    RegressionExperimentRecord,
    ValidationRunRecord,
)


_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "transfer_approved_state",
    _ROOT / "scripts" / "transfer_approved_state.py",
)
assert _SPEC is not None and _SPEC.loader is not None
TRANSFER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(TRANSFER)


EXPERIMENT_ID = UUID("00000000-0000-0000-0000-000000000001")
HOLDOUT_ID = UUID("00000000-0000-0000-0000-000000000002")
VALIDATION_ID = UUID("00000000-0000-0000-0000-000000000003")
INGESTION_ID = UUID("00000000-0000-0000-0000-000000000004")
FEATURE_ID = UUID("00000000-0000-0000-0000-000000000005")
TARGET_ID = UUID("00000000-0000-0000-0000-000000000006")


def _row() -> dict:
    provenance = {
        "selected_experiment_id": str(EXPERIMENT_ID),
        "experiment_configuration_hash": "1" * 64,
        "experiment_result_hash": "2" * 64,
        "holdout_evaluation_report_id": str(HOLDOUT_ID),
        "holdout_configuration_hash": "3" * 64,
        "holdout_result_hash": "4" * 64,
        "validation_run_id": str(VALIDATION_ID),
        "split_hash": "5" * 64,
        "source_ingestion_batch_id": str(INGESTION_ID),
        "source_feature_run_id": str(FEATURE_ID),
        "source_target_run_id": str(TARGET_ID),
    }
    core = build_ridge_artifact_core(
        state=FittedRidgeState(
            scaler_means=(1.0, 2.0),
            scaler_scales=(2.0, 4.0),
            coefficients=(0.5, -1.0),
            intercept=0.25,
        ),
        configuration_hash="6" * 64,
        feature_names=("feature_a", "feature_b"),
        feature_pipeline_version="1.1.0",
        model_dataset_hash="7" * 64,
        training_dataset_hash="8" * 64,
        software_versions={"numpy": "test"},
        provenance=provenance,
    )
    payload, artifact_hash = build_artifact_envelope(
        core=core,
        created_at_iso="2026-09-30T00:00:00+00:00",
    )
    verification = {
        "artifact_only_inference": True,
        "training_invoked_during_inference": False,
        "verification_prediction_count": 5,
        "official_prediction_hash": "9" * 64,
        "artifact_prediction_hash": "9" * 64,
        "all_prediction_float_hex_values_match": True,
        "repeatability_verified": True,
        "predictions": [],
        "model_tuned": False,
        "experiment_modified": False,
        "research_artifacts_modified": False,
        "holdout_metrics_recomputed": False,
    }
    return {
        "id": "00000000-0000-0000-0000-000000000007",
        "artifact_version": "1.0.0",
        "model_family": "ridge_regression",
        "artifact_payload": payload,
        "verification_evidence": verification,
        "configuration_hash": "6" * 64,
        "artifact_sha256": artifact_hash,
        "state_sha256": payload["state_sha256"],
        "verification_evidence_hash": TRANSFER.hash_json(verification),
        "selected_experiment_id": str(EXPERIMENT_ID),
        "holdout_evaluation_report_id": str(HOLDOUT_ID),
        "model_dataset_hash": "7" * 64,
        "training_dataset_hash": "8" * 64,
        "feature_pipeline_version": "1.1.0",
        "target_version": "1.0.0",
        "validation_run_id": str(VALIDATION_ID),
        "split_hash": "5" * 64,
        "final_training_observation_count": 610,
        "purged_observation_count": 50,
        "feature_count": 2,
        "coefficient_count": 2,
        "scaler_mean_count": 2,
        "scaler_scale_count": 2,
        "verification_prediction_count": 5,
        "official_prediction_hash": "9" * 64,
        "deterministic_replay": True,
        "official_prediction_hash_verified": True,
        "artifact_only_inference_verified": True,
        "model_tuned": False,
        "experiment_modified": False,
        "research_artifacts_modified": False,
        "created_at": "2026-09-30T00:00:00+00:00",
    }


def _document(row: dict | None = None) -> dict:
    return {
        "format": "alphalens-approved-state/1",
        "model_inference_artifacts": [row or _row()],
    }


def _release_manifest(row: dict | None = None) -> dict:
    row = row or _row()
    manifest = {
        "format": "alphalens-release-manifest/1",
        "approved": True,
        "approved_by": "reviewer@example.test",
        "approved_at": "2026-10-03T10:00:00+00:00",
        "release_action": "IMPORT_FOR_RELEASE_REVIEW",
        "backup": {"backup_id": "backup-20261003", "sha256": "a" * 64},
        "rollback": {"reference": "release-previous-artifact"},
        "target": {
            "environment": "production",
            "database_name": "alphalens_production",
            "host": "127.0.0.1",
            "port": 5432,
        },
        "artifact": {
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
        },
    }
    manifest["manifest_sha256"] = TRANSFER.hash_json(manifest)
    return manifest


def _parents(row: dict) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    experiment = SimpleNamespace(
        id=EXPERIMENT_ID,
        model_family="ridge_regression",
        feature_pipeline_version="1.1.0",
        target_version="1.0.0",
        selected_experiment_id=EXPERIMENT_ID,
        model_dataset_hash=row["model_dataset_hash"],
        validation_run_id=VALIDATION_ID,
        split_hash=row["split_hash"],
        experiment_configuration_hash="1" * 64,
        result_hash="2" * 64,
        source_ingestion_batch_id=INGESTION_ID,
        source_feature_run_id=FEATURE_ID,
        source_target_run_id=TARGET_ID,
        model_parameters={"alpha": "1.0", "fit_intercept": True, "solver": "svd"},
    )
    holdout = SimpleNamespace(
        id=HOLDOUT_ID,
        final_model_selection_report_id=UUID("00000000-0000-0000-0000-000000000008"),
        selected_experiment_id=EXPERIMENT_ID,
        validation_run_id=VALIDATION_ID,
        model_dataset_hash=row["model_dataset_hash"],
        split_hash=row["split_hash"],
        configuration_hash="3" * 64,
        result_hash="4" * 64,
        report_configuration={},
        report_payload={},
        holdout_consumed=True,
        official_holdout_evaluation=True,
        holdout_evaluated=True,
        development_prediction_hashes_match=True,
        artifact_hashes_verified=True,
        model_parameters_modified=False,
        feature_engineering_performed=False,
        hyperparameter_tuning_performed=False,
        experiments_modified=False,
    )
    holdout.configuration_hash = TRANSFER.hash_json(holdout.report_configuration)
    holdout.result_hash = TRANSFER.hash_json(holdout.report_payload)
    row["artifact_payload"]["core"]["provenance"]["holdout_configuration_hash"] = holdout.configuration_hash
    row["artifact_payload"]["core"]["provenance"]["holdout_result_hash"] = holdout.result_hash
    row["artifact_payload"]["state_sha256"] = TRANSFER.hash_json(
        row["artifact_payload"]["core"]
    )
    row["artifact_sha256"] = TRANSFER.hash_json(row["artifact_payload"])
    row["state_sha256"] = TRANSFER.hash_json(row["artifact_payload"]["core"])
    row["artifact_payload"]["core"]["provenance"]["holdout_configuration_hash"] = holdout.configuration_hash
    row["artifact_payload"]["core"]["provenance"]["holdout_result_hash"] = holdout.result_hash
    row["verification_evidence_hash"] = TRANSFER.hash_json(row["verification_evidence"])
    validation = SimpleNamespace(
        id=VALIDATION_ID,
        split_hash=row["split_hash"],
        point_in_time_validated=True,
        repeatability_verified=True,
        artifact_hashes_verified=True,
        final_holdout_evaluated=False,
        source_ingestion_batch_id=INGESTION_ID,
        source_feature_run_id=FEATURE_ID,
    )
    selection = SimpleNamespace(
        id=holdout.final_model_selection_report_id,
        selected_model_family="ridge_regression",
        selected_experiment_id=EXPERIMENT_ID,
        validation_run_id=VALIDATION_ID,
        model_dataset_hash=row["model_dataset_hash"],
        feature_pipeline_version="1.1.0",
        target_version="1.0.0",
        split_hash=row["split_hash"],
        point_in_time_validated=True,
        repeatability_verified=True,
        artifact_hashes_verified=True,
        final_holdout_evaluated=False,
    )
    return experiment, holdout, validation, selection


class TransferDocumentTests(TestCase):
    def test_complete_document_passes_validation(self) -> None:
        TRANSFER._validate_document(_document())

    def test_malformed_document_rejected(self) -> None:
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_document({"format": "wrong", "model_inference_artifacts": []})

    def test_duplicate_artifact_identity_rejected(self) -> None:
        row = _row()
        with self.assertRaisesRegex(TRANSFER.TransferPreflightError, "duplicate"):
            TRANSFER._validate_document(_document(row) | {
                "model_inference_artifacts": [row, copy.deepcopy(row)],
            })

    def test_duplicate_artifact_hash_rejected(self) -> None:
        first = _row()
        second = copy.deepcopy(first)
        second["id"] = "00000000-0000-0000-0000-000000000008"
        with self.assertRaisesRegex(TRANSFER.TransferPreflightError, "duplicate"):
            TRANSFER._validate_document(_document(first) | {
                "model_inference_artifacts": [first, second],
            })

    def test_invalid_payload_hash_rejected(self) -> None:
        row = _row()
        row["artifact_sha256"] = "a" * 64
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_document(_document(row))

    def test_invalid_recorded_evidence_hash_rejected(self) -> None:
        row = _row()
        row["verification_evidence_hash"] = "b" * 64
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_document(_document(row))

    def test_schema_preflight_rejects_incompatible_schema(self) -> None:
        snapshot = TRANSFER.SchemaSnapshot(
            heads=frozenset({"old-head"}),
            tables=frozenset(),
            columns={},
            foreign_keys=frozenset(),
            unique_columns=frozenset(),
            checks=frozenset(),
        )
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_schema_snapshot(snapshot)

    def test_release_manifest_validates_with_explicit_approval(self) -> None:
        row = _row()
        TRANSFER._validate_release_manifest(
            _release_manifest(row),
            row,
            {
                "database_name": "alphalens_production",
                "database_user": "ignored",
                "host": "127.0.0.1",
                "port": 5432,
            },
        )

    def test_release_manifest_requires_approval_and_integrity(self) -> None:
        row = _row()
        for mutation in (
            lambda manifest: manifest.__setitem__("approved", False),
            lambda manifest: manifest.__setitem__("manifest_sha256", "f" * 64),
            lambda manifest: manifest["artifact"].__setitem__(
                "artifact_id", "00000000-0000-0000-0000-000000000099"
            ),
            lambda manifest: manifest["artifact"].__setitem__(
                "holdout_evaluation_report_id",
                "00000000-0000-0000-0000-000000000099",
            ),
            lambda manifest: manifest["rollback"].pop("reference"),
        ):
            manifest = copy.deepcopy(_release_manifest(row))
            mutation(manifest)
            with self.assertRaises(TRANSFER.TransferPreflightError):
                TRANSFER._validate_release_manifest(
                    manifest,
                    row,
                    {
                        "database_name": "alphalens_production",
                        "host": "127.0.0.1",
                        "port": 5432,
                    },
                )

    def test_target_identity_is_fail_closed(self) -> None:
        expected = {
            "environment": "production",
            "database_name": "alphalens_production",
            "host": "127.0.0.1",
            "port": 5432,
        }
        TRANSFER.verify_target_identity(expected, expected)
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER.verify_target_identity(
                {**expected, "database_name": "wrong_database"}, expected
            )

    def test_replacement_manifest_binds_old_and_new_artifacts(self) -> None:
        row = _row()
        old = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000099"),
            artifact_sha256="e" * 64,
        )
        manifest = _release_manifest(row)
        manifest["replacement"] = {
            "old_artifact_id": str(old.id),
            "old_artifact_sha256": old.artifact_sha256,
            "new_artifact_id": row["id"],
            "new_artifact_sha256": row["artifact_sha256"],
        }
        TRANSFER._validate_replacement_manifest(manifest, row, old)
        manifest["replacement"]["old_artifact_sha256"] = "f" * 64
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_replacement_manifest(manifest, row, old)

    def test_replacement_manifest_rejects_unexpected_identities(self) -> None:
        row = _row()
        old = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000099"),
            artifact_sha256="e" * 64,
        )
        manifest = _release_manifest(row)
        manifest["replacement"] = {
            "old_artifact_id": str(old.id),
            "old_artifact_sha256": old.artifact_sha256,
            "new_artifact_id": row["id"],
            "new_artifact_sha256": row["artifact_sha256"],
        }
        for field, value in (
            ("old_artifact_id", "00000000-0000-0000-0000-000000000098"),
            ("new_artifact_id", "00000000-0000-0000-0000-000000000098"),
        ):
            candidate = copy.deepcopy(manifest)
            candidate["replacement"][field] = value
            with self.assertRaises(TRANSFER.TransferPreflightError):
                TRANSFER._validate_replacement_manifest(candidate, row, old)

    def test_replacement_record_is_explicitly_active(self) -> None:
        record = TRANSFER._record_from_row(
            _row(), release_status=TRANSFER.ACTIVE_ARTIFACT_STATUS
        )
        self.assertEqual(record.release_status, "ACTIVE")


class TransferDatabasePreflightTests(IsolatedAsyncioTestCase):
    async def test_missing_parent_rejected_before_mutation(self) -> None:
        row = _row()

        class Session:
            added = 0

            async def get(self, model, identifier):
                return None

            def add(self, value):
                self.added += 1

        session = Session()
        with self.assertRaisesRegex(TRANSFER.TransferPreflightError, "Missing"):
            await TRANSFER._preflight_parent_closure(session, row)
        self.assertEqual(session.added, 0)

    async def test_complete_parent_closure_passes(self) -> None:
        row = _row()
        experiment, holdout, validation, selection = _parents(row)

        class Session:
            records = {
                RegressionExperimentRecord: experiment,
                HoldoutEvaluationReportRecord: holdout,
                ValidationRunRecord: validation,
                TRANSFER.FinalModelSelectionReportRecord: selection,
            }

            async def get(self, model, identifier):
                if model in self.records:
                    return self.records[model]
                return SimpleNamespace(
                    **{
                        foreign_key.parent.name: None
                        for foreign_key in model.__table__.foreign_keys
                    }
                )

            async def scalars(self, statement):
                class Result:
                    def all(self):
                        return [
                            SimpleNamespace(
                                validation_run_id=VALIDATION_ID,
                                holdout_evaluation_report_id=HOLDOUT_ID,
                                selected_experiment_id=EXPERIMENT_ID,
                                purpose="official_final_evaluation",
                                official=True,
                                irreversible=True,
                            )
                        ]
                return Result()

        await TRANSFER._preflight_parent_closure(Session(), row)

    async def test_transitive_parent_missing_is_rejected(self) -> None:
        row = _row()
        experiment, holdout, validation, selection = _parents(row)

        class Session:
            records = {
                RegressionExperimentRecord: experiment,
                HoldoutEvaluationReportRecord: holdout,
                ValidationRunRecord: validation,
                TRANSFER.FinalModelSelectionReportRecord: selection,
            }

            async def get(self, model, identifier):
                if model.__table__.name == "feature_pipeline_runs":
                    return None
                if model in self.records:
                    return self.records[model]
                return SimpleNamespace(
                    **{
                        foreign_key.parent.name: None
                        for foreign_key in model.__table__.foreign_keys
                    }
                )

        with self.assertRaisesRegex(
            TRANSFER.TransferPreflightError, "feature_pipeline_runs"
        ):
            await TRANSFER._preflight_parent_closure(Session(), row)

    async def test_same_id_same_hash_is_idempotent(self) -> None:
        row = _row()
        existing = SimpleNamespace(**row)

        class Session:
            async def get(self, model, identifier):
                return existing

        self.assertTrue(await TRANSFER._preflight_existing(Session(), row))

    async def test_same_id_different_hash_is_rejected(self) -> None:
        row = _row()
        existing = SimpleNamespace(**row)
        existing.artifact_sha256 = "c" * 64

        class Session:
            async def get(self, model, identifier):
                return existing

        with self.assertRaisesRegex(TRANSFER.TransferPreflightError, "conflict"):
            await TRANSFER._preflight_existing(Session(), row)

    async def test_missing_provenance_is_rejected(self) -> None:
        row = _row()
        del row["artifact_payload"]["core"]["provenance"]
        row["artifact_payload"], row["artifact_sha256"] = build_artifact_envelope(
            core=row["artifact_payload"]["core"],
            created_at_iso="2026-09-30T00:00:00+00:00",
        )
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_document(_document(row))

    async def test_semantic_provenance_conflict_is_rejected(self) -> None:
        row = _row()
        experiment, holdout, validation, selection = _parents(row)
        experiment.result_hash = "d" * 64
        with self.assertRaises(TRANSFER.TransferPreflightError):
            TRANSFER._validate_semantic_provenance(
                row, experiment, holdout, validation, selection, 1
            )


class SharedArtifactLineageTests(TestCase):
    def _verify(self, row: dict, **overrides) -> None:
        experiment, holdout, validation, selection = _parents(row)
        from app.inference.lineage import verify_ridge_artifact_lineage

        verify_ridge_artifact_lineage(
            artifact=row,
            experiment=overrides.get("experiment", experiment),
            selection=overrides.get("selection", selection),
            holdout=overrides.get("holdout", holdout),
            validation=overrides.get("validation", validation),
            holdout_consumption_count=overrides.get("holdout_consumption_count", 1),
            artifact_count=overrides.get("artifact_count", 1),
            holdout_consumption_verified=overrides.get(
                "holdout_consumption_verified", True
            ),
        )

    def test_complete_lineage_passes(self) -> None:
        self._verify(_row())

    def test_lineage_rejects_identity_integrity_and_lineage_mismatches(self) -> None:
        mutations = (
            ("artifact_id", lambda row: row.__setitem__("id", "bad-id")),
            (
                "artifact_hash",
                lambda row: row["artifact_payload"]["core"].__setitem__(
                    "dataset_hash", "f" * 64
                ),
            ),
            ("model", lambda row: row.__setitem__("model_family", "linear_regression")),
            (
                "feature_version",
                lambda row: row.__setitem__("feature_pipeline_version", "stale"),
            ),
            ("target_version", lambda row: row.__setitem__("target_version", "stale")),
            ("dataset_hash", lambda row: row.__setitem__("model_dataset_hash", "f" * 64)),
            (
                "validation_run",
                lambda row: row.__setitem__(
                    "validation_run_id", "00000000-0000-0000-0000-000000000099"
                ),
            ),
            ("split_hash", lambda row: row.__setitem__("split_hash", "f" * 64)),
            (
                "prediction_hash",
                lambda row: row["verification_evidence"].__setitem__(
                    "artifact_prediction_hash", "f" * 64
                ),
            ),
            (
                "training_count",
                lambda row: row.__setitem__("final_training_observation_count", 611),
            ),
        )
        for name, mutation in mutations:
            with self.subTest(name=name):
                row = _row()
                mutation(row)
                with self.assertRaises(ValueError):
                    self._verify(row)

    def test_lineage_rejects_duplicate_artifact_or_invalid_holdout_consumption(self) -> None:
        with self.assertRaises(ValueError):
            self._verify(_row(), artifact_count=2)
        with self.assertRaises(ValueError):
            self._verify(_row(), holdout_consumption_count=0)
        with self.assertRaises(ValueError):
            self._verify(_row(), holdout_consumption_verified=False)

    def test_lineage_rejects_incomplete_holdout_or_selection(self) -> None:
        row = _row()
        experiment, holdout, validation, selection = _parents(row)
        holdout.holdout_consumed = False
        with self.assertRaises(ValueError):
            self._verify(row, holdout=holdout)
        row = _row()
        experiment, holdout, validation, selection = _parents(row)
        selection.selected_experiment_id = UUID(
            "00000000-0000-0000-0000-000000000099"
        )
        with self.assertRaises(ValueError):
            self._verify(row, selection=selection)
