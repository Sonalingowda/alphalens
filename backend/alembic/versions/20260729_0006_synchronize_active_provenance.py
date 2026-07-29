"""Synchronize active research-dataset provenance."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0006"
down_revision: str | None = "20260729_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in (
        "market_data_ingestion_batches",
        "feature_pipeline_runs",
        "validation_runs",
    ):
        op.add_column(
            table_name,
            sa.Column(
                "is_active",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )
        op.add_column(
            table_name,
            sa.Column(
                "superseded_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    op.add_column(
        "validation_runs",
        sa.Column("source_feature_run_id", sa.Uuid(), nullable=True),
    )

    op.execute(
        """
        WITH canonical AS (
            SELECT id
            FROM market_data_ingestion_batches
            WHERE asset_identifier = 'BTC'
              AND quote_currency = 'USD'
              AND timeframe = '1d'
              AND validation_passed
            ORDER BY candle_count DESC, retrieved_at DESC, created_at DESC
            LIMIT 1
        )
        UPDATE market_data_ingestion_batches
        SET is_active = (id = (SELECT id FROM canonical)),
            superseded_at = CASE
                WHEN id <> (SELECT id FROM canonical) THEN now()
                ELSE NULL
            END
        WHERE asset_identifier = 'BTC'
          AND quote_currency = 'USD'
          AND timeframe = '1d'
        """
    )
    op.execute(
        """
        WITH canonical AS (
            SELECT id
            FROM feature_pipeline_runs
            WHERE asset_identifier = 'BTC'
              AND quote_currency = 'USD'
              AND timeframe = '1d'
              AND persisted_value_count > 0
            ORDER BY source_candle_count DESC, computed_at DESC
            LIMIT 1
        )
        UPDATE feature_pipeline_runs
        SET is_active = (id = (SELECT id FROM canonical)),
            superseded_at = CASE
                WHEN id <> (SELECT id FROM canonical) THEN now()
                ELSE NULL
            END
        WHERE asset_identifier = 'BTC'
          AND quote_currency = 'USD'
          AND timeframe = '1d'
        """
    )
    op.execute(
        """
        UPDATE validation_runs AS validation
        SET source_feature_run_id = (
            SELECT feature.id
            FROM feature_pipeline_runs AS feature
            WHERE feature.source_ingestion_batch_id =
                    validation.source_ingestion_batch_id
              AND feature.pipeline_version =
                    validation.feature_pipeline_version
              AND feature.persisted_value_count > 0
            ORDER BY feature.computed_at DESC
            LIMIT 1
        )
        """
    )
    op.execute(
        """
        WITH canonical AS (
            SELECT id
            FROM validation_runs
            WHERE asset_identifier = 'BTC'
              AND quote_currency = 'USD'
              AND timeframe = '1d'
            ORDER BY source_observation_count DESC, created_at DESC
            LIMIT 1
        )
        UPDATE validation_runs
        SET is_active = (id = (SELECT id FROM canonical)),
            superseded_at = CASE
                WHEN id <> (SELECT id FROM canonical) THEN now()
                ELSE NULL
            END
        WHERE asset_identifier = 'BTC'
          AND quote_currency = 'USD'
          AND timeframe = '1d'
        """
    )

    op.alter_column(
        "validation_runs",
        "source_feature_run_id",
        nullable=False,
    )
    op.create_foreign_key(
        "fk_validation_runs_source_feature_run_id",
        "validation_runs",
        "feature_pipeline_runs",
        ["source_feature_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_active_ingestion_batch_market",
        "market_data_ingestion_batches",
        ["asset_identifier", "quote_currency", "timeframe"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_active_feature_run_market",
        "feature_pipeline_runs",
        ["asset_identifier", "quote_currency", "timeframe"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "uq_active_validation_run_market",
        "validation_runs",
        ["asset_identifier", "quote_currency", "timeframe"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_active_validation_run_market",
        table_name="validation_runs",
    )
    op.drop_index(
        "uq_active_feature_run_market",
        table_name="feature_pipeline_runs",
    )
    op.drop_index(
        "uq_active_ingestion_batch_market",
        table_name="market_data_ingestion_batches",
    )
    op.drop_constraint(
        "fk_validation_runs_source_feature_run_id",
        "validation_runs",
        type_="foreignkey",
    )
    op.drop_column("validation_runs", "source_feature_run_id")
    for table_name in (
        "validation_runs",
        "feature_pipeline_runs",
        "market_data_ingestion_batches",
    ):
        op.drop_column(table_name, "superseded_at")
        op.drop_column(table_name, "is_active")
