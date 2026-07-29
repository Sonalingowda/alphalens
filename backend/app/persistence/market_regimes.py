"""Immutable persistence for deterministic market regime analysis."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.model_comparisons import APPROVED_EXPERIMENT_IDS
from app.persistence.models import (
    ExperimentPredictionEvidenceRecord,
    MarketRegimeAnalysisReportRecord,
    MarketRegimeAssignmentRecord,
    MarketRegimePlotRecord,
    MarketRegimeReportExperimentRecord,
    MarketRegimeReportExplainabilityRecord,
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
    RegressionExperimentSplitRecord,
    ResidualDiagnosticsReportRecord,
    StatisticalValidationReportRecord,
)
from app.persistence.statistical_validation import (
    APPROVED_EXPLAINABILITY_ARTIFACT_IDS,
)
from app.research.dataset import ModelReadyDataset, build_model_ready_dataset
from app.research.market_regimes import (
    MARKET_REGIME_REPORT_VERSION,
    BuiltMarketRegimeReport,
    RegimeModelSource,
    RegimePredictionEvidence,
    ResearchArtifactReference,
    build_market_regime_report,
)


@dataclass(frozen=True, slots=True)
class PersistedMarketRegimeReport:
    report_id: UUID
    generated_at: datetime
    built: BuiltMarketRegimeReport
    created: bool


async def create_market_regime_report(
    session: AsyncSession,
) -> PersistedMarketRegimeReport:
    """Build the report from immutable development prediction evidence."""
    async with session.begin():
        dataset = await build_model_ready_dataset(session)
        experiments = await _approved_experiments(session)
        sources = await _model_sources(session, experiments, dataset)
        statistical = (
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
        residual = (
            await session.scalars(
                select(ResidualDiagnosticsReportRecord).where(
                    ResidualDiagnosticsReportRecord.report_version
                    == "1.0.0",
                    ResidualDiagnosticsReportRecord.model_dataset_hash
                    == dataset.model_dataset_hash,
                    ResidualDiagnosticsReportRecord.validation_run_id
                    == dataset.validation_run_id,
                    ResidualDiagnosticsReportRecord.split_hash
                    == dataset.validation_split_hash,
                    ResidualDiagnosticsReportRecord.final_holdout_evaluated
                    .is_(False),
                )
            )
        ).one()
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
        explainability_references = _explainability_references(
            explainability,
            sources,
        )
        built = build_market_regime_report(
            dataset,
            sources,
            statistical_report=ResearchArtifactReference(
                artifact_id=statistical.id,
                artifact_type="statistical_validation_report",
                model_family=None,
                configuration_hash=statistical.configuration_hash,
                result_hash=statistical.result_hash,
            ),
            residual_report=ResearchArtifactReference(
                artifact_id=residual.id,
                artifact_type="residual_diagnostics_report",
                model_family=None,
                configuration_hash=residual.configuration_hash,
                result_hash=residual.result_hash,
            ),
            explainability_artifacts=explainability_references,
        )
        existing = (
            await session.scalars(
                select(MarketRegimeAnalysisReportRecord).where(
                    MarketRegimeAnalysisReportRecord.configuration_hash
                    == built.configuration_hash,
                    MarketRegimeAnalysisReportRecord.result_hash
                    == built.result_hash,
                )
            )
        ).one_or_none()
        if existing is not None:
            await _verify_existing_artifacts(
                session,
                existing.id,
                built,
            )
            return PersistedMarketRegimeReport(
                report_id=existing.id,
                generated_at=existing.generated_at,
                built=built,
                created=False,
            )

        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        assignment_set_hash = built.payload[
            "regime_assignment_set_hash"
        ]
        prediction_count = sum(
            len(source.predictions) for source in sources
        )
        session.add(
            MarketRegimeAnalysisReportRecord(
                id=report_id,
                report_version=MARKET_REGIME_REPORT_VERSION,
                report_configuration=built.configuration,
                report_payload=built.payload,
                configuration_hash=built.configuration_hash,
                result_hash=built.result_hash,
                regime_assignment_set_hash=assignment_set_hash,
                statistical_validation_report_id=statistical.id,
                residual_diagnostics_report_id=residual.id,
                model_dataset_hash=dataset.model_dataset_hash,
                feature_pipeline_version=dataset.feature_pipeline_version,
                target_version=dataset.target_version,
                validation_run_id=dataset.validation_run_id,
                split_hash=dataset.validation_split_hash,
                model_count=len(sources),
                assignment_count=len(built.assignments),
                prediction_evidence_count=prediction_count,
                evaluated_split_count=sources[0].evaluated_split_count,
                plot_count=len(built.plots),
                point_in_time_validated=True,
                final_holdout_evaluated=False,
                model_retraining_performed=False,
                experiments_modified=False,
                generated_at=generated_at,
            )
        )
        await session.flush()
        session.add_all(
            [
                MarketRegimeReportExperimentRecord(
                    report_id=report_id,
                    experiment_id=source.experiment_id,
                    model_family=source.model_family,
                )
                for source in sources
            ]
        )
        session.add_all(
            [
                MarketRegimeReportExplainabilityRecord(
                    report_id=report_id,
                    artifact_id=artifact.id,
                    model_family=artifact.model_family,
                )
                for artifact in explainability
            ]
        )
        session.add_all(
            [
                MarketRegimeAssignmentRecord(
                    report_id=report_id,
                    prediction_timestamp=item.prediction_timestamp,
                    trend_regime=item.trend_regime,
                    volatility_regime=item.volatility_regime,
                    trend_spread=format(item.trend_spread, "f"),
                    bollinger_relative_width=format(
                        item.bollinger_relative_width,
                        "f",
                    ),
                    expanding_width_median=format(
                        item.expanding_width_median,
                        "f",
                    ),
                    assignment_hash=item.assignment_hash,
                )
                for item in built.assignments
            ]
        )
        experiment_ids = {
            source.model_family: source.experiment_id
            for source in sources
        }
        session.add_all(
            [
                MarketRegimePlotRecord(
                    id=uuid4(),
                    report_id=report_id,
                    experiment_id=experiment_ids[item.model_family],
                    model_family=item.model_family,
                    plot_type=item.plot.plot_type,
                    mime_type=item.plot.mime_type,
                    content=item.plot.content,
                    content_hash=item.plot.content_hash,
                    generated_at=generated_at,
                )
                for item in built.plots
            ]
        )
        await session.flush()

    return PersistedMarketRegimeReport(
        report_id=report_id,
        generated_at=generated_at,
        built=built,
        created=True,
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
        raise ValueError("Approved regime experiment set is incomplete.")
    return tuple(
        by_family[family] for family in APPROVED_EXPERIMENT_IDS
    )


async def _model_sources(
    session: AsyncSession,
    experiments: tuple[RegressionExperimentRecord, ...],
    dataset: ModelReadyDataset,
) -> tuple[RegimeModelSource, ...]:
    target_by_timestamp = {
        item.prediction_timestamp: float(item.target_value)
        for item in dataset.development_observations
    }
    sources: list[RegimeModelSource] = []
    for experiment in experiments:
        if (
            experiment.id
            != APPROVED_EXPERIMENT_IDS[experiment.model_family]
        ):
            raise ValueError("Approved experiment ID differs.")
        rows = tuple(
            (
                await session.scalars(
                    select(ExperimentPredictionEvidenceRecord)
                    .where(
                        ExperimentPredictionEvidenceRecord.experiment_id
                        == experiment.id
                    )
                    .order_by(
                        ExperimentPredictionEvidenceRecord
                        .prediction_timestamp
                    )
                )
            ).all()
        )
        splits = tuple(
            (
                await session.scalars(
                    select(RegressionExperimentSplitRecord).where(
                        RegressionExperimentSplitRecord.experiment_id
                        == experiment.id,
                        RegressionExperimentSplitRecord.status
                        == "evaluated",
                    )
                )
            ).all()
        )
        prediction_hashes = {
            split.split_sequence: split.prediction_hash for split in splits
        }
        if (
            len(rows) != experiment.evaluated_observation_count
            or len(splits) != experiment.evaluated_split_count
        ):
            raise ValueError(
                "Immutable prediction evidence coverage differs."
            )
        predictions: list[RegimePredictionEvidence] = []
        for row in rows:
            actual = float.fromhex(row.actual_float_hex)
            predicted = float.fromhex(row.predicted_float_hex)
            residual = float.fromhex(row.residual_float_hex)
            expected_actual = target_by_timestamp.get(
                row.prediction_timestamp
            )
            if (
                expected_actual is None
                or expected_actual.hex() != row.actual_float_hex
                or actual - predicted != residual
                or row.prediction_timestamp >= dataset.final_holdout_start
                or prediction_hashes.get(row.split_sequence)
                != row.source_prediction_hash
                or len(row.evidence_hash) != 64
            ):
                raise ValueError(
                    "Immutable prediction evidence failed verification."
                )
            predictions.append(
                RegimePredictionEvidence(
                    experiment_id=experiment.id,
                    model_family=experiment.model_family,  # type: ignore[arg-type]
                    split_sequence=row.split_sequence,
                    prediction_timestamp=row.prediction_timestamp,
                    actual=actual,
                    predicted=predicted,
                    residual=residual,
                    evidence_hash=row.evidence_hash,
                )
            )
        sources.append(
            RegimeModelSource(
                experiment_id=experiment.id,
                model_family=experiment.model_family,  # type: ignore[arg-type]
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
                predictions=tuple(predictions),
            )
        )
    return tuple(sources)


def _explainability_references(
    artifacts: tuple[ModelExplainabilityArtifactRecord, ...],
    sources: tuple[RegimeModelSource, ...],
) -> tuple[ResearchArtifactReference, ...]:
    if (
        len(artifacts) != len(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
        or {item.id for item in artifacts}
        != set(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
    ):
        raise ValueError("Approved explainability artifacts are incomplete.")
    experiment_ids = {
        source.model_family: source.experiment_id for source in sources
    }
    references: list[ResearchArtifactReference] = []
    for artifact in artifacts:
        if (
            artifact.final_holdout_evaluated
            or experiment_ids.get(artifact.model_family)
            != artifact.experiment_id
        ):
            raise ValueError("Explainability artifact provenance differs.")
        references.append(
            ResearchArtifactReference(
                artifact_id=artifact.id,
                artifact_type="model_explainability_artifact",
                model_family=artifact.model_family,
                configuration_hash=artifact.configuration_hash,
                result_hash=artifact.result_hash,
            )
        )
    return tuple(references)


async def _verify_existing_artifacts(
    session: AsyncSession,
    report_id: UUID,
    built: BuiltMarketRegimeReport,
) -> None:
    assignments = tuple(
        (
            await session.scalars(
                select(MarketRegimeAssignmentRecord)
                .where(MarketRegimeAssignmentRecord.report_id == report_id)
                .order_by(
                    MarketRegimeAssignmentRecord.prediction_timestamp
                )
            )
        ).all()
    )
    expected_assignments = [
        (
            item.prediction_timestamp,
            item.trend_regime,
            item.volatility_regime,
            format(item.trend_spread, "f"),
            format(item.bollinger_relative_width, "f"),
            format(item.expanding_width_median, "f"),
            item.assignment_hash,
        )
        for item in built.assignments
    ]
    observed_assignments = [
        (
            item.prediction_timestamp,
            item.trend_regime,
            item.volatility_regime,
            item.trend_spread,
            item.bollinger_relative_width,
            item.expanding_width_median,
            item.assignment_hash,
        )
        for item in assignments
    ]
    if observed_assignments != expected_assignments:
        raise ValueError("Stored immutable regime assignments differ.")
    plots = tuple(
        (
            await session.scalars(
                select(MarketRegimePlotRecord)
                .where(MarketRegimePlotRecord.report_id == report_id)
                .order_by(
                    MarketRegimePlotRecord.model_family,
                    MarketRegimePlotRecord.plot_type,
                )
            )
        ).all()
    )
    expected_plots = sorted(
        (
            item.model_family,
            item.plot.plot_type,
            item.plot.content_hash,
            item.plot.content,
        )
        for item in built.plots
    )
    observed_plots = [
        (
            item.model_family,
            item.plot_type,
            item.content_hash,
            item.content,
        )
        for item in plots
    ]
    if observed_plots != expected_plots:
        raise ValueError("Stored immutable market regime plots differ.")
