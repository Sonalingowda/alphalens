"""Repository ports for detection, evidence, opportunity, and evaluation."""

from typing import Protocol, runtime_checkable

from app.opportunity_intelligence.domain import (
    DetectionAttempt,
    EvidencePackage,
    Opportunity,
    OpportunityCandidate,
    QualificationRecord,
    ScoreResult,
)
from app.opportunity_intelligence.repositories.base import ImmutableRepository
from app.opportunity_intelligence.repositories.queries import (
    EntityAsOfQuery,
    EntityId,
    HistoryQuery,
    RepositoryListQuery,
    RepositoryPage,
    ScopedRepositoryQuery,
)


@runtime_checkable
class DetectionRepository(Protocol):
    """Append-only access to detection attempts and detected candidates."""

    async def save_attempt(self, attempt: DetectionAttempt) -> DetectionAttempt:
        """Persist one immutable attempt; conflicting identity MUST fail."""
        ...

    async def save_attempt_batch(
        self,
        attempts: tuple[DetectionAttempt, ...],
    ) -> tuple[DetectionAttempt, ...]:
        """Persist an ordered non-empty attempt batch without partial success."""
        ...

    async def save_candidate(
        self,
        candidate: OpportunityCandidate,
    ) -> OpportunityCandidate:
        """Persist one candidate; its matching detected attempt MUST exist."""
        ...

    async def save_candidate_batch(
        self,
        candidates: tuple[OpportunityCandidate, ...],
    ) -> tuple[OpportunityCandidate, ...]:
        """Persist an ordered non-empty candidate batch without partial success."""
        ...

    async def get_attempt_by_id(self, entity_id: EntityId) -> DetectionAttempt:
        """Return one attempt or raise EntityNotFoundError."""
        ...

    async def get_candidate_by_id(
        self,
        entity_id: EntityId,
    ) -> OpportunityCandidate:
        """Return one candidate or raise EntityNotFoundError."""
        ...

    async def get_latest_candidate(
        self,
        query: ScopedRepositoryQuery,
    ) -> OpportunityCandidate:
        """Return latest candidate at as-of or raise EntityNotFoundError."""
        ...

    async def list_attempts(
        self,
        query: RepositoryListQuery,
    ) -> RepositoryPage[DetectionAttempt]:
        """Return attempts in stable contract order."""
        ...

    async def list_candidates(
        self,
        query: RepositoryListQuery,
    ) -> RepositoryPage[OpportunityCandidate]:
        """Return candidates in stable contract order."""
        ...

    async def attempt_exists(self, query: EntityAsOfQuery) -> bool:
        """Return whether the exact attempt exists at the explicit as-of."""
        ...

    async def candidate_exists(self, query: EntityAsOfQuery) -> bool:
        """Return whether the exact candidate exists at the explicit as-of."""
        ...


@runtime_checkable
class EvidenceRepository(ImmutableRepository[EvidencePackage], Protocol):
    """Append-only access to canonical evidence packages."""

    async def get_by_candidate_id(self, candidate_id: EntityId) -> EvidencePackage:
        """Return candidate evidence or raise EntityNotFoundError."""
        ...

    async def get_by_assessment_id(
        self,
        assessment_id: EntityId,
    ) -> EvidencePackage:
        """Return assessment evidence or raise EntityNotFoundError."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[EvidencePackage]:
        """Return immutable package versions in stable order."""
        ...


@runtime_checkable
class OpportunityRepository(ImmutableRepository[Opportunity], Protocol):
    """Append-only access to canonical opportunity assessments and versions."""

    async def get_latest(self, query: ScopedRepositoryQuery) -> Opportunity:
        """Return latest opportunity at as-of or raise EntityNotFoundError."""
        ...

    async def get_current(self, query: EntityAsOfQuery) -> Opportunity:
        """Return unique current version or raise not-found/version conflict."""
        ...

    async def get_by_scope(
        self,
        query: ScopedRepositoryQuery,
    ) -> RepositoryPage[Opportunity]:
        """Return opportunities in stable contract order."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[Opportunity]:
        """Return complete immutable version history in stable order."""
        ...


@runtime_checkable
class QualificationRepository(
    ImmutableRepository[QualificationRecord],
    Protocol,
):
    """Append-only access to qualification gate results."""

    async def get_latest_for_assessment(
        self,
        query: EntityAsOfQuery,
    ) -> QualificationRecord:
        """Return latest record or raise EntityNotFoundError."""
        ...

    async def history(
        self,
        query: HistoryQuery,
    ) -> RepositoryPage[QualificationRecord]:
        """Return immutable qualification history in stable order."""
        ...


@runtime_checkable
class ScoringRepository(ImmutableRepository[ScoreResult], Protocol):
    """Append-only access to policy-produced score results."""

    async def get_latest_for_opportunity(
        self,
        query: EntityAsOfQuery,
    ) -> ScoreResult:
        """Return latest score or raise EntityNotFoundError."""
        ...

    async def history(self, query: HistoryQuery) -> RepositoryPage[ScoreResult]:
        """Return immutable score history in stable order."""
        ...
