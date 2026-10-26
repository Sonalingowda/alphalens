"""Persistent, diagnostic thesis identity and candle-observation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.opportunity_intelligence.domain import Opportunity


MATCH_POLICY_VERSION = "diagnostic.exact_geometry.v1"
MATCH_WINDOW = timedelta(minutes=30)
TERMINAL_STATES = frozenset({"INITIAL_TARGET_REACHED", "INVALIDATED", "EXPIRED", "RESOLVED", "OUTCOME_AMBIGUOUS"})


@dataclass(frozen=True, slots=True)
class ThesisMatch:
    thesis_id: str
    status: str
    reason: str


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _plan_geometry(opportunity: Opportunity) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    plan = opportunity.plan
    if plan is None or not plan.targets:
        return None
    return (
        plan.entry_zone.lower,
        plan.entry_zone.upper,
        plan.invalidation_price,
        plan.targets[0].price,
    )


def _detection_family(opportunity: Opportunity) -> str:
    """Use the registered candidate family, excluding its candle timestamp."""
    return opportunity.candidate_id.rsplit(".", 1)[0]


class ThesisIntelligenceService:
    """Create stable thesis records without rewriting immutable assessments.

    Matching is intentionally conservative and explicitly diagnostic. Exact
    geometry, direction, scope and a bounded temporal context are required;
    otherwise a new thesis or an ambiguous relation is retained.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def attach_assessment(self, opportunity: Opportunity) -> ThesisMatch:
        observed_at = _utc(opportunity.audit.available_at)
        geometry = _plan_geometry(opportunity)
        detection_family = _detection_family(opportunity)
        assessment_id = opportunity.assessment_id
        payload = opportunity.to_dict()
        payload_hash = _hash(payload)
        async with self._sessions.begin() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"thesis-assessment:{assessment_id}"},
            )
            existing = await session.execute(
                text("SELECT thesis_id, match_status, match_reason FROM opportunity_thesis_assessments WHERE assessment_id = :assessment_id"),
                {"assessment_id": assessment_id},
            )
            row = existing.first()
            if row is not None:
                return ThesisMatch(row.thesis_id, row.match_status, row.match_reason)

            candidates = await session.execute(
                text("""
                    SELECT thesis_id, original_entry_lower, original_entry_upper,
                           original_stop, original_target, original_created_at
                    FROM opportunity_theses
                    WHERE instrument = :instrument AND timeframe = :timeframe
                      AND direction = :direction
                      AND detection_family = :detection_family
                      AND original_created_at BETWEEN :window_start AND :window_end
                      AND current_state NOT IN ('RESOLVED', 'INVALIDATED', 'EXPIRED', 'OUTCOME_AMBIGUOUS')
                    ORDER BY original_created_at DESC
                """),
                {
                    "instrument": opportunity.scope.instrument,
                    "timeframe": opportunity.scope.timeframe,
                    "direction": opportunity.stance.value,
                    "detection_family": detection_family,
                    "window_start": observed_at - MATCH_WINDOW,
                    "window_end": observed_at + MATCH_WINDOW,
                },
            )
            exact: list[str] = []
            for candidate in candidates:
                values = tuple(candidate[index] for index in range(1, 5))
                if geometry is not None and all(
                    Decimal(str(left)) == right for left, right in zip(values, geometry)
                ):
                    exact.append(candidate.thesis_id)
            created_new = False
            if len(exact) == 1:
                thesis_id = exact[0]
                status = "MATCHED_EXACT_GEOMETRY"
                reason = "scope_direction_geometry_and_temporal_context_match"
            elif len(exact) > 1:
                thesis_id = exact[-1]
                status = "AMBIGUOUS"
                reason = "multiple_exact_geometry_candidates"
            else:
                family_candidates = [candidate.thesis_id for candidate in candidates]
                if family_candidates:
                    thesis_id = family_candidates[-1]
                    status = "AMBIGUOUS"
                    reason = "same_registered_detection_family_but_plan_geometry_changed"
                else:
                    thesis_id = self._new_thesis_id(opportunity)
                    created_new = True
                    status = "NEW_THESIS"
                    reason = (
                        "no_existing_exact_geometry_candidate"
                        if geometry is not None
                        else "plan_geometry_missing_relation_ambiguous"
                    )
                    if geometry is None:
                        status = "AMBIGUOUS"

            if created_new:
                await self._insert_thesis(session, thesis_id, opportunity, observed_at, payload_hash)
                await self._insert_event(
                    session,
                    thesis_id,
                    "THESIS_CREATED",
                    observed_at,
                    {"assessment_id": assessment_id, "match_status": status, "policy": MATCH_POLICY_VERSION},
                )
            else:
                await session.execute(
                    text("UPDATE opportunity_theses SET last_observed_at = :observed_at, updated_at = now() WHERE thesis_id = :thesis_id"),
                    {"observed_at": observed_at, "thesis_id": thesis_id},
                )
            await session.execute(
                text("""
                    INSERT INTO opportunity_thesis_assessments
                    (thesis_id, assessment_id, opportunity_version_id, match_status,
                     match_reason, assessment_payload, observed_at, payload_hash)
                    VALUES (:thesis_id, :assessment_id, :version_id, :match_status,
                            :match_reason, CAST(:payload AS jsonb), :observed_at, :payload_hash)
                """),
                {
                    "thesis_id": thesis_id,
                    "assessment_id": assessment_id,
                    "version_id": opportunity.opportunity_version_id,
                    "match_status": status,
                    "match_reason": reason,
                    "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    "observed_at": observed_at,
                    "payload_hash": payload_hash,
                },
            )
            if status == "MATCHED_EXACT_GEOMETRY":
                await self._insert_event(
                    session,
                    thesis_id,
                    "ASSESSMENT_ATTACHED",
                    observed_at,
                    {"assessment_id": assessment_id, "policy": MATCH_POLICY_VERSION},
                )
            return ThesisMatch(thesis_id, status, reason)

    @staticmethod
    def _new_thesis_id(opportunity: Opportunity) -> str:
        return "thesis." + _hash({
            "scope": opportunity.scope.to_dict(),
            "direction": opportunity.stance.value,
            "assessment_id": opportunity.assessment_id,
        })

    async def _insert_thesis(
        self,
        session: AsyncSession,
        thesis_id: str,
        opportunity: Opportunity,
        observed_at: datetime,
        payload_hash: str,
    ) -> None:
        geometry = _plan_geometry(opportunity)
        plan = opportunity.plan.to_dict() if opportunity.plan is not None else None
        values: dict[str, Any] = {
            "thesis_id": thesis_id,
            "instrument": opportunity.scope.instrument,
            "timeframe": opportunity.scope.timeframe,
            "direction": opportunity.stance.value,
            "assessment_id": opportunity.assessment_id,
            "opportunity_id": opportunity.opportunity_id,
            "version_id": opportunity.opportunity_version_id,
            "detection_family": _detection_family(opportunity),
            "entry_lower": str(geometry[0]) if geometry else None,
            "entry_upper": str(geometry[1]) if geometry else None,
            "stop": str(geometry[2]) if geometry else None,
            "target": str(geometry[3]) if geometry else None,
            "plan": json.dumps(plan, sort_keys=True, separators=(",", ":")) if plan else None,
            "evidence": json.dumps({"evidence_package": opportunity.evidence_package_reference.to_dict()}),
            "reasons": json.dumps(list(opportunity.reason_codes)),
            "policy": MATCH_POLICY_VERSION,
            "provenance": payload_hash,
            "created": observed_at,
        }
        await session.execute(
            text("""
                INSERT INTO opportunity_theses
                (thesis_id, instrument, timeframe, direction, original_assessment_id,
                 original_opportunity_id, original_opportunity_version_id, detection_family,
                 original_entry_lower, original_entry_upper, original_stop,
                 original_target, original_plan, original_evidence,
                 original_reason_codes, strategy_policy_version, provenance_hash,
                 original_created_at, last_observed_at)
                VALUES (:thesis_id, :instrument, :timeframe, :direction, :assessment_id,
                        :opportunity_id, :version_id, :detection_family, :entry_lower, :entry_upper,
                        :stop, :target, CAST(:plan AS jsonb), CAST(:evidence AS jsonb),
                        CAST(:reasons AS jsonb), :policy, :provenance, :created, :created)
            """),
            values,
        )

    async def _insert_event(
        self,
        session: AsyncSession,
        thesis_id: str,
        event_type: str,
        occurred_at: datetime,
        payload: dict[str, Any],
    ) -> None:
        event_id = f"thesis-event.{_hash({'thesis_id': thesis_id, 'event_type': event_type, 'occurred_at': occurred_at.isoformat(), 'payload': payload})}"
        event_hash = _hash({"event_id": event_id, "payload": payload})
        await session.execute(
            text("""
                INSERT INTO opportunity_thesis_events
                (event_id, thesis_id, event_type, occurred_at, payload, event_hash)
                VALUES (:event_id, :thesis_id, :event_type, :occurred_at,
                        CAST(:payload AS jsonb), :event_hash)
                ON CONFLICT (event_hash) DO NOTHING
            """),
            {
                "event_id": event_id,
                "thesis_id": thesis_id,
                "event_type": event_type,
                "occurred_at": occurred_at,
                "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                "event_hash": event_hash,
            },
        )

    async def observe_candle(self, candle: dict[str, Any]) -> int:
        """Advance active thesis diagnostics using one finalized candle."""
        timestamp = _utc(candle["timestamp"])
        async with self._sessions.begin() as session:
            rows = (await session.execute(text("""
                SELECT thesis_id, direction, current_state, original_entry_lower,
                       original_entry_upper, original_stop, original_target,
                       original_plan, original_created_at
                FROM opportunity_theses
                WHERE instrument = 'BTCUSDT' AND timeframe = '5m'
                  AND current_state NOT IN ('INITIAL_TARGET_REACHED', 'INVALIDATED', 'EXPIRED', 'RESOLVED', 'OUTCOME_AMBIGUOUS')
                FOR UPDATE
            """))).mappings().all()
            changed = 0
            for row in rows:
                next_state = self._state_for_candle(row, candle, timestamp)
                if next_state == row["current_state"]:
                    await session.execute(text("UPDATE opportunity_theses SET last_observed_at = :timestamp, updated_at = now() WHERE thesis_id = :thesis_id"), {"timestamp": timestamp, "thesis_id": row["thesis_id"]})
                    continue
                await session.execute(text("UPDATE opportunity_theses SET current_state = :state, last_observed_at = :timestamp, updated_at = now() WHERE thesis_id = :thesis_id"), {"state": next_state, "timestamp": timestamp, "thesis_id": row["thesis_id"]})
                await self._insert_event(session, row["thesis_id"], "STATE_CHANGED", timestamp, {"from": row["current_state"], "to": next_state, "candle_timestamp": timestamp.isoformat(), "candle_provenance": candle.get("provenance")})
                changed += 1
            return changed

    @staticmethod
    def _state_for_candle(row: Any, candle: dict[str, Any], timestamp: datetime) -> str:
        state = row["current_state"]
        direction = row["direction"]
        low = Decimal(str(candle["low"]))
        high = Decimal(str(candle["high"]))
        entry_low = row["original_entry_lower"]
        entry_high = row["original_entry_upper"]
        stop = row["original_stop"]
        target = row["original_target"]
        if None in (entry_low, entry_high, stop, target):
            return "OUTCOME_AMBIGUOUS"
        entry_low, entry_high, stop, target = map(Decimal, (entry_low, entry_high, stop, target))
        if direction == "BUY":
            stop_hit, target_hit = low <= stop, high >= target
            in_entry = low <= entry_high and high >= entry_low
            passed_entry = low > entry_high
        else:
            stop_hit, target_hit = high >= stop, low <= target
            in_entry = high >= entry_low and low <= entry_high
            passed_entry = high < entry_low
        if stop_hit and target_hit:
            return "OUTCOME_AMBIGUOUS"
        if stop_hit:
            return "INVALIDATED"
        if target_hit and state in {"MONITORING", "ENTRY_AVAILABLE"}:
            return "INITIAL_TARGET_REACHED"
        if state in {"DETECTED", "WAITING_FOR_ENTRY", "ENTRY_MISSED"}:
            if in_entry:
                return "ENTRY_AVAILABLE"
            if passed_entry:
                return "ENTRY_MISSED"
            return "WAITING_FOR_ENTRY"
        return "MONITORING"

    async def list(self, *, instrument: str = "BTCUSDT", timeframe: str = "5m", limit: int = 100) -> list[dict[str, Any]]:
        async with self._sessions() as session:
            rows = (await session.execute(text("SELECT * FROM opportunity_theses WHERE instrument = :instrument AND timeframe = :timeframe ORDER BY original_created_at ASC LIMIT :limit"), {"instrument": instrument, "timeframe": timeframe, "limit": limit})).mappings().all()
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                grouped.setdefault(row["detection_family"], []).append(dict(row))
            result: list[dict[str, Any]] = []
            for family, members in grouped.items():
                primary = members[0]
                primary["related_thesis_ids"] = [item["thesis_id"] for item in members]
                primary["related_assessment_count"] = sum(
                    1 for item in members if item["original_assessment_id"]
                )
                primary["review_cluster_status"] = (
                    "SINGLE_THESIS" if len(members) == 1 else "AMBIGUOUS_REVIEW_CLUSTER"
                )
                primary["detection_family"] = family
                result.append(primary)
            return result[:limit]

    async def get(self, thesis_id: str) -> dict[str, Any] | None:
        async with self._sessions() as session:
            row = (await session.execute(text("SELECT * FROM opportunity_theses WHERE thesis_id = :thesis_id"), {"thesis_id": thesis_id})).mappings().first()
            if row is None:
                return None
            events = (await session.execute(text("SELECT event_id, event_type, occurred_at, payload, event_hash FROM opportunity_thesis_events WHERE thesis_id = :thesis_id ORDER BY occurred_at, event_id"), {"thesis_id": thesis_id})).mappings().all()
            assessments = (await session.execute(text("SELECT assessment_id, opportunity_version_id, match_status, match_reason, observed_at, payload_hash FROM opportunity_thesis_assessments WHERE thesis_id = :thesis_id ORDER BY observed_at, assessment_id"), {"thesis_id": thesis_id})).mappings().all()
            result = dict(row)
            result["events"] = [dict(item) for item in events]
            result["assessments"] = [dict(item) for item in assessments]
            return result
