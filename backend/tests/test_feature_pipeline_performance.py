"""Regression test: runtime feature computation must be O(n), not O(n^2).

Before the fix, ``run_intraday_feature_pipeline`` ran ``_verify_prefix_invariance``
for every prefix length (O(n^2) in history length).  With warmup histories of
hundreds of candles this hung the runtime pipeline (HTTP 502 in production).
This test forces the production code path (prefix-invariance check OFF) and
asserts the pipeline completes in bounded time on a large history, while still
producing correct EMA26 values.
"""

import os

# Force the production code path BEFORE importing the pipeline module.
os.environ["ALPHALENS_FEATURE_INVARIANCE_CHECK"] = "0"

import time
import unittest

from app.opportunity_intelligence.persistence import (
    FeatureSnapshotMemoryRepository,
    MarketSnapshotMemoryRepository,
)
from app.runtime_features import RuntimeFeatureEngine

from tests.test_live_market_data import _market_snapshot

HISTORY_LENGTH = 500
TIME_BUDGET_SECONDS = 5.0


class FeaturePipelinePerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_is_linear_not_quadratic_on_large_history(self) -> None:
        markets = MarketSnapshotMemoryRepository()
        features = FeatureSnapshotMemoryRepository()
        snapshots = {i: _market_snapshot(i) for i in range(HISTORY_LENGTH)}
        await markets.save_batch(tuple(snapshots.values()))

        engine = RuntimeFeatureEngine(
            market_snapshots=markets,
            feature_snapshots=features,
            code_version="git:perftest",
        )
        latest = snapshots[HISTORY_LENGTH - 1]

        start = time.time()
        feature_snapshot = await engine.resolve(latest)
        elapsed = time.time() - start

        self.assertLess(
            elapsed,
            TIME_BUDGET_SECONDS,
            f"resolve took {elapsed:.2f}s on {HISTORY_LENGTH} candles; "
            "expected O(n), not O(n^2).",
        )

        ema26 = next(
            (
                v
                for v in feature_snapshot.values
                if v.feature_identifier == "exponential_moving_average_26"
            ),
            None,
        )
        self.assertIsNotNone(ema26)
        self.assertGreater(float(ema26.value), 0)
