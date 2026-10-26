"""Contract-only tests for the versioned BTCUSDT/5m inference boundary."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import unittest

from app.inference.btcusdt_5m_contract import (
    CONTRACT_VERSION,
    FEATURE_NAMES,
    MODEL_FAMILY,
    TARGET_NAME,
    TARGET_VERSION,
    Btcusdt5mContractError,
    Btcusdt5mInferenceBoundary,
    canonical_hash,
    convert_features_to_float64,
    deserialize_feature_vector,
    schema_envelope,
    schema_hash,
    serialize_feature_vector,
    target_envelope,
    target_hash,
    validate_artifact_provenance,
    validate_closed_candle_cutoff,
)


def _features() -> dict[str, Decimal]:
    return {
        name: Decimal(index + 1).quantize(Decimal("0.000000000000000001"))
        for index, name in enumerate(FEATURE_NAMES)
    }


def _artifact() -> dict[str, object]:
    payload = {"contract_only": True, "version": CONTRACT_VERSION}
    state = {"numeric_state": "absent-by-design"}
    return {
        "artifact_id": "approved-placeholder-for-validation-test",
        "artifact_payload": payload,
        "artifact_sha256": canonical_hash(payload),
        "artifact_state": state,
        "state_sha256": canonical_hash(state),
        "approval_status": "approved",
        "contract_version": CONTRACT_VERSION,
        "exchange": "binance",
        "model_family": MODEL_FAMILY,
        "schema_hash": schema_hash(),
        "symbol": "BTCUSDT",
        "target_hash": target_hash(),
        "timeframe": "5m",
        "candle_state": "closed",
        "provenance": {
            "candle_dataset_hash": "a" * 64,
            "feature_dataset_hash": "b" * 64,
            "target_dataset_hash": "c" * 64,
            "validation_result_hash": "d" * 64,
            "validation_run_id": "validation-not-created-in-this-batch",
            "source_commit": "948913a7e2df47b785bef655deaa4843c7589bcf",
            "source_tree": "d5c58d5b7c001c7b84889a80831a0d8c9b054b73",
        },
    }


class Btcusdt5mContractTests(unittest.TestCase):
    def test_exact_order_and_canonical_decimal_wire(self) -> None:
        wire = serialize_feature_vector(dict(reversed(tuple(_features().items()))))
        self.assertEqual(
            json.loads(wire),
            {
                "features": [
                    {"name": name, "value": f"{index + 1}.000000000000000000"}
                    for index, name in enumerate(FEATURE_NAMES)
                ]
            },
        )
        self.assertEqual(deserialize_feature_vector(wire), _features())

    def test_missing_extra_reordered_and_noncanonical_features_reject(self) -> None:
        values = _features()
        with self.assertRaises(Btcusdt5mContractError):
            serialize_feature_vector({name: value for name, value in values.items() if name != FEATURE_NAMES[0]})
        with self.assertRaises(Btcusdt5mContractError):
            serialize_feature_vector(values | {"unexpected": Decimal("1")})
        wire = json.loads(serialize_feature_vector(values))
        wire["features"][0], wire["features"][1] = wire["features"][1], wire["features"][0]
        with self.assertRaises(Btcusdt5mContractError):
            deserialize_feature_vector(json.dumps(wire))
        wire = json.loads(serialize_feature_vector(values))
        wire["features"][0]["value"] = "1.0"
        with self.assertRaises(Btcusdt5mContractError):
            deserialize_feature_vector(json.dumps(wire))

    def test_decimal_quantum_and_float_boundary(self) -> None:
        invalid = _features() | {FEATURE_NAMES[0]: Decimal("1.0000000000000000001")}
        with self.assertRaises(Btcusdt5mContractError):
            convert_features_to_float64(invalid)
        overflow = _features() | {FEATURE_NAMES[0]: Decimal("1e10000")}
        with self.assertRaises(Btcusdt5mContractError):
            convert_features_to_float64(overflow)
        converted = convert_features_to_float64(_features())
        self.assertEqual(converted, (1.0, 2.0, 3.0, 4.0, 5.0))

    def test_schema_and_target_hashes_are_deterministic_and_bound(self) -> None:
        self.assertEqual(schema_hash(), canonical_hash(schema_envelope()))
        self.assertEqual(target_hash(), canonical_hash(target_envelope()))
        self.assertEqual(target_envelope()["target_name"], TARGET_NAME)
        self.assertEqual(target_envelope()["target_version"], TARGET_VERSION)
        self.assertEqual(schema_hash(), schema_hash())
        self.assertEqual(target_hash(), target_hash())

    def test_closed_candle_and_cutoff_contract(self) -> None:
        candle = datetime(2026, 10, 10, 12, 10, tzinfo=timezone.utc)
        available = candle + timedelta(minutes=5)
        validate_closed_candle_cutoff(
            candle_timestamp=candle,
            feature_available_at=available,
            prediction_cutoff=available,
            is_closed=True,
        )
        with self.assertRaises(Btcusdt5mContractError):
            validate_closed_candle_cutoff(
                candle_timestamp=candle,
                feature_available_at=available,
                prediction_cutoff=available,
                is_closed=False,
            )
        with self.assertRaises(Btcusdt5mContractError):
            validate_closed_candle_cutoff(
                candle_timestamp=candle,
                feature_available_at=candle,
                prediction_cutoff=available,
                is_closed=True,
            )

    def test_artifact_provenance_is_fail_closed(self) -> None:
        artifact = _artifact()
        validate_artifact_provenance(artifact)
        boundary = Btcusdt5mInferenceBoundary(artifact)
        self.assertEqual(boundary.prepare_features(_features()), (1.0, 2.0, 3.0, 4.0, 5.0))
        for field, value in (("approval_status", "pending"), ("model_family", "ridge_regression")):
            invalid = dict(artifact)
            invalid[field] = value
            with self.assertRaises(Btcusdt5mContractError):
                validate_artifact_provenance(invalid)
        invalid = dict(artifact)
        invalid["schema_hash"] = "0" * 64
        with self.assertRaises(Btcusdt5mContractError):
            validate_artifact_provenance(invalid)
        invalid = dict(artifact)
        invalid["symbol"] = "ETHUSDT"
        with self.assertRaises(Btcusdt5mContractError):
            validate_artifact_provenance(invalid)

