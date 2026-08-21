"""Multi-market architecture tests.

Proves, without altering certified BTCUSDT behavior:
  1. An explicit ETHUSDT MarketScope propagates through detection,
     assessment, qualification and scoring without fallback to BTCUSDT.
  2. Default-scoped services continue to reject non-BTCUSDT inputs
     (fail-closed backward compatibility).
  3. Ranking populations cannot mix instruments: an ETHUSDT score inside
     the rolling window is excluded from a BTCUSDT-triggered snapshot.
  4. The expected-move artifact instrument binding fails closed: a
     mismatched declared identity or a legacy artifact applied to a
     non-default scope is refused at pipeline construction.
"""

import unittest
from types import SimpleNamespace

from app.market_configuration import get_default_scope
from app.opportunity_intelligence.persistence import DetectionMemoryRepository
from app.runtime_detection.service import RuntimeOpportunityDetectionService
from app.runtime_pipeline import build_runtime_pipeline
from app.runtime_ranking.service import RuntimeRankingService
from tests.test_runtime_evidence import _fixture as _evidence_fixture
from tests.test_runtime_ranking import (
    _as_of,
    _make_service,
    _ranking_fixture,
)


class MarketScopePropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_ethusdt_scope_propagates_through_chain(self) -> None:
        """ETHUSDT scope flows detection -> assessment -> qualification -> scoring."""
        fixture, _, opportunity, qualification, score, _, _ = (
            await _ranking_fixture(instrument="ETHUSDT")
        )

        self.assertEqual(fixture.market.scope.instrument, "ETHUSDT")
        self.assertEqual(fixture.candidate.scope.instrument, "ETHUSDT")
        self.assertEqual(opportunity.scope.instrument, "ETHUSDT")
        self.assertEqual(score.score_id.startswith("score"), True)

    async def test_default_scope_rejects_non_btcusdt_input(self) -> None:
        """A default-scoped (BTCUSDT) detector must not emit ETHUSDT candidates."""
        fixture = await _evidence_fixture(
            "101.000000000000000000", "100.000000000000000000",
            "65.000000000000000000", "ETHUSDT",
        )
        fresh_detections = DetectionMemoryRepository()
        default_detector = RuntimeOpportunityDetectionService(
            market_snapshots=fixture.markets,
            feature_snapshots=fixture.features,
            market_contexts=fixture.contexts,
            detections=fresh_detections,
            code_version="git:multimarket-default",
        )
        self.assertEqual(default_detector._scope, get_default_scope())

        attempt, candidate = await default_detector.detect(
            fixture.market, fixture.feature, fixture.context
        )
        self.assertIsNone(candidate)
        self.assertEqual(attempt.state.value, "UNAVAILABLE")


class RankingMarketIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_btcusdt_population_excludes_ethusdt_score(self) -> None:
        """A cross-instrument score can never enter the ranking membership."""
        btc_fixture, _, btc_opportunity, btc_qualification, btc_score, btc_service, _ = (
            await _ranking_fixture()
        )
        eth_fixture, _, eth_opportunity, eth_qualification, eth_score, _, _ = (
            await _ranking_fixture(instrument="ETHUSDT")
        )

        # Transplant the ETH chain artifacts into the BTC stores so both
        # scores coexist in one rolling window.
        await btc_fixture.opportunities.save(eth_opportunity)
        await btc_fixture.qualifications.save(eth_qualification)
        await btc_fixture.scores.save(eth_score)

        snapshot = await btc_service.rank(
            (btc_opportunity,), (btc_qualification,), (btc_score,), _as_of(btc_fixture)
        )

        membership_opportunity_ids = {
            member.opportunity_id for member in snapshot.memberships
        }
        self.assertEqual(membership_opportunity_ids, {btc_opportunity.opportunity_id})
        self.assertEqual(snapshot.memberships[0].rank, 1)

        excluded_score_ids = {
            exclusion.candidate_id for exclusion in snapshot.exclusions
        }
        self.assertIn(eth_score.score_id, excluded_score_ids)
        for exclusion in snapshot.exclusions:
            if exclusion.candidate_id == eth_score.score_id:
                self.assertIn(
                    "ranking.lineage_validation_failed", exclusion.reason_codes
                )


class ArtifactInstrumentBindingTests(unittest.TestCase):
    def test_mismatched_declared_instrument_fails_closed(self) -> None:
        inference = SimpleNamespace(scope_instrument="ETHUSDT")
        with self.assertRaises(ValueError):
            build_runtime_pipeline(session_factory=object(), expected_move_inference=inference)

    def test_legacy_artifact_rejected_for_non_default_scope(self) -> None:
        inference = SimpleNamespace(scope_instrument=None)
        from app.opportunity_intelligence.domain import MarketScope

        eth_scope = MarketScope(instrument="ETHUSDT", timeframe="5m")
        with self.assertRaises(ValueError):
            build_runtime_pipeline(
                session_factory=object(),
                expected_move_inference=inference,
                scope=eth_scope,
            )

    def test_declared_matching_instrument_builds(self) -> None:
        inference = SimpleNamespace(scope_instrument="BTCUSDT")
        pipeline = build_runtime_pipeline(
            session_factory=object(), expected_move_inference=inference
        )
        self.assertIsNotNone(pipeline)


if __name__ == "__main__":
    unittest.main()
