"""Shared immutable primitives and canonical serialization."""

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Mapping


CONTRACT_VERSION = "1.0.0"
DECIMAL_QUANTUM = Decimal("0.000000000000000001")
_SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


class DomainValidationError(ValueError):
    """Raised when a canonical domain object violates its contract."""


class CanonicalModel:
    """Serialization behavior shared by frozen domain dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        payload = _canonical_value(self)
        if not isinstance(payload, dict):
            raise TypeError("Canonical model must serialize to an object.")
        return payload

    def canonical_json(self) -> str:
        return canonical_json(self)

    def canonical_sha256(self, *, exclude: frozenset[str] = frozenset()) -> str:
        return canonical_sha256(self, exclude=exclude)


def canonical_json(value: object) -> str:
    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_sha256(
    value: object,
    *,
    exclude: frozenset[str] = frozenset(),
) -> str:
    payload = _canonical_value(value, exclude=exclude)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _canonical_value(
    value: object,
    *,
    exclude: frozenset[str] = frozenset(),
) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        result: dict[str, Any] = {}
        for field in fields(value):
            if field.name in exclude:
                continue
            member = getattr(value, field.name)
            if member is None:
                continue
            result[field.name] = _canonical_value(member)
        return result
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise DomainValidationError("Canonical Decimal must be finite.")
        return format(value, "f")
    if isinstance(value, datetime):
        validate_utc(value, "Canonical timestamp")
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise DomainValidationError("Canonical mapping keys must be strings.")
        return {
            key: _canonical_value(value[key])
            for key in sorted(value)
            if value[key] is not None
        }
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported canonical value type: {type(value).__name__}")


def validate_identifier(value: str, name: str) -> None:
    if not value or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise DomainValidationError(f"{name} must be a canonical identifier.")


def validate_semver(value: str, name: str) -> None:
    if not _SEMVER_PATTERN.fullmatch(value):
        raise DomainValidationError(f"{name} must use MAJOR.MINOR.PATCH.")


def validate_contract_version(value: str) -> None:
    if value != CONTRACT_VERSION:
        raise DomainValidationError(
            f"Contract version must be exactly {CONTRACT_VERSION}."
        )


def validate_sha256(value: str, name: str) -> None:
    if not _SHA256_PATTERN.fullmatch(value):
        raise DomainValidationError(f"{name} must be a lowercase SHA-256 digest.")


def validate_utc(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DomainValidationError(f"{name} must be timezone-aware.")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise DomainValidationError(f"{name} must use UTC.")


def validate_decimal(
    value: Decimal,
    name: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise DomainValidationError(f"{name} must be a finite Decimal.")
    if value != value.quantize(DECIMAL_QUANTUM):
        raise DomainValidationError(f"{name} must fit the 18-place Decimal quantum.")
    if positive and value <= 0:
        raise DomainValidationError(f"{name} must be positive.")
    if non_negative and value < 0:
        raise DomainValidationError(f"{name} must not be negative.")


def validate_non_empty_tuple(value: tuple[Any, ...], name: str) -> None:
    if not value:
        raise DomainValidationError(f"{name} must not be empty.")


def validate_unique_identifiers(
    values: tuple[Any, ...],
    attribute: str,
    name: str,
) -> None:
    identifiers = tuple(getattr(item, attribute) for item in values)
    if len(identifiers) != len(set(identifiers)):
        raise DomainValidationError(f"{name} contains duplicate identifiers.")


class _ValidatedModel(CanonicalModel):
    contract_version: str

    def _validate_contract(self) -> None:
        validate_contract_version(self.contract_version)


@dataclass(frozen=True, slots=True)
class IntegrityReference(CanonicalModel):
    artifact_id: str
    artifact_type: str
    artifact_version: str
    integrity_digest: str
    available_at: datetime

    def __post_init__(self) -> None:
        validate_identifier(self.artifact_id, "Artifact identifier")
        validate_identifier(self.artifact_type, "Artifact type")
        validate_semver(self.artifact_version, "Artifact version")
        validate_sha256(self.integrity_digest, "Artifact integrity digest")
        validate_utc(self.available_at, "Artifact availability")


@dataclass(frozen=True, slots=True)
class PolicyReference(CanonicalModel):
    policy_id: str
    policy_version: str
    integrity_digest: str

    def __post_init__(self) -> None:
        validate_identifier(self.policy_id, "Policy identifier")
        validate_semver(self.policy_version, "Policy version")
        validate_sha256(self.integrity_digest, "Policy integrity digest")


@dataclass(frozen=True, slots=True)
class MarketScope(CanonicalModel):
    instrument: str
    timeframe: str

    def __post_init__(self) -> None:
        validate_identifier(self.instrument, "Instrument")
        validate_identifier(self.timeframe, "Timeframe")


@dataclass(frozen=True, slots=True)
class PriceRange(CanonicalModel):
    lower: Decimal
    upper: Decimal

    def __post_init__(self) -> None:
        validate_decimal(self.lower, "Price range lower", positive=True)
        validate_decimal(self.upper, "Price range upper", positive=True)
        if self.lower > self.upper:
            raise DomainValidationError("Price range lower must not exceed upper.")


@dataclass(frozen=True, slots=True)
class DecimalRange(CanonicalModel):
    lower: Decimal
    upper: Decimal

    def __post_init__(self) -> None:
        validate_decimal(self.lower, "Decimal range lower")
        validate_decimal(self.upper, "Decimal range upper")
        if self.lower > self.upper:
            raise DomainValidationError("Decimal range lower must not exceed upper.")


@dataclass(frozen=True, slots=True)
class Provenance(CanonicalModel):
    source_references: tuple[IntegrityReference, ...]
    policy_references: tuple[PolicyReference, ...]
    code_version: str
    configuration_hash: str
    lineage_hash: str

    def __post_init__(self) -> None:
        validate_non_empty_tuple(self.source_references, "Provenance sources")
        validate_identifier(self.code_version, "Code version")
        validate_sha256(self.configuration_hash, "Configuration hash")
        validate_sha256(self.lineage_hash, "Lineage hash")
        validate_unique_identifiers(
            self.source_references, "artifact_id", "Provenance sources"
        )
        validate_unique_identifiers(
            self.policy_references, "policy_id", "Provenance policies"
        )


@dataclass(frozen=True, slots=True)
class AuditMetadata(CanonicalModel):
    created_at: datetime
    evidence_cutoff: datetime
    available_at: datetime
    provenance: Provenance
    result_hash: str

    def __post_init__(self) -> None:
        validate_utc(self.created_at, "Audit creation time")
        validate_utc(self.evidence_cutoff, "Audit evidence cutoff")
        validate_utc(self.available_at, "Audit availability")
        validate_sha256(self.result_hash, "Audit result hash")
        if self.evidence_cutoff > self.available_at:
            raise DomainValidationError(
                "Evidence cutoff must not be later than availability."
            )
        if self.created_at > self.available_at:
            raise DomainValidationError(
                "Audit creation time must not be later than availability."
            )
        if any(
            source.available_at > self.evidence_cutoff
            for source in self.provenance.source_references
        ):
            raise DomainValidationError(
                "Provenance source is unavailable at the evidence cutoff."
            )
