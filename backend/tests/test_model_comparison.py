"""Deterministic model comparison report tests."""

from dataclasses import replace
from decimal import Decimal
import unittest
from uuid import UUID

from app.research.model_comparison import (
    RUNTIME_EVIDENCE_STATUS,
    ComparisonSource,
    build_model_comparison,
)


class ModelComparisonTests(unittest.TestCase):
    def test_rankings_and_hash_are_deterministic(self) -> None:
        sources = _sources()

        first = build_model_comparison(sources)
        second = build_model_comparison(tuple(reversed(sources)))

        self.assertEqual(first.report_hash, second.report_hash)
        self.assertEqual(first.payload, second.payload)
        self.assertEqual(
            [
                item["model_family"]
                for item in first.payload["rankings"]["mae"]
            ],
            [
                "ridge_regression",
                "linear_regression",
                "random_forest_regression",
                "xgboost_regression",
            ],
        )
        self.assertEqual(
            [
                item["model_family"]
                for item in first.payload["rankings"]["rmse"]
            ],
            [
                "ridge_regression",
                "random_forest_regression",
                "linear_regression",
                "xgboost_regression",
            ],
        )
        self.assertEqual(
            [
                item["model_family"]
                for item in first.payload["rankings"][
                    "directional_accuracy"
                ]
            ],
            [
                "random_forest_regression",
                "linear_regression",
                "ridge_regression",
                "xgboost_regression",
            ],
        )
        self.assertFalse(first.payload["final_holdout_evaluated"])
        self.assertFalse(first.payload["model_selection_performed"])

    def test_missing_runtime_and_repeatability_are_explicit(self) -> None:
        report = build_model_comparison(_sources()).payload
        models = {
            model["model_family"]: model for model in report["models"]
        }

        self.assertEqual(
            models["linear_regression"]["runtime"],
            {
                "seconds": None,
                "status": RUNTIME_EVIDENCE_STATUS,
            },
        )
        self.assertEqual(
            models["linear_regression"][
                "deterministic_repeatability"
            ]["status"],
            "not_verified_from_registry",
        )
        self.assertEqual(
            models["random_forest_regression"][
                "deterministic_repeatability"
            ]["status"],
            "verified",
        )

    def test_requires_exactly_four_unique_models(self) -> None:
        sources = _sources()

        with self.assertRaises(ValueError):
            build_model_comparison(sources[:3])
        with self.assertRaises(ValueError):
            build_model_comparison(
                sources[:3] + (replace(sources[0], experiment_id=UUID(int=9)),)
            )


def _sources() -> tuple[ComparisonSource, ...]:
    common = {
        "evaluation_policy_version": "1.1.0",
        "feature_pipeline_version": "1.1.0",
        "target_version": "1.0.0",
        "model_dataset_hash": "a" * 64,
        "validation_run_id": UUID(int=100),
        "split_hash": "b" * 64,
        "evaluated_split_count": 102,
        "skipped_split_count": 26,
        "evaluated_observation_count": 510,
    }
    return (
        ComparisonSource(
            experiment_id=UUID(int=1),
            model_family="linear_regression",
            model_parameters={"fit_intercept": True},
            training_pipeline_version="1.1.0",
            mae=Decimal("0.047"),
            rmse=Decimal("0.068"),
            directional_accuracy=Decimal("0.533"),
            configuration_hash="c" * 64,
            result_hash="d" * 64,
            exact_matching_experiment_count=1,
            **common,
        ),
        ComparisonSource(
            experiment_id=UUID(int=2),
            model_family="ridge_regression",
            model_parameters={"alpha": "1.0"},
            training_pipeline_version="1.1.0",
            mae=Decimal("0.039"),
            rmse=Decimal("0.053"),
            directional_accuracy=Decimal("0.529"),
            configuration_hash="e" * 64,
            result_hash="f" * 64,
            exact_matching_experiment_count=1,
            **common,
        ),
        ComparisonSource(
            experiment_id=UUID(int=3),
            model_family="random_forest_regression",
            model_parameters={"n_estimators": 100},
            training_pipeline_version="1.2.0",
            mae=Decimal("0.052"),
            rmse=Decimal("0.065"),
            directional_accuracy=Decimal("0.547"),
            configuration_hash="1" * 64,
            result_hash="2" * 64,
            exact_matching_experiment_count=2,
            **common,
        ),
        ComparisonSource(
            experiment_id=UUID(int=4),
            model_family="xgboost_regression",
            model_parameters={"n_estimators": 100},
            training_pipeline_version="1.3.0",
            mae=Decimal("0.059"),
            rmse=Decimal("0.073"),
            directional_accuracy=Decimal("0.521"),
            configuration_hash="3" * 64,
            result_hash="4" * 64,
            exact_matching_experiment_count=2,
            **common,
        ),
    )


if __name__ == "__main__":
    unittest.main()
