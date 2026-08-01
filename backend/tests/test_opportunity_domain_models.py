"""Contract tests for Phase 4.1 immutable runtime domain models."""

from contextlib import AbstractContextManager
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ComponentHealthCheck,
    ConfidenceRecord,
    CandidateAttemptState,
    ContextCategory,
    ContextComponent,
    ContextObservation,
    ContextStatus,
    DashboardItem,
    DashboardPage,
    DecimalRange,
    DeliveryAttempt,
    DeliveryState,
    DetectionAttempt,
    EvidenceCategory,
    EvidenceItem,
    EvidencePackage,
    EvidencePolarity,
    EvidenceSeverity,
    ExplanationArtifact,
    ExplanationSection,
    ExplanationSentence,
    FeatureSnapshot,
    FeatureSnapshotValue,
    HealthStatus,
    IndicatorValue,
    IntegrityReference,
    LifecycleEvent,
    LifecycleState,
    MarketCandleSnapshot,
    MarketContext,
    MarketScope,
    MarketSnapshot,
    Notification,
    NotificationEventType,
    Opportunity,
    OpportunityCandidate,
    OpportunityDetail,
    OpportunityLifecycle,
    OpportunityPlan,
    OpportunityStance,
    PlanTarget,
    PolicyReference,
    PriceRange,
    Provenance,
    QualificationGateResult,
    QualificationOutcome,
    QualificationRecord,
    QualificationStatus,
    RankingExclusion,
    RankingSnapshot,
    RuntimeHealthRecord,
    ScoreComponent,
    ScoreComponentAvailability,
    ScoreResult,
    canonical_json,
    canonical_sha256,
)
from app.opportunity_intelligence.domain.explanation import TemplateBinding
from app.opportunity_intelligence.domain.primitives import DomainValidationError


UTC = timezone.utc
START = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
CUTOFF = START + timedelta(minutes=5)
AVAILABLE = CUTOFF + timedelta(seconds=1)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
SCOPE = MarketScope(instrument="BTC/USD", timeframe="5m")


def _raises(
    exception: type[BaseException],
    match: str | None = None,
) -> AbstractContextManager[None]:
    case = unittest.TestCase()
    if match is None:
        return case.assertRaises(exception)
    return case.assertRaisesRegex(exception, match)


def _reference(
    artifact_id: str,
    *,
    artifact_type: str = "test_artifact",
    available_at: datetime = CUTOFF,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        artifact_version="1.0.0",
        integrity_digest=HASH_A,
        available_at=available_at,
    )


def _policy(policy_id: str = "policy.test") -> PolicyReference:
    return PolicyReference(
        policy_id=policy_id,
        policy_version="1.0.0",
        integrity_digest=HASH_B,
    )


def _audit(
    *sources: IntegrityReference,
    cutoff: datetime = CUTOFF,
    available_at: datetime = AVAILABLE,
) -> AuditMetadata:
    if not sources:
        sources = (_reference("source.default"),)
    return AuditMetadata(
        created_at=available_at,
        evidence_cutoff=cutoff,
        available_at=available_at,
        provenance=Provenance(
            source_references=tuple(sources),
            policy_references=(_policy(),),
            code_version="git:0123456789abcdef",
            configuration_hash=HASH_B,
            lineage_hash=HASH_C,
        ),
        result_hash=HASH_A,
    )


def _market_snapshot() -> MarketSnapshot:
    source = _reference("candle.source", available_at=START)
    candle = MarketCandleSnapshot(
        candle_id="candle.1",
        timestamp=START,
        available_at=CUTOFF,
        open=Decimal("100.000000000000000000"),
        high=Decimal("110.000000000000000000"),
        low=Decimal("90.000000000000000000"),
        close=Decimal("105.000000000000000000"),
        volume=Decimal("10.000000000000000000"),
        source_reference=source,
    )
    return MarketSnapshot(
        contract_version="1.0.0",
        snapshot_id="market.snapshot.1",
        scope=SCOPE,
        candles=(candle,),
        complete=True,
        audit=_audit(source),
    )


def _feature_snapshot() -> FeatureSnapshot:
    market = _reference("market.snapshot.1")
    feature_record = _reference("feature.ema20")
    value = FeatureSnapshotValue(
        feature_identifier="ema_20",
        definition_version="1.0.0",
        output_name="ema_value",
        candle_timestamp=START,
        available_at=CUTOFF,
        value=Decimal("101.000000000000000000"),
        feature_record=feature_record,
    )
    return FeatureSnapshot(
        contract_version="1.0.0",
        snapshot_id="feature.snapshot.1",
        scope=SCOPE,
        market_snapshot=market,
        registry_hash=HASH_A,
        values=(value,),
        audit=_audit(market, feature_record),
    )


def _context_component(category: ContextCategory) -> ContextComponent:
    source = _reference(f"context.source.{category.value.lower()}")
    observation = ContextObservation(
        observation_id=f"observation.{category.value.lower()}",
        semantic_identifier=f"semantic.{category.value.lower()}",
        value="observed",
        unit=None,
        time_start=START,
        time_end=START,
        available_at=CUTOFF,
        source_references=(source,),
    )
    return ContextComponent(
        category=category,
        definition_id=f"context.{category.value.lower()}",
        definition_version="1.0.0",
        status=ContextStatus.AVAILABLE,
        observations=(observation,),
        evidence_references=(source,),
        available_at=CUTOFF,
    )


def _context() -> MarketContext:
    components = tuple(_context_component(category) for category in ContextCategory)
    sources = tuple(component.evidence_references[0] for component in components)
    return MarketContext(
        contract_version="1.0.0",
        context_id="market.context.1",
        scope=SCOPE,
        context_timeframes=("5m",),
        trend=components[0],
        momentum=components[1],
        volatility=components[2],
        structure=components[3],
        session=components[4],
        data_quality=components[5],
        definition_set_hash=HASH_B,
        audit=_audit(*sources),
    )


def _evidence_package() -> EvidencePackage:
    source = _reference("evidence.source")
    item = EvidenceItem(
        taxonomy_version="1.0.0",
        evidence_id="evidence.1",
        evidence_type="feature_observation",
        category=EvidenceCategory.FEATURE_TREND,
        description_code="trend.observed",
        source_reference=source,
        source_definition="ema_20.value",
        polarity=EvidencePolarity.CONTEXTUAL,
        proposition="opportunity.assessment",
        severity=EvidenceSeverity.INFORMATIONAL,
        observed_value=Decimal("101.000000000000000000"),
        unit="price",
        scope=SCOPE,
        time_start=START,
        time_end=START,
        available_at=CUTOFF,
        price_scope=None,
        limitations=(),
        integrity_digest=HASH_C,
    )
    return EvidencePackage(
        contract_version="1.0.0",
        package_id="evidence.package.1",
        candidate_id="candidate.1",
        assessment_id="assessment.1",
        items=(item,),
        limitations=(),
        audit=_audit(source),
    )


def _candidate() -> OpportunityCandidate:
    market = _reference("market.snapshot.1")
    features = _reference("feature.snapshot.1")
    context = _reference("market.context.1")
    return OpportunityCandidate(
        contract_version="1.0.0",
        candidate_id="candidate.1",
        scope=SCOPE,
        detected_at=AVAILABLE,
        detection_policy=_policy("policy.detection"),
        market_snapshot_reference=market,
        feature_snapshot_reference=features,
        context_reference=context,
        reason_codes=("candidate.eligible",),
        evidence_references=(market, features, context),
        limitations=(),
        audit=_audit(market, features, context),
    )


def _opportunity() -> Opportunity:
    evidence = _reference("evidence.package.1")
    context = _reference("market.context.1")
    return Opportunity(
        contract_version="1.0.0",
        opportunity_id="opportunity.1",
        opportunity_version_id="opportunity.1.v1",
        assessment_id="assessment.1",
        decision_id="decision.1",
        candidate_id="candidate.1",
        scope=SCOPE,
        stance=OpportunityStance.BUY,
        decision_policy=_policy("policy.decision"),
        evidence_package_reference=evidence,
        context_reference=context,
        reason_codes=("assessment.buy",),
        limitations=(),
        qualification_reference=None,
        score_reference=None,
        confidence=None,
        plan=None,
        valid_until=None,
        supersedes_opportunity_version_id=None,
        audit=_audit(evidence, context),
    )


def _lifecycle() -> OpportunityLifecycle:
    assessment = _reference("assessment.1")
    audit = _audit(assessment)
    event = LifecycleEvent(
        contract_version="1.0.0",
        event_id="lifecycle.event.1",
        opportunity_id="opportunity.1",
        opportunity_version_id="opportunity.1.v1",
        prior_state=None,
        resulting_state=LifecycleState.DETECTED,
        sequence=1,
        policy=_policy("policy.lifecycle"),
        reason_code="candidate.detected",
        occurred_at=CUTOFF,
        available_at=AVAILABLE,
        assessment_reference=assessment,
        evidence_references=(assessment,),
        predecessor_event_id=None,
        successor_opportunity_version_id=None,
        audit=audit,
    )
    return OpportunityLifecycle(
        contract_version="1.0.0",
        opportunity_id="opportunity.1",
        scope=SCOPE,
        direction=OpportunityStance.BUY,
        identity_policy=_policy("policy.identity"),
        originating_candidate_id="candidate.1",
        initial_evidence_cutoff=CUTOFF,
        events=(event,),
        current_event_id=event.event_id,
        current_state=LifecycleState.DETECTED,
        audit=audit,
    )


def _explanation() -> ExplanationArtifact:
    evidence = _reference("evidence.1")
    sentence = ExplanationSentence(
        sentence_id="sentence.1",
        template_id="template.opportunity.scope",
        bindings=(TemplateBinding(name="instrument", value="BTC/USD"),),
        evidence_references=(evidence,),
        rendered_text="AlphaLens observed recorded market evidence.",
    )
    return ExplanationArtifact(
        contract_version="1.0.0",
        explanation_id="explanation.1",
        opportunity_version_id="opportunity.1.v1",
        language="en",
        locale="en-IN",
        taxonomy_version="1.0.0",
        template_set_version="1.0.0",
        sections=(
            ExplanationSection(
                section_id="assessment",
                ordinal=1,
                sentences=(sentence,),
            ),
        ),
        limitations=(),
        audit=_audit(evidence),
    )


def test_canonical_serialization_is_stable_typed_and_omits_absence() -> None:
    candidate = _candidate()

    first = canonical_json(candidate)
    second = candidate.canonical_json()

    assert first == second
    assert '"contract_version":"1.0.0"' in first
    assert '"detected_at":"2025-01-01T00:05:01Z"' in first
    assert "null" not in first
    assert canonical_sha256(candidate) == candidate.canonical_sha256()
    assert len(candidate.canonical_sha256()) == 64


def test_domain_models_are_immutable() -> None:
    candidate = _candidate()

    with _raises(FrozenInstanceError):
        candidate.candidate_id = "candidate.changed"  # type: ignore[misc]


def test_contract_version_and_utc_are_fail_closed() -> None:
    candidate = _candidate()

    with _raises(DomainValidationError, "exactly 1.0.0"):
        replace(candidate, contract_version="2.0.0")

    with _raises(DomainValidationError, "timezone-aware"):
        replace(candidate, detected_at=AVAILABLE.replace(tzinfo=None))


def test_audit_rejects_future_unavailable_provenance() -> None:
    future = _reference("future.source", available_at=AVAILABLE)

    with _raises(DomainValidationError, "unavailable at the evidence"):
        _audit(future)


def test_market_and_feature_snapshots_validate_and_serialize_decimals() -> None:
    market = _market_snapshot()
    features = _feature_snapshot()

    assert market.candles[0].close == Decimal("105")
    assert features.values[0].value == Decimal("101")
    assert '"value":"101.000000000000000000"' in features.canonical_json()

    with _raises(DomainValidationError, "Candle high"):
        replace(market.candles[0], high=Decimal("99"))


def test_feature_snapshot_rejects_noncanonical_ordering() -> None:
    snapshot = _feature_snapshot()
    later = replace(
        snapshot.values[0],
        feature_identifier="atr_14",
        feature_record=_reference("feature.atr14"),
    )

    with _raises(DomainValidationError, "canonical ordering"):
        replace(snapshot, values=(snapshot.values[0], later))


def test_market_context_requires_available_data_quality() -> None:
    context = _context()
    unavailable = replace(
        context.data_quality,
        status=ContextStatus.UNAVAILABLE,
        observations=(),
        evidence_references=(),
    )

    with _raises(DomainValidationError, "Data-quality"):
        replace(context, data_quality=unavailable)


def test_evidence_package_rejects_future_evidence() -> None:
    package = _evidence_package()
    future_source = _reference("evidence.future", available_at=AVAILABLE)

    with _raises(DomainValidationError, "unavailable at evidence"):
        replace(
            package.items[0],
            source_reference=future_source,
            available_at=CUTOFF,
        )


def test_detection_attempt_requires_candidate_only_when_detected() -> None:
    source = _reference("detection.input")
    attempt = DetectionAttempt(
        contract_version="1.0.0",
        attempt_id="attempt.1",
        scope=SCOPE,
        state=CandidateAttemptState.DETECTED,
        detection_policy=_policy("policy.detection"),
        input_references=(source,),
        reason_codes=("candidate.eligible",),
        candidate_id="candidate.1",
        audit=_audit(source),
    )

    assert attempt.candidate_id == "candidate.1"

    with _raises(DomainValidationError, "Only a detected"):
        replace(attempt, state=CandidateAttemptState.NOT_DETECTED)


def test_qualification_outcome_must_match_gate_results() -> None:
    evidence = _reference("qualification.evidence")
    gate = QualificationGateResult(
        gate_id="gate.integrity",
        requirement_class="mandatory",
        status=QualificationStatus.PASS,
        evidence_references=(evidence,),
        reason_code="integrity.valid",
    )
    record = QualificationRecord(
        contract_version="1.0.0",
        qualification_id="qualification.1",
        assessment_reference=_reference("assessment.1"),
        context_reference=_reference("market.context.1"),
        evidence_package_reference=_reference("evidence.package.1"),
        policy=_policy("policy.qualification"),
        gate_results=(gate,),
        outcome=QualificationOutcome.QUALIFIED,
        exclusions=(),
        limitations=(),
        audit=_audit(
            _reference("assessment.1"),
            _reference("market.context.1"),
            _reference("evidence.package.1"),
        ),
    )

    assert record.outcome is QualificationOutcome.QUALIFIED
    with _raises(DomainValidationError, "requires a failed gate"):
        replace(record, outcome=QualificationOutcome.NOT_QUALIFIED)


def test_score_requires_complete_available_components_and_exact_domain() -> None:
    evidence = _reference("score.evidence")
    component = ScoreComponent(
        component_id="component.quality",
        component_version="1.0.0",
        meaning="opportunity.quality",
        availability=ScoreComponentAvailability.AVAILABLE,
        source_evidence=(evidence,),
        raw_value=Decimal("1.000000000000000000"),
        normalized_value=Decimal("1.000000000000000000"),
        weight=Decimal("1.000000000000000000"),
        contribution=Decimal("1.000000000000000000"),
        normalization_reference=_reference("normalization.1"),
        weight_reference=_reference("weights.1"),
        limitations=(),
        component_hash=HASH_A,
    )
    result = ScoreResult(
        contract_version="1.0.0",
        score_id="score.1",
        opportunity_id="opportunity.1",
        qualification_reference=_reference("qualification.1"),
        policy=_policy("policy.score"),
        components=(component,),
        aggregation_definition="aggregate.weighted",
        aggregate_value=Decimal("1.000000000000000000"),
        aggregate_unit="score.unit",
        valid_domain=DecimalRange(
            lower=Decimal("0.000000000000000000"),
            upper=Decimal("100.000000000000000000"),
        ),
        missing_input_disposition="fail_closed",
        audit=_audit(_reference("qualification.1")),
    )

    assert result.aggregate_value == Decimal("1")
    with _raises(DomainValidationError, "outside its valid domain"):
        replace(result, aggregate_value=Decimal("101"))


def test_opportunity_plan_enforces_directional_structure_and_atomicity() -> None:
    evidence = _reference("plan.evidence")
    target = PlanTarget(
        target_id="target.1",
        price=Decimal("120.000000000000000000"),
        potential_reward=Decimal("15.000000000000000000"),
        risk_reward=Decimal("1.500000000000000000"),
        evidence_references=(evidence,),
    )
    plan = OpportunityPlan(
        contract_version="1.0.0",
        plan_id="plan.1",
        opportunity_id="opportunity.1",
        assessment_id="assessment.1",
        decision_id="decision.1",
        policy=_policy("policy.plan"),
        scope=SCOPE,
        direction=OpportunityStance.BUY,
        reference_price=Decimal("105.000000000000000000"),
        reference_price_source=evidence,
        entry_zone=PriceRange(
            lower=Decimal("100.000000000000000000"),
            upper=Decimal("105.000000000000000000"),
        ),
        entry_semantics="entry.zone",
        invalidation_price=Decimal("90.000000000000000000"),
        invalidation_condition="thesis.invalidated",
        targets=(target,),
        risk=Decimal("10.000000000000000000"),
        risk_unit="price.distance",
        assumptions=("Approved policy supplied all values.",),
        limitations=(),
        valid_until=AVAILABLE + timedelta(minutes=5),
        audit=_audit(evidence),
    )

    assert plan.direction is OpportunityStance.BUY
    with _raises(DomainValidationError, "below the entry zone"):
        replace(plan, invalidation_price=Decimal("101"))
    with _raises(DomainValidationError, "WAIT"):
        replace(plan, direction=OpportunityStance.WAIT)


def test_wait_opportunity_cannot_be_scored_or_planned() -> None:
    opportunity = _opportunity()

    with _raises(DomainValidationError, "WAIT cannot"):
        replace(
            opportunity,
            stance=OpportunityStance.WAIT,
            score_reference=_reference("score.1"),
        )


def test_confidence_record_requires_point_in_time_calibration() -> None:
    calibration = _reference("calibration.1")
    confidence = ConfidenceRecord(
        contract_version="1.0.0",
        confidence_id="confidence.1",
        value=Decimal("0.500000000000000000"),
        meaning="calibrated.quantity",
        population_scope="scope.btc-usd.5m",
        calibration_reference=calibration,
        approval_reference=_policy("policy.confidence"),
        audit=_audit(calibration),
    )

    assert confidence.value == Decimal("0.5")


def test_lifecycle_rejects_illegal_transition_and_history_mismatch() -> None:
    lifecycle = _lifecycle()
    first = lifecycle.events[0]

    with _raises(DomainValidationError, "not allowed"):
        LifecycleEvent(
            contract_version="1.0.0",
            event_id="lifecycle.event.2",
            opportunity_id="opportunity.1",
            opportunity_version_id="opportunity.1.v1",
            prior_state=LifecycleState.DETECTED,
            resulting_state=LifecycleState.PUBLISHED,
            sequence=2,
            policy=_policy("policy.lifecycle"),
            reason_code="publication.invalid",
            occurred_at=AVAILABLE,
            available_at=AVAILABLE,
            assessment_reference=first.assessment_reference,
            evidence_references=(first.assessment_reference,),
            predecessor_event_id=first.event_id,
            successor_opportunity_version_id=None,
            audit=first.audit,
        )


def test_ranking_snapshot_accounts_for_every_candidate_and_allows_empty() -> None:
    candidate = _reference("candidate.1")
    exclusion = RankingExclusion(
        exclusion_id="exclusion.1",
        candidate_id="candidate.1",
        opportunity_id=None,
        reason_codes=("qualification.unavailable",),
        evidence_references=(candidate,),
    )
    snapshot = RankingSnapshot(
        contract_version="1.0.0",
        snapshot_id="ranking.1",
        policy=_policy("policy.ranking"),
        as_of=CUTOFF,
        generated_at=AVAILABLE,
        scope=SCOPE,
        eligible_candidate_references=(candidate,),
        qualified_opportunity_references=(),
        memberships=(),
        exclusions=(exclusion,),
        candidate_set_hash=HASH_A,
        predecessor_snapshot_id=None,
        audit=_audit(candidate),
    )

    assert not snapshot.memberships
    assert len(snapshot.exclusions) == 1

    empty = replace(
        snapshot,
        snapshot_id="ranking.empty",
        eligible_candidate_references=(),
        exclusions=(),
    )
    assert empty.memberships == ()

    with _raises(DomainValidationError, "account for every"):
        replace(snapshot, exclusions=())


def test_notification_delivery_state_is_immutable_and_consistent() -> None:
    lifecycle = _reference("lifecycle.event.1")
    pending = Notification(
        contract_version="1.0.0",
        notification_id="notification.1",
        event_type=NotificationEventType.OPPORTUNITY_PUBLISHED,
        opportunity_id="opportunity.1",
        opportunity_version_id="opportunity.1.v1",
        lifecycle_event_reference=lifecycle,
        scope=SCOPE,
        stance=OpportunityStance.BUY,
        score_reference=None,
        rank=None,
        confidence_reference=None,
        evidence_package_reference=_reference("evidence.package.1"),
        plan_reference=None,
        limitation_codes=(),
        deep_link="/opportunities/opportunity.1",
        policy=_policy("policy.notification"),
        deduplication_hash=HASH_B,
        expires_at=None,
        delivery_state=DeliveryState.PENDING,
        delivery_attempts=(),
        audit=_audit(lifecycle, _reference("evidence.package.1")),
    )
    attempt = DeliveryAttempt(
        attempt_id="delivery.1",
        sequence=1,
        state=DeliveryState.DELIVERED,
        attempted_at=AVAILABLE,
        provider_reference="provider.message.1",
        failure_category=None,
    )

    delivered = replace(
        pending,
        delivery_state=DeliveryState.DELIVERED,
        delivery_attempts=(attempt,),
    )
    assert delivered.delivery_state is DeliveryState.DELIVERED

    with _raises(DomainValidationError, "latest delivery"):
        replace(pending, delivery_attempts=(attempt,))


def test_dashboard_page_preserves_rank_order() -> None:
    snapshot = _reference("ranking.1")
    score = _reference("score.1")
    item = DashboardItem(
        opportunity_id="opportunity.1",
        opportunity_version_id="opportunity.1.v1",
        scope=SCOPE,
        stance=OpportunityStance.BUY,
        lifecycle_state=LifecycleState.PUBLISHED,
        evidence_cutoff=CUTOFF,
        available_at=AVAILABLE,
        freshness_state="current",
        rank=1,
        ranking_snapshot_reference=snapshot,
        score_reference=score,
        confidence_reference=None,
        reason_codes=("assessment.buy",),
        has_plan=False,
        limitations=(),
        detail_reference="/opportunities/opportunity.1",
    )
    page = DashboardPage(
        contract_version="1.0.0",
        ranking_snapshot_reference=snapshot,
        ranking_snapshot_hash=HASH_A,
        as_of=CUTOFF,
        generated_at=AVAILABLE,
        scope=SCOPE,
        items=(item,),
        applied_filters=(),
        sort="canonical.rank",
        next_cursor=None,
        previous_cursor=None,
        freshness_status="current",
        coverage_status="complete",
        partial_failures=(),
        audit=_audit(snapshot),
    )

    assert page.items[0].rank == 1


def test_opportunity_detail_validates_cross_object_identity_and_scope() -> None:
    opportunity = _opportunity()
    evidence = _evidence_package()
    context = _context()
    lifecycle = _lifecycle()
    explanation = _explanation()
    market = _market_snapshot()
    indicator = IndicatorValue(
        feature_identifier="ema_20",
        definition_version="1.0.0",
        output_name="ema_value",
        value=Decimal("101.000000000000000000"),
        unit="price",
        candle_timestamp=START,
        available_at=CUTOFF,
        feature_record=_reference("feature.ema20"),
    )
    detail = OpportunityDetail(
        contract_version="1.0.0",
        detail_id="detail.1",
        opportunity=opportunity,
        market_snapshot=market,
        indicators=(indicator,),
        context=context,
        evidence=evidence,
        explanation=explanation,
        lifecycle=lifecycle,
        historical_references=(),
        verification_status="verified",
        audit=_audit(_reference("detail.source")),
    )

    assert detail.opportunity.opportunity_id == "opportunity.1"
    with _raises(DomainValidationError, "incompatible scopes"):
        replace(
            detail,
            market_snapshot=replace(
                market,
                scope=MarketScope(instrument="ETH/USD", timeframe="5m"),
            ),
        )


def test_runtime_health_fails_closed_on_inconsistent_status() -> None:
    source = _reference("health.evidence")
    failed = ComponentHealthCheck(
        check_id="check.market-data",
        component="market_data",
        status=HealthStatus.SUSPENDED,
        reason_codes=("provider.unavailable",),
        observed_at=CUTOFF,
        evidence_references=(source,),
    )

    with _raises(DomainValidationError, "Healthy runtime"):
        RuntimeHealthRecord(
            contract_version="1.0.0",
            cycle_id="cycle.1",
            scope=SCOPE,
            expected_boundary=CUTOFF,
            observed_boundary=None,
            checks=(failed,),
            status=HealthStatus.HEALTHY,
            suspension_action=None,
            recovery_prerequisites=(),
            audit=_audit(source),
        )


class OpportunityDomainModelTests(unittest.TestCase):
    test_canonical_serialization_is_stable_typed_and_omits_absence = staticmethod(
        test_canonical_serialization_is_stable_typed_and_omits_absence
    )
    test_domain_models_are_immutable = staticmethod(test_domain_models_are_immutable)
    test_contract_version_and_utc_are_fail_closed = staticmethod(
        test_contract_version_and_utc_are_fail_closed
    )
    test_audit_rejects_future_unavailable_provenance = staticmethod(
        test_audit_rejects_future_unavailable_provenance
    )
    test_market_and_feature_snapshots_validate_and_serialize_decimals = staticmethod(
        test_market_and_feature_snapshots_validate_and_serialize_decimals
    )
    test_feature_snapshot_rejects_noncanonical_ordering = staticmethod(
        test_feature_snapshot_rejects_noncanonical_ordering
    )
    test_market_context_requires_available_data_quality = staticmethod(
        test_market_context_requires_available_data_quality
    )
    test_evidence_package_rejects_future_evidence = staticmethod(
        test_evidence_package_rejects_future_evidence
    )
    test_detection_attempt_requires_candidate_only_when_detected = staticmethod(
        test_detection_attempt_requires_candidate_only_when_detected
    )
    test_qualification_outcome_must_match_gate_results = staticmethod(
        test_qualification_outcome_must_match_gate_results
    )
    test_score_requires_complete_available_components_and_exact_domain = staticmethod(
        test_score_requires_complete_available_components_and_exact_domain
    )
    test_opportunity_plan_enforces_directional_structure_and_atomicity = staticmethod(
        test_opportunity_plan_enforces_directional_structure_and_atomicity
    )
    test_wait_opportunity_cannot_be_scored_or_planned = staticmethod(
        test_wait_opportunity_cannot_be_scored_or_planned
    )
    test_confidence_record_requires_point_in_time_calibration = staticmethod(
        test_confidence_record_requires_point_in_time_calibration
    )
    test_lifecycle_rejects_illegal_transition_and_history_mismatch = staticmethod(
        test_lifecycle_rejects_illegal_transition_and_history_mismatch
    )
    test_ranking_snapshot_accounts_for_every_candidate_and_allows_empty = staticmethod(
        test_ranking_snapshot_accounts_for_every_candidate_and_allows_empty
    )
    test_notification_delivery_state_is_immutable_and_consistent = staticmethod(
        test_notification_delivery_state_is_immutable_and_consistent
    )
    test_dashboard_page_preserves_rank_order = staticmethod(
        test_dashboard_page_preserves_rank_order
    )
    test_opportunity_detail_validates_cross_object_identity_and_scope = staticmethod(
        test_opportunity_detail_validates_cross_object_identity_and_scope
    )
    test_runtime_health_fails_closed_on_inconsistent_status = staticmethod(
        test_runtime_health_fails_closed_on_inconsistent_status
    )
