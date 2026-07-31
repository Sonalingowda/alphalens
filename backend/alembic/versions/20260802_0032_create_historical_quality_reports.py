"""Create immutable historical freshness and adequacy reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260802_0032"
down_revision: str | None = "20260801_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_quality_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("hash_schema_version", sa.String(32), nullable=False),
        sa.Column("acquisition_policy_identifier", sa.String(96), nullable=False),
        sa.Column("acquisition_policy_version", sa.String(32), nullable=False),
        sa.Column("acquisition_policy_hash", sa.String(64), nullable=False),
        sa.Column("source_policy_identifier", sa.String(96), nullable=False),
        sa.Column("source_policy_version", sa.String(32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_policy_status", sa.String(32), nullable=False),
        sa.Column("publication_allowed", sa.Boolean(), nullable=False),
        sa.Column("source_provenance_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "freshness_policy_status = 'POLICY_UNAVAILABLE'",
            name="ck_historical_quality_freshness_policy",
        ),
        sa.CheckConstraint(
            "NOT publication_allowed",
            name="ck_historical_quality_publication_disabled",
        ),
        sa.CheckConstraint(
            "char_length(acquisition_policy_hash) = 64 AND "
            "char_length(source_provenance_hash) = 64 AND "
            "char_length(result_hash) = 64",
            name="ck_historical_quality_hashes",
        ),
        sa.CheckConstraint("immutable", name="ck_historical_quality_immutable"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("result_hash", name="uq_historical_quality_result_hash"),
    )
    op.create_index(
        "ix_historical_quality_as_of",
        "historical_quality_reports",
        ["as_of"],
        unique=False,
    )
    op.create_table(
        "historical_quality_timeframes",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("adequacy_status", sa.String(32), nullable=False),
        sa.Column("acquisition_outcome", sa.String(64), nullable=False),
        sa.Column("freshness_status", sa.String(32), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("source_snapshot_result_hash", sa.String(64), nullable=True),
        sa.Column("source_provenance_hash", sa.String(64), nullable=True),
        sa.Column(
            "first_completed_timestamp", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "last_completed_timestamp", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("elapsed_history_seconds", sa.BigInteger(), nullable=False),
        sa.Column("expected_candle_count", sa.BigInteger(), nullable=False),
        sa.Column("observed_candle_count", sa.BigInteger(), nullable=False),
        sa.Column("gap_count", sa.BigInteger(), nullable=False),
        sa.Column("gap_timestamps", postgresql.JSONB(), nullable=False),
        sa.Column("coverage_ratio", sa.Numeric(38, 18), nullable=False),
        sa.Column("provider_limited_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "expected_latest_completed_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "latest_canonical_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("canonical_lag_seconds", sa.BigInteger(), nullable=True),
        sa.Column("latest_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieval_age_seconds", sa.BigInteger(), nullable=True),
        sa.Column("unresolved_conflict_count", sa.Integer(), nullable=False),
        sa.Column("validation_verified", sa.Boolean(), nullable=False),
        sa.Column("provenance_verified", sa.Boolean(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "timeframe IN ('5m', '10m', '15m')",
            name="ck_historical_quality_timeframes_scope",
        ),
        sa.CheckConstraint(
            "adequacy_status IN ('ADEQUATE', 'INADEQUATE', "
            "'SOURCE_UNAVAILABLE', 'UNAVAILABLE')",
            name="ck_historical_quality_timeframes_status",
        ),
        sa.CheckConstraint(
            "acquisition_outcome IN ("
            "'ADEQUATE_FOR_DOWNSTREAM_ADEQUACY_EVALUATION', "
            "'INADEQUATE_COVERAGE', 'INADEQUATE_CONTINUITY', "
            "'UNRESOLVED_CONFLICT', 'INTEGRITY_FAILURE', "
            "'SOURCE_UNAVAILABLE')",
            name="ck_historical_quality_timeframes_outcome",
        ),
        sa.CheckConstraint(
            "freshness_status = 'POLICY_UNAVAILABLE'",
            name="ck_historical_quality_timeframes_freshness",
        ),
        sa.CheckConstraint(
            "elapsed_history_seconds >= 0 AND expected_candle_count >= 0 "
            "AND observed_candle_count >= 0 AND gap_count >= 0 "
            "AND unresolved_conflict_count >= 0 "
            "AND coverage_ratio >= 0 AND coverage_ratio <= 1",
            name="ck_historical_quality_timeframes_measurements",
        ),
        sa.CheckConstraint(
            "char_length(result_hash) = 64 AND "
            "(source_snapshot_result_hash IS NULL OR "
            "char_length(source_snapshot_result_hash) = 64) AND "
            "(source_provenance_hash IS NULL OR "
            "char_length(source_provenance_hash) = 64)",
            name="ck_historical_quality_timeframes_hashes",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["historical_quality_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["historical_coverage_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("report_id", "timeframe"),
    )
    op.create_index(
        "ix_historical_quality_timeframes_snapshot_id",
        "historical_quality_timeframes",
        ["source_snapshot_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_quality_timeframes_snapshot_id",
        table_name="historical_quality_timeframes",
    )
    op.drop_table("historical_quality_timeframes")
    op.drop_index(
        "ix_historical_quality_as_of",
        table_name="historical_quality_reports",
    )
    op.drop_table("historical_quality_reports")
