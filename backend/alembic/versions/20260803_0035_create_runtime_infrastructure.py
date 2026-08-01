"""Create immutable runtime aggregate and policy artifact infrastructure.

Revision ID: 20260803_0035
Revises: 20260802_0034
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260803_0035"
down_revision: str | None = "20260802_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "immutable_runtime_aggregates",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("entity_type", sa.String(length=96), nullable=False),
        sa.Column("entity_id", sa.String(length=256), nullable=False),
        sa.Column("logical_id", sa.String(length=256), nullable=False),
        sa.Column("scope_instrument", sa.String(length=64), nullable=True),
        sa.Column("scope_timeframe", sa.String(length=32), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("canonical_hash", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(canonical_hash) = 64", name="ck_immutable_runtime_aggregate_hash"),
        sa.CheckConstraint("revision = 1", name="ck_immutable_runtime_aggregate_revision"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_immutable_runtime_aggregate_identity"),
    )
    op.create_index(
        "ix_immutable_runtime_scope_latest",
        "immutable_runtime_aggregates",
        ["entity_type", "scope_instrument", "scope_timeframe", "available_at"],
    )
    op.create_index(
        "ix_immutable_runtime_logical_history",
        "immutable_runtime_aggregates",
        ["entity_type", "logical_id", "available_at"],
    )
    op.create_table(
        "policy_artifacts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("artifact_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("octet_length(artifact_bytes) > 0", name="ck_policy_artifact_bytes"),
        sa.CheckConstraint("char_length(artifact_hash) = 64", name="ck_policy_artifact_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", "policy_version", name="uq_policy_artifact"),
    )
    op.execute(
        """
        CREATE FUNCTION alphalens_reject_immutable_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'immutable AlphaLens records cannot be updated or deleted';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table_name in ("immutable_runtime_aggregates", "policy_artifacts"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_immutable
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION alphalens_reject_immutable_mutation()
            """
        )


def downgrade() -> None:
    for table_name in ("policy_artifacts", "immutable_runtime_aggregates"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS alphalens_reject_immutable_mutation()")
    op.drop_table("policy_artifacts")
    op.drop_index("ix_immutable_runtime_logical_history", table_name="immutable_runtime_aggregates")
    op.drop_index("ix_immutable_runtime_scope_latest", table_name="immutable_runtime_aggregates")
    op.drop_table("immutable_runtime_aggregates")
