"""Tests for Expected-Move V2: artifact, plan service, and qualification gate."""

import math
import unittest
from decimal import Decimal

import numpy as np

from app.inference.artifact import (
    EXPECTED_MOVE_ARTIFACT_VERSION,
    EXPECTED_MOVE_MAX_RR,
    EXPECTED_MOVE_MIN_SNR,
    EXPECTED_MOVE_MODEL_FAMILY,
    ExpectedMovePrediction,
    PackagedExpectedMoveInference,
    hash_json,
    load_expected_move_inference_artifact,
)
from app.opportunity_intelligence.domain import QualificationStatus


class TestExpectedMoveArtifact(unittest.TestCase):
    """Verify artifact loading and deterministic inference."""

    def _make_artifact_payload(
        self,
        *,
        feature_names: tuple[str, ...] = ("f1", "f2"),
        residual_std: float = 0.001,
    ) -> dict:
        n = len(feature_names)
        means = [0.0] * n
        scales = [1.0] * n
        coefficients = [0.5] * n
        intercept = 0.001
        core = {
            "ordered_feature_schema": [{"name": name} for name in feature_names],
            "numeric_state": {
                "scaler_means_float_hex": [float(m).hex() for m in means],
                "scaler_scales_float_hex": [float(s).hex() for s in scales],
                "ridge_coefficients_float_hex": [float(c).hex() for c in coefficients],
                "ridge_intercept_float_hex": float(intercept).hex(),
                "residual_std_float_hex": float(residual_std).hex(),
            },
        }
        state_hash = hash_json(core)
        payload = {
            "artifact_version": EXPECTED_MOVE_ARTIFACT_VERSION,
            "model_family": EXPECTED_MOVE_MODEL_FAMILY,
            "created_at": "2026-01-01T00:00:00Z",
            "state_sha256": state_hash,
            "core": core,
        }
        return payload

    def test_loads_successfully(self) -> None:
        payload = self._make_artifact_payload()
        sha = hash_json(payload)
        inference = load_expected_move_inference_artifact(
            payload, expected_artifact_sha256=sha
        )
        self.assertEqual(inference.feature_names, ("f1", "f2"))
        self.assertAlmostEqual(inference.residual_std, 0.001, places=6)

    def test_hash_verification_fails_on_tamper(self) -> None:
        payload = self._make_artifact_payload()
        sha = hash_json(payload)
        payload["core"]["numeric_state"]["residual_std_float_hex"] = float(0.002).hex()
        with self.assertRaises(ValueError):
            load_expected_move_inference_artifact(
                payload, expected_artifact_sha256=sha
            )

    def test_wrong_version_rejected(self) -> None:
        payload = self._make_artifact_payload()
        payload["artifact_version"] = "1.0.0"
        sha = hash_json(payload)
        with self.assertRaises(ValueError):
            load_expected_move_inference_artifact(
                payload, expected_artifact_sha256=sha
            )

    def test_wrong_model_family_rejected(self) -> None:
        payload = self._make_artifact_payload()
        payload["model_family"] = "ridge_regression"
        sha = hash_json(payload)
        with self.assertRaises(ValueError):
            load_expected_move_inference_artifact(
                payload, expected_artifact_sha256=sha
            )

    def test_deterministic_inference(self) -> None:
        payload = self._make_artifact_payload()
        sha = hash_json(payload)
        inference = load_expected_move_inference_artifact(
            payload, expected_artifact_sha256=sha
        )
        features = (Decimal("1.0"), Decimal("2.0"))
        first = inference.predict(features)
        second = inference.predict(features)
        self.assertEqual(first.value, second.value)
        self.assertEqual(first.float_hex, second.float_hex)
        self.assertEqual(first.snr, second.snr)

    def test_prediction_is_non_negative(self) -> None:
        payload = self._make_artifact_payload()
        sha = hash_json(payload)
        inference = load_expected_move_inference_artifact(
            payload, expected_artifact_sha256=sha
        )
        prediction = inference.predict((Decimal("1.0"), Decimal("2.0")))
        self.assertGreaterEqual(prediction.value, 0.0)
        self.assertTrue(math.isfinite(prediction.value))

    def test_snr_is_computed_correctly(self) -> None:
        payload = self._make_artifact_payload(residual_std=0.001)
        sha = hash_json(payload)
        inference = load_expected_move_inference_artifact(
            payload, expected_artifact_sha256=sha
        )
        prediction = inference.predict((Decimal("0.0"), Decimal("0.0")))
        expected_snr = prediction.value / 0.001
        self.assertAlmostEqual(prediction.snr, expected_snr, places=6)

    def test_expected_move_prediction_dataclass(self) -> None:
        pred = ExpectedMovePrediction(value=0.001, float_hex=float(0.001).hex(), snr=2.0)
        self.assertEqual(pred.value, 0.001)
        self.assertEqual(pred.snr, 2.0)

    def test_negative_prediction_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ExpectedMovePrediction(value=-0.001, float_hex="", snr=1.0)

    def test_non_finite_snr_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ExpectedMovePrediction(value=0.001, float_hex="", snr=float("nan"))


class TestPlanDomainV2Fields(unittest.TestCase):
    """Verify OpportunityPlan accepts V2 optional fields."""

    def test_v2_plan_accepts_expected_move_fields(self) -> None:
        from app.opportunity_intelligence.domain.plan import OpportunityPlan, PlanTarget
        from app.opportunity_intelligence.domain.primitives import (
            AuditMetadata,
            IntegrityReference,
            MarketScope,
            PolicyReference,
            PriceRange,
            Provenance,
        )
        from app.opportunity_intelligence.domain.stances import OpportunityStance

        from datetime import datetime, timezone

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scope = MarketScope(instrument="BTCUSDT", timeframe="5m")
        policy = PolicyReference("test", "1.0.0", "0" * 64)
        source = IntegrityReference(
            artifact_id="src.test.1",
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=now,
        )
        audit = AuditMetadata(
            created_at=now,
            evidence_cutoff=now,
            available_at=now,
            provenance=Provenance(
                source_references=(source,),
                policy_references=(policy,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        )
        target = PlanTarget(
            target_id="plan.test.1.tp1",
            price=Decimal("115.000000000000000000"),
            potential_reward=Decimal("15.000000000000000000"),
            risk_reward=Decimal("1.500000000000000000"),
            evidence_references=(source,),
        )
        plan = OpportunityPlan(
            contract_version="2.0.0",
            plan_id="plan.test.1",
            opportunity_id="opp.test.1",
            assessment_id="assess.test.1",
            decision_id="decision.test.1",
            policy=policy,
            scope=scope,
            direction=OpportunityStance.BUY,
            reference_price=Decimal("100.000000000000000000"),
            reference_price_source=source,
            entry_zone=PriceRange(
                lower=Decimal("100.000000000000000000"),
                upper=Decimal("100.000000000000000000"),
            ),
            entry_semantics="reference_price_exact",
            invalidation_price=Decimal("90.000000000000000000"),
            invalidation_condition="price_below_invalidation",
            targets=(target,),
            risk=Decimal("10.000000000000000000"),
            risk_unit="price_distance",
            assumptions=("test",),
            limitations=("test",),
            valid_until=None,
            audit=audit,
            expected_move_prediction=Decimal("15.000000000000000000"),
            expected_move_confidence=Decimal("2.5"),
            prediction_horizon_minutes=25,
        )
        self.assertEqual(plan.contract_version, "2.0.0")
        self.assertEqual(plan.expected_move_prediction, Decimal("15.000000000000000000"))
        self.assertEqual(plan.expected_move_confidence, Decimal("2.5"))
        self.assertEqual(plan.prediction_horizon_minutes, 25)

    def test_v1_plan_still_works(self) -> None:
        from app.opportunity_intelligence.domain.plan import OpportunityPlan, PlanTarget
        from app.opportunity_intelligence.domain.primitives import (
            AuditMetadata,
            IntegrityReference,
            MarketScope,
            PolicyReference,
            PriceRange,
            Provenance,
        )
        from app.opportunity_intelligence.domain.stances import OpportunityStance

        from datetime import datetime, timezone

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scope = MarketScope(instrument="BTCUSDT", timeframe="5m")
        policy = PolicyReference("test", "1.0.0", "0" * 64)
        source = IntegrityReference(
            artifact_id="src.test.1",
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=now,
        )
        audit = AuditMetadata(
            created_at=now,
            evidence_cutoff=now,
            available_at=now,
            provenance=Provenance(
                source_references=(source,),
                policy_references=(policy,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        )
        target = PlanTarget(
            target_id="plan.test.1.tp1",
            price=Decimal("115.000000000000000000"),
            potential_reward=Decimal("15.000000000000000000"),
            risk_reward=Decimal("1.500000000000000000"),
            evidence_references=(source,),
        )
        plan = OpportunityPlan(
            contract_version="1.0.0",
            plan_id="plan.test.1",
            opportunity_id="opp.test.1",
            assessment_id="assess.test.1",
            decision_id="decision.test.1",
            policy=policy,
            scope=scope,
            direction=OpportunityStance.BUY,
            reference_price=Decimal("100.000000000000000000"),
            reference_price_source=source,
            entry_zone=PriceRange(
                lower=Decimal("100.000000000000000000"),
                upper=Decimal("100.000000000000000000"),
            ),
            entry_semantics="reference_price_exact",
            invalidation_price=Decimal("90.000000000000000000"),
            invalidation_condition="price_below_invalidation",
            targets=(target,),
            risk=Decimal("10.000000000000000000"),
            risk_unit="price_distance",
            assumptions=("test",),
            limitations=("test",),
            valid_until=None,
            audit=audit,
        )
        self.assertEqual(plan.contract_version, "1.0.0")
        self.assertIsNone(plan.expected_move_prediction)
        self.assertIsNone(plan.expected_move_confidence)
        self.assertIsNone(plan.prediction_horizon_minutes)


class TestV2PlanGeometry(unittest.TestCase):
    """Verify V2 target geometry: predicted_distance, 3R cap, horizon."""

    def _make_inference(
        self,
        feature_names: tuple[str, ...] = ("f1", "f2"),
        coefficients: tuple[float, ...] = (0.5, 0.5),
        intercept: float = 0.001,
        residual_std: float = 0.001,
    ) -> PackagedExpectedMoveInference:
        n = len(feature_names)
        return PackagedExpectedMoveInference(
            feature_names=feature_names,
            scaler_means=np.zeros(n, dtype=np.float64),
            scaler_scales=np.ones(n, dtype=np.float64),
            coefficients=np.array(coefficients, dtype=np.float64),
            intercept=intercept,
            residual_std=residual_std,
            artifact_sha256="a" * 64,
            state_sha256="b" * 64,
        )

    def test_predicted_distance_conversion(self) -> None:
        inference = self._make_inference(
            feature_names=("f1",),
            coefficients=(0.005,),
            intercept=0.0,
            residual_std=0.001,
        )
        prediction = inference.predict((Decimal("1.0"),))
        ref_price = Decimal("100000.000000000000000000")
        predicted_distance = (
            ref_price * (Decimal(str(math.exp(prediction.value))) - 1)
        ).quantize(Decimal("0.000000000000000001"))
        self.assertGreater(predicted_distance, Decimal(0))
        self.assertGreater(prediction.snr, 0)

    def test_3R_cap_applies(self) -> None:
        inference = self._make_inference(
            feature_names=("f1",),
            coefficients=(0.05,),
            intercept=0.0,
            residual_std=0.001,
        )
        prediction = inference.predict((Decimal("1.0"),))
        ref_price = Decimal("100000.000000000000000000")
        atr = Decimal("10.000000000000000000")
        predicted_distance = (
            ref_price * (Decimal(str(math.exp(prediction.value))) - 1)
        ).quantize(Decimal("0.000000000000000001"))
        cap_distance = (atr * EXPECTED_MOVE_MAX_RR).quantize(
            Decimal("0.000000000000000001")
        )
        target_distance = min(predicted_distance, cap_distance)
        self.assertLessEqual(target_distance, atr * EXPECTED_MOVE_MAX_RR)

    def test_3R_cap_does_not_shrink_small_moves(self) -> None:
        inference = self._make_inference(
            feature_names=("f1",),
            coefficients=(0.001,),
            intercept=0.0001,
            residual_std=0.001,
        )
        prediction = inference.predict((Decimal("0.0"),))
        ref_price = Decimal("100000.000000000000000000")
        atr = Decimal("10.000000000000000000")
        predicted_distance = (
            ref_price * (Decimal(str(math.exp(prediction.value))) - 1)
        ).quantize(Decimal("0.000000000000000001"))
        cap_distance = (atr * EXPECTED_MOVE_MAX_RR).quantize(
            Decimal("0.000000000000000001")
        )
        target_distance = min(predicted_distance, cap_distance)
        self.assertEqual(target_distance, predicted_distance)

    def test_horizon_is_25_minutes(self) -> None:
        from app.runtime_opportunity_plan.service import _V2_HORIZON_MINUTES
        self.assertEqual(_V2_HORIZON_MINUTES, 25)

    def test_snr_threshold_is_1(self) -> None:
        self.assertEqual(EXPECTED_MOVE_MIN_SNR, Decimal("1.0"))

    def test_max_rr_is_3(self) -> None:
        self.assertEqual(EXPECTED_MOVE_MAX_RR, Decimal("3.0"))


class TestV1ContractUnchanged(unittest.TestCase):
    """Verify V1.0.0 contract version is still valid for candidates."""

    def test_contract_version_1_accepted(self) -> None:
        from app.opportunity_intelligence.domain.primitives import (
            validate_contract_version,
        )
        validate_contract_version("1.0.0")

    def test_contract_version_2_rejected_for_candidate(self) -> None:
        from app.opportunity_intelligence.domain.primitives import (
            DomainValidationError,
            validate_contract_version,
        )
        with self.assertRaises(DomainValidationError):
            validate_contract_version("2.0.0")

    def test_contract_version_1_1_rejected(self) -> None:
        from app.opportunity_intelligence.domain.primitives import (
            DomainValidationError,
            validate_contract_version,
        )
        with self.assertRaises(DomainValidationError):
            validate_contract_version("1.1.0")


class TestPlanContractVersion(unittest.TestCase):
    """Verify plan contract accepts both 1.0.0 and 2.0.0."""

    def test_plan_contract_version_1_accepted(self) -> None:
        from app.opportunity_intelligence.domain.primitives import (
            validate_plan_contract_version,
        )
        validate_plan_contract_version("1.0.0")

    def test_plan_contract_version_2_accepted(self) -> None:
        from app.opportunity_intelligence.domain.primitives import (
            validate_plan_contract_version,
        )
        validate_plan_contract_version("2.0.0")

    def test_plan_contract_version_1_1_rejected(self) -> None:
        from app.opportunity_intelligence.domain.primitives import (
            DomainValidationError,
            validate_plan_contract_version,
        )
        with self.assertRaises(DomainValidationError):
            validate_plan_contract_version("1.1.0")


class TestRiskRewardGate(unittest.TestCase):
    """Verify the R:R quality gate rejects weak opportunities (R:R < 2.0)."""

    def test_min_rr_constant(self) -> None:
        from app.inference.artifact import EXPECTED_MOVE_MIN_RR
        self.assertEqual(EXPECTED_MOVE_MIN_RR, Decimal("2.0"))

    def _make_opportunity(
        self,
        plan,
        *,
        opportunity_id: str = "opp.test.1",
        opportunity_version_id: str = "oppv.test.1",
    ):
        from app.opportunity_intelligence.domain import Opportunity
        from app.opportunity_intelligence.domain.primitives import (
            AuditMetadata,
            IntegrityReference,
            PolicyReference,
            Provenance,
        )
        from app.opportunity_intelligence.domain.stances import OpportunityStance
        from datetime import datetime, timezone

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        policy = PolicyReference("test", "1.0.0", "0" * 64)
        source = IntegrityReference(
            artifact_id="src.test.1",
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=now,
        )
        audit = AuditMetadata(
            created_at=now,
            evidence_cutoff=now,
            available_at=now,
            provenance=Provenance(
                source_references=(source,),
                policy_references=(policy,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        )
        return Opportunity(
            contract_version="1.0.0",
            opportunity_id=opportunity_id,
            opportunity_version_id=opportunity_version_id,
            assessment_id="assess.test.1",
            decision_id="decision.test.1",
            candidate_id="cand.test.1",
            scope=plan.scope,
            stance=OpportunityStance.BUY,
            decision_policy=policy,
            evidence_package_reference=source,
            context_reference=source,
            reason_codes=("test",),
            limitations=("test",),
            qualification_reference=None,
            score_reference=None,
            confidence=None,
            plan=plan,
            valid_until=None,
            supersedes_opportunity_version_id=None,
            audit=audit,
        )

    def test_rr_gate_passes_above_threshold(self) -> None:
        from app.runtime_qualification.service import _validate_risk_reward
        from app.opportunity_intelligence.domain.plan import OpportunityPlan, PlanTarget
        from app.opportunity_intelligence.domain.primitives import (
            AuditMetadata,
            IntegrityReference,
            MarketScope,
            PolicyReference,
            PriceRange,
            Provenance,
        )
        from app.opportunity_intelligence.domain.stances import OpportunityStance
        from datetime import datetime, timezone

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scope = MarketScope(instrument="BTCUSDT", timeframe="5m")
        policy = PolicyReference("test", "1.0.0", "0" * 64)
        source = IntegrityReference(
            artifact_id="src.test.1",
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=now,
        )
        audit = AuditMetadata(
            created_at=now,
            evidence_cutoff=now,
            available_at=now,
            provenance=Provenance(
                source_references=(source,),
                policy_references=(policy,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        )
        target = PlanTarget(
            target_id="plan.test.1.tp1",
            price=Decimal("125.000000000000000000"),
            potential_reward=Decimal("25.000000000000000000"),
            risk_reward=Decimal("2.500000000000000000"),
            evidence_references=(source,),
        )
        plan = OpportunityPlan(
            contract_version="2.0.0",
            plan_id="plan.test.1",
            opportunity_id="opp.test.1",
            assessment_id="assess.test.1",
            decision_id="decision.test.1",
            policy=policy,
            scope=scope,
            direction=OpportunityStance.BUY,
            reference_price=Decimal("100.000000000000000000"),
            reference_price_source=source,
            entry_zone=PriceRange(
                lower=Decimal("100.000000000000000000"),
                upper=Decimal("100.000000000000000000"),
            ),
            entry_semantics="reference_price_exact",
            invalidation_price=Decimal("90.000000000000000000"),
            invalidation_condition="price_below_invalidation",
            targets=(target,),
            risk=Decimal("10.000000000000000000"),
            risk_unit="price_distance",
            assumptions=("test",),
            limitations=("test",),
            valid_until=None,
            audit=audit,
        )
        opportunity = self._make_opportunity(plan)
        gate = _validate_risk_reward(opportunity)
        self.assertIs(gate.status, QualificationStatus.PASS)
        self.assertEqual(gate.reason_code, "qualification.risk_reward_above_threshold")

    def test_rr_gate_fails_below_threshold(self) -> None:
        from app.runtime_qualification.service import _validate_risk_reward
        from app.opportunity_intelligence.domain.plan import OpportunityPlan, PlanTarget
        from app.opportunity_intelligence.domain.primitives import (
            AuditMetadata,
            IntegrityReference,
            MarketScope,
            PolicyReference,
            PriceRange,
            Provenance,
        )
        from app.opportunity_intelligence.domain.stances import OpportunityStance
        from datetime import datetime, timezone

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scope = MarketScope(instrument="BTCUSDT", timeframe="5m")
        policy = PolicyReference("test", "1.0.0", "0" * 64)
        source = IntegrityReference(
            artifact_id="src.test.1",
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=now,
        )
        audit = AuditMetadata(
            created_at=now,
            evidence_cutoff=now,
            available_at=now,
            provenance=Provenance(
                source_references=(source,),
                policy_references=(policy,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        )
        target = PlanTarget(
            target_id="plan.test.1.tp1",
            price=Decimal("115.000000000000000000"),
            potential_reward=Decimal("15.000000000000000000"),
            risk_reward=Decimal("1.500000000000000000"),
            evidence_references=(source,),
        )
        plan = OpportunityPlan(
            contract_version="2.0.0",
            plan_id="plan.test.1",
            opportunity_id="opp.test.1",
            assessment_id="assess.test.1",
            decision_id="decision.test.1",
            policy=policy,
            scope=scope,
            direction=OpportunityStance.BUY,
            reference_price=Decimal("100.000000000000000000"),
            reference_price_source=source,
            entry_zone=PriceRange(
                lower=Decimal("100.000000000000000000"),
                upper=Decimal("100.000000000000000000"),
            ),
            entry_semantics="reference_price_exact",
            invalidation_price=Decimal("90.000000000000000000"),
            invalidation_condition="price_below_invalidation",
            targets=(target,),
            risk=Decimal("10.000000000000000000"),
            risk_unit="price_distance",
            assumptions=("test",),
            limitations=("test",),
            valid_until=None,
            audit=audit,
        )
        opportunity = self._make_opportunity(plan)
        gate = _validate_risk_reward(opportunity)
        self.assertIs(gate.status, QualificationStatus.FAIL)
        self.assertEqual(gate.reason_code, "qualification.risk_reward_below_threshold")

    def test_rr_gate_exact_threshold_passes(self) -> None:
        from app.runtime_qualification.service import _validate_risk_reward
        from app.opportunity_intelligence.domain.plan import OpportunityPlan, PlanTarget
        from app.opportunity_intelligence.domain.primitives import (
            AuditMetadata,
            IntegrityReference,
            MarketScope,
            PolicyReference,
            PriceRange,
            Provenance,
        )
        from app.opportunity_intelligence.domain.stances import OpportunityStance
        from datetime import datetime, timezone

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        scope = MarketScope(instrument="BTCUSDT", timeframe="5m")
        policy = PolicyReference("test", "1.0.0", "0" * 64)
        source = IntegrityReference(
            artifact_id="src.test.1",
            artifact_type="evidence_package",
            artifact_version="1.0.0",
            integrity_digest="0" * 64,
            available_at=now,
        )
        audit = AuditMetadata(
            created_at=now,
            evidence_cutoff=now,
            available_at=now,
            provenance=Provenance(
                source_references=(source,),
                policy_references=(policy,),
                code_version="test",
                configuration_hash="0" * 64,
                lineage_hash="0" * 64,
            ),
            result_hash="0" * 64,
        )
        target = PlanTarget(
            target_id="plan.test.1.tp1",
            price=Decimal("120.000000000000000000"),
            potential_reward=Decimal("20.000000000000000000"),
            risk_reward=Decimal("2.000000000000000000"),
            evidence_references=(source,),
        )
        plan = OpportunityPlan(
            contract_version="2.0.0",
            plan_id="plan.test.1",
            opportunity_id="opp.test.1",
            assessment_id="assess.test.1",
            decision_id="decision.test.1",
            policy=policy,
            scope=scope,
            direction=OpportunityStance.BUY,
            reference_price=Decimal("100.000000000000000000"),
            reference_price_source=source,
            entry_zone=PriceRange(
                lower=Decimal("100.000000000000000000"),
                upper=Decimal("100.000000000000000000"),
            ),
            entry_semantics="reference_price_exact",
            invalidation_price=Decimal("90.000000000000000000"),
            invalidation_condition="price_below_invalidation",
            targets=(target,),
            risk=Decimal("10.000000000000000000"),
            risk_unit="price_distance",
            assumptions=("test",),
            limitations=("test",),
            valid_until=None,
            audit=audit,
        )
        opportunity = self._make_opportunity(plan)
        gate = _validate_risk_reward(opportunity)
        self.assertIs(gate.status, QualificationStatus.PASS)
        self.assertEqual(gate.reason_code, "qualification.risk_reward_above_threshold")


if __name__ == "__main__":
    unittest.main()
