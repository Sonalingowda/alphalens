"""Create immutable engineered feature persistence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0002"
down_revision: str | None = "20260729_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_pipeline_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False),
        sa.Column("asset_identifier", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
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
        sa.Column("source_data_hash", sa.String(length=64), nullable=False),
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column("feature_value_count", sa.Integer(), nullable=False),
        sa.Column("persisted_value_count", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(source_data_hash) = 64",
            name="ck_feature_pipeline_runs_sha256_length",
        ),
        sa.CheckConstraint(
            "point_in_time_validated",
            name="ck_feature_pipeline_runs_point_in_time_validated",
        ),
        sa.CheckConstraint(
            (
                "source_candle_count > 0 AND feature_value_count >= 0 "
                "AND persisted_value_count >= 0 "
                "AND persisted_value_count <= feature_value_count"
            ),
            name="ck_feature_pipeline_runs_valid_counts",
        ),
        sa.CheckConstraint(
            "source_range_start <= source_range_end",
            name="ck_feature_pipeline_runs_valid_source_range",
        ),
        sa.ForeignKeyConstraint(
            ["source_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feature_pipeline_runs_source_ingestion_batch_id",
        "feature_pipeline_runs",
        ["source_ingestion_batch_id"],
        unique=False,
    )

    op.create_table(
        "engineered_features",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            nullable=False,
        ),
        sa.Column("asset_identifier", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column(
            "candle_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("feature_name", sa.String(length=96), nullable=False),
        sa.Column("feature_value", sa.Numeric(38, 18), nullable=False),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("computation_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "timeframe <> '1d' OR candle_timestamp = "
                "(date_trunc('day', candle_timestamp AT TIME ZONE 'UTC') "
                "AT TIME ZONE 'UTC')"
            ),
            name="ck_engineered_features_daily_utc_alignment",
        ),
        sa.ForeignKeyConstraint(
            ["computation_run_id"],
            ["feature_pipeline_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "candle_timestamp",
            "feature_name",
            "pipeline_version",
            name="uq_engineered_features_identity",
        ),
    )
    op.create_index(
        "ix_engineered_features_computation_run_id",
        "engineered_features",
        ["computation_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_engineered_features_source_ingestion_batch_id",
        "engineered_features",
        ["source_ingestion_batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_engineered_features_source_ingestion_batch_id",
        table_name="engineered_features",
    )
    op.drop_index(
        "ix_engineered_features_computation_run_id",
        table_name="engineered_features",
    )
    op.drop_table("engineered_features")
    op.drop_index(
        "ix_feature_pipeline_runs_source_ingestion_batch_id",
        table_name="feature_pipeline_runs",
    )
    op.drop_table("feature_pipeline_runs")
