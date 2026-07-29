"""Create immutable statistical validation reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0014"
down_revision: str | None = "20260729_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "statistical_validation_reports",
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
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column("bootstrap_random_seed", sa.Integer(), nullable=False),
        sa.Column("bootstrap_resamples", sa.Integer(), nullable=False),
        sa.Column("confidence_level", sa.Numeric(5, 4), nullable=False),
        sa.Column("model_count", sa.Integer(), nullable=False),
        sa.Column("pair_count", sa.Integer(), nullable=False),
        sa.Column("hypothesis_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_fold_count", sa.Integer(), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column("final_holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column("model_retraining_performed", sa.Boolean(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "bootstrap_random_seed = 42 "
                "AND bootstrap_resamples > 0 "
                "AND confidence_level = 0.95 "
                "AND model_count = 4 "
                "AND pair_count = 6 "
                "AND hypothesis_count = 18 "
                "AND evaluated_fold_count > 0 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated "
                "AND NOT model_retraining_performed"
            ),
            name="ck_statistical_validation_reports_integrity",
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
            name="uq_statistical_validation_reports_result",
        ),
    )
    op.create_table(
        "statistical_validation_report_experiments",
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
            ["statistical_validation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "experiment_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_statistical_validation_report_experiments_family",
        ),
    )
    op.create_table(
        "statistical_validation_report_explainability",
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
            ["statistical_validation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "artifact_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_statistical_validation_report_explainability_family",
        ),
    )


def downgrade() -> None:
    op.drop_table("statistical_validation_report_explainability")
    op.drop_table("statistical_validation_report_experiments")
    op.drop_table("statistical_validation_reports")
