"""Deterministic isolated paper execution over immutable source artifacts."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.opportunity_intelligence.domain import IntegrityReference, Opportunity, OpportunityPlan, OpportunityStance, RankingMembership
from app.outcome_resolution.service import _determine_entry, _determine_outcome
from app.paper_execution.domain import PaperExecution, PaperExecutionState, PaperExit, PaperExitReason, PaperOutcome, PaperPosition
from app.paper_execution.successor import PaperSuccessorPlan


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    execution: PaperExecution
    position: PaperPosition
    exit: PaperExit
    outcome: PaperOutcome


class PaperExecutionService:
    """Resolve one ranked opportunity without economic accounting."""

    def create_active_selection(
        self,
        *,
        opportunity: Opportunity,
        ranking_membership: RankingMembership,
    ) -> tuple[PaperExecution, PaperPosition]:
        """Capture immutable scenario snapshots without evaluating market candles."""
        if opportunity.plan is None or opportunity.valid_until is None:
            raise ValueError("A persisted, valid source plan is required.")
        if ranking_membership.opportunity_version_id != opportunity.opportunity_version_id:
            raise ValueError("Ranking membership does not admit this opportunity version.")
        execution = self._build_execution(
            opportunity,
            opportunity.plan,
            ranking_membership,
            state=PaperExecutionState.ACTIVE,
        )
        position = PaperPosition(
            contract_version="1.0.0",
            position_id=f"paper_position:{opportunity.opportunity_version_id}",
            execution_id=execution.execution_id,
            opportunity_version_id=opportunity.opportunity_version_id,
            state=PaperExecutionState.ACTIVE,
            entry_price=None,
            entry_timestamp=None,
            entry_candle_index=None,
        )
        return execution, position

    def evaluate(self, *, opportunity: Opportunity, ranking_membership: RankingMembership, candles: Sequence[dict]) -> PaperExecutionResult:
        if opportunity.plan is None:
            raise ValueError("A persisted source plan is required.")
        if opportunity.valid_until is None or opportunity.plan.valid_until is None:
            raise ValueError("Paper execution requires the existing valid_until boundary.")
        if opportunity.valid_until != opportunity.plan.valid_until:
            raise ValueError("Opportunity and plan validity boundaries must match.")
        return self._evaluate_with_plan(opportunity=opportunity, ranking_membership=ranking_membership, plan=opportunity.plan, candles=candles)

    def evaluate_successor(self, *, opportunity: Opportunity, ranking_membership: RankingMembership, successor: PaperSuccessorPlan, candles: Sequence[dict]) -> PaperExecutionResult:
        """Evaluate an isolated successor while retaining original source identity."""
        if successor.source_opportunity_version_id != opportunity.opportunity_version_id:
            raise ValueError("Successor source version does not match the opportunity.")
        if successor.source_opportunity_id != opportunity.opportunity_id:
            raise ValueError("Successor source opportunity does not match the opportunity.")
        if opportunity.plan is None:
            raise ValueError("A persisted source plan is required.")
        if opportunity.plan.canonical_sha256() != successor.source_plan_canonical_hash:
            raise ValueError("Successor source plan hash does not match the immutable source.")
        return self._evaluate_with_plan(opportunity=opportunity, ranking_membership=ranking_membership, plan=successor.plan, successor=successor, candles=candles)

    def _evaluate_with_plan(self, *, opportunity: Opportunity, ranking_membership: RankingMembership, plan: OpportunityPlan, candles: Sequence[dict], successor: PaperSuccessorPlan | None = None) -> PaperExecutionResult:
        if ranking_membership.opportunity_version_id != opportunity.opportunity_version_id:
            raise ValueError("Ranking membership does not admit this opportunity version.")
        if opportunity.stance is OpportunityStance.WAIT:
            raise ValueError("Only ranked actionable OpportunityVersions are eligible.")
        execution = self._build_execution(opportunity, plan, ranking_membership, successor)
        signal_timestamp = plan.audit.available_at
        candle_tuple = tuple(candle for candle in candles if signal_timestamp < candle["timestamp"] <= plan.valid_until)
        entry_reached, entry_timestamp, entry_index = _determine_entry(opportunity.stance.value, plan.entry_zone.lower, plan.entry_zone.upper, signal_timestamp, candle_tuple)
        outcome, evaluated, touch_price, touch_timestamp, touch_index, _ = _determine_outcome(
            direction=opportunity.stance.value,
            reference_price=plan.reference_price,
            entry_zone_lower=plan.entry_zone.lower,
            entry_zone_upper=plan.entry_zone.upper,
            invalidation_price=plan.invalidation_price,
            target_price=plan.targets[0].price,
            signal_timestamp=signal_timestamp,
            valid_until=plan.valid_until,
            candles=candle_tuple,
        )
        position = PaperPosition("1.0.0", f"paper_position:{opportunity.opportunity_version_id}", execution.execution_id, opportunity.opportunity_version_id, PaperExecutionState.OPEN if entry_reached else PaperExecutionState.ELIGIBLE, plan.reference_price if entry_reached else None, entry_timestamp, entry_index)
        exit_record = PaperExit("1.0.0", f"paper_exit:{opportunity.opportunity_version_id}", position.position_id, opportunity.opportunity_version_id, PaperExitReason(outcome.value), touch_price, touch_timestamp, touch_index, evaluated)
        closed_position = PaperPosition("1.0.0", position.position_id, position.execution_id, position.opportunity_version_id, PaperExecutionState.CLOSED, position.entry_price, position.entry_timestamp, position.entry_candle_index)
        closed_execution = PaperExecution("1.0.0", execution.execution_id, execution.opportunity_id, execution.opportunity_version_id, execution.opportunity_hash, execution.plan_hash, execution.source_references, execution.scope, execution.direction, execution.signal_timestamp, execution.valid_until, PaperExecutionState.CLOSED, source_plan_id=execution.source_plan_id, source_plan_hash=execution.source_plan_hash, successor_plan_id=execution.successor_plan_id, successor_plan_hash=execution.successor_plan_hash)
        outcome_record = PaperOutcome("1.0.0", f"paper_outcome:{opportunity.opportunity_version_id}", execution.execution_id, closed_position.position_id, exit_record.exit_id, opportunity.opportunity_version_id, exit_record.reason, closed_execution.canonical_sha256(), closed_position.canonical_sha256(), exit_record.canonical_sha256())
        return PaperExecutionResult(closed_execution, closed_position, exit_record, outcome_record)

    @staticmethod
    def _build_execution(
        opportunity: Opportunity,
        plan: OpportunityPlan,
        ranking_membership: RankingMembership,
        successor: PaperSuccessorPlan | None = None,
        state: PaperExecutionState = PaperExecutionState.ELIGIBLE,
    ) -> PaperExecution:
        opportunity_hash = opportunity.canonical_sha256()
        plan_hash = plan.canonical_sha256()
        source_references_by_id = {
            reference.artifact_id: reference
            for reference in (
                IntegrityReference(
                    opportunity.opportunity_version_id,
                    "opportunity_version",
                    opportunity.contract_version,
                    opportunity_hash,
                    plan.audit.available_at,
                ),
                IntegrityReference(
                    plan.plan_id,
                    "opportunity_plan",
                    plan.contract_version,
                    plan_hash,
                    plan.audit.available_at,
                ),
                *opportunity.audit.provenance.source_references,
                *plan.audit.provenance.source_references,
            )
        }
        source_references_by_id[ranking_membership.score_reference.artifact_id] = (
            ranking_membership.score_reference
        )
        source_references_by_id[ranking_membership.qualification_reference.artifact_id] = (
            ranking_membership.qualification_reference
        )
        if successor is not None:
            source_references_by_id[successor.source_plan_id] = IntegrityReference(
                successor.source_plan_id,
                "opportunity_plan_source",
                opportunity.plan.contract_version,
                successor.source_plan_canonical_hash,
                opportunity.plan.audit.available_at,
            )
        return PaperExecution(
            contract_version="1.0.0",
            execution_id=f"paper_execution:{opportunity.opportunity_version_id}",
            opportunity_id=opportunity.opportunity_id,
            opportunity_version_id=opportunity.opportunity_version_id,
            opportunity_hash=opportunity_hash,
            plan_hash=plan_hash,
            source_references=tuple(
                source_references_by_id[key] for key in sorted(source_references_by_id)
            ),
            scope=plan.scope,
            direction=opportunity.stance,
            signal_timestamp=plan.audit.available_at,
            valid_until=plan.valid_until,
            state=state,
            source_plan_id=successor.source_plan_id if successor else None,
            source_plan_hash=successor.source_plan_canonical_hash if successor else None,
            successor_plan_id=successor.successor_plan_id if successor else None,
            successor_plan_hash=successor.successor_plan_canonical_hash if successor else None,
        )
