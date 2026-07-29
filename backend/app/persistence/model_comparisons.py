"""Immutable persistence for approved baseline comparison reports."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import (
    ModelComparisonReportExperimentRecord,
    ModelComparisonReportRecord,
    RegressionExperimentRecord,
)
from app.research.model_comparison import (
    APPROVED_EVALUATION_POLICY_VERSION,
    MODEL_COMPARISON_REPORT_VERSION,
    RUNTIME_EVIDENCE_STATUS,
    BuiltModelComparison,
    ComparisonSource,
    build_model_comparison,
)


APPROVED_EXPERIMENT_IDS: dict[str, UUID] = {
    "linear_regression": UUID("38c6b1f1-1684-4a57-bb57-7e1d6cda0e95"),
    "ridge_regression": UUID("c0960ae6-89df-4bf1-b0c4-631b1e1db44b"),
    "random_forest_regression": UUID(
        "50c8db70-b323-49a0-ad51-09e2cef7081a"
    ),
    "xgboost_regression": UUID(
        "ae78c39e-abef-4ec0-81df-e99d3922da6f"
    ),
}


@dataclass(frozen=True, slots=True)
class PersistedModelComparison:
    report_id: UUID
    generated_at: datetime
    report_hash: str
    payload: dict[str, Any]
    created: bool


async def create_model_comparison_report(
    session: AsyncSession,
) -> PersistedModelComparison:
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
        sources = await _comparison_sources(session, experiments)
        _validate_common_provenance(experiments)
        built = build_model_comparison(sources)

        existing = (
            await session.scalars(
                select(ModelComparisonReportRecord).where(
                    ModelComparisonReportRecord.report_hash
                    == built.report_hash
                )
            )
        ).one_or_none()
        if existing is not None:
            return PersistedModelComparison(
                report_id=existing.id,
                generated_at=existing.generated_at,
                report_hash=existing.report_hash,
                payload=existing.report_payload,
                created=False,
            )

        report_id = uuid4()
        generated_at = datetime.now(timezone.utc)
        first = experiments[0]
        session.add(
            ModelComparisonReportRecord(
                id=report_id,
                report_version=MODEL_COMPARISON_REPORT_VERSION,
                report_hash=built.report_hash,
                report_payload=built.payload,
                model_count=len(experiments),
                evaluation_policy_version=(
                    APPROVED_EVALUATION_POLICY_VERSION
                ),
                model_dataset_hash=first.model_dataset_hash,
                feature_pipeline_version=first.feature_pipeline_version,
                target_version=first.target_version,
                validation_run_id=first.validation_run_id,
                split_hash=first.split_hash,
                runtime_evidence_status=RUNTIME_EVIDENCE_STATUS,
                final_holdout_evaluated=False,
                generated_at=generated_at,
            )
        )
        await session.flush()
        session.add_all(
            [
                ModelComparisonReportExperimentRecord(
                    report_id=report_id,
                    experiment_id=experiment.id,
                    model_family=experiment.model_family,
                )
                for experiment in experiments
            ]
        )
        await session.flush()

    return PersistedModelComparison(
        report_id=report_id,
        generated_at=generated_at,
        report_hash=built.report_hash,
        payload=built.payload,
        created=True,
    )


async def _comparison_sources(
    session: AsyncSession,
    experiments: tuple[RegressionExperimentRecord, ...],
) -> tuple[ComparisonSource, ...]:
    by_family = {
        experiment.model_family: experiment
        for experiment in experiments
    }
    if set(by_family) != set(APPROVED_EXPERIMENT_IDS):
        raise ValueError("The approved baseline experiment set is incomplete.")

    sources: list[ComparisonSource] = []
    for family, approved_id in APPROVED_EXPERIMENT_IDS.items():
        experiment = by_family[family]
        if experiment.id != approved_id:
            raise ValueError(
                f"The approved {family} experiment ID does not match."
            )
        policy = experiment.evaluation_policy_parameters
        if (
            policy.get("minimum_training_observations") != 100
            or policy.get("name") != "minimum_training_observations"
        ):
            raise ValueError(
                f"The approved {family} evaluation policy is invalid."
            )
        policy_version = policy.get(
            "version",
            APPROVED_EVALUATION_POLICY_VERSION,
        )
        if policy_version != APPROVED_EVALUATION_POLICY_VERSION:
            raise ValueError(
                f"The approved {family} policy version is invalid."
            )
        matching_count = await session.scalar(
            select(func.count())
            .select_from(RegressionExperimentRecord)
            .where(
                RegressionExperimentRecord.experiment_configuration_hash
                == experiment.experiment_configuration_hash,
                RegressionExperimentRecord.result_hash
                == experiment.result_hash,
            )
        )
        sources.append(
            ComparisonSource(
                experiment_id=experiment.id,
                model_family=experiment.model_family,
                model_parameters=experiment.model_parameters,
                evaluation_policy_version=policy_version,
                training_pipeline_version=(
                    experiment.training_pipeline_version
                ),
                feature_pipeline_version=(
                    experiment.feature_pipeline_version
                ),
                target_version=experiment.target_version,
                model_dataset_hash=experiment.model_dataset_hash,
                validation_run_id=experiment.validation_run_id,
                split_hash=experiment.split_hash,
                evaluated_split_count=experiment.evaluated_split_count,
                skipped_split_count=experiment.skipped_split_count,
                evaluated_observation_count=(
                    experiment.evaluated_observation_count
                ),
                mae=experiment.aggregate_mae,
                rmse=experiment.aggregate_rmse,
                directional_accuracy=(
                    experiment.aggregate_directional_accuracy
                ),
                configuration_hash=(
                    experiment.experiment_configuration_hash
                ),
                result_hash=experiment.result_hash,
                exact_matching_experiment_count=matching_count or 0,
            )
        )
    return tuple(sources)


def _validate_common_provenance(
    experiments: tuple[RegressionExperimentRecord, ...],
) -> None:
    if len(experiments) != len(APPROVED_EXPERIMENT_IDS):
        raise ValueError("The approved baseline experiment set is incomplete.")
    first = experiments[0]
    common_fields = (
        "model_dataset_hash",
        "feature_pipeline_version",
        "target_version",
        "validation_run_id",
        "split_hash",
        "evaluated_split_count",
        "skipped_split_count",
        "evaluated_observation_count",
    )
    for experiment in experiments:
        if not experiment.point_in_time_validated:
            raise ValueError("An approved experiment is not point-in-time valid.")
        if experiment.final_holdout_evaluated:
            raise ValueError("An approved experiment evaluated the holdout.")
        if any(
            getattr(experiment, field) != getattr(first, field)
            for field in common_fields
        ):
            raise ValueError(
                "Approved experiments do not share comparison provenance."
            )
