"""Create immutable Phase-1 historical expansion readiness reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260802_0033"
down_revision: str | None = "20260802_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "historical_expansion_readiness_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("hash_schema_version", sa.String(32), nullable=False),
        sa.Column("asset_identifier", sa.String(32), nullable=False),
        sa.Column("quote_currency", sa.String(16), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_status", sa.String(64), nullable=False),
        sa.Column("acquisition_level_eligible", sa.Boolean(), nullable=False),
        sa.Column("blocker_count", sa.Integer(), nullable=False),
        sa.Column("source_inspection_hash", sa.String(64), nullable=False),
        sa.Column("source_synchronization_hash", sa.String(64), nullable=True),
        sa.Column("source_quality_hash", sa.String(64), nullable=True),
        sa.Column("source_provenance_hash", sa.String(64), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("immutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_identifier = 'BTC' AND quote_currency = 'USD'",
            name="ck_historical_readiness_scope",
        ),
        sa.CheckConstraint(
            "readiness_status IN ("
            "'READY_FOR_DOWNSTREAM_ADEQUACY_EVALUATION', 'BLOCKED')",
            name="ck_historical_readiness_status",
        ),
        sa.CheckConstraint(
            "(readiness_status = 'READY_FOR_DOWNSTREAM_ADEQUACY_EVALUATION' "
            "AND acquisition_level_eligible AND blocker_count = 0) OR "
            "(readiness_status = 'BLOCKED' AND NOT acquisition_level_eligible "
            "AND blocker_count > 0)",
            name="ck_historical_readiness_status_consistency",
        ),
        sa.CheckConstraint(
            "char_length(source_inspection_hash) = 64 AND "
            "(source_synchronization_hash IS NULL OR "
            "char_length(source_synchronization_hash) = 64) AND "
            "(source_quality_hash IS NULL OR "
            "char_length(source_quality_hash) = 64) AND "
            "char_length(source_provenance_hash) = 64 AND "
            "char_length(result_hash) = 64",
            name="ck_historical_readiness_hashes",
        ),
        sa.CheckConstraint("immutable", name="ck_historical_readiness_immutable"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "result_hash",
            name="uq_historical_readiness_result_hash",
        ),
    )
    op.create_index(
        "ix_historical_readiness_as_of",
        "historical_expansion_readiness_reports",
        ["as_of"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_historical_readiness_as_of",
        table_name="historical_expansion_readiness_reports",
    )
    op.drop_table("historical_expansion_readiness_reports")
