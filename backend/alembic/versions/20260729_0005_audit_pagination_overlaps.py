"""Audit exact pagination-boundary overlaps."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0005"
down_revision: str | None = "20260729_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_batches_valid_pagination_counts",
        "market_data_ingestion_batches",
        type_="check",
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "excluded_pagination_overlap_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_ingestion_batches_valid_pagination_counts",
        "market_data_ingestion_batches",
        (
            "provider_page_count > 0 "
            "AND excluded_incomplete_candle_count >= 0 "
            "AND excluded_pagination_overlap_count >= 0 "
            "AND provider_page_limit > 0"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ingestion_batches_valid_pagination_counts",
        "market_data_ingestion_batches",
        type_="check",
    )
    op.drop_column(
        "market_data_ingestion_batches",
        "excluded_pagination_overlap_count",
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
