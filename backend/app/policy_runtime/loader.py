"""Hash-verifying policy resolution and executable loading."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from app.opportunity_intelligence.domain.primitives import validate_utc
from app.policy_runtime.errors import (
    DeprecatedPolicyError,
    InvalidPolicyError,
    PolicyDependencyError,
    PolicyHashMismatchError,
)
from app.policy_runtime.interfaces import (
    PolicyAdapterFactory,
    PolicyArtifactStore,
    PolicyExecutable,
    PolicyRegistryPort,
)
from app.policy_runtime.models import (
    PolicyRegistration,
    PolicySelector,
    PolicyStatus,
)


@dataclass(frozen=True, slots=True)
class LoadedPolicy:
    registration: PolicyRegistration
    executable: PolicyExecutable


class PolicyVersionManager:
    def __init__(self, registry: PolicyRegistryPort) -> None:
        self._registry = registry

    async def resolve(
        self,
        selector: PolicySelector,
        *,
        as_of: datetime,
        allowed_statuses: frozenset[PolicyStatus],
    ) -> PolicyRegistration:
        try:
            validate_utc(as_of, "Policy resolution as-of")
        except ValueError as error:
            raise InvalidPolicyError(str(error)) from error
        policy = await self._registry.get(selector)
        if policy.status is PolicyStatus.DEPRECATED:
            raise DeprecatedPolicyError(policy.registration_id)
        if policy.status not in allowed_statuses:
            raise InvalidPolicyError(
                f"Policy status {policy.status.value} is not executable in this mode."
            )
        if policy.activation_date > as_of:
            raise InvalidPolicyError("Policy is not active at the requested as-of.")
        await self._validate_dependencies(policy, as_of)
        return policy

    async def latest_approved(
        self,
        policy_id: str,
        *,
        as_of: datetime,
    ) -> PolicyRegistration:
        versions = await self._registry.versions(policy_id)
        for policy in versions:
            if (
                policy.status is PolicyStatus.APPROVED
                and policy.activation_date <= as_of
            ):
                await self._validate_dependencies(policy, as_of)
                return policy
        raise InvalidPolicyError("No active approved policy version exists.")

    async def _validate_dependencies(
        self,
        policy: PolicyRegistration,
        as_of: datetime,
    ) -> None:
        for dependency in policy.dependencies:
            try:
                registered = await self._registry.get(
                    PolicySelector(
                        dependency.policy_id,
                        dependency.policy_version,
                    )
                )
            except Exception as error:
                raise PolicyDependencyError(dependency.dependency_id) from error
            if (
                registered.artifact_hash != dependency.integrity_digest
                or registered.status
                not in {PolicyStatus.RESEARCH, PolicyStatus.APPROVED}
                or registered.activation_date > as_of
            ):
                raise PolicyDependencyError(dependency.dependency_id)


class PolicyLoader:
    def __init__(
        self,
        *,
        version_manager: PolicyVersionManager,
        artifact_store: PolicyArtifactStore,
        adapter_factory: PolicyAdapterFactory,
    ) -> None:
        self._versions = version_manager
        self._artifacts = artifact_store
        self._adapters = adapter_factory

    async def load(
        self,
        selector: PolicySelector,
        *,
        as_of: datetime,
        allowed_statuses: frozenset[PolicyStatus],
    ) -> LoadedPolicy:
        registration = await self._versions.resolve(
            selector,
            as_of=as_of,
            allowed_statuses=allowed_statuses,
        )
        artifact = await self._artifacts.load(selector)
        if sha256(artifact).hexdigest() != registration.artifact_hash:
            raise PolicyHashMismatchError(registration.registration_id)
        try:
            executable = self._adapters.build(registration, artifact)
        except Exception as error:
            raise InvalidPolicyError("Policy adapter construction failed.") from error
        if not isinstance(executable, PolicyExecutable):
            raise InvalidPolicyError("Policy adapter does not satisfy executable port.")
        return LoadedPolicy(registration, executable)
