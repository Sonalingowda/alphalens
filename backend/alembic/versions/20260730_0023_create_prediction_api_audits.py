"""Create immutable live prediction API audits."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0023"
down_revision: str | None = "20260730_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prediction_api_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("api_version", sa.String(length=32), nullable=False),
        sa.Column("http_method", sa.String(length=8), nullable=False),
        sa.Column("request_path", sa.String(length=128), nullable=False),
        sa.Column("request_size_bytes", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_hash", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("configuration_hash", sa.String(length=64), nullable=True),
        sa.Column("schema_hash", sa.String(length=64), nullable=True),
        sa.Column("prediction_hash", sa.String(length=64), nullable=True),
        sa.Column("latency_microseconds", sa.BigInteger(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "audit_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("audit_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_verified", sa.Boolean(), nullable=False),
        sa.Column("fit_invoked", sa.Boolean(), nullable=False),
        sa.Column("read_only_inference", sa.Boolean(), nullable=False),
        sa.Column("immutable", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            (
                "api_version = '1.0.0' "
                "AND http_method IN ('GET', 'POST') "
                "AND request_size_bytes >= 0 "
                "AND response_status BETWEEN 100 AND 599 "
                "AND outcome IN ('success', 'error') "
                "AND latency_microseconds >= 0 "
                "AND received_at <= completed_at "
                "AND char_length(request_hash) = 64 "
                "AND char_length(response_hash) = 64 "
                "AND char_length(audit_hash) = 64 "
                "AND (schema_hash IS NULL "
                "OR char_length(schema_hash) = 64) "
                "AND (prediction_hash IS NULL "
                "OR char_length(prediction_hash) = 64) "
                "AND (artifact_sha256 IS NULL "
                "OR char_length(artifact_sha256) = 64) "
                "AND artifact_verified "
                "AND NOT fit_invoked "
                "AND read_only_inference "
                "AND immutable"
            ),
            name="ck_prediction_api_audits_integrity",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["model_inference_artifacts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "audit_hash",
            name="uq_prediction_api_audits_hash",
        ),
    )
    op.create_index(
        "ix_prediction_api_audits_received_at",
        "prediction_api_audits",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prediction_api_audits_received_at",
        table_name="prediction_api_audits",
    )
    op.drop_table("prediction_api_audits")

