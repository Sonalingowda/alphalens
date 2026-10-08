"""Focused contract tests for human-selected paper tracking."""

import unittest
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.opportunity_intelligence.domain import (
    IntegrityReference,
    LifecycleState,
    MarketCandleSnapshot,
    OpportunityOutcome,
)
from app.opportunity_intelligence.persistence import (
    OpportunityMemoryRepository,
    RankingMemoryRepository,
)
from app.paper_execution import (
    InMemoryPaperExecutionRepository,
    RepositoryBackedPaperTrackingAuthoritativeLoader,
    PaperTrackingEventType,
    PaperTrackingObservationService,
    PaperTrackingSelectionError,
    PaperTrackingSelectionService,
    confirmed_scenario_hash,
)
from tests.test_runtime_lifecycle import _lifecycle_fixture


ZERO = "0" * 64


class _AsyncWriter(InMemoryPaperExecutionRepository):
    async def save_selection(self, execution, position, event):
        return super().save_selection(execution, position, event)

    async def save_events(self, execution, position, events, *, exit_record=None, outcome=None):
        return super().save_events(
            execution,
            position,
            events,
            exit_record=exit_record,
            outcome=outcome,
        )


class _FailingWriter:
    async def save_selection(self, execution, position, event):
        raise RuntimeError("test transaction failure")


class PaperTrackingSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def _inputs(self, writer=None):
        fixture, opportunity, qualification, ranking, lifecycle_service, _ = (
            await _lifecycle_fixture()
        )
        lifecycle = await lifecycle_service.advance(opportunity, qualification, ranking, None)
        writer = writer or _AsyncWriter()
        selected_at = fixture.context.audit.available_at
        service = PaperTrackingSelectionService(
            persistence=writer, clock=lambda: selected_at
        )
        confirmation = confirmed_scenario_hash(opportunity=opportunity, ranking=ranking)
        selection = await service.select(
            opportunity=opportunity,
            ranking=ranking,
            lifecycle=lifecycle,
            actor_id="clerk.user_test_owner",
            confirmed_scenario_hash=confirmation,
        )
        return fixture, opportunity, ranking, lifecycle, writer, service, selection

    async def test_selection_is_active_and_persists_no_exit_or_outcome(self) -> None:
        fixture, _, _, _, writer, _, selection = await self._inputs()
        self.assertTrue(selection.active)
        self.assertEqual(selection.selected_at, fixture.context.audit.available_at)
        self.assertEqual(selection.execution.state.value, "ACTIVE")
        self.assertEqual(selection.position.state.value, "ACTIVE")
        self.assertEqual(selection.selection_event.event_type, PaperTrackingEventType.PAPER_TRACKING_SELECTED)
        self.assertEqual(selection.selection_event.actor_id, "clerk.user_test_owner")
        self.assertEqual(selection.selection_event.sequence, 1)
        self.assertEqual(writer._records, {})
        self.assertEqual(len(writer._active), 1)

    async def test_selection_does_not_evaluate_market_data(self) -> None:
        _, opportunity, ranking, lifecycle, writer, _, selection = await self._inputs()
        self.assertEqual(selection.execution.opportunity_hash, opportunity.canonical_sha256())
        self.assertEqual(selection.execution.plan_hash, opportunity.plan.canonical_sha256())
        self.assertEqual(writer._records, {})

    async def test_repeated_selection_is_idempotent_and_preserves_first_actor(self) -> None:
        _, opportunity, ranking, lifecycle, writer, service, first = await self._inputs()
        second = await service.select(
            opportunity=opportunity,
            ranking=ranking,
            lifecycle=lifecycle,
            actor_id="clerk.user_other",
            confirmed_scenario_hash=confirmed_scenario_hash(
                opportunity=opportunity, ranking=ranking
            ),
        )
        self.assertEqual(first.selection_event.event_id, second.selection_event.event_id)
        self.assertEqual(second.selection_event.actor_id, "clerk.user_test_owner")
        self.assertEqual(len(writer._active), 1)
        self.assertEqual(len(writer._events_by_key), 1)

    async def test_noneligible_lifecycle_and_stale_confirmation_are_rejected(self) -> None:
        fixture, opportunity, ranking, lifecycle, writer, service, _ = await self._inputs()
        non_ranked = replace(
            lifecycle,
            events=lifecycle.events[:-1],
            current_event_id=lifecycle.events[1].event_id,
            current_state=LifecycleState.QUALIFIED,
        )
        with self.assertRaises(PaperTrackingSelectionError):
            await service.select(
                opportunity=opportunity,
                ranking=ranking,
                lifecycle=non_ranked,
                actor_id="clerk.user_test_owner",
                confirmed_scenario_hash=confirmed_scenario_hash(
                    opportunity=opportunity, ranking=ranking
                ),
            )
        with self.assertRaises(PaperTrackingSelectionError):
            await service.select(
                opportunity=opportunity,
                ranking=ranking,
                lifecycle=lifecycle,
                actor_id="clerk.user_test_owner",
                confirmed_scenario_hash=ZERO,
            )
        self.assertEqual(len(writer._active), 1)  # only the setup selection


class AuthoritativeSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def _service(self):
        fixture, opportunity, qualification, ranking, lifecycle_service, lifecycles = (
            await _lifecycle_fixture()
        )
        lifecycle = await lifecycle_service.advance(opportunity, qualification, ranking, None)
        opportunities = OpportunityMemoryRepository()
        rankings = RankingMemoryRepository()
        await opportunities.save(opportunity)
        await rankings.save(ranking)
        loader = RepositoryBackedPaperTrackingAuthoritativeLoader(
            opportunities=opportunities,
            rankings=rankings,
            lifecycles=lifecycles,
            market_snapshots=fixture.markets,
            market_contexts=fixture.contexts,
        )
        writer = _AsyncWriter()
        service = PaperTrackingSelectionService(
            persistence=writer,
            clock=lambda: fixture.context.audit.available_at,
            authoritative_loader=loader,
        )
        return fixture, opportunity, ranking, lifecycle, service, writer

    async def test_reference_selection_reloads_authoritative_inputs(self) -> None:
        fixture, opportunity, ranking, _, service, writer = await self._service()
        selection = await service.select_by_reference(
            opportunity_id=opportunity.opportunity_id,
            opportunity_version_id=opportunity.opportunity_version_id,
            actor_id="clerk.authoritative",
            confirmed_scenario_hash=confirmed_scenario_hash(
                opportunity=opportunity, ranking=ranking
            ),
        )
        self.assertEqual(selection.execution.opportunity_hash, opportunity.canonical_sha256())
        self.assertEqual(selection.execution.plan_hash, opportunity.plan.canonical_sha256())
        self.assertEqual(selection.selected_at, fixture.context.audit.available_at)
        self.assertEqual(writer._active[selection.execution.execution_id][2].actor_id, "clerk.authoritative")

    async def test_conflicting_client_snapshots_cannot_override_repository_values(self) -> None:
        _, opportunity, ranking, lifecycle, service, writer = await self._service()
        client_opportunity = replace(
            opportunity,
            plan=replace(
                opportunity.plan,
                reference_price=opportunity.plan.reference_price + Decimal("10"),
            ),
        )
        client_ranking = replace(ranking, snapshot_id="ranking.client.conflict")
        client_lifecycle = lifecycle
        selection = await service.select(
            opportunity=client_opportunity,
            ranking=client_ranking,
            lifecycle=client_lifecycle,
            actor_id="clerk.authoritative",
            confirmed_scenario_hash=confirmed_scenario_hash(
                opportunity=opportunity, ranking=ranking
            ),
        )
        self.assertEqual(selection.execution.opportunity_hash, opportunity.canonical_sha256())
        self.assertEqual(selection.execution.plan_hash, opportunity.plan.canonical_sha256())
        self.assertEqual(selection.selection_event.payload["ranking_hash"], ranking.canonical_sha256())
        self.assertEqual(selection.selection_event.payload["opportunity"]["plan"], opportunity.plan.to_dict())
        self.assertEqual(len(writer._active), 1)

    async def test_authoritative_version_and_eligibility_are_revalidated(self) -> None:
        _, opportunity, ranking, lifecycle, service, _ = await self._service()
        with self.assertRaises(PaperTrackingSelectionError):
            await service.select_by_reference(
                opportunity_id=opportunity.opportunity_id,
                opportunity_version_id="opportunity-version:stale",
                actor_id="clerk.authoritative",
                confirmed_scenario_hash=confirmed_scenario_hash(
                    opportunity=opportunity, ranking=ranking
                ),
            )
        non_ranked = replace(
            lifecycle,
            events=lifecycle.events[:-1],
            current_event_id=lifecycle.events[1].event_id,
            current_state=LifecycleState.QUALIFIED,
        )
        service._authoritative_loader._lifecycles._records[lifecycle.current_event_id] = non_ranked
        with self.assertRaises(PaperTrackingSelectionError):
            await service.select_by_reference(
                opportunity_id=opportunity.opportunity_id,
                opportunity_version_id=opportunity.opportunity_version_id,
                actor_id="clerk.authoritative",
                confirmed_scenario_hash=confirmed_scenario_hash(
                    opportunity=opportunity, ranking=ranking
                ),
            )

    async def test_persistence_failure_reports_no_selection(self) -> None:
        fixture, opportunity, qualification, ranking, lifecycle_service, _ = (
            await _lifecycle_fixture()
        )
        lifecycle = await lifecycle_service.advance(opportunity, qualification, ranking, None)
        service = PaperTrackingSelectionService(
            persistence=_FailingWriter(),
            clock=lambda: fixture.context.audit.available_at,
        )
        with self.assertRaises(RuntimeError):
            await service.select(
                opportunity=opportunity,
                ranking=ranking,
                lifecycle=lifecycle,
                actor_id="clerk.user_test_owner",
                confirmed_scenario_hash=confirmed_scenario_hash(
                    opportunity=opportunity, ranking=ranking
                ),
            )


class PaperTrackingObservationTests(unittest.IsolatedAsyncioTestCase):
    async def _active(self):
        fixture, opportunity, ranking, lifecycle, writer, _, selection = (
            await PaperTrackingSelectionTests()._inputs()
        )
        observer = PaperTrackingObservationService(persistence=writer)
        return fixture, opportunity, writer, observer, selection

    def _candle(self, selection, offset_minutes: int, low: str, high: str):
        timestamp = selection.selected_at + timedelta(minutes=offset_minutes)
        available = timestamp + timedelta(minutes=5)
        prefix = f"binance.spot.{selection.execution.scope.instrument}.{selection.execution.scope.timeframe}"
        source = IntegrityReference(
            artifact_id=f"{prefix}.{offset_minutes}.source",
            artifact_type="binance_spot_completed_kline",
            artifact_version="1.0.0",
            integrity_digest=ZERO,
            available_at=available,
        )
        open_close = (Decimal(low) + Decimal(high)) / 2
        return MarketCandleSnapshot(
            candle_id=f"{prefix}.{offset_minutes}.candle",
            timestamp=timestamp,
            available_at=available,
            open=open_close,
            high=Decimal(high),
            low=Decimal(low),
            close=open_close,
            volume=Decimal("1"),
            source_reference=source,
        )

    async def test_preselection_candle_is_ignored_and_empty_data_stays_active(self):
        _, opportunity, writer, observer, selection = await self._active()
        pre = self._candle(selection, -5, "104", "107")
        pre = replace(pre, available_at=selection.selected_at + timedelta(minutes=1))
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(pre,),
            existing_events=(selection.selection_event,),
            observed_at=selection.selected_at + timedelta(minutes=1),
        )
        self.assertEqual(result.status, "DATA_INSUFFICIENT")
        self.assertTrue(result.active)
        self.assertIsNone(result.outcome)
        self.assertEqual(writer._records, {})

    async def test_market_data_after_observation_cutoff_is_ignored(self):
        _, opportunity, writer, observer, selection = await self._active()
        future = self._candle(selection, 5, "104.5", "107")
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(future,),
            existing_events=(selection.selection_event,),
            observed_at=selection.selected_at + timedelta(minutes=1),
        )
        self.assertEqual(result.status, "DATA_INSUFFICIENT")
        self.assertTrue(result.active)
        self.assertEqual(writer._records, {})

    async def test_target_hit_closes_official_outcome_and_preserves_snapshot(self):
        _, opportunity, writer, observer, selection = await self._active()
        candle = self._candle(selection, 5, "104.5", "107")
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(candle,),
            existing_events=(selection.selection_event,),
            observed_at=candle.available_at,
        )
        self.assertEqual(result.status, "TARGET_HIT")
        self.assertFalse(result.active)
        self.assertEqual(result.outcome.source_execution_hash, selection.execution.canonical_sha256())
        self.assertEqual(result.outcome.source_position_hash, selection.position.canonical_sha256())
        self.assertEqual(result.outcome.source_selection_event_hash, selection.selection_event.canonical_sha256())
        self.assertEqual(writer._records[selection.execution.execution_id][0], selection.execution)
        self.assertEqual(writer._records[selection.execution.execution_id][1], selection.position)

    async def test_stop_loss_hit_closes_official_outcome(self):
        _, opportunity, _, observer, selection = await self._active()
        candle = self._candle(selection, 5, "103", "105.5")
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(candle,),
            existing_events=(selection.selection_event,),
            observed_at=candle.available_at,
        )
        self.assertEqual(result.status, "STOP_HIT")
        self.assertFalse(result.active)

    async def test_ambiguous_candle_is_nonterminal(self):
        _, opportunity, writer, observer, selection = await self._active()
        candle = self._candle(selection, 5, "103", "107")
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(candle,),
            existing_events=(selection.selection_event,),
            observed_at=candle.available_at,
        )
        self.assertEqual(result.status, OpportunityOutcome.AMBIGUOUS_INTRABAR.value)
        self.assertTrue(result.active)
        self.assertIsNone(result.outcome)
        self.assertEqual(result.events[-1].event_type, PaperTrackingEventType.AMBIGUOUS_INTRABAR)
        self.assertEqual(writer._records, {})

    async def test_expiry_does_not_close_active_track(self):
        _, opportunity, writer, observer, selection = await self._active()
        candle = self._candle(selection, 60, "101", "102")
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(candle,),
            existing_events=(selection.selection_event,),
            observed_at=candle.available_at,
        )
        self.assertEqual(result.status, OpportunityOutcome.EXPIRED_BEFORE_ENTRY.value)
        self.assertTrue(result.active)
        self.assertEqual(writer._records, {})

    async def test_post_outcome_observation_is_append_only_and_idempotent(self):
        _, opportunity, writer, observer, selection = await self._active()
        target = self._candle(selection, 5, "104.5", "107")
        result = await observer.observe(
            selection=selection,
            opportunity=opportunity,
            candles=(target,),
            existing_events=(selection.selection_event,),
            observed_at=target.available_at,
        )
        next_candle = self._candle(selection, 10, "106.7", "108")
        post = await observer.post_outcome_observations(
            selection=selection,
            terminal_event=result.events[-1],
            candles=(target, next_candle),
            existing_events=(selection.selection_event, *result.events),
        )
        self.assertEqual(len(post), 1)
        self.assertEqual(post[0].event_type, PaperTrackingEventType.POST_OUTCOME_OBSERVATION)
        self.assertEqual(post[0].outcome_id, result.outcome.outcome_id)
        self.assertEqual(
            await observer.post_outcome_observations(
                selection=selection,
                terminal_event=result.events[-1],
                candles=(target, next_candle),
                existing_events=(selection.selection_event, *result.events, *post),
            ),
            (),
        )
        self.assertEqual(writer._records[selection.execution.execution_id][3], result.outcome)


if __name__ == "__main__":
    unittest.main()
