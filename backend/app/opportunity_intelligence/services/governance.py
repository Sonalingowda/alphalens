"""Service port for runtime health, suspension, and recovery evaluation."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    IntegrityReference,
    MarketScope,
    RuntimeHealthRecord,
)


@runtime_checkable
class RuntimeGovernanceService(Protocol):
    """Evaluate runtime health without producing market intelligence."""

    async def evaluate(
        self,
        cycle_id: str,
        scope: MarketScope,
        expected_boundary: datetime,
        evidence_references: tuple[IntegrityReference, ...],
    ) -> RuntimeHealthRecord:
        """Return immutable health evidence and fail closed on invalid inputs."""
        ...
