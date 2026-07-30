"""Create immutable risk management reports."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0020"
down_revision: str | None = "20260729_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_management_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_version", sa.String(length=32), nullable=False),
        sa.Column("framework_version", sa.String(length=32), nullable=False),
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
        sa.Column("source_backtest_report_id", sa.Uuid(), nullable=False),
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
        sa.Column("risk_event_count", sa.Integer(), nullable=False),
        sa.Column("accepted_trade_count", sa.Integer(), nullable=False),
        sa.Column("rejected_trade_count", sa.Integer(), nullable=False),
        sa.Column("forced_exit_count", sa.Integer(), nullable=False),
        sa.Column("protection_event_count", sa.Integer(), nullable=False),
        sa.Column("risk_event_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "accepted_trade_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "rejected_trade_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("forced_exit_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "protection_event_hash",
            sa.String(length=64),
            nullable=False,
        ),
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
                "AND framework_version = '1.0.0' "
                "AND initial_capital > 0 "
                "AND final_portfolio_value >= 0 "
                "AND risk_event_count > 0 "
                "AND accepted_trade_count >= 0 "
                "AND rejected_trade_count >= 0 "
                "AND forced_exit_count >= 0 "
                "AND protection_event_count >= 0 "
                "AND char_length(configuration_hash) = 64 "
                "AND char_length(result_hash) = 64 "
                "AND char_length(model_dataset_hash) = 64 "
                "AND char_length(split_hash) = 64 "
                "AND char_length(risk_event_hash) = 64 "
                "AND char_length(accepted_trade_hash) = 64 "
                "AND char_length(rejected_trade_hash) = 64 "
                "AND char_length(forced_exit_hash) = 64 "
                "AND char_length(protection_event_hash) = 64 "
                "AND research_artifacts_modified = false "
                "AND deterministic "
                "AND artifact_hashes_verified"
            ),
            name="ck_risk_management_reports_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["selected_experiment_id"],
            ["regression_experiments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_backtest_report_id"],
            ["backtest_reports.id"],
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
            name="uq_risk_management_reports_configuration_hash",
        ),
        sa.UniqueConstraint(
            "result_hash",
            name="uq_risk_management_reports_result_hash",
        ),
    )


def downgrade() -> None:
    op.drop_table("risk_management_reports")
