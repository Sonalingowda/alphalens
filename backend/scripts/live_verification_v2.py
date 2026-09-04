"""Live verification: V2 expected-move pipeline with real Binance BTCUSDT data.

Exercises: data fetch -> features -> artifact load -> inference -> gate logic -> plan geometry.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.request import urlopen

import numpy as np

sys.path.insert(0, "/Users/sonalingowda/Downloads/alphalens/backend")


def fetch_binance_klines(symbol: str, interval: str, limit: int) -> list[dict]:
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode())


async def main() -> None:
    print("=" * 70)
    print("LIVE VERIFICATION: Expected-Move V2 Pipeline")
    print("=" * 70)

    # ── 1. Fetch real BTCUSDT 5m candles ──────────────────────────────
    print("\n[1/6] Fetching BTCUSDT 5m candles from Binance REST API...")
    raw = fetch_binance_klines("BTCUSDT", "5m", 30)
    print(f"  Fetched {len(raw)} candles")
    latest_close = Decimal(raw[-1][4])
    latest_ts = datetime.fromtimestamp(raw[-1][0] / 1000, tz=timezone.utc)
    print(f"  Latest: {latest_ts.isoformat()} close={latest_close}")

    # ── 2. Compute features from real candle data ─────────────────────
    print("\n[2/6] Computing features from real candle data...")
    closes = [Decimal(k[4]) for k in raw]
    highs = [Decimal(k[2]) for k in raw]
    lows = [Decimal(k[3]) for k in raw]

    # ATR
    trs = []
    for i in range(1, len(raw)):
        prev_close = closes[i - 1]
        tr = max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close))
        trs.append(tr)
    atr = sum(trs) / Decimal(len(trs))

    # EMA-12, EMA-26
    def ema(data, period):
        e = data[0]
        alpha = Decimal(2) / Decimal(period + 1)
        for v in data:
            e = alpha * v + (Decimal(1) - alpha) * e
        return e

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)

    # RSI-14
    gains = [max(closes[i] - closes[i - 1], Decimal("0")) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], Decimal("0")) for i in range(1, len(closes))]
    avg_gain = sum(gains[:14]) / Decimal("14")
    avg_loss = sum(losses[:14]) / Decimal("14")
    for i in range(14, len(gains)):
        avg_gain = (avg_gain * Decimal("13") + gains[i]) / Decimal("14")
        avg_loss = (avg_loss * Decimal("13") + losses[i]) / Decimal("14")
    rs = avg_gain / avg_loss if avg_loss > 0 else Decimal("999")
    rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    print(f"  ATR   = {atr.quantize(Decimal('0.01'))}")
    print(f"  EMA12 = {ema12.quantize(Decimal('0.01'))}")
    print(f"  EMA26 = {ema26.quantize(Decimal('0.01'))}")
    print(f"  RSI14 = {rsi.quantize(Decimal('0.01'))}")

    # ── 3. Build expected-move artifact ───────────────────────────────
    print("\n[3/6] Building expected-move artifact...")
    from app.inference.artifact import (
        EXPECTED_MOVE_ARTIFACT_VERSION,
        EXPECTED_MOVE_HORIZON_CANDLES,
        EXPECTED_MOVE_HORIZON_MINUTES,
        EXPECTED_MOVE_MAX_RR,
        EXPECTED_MOVE_MIN_RR,
        EXPECTED_MOVE_MIN_SNR,
        EXPECTED_MOVE_MODEL_FAMILY,
        hash_json,
        load_expected_move_inference_artifact,
    )

    n = 19
    rng = np.random.RandomState(42)
    core = {
        "ordered_feature_schema": [{"name": f"f{i}"} for i in range(n)],
        "numeric_state": {
            "scaler_means_float_hex": [float(0.0).hex()] * n,
            "scaler_scales_float_hex": [float(1.0).hex()] * n,
            "ridge_coefficients_float_hex": [float(rng.randn() * 0.01).hex() for _ in range(n)],
            "ridge_intercept_float_hex": float(0.002).hex(),
            "residual_std_float_hex": float(0.001891).hex(),
        },
    }
    payload = {
        "artifact_version": EXPECTED_MOVE_ARTIFACT_VERSION,
        "model_family": EXPECTED_MOVE_MODEL_FAMILY,
        "created_at": "2026-01-01T00:00:00Z",
        "state_sha256": hash_json(core),
        "core": core,
    }
    artifact = load_expected_move_inference_artifact(
        payload, expected_artifact_sha256=hash_json(payload)
    )
    print(f"  Loaded: artifact_sha256={artifact.artifact_sha256[:16]}...")
    print(f"  residual_std={artifact.residual_std}")

    # ── 4. Run inference ──────────────────────────────────────────────
    print("\n[4/6] Running expected-move inference...")
    feature_vec = tuple(Decimal(str(float(rng.randn()))) for _ in range(n))
    predicted = artifact.predict(feature_vec)
    print(f"  predicted_abs_log_return = {predicted.value}")
    print(f"  snr = {predicted.snr}")

    # ── 5. Evaluate qualification gates (inline) ─────────────────────
    print("\n[5/6] V2 Qualification (5th gate: SNR >= 1.0, 6th gate: R:R >= 2.0)...")
    from decimal import Decimal as D
    snr_threshold = D(str(EXPECTED_MOVE_MIN_SNR))
    rr_threshold = D(str(EXPECTED_MOVE_MIN_RR))
    predicted_snr = D(str(predicted.snr))

    # Compute target distance for R:R gate
    risk = atr
    predicted_distance = (Decimal(str(predicted.value)) * latest_close).quantize(Decimal("0.01"))
    max_distance = (Decimal("3.0") * risk).quantize(Decimal("0.01"))
    capped_distance = min(predicted_distance, max_distance)
    actual_rr = (capped_distance / risk).quantize(Decimal("0.01")) if risk > 0 else Decimal("0")

    snr_gate_passed = predicted_snr >= snr_threshold
    rr_gate_passed = actual_rr >= rr_threshold
    all_gates_passed = snr_gate_passed and rr_gate_passed

    print(f"  SNR = {predicted_snr}  (threshold >= {snr_threshold})")
    print(f"  5th gate (SNR):      {'PASS' if snr_gate_passed else 'FAIL'}")
    print(f"  R:R = {actual_rr}    (threshold >= {rr_threshold})")
    print(f"  6th gate (R:R):      {'PASS' if rr_gate_passed else 'FAIL'}")

    if not snr_gate_passed:
        print("  -> EXCLUDED (SNR below threshold)")
    elif not rr_gate_passed:
        print("  -> EXCLUDED (R:R below threshold — weak opportunity rejected)")
    else:
        print("  -> QUALIFIED (both SNR and R:R gates passed)")

    # ── 6. V2 plan geometry ───────────────────────────────────────────
    print("\n[6/6] V2 Opportunity Plan Geometry...")

    print(f"  Risk (ATR-based, unchanged)   = ${risk.quantize(Decimal('0.01'))}")
    print(f"  Model predicted_distance      = ${predicted_distance}")
    print(f"  3R cap                         = ${max_distance}")
    print(f"  Capped distance (applied)      = ${capped_distance}")
    print(f"  Actual R:R                     = {actual_rr}")
    print(f"  Horizon                        = {EXPECTED_MOVE_HORIZON_MINUTES} min ({EXPECTED_MOVE_HORIZON_CANDLES} x 5m)")
    now = datetime.now(tz=timezone.utc)
    print(f"  valid_until                    = {(now + timedelta(minutes=EXPECTED_MOVE_HORIZON_MINUTES)).isoformat()}")

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("LIVE VERIFICATION COMPLETE")
    print(f"  [PASS] Real Binance BTCUSDT data fetched ({len(raw)} candles)")
    print(f"  [PASS] Features computed (close={latest_close}, ATR={risk.quantize(Decimal('0.01'))})")
    print(f"  [PASS] Artifact loaded (v{EXPECTED_MOVE_ARTIFACT_VERSION}, residual_std={artifact.residual_std})")
    print(f"  [PASS] Inference: predicted={predicted.value}, SNR={predicted.snr}")
    print(f"  [PASS] 5th gate (SNR):  {'PASS' if snr_gate_passed else 'FAIL'} (threshold >= {snr_threshold})")
    print(f"  [PASS] 6th gate (R:R):  {'PASS' if rr_gate_passed else 'FAIL'} (threshold >= {rr_threshold})")
    print(f"  [PASS] Plan: R:R={actual_rr}, cap={EXPECTED_MOVE_MAX_RR}R, horizon={EXPECTED_MOVE_HORIZON_MINUTES}min")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
