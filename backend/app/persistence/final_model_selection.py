"""Immutable persistence for deterministic final model selection."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.model_comparisons import APPROVED_EXPERIMENT_IDS
from app.persistence.models import (
    ExperimentPredictionEvidenceRecord,
    FinalModelSelectionReportExplainabilityRecord,
    FinalModelSelectionReportExperimentRecord,
    FinalModelSelectionReportRecord,
    MarketRegimeAnalysisReportRecord,
    MarketRegimePlotRecord,
    ModelComparisonReportRecord,
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
    RegressionExperimentSplitRecord,
    ResidualDiagnosticPlotRecord,
    ResidualDiagnosticsReportRecord,
    StatisticalValidationReportRecord,
    ValidationRunRecord,
)
from app.persistence.statistical_validation import (
    APPROVED_EXPLAINABILITY_ARTIFACT_IDS,
)
from app.research.final_model_selection import (
    FINAL_MODEL_SELECTION_REPORT_VERSION,
    AutomatedTestEvidence,
    BuiltFinalModelSelectionReport,
    ImmutableArtifact,
    PredictionEvidenceSummary,
    build_final_model_selection_report,
    sha256_json,
    sha256_lines,
)


APPROVED_MODEL_COMPARISON_REPORT_ID = UUID(
    "214f9dcb-0539-41f2-bb72-fb59e9327d0f"
)
APPROVED_STATISTICAL_VALIDATION_REPORT_ID = UUID(
    "4020cdea-5193-425e-8b38-b10b60a2a470"
)
APPROVED_RESIDUAL_DIAGNOSTICS_REPORT_ID = UUID(
    "c272678b-d63b-4764-9d73-1653a03ae1b4"
)
APPROVED_MARKET_REGIME_ANALYSIS_REPORT_ID = UUID(
    "c4daf88b-4b71-4f0e-9a64-2f8cc95b318e"
)


@dataclass(frozen=True, slots=True)
class PersistedFinalModelSelectionReport:
    report_id: UUID
    generated_at: datetime
    built: BuiltFinalModelSelectionReport
    created: bool


async def create_final_model_selection_report(
    session: AsyncSession,
    *,
    test_evidence: AutomatedTestEvidence,
) -> PersistedFinalModelSelectionReport:
    """Aggregate verified immutable evidence without fitting any model."""
    async with session.begin():
        comparison_record = await _required_record(
            session,
            ModelComparisonReportRecord,
            APPROVED_MODEL_COMPARISON_REPORT_ID,
        )
        statistical_record = await _required_record(
            session,
            StatisticalValidationReportRecord,
            APPROVED_STATISTICAL_VALIDATION_REPORT_ID,
        )
        residual_record = await _required_record(
            session,
            ResidualDiagnosticsReportRecord,
            APPROVED_RESIDUAL_DIAGNOSTICS_REPORT_ID,
        )
        market_record = await _required_record(
            session,
            MarketRegimeAnalysisReportRecord,
            APPROVED_MARKET_REGIME_ANALYSIS_REPORT_ID,
        )
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
        experiments = await _approved_experiments(session)

        comparison = _comparison_artifact(comparison_record)
        statistical = _report_artifact(
            statistical_record,
            "statistical_validation_report",
        )
        residual = _report_artifact(
            residual_record,
            "residual_diagnostics_report",
        )
        market = _report_artifact(
            market_record,
            "market_regime_analysis_report",
        )
        explainability = tuple(
            _explainability_artifact(record)
            for record in explainability_records
        )
        residual_plot_count = await _verify_residual_plots(
            session,
            residual_record,
        )
        market_plot_count = await _verify_market_plots(
            session,
            market_record,
        )
        if residual_plot_count + market_plot_count != 28:
            raise ValueError("Source plot artifact coverage differs.")
        prediction_evidence = await _prediction_evidence_summaries(
            session,
            experiments,
            residual_record,
            market_record,
        )
        _validate_cross_artifact_references(
            statistical_record,
            residual_record,
            market_record,
            explainability_records,
        )
        built = build_final_model_selection_report(
            comparison=comparison,
            statistical=statistical,
            residual=residual,
            market_regime=market,
            explainability=explainability,
            prediction_evidence=prediction_evidence,
            test_evidence=test_evidence,
        )

        existing = (
            await session.scalars(
                select(FinalModelSelectionReportRecord).where(
                    FinalModelSelectionReportRecord.configuration_hash
                    == built.configuration_hash,
                    FinalModelSelectionReportRecord.result_hash
                    == built.result_hash,
                )
            )
        ).one_or_none()
        if existing is not None:
            await _verify_existing_report(
                session,
                existing,
                built,
                experiments,
                explainability_records,
            )
            return PersistedFinalModelSelectionReport(
                report_id=existing.id,
                generated_at=existing.generated_at,
                built=built,
                created=False,
            )

        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        provenance = built.payload["provenance"]
        verification = built.payload["verification"]
        session.add(
            FinalModelSelectionReportRecord(
                id=report_id,
                report_version=FINAL_MODEL_SELECTION_REPORT_VERSION,
                report_configuration=built.configuration,
                report_payload=built.payload,
                configuration_hash=built.configuration_hash,
                result_hash=built.result_hash,
                model_comparison_report_id=comparison_record.id,
                statistical_validation_report_id=statistical_record.id,
                residual_diagnostics_report_id=residual_record.id,
                market_regime_analysis_report_id=market_record.id,
                selected_experiment_id=built.selected_experiment_id,
                selected_model_family=built.selected_model_family,
                selected_model_rank=1,
                model_dataset_hash=provenance["model_dataset_hash"],
                feature_pipeline_version=provenance[
                    "feature_pipeline_version"
                ],
                target_version=provenance["target_version"],
                validation_run_id=UUID(provenance["validation_run_id"]),
                split_hash=provenance["split_hash"],
                model_count=verification["model_count"],
                source_artifact_count=verification[
                    "source_artifact_count"
                ],
                source_plot_hash_count=verification[
                    "source_plot_hash_count"
                ],
                prediction_evidence_count=verification[
                    "prediction_evidence_count"
                ],
                prediction_hashes_verified=verification[
                    "prediction_hashes_verified"
                ],
                automated_test_count=test_evidence.tests_run,
                artifact_hashes_verified=True,
                repeatability_verified=True,
                automated_tests_passed=True,
                point_in_time_validated=True,
                final_holdout_evaluated=False,
                model_retraining_performed=False,
                experiments_modified=False,
                new_experimental_evidence_created=False,
                generated_at=generated_at,
            )
        )
        await session.flush()
        session.add_all(
            [
                FinalModelSelectionReportExperimentRecord(
                    report_id=report_id,
                    experiment_id=record.id,
                    model_family=record.model_family,
                )
                for record in experiments
            ]
        )
        session.add_all(
            [
                FinalModelSelectionReportExplainabilityRecord(
                    report_id=report_id,
                    artifact_id=record.id,
                    model_family=record.model_family,
                )
                for record in explainability_records
            ]
        )
        await session.flush()

    return PersistedFinalModelSelectionReport(
        report_id=report_id,
        generated_at=generated_at,
        built=built,
        created=True,
    )


async def _required_record(
    session: AsyncSession,
    model: type,
    record_id: UUID,
):
    record = await session.get(model, record_id)
    if record is None:
        raise ValueError(f"Required immutable artifact {record_id} is absent.")
    return record


def _comparison_artifact(
    record: ModelComparisonReportRecord,
) -> ImmutableArtifact:
    verified = (
        record.report_version == "1.0.0"
        and sha256_json(record.report_payload) == record.report_hash
        and not record.final_holdout_evaluated
    )
    return ImmutableArtifact(
        artifact_id=record.id,
        artifact_type="model_comparison_report",
        report_version=record.report_version,
        configuration_hash=None,
        result_hash=record.report_hash,
        payload=record.report_payload,
        hash_verified=verified,
    )


def _report_artifact(
    record: (
        StatisticalValidationReportRecord
        | ResidualDiagnosticsReportRecord
        | MarketRegimeAnalysisReportRecord
    ),
    artifact_type: str,
) -> ImmutableArtifact:
    verified = (
        record.report_version == "1.0.0"
        and sha256_json(record.report_configuration)
        == record.configuration_hash
        and sha256_json(record.report_payload) == record.result_hash
        and not record.final_holdout_evaluated
    )
    return ImmutableArtifact(
        artifact_id=record.id,
        artifact_type=artifact_type,
        report_version=record.report_version,
        configuration_hash=record.configuration_hash,
        result_hash=record.result_hash,
        payload=record.report_payload,
        hash_verified=verified,
    )


def _explainability_artifact(
    record: ModelExplainabilityArtifactRecord,
) -> ImmutableArtifact:
    verified = (
        record.report_version == "1.0.0"
        and sha256_json(record.method_configuration)
        == record.configuration_hash
        and sha256_json(record.artifact_payload) == record.result_hash
        and record.point_in_time_validated
        and not record.final_holdout_evaluated
    )
    return ImmutableArtifact(
        artifact_id=record.id,
        artifact_type="model_explainability_artifact",
        report_version=record.report_version,
        configuration_hash=record.configuration_hash,
        result_hash=record.result_hash,
        payload=record.artifact_payload,
        hash_verified=verified,
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
        raise ValueError("Approved experiment registry is incomplete.")
    ordered: list[RegressionExperimentRecord] = []
    for family, experiment_id in APPROVED_EXPERIMENT_IDS.items():
        record = by_family[family]
        if (
            record.id != experiment_id
            or not record.point_in_time_validated
            or record.final_holdout_evaluated
        ):
            raise ValueError(f"Approved {family} experiment differs.")
        ordered.append(record)
    return tuple(ordered)


async def _prediction_evidence_summaries(
    session: AsyncSession,
    experiments: tuple[RegressionExperimentRecord, ...],
    residual: ResidualDiagnosticsReportRecord,
    market: MarketRegimeAnalysisReportRecord,
) -> tuple[PredictionEvidenceSummary, ...]:
    validation = await session.get(
        ValidationRunRecord,
        residual.validation_run_id,
    )
    if validation is None:
        raise ValueError("Approved validation run is absent.")
    summaries: list[PredictionEvidenceSummary] = []
    for experiment in experiments:
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
            or any(value is None for value in prediction_hashes.values())
        ):
            raise ValueError(
                f"{experiment.model_family} prediction coverage differs."
            )
        for row in rows:
            actual = float.fromhex(row.actual_float_hex)
            predicted = float.fromhex(row.predicted_float_hex)
            residual_value = float.fromhex(row.residual_float_hex)
            if (
                actual - predicted != residual_value
                or row.prediction_timestamp
                >= validation.final_holdout_start
                or prediction_hashes.get(row.split_sequence)
                != row.source_prediction_hash
                or len(row.evidence_hash) != 64
            ):
                raise ValueError(
                    f"{experiment.model_family} prediction hash differs."
                )
        evidence_set_hash = sha256_lines(
            tuple(row.evidence_hash for row in rows)
        )
        residual_hash = residual.report_payload["model_diagnostics"][
            experiment.model_family
        ]["prediction_evidence_set_hash"]
        market_hash = market.report_payload["model_regime_analysis"][
            experiment.model_family
        ]["prediction_evidence_set_hash"]
        if evidence_set_hash != residual_hash or evidence_set_hash != market_hash:
            raise ValueError(
                f"{experiment.model_family} evidence-set hash differs."
            )
        summaries.append(
            PredictionEvidenceSummary(
                model_family=experiment.model_family,
                observation_count=len(rows),
                prediction_hash_count=len(splits),
                evidence_set_hash=evidence_set_hash,
                hashes_verified=True,
            )
        )
    return tuple(summaries)


async def _verify_residual_plots(
    session: AsyncSession,
    report: ResidualDiagnosticsReportRecord,
) -> int:
    records = tuple(
        (
            await session.scalars(
                select(ResidualDiagnosticPlotRecord).where(
                    ResidualDiagnosticPlotRecord.report_id == report.id
                )
            )
        ).all()
    )
    return _verify_plots(records, report.report_payload["plot_manifest"])


async def _verify_market_plots(
    session: AsyncSession,
    report: MarketRegimeAnalysisReportRecord,
) -> int:
    records = tuple(
        (
            await session.scalars(
                select(MarketRegimePlotRecord).where(
                    MarketRegimePlotRecord.report_id == report.id
                )
            )
        ).all()
    )
    return _verify_plots(records, report.report_payload["plot_manifest"])


def _verify_plots(records: tuple, manifest: list[dict]) -> int:
    stored = {
        (
            record.model_family,
            record.plot_type,
            record.mime_type,
            record.content_hash,
        )
        for record in records
        if sha256(record.content.encode()).hexdigest()
        == record.content_hash
    }
    declared = {
        (
            item["model_family"],
            item["plot_type"],
            item["mime_type"],
            item["content_hash"],
        )
        for item in manifest
    }
    if stored != declared or len(stored) != len(records):
        raise ValueError("Immutable SVG artifact verification failed.")
    return len(records)


def _validate_cross_artifact_references(
    statistical: StatisticalValidationReportRecord,
    residual: ResidualDiagnosticsReportRecord,
    market: MarketRegimeAnalysisReportRecord,
    explainability: tuple[ModelExplainabilityArtifactRecord, ...],
) -> None:
    common = (
        "model_dataset_hash",
        "feature_pipeline_version",
        "target_version",
        "validation_run_id",
        "split_hash",
    )
    if any(
        getattr(residual, name) != getattr(statistical, name)
        or getattr(market, name) != getattr(statistical, name)
        for name in common
    ):
        raise ValueError("Immutable source report provenance differs.")
    if (
        residual.statistical_validation_report_id != statistical.id
        or market.statistical_validation_report_id != statistical.id
        or market.residual_diagnostics_report_id != residual.id
        or {
            record.id for record in explainability
        }
        != set(APPROVED_EXPLAINABILITY_ARTIFACT_IDS)
    ):
        raise ValueError("Immutable source artifact links differ.")
    for record in explainability:
        if any(
            getattr(record, name) != getattr(statistical, name)
            for name in common
        ):
            raise ValueError("Explainability provenance differs.")


async def _verify_existing_report(
    session: AsyncSession,
    existing: FinalModelSelectionReportRecord,
    built: BuiltFinalModelSelectionReport,
    experiments: tuple[RegressionExperimentRecord, ...],
    explainability: tuple[ModelExplainabilityArtifactRecord, ...],
) -> None:
    if (
        sha256_json(existing.report_configuration)
        != built.configuration_hash
        or sha256_json(existing.report_payload) != built.result_hash
        or existing.selected_experiment_id
        != built.selected_experiment_id
        or existing.selected_model_family
        != built.selected_model_family
    ):
        raise ValueError("Stored final selection report differs.")
    experiment_links = tuple(
        (
            await session.scalars(
                select(FinalModelSelectionReportExperimentRecord).where(
                    FinalModelSelectionReportExperimentRecord.report_id
                    == existing.id
                )
            )
        ).all()
    )
    explainability_links = tuple(
        (
            await session.scalars(
                select(
                    FinalModelSelectionReportExplainabilityRecord
                ).where(
                    FinalModelSelectionReportExplainabilityRecord.report_id
                    == existing.id
                )
            )
        ).all()
    )
    if (
        {item.experiment_id for item in experiment_links}
        != {item.id for item in experiments}
        or {item.artifact_id for item in explainability_links}
        != {item.id for item in explainability}
    ):
        raise ValueError("Stored final selection provenance links differ.")
