"""Create immutable historical coverage snapshots."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260731_0028"
down_revision: str | None = "20260730_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_coverage_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("hash_schema_version", sa.String(32), nullable=False),
        sa.Column(
            "acquisition_policy_identifier",
            sa.String(96),
            nullable=False,
        ),
        sa.Column(
            "acquisition_policy_version",
            sa.String(32),
            nullable=False,
        ),
        sa.Column("asset_identifier", sa.String(32), nullable=False),
        sa.Column("quote_currency", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column(
            "requested_range_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "requested_range_end_exclusive",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "coverage_range_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "coverage_range_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("expected_candle_count", sa.Integer(), nullable=False),
        sa.Column("observed_candle_count", sa.Integer(), nullable=False),
        sa.Column("gap_count", sa.Integer(), nullable=False),
        sa.Column(
            "gap_timestamps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_batch_count", sa.Integer(), nullable=False),
        sa.Column(
            "validation_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "derivation_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("validation_hash", sa.String(64), nullable=False),
        sa.Column("source_data_hash", sa.String(64), nullable=False),
        sa.Column("source_provenance_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column(
            "immutable",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requested_range_start < requested_range_end_exclusive",
            name="ck_coverage_snapshots_requested_range",
        ),
        sa.CheckConstraint(
            "coverage_range_start <= coverage_range_end",
            name="ck_coverage_snapshots_coverage_range",
        ),
        sa.CheckConstraint(
            "timeframe IN ('5m', '10m', '15m')",
            name="ck_coverage_snapshots_timeframe",
        ),
        sa.CheckConstraint(
            (
                "expected_candle_count > 0 "
                "AND observed_candle_count > 0 "
                "AND gap_count >= 0 "
                "AND expected_candle_count = observed_candle_count + gap_count "
                "AND source_batch_count > 0"
            ),
            name="ck_coverage_snapshots_counts",
        ),
        sa.CheckConstraint(
            (
                "char_length(validation_hash) = 64 "
                "AND char_length(source_data_hash) = 64 "
                "AND char_length(source_provenance_hash) = 64 "
                "AND char_length(result_hash) = 64"
            ),
            name="ck_coverage_snapshots_hashes",
        ),
        sa.CheckConstraint(
            "immutable",
            name="ck_coverage_snapshots_immutable",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "result_hash",
            name="uq_coverage_snapshots_result_hash",
        ),
    )
    op.create_index(
        "ix_coverage_snapshots_scope",
        "historical_coverage_snapshots",
        [
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "coverage_range_end",
        ],
        unique=False,
    )

    op.create_table(
        "historical_coverage_snapshot_candles",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("candle_id", sa.BigInteger(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0",
            name="ck_coverage_snapshot_candles_ordinal",
        ),
        sa.ForeignKeyConstraint(
            ["candle_id"],
            ["market_data_candles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["historical_coverage_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "candle_id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "ordinal",
            name="uq_coverage_snapshot_candles_ordinal",
        ),
    )
    op.create_index(
        "ix_coverage_snapshot_candles_candle_id",
        "historical_coverage_snapshot_candles",
        ["candle_id"],
        unique=False,
    )

    op.create_table(
        "historical_coverage_snapshot_batches",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("source_subset_hash", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "candle_count > 0",
            name="ck_coverage_snapshot_batches_count",
        ),
        sa.CheckConstraint(
            "char_length(source_subset_hash) = 64",
            name="ck_coverage_snapshot_batches_hash",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["historical_coverage_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "ingestion_batch_id"),
    )
    op.create_index(
        "ix_coverage_snapshot_batches_batch_id",
        "historical_coverage_snapshot_batches",
        ["ingestion_batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coverage_snapshot_batches_batch_id",
        table_name="historical_coverage_snapshot_batches",
    )
    op.drop_table("historical_coverage_snapshot_batches")
    op.drop_index(
        "ix_coverage_snapshot_candles_candle_id",
        table_name="historical_coverage_snapshot_candles",
    )
    op.drop_table("historical_coverage_snapshot_candles")
    op.drop_index(
        "ix_coverage_snapshots_scope",
        table_name="historical_coverage_snapshots",
    )
    op.drop_table("historical_coverage_snapshots")
