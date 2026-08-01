"""Immutable policy-runtime contracts with no embedded business semantics."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    FeatureSnapshot,
    IntegrityReference,
    MarketContext,
    MarketSnapshot,
    PolicyReference,
    Provenance,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.primitives import (
    DomainValidationError,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_semver,
    validate_sha256,
    validate_unique_identifiers,
    validate_utc,
)


class PolicyCategory(StrEnum):
    DETECTION = "DETECTION"
    ASSESSMENT = "ASSESSMENT"
    QUALIFICATION = "QUALIFICATION"
    RANKING = "RANKING"
    NOTIFICATION = "NOTIFICATION"


class PolicyStatus(StrEnum):
    DRAFT = "DRAFT"
    RESEARCH = "RESEARCH"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"


class ExecutionMode(StrEnum):
    PRODUCTION = "PRODUCTION"
    RESEARCH = "RESEARCH"
    SHADOW_PRODUCTION = "SHADOW_PRODUCTION"
    SHADOW_CANDIDATE = "SHADOW_CANDIDATE"
    REPLAY = "REPLAY"


class DecisionState(StrEnum):
    DECISION = "DECISION"
    NO_DECISION = "NO_DECISION"


PolicyScalar = Decimal | str | int | bool


@dataclass(frozen=True, slots=True)
class PolicyAuthorMetadata(CanonicalModel):
    author_id: str
    author_name: str
    creation_source: str

    def __post_init__(self) -> None:
        validate_identifier(self.author_id, "Policy author identifier")
        if not self.author_name.strip():
            raise DomainValidationError("Policy author name must not be empty.")
        validate_identifier(self.creation_source, "Policy creation source")


@dataclass(frozen=True, slots=True)
class PolicyDependency(CanonicalModel):
    policy_id: str
    policy_version: str
    integrity_digest: str

    def __post_init__(self) -> None:
        validate_identifier(self.policy_id, "Policy dependency identifier")
        validate_semver(self.policy_version, "Policy dependency version")
        validate_sha256(self.integrity_digest, "Policy dependency hash")

    @property
    def dependency_id(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"


@dataclass(frozen=True, slots=True)
class PolicyRegistration(CanonicalModel):
    contract_version: str
    policy_id: str
    policy_version: str
    category: PolicyCategory
    status: PolicyStatus
    artifact_hash: str
    provenance: Provenance
    dependencies: tuple[PolicyDependency, ...]
    activation_date: datetime
    author: PolicyAuthorMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.policy_id, "Policy identifier")
        validate_semver(self.policy_version, "Policy version")
        validate_sha256(self.artifact_hash, "Policy artifact hash")
        validate_utc(self.activation_date, "Policy activation date")
        identifiers = tuple(item.dependency_id for item in self.dependencies)
        if len(identifiers) != len(set(identifiers)):
            raise DomainValidationError("Policy dependencies must be unique.")
        if identifiers != tuple(sorted(identifiers)):
            raise DomainValidationError(
                "Policy dependencies must use canonical identifier order."
            )
        if any(item.policy_id == self.policy_id for item in self.dependencies):
            raise DomainValidationError("Policy cannot depend on itself.")

    @property
    def registration_id(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    @property
    def reference(self) -> PolicyReference:
        return PolicyReference(
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            integrity_digest=self.artifact_hash,
        )


@dataclass(frozen=True, slots=True)
class PolicySelector(CanonicalModel):
    policy_id: str
    policy_version: str

    def __post_init__(self) -> None:
        validate_identifier(self.policy_id, "Selected policy identifier")
        validate_semver(self.policy_version, "Selected policy version")


@dataclass(frozen=True, slots=True)
class PolicyInput(CanonicalModel):
    market_snapshot: MarketSnapshot
    feature_snapshot: FeatureSnapshot
    market_context: MarketContext
    as_of: datetime

    def __post_init__(self) -> None:
        validate_utc(self.as_of, "Policy input as-of")
        scopes = (
            self.market_snapshot.scope,
            self.feature_snapshot.scope,
            self.market_context.scope,
        )
        if any(scope != scopes[0] for scope in scopes[1:]):
            raise DomainValidationError("Policy inputs must share one market scope.")
        if self.feature_snapshot.market_snapshot.artifact_id != (
            self.market_snapshot.snapshot_id
        ):
            raise DomainValidationError(
                "Feature snapshot must reference the supplied market snapshot."
            )
        if any(
            item.audit.available_at > self.as_of
            for item in (
                self.market_snapshot,
                self.feature_snapshot,
                self.market_context,
            )
        ):
            raise DomainValidationError(
                "Policy input contains information unavailable at its as-of."
            )

    @property
    def input_hash(self) -> str:
        return canonical_sha256(
            {
                "market_snapshot": self.market_snapshot.canonical_sha256(),
                "feature_snapshot": self.feature_snapshot.canonical_sha256(),
                "market_context": self.market_context.canonical_sha256(),
                "as_of": self.as_of,
            }
        )


@dataclass(frozen=True, slots=True)
class PolicyOutputField(CanonicalModel):
    name: str
    value: PolicyScalar

    def __post_init__(self) -> None:
        validate_identifier(self.name, "Policy output field")
        if isinstance(self.value, Decimal):
            validate_decimal(self.value, "Policy output Decimal")
        elif isinstance(self.value, str):
            if not self.value.strip():
                raise DomainValidationError("Policy output string must not be empty.")
        elif not isinstance(self.value, (int, bool)):
            raise DomainValidationError("Policy output has unsupported scalar type.")


@dataclass(frozen=True, slots=True)
class PolicyIntermediateState(CanonicalModel):
    state_id: str
    sequence: int
    fields: tuple[PolicyOutputField, ...]
    state_hash: str

    def __post_init__(self) -> None:
        validate_identifier(self.state_id, "Policy intermediate-state identifier")
        if self.sequence <= 0:
            raise DomainValidationError("Intermediate-state sequence must be positive.")
        _validate_unique_fields(self.fields, "Intermediate-state fields")
        validate_sha256(self.state_hash, "Intermediate-state hash")
        if self.state_hash != canonical_sha256(self.fields):
            raise DomainValidationError("Intermediate-state hash does not match fields.")


@dataclass(frozen=True, slots=True)
class PolicyEvaluation(CanonicalModel):
    state: DecisionState
    decision_code: str
    output_fields: tuple[PolicyOutputField, ...]
    evidence_references: tuple[IntegrityReference, ...]
    intermediate_states: tuple[PolicyIntermediateState, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_identifier(self.decision_code, "Policy decision code")
        _validate_unique_fields(self.output_fields, "Policy output fields")
        validate_unique_identifiers(
            self.evidence_references,
            "artifact_id",
            "Policy evidence references",
        )
        evidence_ids = tuple(
            item.artifact_id for item in self.evidence_references
        )
        if evidence_ids != tuple(sorted(evidence_ids)):
            raise DomainValidationError(
                "Policy evidence must use canonical identifier order."
            )
        sequences = tuple(item.sequence for item in self.intermediate_states)
        if sequences and sequences != tuple(range(1, len(sequences) + 1)):
            raise DomainValidationError(
                "Policy intermediate states must be contiguously ordered."
            )
        for reason in self.reason_codes:
            validate_identifier(reason, "Policy reason code")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise DomainValidationError("Policy reason codes must be unique.")
        if self.reason_codes != tuple(sorted(self.reason_codes)):
            raise DomainValidationError("Policy reason codes must be ordered.")
        if self.state is DecisionState.NO_DECISION:
            if self.output_fields or not self.reason_codes:
                raise DomainValidationError(
                    "NO_DECISION requires reasons and cannot contain output fields."
                )


@dataclass(frozen=True, slots=True)
class PolicyExecutionRequest(CanonicalModel):
    execution_id: str
    selector: PolicySelector
    mode: ExecutionMode
    inputs: PolicyInput

    def __post_init__(self) -> None:
        validate_identifier(self.execution_id, "Policy execution identifier")


@dataclass(frozen=True, slots=True)
class PolicyExecutionRecord(CanonicalModel):
    execution_id: str
    selector: PolicySelector
    policy_reference: PolicyReference | None
    mode: ExecutionMode
    executed_at: datetime
    input_hash: str
    output_hash: str
    replay_hash: str
    evidence_references: tuple[IntegrityReference, ...]
    duration_microseconds: int
    state: DecisionState
    decision_code: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.execution_id, "Execution record identifier")
        validate_utc(self.executed_at, "Policy execution time")
        validate_sha256(self.input_hash, "Policy execution input hash")
        validate_sha256(self.output_hash, "Policy execution output hash")
        validate_sha256(self.replay_hash, "Policy replay hash")
        if self.duration_microseconds < 0:
            raise DomainValidationError("Policy execution duration must not be negative.")
        validate_identifier(self.decision_code, "Execution decision code")
        validate_unique_identifiers(
            self.evidence_references,
            "artifact_id",
            "Execution evidence references",
        )
        for reason in self.reason_codes:
            validate_identifier(reason, "Execution reason code")


@dataclass(frozen=True, slots=True)
class PolicyExecutionResult(CanonicalModel):
    evaluation: PolicyEvaluation
    record: PolicyExecutionRecord

    def __post_init__(self) -> None:
        if self.evaluation.state is not self.record.state:
            raise DomainValidationError("Evaluation and execution state differ.")
        if self.evaluation.decision_code != self.record.decision_code:
            raise DomainValidationError("Evaluation and execution decision differ.")
        if self.evaluation.evidence_references != self.record.evidence_references:
            raise DomainValidationError("Evaluation and audit evidence differ.")
        if self.evaluation.canonical_sha256() != self.record.output_hash:
            raise DomainValidationError("Execution output hash does not match evaluation.")


@dataclass(frozen=True, slots=True)
class ShadowComparison(CanonicalModel):
    production_execution_id: str
    candidate_execution_id: str
    decision_differs: bool
    output_differs: bool
    evidence_differs: bool
    timing_delta_microseconds: int
    comparison_hash: str

    def __post_init__(self) -> None:
        validate_identifier(self.production_execution_id, "Production execution")
        validate_identifier(self.candidate_execution_id, "Candidate execution")
        validate_sha256(self.comparison_hash, "Shadow comparison hash")


@dataclass(frozen=True, slots=True)
class ShadowExecutionResult(CanonicalModel):
    production_result: PolicyExecutionResult
    comparison: ShadowComparison


@dataclass(frozen=True, slots=True)
class ReplayVerification(CanonicalModel):
    original_execution_id: str
    replay_result: PolicyExecutionResult
    identical: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.original_execution_id, "Original execution")
        for reason in self.reason_codes:
            validate_identifier(reason, "Replay reason code")
        if self.identical and self.reason_codes:
            raise DomainValidationError("Identical replay cannot contain mismatch reasons.")
        if not self.identical and not self.reason_codes:
            raise DomainValidationError("Replay mismatch requires reason codes.")


def _validate_unique_fields(
    fields: tuple[PolicyOutputField, ...],
    name: str,
) -> None:
    identifiers = tuple(field.name for field in fields)
    if len(identifiers) != len(set(identifiers)):
        raise DomainValidationError(f"{name} must be unique.")
    if identifiers != tuple(sorted(identifiers)):
        raise DomainValidationError(f"{name} must use canonical name order.")
