"""Runtime Notification Service.

Governed by ALPHALENS_MVP_RUNTIME_CONTRACT_V1 §2.8 (NOTIFICATION stage).

This service converts a persisted RankingSnapshot and its associated
Opportunity and OpportunityLifecycle objects into one immutable Notification
intent per ranked member, and persists them through NotificationRepository.

Design constraints:
- Consumes only persisted RankingSnapshot and Opportunity artifacts
  (verified by canonical digest round-trip before construction).
- Produces one Notification per ranked member; zero notifications for an
  empty ranking (valid successful outcome — not an error).
- Each Notification is built atomically and persisted via a single save call
  before proceeding to the next member.
- Idempotent: byte-identical inputs produce byte-identical notifications;
  the repository enforces immutability on conflict.
- Fail-closed: any missing or mismatched required artifact raises the
  appropriate service error and prevents persistence.
- No market analysis, scoring, qualification, or evidence generation is
  performed here.  All values are projected directly from persisted inputs.
"""

from dataclasses import replace

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    DeliveryState,
    IntegrityReference,
    Notification,
    NotificationEventType,
    Opportunity,
    OpportunityLifecycle,
    PolicyReference,
    Provenance,
    RankingSnapshot,
    canonical_sha256,
)
from app.opportunity_intelligence.repositories import (
    EntityId,
    EntityNotFoundError,
    NotificationRepository,
    OpportunityRepository,
    RankingRepository,
)
from app.opportunity_intelligence.services import (
    ServiceContractError,
    ServiceUnavailableError,
)


# ---------------------------------------------------------------------------
# Contract anchor
# ---------------------------------------------------------------------------

_RUNTIME_CONTRACT = PolicyReference(
    "alphalens_mvp_runtime_contract",
    "1.0.0",
    "0" * 64,
)

_DEEP_LINK_PREFIX = "/opportunities/"
_CONTRACT_VERSION = "1.0.0"


class RuntimeNotificationService:
    """Create and persist immutable Notification intents for ranked opportunities.

    Implements the Notification stage of the MVP
    OpportunityIntelligencePipeline.  Returns one Notification per ranked
    member in the supplied RankingSnapshot; returns an empty tuple when the
    snapshot has no members.
    """

    def __init__(
        self,
        *,
        rankings: RankingRepository,
        opportunities: OpportunityRepository,
        notifications: NotificationRepository,
        code_version: str,
    ) -> None:
        if not code_version.strip():
            raise ValueError("Runtime notification code version must be non-empty.")
        self._rankings = rankings
        self._opportunities = opportunities
        self._notifications = notifications
        self._code_version = code_version

    async def create_intents(
        self,
        ranking: RankingSnapshot,
        opportunities: tuple[Opportunity, ...],
        lifecycles: tuple[OpportunityLifecycle, ...],
    ) -> tuple[Notification, ...]:
        """Verify persisted inputs and persist one Notification per ranked member.

        Parameters match the NotificationService protocol and the pipeline
        call: notifications.create_intents(ranking, (opportunity,), (lifecycle,))

        Returns an empty tuple when the RankingSnapshot has no members.
        """
        # --- Verify the RankingSnapshot is persisted ---
        try:
            persisted_ranking = await self._rankings.get_by_id(
                EntityId(ranking.snapshot_id)
            )
        except EntityNotFoundError as error:
            raise ServiceUnavailableError(
                "Notification: RankingSnapshot is not persisted."
            ) from error

        if persisted_ranking.canonical_sha256() != ranking.canonical_sha256():
            raise ServiceContractError(
                "Notification: persisted RankingSnapshot conflicts with pipeline input."
            )

        # Empty ranking → valid empty result
        if not persisted_ranking.memberships:
            return ()

        # --- Index opportunities and lifecycles by opportunity_id ---
        opp_index: dict[str, Opportunity] = {
            o.opportunity_id: o for o in opportunities
        }
        lc_index: dict[str, OpportunityLifecycle] = {
            lc.opportunity_id: lc for lc in lifecycles
        }

        results: list[Notification] = []

        for membership in persisted_ranking.memberships:
            opp = opp_index.get(membership.opportunity_id)
            lc = lc_index.get(membership.opportunity_id)

            if opp is None:
                raise ServiceUnavailableError(
                    f"Notification: opportunity {membership.opportunity_id!r} "
                    "not supplied for ranked member."
                )
            if lc is None:
                raise ServiceUnavailableError(
                    f"Notification: lifecycle {membership.opportunity_id!r} "
                    "not supplied for ranked member."
                )

            # --- Verify opportunity is persisted ---
            try:
                persisted_opp = await self._opportunities.get_by_id(
                    EntityId(opp.opportunity_version_id)
                )
            except EntityNotFoundError as error:
                raise ServiceUnavailableError(
                    f"Notification: Opportunity {opp.opportunity_version_id!r} "
                    "is not persisted."
                ) from error

            if persisted_opp.canonical_sha256() != opp.canonical_sha256():
                raise ServiceContractError(
                    "Notification: persisted Opportunity conflicts with pipeline input."
                )

            notification = _build(
                persisted_ranking,
                persisted_opp,
                lc,
                membership.rank,
                membership.score_reference,
                self._code_version,
            )
            results.append(await self._notifications.save(notification))

        return tuple(results)


# ---------------------------------------------------------------------------
# Notification builder
# ---------------------------------------------------------------------------

def _build(
    ranking: RankingSnapshot,
    opportunity: Opportunity,
    lifecycle: OpportunityLifecycle,
    rank: int,
    score_reference: IntegrityReference,
    code_version: str,
) -> Notification:
    """Construct one fully validated immutable Notification from persisted data."""
    cutoff = ranking.audit.evidence_cutoff

    # Lifecycle event reference — use the current event of the lifecycle
    lc_event_ref = IntegrityReference(
        artifact_id=lifecycle.current_event_id,
        artifact_type="lifecycle_event",
        artifact_version="1.0.0",
        integrity_digest=lifecycle.canonical_sha256(),
        available_at=lifecycle.audit.available_at,
    )

    # Notification identity: one per opportunity version per ranking snapshot
    notification_id = (
        f"notification.runtime.{opportunity.opportunity_version_id}"
        f".{ranking.snapshot_id}"
    )

    # Deduplication hash: deterministic from the three anchors
    deduplication_hash = canonical_sha256(
        {
            "notification_id": notification_id,
            "opportunity_version_id": opportunity.opportunity_version_id,
            "ranking_snapshot_id": ranking.snapshot_id,
        }
    )

    # Provenance: ranking snapshot is the primary source
    ranking_ref = IntegrityReference(
        artifact_id=ranking.snapshot_id,
        artifact_type="ranking_snapshot",
        artifact_version="1.0.0",
        integrity_digest=ranking.canonical_sha256(),
        available_at=ranking.audit.available_at,
    )
    opp_ref = IntegrityReference(
        artifact_id=opportunity.opportunity_version_id,
        artifact_type="opportunity",
        artifact_version="1.0.0",
        integrity_digest=opportunity.canonical_sha256(),
        available_at=opportunity.audit.available_at,
    )
    source_refs = (ranking_ref, opp_ref)

    audit = AuditMetadata(
        created_at=cutoff,
        evidence_cutoff=cutoff,
        available_at=cutoff,
        provenance=Provenance(
            source_references=source_refs,
            policy_references=(_RUNTIME_CONTRACT,),
            code_version=code_version,
            configuration_hash=_RUNTIME_CONTRACT.integrity_digest,
            lineage_hash=canonical_sha256(source_refs),
        ),
        result_hash="0" * 64,
    )

    notification = Notification(
        contract_version=_CONTRACT_VERSION,
        notification_id=notification_id,
        event_type=NotificationEventType.OPPORTUNITY_PUBLISHED,
        opportunity_id=opportunity.opportunity_id,
        opportunity_version_id=opportunity.opportunity_version_id,
        lifecycle_event_reference=lc_event_ref,
        scope=opportunity.scope,
        stance=opportunity.stance,
        score_reference=score_reference,
        rank=rank,
        confidence_reference=None,
        evidence_package_reference=opportunity.evidence_package_reference,
        plan_reference=None,
        limitation_codes=tuple(opportunity.limitations),
        deep_link=f"{_DEEP_LINK_PREFIX}{opportunity.opportunity_id}",
        policy=_RUNTIME_CONTRACT,
        deduplication_hash=deduplication_hash,
        expires_at=None,
        delivery_state=DeliveryState.PENDING,
        delivery_attempts=(),
        audit=audit,
    )

    result_hash = canonical_sha256(notification, exclude=frozenset({"result_hash"}))
    return replace(
        notification,
        audit=replace(audit, result_hash=result_hash),
    )
