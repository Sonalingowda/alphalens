"""Declarative, deterministic feature registry infrastructure."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json

from app.features.contracts import (
    FEATURE_AVAILABILITY_CONTRACT_VERSION,
    FeatureDefinitionMetadata,
    FeatureMetadataError,
)
from app.features.atr import ATR_FEATURE_METADATA
from app.features.ema import EMA_FEATURE_METADATA
from app.features.rsi import RSI_FEATURE_METADATA
from app.features.tier_a import TIER_A_FEATURE_METADATA


LEGACY_REGISTRY_SCHEMA_VERSION = "1.0.0"
REGISTRY_SCHEMA_VERSION = "1.1.0"


@dataclass(frozen=True, slots=True)
class FeatureRegistry:
    definitions: tuple[FeatureDefinitionMetadata, ...]
    schema_version: str

    def __init__(
        self,
        definitions: Iterable[FeatureDefinitionMetadata],
        *,
        schema_version: str = REGISTRY_SCHEMA_VERSION,
    ) -> None:
        materialized = tuple(definitions)
        _validate_registry(materialized, schema_version)
        object.__setattr__(self, "definitions", materialized)
        object.__setattr__(self, "schema_version", schema_version)

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @property
    def output_names(self) -> tuple[str, ...]:
        return tuple(
            output.identifier
            for definition in self.definitions
            for output in definition.outputs
        )

    def canonical_payload(self) -> dict[str, object]:
        payload = {
            "registry_schema_version": self.schema_version,
            "availability_contract_version": (FEATURE_AVAILABILITY_CONTRACT_VERSION),
            "definitions": [],
        }
        definitions = []
        for definition in self.definitions:
            definition_payload = {
                "identifier": definition.identifier,
                "description": definition.description,
                "category": definition.category,
                "definition_version": definition.definition_version,
                "required_inputs": [
                    field.value for field in definition.required_inputs
                ],
                "supported_timeframes": [
                    timeframe.value for timeframe in definition.supported_timeframes
                ],
                "outputs": [
                    {
                        "identifier": output.identifier,
                        "description": output.description,
                        "minimum_observations": (output.minimum_observations),
                    }
                    for output in definition.outputs
                ],
                "history_type": definition.history_type.value,
                "maximum_lookback_observations": (
                    definition.maximum_lookback_observations
                ),
                "requires_continuity": (definition.requires_continuity),
                "availability_rule": (definition.availability_rule.value),
                "implementation_reference": (definition.implementation_reference),
                "dependencies": list(definition.dependencies),
                "decimal_quantum": _canonical_decimal(definition.decimal_quantum),
            }
            if self.schema_version != LEGACY_REGISTRY_SCHEMA_VERSION:
                definition_payload["dependency_contracts"] = [
                    {
                        "identifier": contract.identifier,
                        "definition_version": contract.definition_version,
                        "output_names": list(contract.output_names),
                    }
                    for contract in definition.dependency_contracts
                ]
            definitions.append(definition_payload)
        payload["definitions"] = definitions
        return payload

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")


def _validate_registry(
    definitions: tuple[FeatureDefinitionMetadata, ...],
    schema_version: str,
) -> None:
    if schema_version not in {
        LEGACY_REGISTRY_SCHEMA_VERSION,
        REGISTRY_SCHEMA_VERSION,
    }:
        raise FeatureMetadataError("Unsupported feature registry schema.")
    identifiers = tuple(definition.identifier for definition in definitions)
    if len(set(identifiers)) != len(identifiers):
        raise FeatureMetadataError(
            "Feature registry contains duplicate definition identifiers."
        )

    output_owners: dict[str, str] = {}
    registered: dict[str, FeatureDefinitionMetadata] = {}
    for definition in definitions:
        for dependency in definition.dependencies:
            if dependency not in registered:
                raise FeatureMetadataError(
                    f"Feature {definition.identifier} depends on "
                    f"unregistered or later feature {dependency}."
                )
        for output in definition.outputs:
            owner = output_owners.get(output.identifier)
            if owner is not None:
                raise FeatureMetadataError(
                    f"Feature output {output.identifier} is declared by "
                    f"both {owner} and {definition.identifier}."
                )
            output_owners[output.identifier] = definition.identifier
        if schema_version == LEGACY_REGISTRY_SCHEMA_VERSION:
            if definition.dependency_contracts:
                raise FeatureMetadataError(
                    "Registry schema 1.0.0 cannot encode dependency contracts."
                )
        elif set(definition.dependencies) != {
            contract.identifier for contract in definition.dependency_contracts
        }:
            raise FeatureMetadataError(
                f"Feature {definition.identifier} must version every dependency."
            )
        for contract in definition.dependency_contracts:
            dependency = registered[contract.identifier]
            if contract.definition_version != dependency.definition_version:
                raise FeatureMetadataError(
                    f"Feature {definition.identifier} has an incompatible "
                    f"dependency version for {contract.identifier}."
                )
            dependency_outputs = {output.identifier for output in dependency.outputs}
            if not set(contract.output_names).issubset(dependency_outputs):
                raise FeatureMetadataError(
                    f"Feature {definition.identifier} requires an undeclared "
                    f"output from {contract.identifier}."
                )
        registered[definition.identifier] = definition


def _canonical_decimal(value: Decimal) -> str:
    return format(value, "f")


TIER_A_FEATURE_REGISTRY = FeatureRegistry(
    TIER_A_FEATURE_METADATA,
    schema_version=LEGACY_REGISTRY_SCHEMA_VERSION,
)
INTRADAY_FEATURE_REGISTRY = FeatureRegistry(
    TIER_A_FEATURE_METADATA
    + ATR_FEATURE_METADATA
    + EMA_FEATURE_METADATA
    + RSI_FEATURE_METADATA,
)
