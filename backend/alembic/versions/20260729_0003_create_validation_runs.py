"""Create auditable chronological validation runs."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("asset_identifier", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("source_data_hash", sa.String(length=64), nullable=False),
        sa.Column("source_observation_count", sa.Integer(), nullable=False),
        sa.Column("minimum_train_size", sa.Integer(), nullable=False),
        sa.Column("test_size", sa.Integer(), nullable=False),
        sa.Column("step_size", sa.Integer(), nullable=False),
        sa.Column("purge_gap_size", sa.Integer(), nullable=False),
        sa.Column("final_holdout_size", sa.Integer(), nullable=False),
        sa.Column("max_feature_window", sa.Integer(), nullable=False),
        sa.Column(
            "development_range_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "development_range_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "final_holdout_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "final_holdout_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("holdout_excluded", sa.Boolean(), nullable=False),
        sa.Column("split_count", sa.Integer(), nullable=False),
        sa.Column(
            "split_boundaries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "lookback_separation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "char_length(configuration_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(source_data_hash) = 64"
            ),
            name="ck_validation_runs_hash_lengths",
        ),
        sa.CheckConstraint(
            "holdout_excluded",
            name="ck_validation_runs_holdout_excluded",
        ),
        sa.CheckConstraint(
            (
                "minimum_train_size > 0 AND test_size > 0 "
                "AND step_size >= test_size AND final_holdout_size > 0"
            ),
            name="ck_validation_runs_positive_window_sizes",
        ),
        sa.CheckConstraint(
            "purge_gap_size >= max_feature_window",
            name="ck_validation_runs_sufficient_purge",
        ),
        sa.CheckConstraint(
            (
                "source_observation_count > 0 AND split_count > 0 "
                "AND development_range_start <= development_range_end "
                "AND development_range_end < final_holdout_start "
                "AND final_holdout_start <= final_holdout_end"
            ),
            name="ck_validation_runs_valid_ranges",
        ),
        sa.ForeignKeyConstraint(
            ["source_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_validation_runs_configuration_hash",
        "validation_runs",
        ["configuration_hash"],
        unique=False,
    )
    op.create_index(
        "ix_validation_runs_source_ingestion_batch_id",
        "validation_runs",
        ["source_ingestion_batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validation_runs_source_ingestion_batch_id",
        table_name="validation_runs",
    )
    op.drop_index(
        "ix_validation_runs_configuration_hash",
        table_name="validation_runs",
    )
    op.drop_table("validation_runs")
