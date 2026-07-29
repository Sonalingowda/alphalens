"""Record immutable baseline evaluation policy parameters."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0009"
down_revision: str | None = "20260729_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "regression_experiments",
        sa.Column(
            "evaluation_policy_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column(
        "regression_experiments",
        "evaluation_policy_parameters",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "regression_experiments",
        "evaluation_policy_parameters",
    )
