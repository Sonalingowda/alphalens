"""Controlled human selection of an eligible paper opportunity."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from app.opportunity_intelligence.domain import (
    LifecycleState,
    MarketContext,
    MarketSnapshot,
    Opportunity,
    OpportunityLifecycle,
    RankingMembership,
    RankingSnapshot,
)
from app.opportunity_intelligence.domain.primitives import validate_utc
from app.opportunity_intelligence.repositories import (
    EntityAsOfQuery,
    EntityId,
    LifecycleRepository,
    MarketContextRepository,
    MarketSnapshotRepository,
    OpportunityRepository,
    RankingRepository,
    ScopedRepositoryQuery,
)
from app.paper_execution.domain import (
    PaperExecution,
    PaperPosition,
    PaperTrackingEvent,
    PaperTrackingEventType,
)
from app.paper_execution.service import PaperExecutionService


class PaperTrackingSelectionError(ValueError):
    """Raised when a human selection fails the existing eligibility contract."""


class _PaperSelectionWriter(Protocol):
    async def save_selection(
        self,
        execution: PaperExecution,
        position: PaperPosition,
        event: PaperTrackingEvent,
    ) -> tuple[PaperExecution, PaperPosition, PaperTrackingEvent] | None: ...


class PaperTrackingAuthoritativeLoader(Protocol):
    async def load(
        self,
        *,
        opportunity_id: str,
        opportunity_version_id: str,
        selected_at: datetime,
    ) -> tuple[Opportunity, RankingSnapshot, OpportunityLifecycle, MarketSnapshot, MarketContext]:
        """Reload the complete selection basis at the authoritative cutoff."""
        ...


class RepositoryBackedPaperTrackingAuthoritativeLoader:
    """Reload protected selection inputs through existing repository ports."""

    def __init__(
        self,
        *,
        opportunities: OpportunityRepository,
        rankings: RankingRepository,
        lifecycles: LifecycleRepository,
        market_snapshots: MarketSnapshotRepository,
        market_contexts: MarketContextRepository,
    ) -> None:
        self._opportunities = opportunities
        self._rankings = rankings
        self._lifecycles = lifecycles
        self._market_snapshots = market_snapshots
        self._market_contexts = market_contexts

    async def load(
        self,
        *,
        opportunity_id: str,
        opportunity_version_id: str,
        selected_at: datetime,
    ) -> tuple[Opportunity, RankingSnapshot, OpportunityLifecycle, MarketSnapshot, MarketContext]:
        validate_utc(selected_at, "Paper selection time")
        opportunity = await self._opportunities.get_current(
            EntityAsOfQuery(EntityId(opportunity_id), selected_at)
        )
        if opportunity.opportunity_version_id != opportunity_version_id:
            raise PaperTrackingSelectionError(
                "The requested opportunity version is not authoritative at selection time."
            )
        ranking = await self._rankings.get_latest(
            ScopedRepositoryQuery(scope=opportunity.scope, as_of=selected_at, limit=1)
        )
        lifecycle = await self._lifecycles.get_current(
            EntityAsOfQuery(EntityId(opportunity.opportunity_id), selected_at)
        )
        market_snapshot = await self._market_snapshots.get_latest(
            ScopedRepositoryQuery(scope=opportunity.scope, as_of=selected_at, limit=1)
        )
        market_context = await self._market_contexts.get_latest(
            ScopedRepositoryQuery(scope=opportunity.scope, as_of=selected_at, limit=1)
        )
        if market_snapshot.scope != opportunity.scope or market_context.scope != opportunity.scope:
            raise PaperTrackingSelectionError(
                "Authoritative market inputs do not match the opportunity scope."
            )
        for artifact, name in (
            (market_snapshot, "Market snapshot"),
            (market_context, "Market context"),
        ):
            if artifact.audit.available_at > selected_at:
                raise PaperTrackingSelectionError(
                    f"{name} is not available at the selection cutoff."
                )
        return opportunity, ranking, lifecycle, market_snapshot, market_context


@dataclass(frozen=True, slots=True)
class PaperTrackingSelection:
    opportunity_id: str
    opportunity_version_id: str
    selected_at: datetime
    opportunity_hash: str
    plan_hash: str
    execution: PaperExecution
    position: PaperPosition
    selection_event: PaperTrackingEvent
    active: bool = True


class PaperTrackingSelectionService:
    """Persist an explicitly confirmed selection without evaluating candles.

    The caller is a trusted backend boundary and must load current authoritative
    opportunity, ranking, lifecycle, and provenance records itself. No market
    candle is accepted by this method.
    """

    def __init__(
        self,
        *,
        persistence: _PaperSelectionWriter,
        execution: PaperExecutionService | None = None,
        clock: Callable[[], datetime] | None = None,
        authoritative_loader: PaperTrackingAuthoritativeLoader | None = None,
    ) -> None:
        self._execution = execution or PaperExecutionService()
        self._persistence = persistence
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._authoritative_loader = authoritative_loader

    async def select_by_reference(
        self,
        *,
        opportunity_id: str,
        opportunity_version_id: str,
        actor_id: str,
        confirmed_scenario_hash: str,
    ) -> PaperTrackingSelection:
        """Select using only an identifier; protected inputs come from persistence."""
        if self._authoritative_loader is None:
            raise PaperTrackingSelectionError(
                "Repository-backed authoritative loading is required for reference selection."
            )
        selected_at = self._clock()
        opportunity, ranking, lifecycle, _, _ = await self._authoritative_loader.load(
            opportunity_id=opportunity_id,
            opportunity_version_id=opportunity_version_id,
            selected_at=selected_at,
        )
        return await self._select_loaded(
            opportunity=opportunity,
            ranking=ranking,
            lifecycle=lifecycle,
            actor_id=actor_id,
            confirmed_scenario_hash=confirmed_scenario_hash,
            selected_at=selected_at,
        )

    async def confirmation_by_reference(
        self,
        *,
        opportunity_id: str,
        opportunity_version_id: str,
    ) -> dict[str, str]:
        """Return only the server-derived confirmation binding for the UI."""
        if self._authoritative_loader is None:
            raise PaperTrackingSelectionError(
                "Repository-backed authoritative loading is required for confirmation."
            )
        selected_at = self._clock()
        opportunity, ranking, lifecycle, _, _ = await self._authoritative_loader.load(
            opportunity_id=opportunity_id,
            opportunity_version_id=opportunity_version_id,
            selected_at=selected_at,
        )
        self._validate_selection(
            opportunity=opportunity,
            ranking=ranking,
            lifecycle=lifecycle,
            selected_at=selected_at,
        )
        membership = self._membership(opportunity, ranking)
        return {
            "opportunity_id": opportunity.opportunity_id,
            "opportunity_version_id": opportunity.opportunity_version_id,
            "confirmed_scenario_hash": _confirmed_scenario_hash(
                opportunity_hash=opportunity.canonical_sha256(),
                plan_hash=opportunity.plan.canonical_sha256(),
                ranking_hash=ranking.canonical_sha256(),
                membership_hash=membership.canonical_sha256(),
            ),
        }

    async def select(
        self,
        *,
        opportunity: Opportunity,
        ranking: RankingSnapshot,
        lifecycle: OpportunityLifecycle,
        actor_id: str,
        confirmed_scenario_hash: str,
    ) -> PaperTrackingSelection:
        """Revalidate and atomically persist one human-confirmed active track."""
        selected_at = self._clock()
        if self._authoritative_loader is not None:
            opportunity, ranking, lifecycle, _, _ = await self._authoritative_loader.load(
                opportunity_id=opportunity.opportunity_id,
                opportunity_version_id=opportunity.opportunity_version_id,
                selected_at=selected_at,
            )
        return await self._select_loaded(
            opportunity=opportunity,
            ranking=ranking,
            lifecycle=lifecycle,
            actor_id=actor_id,
            confirmed_scenario_hash=confirmed_scenario_hash,
            selected_at=selected_at,
        )

    async def _select_loaded(
        self,
        *,
        opportunity: Opportunity,
        ranking: RankingSnapshot,
        lifecycle: OpportunityLifecycle,
        actor_id: str,
        confirmed_scenario_hash: str,
        selected_at: datetime,
    ) -> PaperTrackingSelection:
        self._validate_selection(
            opportunity=opportunity,
            ranking=ranking,
            lifecycle=lifecycle,
            selected_at=selected_at,
        )
        membership = self._membership(opportunity, ranking)
        opportunity_hash = opportunity.canonical_sha256()
        plan_hash = opportunity.plan.canonical_sha256()
        scenario_hash = _confirmed_scenario_hash(
            opportunity_hash=opportunity_hash,
            plan_hash=plan_hash,
            ranking_hash=ranking.canonical_sha256(),
            membership_hash=membership.canonical_sha256(),
        )
        if confirmed_scenario_hash != scenario_hash:
            raise PaperTrackingSelectionError(
                "Confirmed scenario no longer matches the authoritative opportunity."
            )

        execution, position = self._execution.create_active_selection(
            opportunity=opportunity,
            ranking_membership=membership,
        )
        payload = {
            "opportunity": opportunity.to_dict(),
            "opportunity_hash": opportunity_hash,
            "plan": opportunity.plan.to_dict(),
            "plan_hash": plan_hash,
            "ranking": ranking.to_dict(),
            "ranking_hash": ranking.canonical_sha256(),
            "ranking_membership": membership.to_dict(),
            "ranking_membership_hash": membership.canonical_sha256(),
            "confirmed_scenario_hash": scenario_hash,
        }
        event = PaperTrackingEvent(
            event_id=f"paper_event:{opportunity.opportunity_version_id}:selection",
            execution_id=execution.execution_id,
            position_id=position.position_id,
            sequence=1,
            event_type=PaperTrackingEventType.PAPER_TRACKING_SELECTED,
            idempotency_key=f"paper_selection:{opportunity.opportunity_version_id}",
            occurred_at=selected_at,
            available_at=None,
            recorded_at=datetime.now(timezone.utc),
            actor_id=actor_id,
            opportunity_id=opportunity.opportunity_id,
            opportunity_version_id=opportunity.opportunity_version_id,
            source_execution_hash=execution.canonical_sha256(),
            source_position_hash=position.canonical_sha256(),
            source_artifact_id=None,
            source_artifact_hash=None,
            exit_id=None,
            outcome_id=None,
            payload=payload,
        )
        persisted = await self._persistence.save_selection(execution, position, event)
        if persisted is not None:
            execution, position, event = persisted
        return PaperTrackingSelection(
            opportunity_id=opportunity.opportunity_id,
            opportunity_version_id=opportunity.opportunity_version_id,
            selected_at=event.occurred_at,
            opportunity_hash=opportunity_hash,
            plan_hash=plan_hash,
            execution=execution,
            position=position,
            selection_event=event,
        )

    @staticmethod
    def _membership(opportunity: Opportunity, ranking: RankingSnapshot) -> RankingMembership:
        matches = tuple(
            item
            for item in ranking.memberships
            if item.opportunity_id == opportunity.opportunity_id
            and item.opportunity_version_id == opportunity.opportunity_version_id
        )
        if len(matches) != 1:
            raise PaperTrackingSelectionError(
                "Ranking does not contain exactly one matching opportunity version."
            )
        return matches[0]

    @classmethod
    def _validate_selection(
        cls,
        *,
        opportunity: Opportunity,
        ranking: RankingSnapshot,
        lifecycle: OpportunityLifecycle,
        selected_at: datetime,
    ) -> None:
        validate_utc(selected_at, "Paper selection time")
        if opportunity.plan is None:
            raise PaperTrackingSelectionError("Paper tracking requires an opportunity plan.")
        if opportunity.stance.value == "WAIT":
            raise PaperTrackingSelectionError("WAIT opportunities are not eligible.")
        if lifecycle.opportunity_id != opportunity.opportunity_id or lifecycle.scope != opportunity.scope:
            raise PaperTrackingSelectionError("Lifecycle identity or scope does not match.")
        if lifecycle.current_state is not LifecycleState.RANKED:
            raise PaperTrackingSelectionError(
                "Paper tracking requires the existing RANKED lifecycle state."
            )
        if LifecycleState.QUALIFIED not in tuple(
            event.resulting_state for event in lifecycle.events
        ):
            raise PaperTrackingSelectionError(
                "Paper tracking requires the existing QUALIFIED lifecycle state."
            )
        if ranking.scope is not None and ranking.scope != opportunity.scope:
            raise PaperTrackingSelectionError("Ranking scope does not match the opportunity.")
        if ranking.generated_at > selected_at or ranking.as_of > selected_at:
            raise PaperTrackingSelectionError(
                "Ranking snapshot is not available at the selection cutoff."
            )
        membership = cls._membership(opportunity, ranking)
        if membership.valid_until < selected_at:
            raise PaperTrackingSelectionError("Ranking membership is no longer active.")
        if opportunity.valid_until is None or opportunity.plan.valid_until is None:
            raise PaperTrackingSelectionError("Paper tracking requires the existing validity boundary.")
        if selected_at > opportunity.valid_until or selected_at > opportunity.plan.valid_until:
            raise PaperTrackingSelectionError("Opportunity is no longer active at selection time.")
        for artifact, name in (
            (opportunity, "Opportunity"),
            (opportunity.plan, "Opportunity plan"),
            (ranking, "Ranking snapshot"),
        ):
            if artifact.audit.evidence_cutoff > selected_at:
                raise PaperTrackingSelectionError(
                    f"{name} evidence cutoff is after the selection time."
                )
            if not artifact.audit.provenance.source_references:
                raise PaperTrackingSelectionError(
                    f"{name} is missing immutable provenance references."
                )
        if opportunity.plan.policy not in opportunity.plan.audit.provenance.policy_references:
            raise PaperTrackingSelectionError("Opportunity plan policy provenance is invalid.")
        if opportunity.decision_policy not in opportunity.audit.provenance.policy_references:
            raise PaperTrackingSelectionError("Opportunity policy provenance is invalid.")


def confirmed_scenario_hash(
    *, opportunity: Opportunity, ranking: RankingSnapshot
) -> str:
    """Return the confirmation digest displayed for one authoritative scenario."""
    membership = PaperTrackingSelectionService._membership(opportunity, ranking)
    return _confirmed_scenario_hash(
        opportunity_hash=opportunity.canonical_sha256(),
        plan_hash=opportunity.plan.canonical_sha256(),
        ranking_hash=ranking.canonical_sha256(),
        membership_hash=membership.canonical_sha256(),
    )


def _confirmed_scenario_hash(
    *, opportunity_hash: str, plan_hash: str, ranking_hash: str, membership_hash: str
) -> str:
    from app.opportunity_intelligence.domain.primitives import canonical_sha256

    return canonical_sha256(
        {
            "opportunity_hash": opportunity_hash,
            "plan_hash": plan_hash,
            "ranking_hash": ranking_hash,
            "membership_hash": membership_hash,
        }
    )
