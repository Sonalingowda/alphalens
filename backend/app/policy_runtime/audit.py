"""Immutable in-process ledgers for policy execution and research audit."""

import asyncio
from dataclasses import dataclass

from app.opportunity_intelligence.domain import (
    CanonicalModel,
    IntegrityReference,
    PolicyReference,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.primitives import (
    DomainValidationError,
    validate_identifier,
    validate_sha256,
    validate_unique_identifiers,
)
from app.policy_runtime.errors import PolicyAuditConflictError
from app.policy_runtime.models import (
    DecisionState,
    ExecutionMode,
    PolicyExecutionRecord,
    PolicyExecutionRequest,
    PolicyExecutionResult,
    PolicyIntermediateState,
)


@dataclass(frozen=True, slots=True)
class ResearchLedgerEntry(CanonicalModel):
    execution_id: str
    policy_reference: PolicyReference
    intermediate_states: tuple[PolicyIntermediateState, ...]
    publication_allowed: bool = False
    notification_allowed: bool = False

    def __post_init__(self) -> None:
        validate_identifier(self.execution_id, "Research ledger execution")
        if self.publication_allowed or self.notification_allowed:
            raise DomainValidationError(
                "Research executions cannot publish or notify."
            )


@dataclass(frozen=True, slots=True)
class DecisionLedgerEntry(CanonicalModel):
    execution_id: str
    state: DecisionState
    decision_code: str
    output_hash: str

    def __post_init__(self) -> None:
        validate_identifier(self.execution_id, "Decision ledger execution")
        validate_identifier(self.decision_code, "Decision ledger code")
        validate_sha256(self.output_hash, "Decision ledger output hash")


@dataclass(frozen=True, slots=True)
class EvidenceLedgerEntry(CanonicalModel):
    execution_id: str
    evidence_references: tuple[IntegrityReference, ...]

    def __post_init__(self) -> None:
        validate_identifier(self.execution_id, "Evidence ledger execution")
        validate_unique_identifiers(
            self.evidence_references,
            "artifact_id",
            "Evidence ledger references",
        )


@dataclass(frozen=True, slots=True)
class PolicyExecutionLedgerEntry(CanonicalModel):
    record: PolicyExecutionRecord


@dataclass(frozen=True, slots=True)
class PolicyAuditSnapshot(CanonicalModel):
    research: tuple[ResearchLedgerEntry, ...]
    decisions: tuple[DecisionLedgerEntry, ...]
    evidence: tuple[EvidenceLedgerEntry, ...]
    executions: tuple[PolicyExecutionLedgerEntry, ...]


@dataclass(frozen=True, slots=True)
class PolicyAuditVerification(CanonicalModel):
    valid: bool
    execution_count: int
    ledger_hash: str

    def __post_init__(self) -> None:
        if not self.valid:
            raise DomainValidationError(
                "Successful audit verification must be valid."
            )
        if self.execution_count < 0:
            raise DomainValidationError("Audit execution count cannot be negative.")
        validate_sha256(self.ledger_hash, "Policy audit ledger hash")


class InMemoryPolicyAuditTrail:
    """Atomic append-only ledgers suitable for tests and process-local research."""

    def __init__(self) -> None:
        self._results: dict[str, PolicyExecutionResult] = {}
        self._research: dict[str, ResearchLedgerEntry] = {}
        self._decisions: dict[str, DecisionLedgerEntry] = {}
        self._evidence: dict[str, EvidenceLedgerEntry] = {}
        self._executions: dict[str, PolicyExecutionLedgerEntry] = {}
        self._lock = asyncio.Lock()

    async def record(
        self,
        request: PolicyExecutionRequest,
        result: PolicyExecutionResult,
    ) -> PolicyExecutionResult:
        if request.execution_id != result.record.execution_id:
            raise PolicyAuditConflictError("Audit request/result identity mismatch.")
        decision = DecisionLedgerEntry(
            execution_id=request.execution_id,
            state=result.record.state,
            decision_code=result.record.decision_code,
            output_hash=result.record.output_hash,
        )
        evidence = EvidenceLedgerEntry(
            execution_id=request.execution_id,
            evidence_references=result.record.evidence_references,
        )
        execution = PolicyExecutionLedgerEntry(result.record)
        research = None
        if request.mode is ExecutionMode.RESEARCH:
            if result.record.policy_reference is None:
                research = None
            else:
                research = ResearchLedgerEntry(
                    execution_id=request.execution_id,
                    policy_reference=result.record.policy_reference,
                    intermediate_states=result.evaluation.intermediate_states,
                )
        async with self._lock:
            existing = self._results.get(request.execution_id)
            if existing is not None:
                if existing.canonical_sha256() != result.canonical_sha256():
                    raise PolicyAuditConflictError(
                        "Immutable execution identity has conflicting audit content."
                    )
                return existing
            self._results[request.execution_id] = result
            self._decisions[request.execution_id] = decision
            self._evidence[request.execution_id] = evidence
            self._executions[request.execution_id] = execution
            if research is not None:
                self._research[request.execution_id] = research
        return result

    async def get_result(self, execution_id: str) -> PolicyExecutionResult:
        validate_identifier(execution_id, "Audit execution identifier")
        try:
            return self._results[execution_id]
        except KeyError as error:
            raise PolicyAuditConflictError("Execution audit does not exist.") from error

    async def snapshot(self) -> PolicyAuditSnapshot:
        order = tuple(sorted(self._executions))
        return PolicyAuditSnapshot(
            research=tuple(
                self._research[item]
                for item in order
                if item in self._research
            ),
            decisions=tuple(self._decisions[item] for item in order),
            evidence=tuple(self._evidence[item] for item in order),
            executions=tuple(self._executions[item] for item in order),
        )

    async def verify(self) -> PolicyAuditVerification:
        snapshot = await self.snapshot()
        execution_ids = tuple(
            item.record.execution_id for item in snapshot.executions
        )
        if execution_ids != tuple(item.execution_id for item in snapshot.decisions):
            raise PolicyAuditConflictError("Decision ledger identity mismatch.")
        if execution_ids != tuple(item.execution_id for item in snapshot.evidence):
            raise PolicyAuditConflictError("Evidence ledger identity mismatch.")
        for execution, decision, evidence in zip(
            snapshot.executions,
            snapshot.decisions,
            snapshot.evidence,
            strict=True,
        ):
            record = execution.record
            if (
                decision.state is not record.state
                or decision.decision_code != record.decision_code
                or decision.output_hash != record.output_hash
                or evidence.evidence_references != record.evidence_references
            ):
                raise PolicyAuditConflictError("Cross-ledger content mismatch.")
        return PolicyAuditVerification(
            valid=True,
            execution_count=len(execution_ids),
            ledger_hash=canonical_sha256(snapshot),
        )
