"""Create deterministic multi-timeframe synchronization evidence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260801_0031"
down_revision: str | None = "20260801_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ten_minute_derivations",
        sa.Column("derived_candle_id", sa.BigInteger(), nullable=False),
        sa.Column("derived_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("derivation_method", sa.String(64), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("derived_candle_hash", sa.String(64), nullable=False),
        sa.Column("source_membership_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "derivation_method = 'utc_5m_pair_v1'",
            name="ck_ten_minute_derivations_method",
        ),
        sa.CheckConstraint(
            "char_length(derived_candle_hash) = 64 AND "
            "char_length(source_membership_hash) = 64 AND "
            "char_length(result_hash) = 64",
            name="ck_ten_minute_derivations_hashes",
        ),
        sa.CheckConstraint("immutable", name="ck_ten_minute_derivations_immutable"),
        sa.ForeignKeyConstraint(
            ["derived_candle_id"],
            ["market_data_candles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["derived_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("derived_candle_id"),
        sa.UniqueConstraint(
            "result_hash", name="uq_ten_minute_derivations_result_hash"
        ),
    )
    op.create_table(
        "ten_minute_derivation_sources",
        sa.Column("derived_candle_id", sa.BigInteger(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_candle_id", sa.BigInteger(), nullable=False),
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_candle_hash", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "ordinal IN (0, 1)",
            name="ck_ten_minute_derivation_sources_ordinal",
        ),
        sa.CheckConstraint(
            "char_length(source_candle_hash) = 64",
            name="ck_ten_minute_derivation_sources_hash",
        ),
        sa.ForeignKeyConstraint(
            ["derived_candle_id"],
            ["ten_minute_derivations.derived_candle_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_candle_id"],
            ["market_data_candles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("derived_candle_id", "ordinal"),
        sa.UniqueConstraint(
            "derived_candle_id",
            "source_candle_id",
            name="uq_ten_minute_derivation_sources_member",
        ),
    )
    op.create_index(
        "ix_ten_minute_derivation_sources_source_candle_id",
        "ten_minute_derivation_sources",
        ["source_candle_id"],
        unique=False,
    )
    op.create_table(
        "synchronized_coverage_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("hash_schema_version", sa.String(32), nullable=False),
        sa.Column("asset_identifier", sa.String(32), nullable=False),
        sa.Column("quote_currency", sa.String(16), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("five_minute_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("ten_minute_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("fifteen_minute_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("derivation_count", sa.Integer(), nullable=False),
        sa.Column("differences", postgresql.JSONB(), nullable=False),
        sa.Column("source_provenance_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_identifier = 'BTC' AND quote_currency = 'USD'",
            name="ck_synchronized_coverage_scope",
        ),
        sa.CheckConstraint(
            "derivation_count > 0",
            name="ck_synchronized_coverage_derivation_count",
        ),
        sa.CheckConstraint(
            "char_length(source_provenance_hash) = 64 AND "
            "char_length(result_hash) = 64",
            name="ck_synchronized_coverage_hashes",
        ),
        sa.CheckConstraint("immutable", name="ck_synchronized_coverage_immutable"),
        sa.ForeignKeyConstraint(
            ["five_minute_snapshot_id"],
            ["historical_coverage_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ten_minute_snapshot_id"],
            ["historical_coverage_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fifteen_minute_snapshot_id"],
            ["historical_coverage_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_hash", name="uq_synchronized_coverage_result_hash"),
    )
    op.create_index(
        "ix_synchronized_coverage_as_of",
        "synchronized_coverage_snapshots",
        ["as_of"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_synchronized_coverage_as_of",
        table_name="synchronized_coverage_snapshots",
    )
    op.drop_table("synchronized_coverage_snapshots")
    op.drop_index(
        "ix_ten_minute_derivation_sources_source_candle_id",
        table_name="ten_minute_derivation_sources",
    )
    op.drop_table("ten_minute_derivation_sources")
    op.drop_table("ten_minute_derivations")
