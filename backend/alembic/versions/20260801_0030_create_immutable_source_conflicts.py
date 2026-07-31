"""Create immutable market-data source conflict evidence."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0030"
down_revision: str | None = "20260731_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OUTCOME_REASONS = (
    "terminal_reason IN ('SUCCESS_NEW_INSERTS', 'SUCCESS_REUSE_ONLY', "
    "'PROVIDER_HISTORY_EXHAUSTED', 'PROVIDER_FAILED', 'VALIDATION_FAILED', "
    "'PERSISTENCE_FAILED', 'INTERRUPTED_BEFORE_PERSISTENCE', "
    "'CONFLICT_FAILED')"
)
_OUTCOME_EVIDENCE = (
    "((terminal_reason IN ('SUCCESS_NEW_INSERTS', 'SUCCESS_REUSE_ONLY', "
    "'PROVIDER_HISTORY_EXHAUSTED') AND ingestion_batch_id IS NOT NULL "
    "AND failure_class IS NULL AND failure_summary IS NULL) OR "
    "(terminal_reason IN ('PROVIDER_FAILED', 'VALIDATION_FAILED', "
    "'PERSISTENCE_FAILED', 'INTERRUPTED_BEFORE_PERSISTENCE') "
    "AND ingestion_batch_id IS NULL AND failure_class IS NOT NULL) OR "
    "(terminal_reason = 'CONFLICT_FAILED' AND ingestion_batch_id IS NOT NULL "
    "AND failure_class IS NOT NULL))"
)


def upgrade() -> None:
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "reused_candle_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column(
            "conflict_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "market_data_ingestion_batches",
        sa.Column("source_data_hash", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "ck_ingestion_batches_conflict_counts",
        "market_data_ingestion_batches",
        "reused_candle_count >= 0 AND conflict_count >= 0 AND "
        "(conflict_count = 0 OR persisted_candle_count = 0) AND "
        "(source_data_hash IS NULL OR char_length(source_data_hash) = 64)",
    )

    op.drop_constraint(
        "ck_historical_acquisition_outcomes_reason",
        "historical_acquisition_outcomes",
        type_="check",
    )
    op.drop_constraint(
        "ck_historical_acquisition_outcomes_evidence",
        "historical_acquisition_outcomes",
        type_="check",
    )
    op.create_check_constraint(
        "ck_historical_acquisition_outcomes_reason",
        "historical_acquisition_outcomes",
        _OUTCOME_REASONS,
    )
    op.create_check_constraint(
        "ck_historical_acquisition_outcomes_evidence",
        "historical_acquisition_outcomes",
        _OUTCOME_EVIDENCE,
    )

    op.create_table(
        "market_data_source_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("hash_schema_version", sa.String(32), nullable=False),
        sa.Column("conflict_type", sa.String(64), nullable=False),
        sa.Column("asset_identifier", sa.String(32), nullable=False),
        sa.Column("quote_currency", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("candle_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_candle_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_provider", sa.String(32), nullable=False),
        sa.Column("canonical_open", sa.Numeric(38, 18), nullable=False),
        sa.Column("canonical_high", sa.Numeric(38, 18), nullable=False),
        sa.Column("canonical_low", sa.Numeric(38, 18), nullable=False),
        sa.Column("canonical_close", sa.Numeric(38, 18), nullable=False),
        sa.Column("canonical_volume", sa.Numeric(38, 18), nullable=False),
        sa.Column("incoming_attempt_id", sa.Uuid(), nullable=True),
        sa.Column("incoming_ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("incoming_provider", sa.String(32), nullable=False),
        sa.Column("incoming_open", sa.Numeric(38, 18), nullable=False),
        sa.Column("incoming_high", sa.Numeric(38, 18), nullable=False),
        sa.Column("incoming_low", sa.Numeric(38, 18), nullable=False),
        sa.Column("incoming_close", sa.Numeric(38, 18), nullable=False),
        sa.Column("incoming_volume", sa.Numeric(38, 18), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_candle_hash", sa.String(64), nullable=False),
        sa.Column("incoming_candle_hash", sa.String(64), nullable=False),
        sa.Column("incoming_batch_source_hash", sa.String(64), nullable=False),
        sa.Column("conflict_hash", sa.String(64), nullable=False),
        sa.Column(
            "immutable",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "conflict_type IN ('provider_revision_conflict', "
            "'provider_identity_conflict')",
            name="ck_source_conflicts_type",
        ),
        sa.CheckConstraint(
            "asset_identifier = 'BTC' AND quote_currency = 'USD' "
            "AND timeframe IN ('5m', '15m')",
            name="ck_source_conflicts_scope",
        ),
        sa.CheckConstraint(
            "char_length(canonical_candle_hash) = 64 AND "
            "char_length(incoming_candle_hash) = 64 AND "
            "char_length(incoming_batch_source_hash) = 64 AND "
            "char_length(conflict_hash) = 64",
            name="ck_source_conflicts_hashes",
        ),
        sa.CheckConstraint("immutable", name="ck_source_conflicts_immutable"),
        sa.ForeignKeyConstraint(
            ["canonical_candle_id"],
            ["market_data_candles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incoming_attempt_id"],
            ["historical_acquisition_attempts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incoming_ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "incoming_ingestion_batch_id",
            "canonical_candle_id",
            name="uq_source_conflicts_batch_candle",
        ),
    )
    op.create_index(
        "ix_source_conflicts_scope_timestamp",
        "market_data_source_conflicts",
        ["asset_identifier", "quote_currency", "timeframe", "candle_timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_conflicts_scope_timestamp",
        table_name="market_data_source_conflicts",
    )
    op.drop_table("market_data_source_conflicts")

    op.drop_constraint(
        "ck_historical_acquisition_outcomes_evidence",
        "historical_acquisition_outcomes",
        type_="check",
    )
    op.drop_constraint(
        "ck_historical_acquisition_outcomes_reason",
        "historical_acquisition_outcomes",
        type_="check",
    )
    op.create_check_constraint(
        "ck_historical_acquisition_outcomes_reason",
        "historical_acquisition_outcomes",
        "terminal_reason IN ('SUCCESS_NEW_INSERTS', 'SUCCESS_REUSE_ONLY', "
        "'PROVIDER_HISTORY_EXHAUSTED', 'PROVIDER_FAILED', "
        "'VALIDATION_FAILED', 'PERSISTENCE_FAILED', "
        "'INTERRUPTED_BEFORE_PERSISTENCE')",
    )
    op.create_check_constraint(
        "ck_historical_acquisition_outcomes_evidence",
        "historical_acquisition_outcomes",
        "((terminal_reason IN ('SUCCESS_NEW_INSERTS', "
        "'SUCCESS_REUSE_ONLY', 'PROVIDER_HISTORY_EXHAUSTED') "
        "AND ingestion_batch_id IS NOT NULL AND failure_class IS NULL "
        "AND failure_summary IS NULL) OR "
        "(terminal_reason IN ('PROVIDER_FAILED', 'VALIDATION_FAILED', "
        "'PERSISTENCE_FAILED', 'INTERRUPTED_BEFORE_PERSISTENCE') "
        "AND ingestion_batch_id IS NULL AND failure_class IS NOT NULL))",
    )

    op.drop_constraint(
        "ck_ingestion_batches_conflict_counts",
        "market_data_ingestion_batches",
        type_="check",
    )
    op.drop_column("market_data_ingestion_batches", "source_data_hash")
    op.drop_column("market_data_ingestion_batches", "conflict_count")
    op.drop_column("market_data_ingestion_batches", "reused_candle_count")
