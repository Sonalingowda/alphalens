"""Focused tests for fresh-target approved-state bootstrap."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

from scripts import transfer_approved_state as transfer


CLOSURE_PATH = Path("/private/tmp/alphalens-approved-closure-a6576881.json")
RELEASE_PATH = Path("/private/tmp/alphalens-release-manifest-a6576881.json")


def _documents(database_name: str) -> tuple[dict, dict, dict, dict[str, list[dict]]]:
    closure = json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))
    artifact, tables = transfer._validate_closure_document(closure)
    transfer._validate_closure_relationships(tables)
    manifest = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    manifest["target"] = {
        **manifest["target"],
        "database_name": database_name,
        "host": "127.0.0.1",
        "port": 5432,
    }
    manifest["bootstrap"] = {
        "closure_sha256": closure["closure_sha256"],
        "closure_record_count": closure["closure_record_count"],
        "closure_records_sha256": transfer.hash_json(
            transfer._closure_record_bindings(tables)
        ),
        "source_schema_heads": closure["source_schema_heads"],
        "artifact_id": artifact["id"],
        "artifact_sha256": artifact["artifact_sha256"],
    }
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = transfer.hash_json(manifest)
    return closure, artifact, manifest, tables


async def _persisted_digest(session, table_names: set[str]) -> str:
    from sqlalchemy import select

    state = []
    for table_name in sorted(table_names):
        table = transfer.Base.metadata.tables[table_name]
        rows = (
            await session.execute(select(table))
        ).mappings().all()
        canonical_rows = sorted(
            (
                transfer._canonical_db_values(table, dict(row))
                for row in rows
            ),
            key=transfer.hash_json,
        )
        state.append({"table": table_name, "rows": canonical_rows})
    versions = (
        await session.execute(
            select(transfer.text("version_num")).select_from(
                transfer.text("alembic_version")
            )
        )
    ).scalars().all()
    state.append({"table": "alembic_version", "rows": sorted(versions)})
    return transfer.hash_json(state)


async def _write_bootstrap_inputs(
    directory: str,
    closure: dict,
    manifest: dict,
) -> tuple[str, str]:
    closure_path = Path(directory) / "closure.json"
    manifest_path = Path(directory) / "manifest.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return str(closure_path), str(manifest_path)


def _manifest_for(
    closure: dict,
    tables: dict[str, list[dict]],
    database_name: str,
    host: str,
    port: int,
) -> tuple[dict, dict]:
    artifact = closure["artifact"]
    _, _, manifest, _ = _documents(database_name)
    manifest["target"].update(host=host, port=port)
    manifest["bootstrap"] = {
        "closure_sha256": closure["closure_sha256"],
        "closure_record_count": closure["closure_record_count"],
        "closure_records_sha256": transfer.hash_json(
            transfer._closure_record_bindings(tables)
        ),
        "source_schema_heads": closure["source_schema_heads"],
        "artifact_id": artifact["id"],
        "artifact_sha256": artifact["artifact_sha256"],
    }
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = transfer.hash_json(manifest)
    return artifact, manifest


@unittest.skipUnless(
    CLOSURE_PATH.exists() and RELEASE_PATH.exists(),
    "approved disposable release fixtures are unavailable",
)
class BootstrapValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.closure, self.artifact, self.manifest, self.tables = _documents(
            "alphalens_bootstrap_fixture"
        )

    def test_exact_approved_artifact_and_closure_pass(self) -> None:
        transfer._validate_bootstrap_manifest(
            self.manifest, self.artifact, self.closure, self.tables
        )

    def test_wrong_artifact_fails_closed(self) -> None:
        wrong = copy.deepcopy(self.artifact)
        wrong["id"] = "00000000-0000-0000-0000-000000000099"
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_bootstrap_manifest(
                self.manifest, wrong, self.closure, self.tables
            )

    def test_missing_parent_fails_closed(self) -> None:
        missing = copy.deepcopy(self.tables)
        del missing["validation_runs"]
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_closure_relationships(missing)

    def test_target_mismatch_and_missing_binding_fail_closed(self) -> None:
        mismatched = copy.deepcopy(self.manifest)
        mismatched["target"]["database_name"] = "other-target"
        mismatched.pop("manifest_sha256")
        mismatched["manifest_sha256"] = transfer.hash_json(mismatched)
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_release_manifest(
                mismatched,
                self.artifact,
                {"database_name": "alphalens_bootstrap_fixture", "host": "127.0.0.1", "port": 5432},
            )
        missing = copy.deepcopy(self.manifest)
        missing.pop("bootstrap")
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_bootstrap_manifest(
                missing, self.artifact, self.closure, self.tables
            )

    def test_closure_binding_and_artifact_hash_cannot_be_changed(self) -> None:
        tampered = copy.deepcopy(self.manifest)
        tampered["bootstrap"]["closure_records_sha256"] = "0" * 64
        with self.assertRaises(transfer.TransferPreflightError):
            transfer._validate_bootstrap_manifest(
                tampered, self.artifact, self.closure, self.tables
            )


@unittest.skipUnless(
    os.environ.get("ALPHALENS_DISPOSABLE_BOOTSTRAP_DATABASE_URL")
    and CLOSURE_PATH.exists()
    and RELEASE_PATH.exists(),
    "dedicated disposable bootstrap PostgreSQL fixture is not configured",
)
class DisposableBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_and_exact_duplicate_are_safe(self) -> None:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.persistence.database import create_async_engine
        from app.persistence.models import ModelInferenceArtifactRecord

        url = os.environ["ALPHALENS_DISPOSABLE_BOOTSTRAP_DATABASE_URL"]
        database_name = urlsplit(url).path.lstrip("/")
        if not database_name.startswith("alphalens_bootstrap_fixture_"):
            self.fail("bootstrap integration test requires its dedicated disposable database")
        engine = create_async_engine(url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            identity = await transfer.read_target_identity(session)
        closure, artifact, manifest, _ = _documents(identity["database_name"])
        manifest["target"].update(
            host=identity["host"], port=identity["port"]
        )
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = transfer.hash_json(manifest)
        async def attempt(attempt_closure: dict, attempt_manifest: dict) -> None:
            with tempfile.TemporaryDirectory() as directory:
                closure_path, manifest_path = await _write_bootstrap_inputs(
                    directory, attempt_closure, attempt_manifest
                )
                await transfer._bootstrap_release(
                    url, closure_path, manifest_path
                )

        async with factory() as session:
            baseline = await _persisted_digest(session, set(closure["tables"]))

        wrong_closure = copy.deepcopy(closure)
        wrong_artifact = wrong_closure["artifact"]
        wrong_id = "00000000-0000-0000-0000-000000000099"
        wrong_artifact["id"] = wrong_id
        wrong_closure["artifact_id"] = wrong_id
        artifact_row = wrong_closure["tables"]["model_inference_artifacts"][0]
        artifact_row["primary_key"]["id"] = wrong_id
        artifact_row["values"]["id"] = wrong_id
        artifact_row["row_sha256"] = transfer.hash_json(artifact_row["values"])
        wrong_closure.pop("closure_sha256")
        wrong_closure["closure_sha256"] = transfer.hash_json(wrong_closure)
        wrong_artifact, wrong_manifest = _manifest_for(
            wrong_closure,
            {name: rows for name, rows in wrong_closure["tables"].items()},
            identity["database_name"],
            identity["host"],
            identity["port"],
        )
        del wrong_artifact
        with self.assertRaises(transfer.TransferPreflightError):
            await attempt(wrong_closure, wrong_manifest)

        missing_parent = copy.deepcopy(closure)
        missing_parent["tables"].pop("validation_runs")
        missing_parent["closure_record_count"] = sum(
            len(rows) for rows in missing_parent["tables"].values()
        )
        missing_parent.pop("closure_sha256")
        missing_parent["closure_sha256"] = transfer.hash_json(missing_parent)
        _, missing_manifest = _manifest_for(
            missing_parent,
            missing_parent["tables"],
            identity["database_name"],
            identity["host"],
            identity["port"],
        )
        with self.assertRaises(transfer.TransferPreflightError):
            await attempt(missing_parent, missing_manifest)

        target_mismatch = copy.deepcopy(manifest)
        target_mismatch["target"]["database_name"] = "other-target"
        target_mismatch.pop("manifest_sha256")
        target_mismatch["manifest_sha256"] = transfer.hash_json(target_mismatch)
        with self.assertRaises(transfer.TransferPreflightError):
            await attempt(closure, target_mismatch)

        missing_target = copy.deepcopy(manifest)
        missing_target["target"].pop("database_name")
        missing_target.pop("manifest_sha256")
        missing_target["manifest_sha256"] = transfer.hash_json(missing_target)
        with self.assertRaises(transfer.TransferPreflightError):
            await attempt(closure, missing_target)

        async with factory() as session:
            self.assertEqual(
                baseline, await _persisted_digest(session, set(closure["tables"]))
            )

        with tempfile.TemporaryDirectory() as directory:
            closure_path, manifest_path = await _write_bootstrap_inputs(
                directory, closure, manifest
            )
            first = await transfer._bootstrap_release(
                url, closure_path, manifest_path
            )
        async with factory() as session:
            after_first = await _persisted_digest(session, set(closure["tables"]))
            before_second = await _persisted_digest(session, set(closure["tables"]))
        with tempfile.TemporaryDirectory() as directory:
            closure_path, manifest_path = await _write_bootstrap_inputs(
                directory, closure, manifest
            )
            second = await transfer._bootstrap_release(
                url, closure_path, manifest_path
            )
        async with factory() as session:
            after_second = await _persisted_digest(session, set(closure["tables"]))
        self.assertEqual(first, 0)
        self.assertEqual(second, 0)
        self.assertEqual(after_first, before_second)
        self.assertEqual(before_second, after_second)
        async with factory() as session:
            artifacts = (
                await session.scalars(select(ModelInferenceArtifactRecord))
            ).all()
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(str(artifacts[0].id), artifact["id"])
            self.assertEqual(artifacts[0].artifact_sha256, artifact["artifact_sha256"])
            self.assertEqual(artifacts[0].release_status, transfer.ACTIVE_ARTIFACT_STATUS)
        await engine.dispose()


@unittest.skipUnless(
    os.environ.get("ALPHALENS_DISPOSABLE_BOOTSTRAP_ROLLBACK_DATABASE_URL")
    and CLOSURE_PATH.exists()
    and RELEASE_PATH.exists(),
    "dedicated disposable bootstrap rollback PostgreSQL fixture is not configured",
)
class DisposableBootstrapRollbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_mid_release_failure_leaves_zero_closure_rows(self) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from unittest.mock import patch

        from app.persistence.database import create_async_engine

        url = os.environ["ALPHALENS_DISPOSABLE_BOOTSTRAP_ROLLBACK_DATABASE_URL"]
        engine = create_async_engine(url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            identity = await transfer.read_target_identity(session)
        closure, _, manifest, tables = _documents(identity["database_name"])
        manifest["target"].update(host=identity["host"], port=identity["port"])
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = transfer.hash_json(manifest)
        async with factory() as session:
            before = await _persisted_digest(session, set(tables))
        with tempfile.TemporaryDirectory() as directory:
            closure_path = Path(directory) / "closure.json"
            manifest_path = Path(directory) / "manifest.json"
            closure_path.write_text(json.dumps(closure), encoding="utf-8")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.object(
                transfer,
                "load_production_artifact",
                side_effect=RuntimeError("forced disposable failure"),
            ):
                with self.assertRaises(RuntimeError):
                    await transfer._bootstrap_release(
                        url, str(closure_path), str(manifest_path)
                    )
        async with factory() as session:
            after = await _persisted_digest(session, set(tables))
        self.assertEqual(before, after)
        await engine.dispose()


@unittest.skipUnless(
    os.environ.get("ALPHALENS_DISPOSABLE_BOOTSTRAP_CONFLICT_DATABASE_URL")
    and CLOSURE_PATH.exists()
    and RELEASE_PATH.exists(),
    "dedicated disposable bootstrap conflict PostgreSQL fixture is not configured",
)
class DisposableBootstrapConflictTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_closure_is_rejected_without_mutation(self) -> None:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.persistence.database import create_async_engine

        url = os.environ["ALPHALENS_DISPOSABLE_BOOTSTRAP_CONFLICT_DATABASE_URL"]
        engine = create_async_engine(url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            identity = await transfer.read_target_identity(session)
        closure, _, manifest, tables = _documents(identity["database_name"])
        manifest["target"].update(host=identity["host"], port=identity["port"])
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = transfer.hash_json(manifest)
        async with factory() as session:
            async with session.begin():
                for table_name in transfer._closure_table_order(set(tables)):
                    table = transfer.Base.metadata.tables[table_name]
                    for row in tables[table_name]:
                        values = transfer._closure_values(table, row)
                        if table_name == "model_inference_artifacts":
                            values["release_status"] = transfer.RETIRED_ARTIFACT_STATUS
                        await session.execute(table.insert().values(values))
        async with factory() as session:
            before = await _persisted_digest(session, set(tables))
        with tempfile.TemporaryDirectory() as directory:
            closure_path, manifest_path = await _write_bootstrap_inputs(
                directory, closure, manifest
            )
            with self.assertRaises(transfer.TransferPreflightError):
                await transfer._bootstrap_release(
                    url, closure_path, manifest_path
                )
        async with factory() as session:
            after = await _persisted_digest(session, set(tables))
        self.assertEqual(before, after)
        await engine.dispose()
