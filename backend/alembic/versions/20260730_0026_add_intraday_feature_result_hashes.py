"""Add immutable intraday feature result provenance hashes."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0026"
down_revision: str | None = "20260730_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_pipeline_runs",
        sa.Column(
            "source_provenance_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )
    op.add_column(
        "feature_pipeline_runs",
        sa.Column("result_hash", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_feature_pipeline_runs_result_hashes",
        "feature_pipeline_runs",
        (
            "(source_provenance_hash IS NULL AND result_hash IS NULL) "
            "OR (char_length(source_provenance_hash) = 64 "
            "AND char_length(result_hash) = 64)"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_feature_pipeline_runs_result_hashes",
        "feature_pipeline_runs",
        type_="check",
    )
    op.drop_column("feature_pipeline_runs", "result_hash")
    op.drop_column(
        "feature_pipeline_runs",
        "source_provenance_hash",
    )
