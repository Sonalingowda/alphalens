"""PostgreSQL-backed thesis identity and idempotency regressions.

These tests require an explicitly supplied disposable PostgreSQL database:
``ALPHALENS_THESIS_TEST_DATABASE_URL``. They never use the owner-facing or
Batch 6Z observation databases.
"""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.opportunity_intelligence.domain.primitives import MarketScope, PriceRange
from app.opportunity_intelligence.domain.stances import OpportunityStance
from app.thesis_intelligence import ThesisIntelligenceService


DATABASE_URL = os.getenv("ALPHALENS_THESIS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="requires an explicitly supplied disposable PostgreSQL database",
)


class _Plan:
    def __init__(self, geometry: tuple[str, str, str, str], assessment_id: str) -> None:
        lower, upper, stop, target = map(Decimal, geometry)
        self.entry_zone = PriceRange(lower, upper)
        self.invalidation_price = stop
        self.targets = (SimpleNamespace(price=target),)
        self.assessment_id = assessment_id

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_zone": {
                "lower": str(self.entry_zone.lower),
                "upper": str(self.entry_zone.upper),
            },
            "invalidation_price": str(self.invalidation_price),
            "target": str(self.targets[0].price),
        }


class _Opportunity:
    def __init__(
        self,
        assessment_id: str,
        geometry: tuple[str, str, str, str],
        *,
        available_at: datetime,
    ) -> None:
        self.assessment_id = assessment_id
        self.opportunity_id = f"opportunity.test.{assessment_id}"
        self.opportunity_version_id = f"{self.opportunity_id}.v1"
        self.candidate_id = "candidate.test.registered_family.BTCUSDT.5m.123"
        self.scope = MarketScope("BTCUSDT", "5m")
        self.stance = OpportunityStance.SELL
        self.plan = _Plan(geometry, assessment_id)
        self.reason_codes = ("test.genuine_detection",)
        self.evidence_package_reference = SimpleNamespace(
            available_at=available_at,
            to_dict=lambda: {"artifact_id": f"evidence.{assessment_id}"},
        )
        self.audit = SimpleNamespace(available_at=available_at)

    def to_dict(self) -> dict[str, object]:
        return {
            "assessment_id": self.assessment_id,
            "opportunity_id": self.opportunity_id,
            "opportunity_version_id": self.opportunity_version_id,
            "candidate_id": self.candidate_id,
            "scope": self.scope.to_dict(),
            "stance": self.stance.value,
            "plan": self.plan.to_dict(),
        }


async def _open_sessions():
    assert DATABASE_URL is not None
    engine = create_async_engine(DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE opportunity_thesis_events, "
                "opportunity_thesis_assessments, opportunity_theses CASCADE"
            )
        )
    return engine, sessions


def _opportunity(assessment_id: str, geometry: tuple[str, str, str, str]) -> _Opportunity:
    return _Opportunity(
        assessment_id,
        geometry,
        available_at=datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc),
    )


def test_identical_geometry_attaches_to_one_thesis_and_preserves_original():
    if DATABASE_URL is None:
        pytest.skip("requires an explicitly supplied disposable PostgreSQL database")
    asyncio.run(_test_identical_geometry_attaches_to_one_thesis())


async def _test_identical_geometry_attaches_to_one_thesis():
    engine, thesis_sessions = await _open_sessions()
    service = ThesisIntelligenceService(thesis_sessions)
    geometry = ("80100", "80100", "80200", "79950")

    try:
        first = await service.attach_assessment(_opportunity("a-1", geometry))
        second = await service.attach_assessment(_opportunity("a-2", geometry))

        assert first.status == "NEW_THESIS"
        assert second.status == "MATCHED_EXACT_GEOMETRY"
        assert second.thesis_id == first.thesis_id
        async with thesis_sessions() as session:
            thesis = (
                await session.execute(
                    text(
                        "SELECT original_entry_lower, original_stop, original_target "
                        "FROM opportunity_theses WHERE thesis_id = :id"
                    ),
                    {"id": first.thesis_id},
                )
            ).one()
            counts = (
                await session.execute(
                    text(
                        "SELECT (SELECT count(*) FROM opportunity_theses), "
                        "(SELECT count(*) FROM opportunity_thesis_assessments)"
                    )
                )
            ).one()
        assert tuple(map(str, thesis)) == ("80100.000000000000000000", "80200.000000000000000000", "79950.000000000000000000")
        assert counts == (1, 2)
    finally:
        await engine.dispose()


def test_changed_geometry_is_separate_or_explicitly_ambiguous():
    if DATABASE_URL is None:
        pytest.skip("requires an explicitly supplied disposable PostgreSQL database")
    asyncio.run(_test_changed_geometry_is_separate_or_explicitly_ambiguous())


async def _test_changed_geometry_is_separate_or_explicitly_ambiguous():
    engine, thesis_sessions = await _open_sessions()
    service = ThesisIntelligenceService(thesis_sessions)
    try:
        first = await service.attach_assessment(
            _opportunity("a-1", ("80100", "80100", "80200", "79950"))
        )
        changed = await service.attach_assessment(
            _opportunity("a-2", ("80000", "80000", "80120", "79800"))
        )

        assert (
            changed.status == "AMBIGUOUS"
            and changed.thesis_id == first.thesis_id
        ) or (
            changed.status == "NEW_THESIS"
            and changed.thesis_id != first.thesis_id
        )
        async with thesis_sessions() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT original_entry_lower, original_stop, original_target "
                        "FROM opportunity_theses"
                    )
                )
            ).all()
        assert len(rows) in {1, 2}
        assert tuple(map(str, rows[0])) == ("80100.000000000000000000", "80200.000000000000000000", "79950.000000000000000000")
    finally:
        await engine.dispose()


def test_restart_and_concurrent_duplicate_ingestion_are_idempotent():
    if DATABASE_URL is None:
        pytest.skip("requires an explicitly supplied disposable PostgreSQL database")
    asyncio.run(_test_restart_and_concurrent_duplicate_ingestion())


async def _test_restart_and_concurrent_duplicate_ingestion():
    engine, thesis_sessions = await _open_sessions()
    geometry = ("80100", "80100", "80200", "79950")
    first_service = ThesisIntelligenceService(thesis_sessions)
    try:
        first = await first_service.attach_assessment(_opportunity("a-1", geometry))

        restarted_service = ThesisIntelligenceService(thesis_sessions)
        repeated = _opportunity("a-1", geometry)
        results = await asyncio.gather(
            restarted_service.attach_assessment(repeated),
            ThesisIntelligenceService(thesis_sessions).attach_assessment(repeated),
        )

        assert {result.thesis_id for result in results} == {first.thesis_id}
        assert {result.status for result in results} == {"NEW_THESIS"}
        async with thesis_sessions() as session:
            counts = (
                await session.execute(
                    text(
                        "SELECT (SELECT count(*) FROM opportunity_theses), "
                        "(SELECT count(*) FROM opportunity_thesis_assessments), "
                        "(SELECT count(*) FROM opportunity_thesis_events)"
                    )
                )
            ).one()
        assert counts == (1, 1, 1)
    finally:
        await engine.dispose()
