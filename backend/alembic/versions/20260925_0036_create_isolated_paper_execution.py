"""Create isolated AlphaLens opportunity paper execution records."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260925_0036"
down_revision: str | None = "20260803_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create(name: str, *, foreign_keys: tuple[sa.ForeignKeyConstraint, ...] = ()) -> None:
    columns = [
        sa.Column("identity", sa.String(length=256), primary_key=True),
        sa.Column("opportunity_version_id", sa.String(length=256), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_hash", sa.String(length=64), nullable=False),
    ]
    if name == "paper_outcomes":
        columns.extend(
            [
                sa.Column("execution_id", sa.String(length=256), nullable=False),
                sa.Column("position_id", sa.String(length=256), nullable=False),
                sa.Column("exit_id", sa.String(length=256), nullable=False),
            ]
        )
    op.create_table(
        name,
        *columns,
        sa.CheckConstraint("char_length(canonical_hash) = 64", name=f"ck_{name}_hash"),
        sa.UniqueConstraint("opportunity_version_id", name=f"uq_{name}_opportunity_version"),
        *foreign_keys,
    )


def upgrade() -> None:
    _create("paper_executions")
    _create(
        "paper_positions",
        foreign_keys=(sa.ForeignKeyConstraint(["identity"], ["paper_executions.identity"], ondelete="RESTRICT"),),
    )
    _create(
        "paper_exits",
        foreign_keys=(sa.ForeignKeyConstraint(["identity"], ["paper_positions.identity"], ondelete="RESTRICT"),),
    )
    _create(
        "paper_outcomes",
        foreign_keys=(
            sa.ForeignKeyConstraint(["execution_id"], ["paper_executions.identity"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["position_id"], ["paper_positions.identity"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["exit_id"], ["paper_exits.identity"], ondelete="RESTRICT"),
        ),
    )


def downgrade() -> None:
    op.drop_table("paper_outcomes")
    op.drop_table("paper_exits")
    op.drop_table("paper_positions")
    op.drop_table("paper_executions")
