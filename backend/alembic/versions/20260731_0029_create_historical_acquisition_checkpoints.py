"""Create resumable historical acquisition evidence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0029"
down_revision: str | None = "20260731_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_acquisition_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("endpoint_identity", sa.String(96), nullable=False),
        sa.Column("asset_identifier", sa.String(32), nullable=False),
        sa.Column("quote_currency", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "requested_end_exclusive", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_identifier", sa.String(96), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("code_version", sa.String(64), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("attempt_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "timeframe IN ('5m', '15m')",
            name="ck_historical_acquisition_attempts_timeframe",
        ),
        sa.CheckConstraint(
            "requested_start < requested_end_exclusive",
            name="ck_historical_acquisition_attempts_range",
        ),
        sa.CheckConstraint(
            "char_length(policy_hash) = 64 AND char_length(configuration_hash) = 64 AND char_length(attempt_hash) = 64",
            name="ck_historical_acquisition_attempts_hashes",
        ),
        sa.CheckConstraint(
            "immutable", name="ck_historical_acquisition_attempts_immutable"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_historical_acquisition_attempts_scope",
        "historical_acquisition_attempts",
        ["asset_identifier", "quote_currency", "timeframe", "started_at"],
        unique=False,
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column("acquisition_attempt_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ingestion_batches_acquisition_attempt_id",
        "market_data_ingestion_batches",
        "historical_acquisition_attempts",
        ["acquisition_attempt_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ingestion_batches_acquisition_attempt_id",
        "market_data_ingestion_batches",
        ["acquisition_attempt_id"],
        unique=False,
    )
    op.create_table(
        "historical_acquisition_outcomes",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Uuid(), nullable=True),
        sa.Column("terminal_reason", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(96), nullable=True),
        sa.Column("failure_summary", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint(
            "terminal_reason IN ('SUCCESS_NEW_INSERTS', 'SUCCESS_REUSE_ONLY', 'PROVIDER_HISTORY_EXHAUSTED', 'PROVIDER_FAILED', 'VALIDATION_FAILED', 'PERSISTENCE_FAILED', 'INTERRUPTED_BEFORE_PERSISTENCE')",
            name="ck_historical_acquisition_outcomes_reason",
        ),
        sa.CheckConstraint(
            "((terminal_reason IN ('SUCCESS_NEW_INSERTS', 'SUCCESS_REUSE_ONLY', 'PROVIDER_HISTORY_EXHAUSTED') AND ingestion_batch_id IS NOT NULL AND failure_class IS NULL AND failure_summary IS NULL) OR (terminal_reason IN ('PROVIDER_FAILED', 'VALIDATION_FAILED', 'PERSISTENCE_FAILED', 'INTERRUPTED_BEFORE_PERSISTENCE') AND ingestion_batch_id IS NULL AND failure_class IS NOT NULL))",
            name="ck_historical_acquisition_outcomes_evidence",
        ),
        sa.CheckConstraint(
            "immutable", name="ck_historical_acquisition_outcomes_immutable"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["historical_acquisition_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
    )
    op.create_table(
        "historical_acquisition_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_checkpoint_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("hash_schema_version", sa.String(32), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "requested_end_exclusive", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "provider_available_start", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("provider_available_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_cursor", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_row_count", sa.Integer(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("excluded_incomplete_count", sa.Integer(), nullable=False),
        sa.Column("reused_count", sa.Integer(), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("conflict_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("validation_passed", sa.Boolean(), nullable=False),
        sa.Column("provider_limit_reached", sa.Boolean(), nullable=False),
        sa.Column("terminal_reason", sa.String(64), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("source_data_hash", sa.String(64), nullable=False),
        sa.Column("progress_hash", sa.String(64), nullable=False),
        sa.Column("checkpoint_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "timeframe IN ('5m', '15m')",
            name="ck_historical_acquisition_checkpoints_timeframe",
        ),
        sa.CheckConstraint(
            "provider_row_count >= 0 AND accepted_count > 0 AND excluded_incomplete_count >= 0 AND reused_count >= 0 AND inserted_count >= 0 AND conflict_count = 0 AND accepted_count = reused_count + inserted_count",
            name="ck_historical_acquisition_checkpoints_counts",
        ),
        sa.CheckConstraint(
            "char_length(configuration_hash) = 64 AND char_length(source_data_hash) = 64 AND char_length(progress_hash) = 64 AND char_length(checkpoint_hash) = 64",
            name="ck_historical_acquisition_checkpoints_hashes",
        ),
        sa.CheckConstraint(
            "terminal_reason IN ('SUCCESS_NEW_INSERTS', 'SUCCESS_REUSE_ONLY', 'PROVIDER_HISTORY_EXHAUSTED')",
            name="ck_historical_acquisition_checkpoints_reason",
        ),
        sa.CheckConstraint(
            "validation_passed", name="ck_historical_acquisition_checkpoints_validation"
        ),
        sa.CheckConstraint(
            "immutable", name="ck_historical_acquisition_checkpoints_immutable"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"], ["historical_acquisition_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["predecessor_checkpoint_id"],
            ["historical_acquisition_checkpoints.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "attempt_id", name="uq_historical_acquisition_checkpoints_attempt"
        ),
    )
    op.create_index(
        "ix_historical_acquisition_checkpoints_scope",
        "historical_acquisition_checkpoints",
        ["timeframe", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_acquisition_checkpoints_scope",
        table_name="historical_acquisition_checkpoints",
    )
    op.drop_table("historical_acquisition_checkpoints")
    op.drop_table("historical_acquisition_outcomes")
    op.drop_index(
        "ix_ingestion_batches_acquisition_attempt_id",
        table_name="market_data_ingestion_batches",
    )
    op.drop_constraint(
        "fk_ingestion_batches_acquisition_attempt_id",
        "market_data_ingestion_batches",
        type_="foreignkey",
    )
    op.drop_column("market_data_ingestion_batches", "acquisition_attempt_id")
    op.drop_index(
        "ix_historical_acquisition_attempts_scope",
        table_name="historical_acquisition_attempts",
    )
    op.drop_table("historical_acquisition_attempts")
