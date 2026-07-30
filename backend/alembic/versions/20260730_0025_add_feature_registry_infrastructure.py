"""Add declarative feature registry and provenance infrastructure."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0025"
down_revision: str | None = "20260730_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_pipeline_runs",
        sa.Column("registry_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "feature_pipeline_runs",
        sa.Column(
            "registry_schema_version",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.add_column(
        "feature_pipeline_runs",
        sa.Column(
            "availability_contract_version",
            sa.String(length=32),
            nullable=True,
        ),
    )
    op.add_column(
        "feature_pipeline_runs",
        sa.Column(
            "registry_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_feature_pipeline_runs_registry_metadata",
        "feature_pipeline_runs",
        (
            "(registry_hash IS NULL "
            "AND registry_schema_version IS NULL "
            "AND availability_contract_version IS NULL "
            "AND registry_snapshot IS NULL) "
            "OR (char_length(registry_hash) = 64 "
            "AND registry_schema_version IS NOT NULL "
            "AND availability_contract_version IS NOT NULL "
            "AND registry_snapshot IS NOT NULL)"
        ),
    )

    op.add_column(
        "engineered_features",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_engineered_features_availability",
        "engineered_features",
        (
            "(timeframe = '5m' AND available_at = "
            "candle_timestamp + INTERVAL '5 minutes') "
            "OR (timeframe = '10m' AND available_at = "
            "candle_timestamp + INTERVAL '10 minutes') "
            "OR (timeframe = '15m' AND available_at = "
            "candle_timestamp + INTERVAL '15 minutes') "
            "OR (timeframe = '1d' AND "
            "(available_at IS NULL OR available_at = "
            "candle_timestamp + INTERVAL '1 day')) "
            "OR (timeframe NOT IN ('1d', '5m', '10m', '15m') "
            "AND available_at IS NULL)"
        ),
    )

    op.create_table(
        "feature_pipeline_run_sources",
        sa.Column("feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_candle_count", sa.Integer(), nullable=False),
        sa.Column(
            "source_range_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "source_range_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "source_subset_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_candle_count > 0",
            name="ck_feature_run_sources_positive_count",
        ),
        sa.CheckConstraint(
            "source_range_start <= source_range_end",
            name="ck_feature_run_sources_valid_range",
        ),
        sa.CheckConstraint(
            "char_length(source_subset_hash) = 64",
            name="ck_feature_run_sources_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["feature_run_id"],
            ["feature_pipeline_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["market_data_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "feature_run_id",
            "ingestion_batch_id",
        ),
    )
    op.create_index(
        "ix_feature_run_sources_ingestion_batch_id",
        "feature_pipeline_run_sources",
        ["ingestion_batch_id"],
        unique=False,
    )

    op.create_table(
        "feature_pipeline_run_values",
        sa.Column("feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("feature_value_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
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
        sa.PrimaryKeyConstraint(
            "feature_run_id",
            "feature_value_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("feature_pipeline_run_values")
    op.drop_index(
        "ix_feature_run_sources_ingestion_batch_id",
        table_name="feature_pipeline_run_sources",
    )
    op.drop_table("feature_pipeline_run_sources")
    op.drop_constraint(
        "ck_engineered_features_availability",
        "engineered_features",
        type_="check",
    )
    op.drop_column("engineered_features", "available_at")
    op.drop_constraint(
        "ck_feature_pipeline_runs_registry_metadata",
        "feature_pipeline_runs",
        type_="check",
    )
    op.drop_column("feature_pipeline_runs", "registry_snapshot")
    op.drop_column(
        "feature_pipeline_runs",
        "availability_contract_version",
    )
    op.drop_column("feature_pipeline_runs", "registry_schema_version")
    op.drop_column("feature_pipeline_runs", "registry_hash")
