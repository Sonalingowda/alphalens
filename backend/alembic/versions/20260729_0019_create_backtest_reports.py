"""Create immutable deterministic backtest reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0019"
down_revision: str | None = "20260729_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_version", sa.String(length=32), nullable=False),
        sa.Column("engine_version", sa.String(length=32), nullable=False),
        sa.Column(
            "report_configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("result_hash", sa.String(length=64), nullable=False),
        sa.Column("source_holdout_report_id", sa.Uuid(), nullable=False),
        sa.Column("selected_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "prediction_evidence_set_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("strategy_name", sa.String(length=64), nullable=False),
        sa.Column("strategy_version", sa.String(length=32), nullable=False),
        sa.Column(
            "period_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "period_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("initial_capital", sa.Numeric(38, 18), nullable=False),
        sa.Column(
            "final_portfolio_value",
            sa.Numeric(38, 18),
            nullable=False,
        ),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.Column("fill_count", sa.Integer(), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column(
            "daily_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "input_evidence_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("signal_hash", sa.String(length=64), nullable=False),
        sa.Column("trade_log_hash", sa.String(length=64), nullable=False),
        sa.Column("equity_curve_hash", sa.String(length=64), nullable=False),
        sa.Column("daily_history_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "research_artifacts_modified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("deterministic", sa.Boolean(), nullable=False),
        sa.Column(
            "artifact_hashes_verified",
            sa.Boolean(),
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
                "report_version = '1.0.0' "
                "AND engine_version = '1.0.0' "
                "AND strategy_name = 'ridge_threshold_long_only' "
                "AND strategy_version = '1.0.0' "
                "AND initial_capital > 0 "
                "AND final_portfolio_value >= 0 "
                "AND signal_count > 0 "
                "AND fill_count >= 0 "
                "AND trade_count >= 0 "
                "AND daily_observation_count > 1 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(input_evidence_hash) = 64 "
                "AND char_length(signal_hash) = 64 "
                "AND char_length(trade_log_hash) = 64 "
                "AND char_length(equity_curve_hash) = 64 "
                "AND char_length(daily_history_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(prediction_evidence_set_hash) = 64 "
                "AND research_artifacts_modified = false "
                "AND deterministic "
                "AND artifact_hashes_verified"
            ),
            name="ck_backtest_reports_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["selected_experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_holdout_report_id"],
            ["holdout_evaluation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_run_id"],
            ["validation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "configuration_hash",
            name="uq_backtest_reports_configuration_hash",
        ),
        sa.UniqueConstraint(
            "result_hash",
            name="uq_backtest_reports_result_hash",
        ),
    )


def downgrade() -> None:
    op.drop_table("backtest_reports")
