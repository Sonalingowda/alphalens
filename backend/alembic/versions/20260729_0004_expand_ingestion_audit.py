"""Expand ingestion audit metadata for paginated backfills."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0004"
down_revision: str | None = "20260729_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "provider_page_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "excluded_incomplete_candle_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "provider_page_limit",
            sa.Integer(),
            server_default="720",
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "provider_limit_reached",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "pagination_exhausted",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "available_range_start",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "available_range_end",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "insertion_mode",
            sa.String(length=16),
            server_default="upsert",
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "progress_events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_ingestion_batches_insertion_mode",
        "market_data_ingestion_batches",
        "insertion_mode IN ('upsert', 'insert_only')",
    )
    op.create_check_constraint(
        "ck_ingestion_batches_valid_pagination_counts",
        "market_data_ingestion_batches",
        (
            "provider_page_count > 0 "
            "AND excluded_incomplete_candle_count >= 0 "
            "AND provider_page_limit > 0"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_batches_valid_pagination_counts",
        "market_data_ingestion_batches",
        type_="check",
    )
    op.drop_constraint(
        "ck_ingestion_batches_insertion_mode",
        "market_data_ingestion_batches",
        type_="check",
    )
    op.drop_column("market_data_ingestion_batches", "progress_events")
    op.drop_column("market_data_ingestion_batches", "insertion_mode")
    op.drop_column("market_data_ingestion_batches", "available_range_end")
    op.drop_column("market_data_ingestion_batches", "available_range_start")
    op.drop_column("market_data_ingestion_batches", "pagination_exhausted")
    op.drop_column("market_data_ingestion_batches", "provider_limit_reached")
    op.drop_column("market_data_ingestion_batches", "provider_page_limit")
    op.drop_column(
        "market_data_ingestion_batches",
        "excluded_incomplete_candle_count",
    )
    op.drop_column("market_data_ingestion_batches", "provider_page_count")
