"""Immutable market and feature snapshot domain models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.opportunity_intelligence.domain.primitives import (
    AuditMetadata,
    CanonicalModel,
    DomainValidationError,
    IntegrityReference,
    MarketScope,
    validate_contract_version,
    validate_decimal,
    validate_identifier,
    validate_non_empty_tuple,
    validate_semver,
    validate_sha256,
    validate_unique_identifiers,
    validate_utc,
)


@dataclass(frozen=True, slots=True)
class MarketCandleSnapshot(CanonicalModel):
    candle_id: str
    timestamp: datetime
    available_at: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source_reference: IntegrityReference

    def __post_init__(self) -> None:
        validate_identifier(self.candle_id, "Candle identifier")
        validate_utc(self.timestamp, "Candle timestamp")
        validate_utc(self.available_at, "Candle availability")
        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
        ):
            validate_decimal(value, f"Candle {name}", positive=True)
        validate_decimal(self.volume, "Candle volume", non_negative=True)
        if self.low > min(self.open, self.close, self.high):
            raise DomainValidationError("Candle low exceeds another price field.")
        if self.high < max(self.open, self.close, self.low):
            raise DomainValidationError("Candle high is below another price field.")
        if self.available_at < self.timestamp:
            raise DomainValidationError(
                "Candle availability must not precede its timestamp."
            )
        if self.source_reference.available_at > self.available_at:
            raise DomainValidationError(
                "Candle source must be available by candle availability."
            )


@dataclass(frozen=True, slots=True)
class MarketSnapshot(CanonicalModel):
    contract_version: str
    snapshot_id: str
    scope: MarketScope
    candles: tuple[MarketCandleSnapshot, ...]
    complete: bool
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.snapshot_id, "Market snapshot identifier")
        validate_non_empty_tuple(self.candles, "Market snapshot candles")
        validate_unique_identifiers(self.candles, "candle_id", "Market candles")
        if not self.complete:
            raise DomainValidationError("Canonical market snapshot must be complete.")
        timestamps = tuple(candle.timestamp for candle in self.candles)
        if timestamps != tuple(sorted(timestamps)) or len(set(timestamps)) != len(
            timestamps
        ):
            raise DomainValidationError(
                "Market snapshot candles must be uniquely chronological."
            )
        if any(
            candle.available_at > self.audit.evidence_cutoff
            for candle in self.candles
        ):
            raise DomainValidationError(
                "Market snapshot contains a future-unavailable candle."
            )


@dataclass(frozen=True, slots=True)
class FeatureSnapshotValue(CanonicalModel):
    feature_identifier: str
    definition_version: str
    output_name: str
    candle_timestamp: datetime
    available_at: datetime
    value: Decimal
    feature_record: IntegrityReference

    def __post_init__(self) -> None:
        validate_identifier(self.feature_identifier, "Feature identifier")
        validate_semver(self.definition_version, "Feature definition version")
        validate_identifier(self.output_name, "Feature output name")
        validate_utc(self.candle_timestamp, "Feature candle timestamp")
        validate_utc(self.available_at, "Feature availability")
        validate_decimal(self.value, "Feature value")
        if self.available_at < self.candle_timestamp:
            raise DomainValidationError(
                "Feature availability must not precede its candle."
            )
        if self.feature_record.available_at > self.available_at:
            raise DomainValidationError(
                "Feature record must be available by feature availability."
            )

    @property
    def value_id(self) -> str:
        return (
            f"{self.feature_identifier}:{self.definition_version}:"
            f"{self.output_name}:{self.candle_timestamp.isoformat()}"
        )


@dataclass(frozen=True, slots=True)
class FeatureSnapshot(CanonicalModel):
    contract_version: str
    snapshot_id: str
    scope: MarketScope
    market_snapshot: IntegrityReference
    registry_hash: str
    values: tuple[FeatureSnapshotValue, ...]
    audit: AuditMetadata

    def __post_init__(self) -> None:
        validate_contract_version(self.contract_version)
        validate_identifier(self.snapshot_id, "Feature snapshot identifier")
        validate_sha256(self.registry_hash, "Feature registry hash")
        validate_non_empty_tuple(self.values, "Feature snapshot values")
        identifiers = tuple(value.value_id for value in self.values)
        if len(identifiers) != len(set(identifiers)):
            raise DomainValidationError("Feature snapshot contains duplicate values.")
        if any(
            value.available_at > self.audit.evidence_cutoff for value in self.values
        ):
            raise DomainValidationError(
                "Feature snapshot contains a future-unavailable value."
            )
        ordering = tuple(
            (
                value.feature_identifier,
                value.definition_version,
                value.output_name,
                value.candle_timestamp,
            )
            for value in self.values
        )
        if ordering != tuple(sorted(ordering)):
            raise DomainValidationError(
                "Feature snapshot values must use canonical ordering."
            )

