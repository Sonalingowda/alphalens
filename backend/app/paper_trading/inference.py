"""Paper inference through the single production prediction interface."""

from app.inference.service import ProductionPredictionService
from app.paper_trading.models import PaperFeatureVector, PaperPrediction


class PaperInferenceService:
    def __init__(
        self,
        prediction_service: ProductionPredictionService,
    ) -> None:
        self._prediction_service = prediction_service

    @property
    def ordered_feature_names(self) -> tuple[str, ...]:
        return self._prediction_service.ordered_feature_names

    @property
    def artifact_sha256(self) -> str:
        return self._prediction_service.artifact.artifact_sha256

    def predict(self, vector: PaperFeatureVector) -> PaperPrediction:
        prediction = self._prediction_service.predict(
            prediction_timestamp=vector.timestamp,
            feature_names=vector.feature_names,
            feature_values=vector.feature_values,
            schema_hash=self._prediction_service.schema_hash,
        )
        return PaperPrediction(
            prediction_timestamp=vector.timestamp,
            predicted_forward_return=(
                prediction.predicted_forward_return
            ),
            predicted_float_hex=prediction.predicted_float_hex,
            evidence_hash=prediction.prediction_hash,
            feature_vector_hash=prediction.feature_vector_hash,
            inference_artifact_sha256=prediction.artifact_sha256,
        )
