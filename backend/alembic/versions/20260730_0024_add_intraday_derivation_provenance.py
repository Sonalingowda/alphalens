"""Add intraday derivation provenance and UTC alignment checks."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0024"
down_revision: str | None = "20260730_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column("source_timeframe", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column("derivation_method", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column("source_ingestion_batch_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ingestion_batches_source_ingestion_batch_id",
        "market_data_ingestion_batches",
        "market_data_ingestion_batches",
        ["source_ingestion_batch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_ingestion_batches_complete_derivation_provenance",
        "market_data_ingestion_batches",
        (
            "(source_timeframe IS NULL "
            "AND derivation_method IS NULL "
            "AND source_ingestion_batch_id IS NULL) "
            "OR (source_timeframe IS NOT NULL "
            "AND derivation_method IS NOT NULL "
            "AND source_ingestion_batch_id IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_ingestion_batches_source_ingestion_batch_id",
        "market_data_ingestion_batches",
        ["source_ingestion_batch_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_market_candles_intraday_utc_alignment",
        "market_data_candles",
        (
            "(timeframe = '5m' AND "
            "EXTRACT(EPOCH FROM candle_timestamp)::bigint % 300 = 0) "
            "OR (timeframe = '10m' AND "
            "EXTRACT(EPOCH FROM candle_timestamp)::bigint % 600 = 0) "
            "OR (timeframe = '15m' AND "
            "EXTRACT(EPOCH FROM candle_timestamp)::bigint % 900 = 0) "
            "OR timeframe NOT IN ('5m', '10m', '15m')"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_market_candles_intraday_utc_alignment",
        "market_data_candles",
        type_="check",
    )
    op.drop_index(
        "ix_ingestion_batches_source_ingestion_batch_id",
        table_name="market_data_ingestion_batches",
    )
    op.drop_constraint(
        "ck_ingestion_batches_complete_derivation_provenance",
        "market_data_ingestion_batches",
        type_="check",
    )
    op.drop_constraint(
        "fk_ingestion_batches_source_ingestion_batch_id",
        "market_data_ingestion_batches",
        type_="foreignkey",
    )
    op.drop_column(
        "market_data_ingestion_batches",
        "source_ingestion_batch_id",
    )
    op.drop_column("market_data_ingestion_batches", "derivation_method")
    op.drop_column("market_data_ingestion_batches", "source_timeframe")
