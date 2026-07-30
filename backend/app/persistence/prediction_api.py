"""Immutable observability audit persistence for the prediction API."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.artifact import hash_json
from app.persistence.models import PredictionAPIAuditRecord


@dataclass(frozen=True, slots=True)
class PredictionAPIAudit:
    api_version: str
    http_method: str
    request_path: str
    request_size_bytes: int
    request_hash: str
    response_status: int
    response_hash: str
    outcome: str
    error_code: str | None
    artifact_id: UUID | None
    artifact_sha256: str | None
    configuration_hash: str | None
    schema_hash: str | None
    prediction_hash: str | None
    latency_microseconds: int
    received_at: datetime
    completed_at: datetime


async def persist_prediction_api_audit(
    session: AsyncSession,
    audit: PredictionAPIAudit,
) -> UUID:
    payload = {
        "api_version": audit.api_version,
        "http_method": audit.http_method,
        "request_path": audit.request_path,
        "request_size_bytes": audit.request_size_bytes,
        "request_hash": audit.request_hash,
        "response_status": audit.response_status,
        "response_hash": audit.response_hash,
        "outcome": audit.outcome,
        "error_code": audit.error_code,
        "artifact_id": (
            str(audit.artifact_id)
            if audit.artifact_id is not None
            else None
        ),
        "artifact_sha256": audit.artifact_sha256,
        "configuration_hash": audit.configuration_hash,
        "schema_hash": audit.schema_hash,
        "prediction_hash": audit.prediction_hash,
        "latency_microseconds": audit.latency_microseconds,
        "received_at": audit.received_at.isoformat(),
        "completed_at": audit.completed_at.isoformat(),
        "artifact_verified": True,
        "fit_invoked": False,
        "read_only_inference": True,
        "immutable": True,
    }
    audit_hash = hash_json(payload)
    audit_id = uuid4()
    async with session.begin():
        session.add(
            PredictionAPIAuditRecord(
                id=audit_id,
                api_version=audit.api_version,
                http_method=audit.http_method,
                request_path=audit.request_path,
                request_size_bytes=audit.request_size_bytes,
                request_hash=audit.request_hash,
                response_status=audit.response_status,
                response_hash=audit.response_hash,
                outcome=audit.outcome,
                error_code=audit.error_code,
                artifact_id=audit.artifact_id,
                artifact_sha256=audit.artifact_sha256,
                configuration_hash=audit.configuration_hash,
                schema_hash=audit.schema_hash,
                prediction_hash=audit.prediction_hash,
                latency_microseconds=audit.latency_microseconds,
                received_at=audit.received_at,
                completed_at=audit.completed_at,
                audit_payload=payload,
                audit_hash=audit_hash,
                artifact_verified=True,
                fit_invoked=False,
                read_only_inference=True,
                immutable=True,
            )
        )
        await session.flush()
    return audit_id

