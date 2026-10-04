"""Add append-only events for human-selected paper tracking."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260929_0039"
down_revision: str | None = "20260925_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_tracking_events",
        sa.Column("event_id", sa.String(length=256), nullable=False),
        sa.Column("execution_id", sa.String(length=256), nullable=False),
        sa.Column("position_id", sa.String(length=256), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(length=256), nullable=True),
        sa.Column("opportunity_id", sa.String(length=256), nullable=False),
        sa.Column("opportunity_version_id", sa.String(length=256), nullable=False),
        sa.Column("source_execution_hash", sa.String(length=64), nullable=False),
        sa.Column("source_position_hash", sa.String(length=64), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=256), nullable=True),
        sa.Column("source_artifact_hash", sa.String(length=64), nullable=True),
        sa.Column("exit_id", sa.String(length=256), nullable=True),
        sa.Column("outcome_id", sa.String(length=256), nullable=True),
        sa.Column("canonical_payload", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_paper_tracking_event_sequence_positive"),
        sa.CheckConstraint("char_length(canonical_hash) = 64", name="ck_paper_tracking_event_hash"),
        sa.CheckConstraint("char_length(source_execution_hash) = 64", name="ck_paper_tracking_execution_hash"),
        sa.CheckConstraint("char_length(source_position_hash) = 64", name="ck_paper_tracking_position_hash"),
        sa.CheckConstraint(
            "source_artifact_hash IS NULL OR char_length(source_artifact_hash) = 64",
            name="ck_paper_tracking_source_hash",
        ),
        sa.CheckConstraint(
            "event_type IN ('PAPER_TRACKING_SELECTED', 'ENTRY_REACHED', 'DATA_INSUFFICIENT', "
            "'EXPIRED_BEFORE_ENTRY', 'EXPIRED_AFTER_ENTRY', 'AMBIGUOUS_INTRABAR', "
            "'TARGET_HIT', 'STOP_LOSS_HIT', 'POST_OUTCOME_OBSERVATION')",
            name="ck_paper_tracking_event_type",
        ),
        sa.CheckConstraint(
            "event_type <> 'PAPER_TRACKING_SELECTED' OR actor_id IS NOT NULL",
            name="ck_paper_tracking_selection_actor",
        ),
        sa.CheckConstraint(
            "event_type NOT IN ('ENTRY_REACHED', 'EXPIRED_BEFORE_ENTRY', 'EXPIRED_AFTER_ENTRY', "
            "'AMBIGUOUS_INTRABAR', 'TARGET_HIT', "
            "'STOP_LOSS_HIT', 'POST_OUTCOME_OBSERVATION') OR "
            "(source_artifact_id IS NOT NULL AND source_artifact_hash IS NOT NULL AND available_at IS NOT NULL)",
            name="ck_paper_tracking_market_source",
        ),
        sa.CheckConstraint(
            "(event_type IN ('TARGET_HIT', 'STOP_LOSS_HIT', 'POST_OUTCOME_OBSERVATION') "
            "AND exit_id IS NOT NULL AND outcome_id IS NOT NULL) OR "
            "(event_type NOT IN ('TARGET_HIT', 'STOP_LOSS_HIT', 'POST_OUTCOME_OBSERVATION') "
            "AND exit_id IS NULL AND outcome_id IS NULL)",
            name="ck_paper_tracking_terminal_refs",
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["paper_executions.identity"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["position_id"], ["paper_positions.identity"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["exit_id"], ["paper_exits.identity"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["outcome_id"], ["paper_outcomes.identity"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("execution_id", "sequence", name="uq_paper_tracking_event_sequence"),
        sa.UniqueConstraint("idempotency_key", name="uq_paper_tracking_event_idempotency"),
    )
    op.create_index(
        "uq_paper_tracking_one_selection",
        "paper_tracking_events",
        ["execution_id"],
        unique=True,
        postgresql_where=sa.text("event_type = 'PAPER_TRACKING_SELECTED'"),
    )
    op.execute(
        "CREATE TRIGGER trg_paper_tracking_events_immutable "
        "BEFORE UPDATE OR DELETE ON paper_tracking_events "
        "FOR EACH ROW EXECUTE FUNCTION alphalens_reject_immutable_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_paper_tracking_events_immutable ON paper_tracking_events"
    )
    op.drop_index("uq_paper_tracking_one_selection", table_name="paper_tracking_events")
    op.drop_table("paper_tracking_events")
