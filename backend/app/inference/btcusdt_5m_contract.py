"""Contract-only BTCUSDT/5m inference identity and fail-closed validation.

This module deliberately does not fit models, load numeric model state, score,
rank, or create predictions. It freezes the approved five-feature wire and
provenance boundary so a later approved artifact can be attached without
changing the existing BTC/USD/1d Ridge contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
import re
from typing import Any

from app.features.contracts import (
    FEATURE_AVAILABILITY_CONTRACT_VERSION,
    FEATURE_VALUE_QUANTUM,
    quantize_feature_value,
)
from app.features.registry import INTRADAY_FEATURE_REGISTRY
from app.market_data.models import CandleTimeframe
from app.market_data.validation import floor_timeframe_boundary, timeframe_duration


MODEL_FAMILY = "btcusdt_5m_expected_move_ridge"
CONTRACT_VERSION = "1.0.0"
SCHEMA_ENVELOPE_VERSION = "1.0.0"
TARGET_NAME = "absolute_forward_log_move"
TARGET_VERSION = "expected_move_absolute_log_move.v1.0.0"
TARGET_FORMULA = "abs(log(close[t+5] / close[t]))"
TARGET_HORIZON_CANDLES = 5
TARGET_HORIZON_MINUTES = 25
EXCHANGE = "binance"
SYMBOL = "BTCUSDT"
TIMEFRAME = CandleTimeframe.MINUTE_5.value
TIMEZONE = "UTC"
CANDLE_STATE = "closed"
FEATURE_PIPELINE_VERSION = "2.7.0"
REGISTRY_SCHEMA_VERSION = "1.1.0"
SELECTED_FEATURE_MINIMUM_OBSERVATIONS = 28
FULL_PIPELINE_PREROLL_OBSERVATIONS = 200
DECIMAL_ROUNDING = "ROUND_HALF_EVEN"
WIRE_ENCODING = "canonical_decimal_string"
INFERENCE_NUMERIC_TYPE = "float64"

FEATURE_NAMES: tuple[str, ...] = (
    "average_true_range",
    "candle_range_fraction",
    "bollinger_band_width",
    "rolling_standard_deviation_20",
    "average_directional_index",
)
FEATURE_DEFINITION_VERSIONS: tuple[str, ...] = ("1.0.0",) * len(FEATURE_NAMES)
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class Btcusdt5mContractError(ValueError):
    """Raised when the BTCUSDT/5m contract cannot be satisfied."""


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def canonical_hash(value: object) -> str:
    """Hash compact sorted-key UTF-8 JSON using the contract convention."""
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _canonical_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise Btcusdt5mContractError("Feature values must be finite Decimal values.")
    quantized = quantize_feature_value(value)
    if quantized != value:
        raise Btcusdt5mContractError(
            "Feature value is not quantized to the approved Decimal quantum."
        )
    return format(quantized, "f")


def _validate_feature_mapping(
    feature_values: Mapping[str, Decimal],
) -> tuple[Decimal, ...]:
    if not isinstance(feature_values, Mapping):
        raise Btcusdt5mContractError("Feature values must be a mapping.")
    actual = tuple(feature_values)
    expected = FEATURE_NAMES
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise Btcusdt5mContractError(
            "Feature mapping must contain exactly the approved feature names."
        )
    return tuple(
        _validate_feature_value(feature_values[name]) for name in expected
    )


def _validate_feature_value(value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise Btcusdt5mContractError(
            "Feature values must be finite Decimal values; coercion is unsupported."
        )
    try:
        quantized = value.quantize(FEATURE_VALUE_QUANTUM, rounding=ROUND_HALF_EVEN)
    except Exception as error:
        raise Btcusdt5mContractError(
            "Feature value cannot be represented at the approved quantum."
        ) from error
    if quantized != value:
        raise Btcusdt5mContractError(
            "Feature value is not quantized to the approved Decimal quantum."
        )
    return value


def feature_wire_items(
    feature_values: Mapping[str, Decimal],
) -> tuple[dict[str, str], ...]:
    """Return the ordered, canonical decimal-string feature wire items."""
    values = _validate_feature_mapping(feature_values)
    return tuple(
        {"name": name, "value": _canonical_decimal(value)}
        for name, value in zip(FEATURE_NAMES, values, strict=True)
    )


def serialize_feature_vector(
    feature_values: Mapping[str, Decimal],
) -> bytes:
    """Serialize the exact ordered vector as canonical compact UTF-8 JSON."""
    return _canonical_json_bytes({"features": list(feature_wire_items(feature_values))})


def deserialize_feature_vector(payload: bytes | str) -> dict[str, Decimal]:
    """Parse and validate the exact ordered feature wire representation."""
    try:
        document = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise Btcusdt5mContractError("Feature wire JSON is invalid.") from error
    if not isinstance(document, Mapping) or set(document) != {"features"}:
        raise Btcusdt5mContractError("Feature wire envelope is invalid.")
    items = document["features"]
    if not isinstance(items, list) or len(items) != len(FEATURE_NAMES):
        raise Btcusdt5mContractError("Feature wire vector length is invalid.")
    result: dict[str, Decimal] = {}
    for expected_name, item in zip(FEATURE_NAMES, items, strict=True):
        if not isinstance(item, Mapping) or set(item) != {"name", "value"}:
            raise Btcusdt5mContractError("Feature wire item is invalid.")
        if item["name"] != expected_name or expected_name in result:
            raise Btcusdt5mContractError("Feature wire order or names differ.")
        if not isinstance(item["value"], str):
            raise Btcusdt5mContractError("Feature wire values must be strings.")
        try:
            value = Decimal(item["value"])
        except Exception as error:
            raise Btcusdt5mContractError("Feature wire Decimal is invalid.") from error
        result[expected_name] = _validate_feature_value(value)
        if _canonical_decimal(value) != item["value"]:
            raise Btcusdt5mContractError("Feature wire Decimal is not canonical.")
    _validate_feature_mapping(result)
    return result


def schema_envelope() -> dict[str, Any]:
    """Return the immutable five-feature schema identity envelope."""
    return {
        "schema_envelope_version": SCHEMA_ENVELOPE_VERSION,
        "model_family": MODEL_FAMILY,
        "contract_version": CONTRACT_VERSION,
        "market": {
            "candle_state": CANDLE_STATE,
            "exchange": EXCHANGE,
            "symbol": SYMBOL,
            "timeframe": TIMEFRAME,
            "timezone": TIMEZONE,
        },
        "features": [
            {"definition_version": version, "name": name}
            for name, version in zip(
                FEATURE_NAMES,
                FEATURE_DEFINITION_VERSIONS,
                strict=True,
            )
        ],
        "feature_registry": {
            "pipeline_version": FEATURE_PIPELINE_VERSION,
            "registry_hash": INTRADAY_FEATURE_REGISTRY.configuration_hash,
            "registry_schema_version": REGISTRY_SCHEMA_VERSION,
        },
        "availability": {
            "contract_version": FEATURE_AVAILABILITY_CONTRACT_VERSION,
            "full_pipeline_preroll_observations": FULL_PIPELINE_PREROLL_OBSERVATIONS,
            "rule": "candle_close",
            "selected_feature_minimum_observations": (
                SELECTED_FEATURE_MINIMUM_OBSERVATIONS
            ),
        },
        "numeric": {
            "decimal_quantum": format(FEATURE_VALUE_QUANTUM, "f"),
            "inference_numeric_type": INFERENCE_NUMERIC_TYPE,
            "rounding": DECIMAL_ROUNDING,
            "wire_encoding": WIRE_ENCODING,
        },
    }


def schema_hash() -> str:
    return canonical_hash(schema_envelope())


def target_envelope() -> dict[str, Any]:
    return {
        "target_envelope_version": "1.0.0",
        "model_family": MODEL_FAMILY,
        "contract_version": CONTRACT_VERSION,
        "target_name": TARGET_NAME,
        "target_version": TARGET_VERSION,
        "formula": TARGET_FORMULA,
        "horizon_candles": TARGET_HORIZON_CANDLES,
        "horizon_minutes": TARGET_HORIZON_MINUTES,
        "units": "dimensionless_log_magnitude",
        "non_negative": True,
        "direction_semantics": "not_represented; supplied only by Detection",
        "market": {
            "exchange": EXCHANGE,
            "symbol": SYMBOL,
            "timeframe": TIMEFRAME,
            "timezone": TIMEZONE,
            "cutoff": "closed_candle_close",
        },
    }


def target_hash() -> str:
    return canonical_hash(target_envelope())


def validate_closed_candle_cutoff(
    *,
    candle_timestamp: datetime,
    feature_available_at: datetime,
    prediction_cutoff: datetime,
    is_closed: bool,
) -> None:
    """Require an aligned UTC candle and exact registered close availability."""
    if not is_closed:
        raise Btcusdt5mContractError("Only closed candles are accepted.")
    for name, value in (
        ("candle_timestamp", candle_timestamp),
        ("feature_available_at", feature_available_at),
        ("prediction_cutoff", prediction_cutoff),
    ):
        if value.tzinfo is None or value.utcoffset() is None:
            raise Btcusdt5mContractError(f"{name} must be timezone-aware UTC.")
        if value.utcoffset().total_seconds() != 0:
            raise Btcusdt5mContractError(f"{name} must use canonical UTC.")
    if floor_timeframe_boundary(candle_timestamp, CandleTimeframe.MINUTE_5) != candle_timestamp:
        raise Btcusdt5mContractError("Candle timestamp is not aligned to 5m.")
    expected_available_at = candle_timestamp + timeframe_duration(
        CandleTimeframe.MINUTE_5
    )
    if feature_available_at != expected_available_at:
        raise Btcusdt5mContractError(
            "Feature availability is stale or does not match the candle close."
        )
    if prediction_cutoff < feature_available_at:
        raise Btcusdt5mContractError(
            "Prediction cutoff precedes feature availability and would leak time."
        )


def convert_features_to_float64(
    feature_values: Mapping[str, Decimal],
) -> tuple[float, ...]:
    """Convert only a validated ordered vector at the inference boundary."""
    values = _validate_feature_mapping(feature_values)
    try:
        converted = tuple(float(value) for value in values)
    except (OverflowError, ValueError) as error:
        raise Btcusdt5mContractError(
            "Feature conversion cannot produce float64."
        ) from error
    if any(not math.isfinite(value) for value in converted):
        raise Btcusdt5mContractError("Feature conversion produced non-finite float64.")
    return converted


def _require_hash(value: object, field: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise Btcusdt5mContractError(f"{field} must be a lowercase SHA-256 hash.")
    return value


def validate_artifact_provenance(
    artifact: Mapping[str, Any],
) -> None:
    """Validate an approved artifact envelope without loading or predicting."""
    if not isinstance(artifact, Mapping):
        raise Btcusdt5mContractError("Artifact envelope must be a mapping.")
    required = {
        "artifact_id",
        "artifact_payload",
        "artifact_sha256",
        "artifact_state",
        "state_sha256",
        "approval_status",
        "contract_version",
        "exchange",
        "model_family",
        "schema_hash",
        "symbol",
        "target_hash",
        "timeframe",
        "candle_state",
        "provenance",
    }
    if not required.issubset(artifact):
        raise Btcusdt5mContractError("Artifact provenance fields are incomplete.")
    if artifact["model_family"] != MODEL_FAMILY:
        raise Btcusdt5mContractError("Artifact model family differs.")
    if artifact["contract_version"] != CONTRACT_VERSION:
        raise Btcusdt5mContractError("Artifact contract version differs.")
    if (
        artifact["exchange"] != EXCHANGE
        or artifact["symbol"] != SYMBOL
        or artifact["timeframe"] != TIMEFRAME
        or artifact["candle_state"] != CANDLE_STATE
    ):
        raise Btcusdt5mContractError("Artifact market or candle scope differs.")
    if artifact["schema_hash"] != schema_hash():
        raise Btcusdt5mContractError("Artifact schema hash differs.")
    if artifact["target_hash"] != target_hash():
        raise Btcusdt5mContractError("Artifact target hash differs.")
    if artifact["approval_status"] != "approved":
        raise Btcusdt5mContractError("Artifact is not explicitly approved.")
    if not isinstance(artifact["artifact_id"], str) or not artifact["artifact_id"]:
        raise Btcusdt5mContractError("Artifact identity is missing.")
    if not isinstance(artifact["artifact_payload"], Mapping) or not isinstance(
        artifact["artifact_state"], Mapping
    ):
        raise Btcusdt5mContractError("Artifact payload/state are incomplete.")
    if canonical_hash(artifact["artifact_payload"]) != artifact["artifact_sha256"]:
        raise Btcusdt5mContractError("Artifact payload hash differs.")
    if canonical_hash(artifact["artifact_state"]) != artifact["state_sha256"]:
        raise Btcusdt5mContractError("Artifact state hash differs.")
    provenance = artifact["provenance"]
    if not isinstance(provenance, Mapping):
        raise Btcusdt5mContractError("Artifact provenance is incomplete.")
    for field in (
        "candle_dataset_hash",
        "feature_dataset_hash",
        "target_dataset_hash",
        "validation_result_hash",
    ):
        _require_hash(provenance.get(field), f"provenance.{field}")
    for field in ("validation_run_id", "source_commit", "source_tree"):
        if not isinstance(provenance.get(field), str) or not provenance[field]:
            raise Btcusdt5mContractError(f"provenance.{field} is missing.")


class Btcusdt5mInferenceBoundary:
    """Contract gate and float64 preparation; deliberately no prediction API."""

    def __init__(self, artifact: Mapping[str, Any]) -> None:
        validate_artifact_provenance(artifact)
        self.artifact_id = artifact["artifact_id"]
        self.schema_hash = schema_hash()
        self.target_hash = target_hash()

    def prepare_features(self, feature_values: Mapping[str, Decimal]) -> tuple[float, ...]:
        return convert_features_to_float64(feature_values)

