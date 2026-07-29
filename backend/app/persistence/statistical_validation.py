"""Immutable persistence for statistical validation reports."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.model_comparisons import APPROVED_EXPERIMENT_IDS
from app.persistence.models import (
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
    RegressionExperimentSplitRecord,
    StatisticalValidationReportExperimentRecord,
    StatisticalValidationReportExplainabilityRecord,
    StatisticalValidationReportRecord,
)
from app.research.statistical_validation import (
    BOOTSTRAP_RANDOM_SEED,
    BOOTSTRAP_RESAMPLES,
    CONFIDENCE_LEVEL,
    PAIRWISE_COMPARISONS,
    STATISTICAL_REPORT_VERSION,
    BuiltStatisticalValidationReport,
    ExplainabilityArtifactReference,
    FoldMetricEvidence,
    StatisticalModelSource,
    build_statistical_validation_report,
)


APPROVED_EXPLAINABILITY_ARTIFACT_IDS: tuple[UUID, ...] = (
    UUID("d019cd2a-4eca-4720-8821-7651e12c0249"),
    UUID("79ec968c-bc62-476e-b35d-427dc6acc78b"),
)


@dataclass(frozen=True, slots=True)
class PersistedStatisticalValidationReport:
    report_id: UUID
    generated_at: datetime
    built: BuiltStatisticalValidationReport
    created: bool


async def create_statistical_validation_report(
    session: AsyncSession,
) -> PersistedStatisticalValidationReport:
    async with session.begin():
        experiments = tuple(
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
        sources = await _model_sources(session, experiments)
        explainability = tuple(
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
        references = _explainability_references(explainability, sources)
        built = build_statistical_validation_report(sources, references)
        existing = (
            await session.scalars(
                select(StatisticalValidationReportRecord).where(
                    StatisticalValidationReportRecord.configuration_hash
                    == built.configuration_hash,
                    StatisticalValidationReportRecord.result_hash
                    == built.result_hash,
                )
            )
        ).one_or_none()
        if existing is not None:
            return PersistedStatisticalValidationReport(
                report_id=existing.id,
                generated_at=existing.generated_at,
                built=built,
                created=False,
            )

        first = experiments[0]
        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        session.add(
            StatisticalValidationReportRecord(
                id=report_id,
                report_version=STATISTICAL_REPORT_VERSION,
                report_configuration=built.configuration,
                report_payload=built.payload,
                configuration_hash=built.configuration_hash,
                result_hash=built.result_hash,
                model_dataset_hash=first.model_dataset_hash,
                feature_pipeline_version=first.feature_pipeline_version,
                target_version=first.target_version,
                validation_run_id=first.validation_run_id,
                split_hash=first.split_hash,
                bootstrap_random_seed=BOOTSTRAP_RANDOM_SEED,
                bootstrap_resamples=BOOTSTRAP_RESAMPLES,
                confidence_level=str(CONFIDENCE_LEVEL),
                model_count=len(experiments),
                pair_count=len(PAIRWISE_COMPARISONS),
                hypothesis_count=len(PAIRWISE_COMPARISONS) * 3,
                evaluated_fold_count=len(sources[0].folds),
                point_in_time_validated=True,
                final_holdout_evaluated=False,
                model_retraining_performed=False,
                generated_at=generated_at,
            )
        )
        await session.flush()
        session.add_all(
            [
                StatisticalValidationReportExperimentRecord(
                    report_id=report_id,
                    experiment_id=experiment.id,
                    model_family=experiment.model_family,
                )
                for experiment in experiments
            ]
        )
        session.add_all(
            [
                StatisticalValidationReportExplainabilityRecord(
                    report_id=report_id,
                    artifact_id=artifact.id,
                    model_family=artifact.model_family,
                )
                for artifact in explainability
            ]
        )
        await session.flush()

    return PersistedStatisticalValidationReport(
        report_id=report_id,
        generated_at=generated_at,
        built=built,
        created=True,
    )


async def _model_sources(
    session: AsyncSession,
    experiments: tuple[RegressionExperimentRecord, ...],
) -> tuple[StatisticalModelSource, ...]:
    by_family = {
        experiment.model_family: experiment
        for experiment in experiments
    }
    if set(by_family) != set(APPROVED_EXPERIMENT_IDS):
        raise ValueError("Approved statistical experiment set is incomplete.")

    sources: list[StatisticalModelSource] = []
    for family, approved_id in APPROVED_EXPERIMENT_IDS.items():
        experiment = by_family[family]
        if experiment.id != approved_id:
            raise ValueError(f"Approved {family} experiment ID differs.")
        rows = tuple(
            (
                await session.scalars(
                    select(RegressionExperimentSplitRecord)
                    .where(
                        RegressionExperimentSplitRecord.experiment_id
                        == experiment.id,
                        RegressionExperimentSplitRecord.status
                        == "evaluated",
                    )
                    .order_by(
                        RegressionExperimentSplitRecord.split_sequence
                    )
                )
            ).all()
        )
        if len(rows) != experiment.evaluated_split_count:
            raise ValueError(f"Approved {family} fold evidence is incomplete.")
        folds: list[FoldMetricEvidence] = []
        for row in rows:
            if (
                row.mae is None
                or row.rmse is None
                or row.directional_accuracy is None
                or row.prediction_hash is None
            ):
                raise ValueError(
                    f"Approved {family} fold metrics are incomplete."
                )
            folds.append(
                FoldMetricEvidence(
                    sequence=row.split_sequence,
                    test_start=row.test_start.isoformat(),
                    test_end=row.test_end.isoformat(),
                    mae=row.mae,
                    rmse=row.rmse,
                    directional_accuracy=row.directional_accuracy,
                    prediction_hash=row.prediction_hash,
                )
            )
        sources.append(
            StatisticalModelSource(
                experiment_id=experiment.id,
                model_family=experiment.model_family,
                configuration_hash=(
                    experiment.experiment_configuration_hash
                ),
                result_hash=experiment.result_hash,
                model_dataset_hash=experiment.model_dataset_hash,
                feature_pipeline_version=(
                    experiment.feature_pipeline_version
                ),
                target_version=experiment.target_version,
                validation_run_id=experiment.validation_run_id,
                split_hash=experiment.split_hash,
                final_holdout_evaluated=(
                    experiment.final_holdout_evaluated
                ),
                folds=tuple(folds),
            )
        )
    return tuple(sources)


def _explainability_references(
    artifacts: tuple[ModelExplainabilityArtifactRecord, ...],
    sources: tuple[StatisticalModelSource, ...],
) -> tuple[ExplainabilityArtifactReference, ...]:
    if (
        len(artifacts) != len(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
        or {artifact.id for artifact in artifacts}
        != set(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
    ):
        raise ValueError("Approved explainability artifacts are incomplete.")
    first = sources[0]
    references: list[ExplainabilityArtifactReference] = []
    for artifact in artifacts:
        if (
            artifact.final_holdout_evaluated
            or artifact.model_dataset_hash != first.model_dataset_hash
            or artifact.validation_run_id != first.validation_run_id
            or artifact.split_hash != first.split_hash
        ):
            raise ValueError("Explainability artifact provenance differs.")
        references.append(
            ExplainabilityArtifactReference(
                artifact_id=artifact.id,
                experiment_id=artifact.experiment_id,
                model_family=artifact.model_family,
                configuration_hash=artifact.configuration_hash,
                result_hash=artifact.result_hash,
            )
        )
    return tuple(references)
