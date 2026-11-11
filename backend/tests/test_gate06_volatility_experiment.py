from __future__ import annotations

import unittest

from scripts.gate06_volatility_experiment import (
    CANDIDATES,
    EXPECTED_FOLDS,
    EXPECTED_OBSERVATIONS,
    FEATURES,
    fold_bounds,
)
from scripts.gate06_volatility_features import GARMAN_KLASS_NAME, PARKINSON_NAME


class VolatilityExperimentContractTests(unittest.TestCase):
    def test_frozen_candidates_are_exactly_the_three_authorized_ridge_variants(self):
        self.assertEqual(
            [candidate[0] for candidate in CANDIDATES],
            [
                "ridge_alpha_1_baseline",
                "ridge_alpha_1_plus_parkinson",
                "ridge_alpha_1_plus_garman_klass",
            ],
        )
        self.assertEqual(CANDIDATES[0][1], FEATURES)
        self.assertEqual(CANDIDATES[1][1], FEATURES + (PARKINSON_NAME,))
        self.assertEqual(CANDIDATES[2][1], FEATURES + (GARMAN_KLASS_NAME,))

    def test_fold_schedule_has_frozen_count_and_observation_budget(self):
        folds = fold_bounds(17_176)
        self.assertEqual(len(folds), EXPECTED_FOLDS)
        self.assertEqual(sum(end - start for _, start, end in folds), EXPECTED_OBSERVATIONS)
        self.assertEqual(folds[0], (500, 750, 850))
        self.assertEqual(folds[-1], (16_800, 17_050, 17_150))

    def test_fold_schedule_rejects_unexpected_population(self):
        with self.assertRaises(SystemExit):
            fold_bounds(17_075)


if __name__ == "__main__":
    unittest.main()
