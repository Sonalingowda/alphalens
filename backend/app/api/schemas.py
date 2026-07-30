"""Strict request and response schemas for prediction API v1."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=1, max_length=128),
]
HashText = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
DecimalText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=False,
        min_length=1,
        max_length=128,
    ),
]


class FeatureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonEmptyText
    value: DecimalText


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: NonEmptyText
    schema_hash: HashText
    prediction_timestamp: datetime
    features: list[FeatureInput] = Field(max_length=128)


class PredictionResponse(BaseModel):
    api_version: str
    prediction_timestamp: datetime
    inference_timestamp: datetime
    target_name: str
    target_version: str
    horizon_observations: int
    predicted_forward_log_return: str
    predicted_float_hex: str
    prediction_hash: str
    feature_vector_hash: str
    schema_hash: str
    artifact_identifier: UUID
    artifact_sha256: str
    configuration_hash: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    api_version: str
    details: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    error: ErrorDetail

