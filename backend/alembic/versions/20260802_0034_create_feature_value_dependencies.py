"""Create ordered feature-value dependency provenance."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260802_0034"
down_revision: str | None = "20260802_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_value_dependencies",
        sa.Column("feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("feature_value_id", sa.BigInteger(), nullable=False),
        sa.Column("dependency_ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "dependency_feature_value_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dependency_ordinal >= 0",
            name="ck_feature_value_dependencies_nonnegative_ordinal",
        ),
        sa.CheckConstraint(
            "feature_value_id <> dependency_feature_value_id",
            name="ck_feature_value_dependencies_distinct_values",
        ),
        sa.ForeignKeyConstraint(
            ["feature_run_id"],
            ["feature_pipeline_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["feature_value_id"],
            ["engineered_features.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dependency_feature_value_id"],
            ["engineered_features.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "feature_run_id",
            "feature_value_id",
            "dependency_ordinal",
        ),
    )
    op.create_index(
        "ix_feature_value_dependencies_dependency_value_id",
        "feature_value_dependencies",
        ["dependency_feature_value_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_feature_value_dependencies_dependency_value_id",
        table_name="feature_value_dependencies",
    )
    op.drop_table("feature_value_dependencies")
