"""V2 opportunity outcome resolution service.

Resolves a terminal market outcome for one V2 opportunity using only
post-signal candles.  The resolution logic is deterministic: the first
candle that touches either barrier determines the outcome.
"""

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol

from app.opportunity_intelligence.domain import (
    AuditMetadata,
    IntegrityReference,
    OpportunityOutcome,
    OpportunityPlan,
    OutcomeRecord,
    PolicyReference,
    Provenance,
    canonical_sha256,
)


_CODE_VERSION = "alphalens.outcome_resolution.1.0.0"

_OUTCOME_POLICY = PolicyReference(
    "alphalens_outcome_resolution",
    "1.0.0",
    "0" * 64,
)


class CandleQuery(Protocol):
    """Protocol for fetching post-signal candles."""

    async def query(
        self,
        instrument: str,
        timeframe: str,
        after: datetime,
        up_to_and_including: datetime,
    ) -> tuple[dict, ...]:
        """Return candles with keys: timestamp, open, high, low, close, volume."""
        ...


class OpportunityOutcomeError(Exception):
    """Raised when outcome resolution fails due to missing data or invalid state."""


def _determine_outcome(
    direction: str,
    reference_price: Decimal,
    entry_zone_lower: Decimal,
    entry_zone_upper: Decimal,
    invalidation_price: Decimal,
    target_price: Decimal,
    signal_timestamp: datetime,
    valid_until: datetime,
    candles: tuple[dict, ...],
) -> tuple[
    OpportunityOutcome,
    int,
    Decimal | None,
    datetime | None,
    int | None,
    str | None,
]:
    """Walk candles chronologically and return the first-touch outcome.

    Returns:
        (outcome, candles_evaluated, first_touch_price, first_touch_timestamp,
         first_touch_candle_index, exclusion_reason)
    """
    is_buy = direction.upper() == "BUY"

    for idx, candle in enumerate(candles):
        candle_ts = candle["timestamp"]
        candle_high = candle["high"]
        candle_low = candle["low"]

        if candle_high is None or candle_low is None:
            continue

        if is_buy:
            stop_touched = candle_low <= invalidation_price
            target_touched = candle_high >= target_price
        else:
            stop_touched = candle_high >= invalidation_price
            target_touched = candle_low <= target_price

        if stop_touched and target_touched:
            return (
                OpportunityOutcome.UNRESOLVED,
                idx + 1,
                reference_price,
                candle_ts,
                idx,
                None,
            )

        if stop_touched:
            return (
                OpportunityOutcome.STOP_HIT,
                idx + 1,
                invalidation_price,
                candle_ts,
                idx,
                None,
            )

        if target_touched:
            return (
                OpportunityOutcome.TARGET_HIT,
                idx + 1,
                target_price,
                candle_ts,
                idx,
                None,
            )

    return (
        OpportunityOutcome.EXPIRED,
        len(candles),
        None,
        None,
        None,
        None,
    )


class OutcomeResolutionService:
    """Resolve a terminal market outcome for one V2 opportunity."""

    def __init__(
        self,
        *,
        candle_query: CandleQuery,
        code_version: str = _CODE_VERSION,
        policy: PolicyReference = _OUTCOME_POLICY,
    ) -> None:
        self._candle_query = candle_query
        self._code_version = code_version
        self._policy = policy

    async def resolve(
        self,
        *,
        opportunity_id: str,
        opportunity_version_id: str,
        direction: str,
        signal_timestamp: datetime,
        evidence_cutoff: datetime,
        plan: OpportunityPlan,
        source_integrity_digest: str = "0" * 64,
        source_contract_version: str = "1.0.0",
    ) -> OutcomeRecord:
        """Resolve the outcome for one V2 opportunity.

        The resolution uses ONLY candles after the signal timestamp and up to
        valid_until.  No future information is used.
        """
        if plan.valid_until is None:
            raise OpportunityOutcomeError("Cannot resolve outcome for plan without valid_until.")
        if plan.targets is None or len(plan.targets) == 0:
            raise OpportunityOutcomeError("Cannot resolve outcome for plan without targets.")

        target_price = plan.targets[0].price
        valid_until = plan.valid_until

        candles_raw = await self._candle_query.query(
            instrument=plan.scope.instrument,
            timeframe=plan.scope.timeframe,
            after=signal_timestamp,
            up_to_and_including=valid_until,
        )

        outcome, candles_evaluated, first_touch_price, first_touch_timestamp, first_touch_candle_index, exclusion_reason = _determine_outcome(
            direction=direction,
            reference_price=plan.reference_price,
            entry_zone_lower=plan.entry_zone.lower,
            entry_zone_upper=plan.entry_zone.upper,
            invalidation_price=plan.invalidation_price,
            target_price=target_price,
            signal_timestamp=signal_timestamp,
            valid_until=valid_until,
            candles=tuple(candles_raw),
        )

        resolved_at = max(datetime.now(timezone.utc), valid_until)

        source_refs = (
            IntegrityReference(
                artifact_id=opportunity_version_id,
                artifact_type="opportunity_version",
                artifact_version=source_contract_version,
                integrity_digest=source_integrity_digest,
                available_at=signal_timestamp,
            ),
        )

        audit = AuditMetadata(
            created_at=resolved_at,
            evidence_cutoff=evidence_cutoff,
            available_at=resolved_at,
            provenance=Provenance(
                source_references=source_refs,
                policy_references=(self._policy,),
                code_version=self._code_version,
                configuration_hash=self._policy.integrity_digest,
                lineage_hash=canonical_sha256(source_refs),
            ),
            result_hash="0" * 64,
        )

        outcome_record = OutcomeRecord(
            contract_version="2.0.0",
            outcome_id=f"outcome.{opportunity_id}.v1",
            opportunity_id=opportunity_id,
            opportunity_version_id=opportunity_version_id,
            lifecycle_id=opportunity_id,
            outcome=outcome,
            direction=direction,
            reference_price=plan.reference_price,
            entry_zone_lower=plan.entry_zone.lower,
            entry_zone_upper=plan.entry_zone.upper,
            invalidation_price=plan.invalidation_price,
            target_price=target_price,
            signal_timestamp=signal_timestamp,
            outcome_interval_start=signal_timestamp,
            outcome_interval_end=valid_until,
            resolved_at=resolved_at,
            candles_evaluated=candles_evaluated,
            first_touch_price=first_touch_price,
            first_touch_timestamp=first_touch_timestamp,
            first_touch_candle_index=first_touch_candle_index,
            exclusion_reason=exclusion_reason,
            policy=self._policy,
            evidence_references=source_refs,
            audit=audit,
        )

        return replace(
            outcome_record,
            audit=replace(
                audit,
                result_hash=canonical_sha256(
                    outcome_record,
                    exclude=frozenset({"result_hash"}),
                ),
            ),
        )
