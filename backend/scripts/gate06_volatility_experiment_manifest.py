"""Validate and emit the frozen volatility-experiment identity; never fits."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DATASET_SHA256 = "2825f80df1434ac52eef868cd3606b95b046d7e624d9e0ad84754be494e156b4"
SOURCE_MANIFEST_SHA256 = "4ac7f09116a90a703dc48a6efa6bbd990dd24c7f99651bde707c4f441d990038"
PROTOCOL = "docs/GATE06_VOLATILITY_FEATURE_PROTOCOL_20261111.md"
FOLD_MANIFEST = {
    "scheme": "expanding_chronological",
    "minimum_train_observations": 500,
    "test_observations": 100,
    "step_observations": 100,
    "purge_observations": 250,
    "fold_count": 164,
    "observations_per_candidate": 16400,
}
CANDIDATES = (
    {"name": "ridge_alpha_1_baseline", "features": "existing_17", "alpha": 1.0},
    {"name": "ridge_alpha_1_plus_parkinson", "features": "existing_17+parkinson_volatility_20", "alpha": 1.0},
    {"name": "ridge_alpha_1_plus_garman_klass", "features": "existing_17+garman_klass_volatility_20", "alpha": 1.0},
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if sha256(args.dataset) != DATASET_SHA256:
        raise SystemExit("development dataset hash mismatch")
    if sha256(args.source_manifest) != SOURCE_MANIFEST_SHA256:
        raise SystemExit("source manifest hash mismatch")
    protocol = Path(__file__).parents[2] / PROTOCOL
    features = Path(__file__).with_name("gate06_volatility_features.py")
    manifest = {
        "schema": "alphalens.gate06.volatility-experiment.v1",
        "lineage_id": "gate06-development-20261111-volatility-v1",
        "fitting_performed": False,
        "protected_data_accessed": False,
        "dataset_sha256": sha256(args.dataset),
        "source_manifest_sha256": sha256(args.source_manifest),
        "feature_implementation_sha256": sha256(features),
        "runner_sha256": sha256(Path(__file__)),
        "protocol_sha256": sha256(protocol),
        "dependency_lock_sha256": sha256(Path(__file__).parents[1] / "uv.lock"),
        "development_cutoff": "2026-09-12T10:05:00Z",
        "feature_window": 20,
        "label_extension": 5,
        "purge": 250,
        "fold_manifest": FOLD_MANIFEST,
        "experiment_budget": {
            "candidate_count": 3,
            "maximum_fits": 492,
            "protected_data_accessed": False,
        },
        "candidates": CANDIDATES,
        "acceptance_criteria": [
            "r2_improvement_gt_0.01",
            "correlation_improvement_gt_0.05",
            "mae_reduction_gt_5pct",
            "monotonic_calibration",
            "positive_mae_and_r2_in_every_30_day_regime",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
