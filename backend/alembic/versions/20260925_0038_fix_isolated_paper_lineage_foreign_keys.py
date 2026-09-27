"""Align isolated paper foreign keys with distinct frozen identities."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260925_0038"
down_revision: str | None = "20260925_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_positions",
        sa.Column("execution_id", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "paper_exits",
        sa.Column("position_id", sa.String(length=256), nullable=True),
    )
    op.execute(
        "UPDATE paper_positions SET execution_id = identity"
    )
    op.execute(
        "UPDATE paper_exits SET position_id = identity"
    )
    op.alter_column(
        "paper_positions",
        "execution_id",
        existing_type=sa.String(length=256),
        nullable=False,
    )
    op.alter_column(
        "paper_exits",
        "position_id",
        existing_type=sa.String(length=256),
        nullable=False,
    )

    op.drop_constraint(
        "paper_positions_identity_fkey",
        "paper_positions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "paper_exits_identity_fkey",
        "paper_exits",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "paper_positions_execution_id_fkey",
        "paper_positions",
        "paper_executions",
        ["execution_id"],
        ["identity"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "paper_exits_position_id_fkey",
        "paper_exits",
        "paper_positions",
        ["position_id"],
        ["identity"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "paper_exits_position_id_fkey",
        "paper_exits",
        type_="foreignkey",
    )
    op.drop_column("paper_exits", "position_id")
    op.create_foreign_key(
        "paper_exits_identity_fkey",
        "paper_exits",
        "paper_positions",
        ["identity"],
        ["identity"],
        ondelete="RESTRICT",
    )

    op.drop_constraint(
        "paper_positions_execution_id_fkey",
        "paper_positions",
        type_="foreignkey",
    )
    op.drop_column("paper_positions", "execution_id")
    op.create_foreign_key(
        "paper_positions_identity_fkey",
        "paper_positions",
        "paper_executions",
        ["identity"],
        ["identity"],
        ondelete="RESTRICT",
    )
