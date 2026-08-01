"""Research, shadow, and deterministic historical replay coordinators."""

import asyncio
from dataclasses import replace

from app.opportunity_intelligence.domain import canonical_sha256
from app.policy_runtime.models import (
    ExecutionMode,
    PolicyExecutionRequest,
    PolicyExecutionResult,
    PolicySelector,
    ReplayVerification,
    ShadowComparison,
    ShadowExecutionResult,
)
from app.policy_runtime.runtime import DecisionSandbox, PolicyExecutionRuntime


class ResearchMode:
    def __init__(self, sandbox: DecisionSandbox) -> None:
        self._sandbox = sandbox

    async def execute(
        self,
        request: PolicyExecutionRequest,
    ) -> PolicyExecutionResult:
        research_request = replace(request, mode=ExecutionMode.RESEARCH)
        return await self._sandbox.execute(research_request)


class ShadowMode:
    """Compare a hidden candidate with production without returning its decision."""

    def __init__(
        self,
        *,
        runtime: PolicyExecutionRuntime,
        sandbox: DecisionSandbox,
    ) -> None:
        self._runtime = runtime
        self._sandbox = sandbox

    async def execute(
        self,
        *,
        production_request: PolicyExecutionRequest,
        candidate_selector: PolicySelector,
        candidate_execution_id: str,
    ) -> ShadowExecutionResult:
        production = replace(
            production_request,
            mode=ExecutionMode.SHADOW_PRODUCTION,
        )
        candidate = PolicyExecutionRequest(
            execution_id=candidate_execution_id,
            selector=candidate_selector,
            mode=ExecutionMode.SHADOW_CANDIDATE,
            inputs=production_request.inputs,
        )
        production_result, candidate_result = await asyncio.gather(
            self._runtime.execute(production),
            self._sandbox.execute(candidate),
        )
        comparison_payload = {
            "production_execution_id": production_result.record.execution_id,
            "candidate_execution_id": candidate_result.record.execution_id,
            "decision_differs": (
                production_result.evaluation.decision_code
                != candidate_result.evaluation.decision_code
            ),
            "output_differs": (
                production_result.record.output_hash
                != candidate_result.record.output_hash
            ),
            "evidence_differs": (
                tuple(
                    item.artifact_id
                    for item in production_result.record.evidence_references
                )
                != tuple(
                    item.artifact_id
                    for item in candidate_result.record.evidence_references
                )
            ),
            "timing_delta_microseconds": (
                candidate_result.record.duration_microseconds
                - production_result.record.duration_microseconds
            ),
        }
        comparison = ShadowComparison(
            **comparison_payload,
            comparison_hash=canonical_sha256(comparison_payload),
        )
        return ShadowExecutionResult(
            production_result=production_result,
            comparison=comparison,
        )


class PolicyReplayEngine:
    def __init__(self, sandbox: DecisionSandbox) -> None:
        self._sandbox = sandbox

    async def replay(
        self,
        *,
        original: PolicyExecutionResult,
        request: PolicyExecutionRequest,
    ) -> ReplayVerification:
        replay_request = replace(request, mode=ExecutionMode.REPLAY)
        replayed = await self._sandbox.execute(replay_request)
        reasons: list[str] = []
        if replayed.record.input_hash != original.record.input_hash:
            reasons.append("replay.input_mismatch")
        if replayed.record.output_hash != original.record.output_hash:
            reasons.append("replay.output_mismatch")
        if replayed.record.replay_hash != original.record.replay_hash:
            reasons.append("replay.hash_mismatch")
        return ReplayVerification(
            original_execution_id=original.record.execution_id,
            replay_result=replayed,
            identical=not reasons,
            reason_codes=tuple(reasons),
        )
