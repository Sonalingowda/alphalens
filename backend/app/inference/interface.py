"""Protocol required of production prediction services."""

from decimal import Decimal
from typing import Protocol

from app.inference.artifact import InferencePrediction


class InferenceModel(Protocol):
    @property
    def feature_names(self) -> tuple[str, ...]: ...

    def predict(
        self,
        feature_values: tuple[Decimal | float, ...],
    ) -> InferencePrediction: ...

