"""Create immutable paper trading reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0022"
down_revision: str | None = "20260730_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_trading_reports",
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
        sa.Column("previous_report_id", sa.Uuid(), nullable=True),
        sa.Column("inference_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("selected_experiment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "holdout_evaluation_report_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("validation_run_id", sa.Uuid(), nullable=False),
        sa.Column("session_name", sa.String(length=96), nullable=False),
        sa.Column("cycle_sequence", sa.Integer(), nullable=False),
        sa.Column(
            "cycle_start",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "cycle_end",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "processed_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("model_dataset_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "training_dataset_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "feature_pipeline_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("target_version", sa.String(length=32), nullable=False),
        sa.Column("split_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "inference_artifact_sha256",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "current_cash",
            sa.Numeric(precision=38, scale=18),
            nullable=False,
        ),
        sa.Column(
            "current_equity",
            sa.Numeric(precision=38, scale=18),
            nullable=False,
        ),
        sa.Column("open_position_count", sa.Integer(), nullable=False),
        sa.Column("prediction_count", sa.Integer(), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("risk_event_count", sa.Integer(), nullable=False),
        sa.Column(
            "portfolio_observation_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("audit_event_count", sa.Integer(), nullable=False),
        sa.Column("market_data_hash", sa.String(length=64), nullable=False),
        sa.Column("feature_set_hash", sa.String(length=64), nullable=False),
        sa.Column("prediction_hash", sa.String(length=64), nullable=False),
        sa.Column("signal_hash", sa.String(length=64), nullable=False),
        sa.Column("order_hash", sa.String(length=64), nullable=False),
        sa.Column("trade_hash", sa.String(length=64), nullable=False),
        sa.Column("risk_event_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "portfolio_history_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("audit_log_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_only_inference", sa.Boolean(), nullable=False),
        sa.Column("fit_invoked", sa.Boolean(), nullable=False),
        sa.Column("live_orders_placed", sa.Boolean(), nullable=False),
        sa.Column(
            "research_artifacts_modified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("deterministic", sa.Boolean(), nullable=False),
        sa.Column("artifact_hashes_verified", sa.Boolean(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            (
                "report_version = '1.0.0' "
                "AND engine_version = '2.0.0' "
                "AND cycle_sequence > 0 "
                "AND cycle_start <= cycle_end "
                "AND processed_observation_count > 0 "
                "AND current_cash >= 0 "
                "AND current_equity >= 0 "
                "AND open_position_count BETWEEN 0 AND 1 "
                "AND prediction_count = portfolio_observation_count "
                "AND signal_count = prediction_count "
                "AND order_count >= 0 "
                "AND trade_count >= 0 "
                "AND risk_event_count >= 0 "
                "AND audit_event_count >= prediction_count * 8 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(market_data_hash) = 64 "
                "AND char_length(feature_set_hash) = 64 "
                "AND char_length(prediction_hash) = 64 "
                "AND char_length(signal_hash) = 64 "
                "AND char_length(order_hash) = 64 "
                "AND char_length(trade_hash) = 64 "
                "AND char_length(risk_event_hash) = 64 "
                "AND char_length(portfolio_history_hash) = 64 "
                "AND char_length(audit_log_hash) = 64 "
                "AND char_length(inference_artifact_sha256) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(training_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND artifact_only_inference "
                "AND NOT fit_invoked "
                "AND NOT live_orders_placed "
                "AND NOT research_artifacts_modified "
                "AND deterministic "
                "AND artifact_hashes_verified"
            ),
            name="ck_paper_trading_reports_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["holdout_evaluation_report_id"],
            ["holdout_evaluation_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["inference_artifact_id"],
            ["model_inference_artifacts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_report_id"],
            ["paper_trading_reports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_experiment_id"],
            ["regression_experiments.id"],
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
            "cycle_end",
            name="uq_paper_trading_reports_cycle",
        ),
        sa.UniqueConstraint(
            "result_hash",
            name="uq_paper_trading_reports_result_hash",
        ),
    )
    op.create_index(
        "ix_paper_trading_reports_session_cycle",
        "paper_trading_reports",
        ["session_name", "cycle_end"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_paper_trading_reports_session_cycle",
        table_name="paper_trading_reports",
    )
    op.drop_table("paper_trading_reports")

