"""Append-only policy metadata registry and immutable artifact store."""

import asyncio
from hashlib import sha256

from app.opportunity_intelligence.domain.primitives import validate_identifier
from app.policy_runtime.errors import (
    InvalidPolicyError,
    PolicyArtifactNotFoundError,
    PolicyAuditConflictError,
    PolicyMissingError,
    UnsupportedPolicyVersionError,
)
from app.policy_runtime.models import PolicyRegistration, PolicySelector


class PolicyRegistry:
    """In-process immutable registry with deterministic semantic ordering."""

    def __init__(self) -> None:
        self._records: dict[str, PolicyRegistration] = {}
        self._lock = asyncio.Lock()

    async def register(self, policy: PolicyRegistration) -> PolicyRegistration:
        if not isinstance(policy, PolicyRegistration):
            raise InvalidPolicyError("Registry requires PolicyRegistration.")
        async with self._lock:
            existing = self._records.get(policy.registration_id)
            if existing is not None:
                if existing.canonical_sha256() != policy.canonical_sha256():
                    raise PolicyAuditConflictError(
                        "Immutable policy registration already has different content."
                    )
                return existing
            self._records[policy.registration_id] = policy
        return policy

    async def get(self, selector: PolicySelector) -> PolicyRegistration:
        if not isinstance(selector, PolicySelector):
            raise InvalidPolicyError("Registry lookup requires PolicySelector.")
        try:
            return self._records[
                f"{selector.policy_id}:{selector.policy_version}"
            ]
        except KeyError as error:
            if any(
                item.policy_id == selector.policy_id
                for item in self._records.values()
            ):
                raise UnsupportedPolicyVersionError(
                    f"Policy version {selector.policy_version!r} is not registered."
                ) from error
            raise PolicyMissingError(
                f"Policy {selector.policy_id!r} is not registered."
            ) from error

    async def versions(self, policy_id: str) -> tuple[PolicyRegistration, ...]:
        try:
            validate_identifier(policy_id, "Policy identifier")
        except ValueError as error:
            raise InvalidPolicyError(str(error)) from error
        records = tuple(
            item for item in self._records.values() if item.policy_id == policy_id
        )
        if not records:
            raise PolicyMissingError(f"Policy {policy_id!r} is not registered.")
        return tuple(
            sorted(
                records,
                key=lambda item: _semantic_version(item.policy_version),
                reverse=True,
            )
        )


class ImmutablePolicyArtifactStore:
    """Append-only byte store; policy interpretation remains adapter-owned."""

    def __init__(self) -> None:
        self._artifacts: dict[str, bytes] = {}
        self._lock = asyncio.Lock()

    async def add(self, selector: PolicySelector, artifact: bytes) -> str:
        if not isinstance(selector, PolicySelector):
            raise InvalidPolicyError("Artifact identity requires PolicySelector.")
        if not isinstance(artifact, bytes) or not artifact:
            raise InvalidPolicyError("Policy artifact must be non-empty bytes.")
        identity = f"{selector.policy_id}:{selector.policy_version}"
        async with self._lock:
            existing = self._artifacts.get(identity)
            if existing is not None and existing != artifact:
                raise PolicyAuditConflictError(
                    "Immutable policy artifact already has different bytes."
                )
            self._artifacts[identity] = bytes(artifact)
        return sha256(artifact).hexdigest()

    async def load(self, selector: PolicySelector) -> bytes:
        if not isinstance(selector, PolicySelector):
            raise InvalidPolicyError("Artifact lookup requires PolicySelector.")
        identity = f"{selector.policy_id}:{selector.policy_version}"
        try:
            return bytes(self._artifacts[identity])
        except KeyError as error:
            raise PolicyArtifactNotFoundError(identity) from error


def _semantic_version(value: str) -> tuple[int, int, int]:
    try:
        return tuple(int(item) for item in value.split("."))  # type: ignore[return-value]
    except (TypeError, ValueError) as error:
        raise InvalidPolicyError("Registered policy has invalid semantic version.") from error
