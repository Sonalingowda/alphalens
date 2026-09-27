"""Create isolated immutable paper successor-plan artifacts."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260925_0037"
down_revision: str | None = "20260925_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_successor_plans",
        sa.Column("successor_plan_id", sa.String(length=256), primary_key=True),
        sa.Column("source_opportunity_version_id", sa.String(length=256), nullable=False),
        sa.Column("source_opportunity_id", sa.String(length=256), nullable=False),
        sa.Column("source_plan_id", sa.String(length=256), nullable=False),
        sa.Column("source_plan_canonical_hash", sa.String(length=64), nullable=False),
        sa.Column("successor_plan_canonical_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("source_opportunity_version_id", name="uq_paper_successor_source_version"),
        sa.CheckConstraint("char_length(source_plan_canonical_hash) = 64", name="ck_paper_successor_source_hash"),
        sa.CheckConstraint("char_length(successor_plan_canonical_hash) = 64", name="ck_paper_successor_hash"),
    )


def downgrade() -> None:
    op.drop_table("paper_successor_plans")
