"""Stable, policy-neutral runtime failure taxonomy."""


class PolicyRuntimeError(Exception):
    reason_code = "policy.invalid"


class PolicyMissingError(PolicyRuntimeError):
    reason_code = "policy.missing"


class UnsupportedPolicyVersionError(PolicyRuntimeError):
    reason_code = "policy.version_unsupported"


class InvalidPolicyError(PolicyRuntimeError):
    reason_code = "policy.invalid"


class DeprecatedPolicyError(PolicyRuntimeError):
    reason_code = "policy.deprecated"


class PolicyHashMismatchError(PolicyRuntimeError):
    reason_code = "policy.hash_mismatch"


class PolicyArtifactNotFoundError(PolicyRuntimeError):
    reason_code = "policy.artifact_missing"


class PolicyDependencyError(PolicyRuntimeError):
    reason_code = "policy.dependency_invalid"


class PolicyExecutionError(PolicyRuntimeError):
    reason_code = "policy.execution_failed"


class PolicyAuditConflictError(PolicyRuntimeError):
    reason_code = "policy.audit_conflict"
