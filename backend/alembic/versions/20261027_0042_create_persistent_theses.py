"""Create append-only thesis identities and diagnostic lifecycle events."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261027_0042"
down_revision: str | None = "20261026_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_theses",
        sa.Column("thesis_id", sa.String(256), nullable=False),
        sa.Column("instrument", sa.String(64), nullable=False),
        sa.Column("timeframe", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("original_assessment_id", sa.String(256), nullable=False),
        sa.Column("original_opportunity_id", sa.String(256), nullable=False),
        sa.Column("original_opportunity_version_id", sa.String(256), nullable=False),
        sa.Column("original_entry_lower", sa.Numeric(38, 18), nullable=True),
        sa.Column("original_entry_upper", sa.Numeric(38, 18), nullable=True),
        sa.Column("original_stop", sa.Numeric(38, 18), nullable=True),
        sa.Column("original_target", sa.Numeric(38, 18), nullable=True),
        sa.Column("original_plan", postgresql.JSONB, nullable=True),
        sa.Column("original_evidence", postgresql.JSONB, nullable=False),
        sa.Column("original_reason_codes", postgresql.JSONB, nullable=False),
        sa.Column("current_state", sa.String(32), nullable=False, server_default="DETECTED"),
        sa.Column("strategy_policy_version", sa.String(128), nullable=False),
        sa.Column("provenance_hash", sa.String(64), nullable=False),
        sa.Column("original_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("direction IN ('BUY', 'SELL')", name="ck_opportunity_thesis_direction"),
        sa.CheckConstraint(
            "current_state IN ('DETECTED', 'WAITING_FOR_ENTRY', 'ENTRY_AVAILABLE', 'ENTRY_MISSED', 'MONITORING', 'INITIAL_TARGET_REACHED', 'INVALIDATED', 'EXPIRED', 'RESOLVED', 'OUTCOME_AMBIGUOUS')",
            name="ck_opportunity_thesis_state",
        ),
        sa.PrimaryKeyConstraint("thesis_id"),
        sa.UniqueConstraint("original_assessment_id", name="uq_opportunity_thesis_original_assessment"),
    )
    op.create_index(
        "ix_opportunity_theses_scope_state",
        "opportunity_theses",
        ["instrument", "timeframe", "direction", "current_state"],
    )
    op.create_table(
        "opportunity_thesis_assessments",
        sa.Column("thesis_id", sa.String(256), nullable=False),
        sa.Column("assessment_id", sa.String(256), nullable=False),
        sa.Column("opportunity_version_id", sa.String(256), nullable=False),
        sa.Column("match_status", sa.String(32), nullable=False),
        sa.Column("match_reason", sa.String(512), nullable=False),
        sa.Column("assessment_payload", postgresql.JSONB, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["opportunity_theses.thesis_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("match_status IN ('NEW_THESIS', 'MATCHED_EXACT_GEOMETRY', 'AMBIGUOUS')", name="ck_thesis_assessment_match_status"),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint("thesis_id", "opportunity_version_id", name="uq_thesis_assessment_version"),
    )
    op.create_index(
        "ix_opportunity_thesis_assessments_thesis",
        "opportunity_thesis_assessments",
        ["thesis_id", "observed_at"],
    )
    op.create_table(
        "opportunity_thesis_events",
        sa.Column("event_id", sa.String(256), nullable=False),
        sa.Column("thesis_id", sa.String(256), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["opportunity_theses.thesis_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("event_hash", name="uq_opportunity_thesis_event_hash"),
    )
    op.create_index(
        "ix_opportunity_thesis_events_thesis_time",
        "opportunity_thesis_events",
        ["thesis_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_opportunity_thesis_events_thesis_time", table_name="opportunity_thesis_events")
    op.drop_table("opportunity_thesis_events")
    op.drop_index("ix_opportunity_thesis_assessments_thesis", table_name="opportunity_thesis_assessments")
    op.drop_table("opportunity_thesis_assessments")
    op.drop_index("ix_opportunity_theses_scope_state", table_name="opportunity_theses")
    op.drop_table("opportunity_theses")
