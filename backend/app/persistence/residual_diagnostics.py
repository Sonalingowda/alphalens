"""Persistence orchestration for immutable residual diagnostics."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.model_comparisons import APPROVED_EXPERIMENT_IDS
from app.persistence.models import (
    ExperimentPredictionEvidenceRecord,
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
    RegressionExperimentSplitRecord,
    ResidualDiagnosticPlotRecord,
    ResidualDiagnosticsReportExperimentRecord,
    ResidualDiagnosticsReportExplainabilityRecord,
    ResidualDiagnosticsReportRecord,
    StatisticalValidationReportRecord,
)
from app.persistence.statistical_validation import (
    APPROVED_EXPLAINABILITY_ARTIFACT_IDS,
)
from app.research.dataset import build_model_ready_dataset
from app.research.residual_diagnostics import (
    RESIDUAL_DIAGNOSTICS_REPORT_VERSION,
    ArtifactReference,
    BuiltResidualDiagnosticsReport,
    ReplaySplitEvidence,
    ReplayedModelPredictions,
    ResidualExperimentSource,
    build_residual_diagnostics_report,
    decimal_value,
    replay_approved_experiment,
)


@dataclass(frozen=True, slots=True)
class PersistedResidualDiagnosticsReport:
    report_id: UUID
    generated_at: datetime
    built: BuiltResidualDiagnosticsReport
    created: bool
    prediction_evidence_created: int


async def create_residual_diagnostics_report(
    session: AsyncSession,
) -> PersistedResidualDiagnosticsReport:
    """Replay approved experiments, verify hashes, and persist diagnostics."""
    async with session.begin():
        dataset = await build_model_ready_dataset(session)
        experiments = await _approved_experiments(session)
        sources = await _experiment_sources(session, experiments)

        # No persistence occurs until every experiment and split hash matches.
        replays = tuple(
            replay_approved_experiment(dataset, source)
            for source in sources
        )

        statistical_record = (
            await session.scalars(
                select(StatisticalValidationReportRecord).where(
                    StatisticalValidationReportRecord.report_version
                    == "1.0.0",
                    StatisticalValidationReportRecord.model_dataset_hash
                    == dataset.model_dataset_hash,
                    StatisticalValidationReportRecord.validation_run_id
                    == dataset.validation_run_id,
                    StatisticalValidationReportRecord.split_hash
                    == dataset.validation_split_hash,
                    StatisticalValidationReportRecord.final_holdout_evaluated
                    .is_(False),
                )
            )
        ).one()
        explainability_records = tuple(
            (
                await session.scalars(
                    select(ModelExplainabilityArtifactRecord).where(
                        ModelExplainabilityArtifactRecord.id.in_(
                            APPROVED_EXPLAINABILITY_ARTIFACT_IDS
                        )
                    )
                )
            ).all()
        )
        explainability_references = _explainability_references(
            explainability_records,
            replays,
        )
        statistical_reference = ArtifactReference(
            artifact_id=statistical_record.id,
            artifact_type="statistical_validation_report",
            model_family=None,
            configuration_hash=statistical_record.configuration_hash,
            result_hash=statistical_record.result_hash,
        )
        built = build_residual_diagnostics_report(
            replays,
            statistical_report=statistical_reference,
            explainability_artifacts=explainability_references,
        )

        evidence_created = await _persist_or_verify_prediction_evidence(
            session,
            replays,
        )
        existing = (
            await session.scalars(
                select(ResidualDiagnosticsReportRecord).where(
                    ResidualDiagnosticsReportRecord.configuration_hash
                    == built.configuration_hash,
                    ResidualDiagnosticsReportRecord.result_hash
                    == built.result_hash,
                )
            )
        ).one_or_none()
        if existing is not None:
            await _verify_existing_report_artifacts(
                session,
                existing.id,
                built,
            )
            return PersistedResidualDiagnosticsReport(
                report_id=existing.id,
                generated_at=existing.generated_at,
                built=built,
                created=False,
                prediction_evidence_created=evidence_created,
            )

        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        first = replays[0]
        prediction_count = sum(
            len(replay.predictions) for replay in replays
        )
        verified_hash_count = sum(
            replay.verified_prediction_hash_count for replay in replays
        )
        session.add(
            ResidualDiagnosticsReportRecord(
                id=report_id,
                report_version=RESIDUAL_DIAGNOSTICS_REPORT_VERSION,
                report_configuration=built.configuration,
                report_payload=built.payload,
                configuration_hash=built.configuration_hash,
                result_hash=built.result_hash,
                statistical_validation_report_id=statistical_record.id,
                model_dataset_hash=dataset.model_dataset_hash,
                feature_pipeline_version=dataset.feature_pipeline_version,
                target_version=dataset.target_version,
                validation_run_id=dataset.validation_run_id,
                split_hash=dataset.validation_split_hash,
                model_count=len(replays),
                evaluated_split_count=(
                    first.source.evaluated_split_count
                ),
                evaluated_observation_count_per_model=len(
                    first.predictions
                ),
                prediction_evidence_count=prediction_count,
                prediction_hashes_verified=verified_hash_count,
                plot_count=len(built.plots),
                deterministic_replay_performed=True,
                experiments_modified=False,
                final_holdout_evaluated=False,
                generated_at=generated_at,
            )
        )
        await session.flush()
        session.add_all(
            [
                ResidualDiagnosticsReportExperimentRecord(
                    report_id=report_id,
                    experiment_id=replay.source.experiment_id,
                    model_family=replay.source.model_family,
                )
                for replay in replays
            ]
        )
        session.add_all(
            [
                ResidualDiagnosticsReportExplainabilityRecord(
                    report_id=report_id,
                    artifact_id=record.id,
                    model_family=record.model_family,
                )
                for record in explainability_records
            ]
        )
        experiment_ids = {
            replay.source.model_family: replay.source.experiment_id
            for replay in replays
        }
        session.add_all(
            [
                ResidualDiagnosticPlotRecord(
                    id=uuid4(),
                    report_id=report_id,
                    experiment_id=experiment_ids[artifact.model_family],
                    model_family=artifact.model_family,
                    plot_type=artifact.plot.plot_type,
                    mime_type=artifact.plot.mime_type,
                    content=artifact.plot.content,
                    content_hash=artifact.plot.content_hash,
                    generated_at=generated_at,
                )
                for artifact in built.plots
            ]
        )
        await session.flush()

    return PersistedResidualDiagnosticsReport(
        report_id=report_id,
        generated_at=generated_at,
        built=built,
        created=True,
        prediction_evidence_created=evidence_created,
    )


async def _approved_experiments(
    session: AsyncSession,
) -> tuple[RegressionExperimentRecord, ...]:
    records = tuple(
        (
            await session.scalars(
                select(RegressionExperimentRecord).where(
                    RegressionExperimentRecord.id.in_(
                        tuple(APPROVED_EXPERIMENT_IDS.values())
                    )
                )
            )
        ).all()
    )
    by_family = {record.model_family: record for record in records}
    if set(by_family) != set(APPROVED_EXPERIMENT_IDS):
        raise ValueError("Approved residual experiment set is incomplete.")
    ordered: list[RegressionExperimentRecord] = []
    for family, expected_id in APPROVED_EXPERIMENT_IDS.items():
        record = by_family[family]
        if record.id != expected_id:
            raise ValueError(f"Approved {family} experiment ID differs.")
        ordered.append(record)
    return tuple(ordered)


async def _experiment_sources(
    session: AsyncSession,
    experiments: tuple[RegressionExperimentRecord, ...],
) -> tuple[ResidualExperimentSource, ...]:
    sources: list[ResidualExperimentSource] = []
    for experiment in experiments:
        splits = tuple(
            (
                await session.scalars(
                    select(RegressionExperimentSplitRecord)
                    .where(
                        RegressionExperimentSplitRecord.experiment_id
                        == experiment.id
                    )
                    .order_by(
                        RegressionExperimentSplitRecord.split_sequence
                    )
                )
            ).all()
        )
        sources.append(
            ResidualExperimentSource(
                experiment_id=experiment.id,
                model_family=experiment.model_family,  # type: ignore[arg-type]
                model_parameters=experiment.model_parameters,
                preprocessing_parameters=(
                    experiment.preprocessing_parameters
                ),
                evaluation_policy_parameters=(
                    experiment.evaluation_policy_parameters
                ),
                random_seeds=tuple(experiment.random_seeds),
                training_pipeline_version=(
                    experiment.training_pipeline_version
                ),
                experiment_configuration_hash=(
                    experiment.experiment_configuration_hash
                ),
                experiment_result_hash=experiment.result_hash,
                model_dataset_hash=experiment.model_dataset_hash,
                feature_pipeline_version=(
                    experiment.feature_pipeline_version
                ),
                target_version=experiment.target_version,
                validation_run_id=experiment.validation_run_id,
                split_hash=experiment.split_hash,
                evaluated_split_count=experiment.evaluated_split_count,
                evaluated_observation_count=(
                    experiment.evaluated_observation_count
                ),
                final_holdout_evaluated=(
                    experiment.final_holdout_evaluated
                ),
                split_evidence=tuple(
                    ReplaySplitEvidence(
                        split_record_id=split.id,
                        sequence=split.split_sequence,
                        train_start=split.train_start,
                        train_end=split.train_end,
                        test_start=split.test_start,
                        test_end=split.test_end,
                        status=split.status,
                        train_observation_count=(
                            split.train_observation_count
                        ),
                        test_observation_count=(
                            split.test_observation_count
                        ),
                        latest_train_label_available_at=(
                            split.latest_train_label_available_at
                        ),
                        mae=split.mae,
                        rmse=split.rmse,
                        directional_accuracy=(
                            split.directional_accuracy
                        ),
                        prediction_hash=split.prediction_hash,
                    )
                    for split in splits
                ),
            )
        )
    return tuple(sources)


def _explainability_references(
    records: tuple[ModelExplainabilityArtifactRecord, ...],
    replays: tuple[ReplayedModelPredictions, ...],
) -> tuple[ArtifactReference, ...]:
    if (
        len(records) != len(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
        or {record.id for record in records}
        != set(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
    ):
        raise ValueError("Approved explainability artifacts are incomplete.")
    experiment_by_family = {
        replay.source.model_family: replay.source.experiment_id
        for replay in replays
    }
    references: list[ArtifactReference] = []
    for record in records:
        if (
            record.final_holdout_evaluated
            or experiment_by_family.get(record.model_family)
            != record.experiment_id
        ):
            raise ValueError("Explainability provenance differs.")
        references.append(
            ArtifactReference(
                artifact_id=record.id,
                artifact_type="model_explainability_artifact",
                model_family=record.model_family,
                configuration_hash=record.configuration_hash,
                result_hash=record.result_hash,
            )
        )
    return tuple(references)


async def _persist_or_verify_prediction_evidence(
    session: AsyncSession,
    replays: tuple[ReplayedModelPredictions, ...],
) -> int:
    created = 0
    for replay in replays:
        existing = tuple(
            (
                await session.scalars(
                    select(ExperimentPredictionEvidenceRecord)
                    .where(
                        ExperimentPredictionEvidenceRecord.experiment_id
                        == replay.source.experiment_id
                    )
                    .order_by(
                        ExperimentPredictionEvidenceRecord
                        .prediction_timestamp
                    )
                )
            ).all()
        )
        expected = tuple(
            sorted(
                replay.predictions,
                key=lambda item: item.prediction_timestamp,
            )
        )
        if existing:
            if len(existing) != len(expected):
                raise ValueError(
                    "Stored prediction evidence is incomplete; immutable "
                    "records will not be altered."
                )
            for stored, replayed in zip(existing, expected, strict=True):
                if (
                    stored.experiment_split_id
                    != replayed.experiment_split_id
                    or stored.split_sequence != replayed.split_sequence
                    or stored.observation_index
                    != replayed.observation_index
                    or stored.prediction_timestamp
                    != replayed.prediction_timestamp
                    or stored.actual_float_hex != replayed.actual.hex()
                    or stored.predicted_float_hex
                    != replayed.predicted.hex()
                    or stored.residual_float_hex
                    != replayed.residual.hex()
                    or stored.source_prediction_hash
                    != replayed.source_prediction_hash
                    or stored.evidence_hash != replayed.evidence_hash
                ):
                    raise ValueError(
                        "Stored immutable prediction evidence differs."
                    )
            continue

        rows = [
            ExperimentPredictionEvidenceRecord(
                experiment_id=evidence.experiment_id,
                experiment_split_id=evidence.experiment_split_id,
                model_family=evidence.model_family,
                split_sequence=evidence.split_sequence,
                observation_index=evidence.observation_index,
                prediction_timestamp=evidence.prediction_timestamp,
                actual_value=decimal_value(evidence.actual),
                predicted_value=decimal_value(evidence.predicted),
                residual_value=decimal_value(evidence.residual),
                actual_float_hex=evidence.actual.hex(),
                predicted_float_hex=evidence.predicted.hex(),
                residual_float_hex=evidence.residual.hex(),
                source_prediction_hash=(
                    evidence.source_prediction_hash
                ),
                evidence_hash=evidence.evidence_hash,
            )
            for evidence in expected
        ]
        session.add_all(rows)
        created += len(rows)
    await session.flush()
    return created


async def _verify_existing_report_artifacts(
    session: AsyncSession,
    report_id: UUID,
    built: BuiltResidualDiagnosticsReport,
) -> None:
    plots = tuple(
        (
            await session.scalars(
                select(ResidualDiagnosticPlotRecord)
                .where(ResidualDiagnosticPlotRecord.report_id == report_id)
                .order_by(
                    ResidualDiagnosticPlotRecord.model_family,
                    ResidualDiagnosticPlotRecord.plot_type,
                )
            )
        ).all()
    )
    expected = sorted(
        (
            artifact.model_family,
            artifact.plot.plot_type,
            artifact.plot.content_hash,
            artifact.plot.content,
        )
        for artifact in built.plots
    )
    observed = [
        (
            plot.model_family,
            plot.plot_type,
            plot.content_hash,
            plot.content,
        )
        for plot in plots
    ]
    if observed != expected:
        raise ValueError("Stored immutable diagnostic plots differ.")
