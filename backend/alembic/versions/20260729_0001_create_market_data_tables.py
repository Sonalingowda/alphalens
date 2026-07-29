"""Create validated market data persistence tables."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_data_ingestion_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("asset_identifier", sa.String(length=32), nullable=False),
        sa.Column("quote_currency", sa.String(length=16), nullable=False),
        sa.Column("timeframe", sa.String(length=16), nullable=False),
        sa.Column(
            "requested_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "requested_end_exclusive",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validation_passed", sa.Boolean(), nullable=False),
        sa.Column(
            "validation_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("persisted_candle_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "requested_start < requested_end_exclusive",
            name="ck_ingestion_batches_valid_range",
        ),
        sa.CheckConstraint(
            "candle_count >= 0 AND persisted_candle_count >= 0",
            name="ck_ingestion_batches_non_negative_counts",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "market_data_candles",
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
        sa.Column("open_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("high_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("low_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("close_price", sa.Numeric(38, 18), nullable=False),
        sa.Column("volume", sa.Numeric(38, 18), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("is_complete", sa.Boolean(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column(
            "ingested_at",
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
            name="ck_market_candles_daily_utc_alignment",
        ),
        sa.CheckConstraint(
            (
                "low_price <= high_price "
                "AND open_price BETWEEN low_price AND high_price "
                "AND close_price BETWEEN low_price AND high_price"
            ),
            name="ck_market_candles_ohlc_relationships",
        ),
        sa.CheckConstraint(
            (
                "open_price > 0 AND high_price > 0 AND low_price > 0 "
                "AND close_price > 0 AND volume >= 0"
            ),
            name="ck_market_candles_positive_values",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_identifier",
            "quote_currency",
            "timeframe",
            "candle_timestamp",
            name="uq_market_candles_asset_quote_timeframe_timestamp",
        ),
    )
    op.create_index(
        "ix_market_candles_ingestion_batch_id",
        "market_data_candles",
        ["ingestion_batch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_candles_ingestion_batch_id",
        table_name="market_data_candles",
    )
    op.drop_table("market_data_candles")
    op.drop_table("market_data_ingestion_batches")
