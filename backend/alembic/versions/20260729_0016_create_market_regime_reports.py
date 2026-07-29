"""Create immutable market regime analysis reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0016"
down_revision: str | None = "20260729_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_regime_analysis_reports",
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
        sa.Column(
            "regime_assignment_set_hash",
            sa.String(length=64),
            nullable=False,
        ),
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
        sa.Column("assignment_count", sa.Integer(), nullable=False),
        sa.Column("prediction_evidence_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_split_count", sa.Integer(), nullable=False),
        sa.Column("plot_count", sa.Integer(), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column("final_holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column("model_retraining_performed", sa.Boolean(), nullable=False),
        sa.Column("experiments_modified", sa.Boolean(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "model_count = 4 "
                "AND assignment_count > 0 "
                "AND prediction_evidence_count = model_count * "
                "assignment_count "
                "AND evaluated_split_count > 0 "
                "AND plot_count = 12 "
                "AND char_length(regime_assignment_set_hash) = 64 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated "
                "AND NOT model_retraining_performed "
                "AND NOT experiments_modified"
            ),
            name="ck_market_regime_analysis_reports_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["residual_diagnostics_report_id"],
            ["residual_diagnostics_reports.id"],
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
            name="uq_market_regime_analysis_reports_result",
        ),
    )
    op.create_table(
        "market_regime_report_experiments",
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
            ["market_regime_analysis_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "experiment_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_market_regime_report_experiments_family",
        ),
    )
    op.create_table(
        "market_regime_report_explainability",
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
            ["market_regime_analysis_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "artifact_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_market_regime_report_explainability_family",
        ),
    )
    op.create_table(
        "market_regime_assignments",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column(
            "prediction_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("trend_regime", sa.String(length=32), nullable=False),
        sa.Column("volatility_regime", sa.String(length=32), nullable=False),
        sa.Column("trend_spread", sa.String(length=96), nullable=False),
        sa.Column(
            "bollinger_relative_width",
            sa.String(length=96),
            nullable=False,
        ),
        sa.Column(
            "expanding_width_median",
            sa.String(length=96),
            nullable=False,
        ),
        sa.Column("assignment_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            (
                "trend_regime IN "
                "('bull_trend', 'bear_trend', 'sideways_market') "
                "AND volatility_regime IN "
                "('high_volatility_regime', 'low_volatility_regime') "
                "AND char_length(trend_spread) > 0 "
                "AND char_length(bollinger_relative_width) > 0 "
                "AND char_length(expanding_width_median) > 0 "
                "AND char_length(assignment_hash) = 64"
            ),
            name="ck_market_regime_assignments_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["market_regime_analysis_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id",
            "assignment_hash",
            name="uq_market_regime_assignments_hash",
        ),
        sa.UniqueConstraint(
            "report_id",
            "prediction_timestamp",
            name="uq_market_regime_assignments_timestamp",
        ),
    )
    op.create_table(
        "market_regime_plots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column("plot_type", sa.String(length=48), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "plot_type IN "
                "('performance_by_regime', 'error_by_regime', "
                "'residual_distribution_by_regime') "
                "AND mime_type = 'image/svg+xml' "
                "AND char_length(content_hash) = 64 "
                "AND char_length(content) > 0"
            ),
            name="ck_market_regime_plots_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["market_regime_analysis_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_hash",
            name="uq_market_regime_plots_content_hash",
        ),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            "plot_type",
            name="uq_market_regime_plots_report_model_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("market_regime_plots")
    op.drop_table("market_regime_assignments")
    op.drop_table("market_regime_report_explainability")
    op.drop_table("market_regime_report_experiments")
    op.drop_table("market_regime_analysis_reports")
