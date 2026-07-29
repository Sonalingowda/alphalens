"""Create immutable model explainability artifacts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0013"
down_revision: str | None = "20260729_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_explainability_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column("report_version", sa.String(length=32), nullable=False),
        sa.Column(
            "method_configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "artifact_payload",
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
        sa.Column("permutation_random_seed", sa.Integer(), nullable=False),
        sa.Column("permutation_repeats", sa.Integer(), nullable=False),
        sa.Column("evaluated_split_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_observation_count", sa.Integer(), nullable=False),
        sa.Column("prediction_hashes_verified", sa.Integer(), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column("final_holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "model_family IN "
                "('random_forest_regression', 'xgboost_regression') "
                "AND permutation_random_seed = 42 "
                "AND permutation_repeats > 0 "
                "AND evaluated_split_count > 0 "
                "AND evaluated_observation_count > 0 "
                "AND prediction_hashes_verified = evaluated_split_count "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND point_in_time_validated "
                "AND NOT final_holdout_evaluated"
            ),
            name="ck_model_explainability_artifacts_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id",
            "configuration_hash",
            "result_hash",
            name="uq_model_explainability_artifacts_result",
        ),
    )


def downgrade() -> None:
    op.drop_table("model_explainability_artifacts")
