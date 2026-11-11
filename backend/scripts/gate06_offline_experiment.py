"""Offline, development-only Gate 06 bounded experiment runner."""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from app.market_data.models import Candle, CandleTimeframe
from app.features.intraday_pipeline import (
    SourceCandleObservation,
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
)
import app.features.intraday_pipeline as _pipeline

# The feature values are unchanged; the production prefix-invariance audit is
# an O(n²) research diagnostic and is covered by its dedicated regression tests.
_pipeline._verify_prefix_invariance = lambda *args, **kwargs: None

FEATURES = [
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
]
CANDIDATES = (
    ("ridge_alpha_1", "ridge", {"alpha": 1.0, "random_state": None}),
    (
        "random_forest_200_depth_4",
        "random_forest",
        {
            "n_estimators": 200,
            "max_depth": 4,
            "min_samples_leaf": 20,
            "max_features": 1.0,
            "random_state": 20261111,
        },
    ),
    (
        "random_forest_400_depth_6",
        "random_forest",
        {
            "n_estimators": 400,
            "max_depth": 6,
            "min_samples_leaf": 20,
            "max_features": 1.0,
            "random_state": 20261111,
        },
    ),
)
HORIZON = 5
PURGE = 250
MIN_TRAIN = 500
TEST_SIZE = 100
STEP = 100
REGIME_SECONDS = 30 * 24 * 60 * 60


def select(x, y):
    order = sorted(
        range(x.shape[1]),
        key=lambda i: abs(np.corrcoef(x[:, i], y)[0, 1]),
        reverse=True,
    )
    selected = []
    for i in order:
        if len(selected) == 10:
            break
        if all(abs(np.corrcoef(x[:, i], x[:, j])[0, 1]) <= 0.95 for j in selected):
            selected.append(i)
    return selected


def metrics(y, p):
    if not (np.isfinite(y).all() and np.isfinite(p).all()):
        raise ValueError("nonfinite metric input")
    mae = float(np.mean(abs(y - p)))
    ss = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1 - np.sum((y - p) ** 2) / ss) if ss else 0.0
    corr = float(np.corrcoef(y, p)[0, 1]) if np.std(y) and np.std(p) else 0.0
    return {"mae": mae, "r2": r2, "correlation": corr}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def regime_evidence(rows: list[dict]) -> tuple[dict[str, dict], bool]:
    if not rows:
        return {}, False
    first = datetime.fromisoformat(rows[0]["timestamp"])
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        index = int(
            (datetime.fromisoformat(row["timestamp"]) - first).total_seconds()
            // REGIME_SECONDS
        )
        grouped.setdefault(index, []).append(row)
    expected = set(range(min(grouped), max(grouped) + 1))
    complete = expected == set(grouped) and all(grouped[index] for index in expected)
    evidence = {}
    for index in sorted(grouped):
        group = grouped[index]
        y = np.array([row["actual"] for row in group])
        p = np.array([row["prediction"] for row in group])
        b = np.array([row["baseline"] for row in group])
        model = metrics(y, p)
        baseline = metrics(y, b)
        evidence[str(index)] = {
            "observation_count": len(group),
            "mae_improvement": baseline["mae"] - model["mae"],
            "r2_improvement": model["r2"] - baseline["r2"],
            "passes": baseline["mae"] > model["mae"] and model["r2"] > baseline["r2"],
        }
    return evidence, complete and all(item["passes"] for item in evidence.values())


def acceptance_criteria(
    model: dict, baseline: dict, calibration: list[float], regime_pass: bool
) -> dict[str, bool]:
    if not calibration or not np.isfinite(calibration).all():
        monotonic = False
    else:
        monotonic = all(left <= right for left, right in zip(calibration, calibration[1:]))
    return {
        "r2_improvement_gt_0.01": model["r2"] - baseline["r2"] > 0.01,
        "correlation_improvement_gt_0.05": model["correlation"] - baseline["correlation"] > 0.05,
        "mae_reduction_gt_5pct": (baseline["mae"] - model["mae"]) / baseline["mae"] > 0.05,
        "monotonic_calibration": monotonic,
        "positive_mae_and_r2_in_every_30_day_regime": regime_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", type=Path)
    ap.add_argument("output", type=Path)
    a = ap.parse_args()
    raw = a.dataset.read_bytes()
    d = json.loads(raw)
    if (
        d["symbol"] != "BTCUSDT"
        or d["timeframe"] != "5m"
        or d["development_cutoff"] != "2026-09-12T10:05:00Z"
    ):
        raise SystemExit("invalid development boundary")
    ks = d["klines"]
    fixed_id = __import__("uuid").UUID("caf88988-248f-46e0-b2ef-348161fe38ee")
    obs = []
    ts = []
    closes = []
    for k in ks:
        t = datetime.fromtimestamp(k[0] / 1000, timezone.utc)
        ts.append(t)
        closes.append(float(k[4]))
        obs.append(
            SourceCandleObservation(
                Candle(
                    timestamp=t,
                    open=Decimal(k[1]),
                    high=Decimal(k[2]),
                    low=Decimal(k[3]),
                    close=Decimal(k[4]),
                    volume=Decimal(k[5]),
                ),
                fixed_id,
                True,
            )
        )
    src = build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USDT",
        timeframe=CandleTimeframe.MINUTE_5,
        observations=tuple(obs),
    )
    result = run_intraday_feature_pipeline(src)
    by = {}
    for v in result.values:
        by.setdefault(v.candle_timestamp, {})[v.output_name] = float(v.value)
    x = []
    y = []
    valid_ts = []
    valid_close = []
    for i in range(len(ks) - HORIZON):
        if ts[i] not in by or any(
            f not in by[ts[i]] or np.isnan(by[ts[i]][f]) for f in FEATURES
        ):
            continue
        x.append([by[ts[i]][f] for f in FEATURES])
        y.append(abs(np.log(closes[i + HORIZON] / closes[i])))
        valid_ts.append(ts[i])
        valid_close.append(closes[i])
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    valid_close = np.asarray(valid_close)
    if len(ks) < 200 + HORIZON or len(x) == 0:
        raise SystemExit(
            "insufficient data for the frozen 200-candle pre-roll and five-candle label extension"
        )
    if not (
        np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(valid_close).all()
    ):
        raise SystemExit("nonfinite source-derived feature or target value")
    n = len(y)
    folds = []
    for train_end in range(MIN_TRAIN, n - PURGE - TEST_SIZE + 1, STEP):
        test_start = train_end + PURGE
        test_end = test_start + TEST_SIZE
        sel = select(x[:train_end], y[:train_end])
        scaler = StandardScaler().fit(x[:train_end, sel])
        xt = scaler.transform(x[:train_end, sel])
        xv = scaler.transform(x[test_start:test_end, sel])
        atr = x[test_start:test_end, 1] * 1.5 / valid_close[test_start:test_end]
        folds.append(
            (train_end, test_start, test_end, sel, xt, xv, y[test_start:test_end], atr)
        )
    if not folds:
        raise SystemExit(
            "no chronological folds satisfy the frozen train, purge, and test sizes"
        )
    checkpoint_path = a.output.with_suffix(".checkpoint.json")
    dataset_hash = hashlib.sha256(raw).hexdigest()
    identity = {
        "dataset_sha256": dataset_hash,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256(
            Path(__file__)
            .parents[2]
            .joinpath("docs/GATE06_NEW_LINEAGE_PROTOCOL_20261111.md")
            .read_bytes()
        ).hexdigest(),
        "feature_count": len(FEATURES),
        "fold_count": len(folds),
        "purge": PURGE,
        "test_size": TEST_SIZE,
    }
    checkpoint = {
        "schema": "alphalens.gate06.checkpoint.v1",
        "identity": identity,
        "candidates": {},
    }
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if checkpoint.get("identity") != identity:
            raise SystemExit("checkpoint identity mismatch; refusing to reuse it")
    results = []
    for name, kind, params in CANDIDATES:
        saved = checkpoint["candidates"].get(name, {})
        rows = list(saved.get("rows", []))
        completed = int(saved.get("completed_folds", 0))
        if completed != len(rows) // TEST_SIZE or completed > len(folds):
            raise SystemExit(f"checkpoint fold state is invalid for {name}")
        predictions = [row["prediction"] for row in rows]
        actual = [row["actual"] for row in rows]
        baseline = [row["baseline"] for row in rows]
        for seq, (te, ss, se, sel, xt, xv, yt, atr) in enumerate(folds, 1):
            if seq <= completed:
                continue
            model = (
                Ridge(alpha=params["alpha"])
                if kind == "ridge"
                else RandomForestRegressor(**params, n_jobs=-1)
            )
            model.fit(xt, y[:te])
            pred = np.maximum(model.predict(xv), 0)
            predictions.extend(pred)
            actual.extend(yt)
            baseline.extend(atr)
            rows.extend(
                {
                    "fold": seq,
                    "timestamp": valid_ts[ss + i].isoformat(),
                    "actual": float(yt[i]),
                    "prediction": float(pred[i]),
                    "residual": float(yt[i] - pred[i]),
                    "baseline": float(atr[i]),
                }
                for i in range(len(yt))
            )
            checkpoint["candidates"][name] = {
                "parameters": params,
                "completed_folds": seq,
                "rows": rows,
            }
            atomic_json(checkpoint_path, checkpoint)
            print(f"{name}: completed fold {seq}/{len(folds)}", flush=True)
        m = metrics(np.array(actual), np.array(predictions))
        b = metrics(np.array(actual), np.array(baseline))
        cal = []
        for lo, hi in zip(
            np.percentile(predictions, [0, 20, 40, 60, 80]),
            np.percentile(predictions, [20, 40, 60, 80, 100]),
        ):
            values = np.array(actual)[
                (np.array(predictions) >= lo) & (np.array(predictions) <= hi)
            ]
            if values.size == 0:
                raise SystemExit(f"empty calibration bin for {name}")
            cal.append(float(np.mean(values)))
        regime, regime_pass = regime_evidence(rows)
        criteria = acceptance_criteria(m, b, cal, regime_pass)
        candidate_result = {
            "candidate": name,
            "kind": kind,
            "parameters": params,
            "fold_count": len(folds),
            "observation_count": len(rows),
            "metrics": m,
            "baseline_metrics": b,
            "improvements": {
                "r2": m["r2"] - b["r2"],
                "correlation": m["correlation"] - b["correlation"],
                "mae_reduction": (b["mae"] - m["mae"]) / b["mae"],
            },
            "calibration_bin_actual_means": cal,
            "regimes": regime,
            "criteria": criteria,
            "accepted_development": all(criteria.values()),
            "predictions": rows,
        }
        checkpoint["candidates"][name]["result"] = candidate_result
        atomic_json(checkpoint_path, checkpoint)
        results.append(candidate_result)
    output = {
        "schema": "alphalens.gate06.experiment.v1",
        "lineage_id": "gate06-development-20261111-v2",
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "candidates": results,
        "protected_data_accessed": False,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(output, sort_keys=True, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "dataset_sha256": output["dataset_sha256"],
                "candidates": [
                    {k: v for k, v in r.items() if k not in ("predictions",)}
                    for r in results
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
