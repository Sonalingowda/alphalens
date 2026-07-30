"""Create immutable official holdout evaluation evidence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0018"
down_revision: str | None = "20260729_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "holdout_evaluation_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_version", sa.String(length=32), nullable=False),
        sa.Column(
            "report_configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("selected_experiment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "final_model_selection_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("model_comparison_report_id", sa.Uuid(), nullable=False),
        sa.Column(
            "statistical_validation_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "residual_diagnostics_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "market_regime_analysis_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "selected_model_family",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("holdout_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("training_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "registered_holdout_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "registered_holdout_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "first_evaluated_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_evaluated_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "registered_holdout_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "eligible_holdout_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "excluded_missing_target_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "final_training_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "purged_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "development_prediction_hashes_verified",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "development_prediction_evidence_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "development_prediction_evidence_set_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "holdout_prediction_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "holdout_prediction_evidence_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "holdout_prediction_evidence_set_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("source_artifact_count", sa.Integer(), nullable=False),
        sa.Column(
            "official_holdout_evaluation",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column("holdout_consumed", sa.Boolean(), nullable=False),
        sa.Column(
            "development_prediction_hashes_match",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "artifact_hashes_verified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "model_parameters_modified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "feature_engineering_performed",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "hyperparameter_tuning_performed",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("experiments_modified", sa.Boolean(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "selected_model_family = 'ridge_regression' "
                "AND registered_holdout_observation_count = 10 "
                "AND eligible_holdout_observation_count > 0 "
                "AND excluded_missing_target_count = "
                "registered_holdout_observation_count "
                "- eligible_holdout_observation_count "
                "AND final_training_observation_count >= 100 "
                "AND purged_observation_count = 50 "
                "AND development_prediction_hashes_verified > 0 "
                "AND development_prediction_evidence_count > 0 "
                "AND holdout_prediction_evidence_count = "
                "eligible_holdout_observation_count "
                "AND source_artifact_count = 7 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(holdout_dataset_hash) = 64 "
                "AND char_length(training_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(development_prediction_evidence_set_hash) "
                "= 64 "
                "AND char_length(holdout_prediction_hash) = 64 "
                "AND char_length(holdout_prediction_evidence_set_hash) "
                "= 64 "
                "AND official_holdout_evaluation "
                "AND holdout_evaluated "
                "AND holdout_consumed "
                "AND development_prediction_hashes_match "
                "AND artifact_hashes_verified "
                "AND NOT model_parameters_modified "
                "AND NOT feature_engineering_performed "
                "AND NOT hyperparameter_tuning_performed "
                "AND NOT experiments_modified"
            ),
            name="ck_holdout_evaluation_reports_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["final_model_selection_report_id"],
            ["final_model_selection_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["market_regime_analysis_report_id"],
            ["market_regime_analysis_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_comparison_report_id"],
            ["model_comparison_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["residual_diagnostics_report_id"],
            ["residual_diagnostics_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["statistical_validation_report_id"],
            ["statistical_validation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "validation_run_id",
            name="uq_holdout_evaluation_reports_validation_run",
        ),
        sa.UniqueConstraint(
            "configuration_hash",
            "result_hash",
            name="uq_holdout_evaluation_reports_result",
        ),
    )
    op.create_table(
        "holdout_prediction_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("observation_index", sa.Integer(), nullable=False),
        sa.Column(
            "prediction_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "label_available_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("actual_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("predicted_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("residual_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("actual_float_hex", sa.String(length=32), nullable=False),
        sa.Column("predicted_float_hex", sa.String(length=32), nullable=False),
        sa.Column("residual_float_hex", sa.String(length=32), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "observation_index > 0 "
                "AND label_available_at > prediction_timestamp "
                "AND char_length(actual_float_hex) > 0 "
                "AND char_length(predicted_float_hex) > 0 "
                "AND char_length(residual_float_hex) > 0 "
                "AND char_length(evidence_hash) = 64"
            ),
            name="ck_holdout_prediction_evidence_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["holdout_evaluation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id",
            "prediction_timestamp",
            name="uq_holdout_prediction_evidence_timestamp",
        ),
        sa.UniqueConstraint(
            "evidence_hash",
            name="uq_holdout_prediction_evidence_hash",
        ),
    )
    op.create_table(
        "holdout_consumptions",
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "holdout_evaluation_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("selected_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=48), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False),
        sa.Column("irreversible", sa.Boolean(), nullable=False),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "purpose = 'official_final_evaluation' "
                "AND official "
                "AND irreversible"
            ),
            name="ck_holdout_consumptions_official",
        ),
        sa.ForeignKeyConstraint(
            ["holdout_evaluation_report_id"],
            ["holdout_evaluation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("validation_run_id"),
        sa.UniqueConstraint(
            "holdout_evaluation_report_id",
            name="uq_holdout_consumptions_report",
        ),
    )


def downgrade() -> None:
    op.drop_table("holdout_consumptions")
    op.drop_table("holdout_prediction_evidence")
    op.drop_table("holdout_evaluation_reports")
