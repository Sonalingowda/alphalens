"""Create immutable forward log-return target persistence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0007"
down_revision: str | None = "20260729_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forward_log_return_target_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_name", sa.String(length=64), nullable=False),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column(
            "target_definition_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("asset_identifier", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_feature_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("label_data_hash", sa.String(length=64), nullable=False),
        sa.Column("source_candle_count", sa.Integer(), nullable=False),
        sa.Column(
            "source_range_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "source_range_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("generated_label_count", sa.Integer(), nullable=False),
        sa.Column("persisted_label_count", sa.Integer(), nullable=False),
        sa.Column(
            "excluded_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "exclusion_details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "first_eligible_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_eligible_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("label_value_min", sa.Numeric(38, 18), nullable=False),
        sa.Column("label_value_max", sa.Numeric(38, 18), nullable=False),
        sa.Column("label_value_mean", sa.Numeric(38, 18), nullable=False),
        sa.Column("positive_label_count", sa.Integer(), nullable=False),
        sa.Column("negative_label_count", sa.Integer(), nullable=False),
        sa.Column("zero_label_count", sa.Integer(), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "superseded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "horizon > 0 AND source_candle_count > horizon "
                "AND generated_label_count > 0 "
                "AND persisted_label_count >= 0 "
                "AND persisted_label_count <= generated_label_count "
                "AND excluded_observation_count >= 0 "
                "AND source_candle_count = "
                "generated_label_count + excluded_observation_count"
            ),
            name="ck_forward_log_return_runs_valid_counts",
        ),
        sa.CheckConstraint(
            (
                "positive_label_count >= 0 AND negative_label_count >= 0 "
                "AND zero_label_count >= 0 "
                "AND generated_label_count = positive_label_count "
                "+ negative_label_count + zero_label_count"
            ),
            name="ck_forward_log_return_runs_valid_sign_counts",
        ),
        sa.CheckConstraint(
            (
                "source_range_start <= first_eligible_timestamp "
                "AND first_eligible_timestamp <= last_eligible_timestamp "
                "AND last_eligible_timestamp < source_range_end"
            ),
            name="ck_forward_log_return_runs_valid_ranges",
        ),
        sa.CheckConstraint(
            (
                "char_length(target_definition_hash) = 64 "
                "AND char_length(dataset_hash) = 64 "
                "AND char_length(label_data_hash) = 64"
            ),
            name="ck_forward_log_return_runs_hash_lengths",
        ),
        sa.CheckConstraint(
            "point_in_time_validated",
            name="ck_forward_log_return_runs_point_in_time_validated",
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_forward_log_return_runs_source_ingestion_batch_id",
        "forward_log_return_target_runs",
        ["source_ingestion_batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_forward_log_return_runs_source_feature_run_id",
        "forward_log_return_target_runs",
        ["source_feature_run_id"],
        unique=False,
    )
    op.create_index(
        "uq_active_forward_log_return_target_market",
        "forward_log_return_target_runs",
        ["asset_identifier", "quote_currency", "timeframe", "target_name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "forward_log_return_targets",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("asset_identifier", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("target_name", sa.String(length=64), nullable=False),
        sa.Column("target_version", sa.String(length=32), nullable=False),
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
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("target_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_feature_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "horizon > 0 AND prediction_timestamp < label_available_at",
            name="ck_forward_log_return_targets_valid_horizon",
        ),
        sa.CheckConstraint(
            "char_length(dataset_hash) = 64",
            name="ck_forward_log_return_targets_dataset_hash_length",
        ),
        sa.CheckConstraint(
            (
                "timeframe <> '1d' OR "
                "(prediction_timestamp = "
                "(date_trunc('day', prediction_timestamp AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC') "
                "AND label_available_at = "
                "(date_trunc('day', label_available_at AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC'))"
            ),
            name="ck_forward_log_return_targets_daily_utc_alignment",
        ),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["forward_log_return_target_runs.id"],
            ondelete="RESTRICT",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "prediction_timestamp",
            "target_name",
            "target_version",
            name="uq_forward_log_return_targets_identity",
        ),
    )
    op.create_index(
        "ix_forward_log_return_targets_generation_run_id",
        "forward_log_return_targets",
        ["generation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_forward_log_return_targets_source_ingestion_batch_id",
        "forward_log_return_targets",
        ["source_ingestion_batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_forward_log_return_targets_source_feature_run_id",
        "forward_log_return_targets",
        ["source_feature_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_forward_log_return_targets_source_feature_run_id",
        table_name="forward_log_return_targets",
    )
    op.drop_index(
        "ix_forward_log_return_targets_source_ingestion_batch_id",
        table_name="forward_log_return_targets",
    )
    op.drop_index(
        "ix_forward_log_return_targets_generation_run_id",
        table_name="forward_log_return_targets",
    )
    op.drop_table("forward_log_return_targets")
    op.drop_index(
        "uq_active_forward_log_return_target_market",
        table_name="forward_log_return_target_runs",
    )
    op.drop_index(
        "ix_forward_log_return_runs_source_feature_run_id",
        table_name="forward_log_return_target_runs",
    )
    op.drop_index(
        "ix_forward_log_return_runs_source_ingestion_batch_id",
        table_name="forward_log_return_target_runs",
    )
    op.drop_table("forward_log_return_target_runs")
