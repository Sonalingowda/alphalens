"""Focused tests for the policy-agnostic execution runtime."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import unittest

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    ContextCategory,
    ContextComponent,
    ContextObservation,
    ContextStatus,
    FeatureSnapshot,
    FeatureSnapshotValue,
    IntegrityReference,
    MarketCandleSnapshot,
    MarketContext,
    MarketScope,
    MarketSnapshot,
    Provenance,
)
from app.opportunity_intelligence.domain.primitives import DomainValidationError
from app.policy_runtime import (
    DecisionSandbox,
    DecisionState,
    ExecutionMode,
    ImmutablePolicyArtifactStore,
    InMemoryPolicyAuditTrail,
    PolicyAuthorMetadata,
    PolicyCategory,
    PolicyEvaluation,
    PolicyExecutionRequest,
    PolicyExecutionRuntime,
    PolicyHashMismatchError,
    PolicyInput,
    PolicyIntermediateState,
    PolicyLoader,
    PolicyOutputField,
    PolicyRegistration,
    PolicyRegistry,
    PolicyReplayEngine,
    PolicySelector,
    PolicyStatus,
    PolicyVersionManager,
    ResearchMode,
    ShadowMode,
)


UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
CUTOFF = START + timedelta(minutes=5)
AVAILABLE = CUTOFF + timedelta(seconds=1)
HASH_A = "a" * 64
HASH_B = "b" * 64
SCOPE = MarketScope("BTCUSDT", "5m")


class StaticExecutable:
    def __init__(self, evaluation: PolicyEvaluation) -> None:
        self._evaluation = evaluation

    async def evaluate(self, inputs: PolicyInput) -> PolicyEvaluation:
        del inputs
        return self._evaluation


class ArtifactAdapterFactory:
    def __init__(self, evaluations: dict[bytes, PolicyEvaluation]) -> None:
        self._evaluations = evaluations

    def build(
        self,
        registration: PolicyRegistration,
        artifact: bytes,
    ) -> StaticExecutable:
        del registration
        return StaticExecutable(self._evaluations[artifact])


class IncrementingTimer:
    def __init__(self) -> None:
        self._value = 0

    def __call__(self) -> int:
        value = self._value
        self._value += 1_000
        return value


class PolicyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.registry = PolicyRegistry()
        self.artifacts = ImmutablePolicyArtifactStore()
        self.audit = InMemoryPolicyAuditTrail()
        self.approved_artifact = b"approved-policy-artifact"
        self.candidate_artifact = b"candidate-policy-artifact"
        self.evidence = _reference("evidence.policy")
        state_fields = (PolicyOutputField("stage", "evaluated"),)
        self.approved_evaluation = PolicyEvaluation(
            state=DecisionState.DECISION,
            decision_code="policy.result.available",
            output_fields=(PolicyOutputField("result", "available"),),
            evidence_references=(self.evidence,),
            intermediate_states=(
                PolicyIntermediateState(
                    state_id="state.validation",
                    sequence=1,
                    fields=state_fields,
                    state_hash=_hash_fields(state_fields),
                ),
            ),
        )
        self.candidate_evaluation = PolicyEvaluation(
            state=DecisionState.DECISION,
            decision_code="policy.result.alternative",
            output_fields=(PolicyOutputField("result", "alternative"),),
            evidence_references=(_reference("evidence.candidate"),),
        )
        self.approved = _registration(
            "policy.detection",
            "1.0.0",
            PolicyStatus.APPROVED,
            self.approved_artifact,
        )
        self.candidate = _registration(
            "policy.detection",
            "2.0.0",
            PolicyStatus.RESEARCH,
            self.candidate_artifact,
        )
        await self.registry.register(self.approved)
        await self.registry.register(self.candidate)
        await self.artifacts.add(
            PolicySelector("policy.detection", "1.0.0"),
            self.approved_artifact,
        )
        await self.artifacts.add(
            PolicySelector("policy.detection", "2.0.0"),
            self.candidate_artifact,
        )
        factory = ArtifactAdapterFactory(
            {
                self.approved_artifact: self.approved_evaluation,
                self.candidate_artifact: self.candidate_evaluation,
            }
        )
        versions = PolicyVersionManager(self.registry)
        self.loader = PolicyLoader(
            version_manager=versions,
            artifact_store=self.artifacts,
            adapter_factory=factory,
        )
        self.runtime = PolicyExecutionRuntime(
            loader=self.loader,
            audit_trail=self.audit,
            clock=lambda: AVAILABLE,
            timer=IncrementingTimer(),
        )
        self.sandbox = DecisionSandbox(self.runtime)
        self.inputs = _inputs()

    async def test_registry_is_immutable_and_versions_are_semantically_ordered(
        self,
    ) -> None:
        versions = await self.registry.versions("policy.detection")
        duplicate = await self.registry.register(self.approved)

        self.assertEqual(
            tuple(item.policy_version for item in versions),
            ("2.0.0", "1.0.0"),
        )
        self.assertIs(duplicate, self.approved)
        with self.assertRaises(FrozenInstanceError):
            self.approved.status = PolicyStatus.DEPRECATED  # type: ignore[misc]

    async def test_version_manager_switches_only_to_explicit_versions(self) -> None:
        versions = PolicyVersionManager(self.registry)
        selected = await versions.resolve(
            PolicySelector("policy.detection", "2.0.0"),
            as_of=AVAILABLE,
            allowed_statuses=frozenset({PolicyStatus.RESEARCH}),
        )
        latest = await versions.latest_approved(
            "policy.detection",
            as_of=AVAILABLE,
        )

        self.assertEqual(selected.policy_version, "2.0.0")
        self.assertEqual(latest.policy_version, "1.0.0")

    async def test_production_execution_is_deterministic_and_audited(self) -> None:
        first = await self.runtime.execute(self._request("execution.1"))
        second = await self.runtime.execute(self._request("execution.2"))
        ledgers = await self.audit.snapshot()
        verification = await self.audit.verify()

        self.assertEqual(first.evaluation, second.evaluation)
        self.assertEqual(first.record.output_hash, second.record.output_hash)
        self.assertEqual(first.record.replay_hash, second.record.replay_hash)
        self.assertEqual(first.record.input_hash, self.inputs.input_hash)
        self.assertEqual(len(ledgers.executions), 2)
        self.assertEqual(len(ledgers.decisions), 2)
        self.assertEqual(len(ledgers.evidence), 2)
        self.assertEqual(len(ledgers.research), 0)
        self.assertTrue(verification.valid)
        self.assertEqual(verification.execution_count, 2)
        self.assertEqual(len(verification.ledger_hash), 64)

    async def test_research_mode_records_states_and_cannot_publish(self) -> None:
        mode = ResearchMode(self.sandbox)
        result = await mode.execute(
            self._request(
                "research.1",
                version="2.0.0",
                mode=ExecutionMode.PRODUCTION,
            )
        )
        ledgers = await self.audit.snapshot()

        self.assertEqual(result.record.mode, ExecutionMode.RESEARCH)
        self.assertEqual(len(ledgers.research), 1)
        self.assertFalse(ledgers.research[0].publication_allowed)
        self.assertFalse(ledgers.research[0].notification_allowed)
        self.assertEqual(
            ledgers.research[0].intermediate_states,
            self.candidate_evaluation.intermediate_states,
        )

    async def test_shadow_mode_hides_candidate_output_and_records_difference(
        self,
    ) -> None:
        shadow = ShadowMode(runtime=self.runtime, sandbox=self.sandbox)
        result = await shadow.execute(
            production_request=self._request("shadow.production"),
            candidate_selector=PolicySelector("policy.detection", "2.0.0"),
            candidate_execution_id="shadow.candidate",
        )
        ledgers = await self.audit.snapshot()

        self.assertEqual(
            result.production_result.evaluation.decision_code,
            "policy.result.available",
        )
        self.assertTrue(result.comparison.decision_differs)
        self.assertTrue(result.comparison.output_differs)
        self.assertTrue(result.comparison.evidence_differs)
        self.assertFalse(hasattr(result, "candidate_result"))
        self.assertEqual(len(ledgers.executions), 2)

    async def test_replay_produces_identical_policy_output_and_hash(self) -> None:
        original = await self.runtime.execute(self._request("original.1"))
        replay = await PolicyReplayEngine(self.sandbox).replay(
            original=original,
            request=self._request("replay.1"),
        )

        self.assertTrue(replay.identical)
        self.assertEqual(replay.reason_codes, ())
        self.assertEqual(
            replay.replay_result.record.replay_hash,
            original.record.replay_hash,
        )

    async def test_missing_deprecated_unsupported_and_draft_fail_closed(self) -> None:
        deprecated_artifact = b"deprecated"
        draft_artifact = b"draft"
        for registration, artifact in (
            (
                _registration(
                    "policy.deprecated",
                    "1.0.0",
                    PolicyStatus.DEPRECATED,
                    deprecated_artifact,
                ),
                deprecated_artifact,
            ),
            (
                _registration(
                    "policy.draft",
                    "1.0.0",
                    PolicyStatus.DRAFT,
                    draft_artifact,
                ),
                draft_artifact,
            ),
        ):
            await self.registry.register(registration)
            await self.artifacts.add(
                PolicySelector(
                    registration.policy_id,
                    registration.policy_version,
                ),
                artifact,
            )
        cases = (
            ("policy.missing", "1.0.0", "policy.missing"),
            ("policy.detection", "9.0.0", "policy.version_unsupported"),
            ("policy.deprecated", "1.0.0", "policy.deprecated"),
            ("policy.draft", "1.0.0", "policy.invalid"),
        )
        for index, (policy_id, version, reason) in enumerate(cases, start=1):
            result = await self.runtime.execute(
                PolicyExecutionRequest(
                    execution_id=f"failed.{index}",
                    selector=PolicySelector(policy_id, version),
                    mode=ExecutionMode.PRODUCTION,
                    inputs=self.inputs,
                )
            )
            self.assertEqual(result.evaluation.state, DecisionState.NO_DECISION)
            self.assertEqual(result.evaluation.decision_code, "NO_DECISION")
            self.assertEqual(result.evaluation.reason_codes, (reason,))

    async def test_hash_mismatch_is_rejected_before_adapter_execution(self) -> None:
        registration = _registration(
            "policy.mismatch",
            "1.0.0",
            PolicyStatus.APPROVED,
            b"registered",
        )
        await self.registry.register(registration)
        await self.artifacts.add(
            PolicySelector("policy.mismatch", "1.0.0"),
            b"different",
        )

        with self.assertRaises(PolicyHashMismatchError):
            await self.loader.load(
                PolicySelector("policy.mismatch", "1.0.0"),
                as_of=AVAILABLE,
                allowed_statuses=frozenset({PolicyStatus.APPROVED}),
            )
        result = await self.runtime.execute(
            PolicyExecutionRequest(
                execution_id="mismatch.1",
                selector=PolicySelector("policy.mismatch", "1.0.0"),
                mode=ExecutionMode.PRODUCTION,
                inputs=self.inputs,
            )
        )
        self.assertEqual(result.evaluation.reason_codes, ("policy.hash_mismatch",))

    async def test_sandbox_rejects_production_mode(self) -> None:
        with self.assertRaisesRegex(Exception, "cannot execute"):
            await self.sandbox.execute(self._request("sandbox.production"))

    def test_input_rejects_future_unavailable_snapshot(self) -> None:
        with self.assertRaisesRegex(DomainValidationError, "unavailable"):
            PolicyInput(
                market_snapshot=self.inputs.market_snapshot,
                feature_snapshot=self.inputs.feature_snapshot,
                market_context=self.inputs.market_context,
                as_of=CUTOFF,
            )

    def _request(
        self,
        execution_id: str,
        *,
        version: str = "1.0.0",
        mode: ExecutionMode = ExecutionMode.PRODUCTION,
    ) -> PolicyExecutionRequest:
        return PolicyExecutionRequest(
            execution_id=execution_id,
            selector=PolicySelector("policy.detection", version),
            mode=mode,
            inputs=self.inputs,
        )


def _registration(
    policy_id: str,
    version: str,
    status: PolicyStatus,
    artifact: bytes,
) -> PolicyRegistration:
    return PolicyRegistration(
        contract_version="1.0.0",
        policy_id=policy_id,
        policy_version=version,
        category=PolicyCategory.DETECTION,
        status=status,
        artifact_hash=sha256(artifact).hexdigest(),
        provenance=_provenance(),
        dependencies=(),
        activation_date=START,
        author=PolicyAuthorMetadata(
            author_id="research.team",
            author_name="AlphaLens Research",
            creation_source="research.governance",
        ),
    )


def _inputs() -> PolicyInput:
    market_source = _reference("source.market", available_at=START)
    market = MarketSnapshot(
        contract_version="1.0.0",
        snapshot_id="market.snapshot.1",
        scope=SCOPE,
        candles=(
            MarketCandleSnapshot(
                candle_id="candle.1",
                timestamp=START,
                available_at=CUTOFF,
                open=Decimal("100.000000000000000000"),
                high=Decimal("110.000000000000000000"),
                low=Decimal("90.000000000000000000"),
                close=Decimal("105.000000000000000000"),
                volume=Decimal("10.000000000000000000"),
                source_reference=market_source,
            ),
        ),
        complete=True,
        audit=_audit(market_source),
    )
    market_reference = _reference("market.snapshot.1")
    feature_reference = _reference("feature.ema")
    features = FeatureSnapshot(
        contract_version="1.0.0",
        snapshot_id="feature.snapshot.1",
        scope=SCOPE,
        market_snapshot=market_reference,
        registry_hash=HASH_A,
        values=(
            FeatureSnapshotValue(
                feature_identifier="ema_20",
                definition_version="1.0.0",
                output_name="ema_value",
                candle_timestamp=START,
                available_at=CUTOFF,
                value=Decimal("101.000000000000000000"),
                feature_record=feature_reference,
            ),
        ),
        audit=_audit(market_reference, feature_reference),
    )
    components = tuple(_context_component(category) for category in ContextCategory)
    context = MarketContext(
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
        audit=_audit(*(item.evidence_references[0] for item in components)),
    )
    return PolicyInput(market, features, context, AVAILABLE)


def _context_component(category: ContextCategory) -> ContextComponent:
    source = _reference(f"source.context.{category.value.lower()}")
    observation = ContextObservation(
        observation_id=f"observation.{category.value.lower()}",
        semantic_identifier=f"context.{category.value.lower()}",
        value="available",
        unit=None,
        time_start=START,
        time_end=CUTOFF,
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


def _reference(
    artifact_id: str,
    *,
    available_at: datetime = CUTOFF,
) -> IntegrityReference:
    return IntegrityReference(
        artifact_id=artifact_id,
        artifact_type="test.artifact",
        artifact_version="1.0.0",
        integrity_digest=HASH_A,
        available_at=available_at,
    )


def _provenance(*sources: IntegrityReference) -> Provenance:
    return Provenance(
        source_references=sources or (_reference("source.policy"),),
        policy_references=(),
        code_version="git:policy-runtime",
        configuration_hash=HASH_A,
        lineage_hash=HASH_B,
    )


def _audit(*sources: IntegrityReference) -> AuditMetadata:
    return AuditMetadata(
        created_at=AVAILABLE,
        evidence_cutoff=CUTOFF,
        available_at=AVAILABLE,
        provenance=_provenance(*sources),
        result_hash=HASH_A,
    )


def _hash_fields(fields: tuple[PolicyOutputField, ...]) -> str:
    from app.opportunity_intelligence.domain import canonical_sha256

    return canonical_sha256(fields)


if __name__ == "__main__":
    unittest.main()
