"""Create durable, fenced notification delivery queue state."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_0041"
down_revision: str | None = "20261003_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_delivery_jobs",
        sa.Column("job_id", sa.String(length=256), nullable=False),
        sa.Column("notification_id", sa.String(length=256), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_expired_recoveries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=256), nullable=True),
        sa.Column("provider_reference", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("state IN ('PENDING', 'CLAIMED', 'RETRYABLE_FAILURE', 'DELIVERED', 'PERMANENT_FAILURE', 'EXPIRED')", name="ck_notification_delivery_job_state"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts", name="ck_notification_delivery_job_attempts"),
        sa.CheckConstraint("claim_version >= 0 AND lease_expired_recoveries >= 0", name="ck_notification_delivery_job_versions"),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_notification_delivery_job_idempotency"),
    )
    op.create_index(
        "ix_notification_delivery_jobs_claimable",
        "notification_delivery_jobs",
        ["state", "next_attempt_at", "lease_expires_at"],
    )
    op.create_index(
        "ix_notification_delivery_jobs_observability",
        "notification_delivery_jobs",
        ["state", "created_at", "updated_at"],
    )
    op.create_table(
        "notification_delivery_attempts",
        sa.Column("attempt_id", sa.String(length=320), nullable=False),
        sa.Column("job_id", sa.String(length=256), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("lease_token", sa.String(length=64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_reference", sa.String(length=256), nullable=True),
        sa.Column("failure_category", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_notification_delivery_attempt_sequence"),
        sa.CheckConstraint("state IN ('IN_FLIGHT', 'RETRYABLE_FAILURE', 'DELIVERED', 'PERMANENT_FAILURE', 'EXPIRED')", name="ck_notification_delivery_attempt_state"),
        sa.ForeignKeyConstraint(["job_id"], ["notification_delivery_jobs.job_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint("job_id", "sequence", name="uq_notification_delivery_attempt_sequence"),
    )
    op.create_index(
        "ix_notification_delivery_attempts_job_sequence",
        "notification_delivery_attempts",
        ["job_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_delivery_attempts_job_sequence", table_name="notification_delivery_attempts")
    op.drop_table("notification_delivery_attempts")
    op.drop_index("ix_notification_delivery_jobs_observability", table_name="notification_delivery_jobs")
    op.drop_index("ix_notification_delivery_jobs_claimable", table_name="notification_delivery_jobs")
    op.drop_table("notification_delivery_jobs")

