"""Atomic persistence for the one-time official holdout evaluation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.final_model_selection import (
    APPROVED_MARKET_REGIME_ANALYSIS_REPORT_ID,
    APPROVED_MODEL_COMPARISON_REPORT_ID,
    APPROVED_RESIDUAL_DIAGNOSTICS_REPORT_ID,
    APPROVED_STATISTICAL_VALIDATION_REPORT_ID,
)
from app.persistence.models import (
    CandleRecord,
    EngineeredFeatureRecord,
    ExperimentPredictionEvidenceRecord,
    FinalModelSelectionReportRecord,
    ForwardLogReturnTargetRecord,
    HoldoutConsumptionRecord,
    HoldoutEvaluationReportRecord,
    HoldoutPredictionEvidenceRecord,
    MarketRegimeAnalysisReportRecord,
    ModelComparisonReportRecord,
    ModelExplainabilityArtifactRecord,
    RegressionExperimentRecord,
    ResidualDiagnosticsReportRecord,
    StatisticalValidationReportRecord,
    ValidationRunRecord,
)
from app.persistence.residual_diagnostics import _experiment_sources
from app.persistence.statistical_validation import (
    APPROVED_EXPLAINABILITY_ARTIFACT_IDS,
)
from app.research.dataset import (
    MODEL_FEATURE_NAMES,
    ModelObservation,
    build_model_ready_dataset,
)
from app.research.final_model_selection import sha256_json, sha256_lines
from app.research.holdout_evaluation import (
    HOLDOUT_EVALUATION_REPORT_VERSION,
    DevelopmentResidualEvidence,
    SelectedRidgeSpecification,
    SourceArtifactReference,
    build_holdout_evaluation_report,
    decimal_value,
    evaluate_official_holdout,
)
from app.research.residual_diagnostics import replay_approved_experiment
from app.validation.splits import (
    WalkForwardConfig,
    access_final_holdout,
)


APPROVED_FINAL_MODEL_SELECTION_REPORT_ID = UUID(
    "bf852165-d97a-4872-8ee9-9f4e0df26d68"
)
APPROVED_SELECTED_RIDGE_EXPERIMENT_ID = UUID(
    "c0960ae6-89df-4bf1-b0c4-631b1e1db44b"
)


@dataclass(frozen=True, slots=True)
class PersistedHoldoutEvaluationReport:
    report_id: UUID
    generated_at: datetime
    configuration_hash: str
    result_hash: str
    payload: dict
    created: bool
    holdout_access_performed: bool


async def create_official_holdout_evaluation_report(
    session: AsyncSession,
) -> PersistedHoldoutEvaluationReport:
    """Evaluate once, then make all subsequent calls read-only verification."""
    async with session.begin():
        selection = await _required_record(
            session,
            FinalModelSelectionReportRecord,
            APPROVED_FINAL_MODEL_SELECTION_REPORT_ID,
        )
        if (
            selection.selected_experiment_id
            != APPROVED_SELECTED_RIDGE_EXPERIMENT_ID
            or selection.selected_model_family != "ridge_regression"
            or selection.final_holdout_evaluated
            or sha256_json(selection.report_configuration)
            != selection.configuration_hash
            or sha256_json(selection.report_payload)
            != selection.result_hash
        ):
            raise ValueError("Approved final model selection differs.")
        validation = (
            await session.scalars(
                select(ValidationRunRecord)
                .where(
                    ValidationRunRecord.id
                    == selection.validation_run_id
                )
                .with_for_update()
            )
        ).one()
        consumption = await session.get(
            HoldoutConsumptionRecord,
            validation.id,
        )
        if consumption is not None:
            return await _load_consumed_report(
                session,
                consumption,
            )

        selected_experiment = await _required_record(
            session,
            RegressionExperimentRecord,
            APPROVED_SELECTED_RIDGE_EXPERIMENT_ID,
        )
        source_records = await _source_records(session)
        source_artifacts = _verified_source_artifacts(
            selection,
            source_records,
        )
        dataset = await build_model_ready_dataset(session)
        if (
            dataset.validation_run_id != validation.id
            or validation.purge_gap_size != 50
            or validation.final_holdout_size != 10
        ):
            raise ValueError("Registered holdout configuration differs.")

        replay_source = (
            await _experiment_sources(
                session,
                (selected_experiment,),
            )
        )[0]
        replay = replay_approved_experiment(dataset, replay_source)
        development_residuals = await _development_residual_evidence(
            session,
            replay,
            source_records["residual"],
        )
        registered_timestamps, holdout_observations = (
            await _load_authorized_holdout(
                session,
                dataset,
                validation,
            )
        )
        selected = _selected_specification(selected_experiment)
        evaluated = evaluate_official_holdout(
            dataset=dataset,
            selected=selected,
            development_residuals=development_residuals,
            registered_holdout_timestamps=registered_timestamps,
            holdout_observations=holdout_observations,
            purge_gap_size=validation.purge_gap_size,
            source_artifacts=source_artifacts,
        )
        first_build = build_holdout_evaluation_report(
            dataset=dataset,
            selected=selected,
            development_residuals=development_residuals,
            evaluated=evaluated,
        )
        repeated_build = build_holdout_evaluation_report(
            dataset=dataset,
            selected=selected,
            development_residuals=development_residuals,
            evaluated=evaluated,
        )
        if (
            first_build.configuration_hash
            != repeated_build.configuration_hash
            or first_build.result_hash != repeated_build.result_hash
        ):
            raise ValueError("Holdout report construction is not repeatable.")

        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        report = HoldoutEvaluationReportRecord(
            id=report_id,
            report_version=HOLDOUT_EVALUATION_REPORT_VERSION,
            report_configuration=first_build.configuration,
            report_payload=first_build.payload,
            configuration_hash=first_build.configuration_hash,
            result_hash=first_build.result_hash,
            selected_experiment_id=selected_experiment.id,
            final_model_selection_report_id=selection.id,
            model_comparison_report_id=source_records["comparison"].id,
            statistical_validation_report_id=source_records[
                "statistical"
            ].id,
            residual_diagnostics_report_id=source_records["residual"].id,
            market_regime_analysis_report_id=source_records["market"].id,
            selected_model_family="ridge_regression",
            model_dataset_hash=dataset.model_dataset_hash,
            holdout_dataset_hash=evaluated.holdout_dataset_hash,
            training_dataset_hash=evaluated.training_dataset_hash,
            feature_pipeline_version=dataset.feature_pipeline_version,
            target_version=dataset.target_version,
            validation_run_id=validation.id,
            split_hash=dataset.validation_split_hash,
            registered_holdout_start=validation.final_holdout_start,
            registered_holdout_end=validation.final_holdout_end,
            first_evaluated_timestamp=(
                evaluated.first_evaluated_timestamp
            ),
            last_evaluated_timestamp=evaluated.last_evaluated_timestamp,
            registered_holdout_observation_count=(
                evaluated.registered_holdout_observation_count
            ),
            eligible_holdout_observation_count=(
                evaluated.eligible_holdout_observation_count
            ),
            excluded_missing_target_count=(
                evaluated.excluded_missing_target_count
            ),
            final_training_observation_count=(
                evaluated.training_observation_count
            ),
            purged_observation_count=evaluated.purged_observation_count,
            development_prediction_hashes_verified=(
                development_residuals
                .verified_split_prediction_hash_count
            ),
            development_prediction_evidence_count=(
                development_residuals.prediction_evidence_count
            ),
            development_prediction_evidence_set_hash=(
                development_residuals.prediction_evidence_set_hash
            ),
            holdout_prediction_hash=evaluated.holdout_prediction_hash,
            holdout_prediction_evidence_count=len(
                evaluated.predictions
            ),
            holdout_prediction_evidence_set_hash=(
                evaluated.prediction_evidence_set_hash
            ),
            source_artifact_count=len(source_artifacts),
            official_holdout_evaluation=True,
            holdout_evaluated=True,
            holdout_consumed=True,
            development_prediction_hashes_match=True,
            artifact_hashes_verified=True,
            model_parameters_modified=False,
            feature_engineering_performed=False,
            hyperparameter_tuning_performed=False,
            experiments_modified=False,
            generated_at=generated_at,
        )
        session.add(report)
        await session.flush()
        session.add_all(
            [
                HoldoutPredictionEvidenceRecord(
                    report_id=report_id,
                    observation_index=item.observation_index,
                    prediction_timestamp=item.prediction_timestamp,
                    label_available_at=item.label_available_at,
                    actual_value=decimal_value(item.actual),
                    predicted_value=decimal_value(item.predicted),
                    residual_value=decimal_value(item.residual),
                    actual_float_hex=item.actual.hex(),
                    predicted_float_hex=item.predicted.hex(),
                    residual_float_hex=item.residual.hex(),
                    evidence_hash=item.evidence_hash,
                    created_at=generated_at,
                )
                for item in evaluated.predictions
            ]
        )
        session.add(
            HoldoutConsumptionRecord(
                validation_run_id=validation.id,
                holdout_evaluation_report_id=report_id,
                selected_experiment_id=selected_experiment.id,
                purpose="official_final_evaluation",
                official=True,
                irreversible=True,
                consumed_at=generated_at,
            )
        )
        await session.flush()

    return PersistedHoldoutEvaluationReport(
        report_id=report_id,
        generated_at=generated_at,
        configuration_hash=first_build.configuration_hash,
        result_hash=first_build.result_hash,
        payload=first_build.payload,
        created=True,
        holdout_access_performed=True,
    )


async def _load_consumed_report(
    session: AsyncSession,
    consumption: HoldoutConsumptionRecord,
) -> PersistedHoldoutEvaluationReport:
    report = await _required_record(
        session,
        HoldoutEvaluationReportRecord,
        consumption.holdout_evaluation_report_id,
    )
    evidence = tuple(
        (
            await session.scalars(
                select(HoldoutPredictionEvidenceRecord)
                .where(
                    HoldoutPredictionEvidenceRecord.report_id
                    == report.id
                )
                .order_by(
                    HoldoutPredictionEvidenceRecord.observation_index
                )
            )
        ).all()
    )
    evidence_set_hash = sha256_lines(
        tuple(item.evidence_hash for item in evidence)
    )
    if (
        sha256_json(report.report_configuration)
        != report.configuration_hash
        or sha256_json(report.report_payload) != report.result_hash
        or len(evidence) != report.holdout_prediction_evidence_count
        or evidence_set_hash
        != report.holdout_prediction_evidence_set_hash
        or not consumption.official
        or not consumption.irreversible
    ):
        raise ValueError("Consumed holdout evidence failed verification.")
    return PersistedHoldoutEvaluationReport(
        report_id=report.id,
        generated_at=report.generated_at,
        configuration_hash=report.configuration_hash,
        result_hash=report.result_hash,
        payload=report.report_payload,
        created=False,
        holdout_access_performed=False,
    )


async def _source_records(
    session: AsyncSession,
) -> dict[str, object]:
    return {
        "comparison": await _required_record(
            session,
            ModelComparisonReportRecord,
            APPROVED_MODEL_COMPARISON_REPORT_ID,
        ),
        "statistical": await _required_record(
            session,
            StatisticalValidationReportRecord,
            APPROVED_STATISTICAL_VALIDATION_REPORT_ID,
        ),
        "residual": await _required_record(
            session,
            ResidualDiagnosticsReportRecord,
            APPROVED_RESIDUAL_DIAGNOSTICS_REPORT_ID,
        ),
        "market": await _required_record(
            session,
            MarketRegimeAnalysisReportRecord,
            APPROVED_MARKET_REGIME_ANALYSIS_REPORT_ID,
        ),
        "explainability": tuple(
            (
                await session.scalars(
                    select(ModelExplainabilityArtifactRecord).where(
                        ModelExplainabilityArtifactRecord.id.in_(
                            APPROVED_EXPLAINABILITY_ARTIFACT_IDS
                        )
                    )
                )
            ).all()
        ),
    }


def _verified_source_artifacts(
    selection: FinalModelSelectionReportRecord,
    records: dict[str, object],
) -> tuple[SourceArtifactReference, ...]:
    comparison = records["comparison"]
    statistical = records["statistical"]
    residual = records["residual"]
    market = records["market"]
    explainability = records["explainability"]
    if not isinstance(comparison, ModelComparisonReportRecord):
        raise TypeError
    if not isinstance(statistical, StatisticalValidationReportRecord):
        raise TypeError
    if not isinstance(residual, ResidualDiagnosticsReportRecord):
        raise TypeError
    if not isinstance(market, MarketRegimeAnalysisReportRecord):
        raise TypeError
    if not isinstance(explainability, tuple):
        raise TypeError
    verified = (
        sha256_json(comparison.report_payload) == comparison.report_hash
        and sha256_json(statistical.report_configuration)
        == statistical.configuration_hash
        and sha256_json(statistical.report_payload)
        == statistical.result_hash
        and sha256_json(residual.report_configuration)
        == residual.configuration_hash
        and sha256_json(residual.report_payload) == residual.result_hash
        and sha256_json(market.report_configuration)
        == market.configuration_hash
        and sha256_json(market.report_payload) == market.result_hash
        and len(explainability) == 2
        and all(
            isinstance(item, ModelExplainabilityArtifactRecord)
            and sha256_json(item.method_configuration)
            == item.configuration_hash
            and sha256_json(item.artifact_payload) == item.result_hash
            for item in explainability
        )
    )
    if not verified:
        raise ValueError("A required source artifact hash differs.")
    references = [
        SourceArtifactReference(
            artifact_id=comparison.id,
            artifact_type="model_comparison_report",
            configuration_hash=None,
            result_hash=comparison.report_hash,
        ),
        SourceArtifactReference(
            artifact_id=statistical.id,
            artifact_type="statistical_validation_report",
            configuration_hash=statistical.configuration_hash,
            result_hash=statistical.result_hash,
        ),
        SourceArtifactReference(
            artifact_id=residual.id,
            artifact_type="residual_diagnostics_report",
            configuration_hash=residual.configuration_hash,
            result_hash=residual.result_hash,
        ),
        SourceArtifactReference(
            artifact_id=market.id,
            artifact_type="market_regime_analysis_report",
            configuration_hash=market.configuration_hash,
            result_hash=market.result_hash,
        ),
        SourceArtifactReference(
            artifact_id=selection.id,
            artifact_type="final_model_selection_report",
            configuration_hash=selection.configuration_hash,
            result_hash=selection.result_hash,
        ),
    ]
    for item in explainability:
        if not isinstance(item, ModelExplainabilityArtifactRecord):
            raise TypeError
        references.append(
            SourceArtifactReference(
                artifact_id=item.id,
                artifact_type=(
                    f"{item.model_family.removesuffix('_regression')}"
                    "_explainability_artifact"
                ),
                configuration_hash=item.configuration_hash,
                result_hash=item.result_hash,
            )
        )
    return tuple(references)


async def _development_residual_evidence(
    session: AsyncSession,
    replay,
    residual_record: object,
) -> DevelopmentResidualEvidence:
    if not isinstance(
        residual_record,
        ResidualDiagnosticsReportRecord,
    ):
        raise TypeError
    rows = tuple(
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
    replay_hash = sha256_lines(
        tuple(item.evidence_hash for item in replay.predictions)
    )
    stored_hash = sha256_lines(
        tuple(item.evidence_hash for item in rows)
    )
    diagnostic = residual_record.report_payload["model_diagnostics"][
        "ridge_regression"
    ]
    expected_hash = diagnostic["prediction_evidence_set_hash"]
    if (
        replay.verified_prediction_hash_count
        != replay.source.evaluated_split_count
        or len(replay.predictions)
        != replay.source.evaluated_observation_count
        or len(rows) != len(replay.predictions)
        or replay_hash != stored_hash
        or stored_hash != expected_hash
    ):
        raise ValueError(
            "Regenerated development prediction evidence differs."
        )
    distribution = diagnostic["residual_distribution"]
    return DevelopmentResidualEvidence(
        mean_residual=Decimal(distribution["mean"]),
        residual_variance=Decimal(
            distribution["sample_variance"]
        ),
        prediction_evidence_set_hash=stored_hash,
        verified_split_prediction_hash_count=(
            replay.verified_prediction_hash_count
        ),
        prediction_evidence_count=len(rows),
    )


async def _load_authorized_holdout(
    session: AsyncSession,
    dataset,
    validation: ValidationRunRecord,
) -> tuple[tuple[datetime, ...], tuple[ModelObservation, ...]]:
    all_timestamps = tuple(
        (
            await session.scalars(
                select(CandleRecord.candle_timestamp)
                .where(
                    CandleRecord.asset_identifier == "BTC",
                    CandleRecord.quote_currency == "USD",
                    CandleRecord.timeframe == "1d",
                    CandleRecord.is_complete.is_(True),
                )
                .order_by(CandleRecord.candle_timestamp)
            )
        ).all()
    )
    registered = access_final_holdout(
        all_timestamps,
        WalkForwardConfig(
            minimum_train_size=validation.minimum_train_size,
            test_size=validation.test_size,
            step_size=validation.step_size,
            purge_gap_size=validation.purge_gap_size,
            final_holdout_size=validation.final_holdout_size,
        ),
        acknowledge_final_evaluation=True,
    )
    if (
        registered[0] != validation.final_holdout_start
        or registered[-1] != validation.final_holdout_end
    ):
        raise ValueError("Explicit holdout access boundaries differ.")
    feature_rows = (
        await session.execute(
            select(
                EngineeredFeatureRecord.candle_timestamp,
                EngineeredFeatureRecord.feature_name,
                EngineeredFeatureRecord.feature_value,
            )
            .where(
                EngineeredFeatureRecord.computation_run_id
                == dataset.source_feature_run_id,
                EngineeredFeatureRecord.candle_timestamp.in_(registered),
            )
            .order_by(
                EngineeredFeatureRecord.candle_timestamp,
                EngineeredFeatureRecord.feature_name,
            )
        )
    ).all()
    target_rows = tuple(
        (
            await session.scalars(
                select(ForwardLogReturnTargetRecord)
                .where(
                    ForwardLogReturnTargetRecord.generation_run_id
                    == dataset.source_target_run_id,
                    ForwardLogReturnTargetRecord.prediction_timestamp
                    .in_(registered),
                )
                .order_by(
                    ForwardLogReturnTargetRecord.prediction_timestamp
                )
            )
        ).all()
    )
    features: dict[datetime, dict[str, Decimal]] = {}
    for timestamp, name, value in feature_rows:
        features.setdefault(timestamp, {})[name] = value
    targets = {item.prediction_timestamp: item for item in target_rows}
    observations: list[ModelObservation] = []
    for timestamp in registered:
        target = targets.get(timestamp)
        if target is None:
            continue
        values = features.get(timestamp)
        if (
            values is None
            or tuple(sorted(values)) != MODEL_FEATURE_NAMES
            or target.label_available_at > validation.final_holdout_end
            or target.source_ingestion_batch_id
            != dataset.source_ingestion_batch_id
            or target.source_feature_run_id
            != dataset.source_feature_run_id
            or target.dataset_hash != dataset.source_dataset_hash
        ):
            raise ValueError(
                "An eligible holdout observation is incomplete."
            )
        observations.append(
            ModelObservation(
                prediction_timestamp=timestamp,
                label_available_at=target.label_available_at,
                feature_values=tuple(
                    values[name] for name in MODEL_FEATURE_NAMES
                ),
                target_value=target.target_value,
            )
        )
    return registered, tuple(observations)


def _selected_specification(
    record: RegressionExperimentRecord,
) -> SelectedRidgeSpecification:
    return SelectedRidgeSpecification(
        experiment_id=record.id,
        model_family=record.model_family,
        model_parameters=record.model_parameters,
        preprocessing_parameters=record.preprocessing_parameters,
        evaluation_policy_parameters=(
            record.evaluation_policy_parameters
        ),
        training_pipeline_version=record.training_pipeline_version,
        experiment_configuration_hash=(
            record.experiment_configuration_hash
        ),
        experiment_result_hash=record.result_hash,
        model_dataset_hash=record.model_dataset_hash,
        feature_pipeline_version=record.feature_pipeline_version,
        target_version=record.target_version,
        validation_run_id=record.validation_run_id,
        split_hash=record.split_hash,
        development_mae=record.aggregate_mae,
        development_rmse=record.aggregate_rmse,
        development_directional_accuracy=(
            record.aggregate_directional_accuracy
        ),
    )


async def _required_record(
    session: AsyncSession,
    model: type,
    record_id: UUID,
):
    record = await session.get(model, record_id)
    if record is None:
        raise ValueError(f"Required immutable record {record_id} is absent.")
    return record
