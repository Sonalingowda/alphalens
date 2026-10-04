"""Align packaged inference training-count integrity with the approved cycle."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261003_0040"
down_revision: str | None = "20260929_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_inference_artifacts",
        sa.Column(
            "release_status",
            sa.String(length=16),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.execute(
        "UPDATE model_inference_artifacts "
        "SET release_status = 'RETIRED' "
        "WHERE final_training_observation_count = 611"
    )
    op.drop_constraint(
        "ck_model_inference_artifacts_integrity",
        "model_inference_artifacts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_model_inference_artifacts_integrity",
        "model_inference_artifacts",
        "release_status IN ('ACTIVE', 'RETIRED') "
        "AND (release_status = 'RETIRED' "
        "OR final_training_observation_count = 610) "
        "AND artifact_version = '1.0.0' "
        "AND model_family = 'ridge_regression' "
        "AND feature_pipeline_version = '1.1.0' "
        "AND target_version = '1.0.0' "
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
        "AND NOT research_artifacts_modified",
    )
    op.create_index(
        "uq_model_inference_artifacts_one_active",
        "model_inference_artifacts",
        ["release_status"],
        unique=True,
        postgresql_where=sa.text("release_status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_model_inference_artifacts_one_active",
        table_name="model_inference_artifacts",
    )
    op.drop_constraint(
        "ck_model_inference_artifacts_integrity",
        "model_inference_artifacts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_model_inference_artifacts_integrity",
        "model_inference_artifacts",
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
        "AND NOT research_artifacts_modified",
    )
    op.drop_column("model_inference_artifacts", "release_status")
