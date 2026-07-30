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
from app.features.tier_a import TIER_A_FEATURE_METADATA


REGISTRY_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class FeatureRegistry:
    definitions: tuple[FeatureDefinitionMetadata, ...]

    def __init__(
        self,
        definitions: Iterable[FeatureDefinitionMetadata],
    ) -> None:
        materialized = tuple(definitions)
        _validate_registry(materialized)
        object.__setattr__(self, "definitions", materialized)

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
        return {
            "registry_schema_version": REGISTRY_SCHEMA_VERSION,
            "availability_contract_version": (
                FEATURE_AVAILABILITY_CONTRACT_VERSION
            ),
            "definitions": [
                {
                    "identifier": definition.identifier,
                    "description": definition.description,
                    "category": definition.category,
                    "definition_version": definition.definition_version,
                    "required_inputs": [
                        field.value for field in definition.required_inputs
                    ],
                    "supported_timeframes": [
                        timeframe.value
                        for timeframe in definition.supported_timeframes
                    ],
                    "outputs": [
                        {
                            "identifier": output.identifier,
                            "description": output.description,
                            "minimum_observations": (
                                output.minimum_observations
                            ),
                        }
                        for output in definition.outputs
                    ],
                    "history_type": definition.history_type.value,
                    "maximum_lookback_observations": (
                        definition.maximum_lookback_observations
                    ),
                    "requires_continuity": (
                        definition.requires_continuity
                    ),
                    "availability_rule": (
                        definition.availability_rule.value
                    ),
                    "implementation_reference": (
                        definition.implementation_reference
                    ),
                    "dependencies": list(definition.dependencies),
                    "decimal_quantum": _canonical_decimal(
                        definition.decimal_quantum
                    ),
                }
                for definition in self.definitions
            ],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

def _validate_registry(
    definitions: tuple[FeatureDefinitionMetadata, ...],
) -> None:
    identifiers = tuple(definition.identifier for definition in definitions)
    if len(set(identifiers)) != len(identifiers):
        raise FeatureMetadataError(
            "Feature registry contains duplicate definition identifiers."
        )

    output_owners: dict[str, str] = {}
    registered: set[str] = set()
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
        registered.add(definition.identifier)


def _canonical_decimal(value: Decimal) -> str:
    return format(value, "f")


INTRADAY_FEATURE_REGISTRY = FeatureRegistry(TIER_A_FEATURE_METADATA)
