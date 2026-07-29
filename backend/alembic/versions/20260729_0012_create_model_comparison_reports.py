"""Create immutable model comparison research artifacts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0012"
down_revision: str | None = "20260729_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_comparison_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_version", sa.String(length=32), nullable=False),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("model_count", sa.Integer(), nullable=False),
        sa.Column(
            "evaluation_policy_version",
            sa.String(length=32),
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
        sa.Column(
            "runtime_evidence_status",
            sa.String(length=64),
            nullable=False,
        ),
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
                "AND char_length(report_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND NOT final_holdout_evaluated"
            ),
            name="ck_model_comparison_reports_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_hash",
            name="uq_model_comparison_reports_hash",
        ),
    )
    op.create_table(
        "model_comparison_report_experiments",
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
            ["model_comparison_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "experiment_id"),
        sa.UniqueConstraint(
            "report_id",
            "model_family",
            name="uq_model_comparison_report_experiments_family",
        ),
    )


def downgrade() -> None:
    op.drop_table("model_comparison_report_experiments")
    op.drop_table("model_comparison_reports")
