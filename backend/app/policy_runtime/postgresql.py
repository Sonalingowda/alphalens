"""PostgreSQL policy registry, artifact, and execution-audit adapters."""

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.opportunity_intelligence.persistence.postgresql import (
    PostgreSQLImmutableRepository,
)
from app.opportunity_intelligence.repositories import (
    ContractViolationError,
    DuplicateEntityError,
    EntityId,
    EntityNotFoundError,
    HistoryQuery,
    RepositoryListQuery,
    StorageUnavailableError,
    VersionConflictError,
)
from app.persistence.models import PolicyArtifactRecord
from app.policy_runtime.audit import (
    DecisionLedgerEntry,
    EvidenceLedgerEntry,
    PolicyAuditSnapshot,
    PolicyExecutionLedgerEntry,
    ResearchLedgerEntry,
)
from app.policy_runtime.errors import (
    InvalidPolicyError,
    PolicyArtifactNotFoundError,
    PolicyAuditConflictError,
)
from app.policy_runtime.models import (
    ExecutionMode,
    PolicyExecutionRequest,
    PolicyExecutionResult,
    PolicyRegistration,
    PolicySelector,
)


_MAX_AS_OF = datetime.max.replace(tzinfo=timezone.utc)


class PostgreSQLPolicyRegistry:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._repository = PostgreSQLImmutableRepository(
            sessions,
            PolicyRegistration,
            lambda item: item.registration_id,
            lambda item: item.policy_id,
            availability=lambda item: item.activation_date,
        )

    async def register(self, policy: PolicyRegistration) -> PolicyRegistration:
        if not isinstance(policy, PolicyRegistration):
            raise InvalidPolicyError("Registry requires PolicyRegistration.")
        try:
            return await self._repository.save(policy)
        except (ContractViolationError, DuplicateEntityError) as error:
            raise PolicyAuditConflictError(str(error)) from error

    async def get(self, selector: PolicySelector) -> PolicyRegistration:
        if not isinstance(selector, PolicySelector):
            raise InvalidPolicyError("Registry lookup requires PolicySelector.")
        identity = EntityId(f"{selector.policy_id}:{selector.policy_version}")
        try:
            return await self._repository.get_by_id(identity)
        except EntityNotFoundError as error:
            versions = await self._versions_or_empty(selector.policy_id)
            if versions:
                from app.policy_runtime.errors import UnsupportedPolicyVersionError

                raise UnsupportedPolicyVersionError(identity.value) from error
            from app.policy_runtime.errors import PolicyMissingError

            raise PolicyMissingError(selector.policy_id) from error

    async def versions(self, policy_id: str) -> tuple[PolicyRegistration, ...]:
        versions = await self._versions_or_empty(policy_id)
        if not versions:
            from app.policy_runtime.errors import PolicyMissingError

            raise PolicyMissingError(policy_id)
        return tuple(
            sorted(
                versions,
                key=lambda item: tuple(int(part) for part in item.policy_version.split(".")),
                reverse=True,
            )
        )

    async def _versions_or_empty(self, policy_id: str) -> tuple[PolicyRegistration, ...]:
        try:
            page = await self._repository.history(
                HistoryQuery(EntityId(policy_id), _MAX_AS_OF, 10_000)
            )
        except EntityNotFoundError:
            return ()
        return page.items


class PostgreSQLPolicyArtifactStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, selector: PolicySelector, artifact: bytes) -> str:
        if not isinstance(artifact, bytes) or not artifact:
            raise InvalidPolicyError("Policy artifact must be non-empty bytes.")
        digest = sha256(artifact).hexdigest()
        key = f"policy-artifact:{selector.policy_id}:{selector.policy_version}"
        try:
            async with self._sessions.begin() as session:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                    {"key": key},
                )
                existing = await session.scalar(
                    select(PolicyArtifactRecord).where(
                        PolicyArtifactRecord.policy_id == selector.policy_id,
                        PolicyArtifactRecord.policy_version == selector.policy_version,
                    )
                )
                if existing is not None:
                    if existing.artifact_hash != digest or existing.artifact_bytes != artifact:
                        raise PolicyAuditConflictError(
                            "Immutable policy artifact has conflicting bytes."
                        )
                    return digest
                session.add(
                    PolicyArtifactRecord(
                        policy_id=selector.policy_id,
                        policy_version=selector.policy_version,
                        artifact_bytes=artifact,
                        artifact_hash=digest,
                    )
                )
        except PolicyAuditConflictError:
            raise
        except SQLAlchemyError as error:
            raise StorageUnavailableError("Policy artifact write failed.") from error
        return digest

    async def load(self, selector: PolicySelector) -> bytes:
        try:
            async with self._sessions() as session:
                record = await session.scalar(
                    select(PolicyArtifactRecord).where(
                        PolicyArtifactRecord.policy_id == selector.policy_id,
                        PolicyArtifactRecord.policy_version == selector.policy_version,
                    )
                )
        except SQLAlchemyError as error:
            raise StorageUnavailableError("Policy artifact read failed.") from error
        if record is None:
            raise PolicyArtifactNotFoundError(
                f"{selector.policy_id}:{selector.policy_version}"
            )
        artifact = bytes(record.artifact_bytes)
        if sha256(artifact).hexdigest() != record.artifact_hash:
            raise PolicyAuditConflictError("Stored policy artifact hash mismatch.")
        return artifact


class PostgreSQLPolicyAuditTrail:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._repository = PostgreSQLImmutableRepository(
            sessions,
            PolicyExecutionResult,
            lambda item: item.record.execution_id,
            lambda item: item.record.selector.policy_id,
            availability=lambda item: item.record.executed_at,
        )

    async def record(
        self,
        request: PolicyExecutionRequest,
        result: PolicyExecutionResult,
    ) -> PolicyExecutionResult:
        if request.execution_id != result.record.execution_id:
            raise PolicyAuditConflictError("Audit request/result identity mismatch.")
        try:
            return await self._repository.save(result)
        except (
            ContractViolationError,
            DuplicateEntityError,
            VersionConflictError,
        ) as error:
            raise PolicyAuditConflictError(str(error)) from error

    async def get_result(self, execution_id: str) -> PolicyExecutionResult:
        return await self._repository.get_by_id(EntityId(execution_id))

    async def snapshot(self, *, limit: int = 10_000) -> PolicyAuditSnapshot:
        page = await self._repository.list(
            RepositoryListQuery(as_of=_MAX_AS_OF, limit=limit)
        )
        results = tuple(
            sorted(page.items, key=lambda item: item.record.execution_id)
        )
        return PolicyAuditSnapshot(
            research=tuple(
                ResearchLedgerEntry(
                    execution_id=item.record.execution_id,
                    policy_reference=item.record.policy_reference,
                    intermediate_states=item.evaluation.intermediate_states,
                )
                for item in results
                if item.record.mode is ExecutionMode.RESEARCH
                and item.record.policy_reference is not None
            ),
            decisions=tuple(
                DecisionLedgerEntry(
                    item.record.execution_id,
                    item.record.state,
                    item.record.decision_code,
                    item.record.output_hash,
                )
                for item in results
            ),
            evidence=tuple(
                EvidenceLedgerEntry(
                    item.record.execution_id,
                    item.record.evidence_references,
                )
                for item in results
            ),
            executions=tuple(
                PolicyExecutionLedgerEntry(item.record) for item in results
            ),
        )
