"""Concrete PostgreSQL-backed runtime opportunity lifecycle service."""

from dataclasses import replace

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    IntegrityReference,
    LifecycleEvent,
    LifecycleState,
    Opportunity,
    OpportunityLifecycle,
    OpportunityStance,
    PolicyReference,
    Provenance,
    QualificationRecord,
    QualificationOutcome,
    RankingSnapshot,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import LifecycleRepository
from app.opportunity_intelligence.services import ServiceContractError


_CODE_VERSION = "alphalens.runtime.1.0.0"

_LIFECYCLE_POLICY = PolicyReference(
    "alphalens_runtime_lifecycle",
    "1.0.0",
    "0" * 64,
)


class RuntimeLifecycleService:
    """Persist immutable lifecycle history for a ranked opportunity."""

    def __init__(
        self,
        *,
        lifecycles: LifecycleRepository,
        code_version: str = _CODE_VERSION,
        policy: PolicyReference = _LIFECYCLE_POLICY,
    ) -> None:
        self._lifecycles = lifecycles
        self._code_version = code_version
        self._policy = policy

    async def advance(
        self,
        opportunity: Opportunity,
        qualification: QualificationRecord,
        ranking: RankingSnapshot,
        previous: OpportunityLifecycle | None,
    ) -> OpportunityLifecycle:
        if opportunity.stance is OpportunityStance.WAIT:
            raise ServiceContractError(
                "WAIT cannot acquire an opportunity lifecycle."
            )

        if qualification.assessment_reference.artifact_id != opportunity.opportunity_version_id:
            raise ServiceContractError(
                "Lifecycle qualification assessment does not match opportunity."
            )

        if (
            opportunity.qualification_reference is not None
            and opportunity.qualification_reference.artifact_id
            != qualification.qualification_id
        ):
            raise ServiceContractError(
                "Lifecycle qualification identity does not match opportunity."
            )

        ranking_membership = next(
            (
                item
                for item in ranking.memberships
                if item.opportunity_id == opportunity.opportunity_id
            ),
            None,
        )

        if ranking_membership is None:
            raise ServiceContractError(
                "Ranking does not contain the opportunity."
            )

        cutoff = min(
            opportunity.audit.evidence_cutoff,
            qualification.audit.evidence_cutoff,
            ranking.audit.evidence_cutoff,
        )

        ranking_ref = IntegrityReference(
            artifact_id=ranking.snapshot_id,
            artifact_type="ranking_snapshot",
            artifact_version="1.0.0",
            integrity_digest=ranking.canonical_sha256(),
            available_at=ranking.audit.available_at,
        )

        qualification_ref = IntegrityReference(
            artifact_id=qualification.qualification_id,
            artifact_type="qualification_record",
            artifact_version="1.0.0",
            integrity_digest=qualification.canonical_sha256(),
            available_at=qualification.audit.available_at,
        )

        opportunity_ref = IntegrityReference(
            artifact_id=opportunity.opportunity_version_id,
            artifact_type="opportunity",
            artifact_version="1.0.0",
            integrity_digest=opportunity.canonical_sha256(),
            available_at=opportunity.audit.available_at,
        )

        evidence_refs = (
            opportunity.evidence_package_reference,
            opportunity_ref,
            qualification_ref,
            ranking_ref,
        )

        source_refs = (
            opportunity_ref,
            qualification_ref,
            ranking_ref,
        )

        def audit_for(
            refs: tuple[IntegrityReference, ...],
            available_at,
        ) -> AuditMetadata:
            audit = AuditMetadata(
                created_at=available_at,
                evidence_cutoff=cutoff,
                available_at=available_at,
                provenance=Provenance(
                    source_references=source_refs,
                    policy_references=(self._policy,),
                    code_version=self._code_version,
                    configuration_hash=self._policy.integrity_digest,
                    lineage_hash=canonical_sha256(source_refs),
                ),
                result_hash="0" * 64,
            )
            return audit

        def make_event(
            *,
            sequence: int,
            prior_state: LifecycleState | None,
            resulting_state: LifecycleState,
            reason_code: str,
            predecessor_event_id: str | None,
            refs: tuple[IntegrityReference, ...],
            available_at,
        ) -> LifecycleEvent:
            audit = audit_for(refs, available_at)

            event = LifecycleEvent(
                contract_version="1.0.0",
                event_id=(
                    f"lifecycle.event."
                    f"{opportunity.opportunity_id}."
                    f"{sequence}"
                ),
                opportunity_id=opportunity.opportunity_id,
                opportunity_version_id=opportunity.opportunity_version_id,
                prior_state=prior_state,
                resulting_state=resulting_state,
                sequence=sequence,
                policy=self._policy,
                reason_code=reason_code,
                occurred_at=available_at,
                available_at=available_at,
                assessment_reference=opportunity_ref,
                evidence_references=refs,
                predecessor_event_id=predecessor_event_id,
                successor_opportunity_version_id=None,
                audit=audit,
            )

            return replace(
                event,
                audit=replace(
                    audit,
                    result_hash=canonical_sha256(
                        event,
                        exclude=frozenset({"result_hash"}),
                    ),
                ),
            )

        # A new opportunity has already traversed detection, qualification
        # and ranking before this service is called. Represent that history
        # explicitly instead of leaving the production lifecycle at DETECTED.
        if previous is None:
            events = [
                make_event(
                    sequence=1,
                    prior_state=None,
                    resulting_state=LifecycleState.DETECTED,
                    reason_code="candidate.detected",
                    predecessor_event_id=None,
                    refs=(opportunity_ref,),
                    available_at=opportunity.audit.available_at,
                )
            ]
        else:
            if previous.opportunity_id != opportunity.opportunity_id:
                raise ServiceContractError(
                    "Previous lifecycle belongs to another opportunity."
                )

            if previous.current_event_id == "":
                raise ServiceContractError(
                    "Previous lifecycle has no current event."
                )

            events = list(previous.events)

        if qualification.outcome is not QualificationOutcome.QUALIFIED:
            # The pipeline should normally not invoke lifecycle for a
            # non-qualified opportunity. Fail closed rather than publishing it.
            raise ServiceContractError(
                "Lifecycle requires a QUALIFIED opportunity."
            )

        if events[-1].resulting_state is LifecycleState.DETECTED:
            events.append(
                make_event(
                    sequence=len(events) + 1,
                    prior_state=LifecycleState.DETECTED,
                    resulting_state=LifecycleState.QUALIFIED,
                    reason_code="qualification.passed",
                    predecessor_event_id=events[-1].event_id,
                    refs=(opportunity_ref, qualification_ref),
                    available_at=qualification.audit.available_at,
                )
            )

        if events[-1].resulting_state is LifecycleState.QUALIFIED:
            events.append(
                make_event(
                    sequence=len(events) + 1,
                    prior_state=LifecycleState.QUALIFIED,
                    resulting_state=LifecycleState.RANKED,
                    reason_code="ranking.completed",
                    predecessor_event_id=events[-1].event_id,
                    refs=(
                        opportunity_ref,
                        qualification_ref,
                        ranking_ref,
                    ),
                    available_at=ranking.audit.available_at,
                )
            )

        if events[-1].resulting_state is not LifecycleState.RANKED:
            raise ServiceContractError(
                "Lifecycle cannot advance to an approved ranked state."
            )

        final_events = tuple(events)

        lifecycle_audit = audit_for(
            evidence_refs,
            final_events[-1].available_at,
        )

        provisional = OpportunityLifecycle(
            contract_version="1.0.0",
            opportunity_id=opportunity.opportunity_id,
            scope=opportunity.scope,
            direction=opportunity.stance,
            identity_policy=self._policy,
            originating_candidate_id=opportunity.candidate_id,
            initial_evidence_cutoff=final_events[0].audit.evidence_cutoff,
            events=final_events,
            current_event_id=final_events[-1].event_id,
            current_state=final_events[-1].resulting_state,
            audit=lifecycle_audit,
        )

        lifecycle = replace(
            provisional,
            audit=replace(
                lifecycle_audit,
                result_hash=canonical_sha256(
                    provisional,
                    exclude=frozenset({"result_hash"}),
                ),
            ),
        )

        # Persist lifecycle events through the append-only repository.
        await self._lifecycles.save_event_batch(final_events)

        # Persist the reconstructed OpportunityLifecycle so that
        # LifecycleRepository.get_current() can retrieve it.
        await self._lifecycles.save(lifecycle)

        return lifecycle
