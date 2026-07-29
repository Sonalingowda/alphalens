"""Create immutable prediction evidence and residual diagnostics."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0015"
down_revision: str | None = "20260729_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_prediction_evidence",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_split_id", sa.BigInteger(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column("split_sequence", sa.Integer(), nullable=False),
        sa.Column("observation_index", sa.Integer(), nullable=False),
        sa.Column(
            "prediction_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("actual_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("predicted_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("residual_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("actual_float_hex", sa.String(length=32), nullable=False),
        sa.Column(
            "predicted_float_hex",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("residual_float_hex", sa.String(length=32), nullable=False),
        sa.Column(
            "source_prediction_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "split_sequence > 0 "
                "AND observation_index > 0 "
                "AND char_length(source_prediction_hash) = 64 "
                "AND char_length(evidence_hash) = 64 "
                "AND char_length(actual_float_hex) > 0 "
                "AND char_length(predicted_float_hex) > 0 "
                "AND char_length(residual_float_hex) > 0"
            ),
            name="ck_experiment_prediction_evidence_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_split_id"],
            ["regression_experiment_splits.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id",
            "prediction_timestamp",
            name="uq_experiment_prediction_evidence_timestamp",
        ),
        sa.UniqueConstraint(
            "evidence_hash",
            name="uq_experiment_prediction_evidence_hash",
        ),
    )
    op.create_index(
        "ix_experiment_prediction_evidence_experiment_split",
        "experiment_prediction_evidence",
        ["experiment_split_id"],
        unique=False,
    )

    op.create_table(
        "residual_diagnostics_reports",
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
            "statistical_validation_report_id",
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
        sa.Column("evaluated_split_count", sa.Integer(), nullable=False),
        sa.Column(
            "evaluated_observation_count_per_model",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("prediction_evidence_count", sa.Integer(), nullable=False),
        sa.Column("prediction_hashes_verified", sa.Integer(), nullable=False),
        sa.Column("plot_count", sa.Integer(), nullable=False),
        sa.Column(
            "deterministic_replay_performed",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("experiments_modified", sa.Boolean(), nullable=False),
        sa.Column("final_holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "model_count = 4 "
                "AND evaluated_split_count > 0 "
                "AND evaluated_observation_count_per_model > 0 "
                "AND prediction_evidence_count = "
                "model_count * evaluated_observation_count_per_model "
                "AND prediction_hashes_verified = "
                "model_count * evaluated_split_count "
                "AND plot_count = 16 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND deterministic_replay_performed "
                "AND NOT experiments_modified "
                "AND NOT final_holdout_evaluated"
            ),
            name="ck_residual_diagnostics_reports_integrity",
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
            name="uq_residual_diagnostics_reports_result",
        ),
    )
    op.create_table(
        "residual_diagnostics_report_experiments",
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
            ["residual_diagnostics_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "experiment_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_residual_diagnostics_report_experiments_family",
        ),
    )
    op.create_table(
        "residual_diagnostics_report_explainability",
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
            ["residual_diagnostics_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "artifact_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_residual_diagnostics_report_explainability_family",
        ),
    )
    op.create_table(
        "residual_diagnostic_plots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column("plot_type", sa.String(length=32), nullable=False),
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
                "('residual_histogram', 'residual_qq', "
                "'residual_vs_predicted', 'residual_vs_actual') "
                "AND mime_type = 'image/svg+xml' "
                "AND char_length(content_hash) = 64 "
                "AND char_length(content) > 0"
            ),
            name="ck_residual_diagnostic_plots_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["residual_diagnostics_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            "plot_type",
            name="uq_residual_diagnostic_plots_report_model_type",
        ),
        sa.UniqueConstraint(
            "content_hash",
            name="uq_residual_diagnostic_plots_content_hash",
        ),
    )


def downgrade() -> None:
    op.drop_table("residual_diagnostic_plots")
    op.drop_table("residual_diagnostics_report_explainability")
    op.drop_table("residual_diagnostics_report_experiments")
    op.drop_table("residual_diagnostics_reports")
    op.drop_index(
        "ix_experiment_prediction_evidence_experiment_split",
        table_name="experiment_prediction_evidence",
    )
    op.drop_table("experiment_prediction_evidence")
