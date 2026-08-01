"""Policy-runtime ports isolating policy contents and storage mechanics."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.policy_runtime.models import (
    PolicyEvaluation,
    PolicyExecutionRequest,
    PolicyExecutionResult,
    PolicyInput,
    PolicyRegistration,
    PolicySelector,
    PolicyStatus,
)


@runtime_checkable
class PolicyExecutable(Protocol):
    async def evaluate(self, inputs: PolicyInput) -> PolicyEvaluation:
        """Evaluate policy-owned behavior and return a canonical result."""
        ...


@runtime_checkable
class PolicyAdapterFactory(Protocol):
    def build(
        self,
        registration: PolicyRegistration,
        artifact: bytes,
    ) -> PolicyExecutable:
        """Build an isolated executable adapter from verified artifact bytes."""
        ...


@runtime_checkable
class PolicyArtifactStore(Protocol):
    async def load(self, selector: PolicySelector) -> bytes:
        """Load immutable policy bytes or raise PolicyArtifactNotFoundError."""
        ...


@runtime_checkable
class PolicyRegistryPort(Protocol):
    async def register(self, policy: PolicyRegistration) -> PolicyRegistration: ...

    async def get(self, selector: PolicySelector) -> PolicyRegistration: ...

    async def versions(self, policy_id: str) -> tuple[PolicyRegistration, ...]: ...


@runtime_checkable
class PolicyAuditTrailPort(Protocol):
    async def record(
        self,
        request: PolicyExecutionRequest,
        result: PolicyExecutionResult,
    ) -> PolicyExecutionResult:
        """Atomically append execution, decision, evidence, and research ledgers."""
        ...


@runtime_checkable
class PolicyVersionResolver(Protocol):
    async def resolve(
        self,
        selector: PolicySelector,
        *,
        as_of: datetime,
        allowed_statuses: frozenset[PolicyStatus],
    ) -> PolicyRegistration: ...
