"""Tests for immutable final model selection aggregation."""

from copy import deepcopy
import unittest
from uuid import UUID

from app.research.final_model_selection import (
    AutomatedTestEvidence,
    FinalModelSelectionError,
    ImmutableArtifact,
    PredictionEvidenceSummary,
    build_final_model_selection_report,
)


FAMILIES = (
    "linear_regression",
    "ridge_regression",
    "random_forest_regression",
    "xgboost_regression",
)
QUALITY = {
    "ridge_regression": 1,
    "random_forest_regression": 2,
    "linear_regression": 3,
    "xgboost_regression": 4,
}
IDS = {
    family: UUID(int=index)
    for index, family in enumerate(FAMILIES, start=1)
}
PROVENANCE = {
    "model_dataset_hash": "d" * 64,
    "feature_pipeline_version": "1.1.0",
    "target_version": "1.0.0",
    "validation_run_id": str(UUID(int=20)),
    "split_hash": "s" * 64,
}


class FinalModelSelectionTests(unittest.TestCase):
    def test_selection_is_deterministic_and_ranks_all_models(self) -> None:
        inputs = _inputs()
        first = build_final_model_selection_report(**inputs)
        second = build_final_model_selection_report(
            **{
                **inputs,
                "explainability": tuple(
                    reversed(inputs["explainability"])
                ),
                "prediction_evidence": tuple(
                    reversed(inputs["prediction_evidence"])
                ),
            }
        )

        self.assertEqual(first.configuration_hash, second.configuration_hash)
        self.assertEqual(first.result_hash, second.result_hash)
        self.assertEqual(first.selected_model_family, "ridge_regression")
        self.assertEqual(
            [
                item["model_family"]
                for item in first.payload["ranking_table"]
            ],
            [
                "ridge_regression",
                "random_forest_regression",
                "linear_regression",
                "xgboost_regression",
            ],
        )

    def test_report_contains_every_required_evidence_domain(self) -> None:
        built = build_final_model_selection_report(**_inputs())

        for family in FAMILIES:
            summary = built.payload["evidence_summary"][family]
            self.assertEqual(
                set(summary["domain_scores"]),
                {
                    "performance",
                    "statistical_evidence",
                    "residual_quality",
                    "market_robustness",
                    "explainability_integrity",
                    "engineering_integrity",
                },
            )
            self.assertEqual(
                len(summary["statistical_evidence"]["comparisons"]),
                9,
            )
        self.assertFalse(
            built.payload["verification"]["final_holdout_evaluated"]
        )
        self.assertFalse(
            built.payload["verification"][
                "new_experimental_evidence_created"
            ]
        )

    def test_holdout_source_artifact_is_rejected(self) -> None:
        inputs = _inputs()
        residual = inputs["residual"]
        payload = deepcopy(residual.payload)
        payload["verification"]["final_holdout_evaluated"] = True
        inputs["residual"] = ImmutableArtifact(
            artifact_id=residual.artifact_id,
            artifact_type=residual.artifact_type,
            report_version=residual.report_version,
            configuration_hash=residual.configuration_hash,
            result_hash=residual.result_hash,
            payload=payload,
            hash_verified=True,
        )

        with self.assertRaisesRegex(
            FinalModelSelectionError,
            "final holdout",
        ):
            build_final_model_selection_report(**inputs)

    def test_missing_tree_explainability_artifact_is_rejected(self) -> None:
        inputs = _inputs()
        inputs["explainability"] = inputs["explainability"][:1]

        with self.assertRaisesRegex(
            FinalModelSelectionError,
            "explainability",
        ):
            build_final_model_selection_report(**inputs)


def _inputs() -> dict:
    comparison_payload = {
        "model_count": 4,
        "final_holdout_evaluated": False,
        "models": [
            {
                "model_family": family,
                "experiment_id": str(IDS[family]),
                "metrics": {
                    "mae": f"0.0{QUALITY[family]}",
                    "rmse": f"0.1{QUALITY[family]}",
                    "directional_accuracy": (
                        f"0.{6 - QUALITY[family]}"
                    ),
                },
                "dataset_hash": PROVENANCE["model_dataset_hash"],
                "feature_pipeline_version": (
                    PROVENANCE["feature_pipeline_version"]
                ),
                "target_version": PROVENANCE["target_version"],
                "validation_run_id": PROVENANCE["validation_run_id"],
                "split_hash": PROVENANCE["split_hash"],
                "deterministic_repeatability": {
                    "status": "verified",
                    "exact_matching_experiment_count": 2,
                },
            }
            for family in FAMILIES
        ],
    }
    statistical_payload = {
        "provenance": PROVENANCE,
        "verification": {"final_holdout_evaluated": False},
        "pairwise_comparisons": _statistical_pairs(),
    }
    residual_payload = {
        "provenance": PROVENANCE,
        "verification": {
            "final_holdout_evaluated": False,
            "deterministic_replay_performed": True,
            "experiment_records_modified": False,
            "model_tuning_performed": False,
        },
        "plot_manifest": _plots(16),
        "model_diagnostics": {
            family: _residual_diagnostic(family) for family in FAMILIES
        },
    }
    regime_payload = {
        "provenance": PROVENANCE,
        "verification": {"final_holdout_evaluated": False},
        "plot_manifest": _plots(12, offset=16),
        "model_regime_analysis": {
            family: _regime_analysis(family) for family in FAMILIES
        },
    }
    explainability = tuple(
        _explainability_artifact(family, index)
        for index, family in enumerate(
            ("random_forest_regression", "xgboost_regression"),
            start=30,
        )
    )
    prediction_evidence = tuple(
        PredictionEvidenceSummary(
            model_family=family,
            observation_count=510,
            prediction_hash_count=102,
            evidence_set_hash=str(QUALITY[family]) * 64,
            hashes_verified=True,
        )
        for family in FAMILIES
    )
    return {
        "comparison": _artifact(
            10,
            "model_comparison_report",
            comparison_payload,
        ),
        "statistical": _artifact(
            11,
            "statistical_validation_report",
            statistical_payload,
        ),
        "residual": _artifact(
            12,
            "residual_diagnostics_report",
            residual_payload,
        ),
        "market_regime": _artifact(
            13,
            "market_regime_analysis_report",
            regime_payload,
        ),
        "explainability": explainability,
        "prediction_evidence": prediction_evidence,
        "test_evidence": AutomatedTestEvidence(
            command="python -m unittest discover -s tests -v",
            tests_run=48,
            status="passed",
        ),
    }


def _artifact(
    identifier: int,
    artifact_type: str,
    payload: dict,
) -> ImmutableArtifact:
    return ImmutableArtifact(
        artifact_id=UUID(int=identifier),
        artifact_type=artifact_type,
        report_version="1.0.0",
        configuration_hash="c" * 64,
        result_hash="r" * 64,
        payload=payload,
        hash_verified=True,
    )


def _statistical_pairs() -> list[dict]:
    pairs: list[dict] = []
    for first_index, first in enumerate(FAMILIES):
        for second in FAMILIES[first_index + 1 :]:
            metrics = {}
            for metric in ("mae", "rmse", "directional_accuracy"):
                if metric == "directional_accuracy":
                    difference = QUALITY[second] - QUALITY[first]
                else:
                    difference = QUALITY[first] - QUALITY[second]
                value = f"{difference / 100:.2f}"
                lower = f"{(difference / 100) - 0.001:.3f}"
                upper = f"{(difference / 100) + 0.001:.3f}"
                metrics[metric] = {
                    "difference_definition": (
                        f"{first}_minus_{second}"
                    ),
                    "mean_difference": value,
                    "confidence_interval_95": {
                        "lower": lower,
                        "upper": upper,
                        "method": "paired_fold_percentile_mean_difference",
                    },
                    "wilcoxon": {
                        "adjusted_p_value": "0.01",
                        "raw_p_value": "0.001",
                        "significant_at_0_05": True,
                        "rank_biserial_correlation": "0.5",
                    },
                    "effect_size": {"paired_cohens_dz": "0.5"},
                    "paired_t_test": {"performed": False},
                }
            pairs.append(
                {
                    "first_model": first,
                    "second_model": second,
                    "metrics": metrics,
                }
            )
    return pairs


def _residual_diagnostic(family: str) -> dict:
    quality = QUALITY[family]
    value = f"0.0{quality}"
    return {
        "overall_residual_summary": {
            "residual_mean": value,
            "mean_absolute_error": value,
            "root_mean_squared_error": value,
        },
        "residual_distribution": {
            "mean": value,
            "median": value,
            "sample_variance": value,
            "skewness": value,
            "excess_kurtosis": value,
        },
        "heteroscedasticity_tests": {
            "white": {"p_value": "0.01"},
            "breusch_pagan": {"p_value": "0.01"},
        },
        "autocorrelation": [
            {"lag": 1, "autocorrelation": value}
        ],
    }


def _regime_analysis(family: str) -> dict:
    quality = QUALITY[family]
    performance = {}
    for regime in (
        "bull_trend",
        "bear_trend",
        "sideways_market",
        "high_volatility_regime",
        "low_volatility_regime",
    ):
        performance[regime] = {
            "mae": f"0.0{quality}",
            "rmse": f"0.1{quality}",
            "directional_accuracy": f"0.{6 - quality}",
        }
    fold_consistency = {
        regime: {
            metric: {
                "coefficient_of_variation": f"0.{quality}",
            }
            for metric in ("mae", "rmse", "directional_accuracy")
        }
        for regime in performance
    }
    return {
        "overall_regime_performance": performance,
        "stability_across_regimes": {
            "metric_spreads": {
                metric: {"performance_spread": f"0.0{quality}"}
                for metric in ("mae", "rmse", "directional_accuracy")
            },
            "fold_consistency": fold_consistency,
        },
    }


def _explainability_artifact(
    family: str,
    identifier: int,
) -> ImmutableArtifact:
    rankings = [
        {
            "feature_name": name,
            "rank": rank,
            "standard_deviation": f"0.00{rank}",
        }
        for rank, name in enumerate(("a", "b", "c"), start=1)
    ]
    methods = {
        "tree_shap": {
            "ranking": [
                {
                    "feature_name": item["feature_name"],
                    "rank": item["rank"],
                    "standard_deviation": None,
                }
                for item in rankings
            ]
        },
        "permutation_importance": {"ranking": rankings},
    }
    if family == "random_forest_regression":
        methods["impurity_feature_importance"] = {
            "ranking": rankings
        }
    return _artifact(
        identifier,
        "model_explainability_artifact",
        {
            "model_family": family,
            "provenance": PROVENANCE,
            "methods": methods,
        },
    )


def _plots(count: int, offset: int = 0) -> list[dict]:
    return [
        {
            "model_family": FAMILIES[index % 4],
            "plot_type": f"plot_{index}",
            "mime_type": "image/svg+xml",
            "content_hash": f"{index + offset:064x}",
        }
        for index in range(count)
    ]


if __name__ == "__main__":
    unittest.main()
