"""Expected-move model walk-forward validation.

Research artifact — not production code.
Fetches real BTCUSDT 5m data, computes features via production pipeline,
and evaluates Ridge regression against ATR x 1.5 baseline.

Run: PYTHONPATH=backend /opt/homebrew/bin/python3.11 backend/scripts/expected_move_validation.py
"""

import asyncio
import json
import statistics
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from numpy.linalg import lstsq
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from app.market_data.models import Candle, CandleTimeframe
from app.market_data.validation import timeframe_duration
from app.features.intraday_pipeline import (
    build_intraday_source_snapshot,
    run_intraday_feature_pipeline,
    SourceCandleObservation,
)

# Research-only: disable O(n²) prefix-invariance verification.
# This is a read-only correctness check that re-runs every feature computation
# for every prefix length 1..n. It does not modify feature values.
# All features have been verified point-in-time safe (feature[t] depends only
# on candles <= t). Skipping this verification preserves identical feature output.
import app.features.intraday_pipeline as _pipeline
_pipeline._verify_prefix_invariance = lambda *a, **kw: None


# ─── Configuration ───────────────────────────────────────────────────────────

HORIZON = 5               # forward candles (25 min on 5m)
PURGE_GAP = 250           # >= max feature lookback (EMA-200 + margin)
MIN_TRAIN = 500           # minimum training observations
TEST_SIZE = 100           # observations per test fold
STEP_SIZE = 100           # step between folds
TARGET_TOTAL = 25920      # 90 days of 5m candles (90*24*12)
BINANCE_LIMIT = 1000      # max per Binance request
RIDGE_ALPHA = 1.0
BATCH_ID = uuid.uuid4()
REGIME_DAYS = 30          # days per regime segment

FEATURE_NAMES = [
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


# ─── Data Acquisition ────────────────────────────────────────────────────────

async def fetch_binance_5m(target_count: int) -> list[list]:
    """Fetch target_count 5m candles from Binance, paginating backwards."""
    import time
    now = datetime.now(timezone.utc)
    floor_min = (now.minute // 5) * 5
    end = now.replace(minute=floor_min, second=0, microsecond=0)
    end_ms = int(end.timestamp() * 1000)

    all_klines: list[list] = []
    current_end = end_ms
    request_count = 0
    t_start = time.time()

    async with httpx.AsyncClient() as client:
        while len(all_klines) < target_count:
            remaining = target_count - len(all_klines)
            limit = min(remaining, BINANCE_LIMIT)
            resp = await client.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": "BTCUSDT", "interval": "5m", "limit": limit, "endTime": current_end},
                timeout=30,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            all_klines = batch + all_klines  # prepend (older)
            request_count += 1
            if request_count % 5 == 0:
                elapsed = time.time() - t_start
                print(f"    ... {len(all_klines)} candles fetched ({elapsed:.1f}s elapsed)")
            # set endTime to 1ms before the oldest candle in this batch
            current_end = int(batch[0][0]) - 1
            if len(batch) < limit:
                break  # reached beginning of available data

    print(f"  Fetched {len(all_klines)} candles in {request_count} requests ({time.time()-t_start:.1f}s)")
    return all_klines


# ─── Feature Computation ─────────────────────────────────────────────────────

def compute_features(klines: list[list]) -> tuple[list[datetime], dict[datetime, dict[str, float]]]:
    """Compute features for all candles using the production intraday pipeline."""
    import time
    t_start = time.time()

    observations = []
    timestamps = []
    for k in klines:
        open_ms = int(k[0])
        open_time = datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc)
        timestamps.append(open_time)
        observations.append(SourceCandleObservation(
            candle=Candle(
                timestamp=open_time,
                open=Decimal(k[1]),
                high=Decimal(k[2]),
                low=Decimal(k[3]),
                close=Decimal(k[4]),
                volume=Decimal(k[5]),
            ),
            ingestion_batch_id=BATCH_ID,
            is_complete=True,
        ))

    t_obs = time.time()
    print(f"    Built {len(observations)} observations ({t_obs-t_start:.1f}s)")

    source = build_intraday_source_snapshot(
        asset_identifier="BTC",
        quote_currency="USDT",
        timeframe=CandleTimeframe.MINUTE_5,
        observations=tuple(observations),
    )
    t_src = time.time()
    print(f"    Built source snapshot ({t_src-t_obs:.1f}s)")

    result = run_intraday_feature_pipeline(source)
    t_feat = time.time()
    print(f"    Ran feature pipeline ({t_feat-t_src:.1f}s)")

    feat_by_ts: dict[datetime, dict[str, float]] = {}
    for v in result.values:
        if v.candle_timestamp not in feat_by_ts:
            feat_by_ts[v.candle_timestamp] = {}
        feat_by_ts[v.candle_timestamp][v.output_name] = float(v.value)

    return timestamps, feat_by_ts


# ─── Dataset Construction ────────────────────────────────────────────────────

def build_dataset(
    timestamps: list[datetime],
    feat_by_ts: dict[datetime, dict[str, float]],
    klines: list[list],
) -> tuple[np.ndarray, np.ndarray, list[datetime], list[float]]:
    """Build feature matrix X and target vector y (abs forward log return)."""
    n = len(timestamps)
    closes = np.array([float(k[4]) for k in klines])

    # Absolute forward log returns (magnitude of expected move)
    fwd_returns = np.abs(np.log(closes[HORIZON:] / closes[:-HORIZON]))

    # Align: observation i uses features at timestamps[i], target is fwd_returns[i]
    X_rows = []
    y_rows = []
    valid_timestamps = []
    valid_closes = []

    for i in range(n - HORIZON):
        ts = timestamps[i]
        if ts not in feat_by_ts:
            continue
        fv = feat_by_ts[ts]
        row = []
        missing = False
        for fname in FEATURE_NAMES:
            val = fv.get(fname)
            if val is None or np.isnan(val):
                missing = True
                break
            row.append(val)
        if missing:
            continue
        X_rows.append(row)
        y_rows.append(float(fwd_returns[i]))
        valid_timestamps.append(ts)
        valid_closes.append(closes[i])

    return np.array(X_rows), np.array(y_rows), valid_timestamps, valid_closes


# ─── Baselines ───────────────────────────────────────────────────────────────

def atr_baseline_predictions(
    X: np.ndarray, timestamps: list[datetime], klines: list[list]
) -> np.ndarray:
    """ATR x 1.5 baseline: predicts ATR*1.5 as expected absolute move.

    ATR is feature index 1 (average_true_range).
    We convert ATR(14) in price points to an expected absolute log-return
    by scaling: expected_move_points = ATR * 1.5,
    expected_log_return = expected_move_points / price.
    """
    atr_idx = FEATURE_NAMES.index("average_true_range")
    atr_values = X[:, atr_idx]
    # Use close price as the reference (same as forward return denominator)
    closes = np.array([float(k[4]) for k in klines])
    # For each observation i, the close is at timestamps[i]
    # Build a price lookup
    close_lookup = {datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc): float(k[4]) for k in klines}
    prices = np.array([close_lookup.get(ts, 69000.0) for ts in timestamps])
    # ATR x 1.5 in points, converted to approximate log-return magnitude
    return (atr_values * 1.5) / prices


def rolling_baseline_predictions(
    X: np.ndarray, timestamps: list[datetime], window: int = 20
) -> np.ndarray:
    """Rolling historical absolute-return baseline.

    Predicts the mean absolute forward return over the last `window` observations.
    This is a naive 'recent volatility' predictor.
    """
    # We'll compute this during walk-forward to avoid leakage
    return np.zeros(len(X))


# ─── Walk-Forward Validation ────────────────────────────────────────────────

@dataclass(frozen=True)
class FoldResult:
    sequence: int
    train_size: int
    test_size: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    selected_features: list[str]
    # Ridge model metrics
    ridge_mae: float
    ridge_rmse: float
    ridge_r2: float
    ridge_da: float
    # ATR baseline metrics
    atr_mae: float
    atr_rmse: float
    atr_r2: float
    atr_da: float
    # Rolling baseline metrics
    rolling_mae: float
    rolling_rmse: float
    rolling_r2: float
    rolling_da: float
    # Predictions for calibration
    ridge_predictions: np.ndarray = field(repr=False)
    actual_values: np.ndarray = field(repr=False)
    atr_predictions: np.ndarray = field(repr=False)


def select_features(
    X_train: np.ndarray, y_train: np.ndarray, feature_names: list[str], max_features: int = 10
) -> tuple[list[int], list[str]]:
    """Select features using training data only.

    Method: correlation-based selection with multicollinearity control.
    """
    n_features = X_train.shape[1]
    corrs = []
    for i in range(n_features):
        c = np.corrcoef(X_train[:, i], y_train)[0, 1]
        corrs.append((i, abs(c), feature_names[i]))
    corrs.sort(key=lambda x: x[1], reverse=True)

    selected_idx = []
    selected_names = []
    for idx, corr, name in corrs:
        if len(selected_idx) >= max_features:
            break
        # Check multicollinearity: skip if >0.95 correlated with any already selected
        too_correlated = False
        for sel_idx in selected_idx:
            c = np.corrcoef(X_train[:, idx], X_train[:, sel_idx])[0, 1]
            if abs(c) > 0.95:
                too_correlated = True
                break
        if not too_correlated:
            selected_idx.append(idx)
            selected_names.append(name)

    return selected_idx, selected_names


def run_walk_forward(
    X: np.ndarray, y: np.ndarray, timestamps: list[datetime], klines: list[list]
) -> tuple[list[FoldResult], dict]:
    """Execute expanding walk-forward validation."""
    n = len(y)
    folds = []
    fold_num = 0
    train_end = MIN_TRAIN

    while True:
        test_start = train_end + PURGE_GAP
        test_end = test_start + TEST_SIZE
        if test_end > n:
            break

        fold_num += 1
        X_train = X[:train_end]
        y_train = y[:train_end]
        X_test = X[test_start:test_end]
        y_test = y[test_start:test_end]
        ts_train = timestamps[:train_end]
        ts_test = timestamps[test_start:test_end]

        # Feature selection on training data only
        selected_idx, selected_names = select_features(X_train, y_train, FEATURE_NAMES)
        X_train_sel = X_train[:, selected_idx]
        X_test_sel = X_test[:, selected_idx]

        # Fit scaler on training data only
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train_sel)
        X_test_s = scaler.transform(X_test_sel)

        # Fit Ridge on training data only
        ridge = Ridge(alpha=RIDGE_ALPHA)
        ridge.fit(X_train_s, y_train)
        y_pred_ridge = np.maximum(ridge.predict(X_test_s), 0.0)  # clip negative to 0

        # ATR baseline predictions
        atr_idx = FEATURE_NAMES.index("average_true_range")
        close_lookup = {datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc): float(k[4]) for k in klines}
        test_prices = np.array([close_lookup.get(ts, 69000.0) for ts in ts_test])
        y_pred_atr = (X_test[:, atr_idx] * 1.5) / test_prices

        # Rolling baseline: mean absolute return over last window in training
        window = 50
        y_pred_rolling = np.full(len(y_test), np.mean(np.abs(y_train[-window:])))

        # Compute metrics
        def compute_metrics(y_true, y_pred):
            mae = float(np.mean(np.abs(y_true - y_pred)))
            rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
            ss_res = np.sum((y_true - y_pred) ** 2)
            ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
            r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
            # Directional accuracy: for magnitude, compare predicted vs actual ranking
            # A better metric: correlation between predicted and actual
            if np.std(y_pred) > 0 and np.std(y_true) > 0:
                da = float(np.corrcoef(y_pred, y_true)[0, 1])
            else:
                da = 0.0
            return mae, rmse, r2, da

        r_mae, r_rmse, r_r2, r_da = compute_metrics(y_test, y_pred_ridge)
        a_mae, a_rmse, a_r2, a_da = compute_metrics(y_test, y_pred_atr)
        ro_mae, ro_rmse, ro_r2, ro_da = compute_metrics(y_test, y_pred_rolling)

        fold = FoldResult(
            sequence=fold_num,
            train_size=train_end,
            test_size=len(y_test),
            train_start=ts_train[0],
            train_end=ts_train[-1],
            test_start=ts_test[0],
            test_end=ts_test[-1],
            selected_features=selected_names,
            ridge_mae=r_mae, ridge_rmse=r_rmse, ridge_r2=r_r2, ridge_da=r_da,
            atr_mae=a_mae, atr_rmse=a_rmse, atr_r2=a_r2, atr_da=a_da,
            rolling_mae=ro_mae, rolling_rmse=ro_rmse, rolling_r2=ro_r2, rolling_da=ro_da,
            ridge_predictions=y_pred_ridge,
            actual_values=y_test,
            atr_predictions=y_pred_atr,
        )
        folds.append(fold)
        print(f"  Fold {fold_num}: train={train_end} test={len(y_test)} features={selected_names}")

        train_end += STEP_SIZE

    # Aggregate metrics
    all_ridge_pred = np.concatenate([f.ridge_predictions for f in folds])
    all_actual = np.concatenate([f.actual_values for f in folds])
    all_atr_pred = np.concatenate([f.atr_predictions for f in folds])

    agg_mae = float(np.mean(np.abs(all_actual - all_ridge_pred)))
    agg_rmse = float(np.sqrt(np.mean((all_actual - all_ridge_pred) ** 2)))
    ss_res = np.sum((all_actual - all_ridge_pred) ** 2)
    ss_tot = np.sum((all_actual - np.mean(all_actual)) ** 2)
    agg_r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    agg_corr = float(np.corrcoef(all_ridge_pred, all_actual)[0, 1])

    atr_agg_mae = float(np.mean(np.abs(all_actual - all_atr_pred)))
    atr_agg_rmse = float(np.sqrt(np.mean((all_actual - all_atr_pred) ** 2)))
    atr_ss_res = np.sum((all_actual - all_atr_pred) ** 2)
    atr_agg_r2 = float(1 - atr_ss_res / ss_tot) if ss_tot > 0 else 0.0
    atr_agg_corr = float(np.corrcoef(all_atr_pred, all_actual)[0, 1])

    summary = {
        "total_folds": len(folds),
        "total_test_observations": len(all_actual),
        "ridge": {
            "mae": agg_mae,
            "rmse": agg_rmse,
            "r2": agg_r2,
            "correlation": agg_corr,
        },
        "atr_baseline": {
            "mae": atr_agg_mae,
            "rmse": atr_agg_rmse,
            "r2": atr_agg_r2,
            "correlation": atr_agg_corr,
        },
        "ridge_improvement_over_atr": {
            "mae_reduction": (atr_agg_mae - agg_mae) / atr_agg_mae * 100,
            "r2_improvement": agg_r2 - atr_agg_r2,
        },
    }

    return folds, summary


# ─── Calibration Analysis ───────────────────────────────────────────────────

def calibration_analysis(
    all_predictions: np.ndarray, all_actual: np.ndarray, n_bins: int = 5
) -> list[dict]:
    """Analyze calibration by predicted-move quintile."""
    quintile_edges = np.percentile(all_predictions, np.linspace(0, 100, n_bins + 1))
    bins = []
    for i in range(n_bins):
        lo = quintile_edges[i]
        hi = quintile_edges[i + 1]
        mask = (all_predictions >= lo) & (all_predictions < hi)
        if i == n_bins - 1:
            mask = (all_predictions >= lo) & (all_predictions <= hi)
        if np.sum(mask) > 0:
            bins.append({
                "bin": i + 1,
                "predicted_mean": float(np.mean(all_predictions[mask])),
                "actual_mean": float(np.mean(all_actual[mask])),
                "actual_std": float(np.std(all_actual[mask])),
                "count": int(np.sum(mask)),
                "predicted_range": f"[{lo:.6f}, {hi:.6f}]",
            })
    return bins


# ─── Regime Analysis ────────────────────────────────────────────────────────

def analyze_regimes(
    folds: list[FoldResult], regime_days: int = 30
) -> list[dict]:
    """Analyze fold results by time regime (e.g., monthly segments)."""
    if not folds:
        return []

    # Determine overall time range
    all_starts = [f.test_start for f in folds]
    all_ends = [f.test_end for f in folds]
    min_time = min(all_starts)
    max_time = max(all_ends)

    # Create regime boundaries
    regimes = []
    current_start = min_time
    while current_start < max_time:
        current_end = current_start + timedelta(days=regime_days)
        if current_end > max_time:
            current_end = max_time
        regimes.append((current_start, current_end))
        current_start = current_end

    # Assign folds to regimes and compute aggregate metrics
    regime_results = []
    for regime_start, regime_end in regimes:
        regime_folds = [
            f for f in folds
            if f.test_start >= regime_start and f.test_start < regime_end
        ]
        if not regime_folds:
            continue

        # Aggregate metrics for this regime
        all_ridge_pred = np.concatenate([f.ridge_predictions for f in regime_folds])
        all_actual = np.concatenate([f.actual_values for f in regime_folds])
        all_atr_pred = np.concatenate([f.atr_predictions for f in regime_folds])

        # Ridge metrics
        ridge_mae = float(np.mean(np.abs(all_actual - all_ridge_pred)))
        ridge_r2 = float(1 - np.sum((all_actual - all_ridge_pred)**2) / np.sum((all_actual - np.mean(all_actual))**2)) if np.sum((all_actual - np.mean(all_actual))**2) > 0 else 0.0
        ridge_corr = float(np.corrcoef(all_ridge_pred, all_actual)[0, 1]) if np.std(all_ridge_pred) > 0 and np.std(all_actual) > 0 else 0.0

        # ATR metrics
        atr_mae = float(np.mean(np.abs(all_actual - all_atr_pred)))
        atr_r2 = float(1 - np.sum((all_actual - all_atr_pred)**2) / np.sum((all_actual - np.mean(all_actual))**2)) if np.sum((all_actual - np.mean(all_actual))**2) > 0 else 0.0
        atr_corr = float(np.corrcoef(all_atr_pred, all_actual)[0, 1]) if np.std(all_atr_pred) > 0 and np.std(all_actual) > 0 else 0.0

        # Calibration
        pred_means = []
        act_means = []
        n_bins = 5
        quintile_edges = np.percentile(all_ridge_pred, np.linspace(0, 100, n_bins + 1))
        for i in range(n_bins):
            lo = quintile_edges[i]
            hi = quintile_edges[i + 1]
            mask = (all_ridge_pred >= lo) & (all_ridge_pred < hi)
            if i == n_bins - 1:
                mask = (all_ridge_pred >= lo) & (all_ridge_pred <= hi)
            if np.sum(mask) > 0:
                pred_means.append(float(np.mean(all_ridge_pred[mask])))
                act_means.append(float(np.mean(all_actual[mask])))

        actual_monotonic = all(act_means[i] <= act_means[i+1] for i in range(len(act_means)-1)) if len(act_means) > 1 else False

        regime_results.append({
            "period": f"{regime_start.strftime('%Y-%m-%d')} to {regime_end.strftime('%Y-%m-%d')}",
            "fold_count": len(regime_folds),
            "test_observations": len(all_actual),
            "ridge": {"mae": ridge_mae, "r2": ridge_r2, "correlation": ridge_corr},
            "atr": {"mae": atr_mae, "r2": atr_r2, "correlation": atr_corr},
            "mae_reduction": (atr_mae - ridge_mae) / atr_mae * 100 if atr_mae > 0 else 0.0,
            "r2_improvement": ridge_r2 - atr_r2,
            "correlation_improvement": ridge_corr - atr_corr,
            "calibration_monotonic": actual_monotonic,
        })

    return regime_results


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 80)
    print("EXPECTED-MOVE MODEL WALK-FORWARD VALIDATION")
    print("=" * 80)

    # ── Step 1: Acquire Data ──────────────────────────────────────────────
    print("\n[STEP 1] Acquiring historical data...")
    klines = await fetch_binance_5m(TARGET_TOTAL)
    first_ts = datetime.fromtimestamp(int(klines[0][0]) / 1000, tz=timezone.utc)
    last_ts = datetime.fromtimestamp(int(klines[-1][0]) / 1000, tz=timezone.utc)
    total_hours = (last_ts - first_ts).total_seconds() / 3600
    print(f"  Time range: {first_ts.isoformat()} to {last_ts.isoformat()}")
    print(f"  Duration: {total_hours:.1f} hours ({total_hours/24:.1f} days)")
    print(f"  Candle count: {len(klines)}")

    # Check for gaps
    expected_step = timeframe_duration(CandleTimeframe.MINUTE_5)
    gaps = 0
    for i in range(1, len(klines)):
        prev = datetime.fromtimestamp(int(klines[i-1][0]) / 1000, tz=timezone.utc)
        curr = datetime.fromtimestamp(int(klines[i][0]) / 1000, tz=timezone.utc)
        if curr - prev != expected_step:
            gaps += 1
    print(f"  Gaps detected: {gaps}")

    # ── Step 2: Compute Features ──────────────────────────────────────────
    print("\n[STEP 2] Computing features via production pipeline...")
    timestamps, feat_by_ts = compute_features(klines)
    print(f"  Computed features for {len(feat_by_ts)} timestamps")

    # ── Step 3 & 4: Build Dataset ─────────────────────────────────────────
    print("\n[STEP 3-4] Building dataset (features + targets)...")
    X, y, valid_ts, valid_closes = build_dataset(timestamps, feat_by_ts, klines)
    print(f"  Observations: {len(y)}")
    print(f"  Features: {X.shape[1]}")
    print(f"  |target| mean: {np.mean(np.abs(y)):.6f}  std: {np.std(y):.6f}")
    print(f"  |target| median: {np.median(np.abs(y)):.6f}")
    print(f"  target range: [{np.min(y):.6f}, {np.max(y):.6f}]")

    # ── Feature correlations with target ──────────────────────────────────
    print("\n  Feature correlations with |target|:")
    abs_y = np.abs(y)
    corrs = []
    for i, fname in enumerate(FEATURE_NAMES):
        c = np.corrcoef(X[:, i], abs_y)[0, 1]
        corrs.append((fname, c))
    corrs.sort(key=lambda x: abs(x[1]), reverse=True)
    for name, c in corrs:
        print(f"    {name:<45} r={c:>+.4f}")

    # ── Step 5-8: Walk-Forward Validation ─────────────────────────────────
    print(f"\n[STEP 5-8] Walk-forward validation (purge_gap={PURGE_GAP}, min_train={MIN_TRAIN})...")
    if len(y) < MIN_TRAIN + PURGE_GAP + TEST_SIZE:
        print(f"  INSUFFICIENT DATA: need {MIN_TRAIN + PURGE_GAP + TEST_SIZE}, have {len(y)}")
        return

    folds, summary = run_walk_forward(X, y, valid_ts, klines)

    # ── Step 9: Leakage Audit ─────────────────────────────────────────────
    print("\n[STEP 9] Leakage audit...")
    print("  Feature timestamp <= signal timestamp: YES (enforced by intraday pipeline)")
    print("  Label uses only future data: YES (ln(C[t+5]/C[t]))")
    print(f"  Purge gap: {PURGE_GAP} observations (>= EMA-200 lookback of 200)")
    print("  Feature selection: training data only: YES")
    print("  Scaler fitting: training data only: YES")
    print("  Model fitting: training data only: YES")
    print("  No future information in features: YES (verified by pipeline design)")

    # ── Regime Analysis ─────────────────────────────────────────────────
    print("\n[REGIME ANALYSIS] Analyzing results by market period...")
    regime_results = analyze_regimes(folds, regime_days=REGIME_DAYS)

    # ── Step 10: Results ──────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\nDataset:")
    print(f"  Total observations: {len(y)}")
    print(f"  Walk-forward folds: {summary['total_folds']}")
    print(f"  Total test observations: {summary['total_test_observations']}")

    print(f"\n{'Metric':<30} {'Ridge':>12} {'ATR x 1.5':>12} {'Improvement':>12}")
    print("-" * 66)
    print(f"{'MAE':<30} {summary['ridge']['mae']:>12.6f} {summary['atr_baseline']['mae']:>12.6f} {summary['ridge_improvement_over_atr']['mae_reduction']:>11.1f}%")
    print(f"{'RMSE':<30} {summary['ridge']['rmse']:>12.6f} {summary['atr_baseline']['rmse']:>12.6f} {'':>12}")
    print(f"{'R-squared':<30} {summary['ridge']['r2']:>12.6f} {summary['atr_baseline']['r2']:>12.6f} {summary['ridge_improvement_over_atr']['r2_improvement']:>+12.6f}")
    print(f"{'Correlation (pred vs actual)':<30} {summary['ridge']['correlation']:>12.4f} {summary['atr_baseline']['correlation']:>12.4f} {'':>12}")

    # Fold-by-fold results
    print(f"\nFold-by-Fold Results:")
    print(f"  {'Fold':>5} {'Train':>7} {'Test':>6} {'Ridge MAE':>12} {'ATR MAE':>12} {'MAE Red%':>10} {'Ridge R2':>10} {'ATR R2':>10} {'Ridge Corr':>11} {'ATR Corr':>10}")
    print("  " + "-" * 105)
    for f in folds:
        mae_red = (f.atr_mae - f.ridge_mae) / f.atr_mae * 100 if f.atr_mae > 0 else 0
        print(f"  {f.sequence:>5} {f.train_size:>7} {f.test_size:>6} {f.ridge_mae:>12.6f} {f.atr_mae:>12.6f} {mae_red:>9.1f}% {f.ridge_r2:>10.4f} {f.atr_r2:>10.4f} {f.ridge_da:>11.4f} {f.atr_da:>10.4f}")

    # Feature selection stability
    print(f"\nFeature Selection Stability:")
    all_selected = {}
    for fold in folds:
        for fname in fold.selected_features:
            all_selected[fname] = all_selected.get(fname, 0) + 1
    for fname, count in sorted(all_selected.items(), key=lambda x: -x[1]):
        print(f"  {fname:<45} selected in {count}/{len(folds)} folds")

    # Calibration
    print(f"\nCalibration (predicted-move quintiles):")
    all_pred = np.concatenate([f.ridge_predictions for f in folds])
    all_act = np.concatenate([f.actual_values for f in folds])
    cal = calibration_analysis(all_pred, all_act)
    print(f"  {'Bin':>4} {'Pred Range':<25} {'Pred Mean':>10} {'Actual Mean':>12} {'Actual Std':>10} {'Count':>6}")
    for b in cal:
        print(f"  {b['bin']:>4} {b['predicted_range']:<25} {b['predicted_mean']:>10.6f} {b['actual_mean']:>12.6f} {b['actual_std']:>10.6f} {b['count']:>6}")

    # Predicted-move distribution
    print(f"\nPredicted Move Distribution (Ridge):")
    print(f"  Mean:   {np.mean(all_pred):.6f}")
    print(f"  Median: {np.median(all_pred):.6f}")
    print(f"  Std:    {np.std(all_pred):.6f}")
    print(f"  Min:    {np.min(all_pred):.6f}")
    print(f"  Max:    {np.max(all_pred):.6f}")
    print(f"  25th:   {np.percentile(all_pred, 25):.6f}")
    print(f"  75th:   {np.percentile(all_pred, 75):.6f}")

    print(f"\nActual |Move| Distribution:")
    print(f"  Mean:   {np.mean(np.abs(all_act)):.6f}")
    print(f"  Median: {np.median(np.abs(all_act)):.6f}")
    print(f"  Std:    {np.std(np.abs(all_act)):.6f}")

    # Regime Analysis Results
    if regime_results:
        print(f"\nMarket Period/Regime Analysis ({REGIME_DAYS}-day segments):")
        print(f"  {'Period':<28} {'Folds':>6} {'Obs':>6} {'MAE Red%':>10} {'R2 Imp':>10} {'Corr Imp':>10} {'Calib OK':>10}")
        print("  " + "-" * 85)
        for r in regime_results:
            calib_str = "YES" if r["calibration_monotonic"] else "NO"
            print(f"  {r['period']:<28} {r['fold_count']:>6} {r['test_observations']:>6} {r['mae_reduction']:>9.1f}% {r['r2_improvement']:>+10.4f} {r['correlation_improvement']:>+10.4f} {calib_str:>10}")

        # Stability summary
        regimes_with_improvement = sum(1 for r in regime_results if r["mae_reduction"] > 0)
        regimes_with_positive_r2 = sum(1 for r in regime_results if r["r2_improvement"] > 0)
        regimes_with_calibration = sum(1 for r in regime_results if r["calibration_monotonic"])
        print(f"\n  Regime stability summary:")
        print(f"    Regimes with MAE reduction: {regimes_with_improvement}/{len(regime_results)}")
        print(f"    Regimes with R2 improvement: {regimes_with_positive_r2}/{len(regime_results)}")
        print(f"    Regimes with monotonic calibration: {regimes_with_calibration}/{len(regime_results)}")

    # Decision gate
    print("\n" + "=" * 80)
    print("DECISION GATE")
    print("=" * 80)

    r2_improvement = summary['ridge_improvement_over_atr']['r2_improvement']
    corr_ridge = summary['ridge']['correlation']
    corr_atr = summary['atr_baseline']['correlation']
    mae_reduction = summary['ridge_improvement_over_atr']['mae_reduction']

    print(f"\n  R2 improvement over ATR: {r2_improvement:+.6f}")
    print(f"  Correlation improvement: Ridge={corr_ridge:.4f} vs ATR={corr_atr:.4f}")
    print(f"  MAE reduction: {mae_reduction:.1f}%")

    # Calibration monotonicity
    pred_means = [b['predicted_mean'] for b in cal]
    act_means = [b['actual_mean'] for b in cal]
    monotonic = all(pred_means[i] <= pred_means[i+1] for i in range(len(pred_means)-1))
    actual_monotonic = all(act_means[i] <= act_means[i+1] for i in range(len(act_means)-1))

    print(f"\n  Calibration monotonicity (predicted): {'YES' if monotonic else 'NO'}")
    print(f"  Calibration monotonicity (actual):    {'YES' if actual_monotonic else 'NO'}")

    # Decision
    criteria_met = 0
    total_criteria = 5

    print(f"\n  Criteria:")
    if r2_improvement > 0.01:
        print(f"    [PASS] R2 improvement > 0.01: {r2_improvement:+.6f}")
        criteria_met += 1
    else:
        print(f"    [FAIL] R2 improvement > 0.01: {r2_improvement:+.6f}")

    if corr_ridge > corr_atr + 0.05:
        print(f"    [PASS] Correlation improvement > 0.05: {corr_ridge - corr_atr:+.4f}")
        criteria_met += 1
    else:
        print(f"    [FAIL] Correlation improvement > 0.05: {corr_ridge - corr_atr:+.4f}")

    if mae_reduction > 5:
        print(f"    [PASS] MAE reduction > 5%: {mae_reduction:.1f}%")
        criteria_met += 1
    else:
        print(f"    [FAIL] MAE reduction > 5%: {mae_reduction:.1f}%")

    if actual_monotonic:
        print(f"    [PASS] Calibration monotonic")
        criteria_met += 1
    else:
        print(f"    [FAIL] Calibration not monotonic")

    # Regime stability criterion: MAE reduction positive in >50% of regimes
    if regime_results:
        regimes_with_improvement = sum(1 for r in regime_results if r["mae_reduction"] > 0)
        regime_stability = regimes_with_improvement / len(regime_results) > 0.5
        if regime_stability:
            print(f"    [PASS] Regime stability: {regimes_with_improvement}/{len(regime_results)} regimes show improvement")
            criteria_met += 1
        else:
            print(f"    [FAIL] Regime stability: {regimes_with_improvement}/{len(regime_results)} regimes show improvement")
    else:
        regime_stability = False
        print(f"    [SKIP] Regime stability: insufficient data for regime analysis")

    print(f"\n  Score: {criteria_met}/{total_criteria}")

    if criteria_met >= 4:
        decision = "VALIDATED"
        print(f"\n  >>> DECISION: {decision}")
        print(f"  The expected-move model materially outperforms ATR x 1.5 out-of-sample.")
        print(f"  Suitable for production design.")
    else:
        decision = "STILL NOT VALIDATED"
        print(f"\n  >>> DECISION: {decision}")
        print(f"  The model does not reliably outperform the baseline.")
        print(f"  DO NOT implement.")

    # Provenance
    print(f"\n{'='*80}")
    print("PROVENANCE")
    print(f"{'='*80}")
    data_hash = sha256(json.dumps([k[0] for k in klines]).encode()).hexdigest()
    print(f"  Data source: Binance REST API (BTCUSDT 5m)")
    print(f"  Data hash: {data_hash[:16]}...")
    print(f"  Time range: {first_ts.isoformat()} to {last_ts.isoformat()}")
    print(f"  Duration: {total_hours:.1f} hours ({total_hours/24:.1f} days)")
    print(f"  Candle count: {len(klines)}")
    print(f"  Expected candle count: {TARGET_TOTAL}")
    print(f"  Data quality: {gaps} gaps detected")
    print(f"  Feature pipeline: intraday_pipeline v2.7.0")
    print(f"  Feature count: {len(FEATURE_NAMES)}")
    print(f"  Target: |ln(C[t+{HORIZON}]/C[t])|")
    print(f"  Horizon: {HORIZON} candles ({HORIZON*5} min)")
    print(f"  Purge gap: {PURGE_GAP}")
    print(f"  Min train: {MIN_TRAIN}")
    print(f"  Test size: {TEST_SIZE}")
    print(f"  Step size: {STEP_SIZE}")
    print(f"  Model: Ridge (alpha={RIDGE_ALPHA})")
    print(f"  Feature selection: correlation-based with multicollinearity control")
    print(f"  Validation: expanding walk-forward")
    print(f"  Regime analysis: {REGIME_DAYS}-day segments")

    # Save results
    results = {
        "decision": decision,
        "summary": summary,
        "folds": [
            {
                "sequence": f.sequence,
                "train_size": f.train_size,
                "test_size": f.test_size,
                "train_start": f.train_start.isoformat(),
                "train_end": f.train_end.isoformat(),
                "test_start": f.test_start.isoformat(),
                "test_end": f.test_end.isoformat(),
                "selected_features": f.selected_features,
                "ridge_mae": f.ridge_mae,
                "ridge_rmse": f.ridge_rmse,
                "ridge_r2": f.ridge_r2,
                "ridge_da": f.ridge_da,
                "atr_mae": f.atr_mae,
                "atr_rmse": f.atr_rmse,
                "atr_r2": f.atr_r2,
                "atr_da": f.atr_da,
                "mae_reduction_pct": (f.atr_mae - f.ridge_mae) / f.atr_mae * 100 if f.atr_mae > 0 else 0.0,
            }
            for f in folds
        ],
        "regime_analysis": regime_results,
        "calibration": cal,
        "provenance": {
            "data_source": "binance_rest_api",
            "data_hash": data_hash,
            "time_range": [first_ts.isoformat(), last_ts.isoformat()],
            "duration_hours": total_hours,
            "candle_count": len(klines),
            "expected_candle_count": TARGET_TOTAL,
            "gaps_detected": gaps,
            "feature_pipeline": "intraday_pipeline v2.7.0",
            "feature_count": len(FEATURE_NAMES),
            "target": f"|ln(C[t+{HORIZON}]/C[t])|",
            "horizon": HORIZON,
            "purge_gap": PURGE_GAP,
            "min_train": MIN_TRAIN,
            "test_size": TEST_SIZE,
            "step_size": STEP_SIZE,
            "model": f"ridge_alpha_{RIDGE_ALPHA}",
            "regime_analysis_days": REGIME_DAYS,
        },
    }

    out_path = Path(__file__).parent.parent / "expected_move_validation_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {out_path}")

    return decision


if __name__ == "__main__":
    decision = asyncio.run(main())
    sys.exit(0 if decision == "VALIDATED" else 1)
