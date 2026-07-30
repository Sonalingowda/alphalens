"""Content-addressed paper cycle audit events."""

from datetime import datetime
from hashlib import sha256
import json

from app.paper_trading.models import PaperAuditEvent


class PaperAuditLogger:
    def append(
        self,
        events: tuple[PaperAuditEvent, ...],
        *,
        observation_timestamp: datetime,
        event_type: str,
        evidence: object,
    ) -> tuple[PaperAuditEvent, ...]:
        event = PaperAuditEvent(
            sequence=len(events) + 1,
            observation_timestamp=observation_timestamp,
            event_type=event_type,
            evidence_hash=hash_json(evidence),
        )
        return (*events, event)


def hash_json(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def hash_lines(values: tuple[str, ...]) -> str:
    digest = sha256()
    for value in values:
        digest.update((value + "\n").encode())
    return digest.hexdigest()

