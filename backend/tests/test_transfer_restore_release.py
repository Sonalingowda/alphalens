"""Disposable PostgreSQL coverage for the atomic approved-state restore."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
from unittest import IsolatedAsyncioTestCase, TestCase
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.persistence.database import create_async_engine
from app.persistence.models import Base
from scripts import transfer_approved_state as transfer


_CLOSURE_PATH = Path("/private/tmp/alphalens-approved-closure-a6576881.json")
_RELEASE_PATH = Path("/private/tmp/alphalens-release-manifest-a6576881.json")


def _fixture_documents(database_name: str) -> tuple[dict, dict, dict, dict[str, list[dict]]]:
    closure = json.loads(_CLOSURE_PATH.read_text(encoding="utf-8"))
    artifact, tables = transfer._validate_closure_document(closure)
    transfer._validate_closure_relationships(tables)
    manifest = json.loads(_RELEASE_PATH.read_text(encoding="utf-8"))
    manifest["target"] = {
        **manifest["target"],
        "database_name": database_name,
        "host": "127.0.0.1",
        "port": 5432,
    }
    historical = [
        {
            "table": transfer._INGESTION_TABLE,
            "id": transfer._LEGACY_INGESTION_ID,
            "row_sha256": transfer._LEGACY_INGESTION_ROW_SHA256,
            "status_after": "INACTIVE",
        },
        {
            "table": "feature_pipeline_runs",
            "id": transfer._LEGACY_FEATURE_RUN_ID,
            "row_sha256": transfer._LEGACY_FEATURE_RUN_ROW_SHA256,
            "status_after": "INACTIVE",
        },
        {
            "table": "forward_log_return_target_runs",
            "id": transfer._LEGACY_TARGET_RUN_ID,
            "row_sha256": transfer._LEGACY_TARGET_RUN_ROW_SHA256,
            "status_after": "INACTIVE",
        },
        {
            "table": "validation_runs",
            "id": transfer._LEGACY_VALIDATION_RUN_ID,
            "row_sha256": transfer._LEGACY_VALIDATION_RUN_ROW_SHA256,
            "status_after": "INACTIVE",
        },
    ]
    manifest["restoration"] = {
        "closure_sha256": closure["closure_sha256"],
        "closure_record_count": closure["closure_record_count"],
        "closure_records_sha256": transfer.hash_json(
            transfer._closure_record_bindings(tables)
        ),
        "approved_ingestion_batch_id": transfer._APPROVED_INGESTION_ID,
        "approved_ingestion_row_sha256": transfer._APPROVED_INGESTION_ROW_SHA256,
        "legacy_ingestion_batch_id": transfer._LEGACY_INGESTION_ID,
        "legacy_ingestion_row_sha256": transfer._LEGACY_INGESTION_ROW_SHA256,
        "legacy_ingestion_status_after": "INACTIVE",
        "historical_active_rows": historical,
        "historical_active_rows_sha256": transfer.hash_json(historical),
        "legacy_artifact_id": transfer._LEGACY_ARTIFACT_ID,
        "legacy_artifact_sha256": transfer._LEGACY_ARTIFACT_SHA256,
        "legacy_artifact_status_after": "RETIRED",
        "active_artifact_id": transfer._APPROVED_ARTIFACT_ID,
        "active_artifact_sha256": transfer._APPROVED_ARTIFACT_SHA256,
    }
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = transfer.hash_json(manifest)
    transfer._validate_restore_manifest(manifest, artifact, closure, tables)
    return closure, artifact, manifest, tables


class RestoreManifestTests(TestCase):
    def test_manifest_binds_every_closure_row_and_historical_parent(self) -> None:
        if not _CLOSURE_PATH.exists() or not _RELEASE_PATH.exists():
            self.skipTest("approved closure and release manifest are unavailable")
        closure, artifact, manifest, tables = _fixture_documents("test-db")
        self.assertEqual(artifact["id"], transfer._APPROVED_ARTIFACT_ID)
        self.assertEqual(
            manifest["restoration"]["closure_records_sha256"],
            transfer.hash_json(transfer._closure_record_bindings(tables)),
        )
        invalid = copy.deepcopy(manifest)
        invalid["restoration"]["historical_active_rows"][0]["row_sha256"] = "0" * 64
        invalid.pop("manifest_sha256")
        invalid["manifest_sha256"] = transfer.hash_json(invalid)
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_restore_manifest(invalid, artifact, closure, tables)

    def test_different_artifact_or_closure_binding_fails_closed(self) -> None:
        if not _CLOSURE_PATH.exists() or not _RELEASE_PATH.exists():
            self.skipTest("approved closure and release manifest are unavailable")
        closure, artifact, manifest, tables = _fixture_documents("test-db")
        bad_artifact = copy.deepcopy(artifact)
        bad_artifact["id"] = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_restore_manifest(manifest, bad_artifact, closure, tables)
        invalid = copy.deepcopy(manifest)
        invalid["restoration"]["closure_sha256"] = "0" * 64
        invalid.pop("manifest_sha256")
        invalid["manifest_sha256"] = transfer.hash_json(invalid)
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_restore_manifest(invalid, artifact, closure, tables)


class ProductionBoundManifestTests(TestCase):
    def setUp(self) -> None:
        if not _CLOSURE_PATH.exists() or not _RELEASE_PATH.exists():
            self.skipTest("approved closure and release manifest are unavailable")
        self.closure = json.loads(_CLOSURE_PATH.read_text(encoding="utf-8"))
        self.manifest = json.loads(_RELEASE_PATH.read_text(encoding="utf-8"))
        self.original_closure = copy.deepcopy(self.closure)
        self.original_closure_hash = self.closure["closure_sha256"]

    def test_generation_binds_exact_approved_inputs_without_mutating_closure(self) -> None:
        derived = transfer._build_restore_manifest(self.manifest, self.closure)
        self.assertIn("restoration", derived)
        self.assertEqual(
            derived["restoration"]["closure_sha256"], self.original_closure_hash
        )
        self.assertEqual(
            derived["restoration"]["active_artifact_id"],
            transfer._APPROVED_ARTIFACT_ID,
        )
        self.assertEqual(
            derived["restoration"]["active_artifact_sha256"],
            transfer._APPROVED_ARTIFACT_SHA256,
        )
        self.assertEqual(self.closure, self.original_closure)
        self.assertEqual(derived["target"], self.manifest["target"])

    def test_generation_rejects_mismatched_production_target(self) -> None:
        mismatched = copy.deepcopy(self.manifest)
        mismatched["target"]["database_name"] = "unexpected-production-db"
        mismatched.pop("manifest_sha256")
        mismatched["manifest_sha256"] = transfer.hash_json(mismatched)
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._build_restore_manifest(mismatched, self.closure)

    def test_generation_rejects_changed_approved_artifact_identity(self) -> None:
        tampered = copy.deepcopy(self.closure)
        tampered["artifact_id"] = "00000000-0000-0000-0000-000000000000"
        tampered["artifact"]["id"] = tampered["artifact_id"]
        artifact_row = tampered["tables"]["model_inference_artifacts"][0]
        artifact_row["primary_key"]["id"] = tampered["artifact_id"]
        artifact_row["values"]["id"] = tampered["artifact_id"]
        tampered.pop("closure_sha256")
        tampered["closure_sha256"] = transfer.hash_json(tampered)
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._build_restore_manifest(self.manifest, tampered)


class DisposableRestoreReleaseTests(IsolatedAsyncioTestCase):
    async def test_atomic_restore_failures_success_verifier_and_idempotency(self) -> None:
        database_url = os.environ.get("ALPHALENS_DISPOSABLE_RESTORE_DATABASE_URL")
        if not database_url or not _CLOSURE_PATH.exists() or not _RELEASE_PATH.exists():
            self.skipTest("dedicated disposable restore PostgreSQL fixture is not configured")
        database_name = urlsplit(database_url).path.lstrip("/")
        if not database_name.startswith("alphalens_restore_fixture_"):
            self.fail("restore integration test requires its dedicated disposable database")

        closure, artifact, manifest, tables = _fixture_documents(database_name)
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def snapshot(session) -> tuple:
            closure_rows = []
            for table_name, rows in tables.items():
                table = Base.metadata.tables[table_name]
                for row in rows:
                    closure_rows.append(
                        (
                            table_name,
                            row["row_sha256"],
                            await transfer._existing_closure_row(session, table, row)
                            is not None,
                        )
                    )
            histories = []
            for binding in manifest["restoration"]["historical_active_rows"]:
                table = Base.metadata.tables[binding["table"]]
                row = (
                    await session.execute(
                        select(table).where(table.c.id == binding["id"])
                    )
                ).mappings().one()
                histories.append(
                    (
                        binding["id"],
                        row["is_active"],
                        transfer.hash_json(
                            transfer._canonical_db_values(table, dict(row))
                        ),
                    )
                )
            artifacts_table = Base.metadata.tables["model_inference_artifacts"]
            artifacts = (
                await session.execute(
                    select(
                        artifacts_table.c.id,
                        artifacts_table.c.artifact_sha256,
                        artifacts_table.c.release_status,
                    ).order_by(artifacts_table.c.id)
                )
            ).all()
            await session.rollback()
            return (
                closure_rows,
                histories,
                [(str(row[0]), row[1], row[2]) for row in artifacts],
            )

        try:
            async with factory() as session:
                baseline = await snapshot(session)
                preflight = await transfer._preflight_restore_release_state(
                    session, manifest, closure, artifact, tables
                )
                self.assertEqual(preflight["preconditions"], "PASS")
                self.assertEqual(preflight["mutation_performed"], "NO")
                self.assertEqual(await snapshot(session), baseline)
                for failure_point in (
                    "after_parent_retirement",
                    "after_parent_restoration",
                    "after_artifact_activation",
                    "after_final_verification",
                ):
                    with self.assertRaises(RuntimeError):
                        await transfer._restore_release_transaction(
                            session,
                            manifest,
                            closure,
                            artifact,
                            tables,
                            failure_point=failure_point,
                        )
                    self.assertEqual(await snapshot(session), baseline)

                result, report = await transfer._restore_release_transaction(
                    session, manifest, closure, artifact, tables
                )
                self.assertEqual(result, "restored")
                self.assertEqual(report["active_artifact_count"], 1)
                self.assertEqual(report["lineage"], "PASS")
                self.assertEqual(report["loader"], "PASS")
                restored = await snapshot(session)
                self.assertTrue(all(item[2] for item in restored[0]))
                self.assertEqual(
                    [item[1] for item in restored[1]],
                    [False] * len(restored[1]),
                )
                self.assertEqual(
                    restored[2],
                    [
                        (
                            transfer._APPROVED_ARTIFACT_ID,
                            transfer._APPROVED_ARTIFACT_SHA256,
                            "ACTIVE",
                        ),
                        (
                            transfer._LEGACY_ARTIFACT_ID,
                            transfer._LEGACY_ARTIFACT_SHA256,
                            "RETIRED",
                        ),
                    ],
                )

                before_verify = await snapshot(session)
                with tempfile.TemporaryDirectory() as directory:
                    closure_path = Path(directory) / "closure.json"
                    manifest_path = Path(directory) / "manifest.json"
                    closure_path.write_text(json.dumps(closure), encoding="utf-8")
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                    self.assertEqual(
                        await transfer._verify_restore(
                            database_url, str(closure_path), str(manifest_path)
                        ),
                        0,
                    )
                self.assertEqual(await snapshot(session), before_verify)

                second, second_report = await transfer._restore_release_transaction(
                    session, manifest, closure, artifact, tables
                )
                self.assertEqual(second, "already_restored")
                self.assertEqual(second_report["artifact_id"], transfer._APPROVED_ARTIFACT_ID)
                self.assertEqual(await snapshot(session), before_verify)
        finally:
            await engine.dispose()
