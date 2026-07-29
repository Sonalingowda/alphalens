"""Create immutable baseline regression experiment records."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0008"
down_revision: str | None = "20260729_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regression_experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(length=32), nullable=False),
        sa.Column(
            "model_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "preprocessing_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "random_seeds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "training_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("training_code_hash", sa.String(length=64), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_target_run_id", sa.Uuid(), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "feature_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("target_name", sa.String(length=64), nullable=False),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column(
            "target_definition_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column("source_observation_count", sa.Integer(), nullable=False),
        sa.Column(
            "model_eligible_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "development_eligible_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "holdout_eligible_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "excluded_feature_warmup_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "excluded_missing_target_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("validation_split_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_split_count", sa.Integer(), nullable=False),
        sa.Column("skipped_split_count", sa.Integer(), nullable=False),
        sa.Column(
            "evaluated_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("aggregate_mae", sa.Numeric(38, 18), nullable=False),
        sa.Column("aggregate_rmse", sa.Numeric(38, 18), nullable=False),
        sa.Column(
            "aggregate_directional_accuracy",
            sa.Numeric(38, 18),
            nullable=False,
        ),
        sa.Column(
            "aggregation_method",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "software_versions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "experiment_configuration_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column("final_holdout_evaluated", sa.Boolean(), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "model_family IN ('linear_regression', 'ridge_regression')",
            name="ck_regression_experiments_model_family",
        ),
        sa.CheckConstraint(
            (
                "source_observation_count > 0 "
                "AND model_eligible_observation_count > 0 "
                "AND development_eligible_observation_count > 0 "
                "AND holdout_eligible_observation_count >= 0 "
                "AND excluded_feature_warmup_count >= 0 "
                "AND excluded_missing_target_count >= 0 "
                "AND model_eligible_observation_count = "
                "development_eligible_observation_count "
                "+ holdout_eligible_observation_count "
                "AND source_observation_count = "
                "model_eligible_observation_count "
                "+ excluded_feature_warmup_count "
                "+ excluded_missing_target_count"
            ),
            name="ck_regression_experiments_dataset_counts",
        ),
        sa.CheckConstraint(
            (
                "validation_split_count > 0 "
                "AND evaluated_split_count > 0 "
                "AND skipped_split_count >= 0 "
                "AND validation_split_count = "
                "evaluated_split_count + skipped_split_count "
                "AND evaluated_observation_count > 0"
            ),
            name="ck_regression_experiments_evaluation_counts",
        ),
        sa.CheckConstraint(
            (
                "aggregate_mae >= 0 AND aggregate_rmse >= 0 "
                "AND aggregate_directional_accuracy BETWEEN 0 AND 1"
            ),
            name="ck_regression_experiments_metric_ranges",
        ),
        sa.CheckConstraint(
            (
                "char_length(source_dataset_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(target_definition_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(training_code_hash) = 64 "
                "AND char_length(experiment_configuration_hash) = 64 "
                "AND char_length(result_hash) = 64"
            ),
            name="ck_regression_experiments_hash_lengths",
        ),
        sa.CheckConstraint(
            "point_in_time_validated AND NOT final_holdout_evaluated",
            name="ck_regression_experiments_research_safeguards",
        ),
        sa.ForeignKeyConstraint(
            ["source_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_feature_run_id"],
            ["feature_pipeline_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_target_run_id"],
            ["forward_log_return_target_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_regression_experiments_validation_run_id",
        "regression_experiments",
        ["validation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_regression_experiments_source_target_run_id",
        "regression_experiments",
        ["source_target_run_id"],
        unique=False,
    )

    op.create_table(
        "regression_experiment_splits",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("split_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "train_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "train_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "test_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "test_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "train_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "test_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=96), nullable=True),
        sa.Column(
            "latest_train_label_available_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("mae", sa.Numeric(38, 18), nullable=True),
        sa.Column("rmse", sa.Numeric(38, 18), nullable=True),
        sa.Column(
            "directional_accuracy",
            sa.Numeric(38, 18),
            nullable=True,
        ),
        sa.Column("prediction_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            (
                "split_sequence > 0 "
                "AND train_start <= train_end "
                "AND train_end < test_start "
                "AND test_start <= test_end "
                "AND train_observation_count >= 0 "
                "AND test_observation_count >= 0"
            ),
            name="ck_regression_experiment_splits_ranges",
        ),
        sa.CheckConstraint(
            (
                "(status = 'evaluated' "
                "AND exclusion_reason IS NULL "
                "AND train_observation_count > 0 "
                "AND test_observation_count > 0 "
                "AND latest_train_label_available_at IS NOT NULL "
                "AND latest_train_label_available_at < test_start "
                "AND mae IS NOT NULL AND mae >= 0 "
                "AND rmse IS NOT NULL AND rmse >= 0 "
                "AND directional_accuracy IS NOT NULL "
                "AND directional_accuracy BETWEEN 0 AND 1 "
                "AND char_length(prediction_hash) = 64) "
                "OR (status = 'skipped' "
                "AND exclusion_reason IS NOT NULL "
                "AND mae IS NULL AND rmse IS NULL "
                "AND directional_accuracy IS NULL "
                "AND prediction_hash IS NULL)"
            ),
            name="ck_regression_experiment_splits_status",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_id",
            "split_sequence",
            name="uq_regression_experiment_splits_sequence",
        ),
    )
    op.create_index(
        "ix_regression_experiment_splits_experiment_id",
        "regression_experiment_splits",
        ["experiment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regression_experiment_splits_experiment_id",
        table_name="regression_experiment_splits",
    )
    op.drop_table("regression_experiment_splits")
    op.drop_index(
        "ix_regression_experiments_source_target_run_id",
        table_name="regression_experiments",
    )
    op.drop_index(
        "ix_regression_experiments_validation_run_id",
        table_name="regression_experiments",
    )
    op.drop_table("regression_experiments")
