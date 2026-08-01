"""Deterministic, policy-agnostic execution and fail-closed sandbox."""

from collections.abc import Callable
from datetime import datetime, timezone
from time import perf_counter_ns

from app.opportunity_intelligence.domain import PolicyReference, canonical_sha256
from app.opportunity_intelligence.domain.primitives import validate_utc
from app.policy_runtime.errors import PolicyExecutionError, PolicyRuntimeError
from app.policy_runtime.interfaces import PolicyAuditTrailPort
from app.policy_runtime.loader import LoadedPolicy, PolicyLoader
from app.policy_runtime.models import (
    DecisionState,
    ExecutionMode,
    PolicyEvaluation,
    PolicyExecutionRecord,
    PolicyExecutionRequest,
    PolicyExecutionResult,
    PolicyStatus,
)


Clock = Callable[[], datetime]
Timer = Callable[[], int]


class PolicyExecutionRuntime:
    """Execute a verified adapter without interpreting its decision semantics."""

    def __init__(
        self,
        *,
        loader: PolicyLoader,
        audit_trail: PolicyAuditTrailPort,
        clock: Clock | None = None,
        timer: Timer | None = None,
    ) -> None:
        self._loader = loader
        self._audit = audit_trail
        self._clock = clock or _utc_now
        self._timer = timer or perf_counter_ns

    async def execute(
        self,
        request: PolicyExecutionRequest,
    ) -> PolicyExecutionResult:
        if not isinstance(request, PolicyExecutionRequest):
            raise TypeError("Policy runtime requires PolicyExecutionRequest.")
        started = self._timer()
        loaded: LoadedPolicy | None = None
        try:
            loaded = await self._loader.load(
                request.selector,
                as_of=request.inputs.as_of,
                allowed_statuses=_allowed_statuses(request.mode),
            )
            evaluation = await loaded.executable.evaluate(request.inputs)
            if not isinstance(evaluation, PolicyEvaluation):
                raise PolicyExecutionError(
                    "Policy executable returned a non-canonical evaluation."
                )
            if any(
                reference.available_at > request.inputs.as_of
                for reference in evaluation.evidence_references
            ):
                raise PolicyExecutionError(
                    "Policy returned future-unavailable evidence."
                )
        except PolicyRuntimeError as error:
            evaluation = _no_decision(error.reason_code)
        except Exception:
            evaluation = _no_decision(PolicyExecutionError.reason_code)
        completed = self._timer()
        executed_at = self._clock()
        validate_utc(executed_at, "Policy execution clock")
        result = _build_result(
            request,
            evaluation,
            loaded.registration.reference if loaded is not None else None,
            executed_at,
            max((completed - started) // 1_000, 0),
        )
        return await self._audit.record(request, result)


class DecisionSandbox:
    """Execute only non-publishing research, shadow-candidate, or replay modes."""

    _ALLOWED = {
        ExecutionMode.RESEARCH,
        ExecutionMode.SHADOW_CANDIDATE,
        ExecutionMode.REPLAY,
    }

    def __init__(self, runtime: PolicyExecutionRuntime) -> None:
        self._runtime = runtime

    async def execute(
        self,
        request: PolicyExecutionRequest,
    ) -> PolicyExecutionResult:
        if request.mode not in self._ALLOWED:
            raise PolicyExecutionError(
                "Decision sandbox cannot execute a publishing runtime mode."
            )
        return await self._runtime.execute(request)


def _allowed_statuses(mode: ExecutionMode) -> frozenset[PolicyStatus]:
    if mode in {ExecutionMode.PRODUCTION, ExecutionMode.SHADOW_PRODUCTION}:
        return frozenset({PolicyStatus.APPROVED})
    if mode in {
        ExecutionMode.RESEARCH,
        ExecutionMode.SHADOW_CANDIDATE,
        ExecutionMode.REPLAY,
    }:
        return frozenset({PolicyStatus.RESEARCH, PolicyStatus.APPROVED})
    return frozenset()


def _no_decision(reason_code: str) -> PolicyEvaluation:
    return PolicyEvaluation(
        state=DecisionState.NO_DECISION,
        decision_code="NO_DECISION",
        output_fields=(),
        evidence_references=(),
        reason_codes=(reason_code,),
    )


def _build_result(
    request: PolicyExecutionRequest,
    evaluation: PolicyEvaluation,
    policy_reference: PolicyReference | None,
    executed_at: datetime,
    duration_microseconds: int,
) -> PolicyExecutionResult:
    output_hash = evaluation.canonical_sha256()
    replay_hash = canonical_sha256(
        {
            "selector": request.selector,
            "input_hash": request.inputs.input_hash,
            "output_hash": output_hash,
        }
    )
    record = PolicyExecutionRecord(
        execution_id=request.execution_id,
        selector=request.selector,
        policy_reference=policy_reference,
        mode=request.mode,
        executed_at=executed_at,
        input_hash=request.inputs.input_hash,
        output_hash=output_hash,
        replay_hash=replay_hash,
        evidence_references=evaluation.evidence_references,
        duration_microseconds=duration_microseconds,
        state=evaluation.state,
        decision_code=evaluation.decision_code,
        reason_codes=evaluation.reason_codes,
    )
    return PolicyExecutionResult(evaluation=evaluation, record=record)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
