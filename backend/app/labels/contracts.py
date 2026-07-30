"""Technology-independent metadata contracts for AlphaLens v2 labels."""

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

from app.market_data.models import CandleTimeframe


LABEL_INFRASTRUCTURE_SCHEMA_VERSION = "1.0.0"
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_SEMANTIC_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_TIMEFRAMES = frozenset(
    {
        CandleTimeframe.MINUTE_5,
        CandleTimeframe.MINUTE_10,
        CandleTimeframe.MINUTE_15,
    }
)


class LabelPolicyMetadataError(ValueError):
    """Raised when label-policy metadata is incomplete or inconsistent."""


class LabelClass(StrEnum):
    """The exclusive AlphaLens v2 research-label vocabulary."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class LabelStrategy(StrEnum):
    """Approved strategy families, not executable parameterizations."""

    FIRST_TOUCH_BARRIER = "first_touch_barrier"


@dataclass(frozen=True, slots=True)
class LabelPolicyDeclaration:
    """Immutable identity for a separately approved quantitative policy.

    The declaration cannot calculate a label. It records an already approved
    policy configuration so later generation evidence can refer to immutable
    content rather than an implicit runtime default.
    """

    identifier: str
    version: str
    strategy: LabelStrategy
    asset_identifier: str
    quote_currency: str
    timeframe: CandleTimeframe
    approval_reference: str
    configuration: Mapping[str, object]
    configuration_hash: str

    def __post_init__(self) -> None:
        if not _IDENTIFIER_PATTERN.fullmatch(self.identifier):
            raise LabelPolicyMetadataError(
                "Label-policy identifier must use lowercase snake_case."
            )
        if not _SEMANTIC_VERSION_PATTERN.fullmatch(self.version):
            raise LabelPolicyMetadataError(
                "Label-policy version must use MAJOR.MINOR.PATCH."
            )
        if self.strategy is not LabelStrategy.FIRST_TOUCH_BARRIER:
            raise LabelPolicyMetadataError(
                "Only the approved first-touch strategy family is admissible."
            )
        if self.asset_identifier != "BTC" or self.quote_currency != "USD":
            raise LabelPolicyMetadataError(
                "The approved AlphaLens v2 scope is BTC/USD only."
            )
        if self.timeframe not in _SUPPORTED_TIMEFRAMES:
            raise LabelPolicyMetadataError(
                "Label policies support only 5m, 10m, and 15m."
            )
        if not self.approval_reference.strip():
            raise LabelPolicyMetadataError(
                "An explicit human approval reference is required."
            )
        if not self.configuration:
            raise LabelPolicyMetadataError(
                "An approved quantitative configuration is required."
            )
        if not _SHA256_PATTERN.fullmatch(self.configuration_hash):
            raise LabelPolicyMetadataError(
                "Configuration hash must be lowercase SHA-256."
            )

        immutable_configuration = _freeze_json_object(
            _copy_json_object(self.configuration)
        )
        object.__setattr__(self, "configuration", immutable_configuration)
        expected_hash = hashlib.sha256(
            _canonical_json_bytes(self.canonical_configuration_payload())
        ).hexdigest()
        if self.configuration_hash != expected_hash:
            raise LabelPolicyMetadataError(
                "Configuration hash does not match canonical policy content."
            )

    def canonical_configuration_payload(self) -> dict[str, object]:
        return {
            "label_infrastructure_schema_version": (
                LABEL_INFRASTRUCTURE_SCHEMA_VERSION
            ),
            "identifier": self.identifier,
            "version": self.version,
            "strategy": self.strategy.value,
            "asset_identifier": self.asset_identifier,
            "quote_currency": self.quote_currency,
            "timeframe": self.timeframe.value,
            "approval_reference": self.approval_reference,
            "configuration": _thaw_json_value(self.configuration),
        }

    @classmethod
    def approved(
        cls,
        *,
        identifier: str,
        version: str,
        strategy: LabelStrategy,
        asset_identifier: str,
        quote_currency: str,
        timeframe: CandleTimeframe,
        approval_reference: str,
        configuration: Mapping[str, object],
    ) -> "LabelPolicyDeclaration":
        """Build a declaration from explicitly supplied approved content."""
        provisional_payload = {
            "label_infrastructure_schema_version": (
                LABEL_INFRASTRUCTURE_SCHEMA_VERSION
            ),
            "identifier": identifier,
            "version": version,
            "strategy": strategy.value,
            "asset_identifier": asset_identifier,
            "quote_currency": quote_currency,
            "timeframe": timeframe.value,
            "approval_reference": approval_reference,
            "configuration": _copy_json_object(configuration),
        }
        configuration_hash = hashlib.sha256(
            _canonical_json_bytes(provisional_payload)
        ).hexdigest()
        return cls(
            identifier=identifier,
            version=version,
            strategy=strategy,
            asset_identifier=asset_identifier,
            quote_currency=quote_currency,
            timeframe=timeframe,
            approval_reference=approval_reference,
            configuration=configuration,
            configuration_hash=configuration_hash,
        )


def _canonical_json_bytes(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise LabelPolicyMetadataError(
            "Policy configuration must be canonical JSON data."
        ) from error


def _copy_json_object(value: Mapping[str, object]) -> dict[str, object]:
    try:
        encoded = _canonical_json_bytes(dict(value))
        decoded = json.loads(encoded)
    except LabelPolicyMetadataError:
        raise
    if not isinstance(decoded, dict):
        raise LabelPolicyMetadataError(
            "Policy configuration must be a JSON object."
        )
    return decoded


def _freeze_json_object(
    value: Mapping[str, object],
) -> Mapping[str, object]:
    return MappingProxyType(
        {
            key: _freeze_json_value(item)
            for key, item in value.items()
        }
    )


def _freeze_json_value(value: object) -> object:
    if isinstance(value, dict):
        return _freeze_json_object(value)
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _thaw_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value
