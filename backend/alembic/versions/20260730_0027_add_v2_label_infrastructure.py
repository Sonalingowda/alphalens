"""Add non-executable AlphaLens v2 label provenance infrastructure."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0027"
down_revision: str | None = "20260730_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "v2_label_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_identifier", sa.String(96), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("strategy", sa.String(64), nullable=False),
        sa.Column("asset_identifier", sa.String(32), nullable=False),
        sa.Column("quote_currency", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("approval_reference", sa.Text(), nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("registry_hash", sa.String(64), nullable=False),
        sa.Column(
            "infrastructure_schema_version",
            sa.String(32),
            nullable=False,
        ),
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
            "strategy = 'first_touch_barrier'",
            name="ck_v2_label_policies_strategy",
        ),
        sa.CheckConstraint(
            "timeframe IN ('5m', '10m', '15m')",
            name="ck_v2_label_policies_timeframe",
        ),
        sa.CheckConstraint(
            (
                "char_length(configuration_hash) = 64 "
                "AND char_length(registry_hash) = 64"
            ),
            name="ck_v2_label_policies_hashes",
        ),
        sa.CheckConstraint(
            "immutable",
            name="ck_v2_label_policies_immutable",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_identifier",
            "policy_version",
            "asset_identifier",
            "quote_currency",
            "timeframe",
            name="uq_v2_label_policies_identity",
        ),
    )
    op.create_index(
        "ix_v2_label_policies_configuration_hash",
        "v2_label_policies",
        ["configuration_hash"],
        unique=False,
    )

    op.create_table(
        "v2_label_generation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("source_feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("feature_pipeline_version", sa.String(32), nullable=False),
        sa.Column("registry_hash", sa.String(64), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("source_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("source_provenance_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("source_observation_count", sa.Integer(), nullable=False),
        sa.Column("generated_label_count", sa.Integer(), nullable=False),
        sa.Column("excluded_observation_count", sa.Integer(), nullable=False),
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
        sa.Column("point_in_time_validated", sa.Boolean(), nullable=False),
        sa.Column(
            "immutable",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "source_observation_count > 0 "
                "AND generated_label_count >= 0 "
                "AND excluded_observation_count >= 0 "
                "AND source_observation_count = generated_label_count "
                "+ excluded_observation_count"
            ),
            name="ck_v2_label_runs_counts",
        ),
        sa.CheckConstraint(
            "source_range_start <= source_range_end",
            name="ck_v2_label_runs_range",
        ),
        sa.CheckConstraint(
            (
                "char_length(configuration_hash) = 64 "
                "AND char_length(source_snapshot_hash) = 64 "
                "AND char_length(source_provenance_hash) = 64 "
                "AND char_length(result_hash) = 64"
            ),
            name="ck_v2_label_runs_hashes",
        ),
        sa.CheckConstraint(
            "point_in_time_validated AND immutable",
            name="ck_v2_label_runs_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["v2_label_policies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_feature_run_id"],
            ["feature_pipeline_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_v2_label_runs_policy_id",
        "v2_label_generation_runs",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_label_runs_feature_run_id",
        "v2_label_generation_runs",
        ["source_feature_run_id"],
        unique=False,
    )

    op.create_table(
        "v2_label_observations",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("generation_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "prediction_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "evidence_cutoff",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "outcome_interval_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "outcome_interval_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "label_available_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("label_class", sa.String(8), nullable=True),
        sa.Column("exclusion_reason", sa.String(96), nullable=True),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "(label_class IN ('BUY', 'SELL', 'WAIT') "
                "AND exclusion_reason IS NULL) "
                "OR (label_class IS NULL "
                "AND exclusion_reason IS NOT NULL)"
            ),
            name="ck_v2_label_observations_outcome",
        ),
        sa.CheckConstraint(
            (
                "prediction_timestamp < label_available_at "
                "AND outcome_interval_start <= outcome_interval_end "
                "AND outcome_interval_end <= label_available_at"
            ),
            name="ck_v2_label_observations_chronology",
        ),
        sa.CheckConstraint(
            "char_length(result_hash) = 64",
            name="ck_v2_label_observations_result_hash",
        ),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["v2_label_generation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "generation_run_id",
            "prediction_timestamp",
            name="uq_v2_label_observations_run_timestamp",
        ),
    )
    op.create_index(
        "ix_v2_label_observations_prediction_timestamp",
        "v2_label_observations",
        ["prediction_timestamp"],
        unique=False,
    )

    op.create_table(
        "v2_label_run_sources",
        sa.Column("generation_run_id", sa.Uuid(), nullable=False),
        sa.Column("candle_id", sa.BigInteger(), nullable=False),
        sa.Column("source_role", sa.String(32), nullable=False),
        sa.Column("source_subset_hash", sa.String(64), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(source_role) > 0",
            name="ck_v2_label_run_sources_role",
        ),
        sa.CheckConstraint(
            "char_length(source_subset_hash) = 64",
            name="ck_v2_label_run_sources_hash",
        ),
        sa.ForeignKeyConstraint(
            ["candle_id"],
            ["market_data_candles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["v2_label_generation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "generation_run_id",
            "candle_id",
            "source_role",
        ),
    )
    op.create_index(
        "ix_v2_label_run_sources_candle_id",
        "v2_label_run_sources",
        ["candle_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_v2_label_run_sources_candle_id",
        table_name="v2_label_run_sources",
    )
    op.drop_table("v2_label_run_sources")
    op.drop_index(
        "ix_v2_label_observations_prediction_timestamp",
        table_name="v2_label_observations",
    )
    op.drop_table("v2_label_observations")
    op.drop_index(
        "ix_v2_label_runs_feature_run_id",
        table_name="v2_label_generation_runs",
    )
    op.drop_index(
        "ix_v2_label_runs_policy_id",
        table_name="v2_label_generation_runs",
    )
    op.drop_table("v2_label_generation_runs")
    op.drop_index(
        "ix_v2_label_policies_configuration_hash",
        table_name="v2_label_policies",
    )
    op.drop_table("v2_label_policies")
