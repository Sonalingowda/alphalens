"""AlphaLens v2 labeling contracts.

This package intentionally contains no label calculation. A quantitative
Candidate C policy cannot be executed until its unresolved parameters receive
explicit approval.
"""

from app.labels.contracts import (
    LABEL_INFRASTRUCTURE_SCHEMA_VERSION,
    LabelClass,
    LabelPolicyDeclaration,
    LabelPolicyMetadataError,
    LabelStrategy,
)
from app.labels.registry import (
    FIRST_TOUCH_STRATEGY_DEFINITION,
    LABEL_STRATEGY_REGISTRY,
)

__all__ = [
    "FIRST_TOUCH_STRATEGY_DEFINITION",
    "LABEL_INFRASTRUCTURE_SCHEMA_VERSION",
    "LABEL_STRATEGY_REGISTRY",
    "LabelClass",
    "LabelPolicyDeclaration",
    "LabelPolicyMetadataError",
    "LabelStrategy",
]
