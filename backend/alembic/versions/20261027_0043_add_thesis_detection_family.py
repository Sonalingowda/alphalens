"""Add an explicit detection-family key for conservative review clustering."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_0043"
down_revision: str | None = "20261027_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "opportunity_theses",
        sa.Column("detection_family", sa.String(256), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_opportunity_theses_detection_family",
        "opportunity_theses",
        ["instrument", "timeframe", "direction", "detection_family"],
    )


def downgrade() -> None:
    op.drop_index("ix_opportunity_theses_detection_family", table_name="opportunity_theses")
    op.drop_column("opportunity_theses", "detection_family")
