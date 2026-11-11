"""Run the frozen three-candidate Gate 06 volatility experiment.

This runner is development-only. It reads one explicitly supplied, isolated
dataset, writes private research artifacts, and never opens a database or
network client.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from app.features.intraday_pipeline import (
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
from app.market_data.models import Candle, CandleTimeframe
from scripts.gate06_offline_experiment import (
    acceptance_criteria,
    metrics,
    regime_evidence,
    select,
)
from scripts.gate06_volatility_features import (
    CompletedOHLC,
    GARMAN_KLASS_NAME,
    PARKINSON_NAME,
    rolling_volatility_features,
)


FEATURES = (
    "average_directional_index",
    "average_true_range",
    "bollinger_band_width",
    "bollinger_percent_b",
    "candle_body_fraction",
    "candle_range_fraction",
    "exponential_moving_average_12",
    "exponential_moving_average_26",
    "exponential_moving_average_50",
    "macd_histogram",
    "macd_line",
    "macd_signal",
    "negative_directional_indicator",
    "positive_directional_indicator",
    "relative_strength_index",
    "rolling_standard_deviation_20",
    "simple_moving_average_20",
)
HORIZON = 5
PURGE = 250
MIN_TRAIN = 500
TEST_SIZE = 100
STEP = 100
EXPECTED_FOLDS = 164
EXPECTED_OBSERVATIONS = 16_400
REGIME_SECONDS = 30 * 24 * 60 * 60
DATASET_SHA256 = "2825f80df1434ac52eef868cd3606b95b046d7e624d9e0ad84754be494e156b4"
DEVELOPMENT_CONTENT_SHA256 = "d24af87a174a6baef4042afe682760954d7851c18fc75865a18c24f55c5308da"
SOURCE_FILE_SHA256 = "f17dfdab0dfcaa1e24508d9484942eee6677c2e56ddb96869ce774e85ca80fbc"
SOURCE_MANIFEST_SHA256 = "4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038"
PROTOCOL_PATH = "docs/GATE06_VOLATILITY_FEATURE_PROTOCOL_20261111.md"
PROTOCOL_SHA256 = "8decbda413ed41c7ca9cb81f648625a52bf9189d2b387beb856b2d931941b45f"
FEATURE_SCRIPT = "backend/scripts/gate06_volatility_features.py"
CANDIDATES = (
    ("ridge_alpha_1_baseline", FEATURES),
    ("ridge_alpha_1_plus_parkinson", FEATURES + (PARKINSON_NAME,)),
    ("ridge_alpha_1_plus_garman_klass", FEATURES + (GARMAN_KLASS_NAME,)),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def git_identity(repo_root: Path) -> dict[str, str]:
    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ("git", *arguments), cwd=repo_root, text=True
        ).strip()

    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}


def load_dataset(path: Path) -> tuple[dict, list, list[datetime], list[float]]:
    raw = path.read_bytes()
    if sha256_bytes(raw) != DATASET_SHA256:
        raise SystemExit("development dataset hash mismatch")
    data = json.loads(raw)
    if (
        data.get("symbol") != "BTCUSDT"
        or data.get("timeframe") != "5m"
        or data.get("development_cutoff") != "2026-09-12T10:05:00Z"
    ):
        raise SystemExit("invalid development boundary")
    candles = data.get("klines")
    if not isinstance(candles, list) or not candles:
        raise SystemExit("development dataset has no candles")
    timestamps = [datetime.fromtimestamp(row[0] / 1000, timezone.utc) for row in candles]
    closes = [float(row[4]) for row in candles]
    if timestamps[-1].isoformat().replace("+00:00", "Z") != "2026-09-12T10:05:00Z":
        raise SystemExit("development dataset end timestamp mismatch")
    return data, candles, timestamps, closes


def build_tables(candles: list) -> tuple[dict[datetime, dict[str, float]], dict[datetime, dict[str, float]]]:
    fixed_id = __import__("uuid").UUID("caf88988-248f-46e0-b2ef-348161fe38ee")
    observations = []
    volatility_candles = []
    for row in candles:
        timestamp = datetime.fromtimestamp(row[0] / 1000, timezone.utc)
        candle = Candle(
            timestamp=timestamp,
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            close=Decimal(row[4]),
            volume=Decimal(row[5]),
        )
        observations.append(SourceCandleObservation(candle, fixed_id, True))
        volatility_candles.append(
            CompletedOHLC(
                timestamp,
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
            )
        )
    source = build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USDT",
        timeframe=CandleTimeframe.MINUTE_5,
        observations=tuple(observations),
    )
    production = run_intraday_feature_pipeline(source)
    production_by_time: dict[datetime, dict[str, float]] = {}
    for value in production.values:
        production_by_time.setdefault(value.candle_timestamp, {})[value.output_name] = float(value.value)
    volatility_by_time = {
        row["timestamp"]: {PARKINSON_NAME: row[PARKINSON_NAME], GARMAN_KLASS_NAME: row[GARMAN_KLASS_NAME]}
        for row in rolling_volatility_features(volatility_candles)
    }
    return production_by_time, volatility_by_time


def build_observations(
    candles: list, timestamps: list[datetime], closes: list[float]
) -> tuple[list[dict[str, float]], list[datetime], list[float], np.ndarray]:
    production, volatility = build_tables(candles)
    rows: list[dict[str, float]] = []
    valid_timestamps: list[datetime] = []
    valid_closes: list[float] = []
    target = []
    for index in range(len(candles) - HORIZON):
        timestamp = timestamps[index]
        if timestamp not in production or timestamp not in volatility:
            continue
        values = {**production[timestamp], **volatility[timestamp]}
        if any(name not in values or not np.isfinite(values[name]) for name in FEATURES + (PARKINSON_NAME, GARMAN_KLASS_NAME)):
            continue
        rows.append(values)
        valid_timestamps.append(timestamp)
        valid_closes.append(closes[index])
        target.append(abs(np.log(closes[index + HORIZON] / closes[index])))
    if not rows or len(rows) < MIN_TRAIN + PURGE + TEST_SIZE:
        raise SystemExit("insufficient observations for frozen chronological folds")
    return rows, valid_timestamps, valid_closes, np.asarray(target, dtype=float)


def fold_bounds(observation_count: int) -> list[tuple[int, int, int]]:
    folds = [
        (train_end, train_end + PURGE, train_end + PURGE + TEST_SIZE)
        for train_end in range(MIN_TRAIN, observation_count - PURGE - TEST_SIZE + 1, STEP)
    ]
    if len(folds) != EXPECTED_FOLDS:
        raise SystemExit(f"expected {EXPECTED_FOLDS} folds, got {len(folds)}")
    return folds


def execution_manifest(repo_root: Path, dataset: Path, source_manifest: Path) -> dict:
    features_path = repo_root / FEATURE_SCRIPT
    lock_path = repo_root / "backend/uv.lock"
    identity = git_identity(repo_root)
    return {
        "schema": "alphalens.gate06.volatility-execution.v1",
        "lineage_id": "gate06-development-20261111-volatility-v1",
        "git_commit": identity["commit"],
        "git_tree": identity["tree"],
        "dataset_sha256": sha256(dataset),
        "development_content_sha256": DEVELOPMENT_CONTENT_SHA256,
        "source_file_sha256": SOURCE_FILE_SHA256,
        "source_manifest_sha256": sha256(source_manifest),
        "feature_implementation_sha256": sha256(features_path),
        "runner_sha256": sha256(Path(__file__)),
        "production_feature_pipeline_sha256": sha256(repo_root / "backend/app/features/intraday_pipeline.py"),
        "protocol_sha256": sha256(repo_root / PROTOCOL_PATH),
        "dependency_lock_sha256": sha256(lock_path),
        "development_cutoff": "2026-09-12T10:05:00Z",
        "feature_window": 20,
        "label_extension": HORIZON,
        "purge": PURGE,
        "fold_manifest": {
            "minimum_train_observations": MIN_TRAIN,
            "test_observations": TEST_SIZE,
            "step_observations": STEP,
            "fold_count": EXPECTED_FOLDS,
            "observations_per_candidate": EXPECTED_OBSERVATIONS,
        },
        "candidates": [
            {"name": name, "model": "Ridge", "alpha": 1.0, "features": list(features)}
            for name, features in CANDIDATES
        ],
        "budget": {"candidate_count": 3, "maximum_fits": 492},
        "protected_data_accessed": False,
        "fitting_performed": False,
    }


def run(args: argparse.Namespace) -> None:
    repo_root = Path(__file__).parents[2]
    dataset = args.dataset.resolve()
    source_manifest = args.source_manifest.resolve()
    if sha256(source_manifest) != SOURCE_MANIFEST_SHA256:
        raise SystemExit("source manifest hash mismatch")
    manifest = execution_manifest(repo_root, dataset, source_manifest)
    if manifest["protocol_sha256"] != PROTOCOL_SHA256:
        raise SystemExit("protocol hash mismatch")
    execution_manifest_path = args.output.parent / "execution-manifest.json"
    if execution_manifest_path.exists():
        existing = json.loads(execution_manifest_path.read_text(encoding="utf-8"))
        if existing != manifest:
            raise SystemExit("execution manifest mismatch; refusing to reuse lineage")
    else:
        atomic_json(execution_manifest_path, manifest)
    execution_manifest_hash = sha256(execution_manifest_path)
    data, candles, timestamps, closes = load_dataset(dataset)
    if data.get("development_dataset_sha256") != DATASET_SHA256:
        if data.get("development_dataset_sha256") != DEVELOPMENT_CONTENT_SHA256:
            raise SystemExit("development dataset content hash mismatch")
    if data.get("source_file_sha256") != SOURCE_FILE_SHA256:
        raise SystemExit("custodied source file hash mismatch")
    rows, valid_timestamps, valid_closes, target = build_observations(candles, timestamps, closes)
    folds = fold_bounds(len(rows))
    checkpoint_path = args.output.with_suffix(".checkpoint.json")
    checkpoint_identity = {
        "execution_manifest_sha256": execution_manifest_hash,
        "dataset_sha256": DATASET_SHA256,
        "fold_count": len(folds),
        "observation_count": EXPECTED_OBSERVATIONS,
    }
    checkpoint = {"schema": "alphalens.gate06.volatility-checkpoint.v1", "identity": checkpoint_identity, "candidates": {}}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("identity") != checkpoint_identity:
            raise SystemExit("checkpoint identity mismatch; refusing to reuse it")
    results = []
    for name, feature_names in CANDIDATES:
        saved = checkpoint["candidates"].get(name, {})
        candidate_rows = list(saved.get("rows", []))
        completed = int(saved.get("completed_folds", 0))
        if completed != len(candidate_rows) // TEST_SIZE or completed > len(folds):
            raise SystemExit(f"checkpoint fold state is invalid for {name}")
        for sequence, (train_end, test_start, test_end) in enumerate(folds, 1):
            if sequence <= completed:
                continue
            x = np.asarray([[row[feature] for feature in feature_names] for row in rows], dtype=float)
            selected = select(x[:train_end], target[:train_end])
            scaler = StandardScaler().fit(x[:train_end, selected])
            model = Ridge(alpha=1.0)
            model.fit(scaler.transform(x[:train_end, selected]), target[:train_end])
            prediction = np.maximum(model.predict(scaler.transform(x[test_start:test_end, selected])), 0)
            baseline = x[test_start:test_end, feature_names.index("average_true_range")] * 1.5 / np.asarray(valid_closes[test_start:test_end])
            actual = target[test_start:test_end]
            candidate_rows.extend(
                {
                    "fold": sequence,
                    "timestamp": valid_timestamps[test_start + offset].isoformat(),
                    "actual": float(actual[offset]),
                    "prediction": float(prediction[offset]),
                    "residual": float(actual[offset] - prediction[offset]),
                    "baseline": float(baseline[offset]),
                }
                for offset in range(TEST_SIZE)
            )
            checkpoint["candidates"][name] = {"parameters": {"alpha": 1.0}, "features": list(feature_names), "completed_folds": sequence, "rows": candidate_rows}
            atomic_json(checkpoint_path, checkpoint)
            print(f"{name}: completed fold {sequence}/{len(folds)}", flush=True)
        actual = np.asarray([row["actual"] for row in candidate_rows])
        prediction = np.asarray([row["prediction"] for row in candidate_rows])
        baseline = np.asarray([row["baseline"] for row in candidate_rows])
        model_metrics = metrics(actual, prediction)
        baseline_metrics = metrics(actual, baseline)
        calibration = []
        for low, high in zip(np.percentile(prediction, [0, 20, 40, 60, 80]), np.percentile(prediction, [20, 40, 60, 80, 100])):
            values = actual[(prediction >= low) & (prediction <= high)]
            if values.size == 0:
                raise SystemExit(f"empty calibration bin for {name}")
            calibration.append(float(np.mean(values)))
        regime, regime_pass = regime_evidence(candidate_rows)
        criteria = acceptance_criteria(model_metrics, baseline_metrics, calibration, regime_pass)
        result = {
            "candidate": name,
            "model": "Ridge",
            "parameters": {"alpha": 1.0},
            "features": list(feature_names),
            "fold_count": len(folds),
            "observation_count": len(candidate_rows),
            "metrics": model_metrics,
            "baseline_metrics": baseline_metrics,
            "improvements": {
                "r2": model_metrics["r2"] - baseline_metrics["r2"],
                "correlation": model_metrics["correlation"] - baseline_metrics["correlation"],
                "mae_reduction": (baseline_metrics["mae"] - model_metrics["mae"]) / baseline_metrics["mae"],
            },
            "calibration_bin_actual_means": calibration,
            "regimes": regime,
            "criteria": criteria,
            "accepted_development": all(criteria.values()),
            "predictions": candidate_rows,
        }
        checkpoint["candidates"][name]["result"] = result
        atomic_json(checkpoint_path, checkpoint)
        results.append(result)
    output = {
        "schema": "alphalens.gate06.volatility-result.v1",
        "lineage_id": manifest["lineage_id"],
        "execution_manifest_sha256": execution_manifest_hash,
        "dataset_sha256": DATASET_SHA256,
        "protected_data_accessed": False,
        "candidates": results,
    }
    atomic_json(args.output, output)
    print(json.dumps({"execution_manifest_sha256": execution_manifest_hash, "candidates": [{k: v for k, v in result.items() if k != "predictions"} for result in results]}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("output", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
