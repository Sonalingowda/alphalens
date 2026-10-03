"""Regression tests for the production artifact release-status contract."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import UUID

from app.inference import repository
from app.persistence.models import ModelInferenceArtifactRecord
from app import startup


class ProductionArtifactReleaseStatusTests(IsolatedAsyncioTestCase):
    def test_orm_declares_existing_release_status_column(self) -> None:
        self.assertEqual(
            ModelInferenceArtifactRecord.release_status.property.columns[0].name,
            "release_status",
        )

    async def test_loader_selects_only_active_artifact(self) -> None:
        record = self._record()
        experiment = SimpleNamespace()
        holdout = SimpleNamespace(
            id=UUID(int=3),
            final_model_selection_report_id=UUID(int=4),
        )
        selection = SimpleNamespace()
        validation = SimpleNamespace()
        session = AsyncMock()
        session.scalars.side_effect = [
            SimpleNamespace(all=lambda: [record]),
            SimpleNamespace(all=lambda: []),
        ]
        session.get.side_effect = [experiment, holdout, selection, validation]

        with (
            patch.object(repository, "verify_ridge_artifact_lineage"),
            patch.object(
                repository,
                "load_ridge_inference_artifact",
                return_value=SimpleNamespace(),
            ),
        ):
            loaded = await repository.load_production_artifact(session)

        statement = session.scalars.call_args_list[0].args[0]
        compiled = statement.compile()
        self.assertEqual(compiled.params["release_status_1"], "ACTIVE")
        self.assertEqual(loaded.artifact_id, record.id)

    async def test_loader_fails_closed_when_active_cardinality_is_wrong(self) -> None:
        for records in ([], [self._record(), self._record(UUID(int=2))]):
            session = AsyncMock()
            session.scalars.return_value = SimpleNamespace(all=lambda: records)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                await repository.load_production_artifact(session)

    async def test_startup_readiness_loads_production_artifact(self) -> None:
        artifact = SimpleNamespace(
            artifact_id=UUID(int=1),
            artifact_sha256="a" * 64,
        )
        session = AsyncMock()
        context = AsyncMock()
        context.__aenter__.return_value = session
        redis = AsyncMock()
        with (
            patch.object(
                startup,
                "load_settings",
                return_value=SimpleNamespace(
                    environment="production",
                    redis_url="redis://test",
                ),
            ),
            patch.object(startup, "session_factory", return_value=context),
            patch.object(
                startup,
                "load_production_artifact",
                new=AsyncMock(return_value=artifact),
            ) as load_artifact,
            patch.object(
                startup.RedisInfrastructure,
                "from_url",
                return_value=redis,
            ),
            patch.object(startup, "schema_is_current", new=AsyncMock(return_value=True)),
        ):
            result = await startup.verify_readiness()

        load_artifact.assert_awaited_once_with(session)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["artifact_identifier"], str(artifact.artifact_id))
        self.assertEqual(result["artifact_sha256"], artifact.artifact_sha256)

    @staticmethod
    def _record(artifact_id: UUID = UUID(int=1)) -> SimpleNamespace:
        return SimpleNamespace(
            id=artifact_id,
            selected_experiment_id=UUID(int=2),
            holdout_evaluation_report_id=UUID(int=3),
            validation_run_id=UUID(int=4),
            artifact_sha256="b" * 64,
            configuration_hash="c" * 64,
            state_sha256="d" * 64,
            model_family="ridge_regression",
            feature_pipeline_version="1.1.0",
            target_version="1.0.0",
            model_dataset_hash="e" * 64,
            training_dataset_hash="f" * 64,
            split_hash="0" * 64,
            artifact_payload={},
        )
