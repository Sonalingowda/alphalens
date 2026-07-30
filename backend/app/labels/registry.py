"""Non-executable registry of approved label strategy families."""

from dataclasses import dataclass
import hashlib
import json

from app.labels.contracts import (
    LABEL_INFRASTRUCTURE_SCHEMA_VERSION,
    LabelPolicyMetadataError,
    LabelStrategy,
)


@dataclass(frozen=True, slots=True)
class LabelStrategyDefinition:
    identifier: LabelStrategy
    description: str
    output_classes: tuple[str, ...]
    required_approvals: tuple[str, ...]
    executable: bool

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise LabelPolicyMetadataError(
                "Label strategy description must not be empty."
            )
        if self.output_classes != ("BUY", "SELL", "WAIT"):
            raise LabelPolicyMetadataError(
                "Label strategy must preserve BUY/SELL/WAIT semantics."
            )
        if not self.required_approvals:
            raise LabelPolicyMetadataError(
                "Label strategy must identify unresolved approval gates."
            )
        if len(set(self.required_approvals)) != len(
            self.required_approvals
        ):
            raise LabelPolicyMetadataError(
                "Label strategy contains duplicate approval gates."
            )
        if self.executable:
            raise LabelPolicyMetadataError(
                "Candidate C is not executable before parameter approval."
            )


@dataclass(frozen=True, slots=True)
class LabelStrategyRegistry:
    definitions: tuple[LabelStrategyDefinition, ...]

    def __post_init__(self) -> None:
        identifiers = tuple(
            definition.identifier for definition in self.definitions
        )
        if len(set(identifiers)) != len(identifiers):
            raise LabelPolicyMetadataError(
                "Label strategy registry contains duplicate identifiers."
            )

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def canonical_payload(self) -> dict[str, object]:
        return {
            "label_infrastructure_schema_version": (
                LABEL_INFRASTRUCTURE_SCHEMA_VERSION
            ),
            "definitions": [
                {
                    "identifier": definition.identifier.value,
                    "description": definition.description,
                    "output_classes": list(definition.output_classes),
                    "required_approvals": list(
                        definition.required_approvals
                    ),
                    "executable": definition.executable,
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


FIRST_TOUCH_STRATEGY_DEFINITION = LabelStrategyDefinition(
    identifier=LabelStrategy.FIRST_TOUCH_BARRIER,
    description=(
        "Candidate C strategy family selected for future quantitative "
        "specification; no barrier policy is executable."
    ),
    output_classes=("BUY", "SELL", "WAIT"),
    required_approvals=(
        "prediction_origin",
        "reference_price",
        "upper_barrier",
        "lower_barrier",
        "time_barrier",
        "touch_semantics",
        "ambiguity_policy",
        "wait_and_exclusion_taxonomy",
        "chronology_and_dependence",
        "numeric_policy",
        "research_adequacy",
        "policy_identity_and_hashing",
    ),
    executable=False,
)

LABEL_STRATEGY_REGISTRY = LabelStrategyRegistry(
    definitions=(FIRST_TOUCH_STRATEGY_DEFINITION,)
)
