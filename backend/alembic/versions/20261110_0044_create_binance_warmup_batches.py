"""Create crash-safe Binance warmup batch lineage."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261110_0044"
down_revision: str | None = "20261027_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "binance_warmup_batches",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_id", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=False),
        sa.Column("request_parameters", postgresql.JSONB(), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_end_exclusive", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_response_hash", sa.String(64), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("contiguous_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contiguous_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_version", sa.String(128), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("membership_hash", sa.String(64), nullable=False),
        sa.Column("batch_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("symbol = 'BTCUSDT' AND interval = '5m'", name="ck_binance_warmup_batches_scope"),
        sa.CheckConstraint("requested_start < requested_end_exclusive", name="ck_binance_warmup_batches_range"),
        sa.CheckConstraint("candle_count >= 200", name="ck_binance_warmup_batches_count"),
        sa.CheckConstraint("contiguous_start < contiguous_end", name="ck_binance_warmup_batches_contiguous_range"),
        sa.CheckConstraint("char_length(source_response_hash) = 64 AND char_length(configuration_hash) = 64 AND char_length(membership_hash) = 64 AND char_length(batch_hash) = 64", name="ck_binance_warmup_batches_hashes"),
        sa.CheckConstraint("state IN ('PENDING', 'ACCEPTED', 'REJECTED', 'RECOVERY_REQUIRED')", name="ck_binance_warmup_batches_state"),
        sa.CheckConstraint("(state = 'ACCEPTED') = (accepted_at IS NOT NULL)", name="ck_binance_warmup_batches_acceptance"),
        sa.CheckConstraint("immutable", name="ck_binance_warmup_batches_immutable"),
        sa.PrimaryKeyConstraint("batch_id"),
        sa.UniqueConstraint("lineage_id", name="uq_binance_warmup_batches_lineage"),
        sa.UniqueConstraint("batch_hash", name="uq_binance_warmup_batches_hash"),
    )
    op.create_index(
        "ix_binance_warmup_batches_scope",
        "binance_warmup_batches",
        ["symbol", "interval", "state", "contiguous_end"],
    )
    op.create_table(
        "binance_warmup_batch_members",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(256), nullable=False),
        sa.Column("candle_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_payload_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_result_hash", sa.String(64), nullable=False),
        sa.Column("member_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_binance_warmup_members_ordinal"),
        sa.CheckConstraint("char_length(source_payload_hash) = 64 AND char_length(snapshot_result_hash) = 64 AND char_length(member_hash) = 64", name="ck_binance_warmup_members_hashes"),
        sa.CheckConstraint("immutable", name="ck_binance_warmup_members_immutable"),
        sa.ForeignKeyConstraint(["batch_id"], ["binance_warmup_batches.batch_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("batch_id", "ordinal"),
        sa.UniqueConstraint("batch_id", "snapshot_id", name="uq_binance_warmup_members_snapshot"),
    )
    op.create_index(
        "ix_binance_warmup_members_snapshot",
        "binance_warmup_batch_members",
        ["snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_binance_warmup_members_snapshot", table_name="binance_warmup_batch_members")
    op.drop_table("binance_warmup_batch_members")
    op.drop_index("ix_binance_warmup_batches_scope", table_name="binance_warmup_batches")
    op.drop_table("binance_warmup_batches")
