import unittest
import json
from tempfile import TemporaryDirectory
from pathlib import Path

from scripts.gate06_offline_experiment import acceptance_criteria, atomic_json, regime_evidence


class Gate06AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.model = {"mae": 0.8, "r2": 0.2, "correlation": 0.2}
        self.baseline = {"mae": 1.0, "r2": 0.1, "correlation": 0.1}

    def test_all_five_criteria_are_required(self):
        criteria = acceptance_criteria(self.model, self.baseline, [1.0, 2.0], True)
        self.assertEqual(
            set(criteria),
            {
                "r2_improvement_gt_0.01",
                "correlation_improvement_gt_0.05",
                "mae_reduction_gt_5pct",
                "monotonic_calibration",
                "positive_mae_and_r2_in_every_30_day_regime",
            },
        )
        self.assertTrue(all(criteria.values()))

    def test_missing_regime_rejects_candidate(self):
        rows = [
            {"timestamp": "2026-07-01T00:00:00+00:00", "actual": 1.0, "prediction": 0.5, "baseline": 1.0},
            {"timestamp": "2026-08-31T00:00:00+00:00", "actual": 1.0, "prediction": 0.5, "baseline": 1.0},
        ]
        evidence, passed = regime_evidence(rows)
        self.assertFalse(passed)
        self.assertEqual(len(evidence), 2)

    def test_nonmonotonic_calibration_rejects_candidate(self):
        criteria = acceptance_criteria(self.model, self.baseline, [1.0, 0.5], True)
        self.assertFalse(criteria["monotonic_calibration"])
        self.assertFalse(all(criteria.values()))

    def test_regime_failure_is_independent_of_other_criteria(self):
        criteria = acceptance_criteria(self.model, self.baseline, [1.0, 2.0], False)
        self.assertFalse(criteria["positive_mae_and_r2_in_every_30_day_regime"])
        self.assertFalse(all(criteria.values()))

    def test_atomic_checkpoint_replacement_leaves_complete_json(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            atomic_json(path, {"fold": 1, "rows": ["complete"]})
            self.assertEqual(json.loads(path.read_text()), {"fold": 1, "rows": ["complete"]})
            atomic_json(path, {"fold": 2, "rows": ["complete", "complete"]})
            self.assertEqual(json.loads(path.read_text())["fold"], 2)


if __name__ == "__main__":
    unittest.main()
