"""Create immutable packaged model inference artifacts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0021"
down_revision: str | None = "20260730_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_inference_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version", sa.String(length=32), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column(
            "artifact_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "verification_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("state_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "verification_evidence_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("selected_experiment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "holdout_evaluation_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "training_dataset_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
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
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("coefficient_count", sa.Integer(), nullable=False),
        sa.Column("scaler_mean_count", sa.Integer(), nullable=False),
        sa.Column("scaler_scale_count", sa.Integer(), nullable=False),
        sa.Column(
            "verification_prediction_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "official_prediction_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("deterministic_replay", sa.Boolean(), nullable=False),
        sa.Column(
            "official_prediction_hash_verified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "artifact_only_inference_verified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("model_tuned", sa.Boolean(), nullable=False),
        sa.Column("experiment_modified", sa.Boolean(), nullable=False),
        sa.Column(
            "research_artifacts_modified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "artifact_version = '1.0.0' "
                "AND model_family = 'ridge_regression' "
                "AND feature_pipeline_version = '1.1.0' "
                "AND target_version = '1.0.0' "
                "AND final_training_observation_count = 611 "
                "AND purged_observation_count = 50 "
                "AND feature_count = 12 "
                "AND coefficient_count = feature_count "
                "AND scaler_mean_count = feature_count "
                "AND scaler_scale_count = feature_count "
                "AND verification_prediction_count = 5 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(artifact_sha256) = 64 "
                "AND char_length(state_sha256) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(training_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(official_prediction_hash) = 64 "
                "AND char_length(verification_evidence_hash) = 64 "
                "AND deterministic_replay "
                "AND official_prediction_hash_verified "
                "AND artifact_only_inference_verified "
                "AND NOT model_tuned "
                "AND NOT experiment_modified "
                "AND NOT research_artifacts_modified"
            ),
            name="ck_model_inference_artifacts_integrity",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "artifact_sha256",
            name="uq_model_inference_artifacts_sha256",
        ),
        sa.UniqueConstraint(
            "configuration_hash",
            name="uq_model_inference_artifacts_configuration",
        ),
        sa.UniqueConstraint(
            "selected_experiment_id",
            name="uq_model_inference_artifacts_experiment",
        ),
    )


def downgrade() -> None:
    op.drop_table("model_inference_artifacts")
