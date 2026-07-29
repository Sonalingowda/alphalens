"""Create immutable final model selection reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0017"
down_revision: str | None = "20260729_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "final_model_selection_reports",
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
        sa.Column("selected_experiment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "selected_model_family",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("selected_model_rank", sa.Integer(), nullable=False),
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column("model_count", sa.Integer(), nullable=False),
        sa.Column("source_artifact_count", sa.Integer(), nullable=False),
        sa.Column("source_plot_hash_count", sa.Integer(), nullable=False),
        sa.Column("prediction_evidence_count", sa.Integer(), nullable=False),
        sa.Column("prediction_hashes_verified", sa.Integer(), nullable=False),
        sa.Column("automated_test_count", sa.Integer(), nullable=False),
        sa.Column("artifact_hashes_verified", sa.Boolean(), nullable=False),
        sa.Column("repeatability_verified", sa.Boolean(), nullable=False),
        sa.Column("automated_tests_passed", sa.Boolean(), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column("final_holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column("model_retraining_performed", sa.Boolean(), nullable=False),
        sa.Column("experiments_modified", sa.Boolean(), nullable=False),
        sa.Column(
            "new_experimental_evidence_created",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "model_count = 4 "
                "AND selected_model_family IN "
                "('linear_regression', 'ridge_regression', "
                "'random_forest_regression', 'xgboost_regression') "
                "AND selected_model_rank = 1 "
                "AND source_artifact_count = 6 "
                "AND source_plot_hash_count = 28 "
                "AND prediction_evidence_count > 0 "
                "AND prediction_hashes_verified > 0 "
                "AND automated_test_count > 0 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND artifact_hashes_verified "
                "AND repeatability_verified "
                "AND automated_tests_passed "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated "
                "AND NOT model_retraining_performed "
                "AND NOT experiments_modified "
                "AND NOT new_experimental_evidence_created"
            ),
            name="ck_final_model_selection_reports_integrity",
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
            "configuration_hash",
            "result_hash",
            name="uq_final_model_selection_reports_result",
        ),
    )
    op.create_table(
        "final_model_selection_report_experiments",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["final_model_selection_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "experiment_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_final_model_selection_report_experiments_family",
        ),
    )
    op.create_table(
        "final_model_selection_report_explainability",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["model_explainability_artifacts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["final_model_selection_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "artifact_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_final_model_selection_report_explainability_family",
        ),
    )


def downgrade() -> None:
    op.drop_table("final_model_selection_report_explainability")
    op.drop_table("final_model_selection_report_experiments")
    op.drop_table("final_model_selection_reports")
