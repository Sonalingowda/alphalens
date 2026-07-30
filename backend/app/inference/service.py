"""Single deterministic production prediction interface."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.inference.artifact import hash_json
from app.inference.repository import LoadedProductionArtifact


PREDICTION_API_VERSION = "1.0.0"


class PredictionValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class ProductionPrediction:
    prediction_timestamp: datetime
    predicted_forward_return: Decimal
    predicted_float_hex: str
    prediction_hash: str
    feature_vector_hash: str
    schema_hash: str
    artifact_id: UUID
    artifact_sha256: str
    configuration_hash: str


class ProductionPredictionService:
    """Validate an exact feature schema and invoke artifact predict only."""

    def __init__(self, artifact: LoadedProductionArtifact) -> None:
        self.artifact = artifact
        self.ordered_feature_names = (
            artifact.inference.feature_names
        )
        self.schema_hash = production_schema_hash(artifact)

    def predict(
        self,
        *,
        prediction_timestamp: datetime,
        feature_names: tuple[str, ...],
        feature_values: tuple[Decimal, ...],
        schema_hash: str,
    ) -> ProductionPrediction:
        if (
            prediction_timestamp.tzinfo is None
            or prediction_timestamp.utcoffset() is None
        ):
            raise PredictionValidationError(
                "INVALID_PREDICTION_TIMESTAMP",
                "prediction_timestamp must include a UTC offset.",
            )
        expected_count = len(self.ordered_feature_names)
        if len(feature_names) != expected_count:
            raise PredictionValidationError(
                "FEATURE_COUNT_MISMATCH",
                f"Exactly {expected_count} ordered features are required.",
            )
        if len(feature_values) != expected_count:
            raise PredictionValidationError(
                "FEATURE_COUNT_MISMATCH",
                f"Exactly {expected_count} feature values are required.",
            )
        if feature_names != self.ordered_feature_names:
            if set(feature_names) == set(self.ordered_feature_names):
                code = "FEATURE_ORDER_MISMATCH"
                message = "Feature ordering differs from the model schema."
            else:
                code = "FEATURE_NAME_MISMATCH"
                message = "Feature names differ from the model schema."
            raise PredictionValidationError(code, message)
        if schema_hash != self.schema_hash:
            raise PredictionValidationError(
                "SCHEMA_HASH_MISMATCH",
                "schema_hash differs from the production model schema.",
            )
        if any(not value.is_finite() for value in feature_values):
            raise PredictionValidationError(
                "NON_FINITE_FEATURE_VALUE",
                "Feature values must be finite decimals.",
            )
        vector_hash = hash_json(
            {
                "prediction_timestamp": (
                    prediction_timestamp.isoformat()
                ),
                "schema_hash": self.schema_hash,
                "features": [
                    {"name": name, "value": format(value, "f")}
                    for name, value in zip(
                        feature_names,
                        feature_values,
                        strict=True,
                    )
                ],
            }
        )
        prediction = self.artifact.inference.predict(feature_values)
        prediction_hash = hash_json(
            {
                "prediction_timestamp": (
                    prediction_timestamp.isoformat()
                ),
                "feature_vector_hash": vector_hash,
                "inference_artifact_sha256": (
                    self.artifact.artifact_sha256
                ),
                "predicted_float_hex": prediction.float_hex,
            }
        )
        return ProductionPrediction(
            prediction_timestamp=prediction_timestamp,
            predicted_forward_return=Decimal(str(prediction.value)),
            predicted_float_hex=prediction.float_hex,
            prediction_hash=prediction_hash,
            feature_vector_hash=vector_hash,
            schema_hash=self.schema_hash,
            artifact_id=self.artifact.artifact_id,
            artifact_sha256=self.artifact.artifact_sha256,
            configuration_hash=self.artifact.configuration_hash,
        )


def production_schema_hash(
    artifact: LoadedProductionArtifact,
) -> str:
    return hash_json(
        {
            "api_version": PREDICTION_API_VERSION,
            "feature_pipeline_version": (
                artifact.feature_pipeline_version
            ),
            "ordered_feature_names": list(
                artifact.inference.feature_names
            ),
            "value_encoding": "decimal_string",
        }
    )
